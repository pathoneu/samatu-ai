"""„Atnaujinti patikrinimus" replaces every check it re-runs — a stale one goes.

2026-10-07: 32acc48 fixed a false „GKP lapų skaičius nesutampa: eilutėje 57
vnt., apskaičiuota 35,2 vnt." (`gk_sheets_off`), yet projects saved before the
fix kept showing it after the refresh. Two leaks:

  · the browser merge (frontend/src/lib/sanitySeverity.js mergeSanity) read „the
    refresh returned no §6 row" as „the refresh did not run §6" and kept the old
    row — then saved it back;
  · the server replaced §6 rows by their `source` tag only, and rows saved before
    2026-08-23 carry the code but no tag, so they rode along on every refresh.

What the refresh cannot recompute (a note written only while the drawing was
read) still stays.
"""
from __future__ import annotations

import re
from pathlib import Path

from fastapi.testclient import TestClient

import main as main_mod  # noqa: F401  (must precede `import auth`)
import auth as _auth
import db as _db
from api.revalidate import RECOMPUTED_SOURCES, _revalidate_payload
from extractor import sanity_checks

REPO_ROOT = Path(__file__).resolve().parents[2]

_STALE_GK_MSG = "GKP lapų skaičius nesutampa: eilutėje 57 vnt., apskaičiuota 35,2 vnt. (leistina ±5 %)"
_LARGE_PDF_MSG = "Didelis PDF (64 psl.) — analizė gali užtrukti virš valandos."


def _stored_project() -> dict:
    """A project as saved before the fix: the GKP row it complains about is gone
    (so the check passes now), the paint/floor ratio really is off (5,0×)."""
    stale_gk = {"code": "gk_sheets_off", "severity": "low", "message": _STALE_GK_MSG,
                "hint": "…", "expected": "≈35 vnt.", "actual": "57 vnt."}
    return {
        "patalpos": [
            {"nr": "1", "pavadinimas": "Salonas", "paskirtis": "svetaine",
             "plotas_m2": 100.0, "perimetras_m": 40.0, "lubu_aukstis_m": 2.80,
             "walls_paintable_m2": 500.0, "ceiling_paintable_m2": 100.0},
        ],
        "bendras_plotas_m2": 100.0,
        "warnings": [
            {**stale_gk, "source": "sanity_checks"},
            # the same check, saved before rows were tagged (code, no source)
            {**stale_gk, "message": "GKP lapų skaičius skiriasi nuo formulės."},
            # a legacy untagged copy of a check that STILL fires
            {"code": "paintable_floor_ratio", "severity": "high",
             "message": "Dažomas sienų plotas 5.00× grindų ploto"},
            # written while the drawing was read — the refresh cannot recompute these
            {"level": "WARN", "message": _LARGE_PDF_MSG},
            {"level": "WARN", "source": "perimeter_validator",
             "code": "perimeter_out_of_bounds", "message": "Salonas: perimetras neįmanomas"},
        ],
    }


def _codes(rows, code):
    return [w for w in rows if isinstance(w, dict) and w.get("code") == code]


def test_refresh_drops_the_stale_check_tagged_or_not():
    out = _revalidate_payload(_stored_project())
    assert _codes(out["warnings"], "gk_sheets_off") == []
    assert _codes(out["lt_sanity"]["warnings"], "gk_sheets_off") == []


def test_refresh_keeps_what_it_cannot_recompute():
    out = _revalidate_payload(_stored_project())
    messages = [w.get("message") for w in out["lt_sanity"]["warnings"]]
    assert _LARGE_PDF_MSG in messages
    assert "Salonas: perimetras neįmanomas" in messages


def test_a_check_that_still_fires_stays_once_and_tagged():
    out = _revalidate_payload(_stored_project())
    rows = _codes(out["lt_sanity"]["warnings"], "paintable_floor_ratio")
    assert len(rows) == 1, rows
    assert rows[0]["source"] == "sanity_checks"
    assert rows[0]["severity"] == "high"


