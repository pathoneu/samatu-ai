"""The learning loop's ONE recording path (togal-v2 W11, Togal capability L).

Every accept, reject or edit of an AI result is a row in `corrections`, written by
`db.log_correction_once`: the POST route for the browser's surfaces, and two server
hooks — the outline endpoints (api/room_outline.py) and the symbol decision
(api/cv_tools.py) — so every client path counts. The same fix twice within 60 s is
one fix.
"""
from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from main import app  # noqa: E402  (main before auth — house idiom)

import db  # noqa: E402
from tests.test_cv_find_symbol import DOORS, _door_box, _login, env  # noqa: E402,F401  (fixture)
from tests.test_room_outline_api import _blob, _click, _isolate, _pct, _set, _store, _store_pocket  # noqa: E402


def _rows(project_id="p1"):
    return db.list_corrections(project_id)


# ── idempotence ──────────────────────────────────────────────────────────────

def test_the_same_fix_within_a_minute_is_written_once(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store()
    clock = {"t": "2026-10-16T10:00:00Z"}
    monkeypatch.setattr(db, "_now_iso", lambda: clock["t"])

    args = dict(project_id="p1", field_path="eilute.abc.kiekis", old_value=143.2, new_value=150.0,
                source="eilute_kiekis")
    assert db.log_correction_once(**args) is True
    clock["t"] = "2026-10-16T10:00:30Z"
    assert db.log_correction_once(**args) is False                         # 30 s later: the same fix
    assert db.log_correction_once(**{**args, "new_value": 151.0}) is True  # another value is another fix
    assert db.log_correction_once(**{**args, "field_path": "eilute.xyz.kiekis"}) is True
    clock["t"] = "2026-10-16T10:01:01Z"
    assert db.log_correction_once(**args) is True                          # 61 s after the first
    assert len(_rows()) == 4


def test_another_project_is_never_a_duplicate(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store("p1")
    _store("p2", pdf=False)
    args = dict(field_path="klausimas.aukstis", old_value=None, new_value={"atsakymas": "tinka"},
                source="klausimas_tinka")
    assert db.log_correction_once(project_id="p1", **args) is True
    assert db.log_correction_once(project_id="p2", **args) is True


def test_the_route_keeps_its_body_and_says_when_it_was_a_duplicate(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store()
    body = {"field_path": "eilute.abc.kiekis", "old_value": 92.5, "new_value": 92.5, "source": "eilute_teisinga",
            "room_nr": None, "note": None}
    with TestClient(app) as tc:
        first = tc.post("/api/projects/p1/corrections", json=body)
        second = tc.post("/api/projects/p1/corrections", json=body)
    assert first.status_code == 200 and first.json() == {"status": "logged"}
    assert second.status_code == 200 and second.json() == {"status": "logged", "duplicate": True}
    rows = _rows()
    assert len(rows) == 1 and rows[0]["source"] == "eilute_teisinga" and rows[0]["new_value"] == 92.5


def test_the_old_prielaidos_body_still_lands(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store()
    with TestClient(app) as tc:
        r = tc.post("/api/projects/p1/corrections", json={"field_path": "lubu_auksciai.03", "old_value": 2.7,
                                                          "new_value": 2.82, "source": "prielaidos", "room_nr": "03"})
    assert r.json() == {"status": "logged"}
    assert _rows()[0]["source"] == "prielaidos"


# ── server hooks ─────────────────────────────────────────────────────────────

def test_a_drawn_outline_is_remembered_server_side(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store()
    t = 0.2
    r = _set(TestClient(app), [(t, t), (4 + t, t), (4 + t, 3 + t), (t, 3 + t)])
    assert r.status_code == 200 and r.json()["status"] == "ok"
    rows = _rows()
    assert len(rows) == 1
    row = rows[0]
    assert row["source"] == "konturas" and row["field_path"] == "patalpa.01.kontūras" and row["room_nr"] == "01"
    assert row["new_value"]["saltinis"] == "nubrezta" and abs(row["new_value"]["plotas_m2"] - 12.0) < 0.2
    assert row["old_value"] == {"plotas_m2": 12.0}


def test_a_failed_journal_write_never_fails_the_outline(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store()

    def boom(**_):
        raise RuntimeError("disk full")

    monkeypatch.setattr(db, "log_correction_once", boom)
    t = 0.2
    r = _set(TestClient(app), [(t, t), (4 + t, t), (4 + t, 3 + t), (t, 3 + t)])
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_an_outline_that_could_not_be_made_is_not_remembered(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store()
    r = _set(TestClient(app), [(0.2, 0.2), (0.3, 0.2), (0.4, 0.2)])   # degenerate: a line, not a room
    assert r.status_code in (200, 400)
    assert _rows() == []


def test_a_symbol_decision_is_one_journal_row_too(env):  # noqa: F811
    cl = _login("owner@x.lt")
    with patch("api.cv_tools.record_label"):
        r = cl.post("/api/cv/record-decision", json={
            "project_id": "proj-A", "page_idx": 0, "box_pt": _door_box(*DOORS[1]),
            "klass": "durys-ai", "decision": "reject", "confidence": 0.81, "source": "symbol_search",
        })
    assert r.status_code == 200, r.text
    rows = db.list_corrections("proj-A")
    assert len(rows) == 1
    row = rows[0]
    assert row["source"] == "simbolis" and row["field_path"] == "simbolis.1.durys-ai"
    assert row["new_value"]["sprendimas"] == "reject" and row["note"] == "symbol_search"
    assert row["old_value"] == {"pasitikejimas": 0.81}


# ── one act, one row: a Patikra answer that lands through an outline endpoint ───────────

def test_an_accepted_outline_proposal_is_exactly_one_konturas_row_carrying_the_question(tmp_path, monkeypatch):
    """The server's „konturas" row IS the record of the outline question's answer; the browser writes no
    klausimas_* row for it (pages/PatikraQuestions.jsx), so „Įsiminta" rises by one."""
    _isolate(tmp_path, monkeypatch)
    blob = _blob(_konturo_siulymas={"page": 1, "polygon_pct": [[0.1, 0.1], [0.2, 0.1], [0.2, 0.2]], "plotas_m2": 12.0,
                                   "perimetras_m": 14.0, "paklaida": 0.3, "taskas_pct": [0.15, 0.13]})
    _store(blob=blob)
    r = _click(TestClient(app), 2.0, 2.5, pritarta=True, klausimas="konturas")
    assert r.status_code == 200 and r.json()["status"] == "ok"
    rows = _rows()
    assert len(rows) == 1
    assert rows[0]["source"] == "konturas" and rows[0]["note"] == "konturas"
    assert rows[0]["new_value"]["saltinis"] == "pasiulyta"


def test_a_line_drawn_through_a_shared_space_carries_the_question_on_each_room(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store_pocket()
    ax, ay = _pct(2.0, -0.5)
    bx, by = _pct(2.0, 4.0)
    out = TestClient(app).post("/api/projects/p1/rooms/01/split-space", json={
        "page": 1, "a": {"x_pct": ax, "y_pct": ay}, "b": {"x_pct": bx, "y_pct": by}, "su": "02", "klausimas": "erdve:01-02"}).json()
    assert out["status"] == "ok"
    rows = _rows()
    assert sorted(r["room_nr"] for r in rows) == ["01", "02"]
    assert {r["source"] for r in rows} == {"konturas"} and {r["note"] for r in rows} == {"erdve:01-02"}


def test_an_accepted_door_answer_is_exactly_one_klausimas_tinka_row(tmp_path, monkeypatch):
    """An answer that changes no outline (heights, doors, counts) is recorded by the browser, once."""
    _isolate(tmp_path, monkeypatch)
    _store()
    body = {"field_path": "klausimas.durys", "old_value": None,
            "new_value": {"atsakymas": "tinka", "patalpos": []}, "source": "klausimas_tinka", "room_nr": None,
            "note": "durys"}
    with TestClient(app) as tc:
        assert tc.post("/api/projects/p1/corrections", json=body).json() == {"status": "logged"}
        assert tc.post("/api/projects/p1/corrections", json=body).json()["duplicate"] is True   # a double click
    rows = _rows()
    assert len(rows) == 1 and rows[0]["source"] == "klausimas_tinka" and rows[0]["note"] == "durys"


def test_a_question_id_that_is_too_long_is_refused(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store()
    r = _click(TestClient(app), 2.0, 2.5, klausimas="x" * 65)
    assert r.status_code == 422 and _rows() == []
