"""v4 Phase 3b — no sąmata row carries a quantity a model guessed or a default invented (plan R1–R3, R7).

docs/superpowers/research/2026-10-25-row-provenance-inventory.md (where each row comes from),
docs/superpowers/research/2026-10-25-kill-model-rows.md (what changed). The guard runs over:

  · every corpus project's frozen extract through the deterministic tail (the eval's path);
  · objektas_i A and B through the cold runner's app variant, when the contractor's uploads are on this machine
    (`SAMATU_COLD_PDFS` / `SAMATU_COLD_BLOBS`, never in the repository).
"""
from __future__ import annotations

import copy
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from extractor import row_provenance as rp  # noqa: E402
from extractor.vision_call import _build_pozicijos_from_rooms, _recompute_per_room_via_python  # noqa: E402

CORPUS = [ROOT / "ground_truth" / f"objektas_{s}" / "ai_extract.json" for s in "abcdgh"]


def _built(parsed: dict, overrides: dict | None = None) -> dict:
    p = copy.deepcopy(parsed)
    p = _recompute_per_room_via_python(p, overrides if overrides is not None else (p.get("_overrides") or {}))
    return _build_pozicijos_from_rooms(p)


def _room(nr="1", **kw):
    r = {"nr": nr, "pavadinimas": "Svetainė", "paskirtis": "gyvenamoji", "plotas_m2": 20.0,
         "perimetras_m": 18.0, "lubu_aukstis_m": 2.7, "elementai": [{"tipas": "duris", "kiekis": 1}]}
    r.update(kw)
    return r


# ── the guard ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("path", [p for p in CORPUS if p.is_file()], ids=lambda p: p.parent.name)
def test_no_corpus_row_carries_a_model_or_default_number(path: Path):
    out = _built(json.loads(path.read_text(encoding="utf-8")))
    rows = out["pozicijos"]
    assert all(p.get(rp.KILME_KEY) for p in rows), [p["aprasymas"] for p in rows if not p.get(rp.KILME_KEY)]
    assert rp.illegal_rows(rows) == []
    for p in rows:
        if p.get(rp.REASON_KEY):
            assert p["kiekis"] is None and p.get("_assumption") == p[rp.REASON_KEY], p["aprasymas"]


def _cold_paths():
    pdfs, blobs = os.environ.get("SAMATU_COLD_PDFS"), os.environ.get("SAMATU_COLD_BLOBS")
    if not pdfs or not blobs:
        return []
    return [(Path(pdfs) / f"{pid}.pdf", Path(blobs) / f"{pid}.json")
            for pid in ("559e17ce-e97c-4cd0-a768-5fbf202f7d72", "b0d5261a-b818-44bb-a679-f4db9c7eea92")]


@pytest.mark.integration
@pytest.mark.parametrize("pdf,blob", _cold_paths() or [pytest.param(None, None, marks=pytest.mark.skip(
    reason="objektas_i uploads not on this machine (SAMATU_COLD_PDFS / SAMATU_COLD_BLOBS)"))])
def test_objektas_i_cold_run_has_no_model_or_default_number(pdf, blob):
    if not pdf.is_file() or not blob.is_file():
        pytest.skip("objektas_i upload not on this machine")
    sys.path.insert(0, str(ROOT / "scripts" / "cold_run"))
    import run_cold
    raw = json.loads(blob.read_text())
    data = raw.get("data") if isinstance(raw.get("data"), dict) else raw
    res = run_cold.project_run("objektas_i", pdf.stem, pdf, data)
    sam = res["app"]["samata"]
    assert sam["illegal"] == []
    by_label = {r["aprasymas"]: r for r in sam["rows"]}
    # the rows the manager's walk named
    assert by_label["LED nišų glaistymas/dažymas"]["kiekis"] == 24.0                      # the legend
    for label in ("Šiukšlių išvežimas (statybinės atliekos)", "Apsauginės dangos / juostos darbų metu",
                  "Ortakių montavimas — suveskite ilgį", "GKP lubų montavimas (standartinis aukštis)",
                  "Durų angų paruošimas beapvadinėms durims", "Sienų glaistymas/dažymas"):
        assert by_label[label]["kiekis"] is None and by_label[label]["priezastis"], label
    assert not any(r["aprasymas"].startswith("Ortakių D125") for r in sam["rows"])


# ── the pieces ─────────────────────────────────────────────────────────────

def test_perimeter_classes():
    assert rp.perimeter_class({"perimetras_m": 12, "perimetras_saltinis": "matmenu_eilutes"}) == rp.DRAWING
    assert rp.perimeter_class({"perimetras_m": 12, "perimetras_saltinis": "konturo_ivertis"}) == rp.DRAWING
    assert rp.perimeter_class({"perimetras_m": 0, "_perimetras_ivertis_m": 14.2}) == rp.DRAWING
    assert rp.perimeter_class({"perimetras_m": 12}) == "model"                 # Pass-1's figure
    assert rp.perimeter_class({"perimetras_m": 12, "perimetras_saltinis": "zoom"}) == "model"
    assert rp.perimeter_class({"plotas_m2": 12}) == "default"                  # the square from the area