def test_refresh_replaces_every_stream_it_names_as_recomputed():
    """RECOMPUTED_SOURCES is what the browser trusts to be the whole truth for
    those streams — so each must really be rebuilt, stale rows dropped."""
    project = _stored_project()
    project["warnings"] += [
        {"level": "WARN", "source": "cross_page_validator", "field": "aukstas_9.plotas_m2",
         "message": "sena kryžminė"},
        {"level": "WARN", "source": "revalidate", "field": "cross_page_validator",
         "message": "sena klaida"},
    ]
    project["_lt_warnings"] = [{"level": "WARN", "patalpa_nr": "1", "message": "sena STR"}]
    out = _revalidate_payload(project)
    messages = {w.get("message") for w in out["lt_sanity"]["warnings"]}
    assert not messages & {"sena kryžminė", "sena klaida", "sena STR"}, messages
    assert set(RECOMPUTED_SOURCES) == {"sanity_checks", "cross_page_validator",
                                       "revalidate", "lt_rules"}


def test_the_endpoint_round_trip_stores_no_stale_check(tmp_path, monkeypatch):
    monkeypatch.setattr(_db, "_DB_PATH", tmp_path / "refresh.db")
    monkeypatch.setattr(_auth, "AUTH_DISABLED", False)
    _db.init_schema()
    _db._migrate_schema()
    user = _db.create_user("u@x.lt", _auth.hash_password("passw0rd123"), name="U")
    pid = "proj-refresh-1"
    blob = _stored_project()
    blob["lt_sanity"] = {"warnings": [
        {"source": "sanity_checks", "code": "gk_sheets_off", "severity": "low",
         "level": "INFO", "message": _STALE_GK_MSG},
        {"source": "large_pdf", "level": "WARNING", "severity": "med",
         "message": _LARGE_PDF_MSG, "room": ""},
    ], "summary": {}}
    _db.upsert_project(pid, {**blob, "id": pid, "name": "t"}, user_id=user["id"])
    c = TestClient(main_mod.app)
    assert c.post("/api/auth/login",
                  json={"email": "u@x.lt", "password": "passw0rd123"}).status_code == 200
    r = c.post(f"/api/projects/{pid}/revalidate")
    assert r.status_code == 200, r.text
    assert _codes(r.json()["lt_sanity"]["warnings"], "gk_sheets_off") == []
    stored = _db.get_project(pid, user_id=user["id"])
    assert _codes(stored["warnings"], "gk_sheets_off") == []
    assert _codes(stored["lt_sanity"]["warnings"], "gk_sheets_off") == []


def test_codes_list_every_code_the_module_emits():
    src = (Path(sanity_checks.__file__)).read_text(encoding="utf-8")
    emitted = set(re.findall(r'code="([a-z0-9_]+)"', src))
    emitted |= set(re.findall(r'"code": "([a-z0-9_]+)"', src))
    assert emitted == set(sanity_checks.CODES), emitted ^ set(sanity_checks.CODES)


def _js_string_array(src: str, name: str) -> list[str]:
    m = re.search(rf"export const {name} = \[(.*?)\];", src, re.S)
    assert m, f"{name} missing from frontend/src/lib/sanitySeverity.js"
    return re.findall(r"'([a-z0-9_]+)'", m.group(1))


def test_the_browser_merge_uses_the_same_lists():
    """The browser decides which rows on screen the refresh replaced. A drift —
    a new §6 code, a new re-run stream — would quietly bring the stale-row bug
    back for exactly that check."""
    src = (REPO_ROOT / "frontend" / "src" / "lib" / "sanitySeverity.js").read_text(encoding="utf-8")
    assert set(_js_string_array(src, "SANITY_CHECK_CODES")) == set(sanity_checks.CODES)
    assert _js_string_array(src, "REFRESH_RECOMPUTES") == list(RECOMPUTED_SOURCES)
