"""The CLAUDE.md §6 cross-checks must reach the user LOUD.

A 2026-08 audit found the app's only generalisation safety net muted: three
hand-rolled copies of the `lt_sanity` mirror flattened every warning to
`{level, room, field, value, expected, message}` and defaulted `level` to
"INFO". `extractor/sanity_checks.py` publishes `severity` and deliberately no
`level`, so a `severity="high"` violation — "dažomas plotas 6,1× grindų ploto"
on a project nobody has ever seen — arrived at the banner as a blue INFO row
that is collapsed by default and left out of the counter.

Two of the three copies also read `_lt_warnings` ONLY, so rebuilding the
mirror ("Atnaujinti AI patikrinimus", any Prielaidos recompute) DELETED every
check living in `warnings`: cross-page, scale, §6 sanity, consistency,
perimeter.

These tests lock both properties.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api.revalidate import _revalidate_payload  # noqa: E402
from extractor.sanity_checks import run_all_checks  # noqa: E402
from extractor.sanity_mirror import (  # noqa: E402
    build_lt_sanity,
    resolve_tier,
    to_ui_warning,
)


# ══════════════════════════════════════════════════════════════════════════
# 1 — severity survives the mirror
# ══════════════════════════════════════════════════════════════════════════

def test_high_severity_check_is_not_demoted_to_info():
    """THE bug: `w.get("level", "INFO")` on a severity-only warning."""
    raw = {"code": "paintable_floor_ratio", "severity": "high",
           "message": "Dažomas sienų plotas 6,10× grindų ploto",
           "hint": "Patikrinkite lubų aukštį Prielaidose.",
           "expected": "2,5–4,0×", "actual": "6,10×"}
    ui = to_ui_warning(raw)
    assert ui["severity"] == "high"
    assert ui["level"] == "WARNING"          # NOT "INFO"


def test_mirror_carries_hint_code_actual_and_expected():
    """The row cannot say "…— patikrinkite lubų aukštį Prielaidose" if the
    mirror threw the hint away, and the banner cannot offer the Prielaidos
    jump without the code."""
    ui = to_ui_warning({
        "code": "ceiling_floor_mismatch", "severity": "med",
        "message": "Lubų plotas 0,70× grindų ploto",
        "hint": "Plokščioms luboms tikėtina ~1,0×.",
        "expected": "0,95–1,05×", "actual": "0,70×",
        "source": "sanity_checks",
    })
    assert ui["code"] == "ceiling_floor_mismatch"
    assert ui["hint"].startswith("Plokščioms luboms")
    assert ui["actual"] == "0,70×"
    assert ui["expected"] == "0,95–1,05×"
    assert ui["source"] == "sanity_checks"


def test_authored_error_outranks_its_severity():
    level, severity = resolve_tier({"level": "ERROR", "severity": "low"})
    assert (level, severity) == ("ERROR", "high")


def test_legacy_level_only_warnings_keep_their_tier():
    """No regression for the streams that never had `severity`."""
    assert resolve_tier({"level": "WARN"}) == ("WARNING", "med")
    assert resolve_tier({"level": "INFO"}) == ("INFO", "low")
    assert resolve_tier({"level": "FAIL"}) == ("ERROR", "high")
    assert resolve_tier({}) == ("INFO", "low")


def test_a_bare_string_warning_cannot_take_the_whole_mirror_down():
    """`warnings` has carried plain strings (scale_validator's older shape).
    `w.get(...)` raised, the caller's blanket except swallowed it, and the
    project ended up with NO lt_sanity at all — every check gone."""
    out = build_lt_sanity({
        "patalpos": [{"nr": "1"}],
        "warnings": ["mastelis neaiškus", {"level": "WARN", "message": "x"}],
    })
    assert len(out["warnings"]) == 2
    assert out["warnings"][0]["message"] == "mastelis neaiškus"


# ══════════════════════════════════════════════════════════════════════════
# 2 — every validator stream reaches the banner
# ══════════════════════════════════════════════════════════════════════════

def test_mirror_reads_both_lt_warnings_and_pipeline_warnings():
    out = build_lt_sanity({
        "patalpos": [{"nr": "1"}, {"nr": "2"}],
        "bendras_plotas_m2": 42.44,
        "_lt_warnings": [{"level": "WARN", "patalpa_nr": "1", "message": "STR"}],
        "warnings": [{"severity": "high", "code": "paintable_floor_ratio",
                      "message": "§6", "source": "sanity_checks"}],
    })
    messages = [w["message"] for w in out["warnings"]]
    assert messages == ["STR", "§6"]
    assert out["summary"]["rooms_count"] == 2
    assert out["summary"]["total_area_m2"] == 42.4


def test_summary_counts_severity_tiers_without_redefining_warnings_count():
    out = build_lt_sanity({"warnings": [
        {"severity": "high", "message": "a"},
        {"severity": "med", "message": "b"},
        {"severity": "low", "message": "c"},
        {"level": "ERROR", "message": "d"},
    ]})
    s = out["summary"]
    assert (s["high"], s["medium"], s["low"]) == (2, 1, 1)
    # Historical meaning kept: ERROR + WARNING. The high-severity §6 check is
    # now inside it — before the fix it counted as INFO and vanished.
    assert s["warnings_count"] == 3
    assert (s["errors"], s["warnings"], s["info"]) == (1, 2, 1)


def test_non_numeric_total_area_does_not_kill_the_mirror():
    out = build_lt_sanity({"bendras_plotas_m2": {"oops": 1}, "warnings": []})
    assert out["summary"]["total_area_m2"] == 0.0


# ══════════════════════════════════════════════════════════════════════════
# 3 — "Atnaujinti AI patikrinimus" must not delete checks
# ══════════════════════════════════════════════════════════════════════════

def _project_with_a_loud_violation() -> dict:
    """walls/floor = 5,0× → paintable_floor_ratio at severity "high"."""
    return {
        "patalpos": [
            {"nr": "1", "pavadinimas": "Salonas", "paskirtis": "svetaine",
             "plotas_m2": 100.0, "perimetras_m": 40.0, "lubu_aukstis_m": 2.80,
             "walls_paintable_m2": 500.0, "ceiling_paintable_m2": 100.0},
        ],
        "bendras_plotas_m2": 100.0,
        "warnings": [
            # A stream revalidate does NOT re-run — it must survive the rebuild.
            {"level": "WARN", "source": "perimeter_validator",
             "code": "perimeter_out_of_bounds",
             "message": "Salonas (nr=1): perimetras neįmanomas plotui"},
        ],
    }


def test_revalidate_round_trip_keeps_a_high_severity_check():
    """The headline guarantee: refreshing the checks may not silence one."""
    out = _revalidate_payload(_project_with_a_loud_violation())
    high = [w for w in out["lt_sanity"]["warnings"]
            if w.get("code") == "paintable_floor_ratio"]
    assert high, "the §6 paint/floor check vanished from the mirror"
    assert high[0]["severity"] == "high"
    assert high[0]["level"] == "WARNING"
    assert out["lt_sanity"]["summary"]["high"] >= 1
    assert out["lt_sanity"]["summary"]["warnings_count"] >= 1


def test_revalidate_preserves_streams_it_does_not_rerun():
    out = _revalidate_payload(_project_with_a_loud_violation())
    sources = {w.get("source") for w in out["lt_sanity"]["warnings"]}
    assert "perimeter_validator" in sources, (
        "rebuilding lt_sanity from _lt_warnings alone deleted the other "
        "validator streams — the bug this endpoint had")


def test_revalidate_is_idempotent_for_sanity_checks():
    once = _revalidate_payload(_project_with_a_loud_violation())
    twice = _revalidate_payload(once)
    n1 = len([w for w in once["warnings"] if w.get("source") == "sanity_checks"])
    n2 = len([w for w in twice["warnings"] if w.get("source") == "sanity_checks"])
    assert n1 == n2 > 0, (n1, n2)


def test_revalidate_drops_a_check_that_now_passes():
    """Merging must not mean "never forget": once the numbers are fixed the
    warning has to go, otherwise the banner becomes noise nobody reads."""
    loud = _revalidate_payload(_project_with_a_loud_violation())
    assert any(w.get("code") == "paintable_floor_ratio"
               for w in loud["warnings"])
    loud["patalpos"][0]["walls_paintable_m2"] = 300.0      # ratio 3,0× — in band
    fixed = _revalidate_payload(loud)
    assert not [w for w in fixed["warnings"]
                if w.get("code") == "paintable_floor_ratio"]


def test_sanity_checks_tag_their_source_so_a_rerun_can_replace_them():
    warnings = run_all_checks({"patalpos": [
        {"plotas_m2": 100, "walls_paintable_m2": 150},
    ]})
    assert warnings
    assert all(w["source"] == "sanity_checks" for w in warnings)
    # …and they still carry no `level`: severity is their source of truth.
    assert all("level" not in w for w in warnings)


def test_the_full_extract_shape_reaches_the_banner_loud():
    """End-to-end over the two real modules: §6 checks → mirror."""
    parsed = {
        "patalpos": [{"nr": "1", "plotas_m2": 100.0,
                      "walls_paintable_m2": 500.0}],
        "bendras_plotas_m2": 100.0,
    }
    parsed["warnings"] = run_all_checks(parsed)
    mirror = build_lt_sanity(parsed)
    row = next(w for w in mirror["warnings"]
               if w["code"] == "paintable_floor_ratio")
    assert row["severity"] == "high"
    assert "Prielaidose" in row["hint"]        # the actionable jump target
    assert row["actual"] == "5,00×"            # LT decimal comma
    assert mirror["summary"]["high"] == 1