def test_height_classes():
    parsed: dict = {}
    assert rp.height_class({"lubu_aukstis_m": 2.8, "lubu_aukstis_saltinis": "ceiling_plan_marker"}, parsed) == rp.DRAWING
    assert rp.height_class({"lubu_aukstis_m": 2.82, "lubu_aukstis_saltinis": "section_average"}, parsed) == "default"
    assert rp.height_class({"lubu_aukstis_m": 2.2, "lubu_aukstis_saltinis": "per_room"}, parsed) == "model"
    marked = {"_lubu_aukstis_saltinis": rp.PROJECT_HEIGHT_FROM_TEXT}
    assert rp.height_class({"lubu_aukstis_m": 2.7, "lubu_aukstis_saltinis": "section_average"}, marked) == rp.DRAWING
    his = {"_overrides": {"lubu_auksciai": {"7": 2.6}}}
    assert rp.height_class({"nr": "7", "lubu_aukstis_m": 2.6, "lubu_aukstis_saltinis": "per_room"}, his) == rp.DRAWING
    assert rp.height_class({"lubu_aukstis_m": 2.7}, parsed, [2.7, 2.7]) == rp.DERIVED   # „kaip kitose"


def test_heights_fill_from_the_read_rooms_or_stay_empty():
    rooms = [_room("1", lubu_aukstis_saltinis="ceiling_plan_marker", lubu_aukstis_m=2.9),
             _room("2", lubu_aukstis_saltinis="per_room", lubu_aukstis_m=2.2)]
    assert rp.fill_heights_from_read(rooms, {}) == 1
    assert (rooms[1]["lubu_aukstis_m"], rooms[1]["lubu_aukstis_saltinis"]) == (2.9, rp.SAME_AS_OTHERS)
    none = [_room("1", lubu_aukstis_saltinis="section_average", lubu_aukstis_m=2.82)]
    rp.fill_heights_from_read(none, {})
    assert none[0]["lubu_aukstis_m"] is None and none[0]["_lubu_aukstis_modelio"] == 2.82


def test_walls_wait_for_the_height_and_come_back_with_his_answer():
    room = _room(perimetras_saltinis="matmenu_eilutes")
    rows = _built({"patalpos": [room], "santrauka": {}})["pozicijos"]
    walls = next(p for p in rows if p["aprasymas"].startswith("Sienų glaistymas/dažymas"))
    assert walls["kiekis"] is None and "Kokio aukščio lubos" in walls["_tuscia_priezastis"]
    answered = {"patalpos": [room], "santrauka": {}, "_overrides": {"lubu_auksciai": {"1": 2.7}}}
    rows = _built(answered)["pozicijos"]
    walls = next(p for p in rows if p["aprasymas"].startswith("Sienų glaistymas/dažymas"))
    assert walls["kiekis"] > 0 and walls["_kilme"] == rp.DERIVED


def test_a_model_perimeter_blanks_the_wall_rows_and_names_the_room():
    room = _room(lubu_aukstis_saltinis="plano_uzrasas")                     # Pass-1 perimeter, read height
    rows = _built({"patalpos": [room], "santrauka": {}})["pozicijos"]
    for label in ("Sienų glaistymas/dažymas", "Dažymo kampų montavimas", "Grindjuosčių sumontavimas"):
        row = next(p for p in rows if p["aprasymas"].startswith(label))
        assert row["kiekis"] is None and "patalpose 1 perimetras neperskaitytas" in row["_tuscia_priezastis"].lower()


def test_ducts_rubbish_and_protection_are_blank_never_a_constant():
    p = {"patalpos": [_room(perimetras_saltinis="matmenu_eilutes", lubu_aukstis_saltinis="plano_uzrasas")],
         "santrauka": {}, "_vector_symbols": {"difuzoriai": {"defined": True, "count": 5, "sakinys": "x"}},
         "detected_symbols_summary": {"ortakiai_d125_m": 25}}
    rows = _built(p)["pozicijos"]
    vent = [r for r in rows if r["skyrius"] == "Ventiliacijos darbai"]
    assert len(vent) == 3 and all(r["kiekis"] is None and r["_tuscia_priezastis"] for r in vent)
    for label in ("Šiukšlių išvežimas", "Apsauginės dangos"):
        row = next(r for r in rows if r["aprasymas"].startswith(label))
        assert row["kiekis"] is None and row["_tuscia_priezastis"]
    assert next(r for r in rows if r["aprasymas"].startswith("Statybvietės"))["kiekis"] == 1


def test_gkp_ceilings_only_where_the_ceiling_plan_marks_the_room():
    base = dict(perimetras_saltinis="matmenu_eilutes", lubu_tipas="gkp")
    unmarked = _built({"patalpos": [_room(lubu_aukstis_saltinis="plano_uzrasas", **base)], "santrauka": {}})
    row = next(r for r in unmarked["pozicijos"] if r["aprasymas"].startswith("GKP lubų montavimas"))
    assert row["kiekis"] is None and "20,00 m²" in row["_tuscia_priezastis"]
    assert not [r for r in unmarked["pozicijos"] if r["aprasymas"].startswith("GKP lapai luboms")]
    marked = _built({"patalpos": [_room(lubu_aukstis_saltinis="ceiling_plan_marker", **base)], "santrauka": {}})
    row = next(r for r in marked["pozicijos"] if r["aprasymas"].startswith("GKP lubų montavimas"))
    assert row["kiekis"] == 20.0 and row["_kilme"] == rp.DRAWING


def test_the_led_legend_reading():
    figs = [{"page": 7, "label": "LED juosta šviesos šaltinis", "value": 24.0, "unit": "m", "family": "led"},
            {"page": 8, "label": "LED juosta šviesos šaltinis", "value": 24.0, "unit": "m", "family": "led"},
            {"page": 7, "label": "Priglaistoma LED juosta", "value": 2.4, "unit": "m", "family": "led"}]
    got = rp.led_legend_length({"_autoriaus_kiekiai": figs})
    assert got["m"] == 24.0 and "2,40 m" in got["sakinys"]          # a legend repeated on two sheets counts once
    assert rp.led_legend_length({"_autoriaus_kiekiai": figs[2:]}) is None
