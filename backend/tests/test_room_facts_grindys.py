"""The floor fact says what the FLOOR PLAN draws — or asks, with a direct choice.

Until 2026-09-20 every floor fact was amber („Brėžinys nesako — parinkta pagal
patalpos paskirtį… jei kitokia — pakeiskite paskirtį"), on projects whose
floor-covering sheet says it in plain words or colours, and the only way to
answer was to change the room's PURPOSE, which also changes its walls.
"""
from __future__ import annotations

from extractor.room_facts import build_room_facts


def _grindys(room: dict, project: dict | None = None) -> dict:
    blob = {"puslapiai": [{"nr": 1, "tipas": "floor_plan"}, {"nr": 7, "tipas": "floor_plan"}],
            "patalpos": [{"nr": "1", "puslapio_nr": 1, "paskirtis": "tamburas", "plotas_m2": 4.48, **room}],
            **(project or {})}
    return next(f for f in build_room_facts(blob, "1")["facts"] if f["key"] == "grindys")


def test_a_covering_written_in_the_room_is_quoted_with_its_sheet():
    f = _grindys({"grindu_danga": "plyteles", "grindu_danga_saltinis": "grindu_planas", "plyteles_grindys_m2": 4.48,
                  "_grindu_danga": {"page": 7, "irodymas": "uzrasas", "tekstas": "plytelės 60X60cm 13vnt. 3.95 m²",
                                    "plotas_m2": 3.95, "rect_pct": [0.15, 0.5, 0.24, 0.55]}})
    assert f["status"] == "read" and f["value"] == "plytelės"
    assert f["source"] == {"kind": "grindu_planas", "page": 7, "rect_pct": [0.15, 0.5, 0.24, 0.55]}
    assert f["sentence"] == ("Grindų plane (7 psl.) šioje patalpoje parašyta: „plytelės 60X60cm 13vnt. 3.95 m²“.")
    assert f["editable"] == {"field": "grindu_danga", "kind": "choice"}


def test_a_hatch_is_explained_by_the_legend_line_it_is_drawn_in():
    f = _grindys({"grindu_danga": "minksta", "grindu_danga_saltinis": "grindu_planas", "pvc_grindys_m2": 4.48,
                  "_grindu_danga": {"page": 7, "irodymas": "rastas", "tekstas": "Grindys - ąžuolas, eglutės raštas 98,37 m²",
                                    "plotas_m2": None, "rect_pct": [0.38, 0.39, 0.47, 0.46]}})
    assert f["status"] == "read" and f["value"] == "parketas arba laminatas"
    assert f["sentence"] == ("Grindų plane (7 psl.) ši patalpa nubraižyta tuo pačiu raštu ir spalva kaip legendos "
                             "eilutė „Grindys - ąžuolas, eglutės raštas 98,37 m²“.")
    assert f["source"]["page"] == 7 and f["source"]["kind"] == "grindu_planas"


def test_his_own_choice_is_his():
    f = _grindys({"grindu_danga": "be_dangos", "grindu_danga_saltinis": "user_override"})
    assert f["status"] == "read" and f["value"] == "betonas, be dangos"
    assert f["sentence"] == "Grindų dangą šiai patalpai pasirinkote patys."
    assert f["editable"] == {"field": "grindu_danga", "kind": "choice"}


def test_two_coverings_written_in_one_room_are_shown_and_asked_about():
    f = _grindys({"paskirtis": "gyvenamoji", "pvc_grindys_m2": 37.86,
                  "_grindu_dangos_dvi": {"page": 7, "tekstai": ["laminuota grindų danga 76.65 m²", "plytelės 60X120cm 7.01 m²"]}})
    assert f["status"] == "assumed" and f["value"] == "parketas arba laminatas"
    assert f["source"]["page"] == 7
    assert f["sentence"] == ("Kokia čia grindų danga? Grindų plane (7 psl.) šioje patalpoje parašytos dvi dangos: "
                             "„laminuota grindų danga 76.65 m²“ ir „plytelės 60X120cm 7.01 m²“. Skaičiuoju visą plotą "
                             "kaip „parketas arba laminatas“ — pasirinkite pagrindinę dangą, o kitos plotą pataisykite sąmatoje.")


def test_a_room_the_floor_plan_says_nothing_about_still_asks_but_lets_him_answer_directly():
    f = _grindys({"paskirtis": "miegamoji", "pvc_grindys_m2": 14.26},
                 {"_meta": {"geometrija": {"grindu_dangos": {"lapai": [7], "perskaityta": {"3": "plyteles"}, "dvi_dangos": []}}}})
    assert f["status"] == "assumed" and f["value"] == "parketas arba laminatas"
    assert f["source"]["page"] == 7
    assert f["sentence"] == ("Kokia čia grindų danga? Grindų plane (7 psl.) šiai patalpai dangos neradau — parinkta pagal "
                             "patalpos paskirtį („miegamoji“). Patikrinkite grindų plane ir pasirinkite.")
    assert f["editable"] == {"field": "grindu_danga", "kind": "choice"}
    assert "pakeiskite paskirtį" not in f["sentence"]


def test_a_project_without_a_floor_sheet_asks_the_old_question_with_the_new_answer():
    f = _grindys({"paskirtis": "miegamoji", "pvc_grindys_m2": 14.26})
    assert f["status"] == "assumed"
    assert f["sentence"] == ("Kokia čia grindų danga? Brėžinys nesako — parinkta pagal patalpos paskirtį („miegamoji“). "
                             "Patikrinkite grindų plane ir pasirinkite.")
    assert f["editable"] == {"field": "grindu_danga", "kind": "choice"}


def test_a_room_kept_out_by_choice_keeps_the_reading_of_its_floor():
    f = _grindys({"_neskaiciuoti": True, "plyteles_grindys_m2": 0.0, "grindu_danga": "plyteles",
                  "grindu_danga_saltinis": "grindu_planas",
                  "_grindu_danga": {"page": 7, "irodymas": "uzrasas", "tekstas": "plytelės 3.95 m²", "plotas_m2": 3.95,
                                    "rect_pct": [0.15, 0.5, 0.24, 0.55]}})
    assert f["value"] == "plytelės" and f["status"] == "read"
    assert "pasirinkimu" in f["sentence"]


def test_the_old_exact_tile_area_override_still_reads_as_marked():
    f = _grindys({"plyteles_grindys_m2_override": 8.54, "plyteles_grindys_m2": 8.54})
    assert f["status"] == "read" and f["value"] == "plytelės"
