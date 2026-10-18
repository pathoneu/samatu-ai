"""The viewer's room tool R (Pathon v3 wave 1, W1-D): one click inside a room → the wall-exact outline is
PROPOSED (`outline-at` with `perziura`), and only his next click or Enter saves it (`outline-set` with
`kaip: "parodyta"`) — review before it exists, one act, one journal row.

The proposal is the very answer „Parodyti patalpą" gives on the room sheet; the save reuses the drawn-ring
route so the walls and openings are read again exactly as after every other outline save, and the outline
is still called the one he pointed at (`_konturas.saltinis = "parodyta"`), never one he drew.
"""
from __future__ import annotations

import copy

from fastapi.testclient import TestClient

from main import app  # noqa: E402

import db  # noqa: E402
from tests.test_room_outline_api import _click, _isolate, _store  # noqa: E402


def _outline_rows(project_id="p1"):
    return [c for c in db.list_corrections(project_id) if c["source"] == "konturas"]


def test_a_preview_reads_the_outline_like_the_room_sheet_but_writes_no_journal_row(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store()
    c = TestClient(app)
    preview = _click(c, 2.0, 2.5, perziura=True)
    assert preview.status_code == 200, preview.text
    out = preview.json()
    assert out["status"] == "ok" and out["room"]["_konturas"]["saltinis"] == "parodyta"
    assert _outline_rows() == []
    # the same click on the room sheet („Parodyti patalpą") is the act itself: one row
    sheet = _click(c, 2.0, 2.5).json()
    assert sheet["room"]["polygon_pct"] == out["room"]["polygon_pct"]
    assert len(_outline_rows()) == 1


def test_committing_the_proposal_through_outline_set_is_the_pointed_outline_with_the_same_walls(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store()
    c = TestClient(app)
    before = copy.deepcopy(db.get_project("p1"))
    proposal = _click(c, 2.0, 2.5, perziura=True).json()["room"]
    r = c.post("/api/projects/p1/rooms/01/outline-set",
               json={"page": 1, "polygon_pct": proposal["polygon_pct"], "kaip": "parodyta"})
    assert r.status_code == 200, r.text
    room = r.json()["room"]
    # the outline he pointed at — said so, measured on the same ring, the walls read the same way
    assert room["polygon_pct"] == proposal["polygon_pct"]
    assert room["polygon_source"] == "corrected" and room["_konturas"]["saltinis"] == "parodyta"
    assert abs(room["_konturas"]["plotas_m2"] - proposal["_konturas"]["plotas_m2"]) < 0.05
    for key in ("perimetras_m", "perimetras_saltinis", "_sienos", "_perimetras_suma", "_angos_sienose"):
        assert room[key] == proposal[key], key
    # one act, one journal row — the outline he pointed at
    rows = _outline_rows()
    assert len(rows) == 1 and rows[0]["new_value"]["saltinis"] == "parodyta" and rows[0]["room_nr"] == "01"
    # …and the server saved nothing (the sheet lands the answer)
    assert db.get_project("p1")["patalpos"] == before["patalpos"]


def test_a_pointed_outline_never_takes_the_drawn_perimeter_in_place_of_an_unread_one(tmp_path, monkeypatch):
    """A drawn ring with no dimension strings along it gives the room its drawn perimeter
    (`sienu_konturas`); the outline he POINTED at keeps „Parodyti patalpą"'s rule — the walls decide."""
    _isolate(tmp_path, monkeypatch)
    _store()
    c = TestClient(app)
    ring = [[0.5, 0.5], [0.55, 0.5], [0.55, 0.55], [0.5, 0.55]]      # far from every dimension string
    drawn = c.post("/api/projects/p1/rooms/01/outline-set", json={"page": 1, "polygon_pct": ring}).json()["room"]
    pointed = c.post("/api/projects/p1/rooms/01/outline-set",
                     json={"page": 1, "polygon_pct": ring, "kaip": "parodyta"}).json()["room"]
    assert drawn["perimetras_saltinis"] == "sienu_konturas"
    assert pointed["perimetras_saltinis"] != "sienu_konturas" and pointed["perimetras_m"] == 13.9
    assert pointed["_konturas"]["saltinis"] == "parodyta"


def test_kaip_takes_only_the_one_word(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store()
    r = TestClient(app).post("/api/projects/p1/rooms/01/outline-set",
                             json={"page": 1, "polygon_pct": [[0.1, 0.1], [0.2, 0.1], [0.2, 0.2]], "kaip": "bet_kas"})
    assert r.status_code == 422
