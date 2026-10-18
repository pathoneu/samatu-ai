"""Undo after every outline save (Pathon v3 wave 1, W1-D, D3; audit F5: outline save, merge, split and subtract
toasted success with no „Atšaukti" — the only way back was a whole-project version restore).

Every saving answer of api/room_outline.py now carries `previous`: for each room the answer changes, the
geometry keys AS STORED before (null = the key was absent), plus the merge keys for „Sujungti", plus the
neighbours' `_angos_sienose`. The browser's „Atšaukti" PUTs that `previous` back through the SAME route; the
server (which saves nothing, as before) checks ownership, the rooms and the keys, writes ONE journal row per
room with source `atsaukta`, and answers in the shape the forward answer had — so the sheet lands it with the
very functions it landed the save with. The same PUT twice is the same answer (and one journal row).
"""
from __future__ import annotations

import copy

from fastapi.testclient import TestClient

from main import app  # noqa: E402

import db  # noqa: E402
from api.room_outline import GEOMETRY_ROOM_KEYS, MERGE_ROOM_KEYS  # noqa: E402
from tests.test_room_outline_api import _blob, _click, _isolate, _merge, _pct, _set, _set_holes, _store  # noqa: E402

T = 0.2
OUTER = [(T, T), (4 + T, T), (4 + T, 3 + T), (T, 3 + T)]          # room 01's inner faces on the synthetic plan
UNION = [(T, T), (7 + 2 * T, T), (7 + 2 * T, 3 + T), (T, 3 + T)]  # rooms 01 + 02 and the partition between


def _stored_room(nr, project_id="p1"):
    return next(r for r in db.get_project(project_id)["patalpos"] if r["nr"] == nr)


def _undo_rows(project_id="p1"):
    return [c for c in db.list_corrections(project_id) if c["source"] == "atsaukta"]


