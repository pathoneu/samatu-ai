"""A height the plan states is a ROOM's ceiling height only when the drawing
ties it to that room (2026-10-05).

objektas_a's santechnikos sheet carries four bare „h=2600 mm", each right under
„Kondicionierius" — the air-conditioner's mounting height. The plan-height lane
took them for the storey height: any room whose model label was a default got
2,6 m, ranked above the voted and name-map heights (room 102 is 3,4 m on the
drawing). Now a stamp sets the height of the one room it belongs to — ceiling
words („Lubų aukštis") or a room's own label beside it inside its outline — and
an element annotation or a stamp no room claims sets nothing.

Synthetic drawings (reportlab, ASCII — Helvetica has no ų) and made-up rooms;
the last test reads objektas_a's real sheet and skips where it is not on disk.
"""
from __future__ import annotations

import copy
import json
from io import BytesIO
from pathlib import Path

import pytest
from reportlab.pdfgen import canvas

from extractor import plan_area_annotations as pa
from extractor.plan_area_annotations import apply_height_statements, read_height_statements

REPO_ROOT = Path(__file__).resolve().parents[2]
PAGE = (842, 1191)


def _pdf(draw) -> bytes:
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=PAGE)
    draw(c)
    c.showPage()
    c.save()
    return buf.getvalue()


def _room(nr, name, box=None, **kw):
    """A room drawn on sheet 1 with the default height; `box` = (x, y, w, h) in page fractions."""
    room = {"nr": nr, "pavadinimas": name, "puslapio_nr": 1, "lubu_aukstis_m": 2.82,
            "lubu_aukstis_saltinis": "section_average", **kw}
    if box:
        room["bbox_pct"] = dict(zip("xywh", box))
    return room


def _heights(rooms):
    return {r["nr"]: (r["lubu_aukstis_m"], r["lubu_aukstis_saltinis"]) for r in rooms}


# ── the element annotation (objektas_a's pattern) ────────────────────────────

def _air_conditioner(c):
    c.setFont("Helvetica", 11)
    c.drawString(250, 600, "103")                    # the room's number, far left of the stamp
    c.setFont("Helvetica", 4.3)
    c.drawString(420, 605, "Kondicionierius")        # the label of the leader line…
    c.drawString(420, 600, "h=2600 mm")              # …and the unit's mounting height under it


def test_a_mounting_height_under_its_element_sets_no_room():
    hs = read_height_statements(_pdf(_air_conditioner))
    assert [(h["value_m"], h["context"], h["ceiling"]) for h in hs] == [(2.6, "Kondicionierius", False)]
    x0, _top, x1, _bottom = hs[0]["bbox"]
    assert 418 < x0 and x1 < 450, "the stamp's own box, not its baseline's"
    rooms = [_room("103", "Koridorius", (0.2, 0.3, 0.4, 0.4)), _room("102", "Svetaine", (0.6, 0.1, 0.3, 0.3))]
    res = apply_height_statements(rooms, hs)
    assert (res["status"], res["rooms"], res["elements"]) == ("not_tied", [], 1)
    assert _heights(rooms) == {"103": (2.82, "section_average"), "102": (2.82, "section_average")}


# ── a room tag: the stamp next to the room's own label ───────────────────────

def _room_tag(c):
    c.setFont("Helvetica", 9)
    c.drawString(100, 900, "104")
    c.drawString(100, 888, "Svetaine")
    c.drawString(100, 876, "25,30 m2")
    c.drawString(100, 864, "H=2700")


def test_a_stamp_beside_a_room_label_inside_its_outline_sets_that_room_only():
    hs = read_height_statements(_pdf(_room_tag))
    assert [(h["value_m"], h["context"]) for h in hs] == [(2.7, "104 Svetaine 25,30 m2")]
    rooms = [_room("104", "Svetainė", (0.05, 0.15, 0.3, 0.25)), _room("105", "Miegamasis", (0.5, 0.15, 0.3, 0.25))]
    res = apply_height_statements(rooms, hs)
    assert (res["status"], res["rooms"], res["value_m"]) == ("applied", ["104"], 2.7)
    assert _heights(rooms) == {"104": (2.7, "plano_uzrasas"), "105": (2.82, "section_average")}
    assert rooms[0]["_lubu_aukstis_uzrasas"]["text"] == "H=2700"


def test_a_label_is_the_room_s_name_or_its_number_never_an_area_or_a_unit():
    def stamp(context):          # a bare stamp at the centre of the left half of sheet 1
        return {"page": 1, "value_m": 2.5, "text": "H=2500", "bbox": [200, 590, 220, 600],
                "page_width": 842, "page_height": 1191, "ceiling": False, "context": context}
    for context in ("WC", "06", "6", "WC 3,20 m²"):
        rooms = [_room("06", "WC", (0.1, 0.4, 0.3, 0.2)), _room("07", "Vonia", (0.6, 0.4, 0.3, 0.2))]
        res = apply_height_statements(rooms, [stamp(context)])
        assert res["rooms"] == ["06"], context
    # the stamp lies in room 02: an area („3,20"), the „2" of „m2" or a decimal never name it,
    # and „WC rėmas" is an element
    for context in ("3,20 m2", "3,20 m²", "2,50", "WC rėmas"):
        rooms = [_room("02", "Kambarys", (0.1, 0.4, 0.3, 0.2))]
        assert apply_height_statements(rooms, [stamp(context)])["rooms"] == [], context


