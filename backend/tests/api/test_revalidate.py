"""Revalidate endpoint — re-runs cross_page_validator + apply_lt_sanity
on saved project payload. Locks the contract that:
  1. The endpoint produces the same `lt_sanity` shape SanityWarningsBanner expects.
  2. Re-runs DON'T accumulate stale warnings — second call should reproduce
     the first call's warnings count, not add to it.
  3. Stale warnings from the bug-fixed parser disappear after revalidation.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from api.revalidate import _revalidate_payload  # noqa: E402


def _two_storey_lt_project() -> dict:
    """Real 2-storey project — pre-fix would be parsed as 9 phantom floors.
    Post-fix the multi-floor reconciliation should see exactly aukštai 1+2."""
    return {
        "patalpos": [
            # 1st floor: bare numbers "1"–"11"
            {"nr": "1",  "pavadinimas": "Holas",       "paskirtis": "holas",       "plotas_m2": 11.55, "perimetras_m": 8.0,  "lubu_aukstis_m": 2.82},
            {"nr": "2",  "pavadinimas": "Katilinė",    "paskirtis": "katiline",    "plotas_m2": 5.9,   "perimetras_m": 5.79, "lubu_aukstis_m": 2.82},
            {"nr": "5",  "pavadinimas": "Kambarys",    "paskirtis": "miegamoji",   "plotas_m2": 12.32, "perimetras_m": 12.79,"lubu_aukstis_m": 2.82},
            {"nr": "11", "pavadinimas": "Garažas",     "paskirtis": "garazas",     "plotas_m2": 35.94, "perimetras_m": 24.27,"lubu_aukstis_m": 2.82},
            # 2nd floor: "X.2" notation
            {"nr": "1.2","pavadinimas": "Holas",       "paskirtis": "holas",       "plotas_m2": 11.55, "perimetras_m": 13.66,"lubu_aukstis_m": 2.82},
            {"nr": "5.2","pavadinimas": "Kambarys",    "paskirtis": "miegamoji",   "plotas_m2": 12.32, "perimetras_m": 9.9,  "lubu_aukstis_m": 2.82},
            {"nr": "9.2","pavadinimas": "Drabužinė",   "paskirtis": "drabuzine",   "plotas_m2": 6.01,  "perimetras_m": 8.46, "lubu_aukstis_m": 2.82},
        ],
        "bendras_plotas_m2": 95.59,
        "warnings": [
            # Pre-existing warning from a different source — must be preserved
            {"level": "INFO", "source": "large_pdf",
             "message": "Large PDF; extraction may be slower"},
            # Stale warning from the buggy parser — must be replaced on revalidate
            {"level": "WARN", "source": "cross_page_validator",
             "field": "aukstas_9.plotas_m2",
             "message": "Aukšto 9 bendras plotas tik 6.01 m² — galimai praleistos patalpos."},
        ],
    }


def test_revalidate_replaces_cross_page_warnings_but_keeps_others():
    """Stale 'aukštas 9' warnings get cleared; large_pdf warning is kept."""
    project = _two_storey_lt_project()
    out = _revalidate_payload(project)
    sources = {w.get("source") for w in out["warnings"]}
    # Pre-existing non-validator warning preserved:
    assert "large_pdf" in sources
    # The single stale warning that referenced "aukstas_9" must be gone —
    # the post-fix parser groups all rooms into floors {1, 2}, never 9.
    stale = [w for w in out["warnings"]
             if w.get("source") == "cross_page_validator"
             and "aukstas_9" in (w.get("field", ""))]
    assert stale == []


def test_revalidate_emits_lt_sanity_mirror_for_ui():
    project = _two_storey_lt_project()
    out = _revalidate_payload(project)
    sanity = out["lt_sanity"]
    # SanityWarningsBanner contract: warnings + summary keys
    assert "warnings" in sanity
    assert "summary" in sanity
    summary = sanity["summary"]
    for k in ("rooms_count", "total_area_m2",
              "warnings_count", "errors", "warnings", "info"):
        assert k in summary
    assert summary["rooms_count"] == 7


def test_revalidate_idempotent_does_not_accumulate_warnings():
    """Running the validator twice yields the same warnings count, not 2× —
    proves that we replace prior cross_page entries, not append."""
    project = _two_storey_lt_project()
    once = _revalidate_payload(project)
    twice = _revalidate_payload(once)
    n_once = len([w for w in once["warnings"] if w.get("source") == "cross_page_validator"])
    n_twice = len([w for w in twice["warnings"] if w.get("source") == "cross_page_validator"])
    assert n_twice == n_once


def test_revalidate_marks_payload_for_audit():
    out = _revalidate_payload(_two_storey_lt_project())
    assert out.get("_revalidated") is True


def test_revalidate_does_not_explode_when_validator_throws(monkeypatch):
    """If a validator rule raises, the endpoint must surface a degraded
    warning rather than 500 — partial success is preferable to full failure."""
    import api.revalidate as mod

    def _bad_validate(_):
        raise RuntimeError("simulated validator crash")

    # Patch the IMPORT inside _revalidate_payload — it imports
    # extractor.cross_page_validator.validate_consistency lazily, so we have
    # to monkeypatch the underlying module entry instead.
    import extractor.cross_page_validator as cpv
    monkeypatch.setattr(cpv, "validate_consistency", _bad_validate)
    out = mod._revalidate_payload(_two_storey_lt_project())
    crashed = [w for w in out["warnings"]
               if w.get("field") == "cross_page_validator"
               and w.get("source") == "cross_page_validator"]
    assert crashed, "validator crash should surface as a soft warning, not raise"
    # …in LITHUANIAN, with no Python internals (2026-07-28 audit): these strings
    # render verbatim in SanityWarningsBanner, so str(exc) leaked stack-y text
    # ("RuntimeError: …", file paths) into the estimator's UI.
    assert "kryžminio puslapių patikrinimo" in crashed[0]["message"]
    assert "simulated validator crash" not in crashed[0]["message"]
    assert "RuntimeError" not in crashed[0]["message"]
