"""A wall finish chosen by the room's purpose stops being a question when the DESIGNER'S OWN total
for painted walls, written on the drawing, agrees with ours.

objektas_h (2026-09-20): nine of eleven rooms opened with the amber „Sienų apdailos brėžinyje neradau —
parinkta pagal patalpos paskirtį. Patikrinkite išklotinėse arba apdailų lentelėje" — on a drawing that
has neither išklotinės nor an apdailų lentelė. What it does have is the designer's legend „Sienų dažai
… 320 m²", and our rooms add up to 320,28 m². The sąmata bills the TOTAL; the designer's own number
confirms it. The figure is a second reading of the same drawing to compare against — never a value we take.
"""
from __future__ import annotations

from extractor.room_facts import build_room_facts

FIGURE = {"page": 6, "label": "Sienų dažai", "value": 320, "unit": "m2", "family": "sienu_dazymas",
          "bbox": [107.0, 562.0, 150.0, 567.0], "page_width": 595, "page_height": 842}


def _project(total_a: float, total_b: float, figures=(FIGURE,), **room_b):
    rooms = [
        {"nr": "01", "puslapio_nr": 1, "paskirtis": "miegamoji", "plotas_m2": 15.0, "walls_paintable_m2": total_a,
         "ceiling_paintable_m2": 15.0},
        {"nr": "02", "puslapio_nr": 1, "paskirtis": "gyvenamoji", "plotas_m2": 21.0, "walls_paintable_m2": total_b,
         "ceiling_paintable_m2": 21.0, **room_b},
    ]
    return {"patalpos": rooms, "_autoriaus_kiekiai": list(figures)}


def _apdaila(project, nr="01"):
    return next(f for f in build_room_facts(project, nr)["facts"] if f["key"] == "apdaila")


def test_the_designers_total_agreeing_with_ours_answers_the_question():
    f = _apdaila(_project(120.28, 200.0))
    assert f["status"] == "read"
    assert f["sentence"] == ("Sienų apdaila — pagal patalpos paskirtį. Visų patalpų dažomų sienų suma 320,28 m² sutampa su "
                             "projekto autoriaus užrašyta 320,00 m² (6 psl.) — kiekvienos patalpos atskirai tikrinti "
                             "nereikia. Lubos — patikrinkite lubų plane.")
    # the evidence is the designer's own legend line, on its sheet
    assert f["source"]["page"] == 6 and f["source"]["kind"] == "planas"
    x0, y0, x1, y1 = f["source"]["rect_pct"]
    assert x0 < 107 / 595 < x1 and y0 < 562 / 842 < y1


def test_a_total_that_disagrees_leaves_the_question_open():
    f = _apdaila(_project(120.0, 150.0))                     # 270 against 320: −16 %
    assert f["status"] == "assumed"
    assert f["sentence"].startswith("Sienų apdailos brėžinyje neradau — parinkta pagal patalpos paskirtį.")
    assert f["source"]["page"] != 6


def test_several_designer_lines_of_the_family_are_added_up():
    parts = ({**FIGURE, "value": 18, "label": "Glaistoma dažoma (akcentinė)"}, {**FIGURE, "value": 202, "label": "Glaistoma dažoma (baltai)"})
    assert _apdaila(_project(100.0, 121.5, figures=parts))["status"] == "read"         # 221,5 against 220: +0,7 %
    assert _apdaila(_project(100.0, 140.0, figures=parts))["status"] == "assumed"      # 240 against 220: +9 %


def test_other_families_and_units_are_not_the_wall_total():
    skirting = {**FIGURE, "family": "grindjuostes", "unit": "m", "value": 320}
    litres = {**FIGURE, "unit": "l", "value": 320}
    assert _apdaila(_project(120.28, 200.0, figures=(skirting, litres)))["status"] == "assumed"
    assert _apdaila(_project(120.28, 200.0, figures=()))["status"] == "assumed"


def test_a_finish_that_was_read_keeps_its_own_sentence():
    read = _project(120.28, 200.0, _tile_read_source="apdailos")
    f = _apdaila(read, "02")
    assert f["status"] == "read" and "projekto autoriaus" not in f["sentence"]