def test_a_room_label_beside_a_stamp_outside_that_room_ties_nothing():
    hs = read_height_statements(_pdf(_room_tag))
    rooms = [_room("104", "Svetainė", (0.5, 0.5, 0.3, 0.3)),              # its outline is elsewhere
             _room("105", "Miegamasis", (0.05, 0.15, 0.3, 0.25))]         # the stamp lies in this one
    res = apply_height_statements(rooms, hs)
    assert (res["status"], res["untied"]) == ("not_tied", 1)
    assert _heights(rooms)["105"] == (2.82, "section_average")


# ── ceiling words ─────────────────────────────────────────────────────────────

def _ceiling_words(c):
    c.setFont("Helvetica", 9)
    c.drawString(500, 700, "Lubu aukstis H=2700")    # inside room 05's outline, no label beside it
    c.drawString(500, 100, "Lubu aukstis H=3000")    # in the notes block, outside every room
    c.drawString(100, 300, "H - 2820")               # a lone stamp in room 06 (objektas_d's pattern)


def test_ceiling_words_tie_the_stamp_to_the_one_room_it_stands_in():
    hs = read_height_statements(_pdf(_ceiling_words))
    assert [(h["value_m"], h["ceiling"]) for h in hs] == [(2.7, True), (2.82, False), (3.0, True)]
    rooms = [_room("05", "Virtuve", (0.55, 0.3, 0.4, 0.3)), _room("06", "Vonia", (0.05, 0.6, 0.3, 0.3)),
             _room("07", "Holas", (0.05, 0.05, 0.2, 0.2))]
    res = apply_height_statements(rooms, hs)
    assert (res["status"], res["rooms"], res["untied"]) == ("applied", ["05"], 2)
    # the notes-block 3,0 m reaches no room, the lone „H - 2820" no room either
    assert _heights(rooms) == {"05": (2.7, "plano_uzrasas"), "06": (2.82, "section_average"),
                               "07": (2.82, "section_average")}


def test_ceiling_words_are_read_on_the_stamp_line_but_soffits_are_not():
    def draw(c):
        c.setFont("Helvetica", 9)
        c.drawString(100, 1100, "Lubu aukstis H=2700")
        c.drawString(100, 1060, "Aukstis iki lubu h - 2,65 m")
        c.drawString(100, 1020, "Pakabinamos lubos h - 2500")     # a suspended ceiling's own height
        c.drawString(100, 980, "Lubu nisa h - 2400")              # a niche
        c.drawString(100, 940, "ap. h - 2260 mm, kai lubos zeminamos")
    hs = read_height_statements(_pdf(draw))
    assert [(h["value_m"], h["ceiling"]) for h in hs] == [(2.7, True), (2.65, True)]


def test_the_text_and_its_char_map_match_line_text():
    def draw(c):
        c.setFont("Helvetica", 9)
        c.drawString(100, 900, "103   h=2600 mm")
        x = 100.0
        for ch in "H - 2820":                                   # character-spaced, the way CAD writes it
            c.drawString(x, 800, ch)
            x += 9.0
    for _pn, _W, _H, chars, _td in pa._iter_pages(_pdf(draw), None):
        for line in pa._lines(chars):
            text, src = pa._line_text_mapped(line)
            assert text == pa._line_text(line)
            assert len(src) == len(text)
            assert all((c is None) == (ch == " ") for ch, c in zip(text, src))


# ── objektas_a, the real sheet ────────────────────────────────────────────────

OBJEKTAS_A_PDF = REPO_ROOT / "docs/superpowers/fixtures/2026-05-26-objektas-a/project.pdf"


@pytest.mark.integration
def test_objektas_a_air_conditioner_heights_reach_no_room(monkeypatch):
    """The simulation the audit asked for: every room's height label a default,
    as a fresh paid run can leave it at Step 2.44. Before 2026-10-05 the four
    „h=2600 mm" set all 11 rooms to 2,6 m and Step 2.45 kept it over the name
    map; now no room takes them and the name map decides (room 102: 3,4 m)."""
    if not OBJEKTAS_A_PDF.is_file():
        pytest.skip("objektas_a: the drawing is not on this machine")
    from extractor.vision_call import _apply_per_room_heights

    monkeypatch.setenv("ENABLE_PER_ROOM_CEILING", "1")
    frozen = json.loads((REPO_ROOT / "ground_truth/objektas_a/ai_extract.json").read_text(encoding="utf-8"))
    rooms = copy.deepcopy(frozen["patalpos"])
    for r in rooms:
        r["lubu_aukstis_saltinis"] = "default_fallback"
    scan = pa.scan_text_layer(OBJEKTAS_A_PDF.read_bytes(),
                              pages=pa.text_pages_from_classification(frozen.get("puslapiai") or []) or None)
    hs = scan["heights"]
    assert [(h["page"], h["value_m"], h["context"]) for h in hs] == [(4, 2.6, "Kondicionierius")] * 4
    res = apply_height_statements(rooms, hs)
    assert (res["status"], res["rooms"], res["elements"]) == ("not_tied", [], 4)
    assert not [r["nr"] for r in rooms if r["lubu_aukstis_saltinis"] == "plano_uzrasas"]
    out = _apply_per_room_heights(rooms, frozen["lubu_auksciai"], 2.8, name_key="pavadinimas")
    got = {r["nr"]: r["lubu_aukstis_m"] for r in out}
    assert len(got) == 11 and 2.6 not in got.values()
    assert (got["102"], got["105"]) == (3.4, 3.0)
