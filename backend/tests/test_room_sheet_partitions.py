"""„Pertvarų sienos atviroje erdvėje" on the room sheet (2026-10-17, togal-v2).

A merged room keeps both rooms' partition ends (api/room_outline.py „Sujungti"); the sheet shows that count
as a fact with its source sentence and lets him change it. His answer is saved on the room like every other
room-sheet number (the sheet's recompute), and the learning journal records it through the one writer,
`db.log_correction_once`, with source „patalpa_pertvaros". Every other room's sheet is unchanged.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from main import app  # noqa: E402  (main before auth — house idiom)

import db  # noqa: E402
from api.learning_journal import sentence_for  # noqa: E402
from extractor.room_facts import build_room_facts  # noqa: E402
from tests.test_cv_find_symbol import _login, env  # noqa: E402,F401  (fixture)
from tests.test_room_outline_api import _isolate, _store  # noqa: E402


def _project(**room4):
    r4 = {"nr": "04", "pavadinimas": "Virtuvė", "paskirtis": "gyvenamoji", "plotas_m2": 61.81, "puslapio_nr": 1,
          "n_partition_walls": 5, **room4}
    r1 = {"nr": "01", "pavadinimas": "Tambūras", "paskirtis": "tamburas", "plotas_m2": 4.48, "puslapio_nr": 1,
          "n_partition_walls": 2}
    return {"name": "P", "tipas": "interjeras", "patalpos": [r1, r4]}


def _fact(project, nr):
    return next((f for f in build_room_facts(project, nr)["facts"] if f["key"] == "pertvaros"), None)


def test_a_merged_room_shows_its_partition_ends_with_where_they_come_from():
    f = _fact(_project(_sujungimas={"su": ["05"], "pertvaru_galai_dalys": [2, 3]}), "04")
    assert f["value"] == 5 and f["unit"] == "vnt." and f["status"] == "assumed"
    assert f["sentence"].startswith("2 + 3 = 5 — patalpos sujungtos.")
    assert f["editable"] == {"field": "n_partition_walls", "kind": "number"} and f["yours"] is False


def test_his_own_count_is_his_and_every_other_room_keeps_todays_sheet():
    f = _fact(_project(n_partition_walls=3, n_partition_walls_saltinis="user_override",
                       _sujungimas={"pertvaru_galai_dalys": [2, 3]}), "04")
    assert f["value"] == 3 and f["status"] == "read" and f["yours"] is True
    assert f["sentence"] == "Pertvarų sienų skaičių įrašėte patys: 3."
    assert _fact(_project(), "01") is None and _fact(_project(), "04") is None


def test_the_route_records_his_count_once_with_its_journal_sentence(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store()
    body = {"field_path": "patalpa.04.pertvaros", "old_value": 5, "new_value": 3, "source": "patalpa_pertvaros",
            "room_nr": "04", "note": None}
    with TestClient(app) as tc:
        first = tc.post("/api/projects/p1/corrections", json=body)
        second = tc.post("/api/projects/p1/corrections", json=body)
        listed = tc.get("/api/projects/p1/corrections").json()["corrections"]
    assert first.json() == {"status": "logged"} and second.json() == {"status": "logged", "duplicate": True}
    rows = db.list_corrections("p1")
    assert len(rows) == 1 and rows[0]["source"] == "patalpa_pertvaros" and rows[0]["new_value"] == 3
    assert sentence_for(rows[0]) == "Patalpa 04: pertvarų sienų atviroje erdvėje pakeitėte 5 → 3"
    assert any("pertvarų sienų" in (c.get("sakinys") or c.get("sentence") or "") for c in listed)


def test_a_stranger_cannot_record_it(env):  # noqa: F811
    cl = _login("other@x.lt")
    r = cl.post("/api/projects/proj-A/corrections", json={
        "field_path": "patalpa.04.pertvaros", "old_value": 5, "new_value": 3, "source": "patalpa_pertvaros", "room_nr": "04"})
    assert r.status_code == 404
    assert db.list_corrections("proj-A") == []
