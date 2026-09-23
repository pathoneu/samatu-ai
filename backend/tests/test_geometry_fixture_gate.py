"""The geometry lane on the real (untracked) drawings, from the cached
extractions: what it reads today must still be read tomorrow. The lists in
fixtures_geometry_gate.json only ever GROW — raise them when a change reads
more, never lower them to make a change pass."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from extractor import geometry_lane as gl  # noqa: E402

GATE = json.loads((Path(__file__).parent / "fixtures_geometry_gate.json").read_text(encoding="utf-8"))


def _fixture(slug: str):
    folder = ROOT / "ground_truth" / slug
    truth, extract = folder / "truth.json", folder / "ai_extract.json"
    if not truth.exists() or not extract.exists():
        return None
    pdf = Path(json.loads(truth.read_text(encoding="utf-8")).get("pdf_path") or "")
    pdf = pdf if pdf.is_absolute() else ROOT / pdf
    if not pdf.is_file():
        return None
    return pdf.read_bytes(), json.loads(extract.read_text(encoding="utf-8"))


@pytest.mark.parametrize("slug", sorted(GATE))
def test_geometry_gate(slug):
    fx = _fixture(slug)
    if fx is None:
        pytest.skip(f"{slug}: drawing not on this machine")
    pdf, extract = fx
    want = GATE[slug]
    parsed = copy.deepcopy(extract)
    extract_perimeters = {str(r["nr"]): r.get("perimetras_m") for r in extract["patalpos"]}
    out = gl.apply_geometry(parsed, pdf)
    rooms = {str(r["nr"]): r for r in parsed["patalpos"]}
    print(f"{slug}: {out['seconds']} s | kontūrai {out['konturai']} | atviros {out['atviros_erdves']} | "
          f"sudėti {out['perimetrai_sudeti']} | tušti {out['perimetrai_tusti']} | {out['konturu_priezastys']}")
    assert set(want["konturai"]) <= set(out["konturai"]), out["konturu_priezastys"]
    assert all(g in out["atviros_erdves"] for g in want["atviros_erdves"])
    for nr, metres in want["perimetrai_sudeti"].items():
        assert rooms[nr].get("perimetras_saltinis") == "matmenu_eilutes", (nr, rooms[nr].get("_perimetras_priezastis"))
        assert abs(rooms[nr]["perimetras_m"] - metres) <= 0.02, (nr, rooms[nr]["perimetras_m"])
        assert rooms[nr]["_perimetras_suma"]["sutampa"] is True
        # every number that was added can be marked on the sheet it is written on — a horizontal or vertical
        # dimension line, or (since 2026-09-21) the slanted line of a slanted wall
        for wall in rooms[nr]["_sienos"]:
            for e in wall["eilutes"]:
                (x0, y0), (x1, y1) = e["line_pct"]
                assert 0 < min(x0, x1, y0, y1) and max(x0, x1, y0, y1) < 1 and (x0, y0) != (x1, y1), (nr, e)
                assert x0 == x1 or y0 == y1 or wall.get("saltinis") == "eilute" and len(wall["eilutes"]) == 1, (nr, e)
    assert all(str(p) in out["sutapdinimas"] for g in out["grupes"] for p in g)
    # the sheets that draw ONE plan lie over each other (objektas_g: two of seven stayed alone until 2026-09-20)
    assert any(set(want["vienas_planas"]) <= set(g) for g in out["grupes"]), out["grupes"]
    for nr, metres in want["atviru_erdviu_iverciai"].items():
        assert rooms[nr]["perimetras_saltinis"] == "atviros_erdves_ivertis"
        assert abs(rooms[nr]["perimetras_m"] - metres) <= 0.05, (nr, rooms[nr]["perimetras_m"])
    # a space two rooms share is divided by the lane's own boundary (2026-09-23): both rooms outlined, the
    # boundary an edge of both and a wall of neither, each room's walls read on their own
    for members in want.get("ribos", []):
        assert members in [r["nariai"] for r in out["ribos"]], out["ribos_nepasiulytos"]
        for nr in members:
            k = rooms[nr]["_konturas"]
            assert k["saltinis"] == "padalinta_programos" and k["menamos"] and rooms[nr]["_atvira_erdve"]["nariai"] == members
            assert rooms[nr]["perimetras_saltinis"] in ("matmenu_eilutes", "konturo_ivertis")
        assert abs(sum(rooms[nr]["perimetras_m"] for nr in members) - rooms[members[0]]["_atvira_erdve"]["perimetras_m"]) <= 0.1
    blanks = [r for r in rooms.values() if r.get("perimetras_saltinis") in ("konturo_ivertis", "atviros_erdves_ivertis")]
    # an estimate is a NUMBER (the sąmata rows are built from it) that the sheet shows as a blank
    assert all(r.get("perimetras_m") and r["perimetras_m"] == r.get("_perimetras_ivertis_m") for r in blanks)
    assert not [r["nr"] for r in rooms.values() if r.get("perimetras_m") is None and extract_perimeters.get(str(r["nr"])) is not None]
    assert len(blanks) >= want["min_tusti_su_iverciu"]
    # a blank is never a silent one: it carries the reason and the estimate to accept
    assert all(r.get("_perimetras_priezastis") and r.get("_perimetras_ivertis_m") for r in blanks)
    # nothing the table, the plan's pairs or a person stated was touched
    for nr, before in ((str(r["nr"]), r) for r in extract["patalpos"]):
        if before.get("perimetras_saltinis") in ("plano_matmenys", "eksplikacija", "user_override", "manual"):
            assert rooms[nr]["perimetras_m"] == before["perimetras_m"]
    # the floor covering the floor plan draws (2026-09-20): what is read stays read, and what the sheet
    # does NOT say is never claimed — a wrong „read" is worse than a question
    floors = out["grindu_dangos"]
    assert floors["lapai"] == want["grindu_lapai"]
    for nr, danga in want["grindu_dangos"].items():
        assert (rooms[nr].get("grindu_danga"), rooms[nr].get("grindu_danga_saltinis")) == (danga, "grindu_planas"), nr
        ev = rooms[nr]["_grindu_danga"]
        assert ev["page"] in want["grindu_lapai"] and ev["tekstas"] and len(ev["rect_pct"]) == 4
    assert set(want["dvi_dangos"]) <= set(floors["dvi_dangos"])
    assert not [nr for nr in want["dangos_neskaitomos"] if rooms[nr].get("grindu_danga")]
    # the openings the wall solid shows in each outlined room's walls (2026-09-20): where they lead and
    # how wide they are, each one placeable on the sheet the room's own outline is drawn on
    for nr, openings in want["angos_sienose"].items():
        rec = rooms[nr]["_angos_sienose"]
        assert rec["page"] == int((rooms[nr].get("_konturas") or {}).get("page") or rooms[nr]["puslapio_nr"]), nr
        for leads_to, width in openings:
            assert [a for a in rec["angos"] if a["i"] == leads_to and abs(a["plotis_m"] - width) <= 0.03], (nr, leads_to, rec["angos"])
        for a in rec["angos"]:
            assert all(0 < v < 1 for pt in a["line_pct"] for v in pt) and 0.05 <= a["storis_m"] <= 0.75, (nr, a)
    assert set(want["angos_sienose"]) <= set(out["angos_sienose"])
    assert not [nr for nr in want["angu_nera"] if "_angos_sienose" in rooms[nr]]
    assert out["seconds"] < 20
