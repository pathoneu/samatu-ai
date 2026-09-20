"""The finish fact speaks in the m² the sąmata bills — never in percentages.

Founder, after the first real Patikra run (2026-09-17): „pasirinkimai keisti,
kai kur procentais". Measured on the two out-of-sample projects (2026-09-20):
the table-read rooms said „Sienos: dažoma 92 %, plytelės 8 %", and a bathroom
whose tiles were read by height said „Sienos: dažoma" while the sąmata billed
21,5 m² of tiles and 2,75 m² of paint for it. A contractor checks a number he
can find in his own estimate; a share of an unnamed whole is not one.
"""
from __future__ import annotations

from extractor import room_facts
from extractor.room_facts import build_room_facts


def _apdaila(room: dict) -> dict:
    project = {"patalpos": [{"nr": "1", "puslapio_nr": 1, **room}]}
    return next(f for f in build_room_facts(project, "1")["facts"] if f["key"] == "apdaila")


def test_walls_are_stated_in_the_square_metres_the_sąmata_bills():
    f = _apdaila({
        "walls_paintable_m2": 93.04, "plyteles_sienos_m2": 5.86, "ceiling_paintable_m2": 37.86,
        "_tile_read_source": "apdailos",
        "sienu_apdailos_breakdown": {"dazymas_share": 0.92, "plyteles_share": 0.08},
    })
    assert f["value"] == "Sienos: dažoma 93,04 m², plytelės 5,86 m²; lubos: dažomos 37,86 m²"
    assert "%" not in f["value"] and "%" not in f["sentence"]


def test_a_tiled_bathroom_read_by_height_is_not_called_painted():
    """No breakdown on the room (the tiles came from their height), so the old
    description fell through to a bare „dažoma"."""
    f = _apdaila({"paskirtis": "san", "walls_paintable_m2": 2.75, "plyteles_sienos_m2": 21.5,
                  "ceiling_paintable_m2": 4.9, "_tile_read_source": "vision_height"})
    assert f["value"].startswith("Sienos: dažoma 2,75 m², plytelės 21,50 m²;")


def test_fully_tiled_walls():
    assert room_facts._walls_description(
        {"_walls_full_tile": True, "walls_paintable_m2": 0.0, "plyteles_sienos_m2": 24.25}) == "plytelės 24,25 m²"
    assert room_facts._walls_description({"_walls_full_tile": True}) == "plytelės"


def test_unpainted_walls_say_so_and_still_name_their_tiles():
    assert room_facts._walls_description({"walls_paintable_m2": 0.0, "_walls_paint_factor": 0.0}) == "nedažomos"
    assert room_facts._walls_description(
        {"walls_paintable_m2": 0.0, "plyteles_sienos_m2": 20.0}) == "nedažomos, plytelės 20,00 m²"


def test_a_room_with_no_computed_walls_yet_is_simply_painted():
    """A blob that was never recomputed carries no areas at all."""
    assert room_facts._walls_description({}) == "dažoma"


def test_a_finish_the_engine_does_not_bill_is_named_without_a_number():
    text = room_facts._walls_description({
        "walls_paintable_m2": 28.0,
        "sienu_apdailos_breakdown": {"dazymas_share": 0.7, "tapetai_share": 0.3}})
    assert text == "dažoma 28,00 m², tapetai"


def test_a_room_kept_out_by_choice_keeps_its_reading():
    """The choice zeroes the quantities; `scope` remembers what they were."""
    room = {"_neskaiciuoti": True, "walls_paintable_m2": 0.0, "plyteles_sienos_m2": 0.0,
            "ceiling_paintable_m2": 0.0,
            "_neskaiciuoti_kiekiai": {"walls_paintable_m2": 4.25, "plyteles_sienos_m2": 18.15,
                                      "ceiling_paintable_m2": 3.52}}
    f = _apdaila(room)
    assert f["value"] == "Sienos: dažoma 4,25 m², plytelės 18,15 m²; lubos: dažomos 3,52 m²"
    assert "pasirinkimu" in f["sentence"]


def test_a_room_kept_out_on_an_old_blob_is_named_without_numbers():
    """No remembered quantities: the reading is still not „nedažomos"."""
    room = {"_neskaiciuoti": True, "walls_paintable_m2": 0.0, "ceiling_paintable_m2": 0.0,
            "sienu_apdailos_breakdown": {"dazymas_share": 0.2, "plyteles_share": 0.8}}
    f = _apdaila(room)
    assert f["value"] == "Sienos: dažoma, plytelės; lubos: dažomos"
    assert "%" not in f["value"]


def test_ceilings_carry_their_area_too():
    assert room_facts._ceiling_description({"ceiling_paintable_m2": 12.0}) == "dažomos 12,00 m²"
    assert room_facts._ceiling_description(
        {"_stretch_ceiling": True, "ceiling_paintable_m2": 24.3}) == "įtempiamos 24,30 m²"
    assert room_facts._ceiling_description({"_stretch_ceiling": True}) == "įtempiamos"
    assert room_facts._ceiling_description({"_ceiling_paint_source": "override_off",
                                            "ceiling_paintable_m2": 0.0}) == "nedažomos"
    assert room_facts._ceiling_description({"ceiling_paintable_m2": 0.0}) == "nedažomos"
    assert room_facts._ceiling_description({}) == "dažomos"
