"""„Sudėtis" explains the rows that exist — it never becomes a second truth (togal-v2 W9).

For every „Medžiagos" row of a project, the composition of the work it serves
lists that row with EXACTLY its quantity; a norm is stated only where norma ×
kiekis × (1 + atliekos) reproduces it. Runs on every tracked corpus extract and,
when the local dev DB carries it, on demo-objektas_h.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import db  # noqa: E402
from api.sudetis import apply_rounding, build_sudetis, match_template  # noqa: E402
from extractor.vision_call import (  # noqa: E402
    _build_pozicijos_from_rooms, _emit_v8_compat_fields)

CORPUS = sorted((ROOT.parent / "ground_truth").glob("*/ai_extract.json"))


def _shipped(source: dict) -> dict:
    parsed = {k: v for k, v in source.items() if k not in ("darbu_sarasas", "pozicijos")}
    parsed["pozicijos"] = []
    return _emit_v8_compat_fields(_build_pozicijos_from_rooms(parsed))


def _explained(project: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for r in project["darbu_sarasas"]:
        if r.get("skyrius") == "Medžiagos" or not r.get("id"):
            continue
        for c in build_sudetis(project, r["id"])["komponentai"]:
            if c["is_eilutes"]:
                assert c["eilutes_id"] not in out, f"{c['pavadinimas']} listed under two works"
                out[c["eilutes_id"]] = c
    return out


def _check_every_material_row_is_explained_exactly(project: dict, name: str) -> int:
    mats = [r for r in project["darbu_sarasas"] if r.get("skyrius") == "Medžiagos" and r.get("id")
            and r.get("kiekis") is not None]          # v4 3b: a blank work row's goods are blank too
    explained = _explained(project)
    with_norm = 0
    for m in mats:
        c = explained.get(m["id"])
        assert c is not None, f"{name}: „{m['aprasymas']}“ appears in no composition"
        assert c["kiekis"] == pytest.approx(float(m["kiekis"]), abs=1e-9), (name, m["aprasymas"])
        assert c["sakinys"]
        if c["norma"] is not None:
            with_norm += 1
            w = c["atliekos_proc"] or 0.0
            work = next(r for r in project["darbu_sarasas"] if r.get("aprasymas") == m["susijes_darbas"]
                        and r.get("skyrius") != "Medžiagos")
            assert c["norma"] * float(work["kiekis"]) * (1 + w / 100) == pytest.approx(
                float(m["kiekis"]), abs=max(1.0, 0.003 * float(m["kiekis"]))), (name, m["aprasymas"])
    return with_norm


@pytest.mark.parametrize("fixture", CORPUS, ids=[p.parent.name for p in CORPUS])
def test_corpus_every_material_row_is_explained_with_its_own_quantity(fixture: Path):
    project = _shipped(json.loads(fixture.read_text(encoding="utf-8")))
    _check_every_material_row_is_explained_exactly(project, fixture.parent.name)


def _demo_h() -> dict | None:
    try:
        return db.get_project("demo-objektas_h")
    except Exception:  # noqa: BLE001
        return None


def test_demo_objektas_h_paint_row_shows_putty_and_paint_like_the_material_rows():
    project = _demo_h()
    if not project or not project.get("darbu_sarasas"):
        pytest.skip("demo-objektas_h is not in this checkout's dev DB")
    with_norm = _check_every_material_row_is_explained_exactly(project, "demo-objektas_h")
    assert with_norm >= 30
    paint = next(r for r in project["darbu_sarasas"] if r["aprasymas"] == "Sienų glaistymas/dažymas")
    s = build_sudetis(project, paint["id"])
    assert s["rinkinys"]["id"] == "numatyta-sienu-dazymas" and s["rinkinys"]["is_default"]
    by = {c["pavadinimas"]: c for c in s["komponentai"]}
    rows = {r["aprasymas"]: r for r in project["darbu_sarasas"]}
    for name, unit in (("Glaistas sienoms (pradinis + baigiamasis)", "kg"),
                       ("Dažai sienoms (2 sluoksniai)", "l")):
        assert by[name]["kiekis"] == float(rows[name]["kiekis"])
        assert by[name]["norma"] is not None and by[name]["vnt"] == unit
        assert by[name]["sakinys"].startswith("norma ")
    assert s["komponentai"][0]["rusis"] == "darbas"


# ── pieces ──────────────────────────────────────────────────────────────────

def test_match_template():
    assert match_template("{vieta} plytelių klijavimas", "Vonios sienų plytelių klijavimas") == "Vonios sienų"
    assert match_template("Sienų glaistymas/dažymas{vieta}", "Sienų glaistymas/dažymas") == ""
    assert match_template("Sienų glaistymas/dažymas{vieta}", "Sienų glaistymas/dažymas virš 3 m") == " virš 3 m"
    assert match_template("Dažymo kampų montavimas", "Dažymo kampų montavimas") == ""
    assert match_template("Dažymo kampų montavimas", "Kampų montavimas") is None


def test_rounding_modes_follow_the_engine():
    assert apply_rounding(50.0023, "aukstyn", None) == 51          # gkp_sheet_count
    assert apply_rounding(4091.1, "zemyn", None) == 4091           # int(gkp_total × 30)
    assert apply_rounding(0.4, "artimiausias", 1.0) == 1           # max(1, round(m / 10))
    assert apply_rounding(2.278, "artimiausias", 1.0) == 2


def test_user_component_without_a_material_row_is_computed_and_says_so():
    project = {"darbu_sarasas": [
        {"id": "w1", "skyrius": "Sienų glaistymas dažymas", "aprasymas": "Mano darbas",
         "vnt": "m2", "kiekis": 100.0, "rinkinys_id": "mine"}]}
    own = [{"id": "mine", "name": "Mano", "kodas": "X.1",
            "taikoma": {"aprasymas": "Mano darbas"},
            "komponentai": [{"rusis": "darbas", "pavadinimas": "Darbas", "norma": 1, "vnt": "m2"},
                            {"rusis": "medziaga", "pavadinimas": "Klijai", "norma": 2.5,
                             "vnt": "kg", "atliekos_proc": 10, "kaina": 1.2}]}]
    s = build_sudetis(project, "w1", own)
    assert s["rinkinys"]["id"] == "mine" and s["eilute"]["kodas"] == "X.1"
    klijai = s["komponentai"][1]
    assert klijai["kiekis"] == 275.0 and not klijai["is_eilutes"]
    assert "atliekos 10 %" in klijai["sakinys"] and "tokios eilutės nėra" in klijai["sakinys"]


def test_unknown_row_is_none():
    assert build_sudetis({"darbu_sarasas": []}, "nope") is None


def test_route_404s_and_answers(monkeypatch, tmp_path):
    import main
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "s.db")
    db.init_schema()
    db._migrate_schema()
    blob = _shipped(json.loads(CORPUS[-1].read_text(encoding="utf-8")))
    uid = db.create_user("sudetis@example.test", "x")["id"]
    db.upsert_project("sud-1", {"name": "Bandymas", **blob}, user_id=uid)
    client = TestClient(main.app)
    import auth
    monkeypatch.setattr(auth, "require_user", lambda request: {"id": uid, "is_admin": False})
    work = next(r for r in blob["darbu_sarasas"] if r.get("skyrius") != "Medžiagos" and r.get("id"))
    r = client.get(f"/api/projects/sud-1/rows/{work['id']}/sudetis")
    assert r.status_code == 200, r.text
    assert r.json()["eilute"]["id"] == work["id"]
    assert client.get("/api/projects/sud-1/rows/nera/sudetis").status_code == 404
    assert client.get("/api/projects/nera/rows/x/sudetis").status_code == 404
