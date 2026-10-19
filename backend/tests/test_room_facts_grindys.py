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
                             "patalpos paskirtį („Miegamasis“). Patikrinkite grindų plane ir pasirinkite.")
    assert f["editable"] == {"field": "grindu_danga", "kind": "choice"}
    assert "pakeiskite paskirtį" not in f["sentence"]


def test_a_project_without_a_floor_sheet_asks_the_old_question_with_the_new_answer():
    f = _grindys({"paskirtis": "miegamoji", "pvc_grindys_m2": 14.26})
    assert f["status"] == "assumed"
    assert f["sentence"] == ("Kokia čia grindų danga? Brėžinys nesako — parinkta pagal patalpos paskirtį („Miegamasis“). "
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


def test_his_choice_against_the_drawing_says_what_the_drawing_shows():
    """He may know better than the floor plan — but the sheet does not hide that the two differ."""
    f = _grindys({"grindu_danga": "plyteles", "grindu_danga_saltinis": "user_override", "plyteles_grindys_m2": 4.48,
                  "_grindu_danga": {"danga": "minksta", "page": 7, "irodymas": "rastas", "tekstas": "Grindys - ąžuolas, eglutės raštas",
                                    "plotas_m2": None, "rect_pct": [0.38, 0.39, 0.47, 0.46]}})
    assert f["status"] == "read" and f["value"] == "plytelės"
    assert f["sentence"] == ("Grindų dangą šiai patalpai pasirinkote patys. Grindų plane (7 psl.) nubraižyta kitaip: "
                             "parketas arba laminatas.")
    assert f["source"]["page"] == 7 and f["source"]["rect_pct"] == [0.38, 0.39, 0.47, 0.46]


def test_his_choice_that_agrees_with_the_drawing_is_just_his():
    f = _grindys({"grindu_danga": "plyteles", "grindu_danga_saltinis": "user_override",
                  "_grindu_danga": {"danga": "plyteles", "page": 7, "irodymas": "uzrasas", "tekstas": "plytelės 3.95 m²",
                                    "plotas_m2": 3.95, "rect_pct": [0.15, 0.5, 0.24, 0.55]}})
    assert f["sentence"] == "Grindų dangą šiai patalpai pasirinkote patys."
    assert f["source"]["page"] == 7 and f["source"]["rect_pct"] == [0.15, 0.5, 0.24, 0.55]


# ── the floor sheet's key line beside the fact (Pathon v3 W5-D, D1) ─────────

_KEY = {"_meta": {"grindu_legenda": [
    {"tekstas": "Grindys - ąžuolas, eglutės raštas 98,37 m²", "klase": "minksta", "spalva": [0.55, 0.3, 0.1],
     "page": 7, "rect_pct": [0.7, 0.1, 0.9, 0.12]},
    {"tekstas": "60 x 60cm plytelė, matinė", "klase": "plyteles", "spalva": [0.1, 0.3, 0.9],
     "page": 7, "rect_pct": [0.7, 0.13, 0.9, 0.15]}]}}


def test_a_hatch_reading_shows_the_key_line_it_matched_with_its_colour_and_crop():
    f = _grindys({"grindu_danga": "minksta", "grindu_danga_saltinis": "grindu_planas", "pvc_grindys_m2": 4.48,
                  "_grindu_danga": {"page": 7, "irodymas": "rastas", "danga": "minksta",
                                    "tekstas": "Grindys - ąžuolas, eglutės raštas 98,37 m²",
                                    "plotas_m2": None, "rect_pct": [0.38, 0.39, 0.47, 0.46]}}, _KEY)
    leg = f["legenda"]
    assert leg["page"] == 7 and leg["rect_pct"] == [0.7, 0.1, 0.9, 0.12]
    assert leg["spalvos_vardas"] == "ruda"
    assert leg["sentence"] == "Legenda: parketas arba laminatas — ruda („Grindys - ąžuolas, eglutės raštas 98,37 m²“)."
    # evidence only: the reading's own sentence and value are untouched
    assert f["value"] == "parketas arba laminatas" and f["sentence"].startswith("Grindų plane (7 psl.)")


def test_a_written_label_takes_the_only_key_line_of_its_kind_on_that_sheet():
    f = _grindys({"grindu_danga": "plyteles", "grindu_danga_saltinis": "grindu_planas", "plyteles_grindys_m2": 4.48,
                  "_grindu_danga": {"page": 7, "irodymas": "uzrasas", "danga": "plyteles", "tekstas": "plytelės 3.95 m²",
                                    "plotas_m2": 3.95, "rect_pct": [0.15, 0.5, 0.24, 0.55]}}, _KEY)
    assert f["legenda"]["sentence"].startswith("Legenda: plytelės — mėlyna")


def test_no_key_line_no_legend_and_a_guess_never_gets_one():
    plain = _grindys({"grindu_danga": "plyteles", "grindu_danga_saltinis": "grindu_planas",
                      "_grindu_danga": {"page": 7, "irodymas": "uzrasas", "danga": "plyteles", "tekstas": "plytelės",
                                        "rect_pct": [0.15, 0.5, 0.24, 0.55]}})
    assert "legenda" not in plain
    guessed = _grindys({"plyteles_grindys_m2": 4.48}, _KEY)
    assert "legenda" not in guessed


def test_the_key_line_gets_its_own_crop_url():
    from extractor.room_facts import attach_crop_urls
    f = _grindys({"grindu_danga": "minksta", "grindu_danga_saltinis": "grindu_planas",
                  "_grindu_danga": {"page": 7, "irodymas": "rastas", "danga": "minksta",
                                    "tekstas": "Grindys - ąžuolas, eglutės raštas 98,37 m²", "rect_pct": [0.3, 0.3, 0.4, 0.4]}}, _KEY)
    attach_crop_urls({"facts": [f]}, "demo-x")
    assert f["legenda"]["crop_url"] and "demo-x" in f["legenda"]["crop_url"]


def test_colour_names_are_plain_words():
    from extractor.room_facts import colour_name_lt
    assert colour_name_lt([0.1, 0.3, 0.9]) == "mėlyna"
    assert colour_name_lt([0.1, 0.7, 0.2]) == "žalia"
    assert colour_name_lt([0.95, 0.55, 0.1]) == "oranžinė"
    assert colour_name_lt([0.5, 0.5, 0.5]) is None and colour_name_lt(None) is None