def test_an_outline_set_answer_carries_what_the_room_had_before(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store(blob=_blob(polygon_pct=[[0.1, 0.1], [0.2, 0.1], [0.2, 0.2]], polygon_source="auto_floodfill"))
    stored = copy.deepcopy(_stored_room("01"))
    out = _set(TestClient(app), OUTER).json()
    prev = out["previous"]
    # every geometry key of the room, as stored — null where it had none
    assert set(prev["01"]) == set(GEOMETRY_ROOM_KEYS)
    assert prev["01"]["polygon_pct"] == stored["polygon_pct"] and prev["01"]["polygon_source"] == "auto_floodfill"
    assert prev["01"]["perimetras_m"] == 13.9 and prev["01"]["_konturas"] is None and prev["01"]["_sienos"] is None
    # a neighbour whose openings the answer changes is in it too, with only its openings
    assert "02" in out["kitu_angos"] and prev["02"] == {"_angos_sienose": None}


def test_atsaukti_puts_previous_back_through_the_same_route_and_is_journalled_once(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store()
    c = TestClient(app)
    saved = _set(c, OUTER).json()
    before = copy.deepcopy(db.get_project("p1"))
    r = c.put("/api/projects/p1/rooms/01/outline-set", json={"previous": saved["previous"]})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["status"] == "ok" and out["atsaukta"] == "konturas"
    # the answer lands like the forward one: the rooms' keys as they were (null = remove)
    assert out["rooms"]["01"] == saved["previous"]["01"] and out["rooms"]["02"] == {"_angos_sienose": None}
    assert out["kitu_angos"] == {}
    # one journal row for the room he undid (none for the neighbour), and the server saved nothing
    rows = _undo_rows()
    assert len(rows) == 1 and rows[0]["room_nr"] == "01" and rows[0]["field_path"] == "patalpa.01.kontūras"
    assert rows[0]["new_value"]["atsaukta"] == "konturas"
    assert db.get_project("p1") == before
    # idempotent: the same Atšaukti again is the same answer, still one row
    again = c.put("/api/projects/p1/rooms/01/outline-set", json={"previous": saved["previous"]}).json()
    assert again == out and len(_undo_rows()) == 1


def test_a_subtract_is_undone_with_its_holes(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store()
    c = TestClient(app)
    first = _set(c, OUTER).json()
    landed = {**_stored_room("01"), **{k: v for k, v in first["room"].items() if v is not None}}
    db.upsert_project("p1", {**db.get_project("p1"), "patalpos": [landed, _stored_room("02")]}, user_id=None)
    holed = _set_holes(c, OUTER, [[(1.0, 1.0), (1.5, 1.0), (1.5, 1.5), (1.0, 1.5)]]).json()
    assert holed["room"]["polygon_holes_pct"] and holed["previous"]["01"]["polygon_holes_pct"] is None
    assert holed["previous"]["01"]["polygon_pct"] == landed["polygon_pct"]
    back = c.put("/api/projects/p1/rooms/01/outline-set", json={"previous": holed["previous"]}).json()
    assert back["rooms"]["01"]["polygon_holes_pct"] is None and back["rooms"]["01"]["polygon_pct"] == landed["polygon_pct"]


def test_a_merge_answer_carries_both_rooms_and_its_undo_restores_both(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    blob = _blob(elementai=[{"tipas": "duris", "kiekis": 1}])
    blob["patalpos"][1]["elementai"] = [{"tipas": "langas", "kiekis": 2}]
    _store(blob=blob)
    c = TestClient(app)
    merged = _merge(c, UNION).json()
    prev = merged["previous"]
    assert set(prev["01"]) == set(GEOMETRY_ROOM_KEYS) | set(MERGE_ROOM_KEYS)
    assert prev["01"]["plotas_m2"] == 12.0 and prev["01"]["plotas_saltinis"] == "eksplikacija" and prev["01"]["_sujungimas"] is None
    assert prev["02"]["plotas_m2"] == 9.0 and prev["02"]["_sujungta_i"] is None
    assert prev["02"]["elementai"] == [{"tipas": "langas", "kiekis": 2}]
    r = c.put("/api/projects/p1/rooms/02/outline-merge", json={"previous": prev})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["atsaukta"] == "sujungimas"
    # geometry keys under `rooms`, merge keys under `sujungimas` — exactly the forward answer's shape
    assert out["sujungimas"]["01"]["plotas_m2"] == 12.0 and out["sujungimas"]["02"]["_sujungta_i"] is None
    assert out["rooms"]["02"]["polygon_pct"] is None and "plotas_m2" not in out["rooms"]["01"]
    assert sorted(row["room_nr"] for row in _undo_rows()) == ["01", "02"]


def test_the_room_sheets_click_and_the_room_tools_preview_carry_previous_too(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store()
    out = _click(TestClient(app), 2.0, 2.5).json()
    assert out["status"] == "ok" and out["previous"]["01"]["polygon_pct"] is None
    preview = _click(TestClient(app), 2.0, 2.5, perziura=True).json()
    assert preview["previous"] == out["previous"]


def test_an_undo_restores_only_rooms_and_keys_it_may(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store()
    c = TestClient(app)
    put = lambda path, body: c.put(f"/api/projects/p1/rooms/{path}", json=body)  # noqa: E731
    # a key that is not geometry (a quantity, a name) is never restored through here
    assert put("01/outline-set", {"previous": {"01": {"plotas_m2": 99.0}}}).status_code == 400
    # merge keys only through the merge route
    assert put("01/outline-set", {"previous": {"01": {"_sujungta_i": None}}}).status_code == 400
    assert put("02/outline-merge", {"previous": {"02": {"_sujungta_i": None}}}).status_code == 200
    # the room in the path must be one of the rooms restored; every room must exist; the shape must be right
    assert put("01/outline-set", {"previous": {"02": {"polygon_pct": None}}}).status_code == 400
    assert put("01/outline-set", {"previous": {"01": {"polygon_pct": None}, "77": {"polygon_pct": None}}}).status_code == 404
    assert put("01/outline-set", {"previous": {"01": "polygon_pct"}}).status_code == 400
    assert put("01/outline-set", {"previous": {}}).status_code == 400
    assert c.put("/api/projects/nope/rooms/01/outline-set", json={"previous": {"01": {"polygon_pct": None}}}).status_code == 404
