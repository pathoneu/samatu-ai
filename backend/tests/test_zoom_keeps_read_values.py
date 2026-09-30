"""The zoomed re-read (Step 2.5) never replaces a value the drawing states or the contractor set.

Audit 2026-09-29 (vision-pipeline-3, geometry-lanes-1): `_apply_zoom_refinements` protected a perimeter
only for three labels and replaced the ceiling height with no source check at all, while the old label
stayed on the room — objektas_h's summed 16,01 m became the zoom's 13,40 m and still read „sudėjau plane
užrašytus", and a bathroom's printed 2,8 m altitude became 3,3 m. Made-up rooms only; no API.
"""
from __future__ import annotations

import pytest

from extractor.vision_call import READ_SOURCES, ZOOM_SOURCE, _apply_zoom_refinements

_ZOOM = {"confidence_zoom": "high",
         "perimetras_saltinis": "from_zoom", "perimetras_m": 13.4,
         "plotas_saltinis": "from_zoom", "plotas_m2": 11.68,
         "lubu_aukstis_m": 3.3}


@pytest.mark.parametrize("label", READ_SOURCES["perimetras_saltinis"])
def test_a_read_perimeter_keeps_its_value_and_label(label):
    room = {"nr": "09", "perimetras_m": 16.01, "perimetras_saltinis": label}
    _apply_zoom_refinements(room, dict(_ZOOM))
    assert room["perimetras_m"] == 16.01 and room["perimetras_saltinis"] == label
    assert room["_perimetras_zoom_m"] == 13.4, "the rejected figure is kept beside it"
    assert any(c.startswith("perimetras (zoom)") for c in room["_zoom_changes"])


@pytest.mark.parametrize("label", READ_SOURCES["plotas_saltinis"])
def test_a_read_area_keeps_its_value_and_label(label):
    room = {"nr": "02", "plotas_m2": 14.26, "plotas_saltinis": label}
    _apply_zoom_refinements(room, dict(_ZOOM))
    assert room["plotas_m2"] == 14.26 and room["plotas_saltinis"] == label
    assert room["_plotas_zoom_m2"] == 11.68


@pytest.mark.parametrize("label", READ_SOURCES["lubu_aukstis_saltinis"])
def test_a_read_height_keeps_its_value_and_label(label):
    room = {"nr": "111", "lubu_aukstis_m": 2.8, "lubu_aukstis_saltinis": label}
    _apply_zoom_refinements(room, dict(_ZOOM))
    assert room["lubu_aukstis_m"] == 2.8 and room["lubu_aukstis_saltinis"] == label
    assert room["_lubu_aukstis_zoom_m"] == 3.3, "the rejected figure is kept beside it"
    assert any(c.startswith("lubu_aukstis (zoom)") for c in room["_zoom_changes"])


@pytest.mark.parametrize("label", [None, "", "section_average", "default_fallback", "height_gate_clamped", "per_room"])
def test_an_assumed_or_unlabelled_height_takes_the_zoom_and_says_so(label):
    room = {"nr": "03", "lubu_aukstis_m": 2.82, "lubu_aukstis_saltinis": label}
    assert _apply_zoom_refinements(room, {"confidence_zoom": "high", "lubu_aukstis_m": 3.0}) is True
    assert room["lubu_aukstis_m"] == 3.0
    assert room["lubu_aukstis_saltinis"] == ZOOM_SOURCE, "the label follows the value"


def test_an_unlabelled_perimeter_takes_the_zoom_and_says_so():
    room = {"nr": "05", "perimetras_m": 12.0}
    assert _apply_zoom_refinements(room, {"confidence_zoom": "high", "perimetras_saltinis": "from_zoom",
                                          "perimetras_m": 13.4}) is True
    assert room["perimetras_m"] == 13.4 and room["perimetras_saltinis"] == ZOOM_SOURCE


def test_the_read_labels_cover_what_the_lanes_write():
    """The constant is built from the labels the code writes — a lane that learns a new one must add it."""
    from extractor.dimension_sum import ESTIMATE_SOURCE, KEEP
    from extractor.geometry_lane import OPEN_PLAN_ESTIMATE
    from extractor.plan_area_annotations import HEIGHT_SOURCE, SOURCE_LABEL
    from extractor.plan_dimensions import SOURCE as PLAN_DIMENSIONS
    from extractor.wall_outline import SOURCE as WALL_OUTLINE
    assert set(KEEP) | {ESTIMATE_SOURCE, OPEN_PLAN_ESTIMATE, PLAN_DIMENSIONS, WALL_OUTLINE} \
        <= set(READ_SOURCES["perimetras_saltinis"])
    assert {SOURCE_LABEL, "eksplikacija", "user_override", "manual"} <= set(READ_SOURCES["plotas_saltinis"])
    assert {HEIGHT_SOURCE, "ceiling_plan_marker", "user_override", "manual"} \
        <= set(READ_SOURCES["lubu_aukstis_saltinis"])
    assert ZOOM_SOURCE not in {s for v in READ_SOURCES.values() for s in v}


def test_a_zoom_replaced_perimeter_is_shown_as_the_programs_estimate():
    """With or without vector geometry on the project, a perimeter the zoomed re-read replaced is an
    estimate on the check sheet — never a quiet „read" row."""
    from extractor import room_facts as rf
    room = {"nr": "01", "pavadinimas": "Kambarys", "paskirtis": "gyvenamoji", "plotas_m2": 20.0,
            "perimetras_m": 18.4, "perimetras_saltinis": "zoom", "lubu_aukstis_m": 2.7, "puslapio_nr": 1}
    for project in ({"patalpos": [room]}, {"patalpos": [room], "_meta": {"geometrija": {}}}):
        perim = rf._fact_perimetras(project, room, None)
        assert perim["key"] == "perimetras"
        assert perim["status"] == "assumed", perim
        assert "padidinto plano vaizdo" in perim["sentence"]


def test_a_zoom_replaced_perimeter_is_not_called_the_tables_when_a_row_of_that_number_has_one():
    """The table's row for this number was not joined to the room (its area contradicted the room's), so the
    room's perimeter is not the table's; the zoomed re-read replaced it. The sheet must not say „from the table"
    over the zoom's number — the room's own label says what the number is."""
    from extractor import room_facts as rf
    room = {"nr": "01", "pavadinimas": "Kambarys", "paskirtis": "gyvenamoji", "plotas_m2": 20.0,
            "perimetras_m": 18.4, "perimetras_saltinis": "zoom", "lubu_aukstis_m": 2.7, "puslapio_nr": 1,
            "plotas_match_rejected": "Sandėlis"}
    project = {"patalpos": [room],
               "_eksplikacija": {"patalpos": [{"row_idx": 0, "nr": "01", "pavadinimas": "Sandėlis",
                                               "plotas_m2": 4.0, "perimetras_m": 8.0, "page": 2}]}}
    perim = rf._fact_perimetras(project, room, None)
    assert perim["status"] == "assumed" and perim["value"] == 18.4, perim
    assert "padidinto plano vaizdo" in perim["sentence"] and "eksplikacijos" not in perim["sentence"]
