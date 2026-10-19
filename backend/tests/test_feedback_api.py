"""👍 / 👎 plus one optional line (api/feedback.py, Pathon v3 W5-C C10): a paid read rated as a whole, a found
symbol rated „neieškoti tokių" — journal rows (source `ivertinimas`), and a negative example the next
„Rasti panašius" search honours. Owner-gated; „Atšaukti" is one more row, nothing is deleted."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from main import app  # noqa: E402

import auth  # noqa: E402
import db  # noqa: E402
import page_raster_cache as _pdf_cache  # noqa: E402
import storage  # noqa: E402
from api.feedback import negatives_for  # noqa: E402
from api.learning_journal import sentence_for  # noqa: E402
from extractor import cv_render_cache  # noqa: E402
from tests.test_cv_find_symbol import DOORS, PAGE_H, PAGE_W, _door_box, _make_pdf  # noqa: E402

_PW = "passw0rd123"


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "feedback.db")
    monkeypatch.setattr(auth, "AUTH_DISABLED", False)
    monkeypatch.setattr(cv_render_cache, "CACHE_DIR", tmp_path / "cv_cache")
    monkeypatch.setenv("LOCAL_STORAGE_DIR", str(tmp_path / "store"))
    for v in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET", "STORAGE_BACKEND", "ENV"):
        monkeypatch.delenv(v, raising=False)
    storage.reset_storage_for_test()
    db.init_schema()
    db._migrate_schema()
    _pdf_cache.clear_pdf_cache()
    owner = db.create_user("owner@x.lt", auth.hash_password(_PW), name="Owner")
    db.create_user("other@x.lt", auth.hash_password(_PW), name="Other")
    db.upsert_project("proj-A", {"name": "A", "tipas": "interjeras"}, user_id=owner["id"])
    _pdf_cache.store_pdf("proj-A", _make_pdf())
    yield
    _pdf_cache.clear_pdf_cache()
    storage.reset_storage_for_test()


def _login(email):
    c = TestClient(app)
    r = c.post("/api/auth/login", json={"email": email, "password": _PW})
    assert r.status_code == 200, r.text
    return c


def _pct(box):
    return [box[0] / PAGE_W, box[1] / PAGE_H, box[2] / PAGE_W, box[3] / PAGE_H]


def test_the_paid_read_rated_with_a_line_is_one_journal_row(env):
    c = _login("owner@x.lt")
    r = c.post("/api/projects/proj-A/feedback", json={"kind": "skaitymas", "up": False, "line": "aukščiai neteisingi"})
    assert r.status_code == 200, r.text
    rows = [x for x in db.list_corrections("proj-A") if x["source"] == "ivertinimas"]
    assert len(rows) == 1
    assert rows[0]["field_path"] == "ivertinimas.skaitymas"
    assert rows[0]["new_value"] == {"ivertinimas": "ne"}
    assert rows[0]["note"] == "aukščiai neteisingi"
    assert sentence_for(rows[0]) == "Brėžinio perskaitymą įvertinote: netiko"
    undo = c.post("/api/projects/proj-A/feedback", json={"kind": "skaitymas", "undo": True})
    assert undo.json()["ivertinimas"] == "atsaukta"


def test_thumbs_down_on_a_symbol_is_a_negative_until_taken_back(env):
    c = _login("owner@x.lt")
    box = _pct(_door_box(*DOORS[1]))
    r = c.post("/api/projects/proj-A/feedback", json={"kind": "simbolis", "up": False, "page": 1, "box_pct": box, "klass": "durys"})
    assert r.status_code == 200 and r.json()["neieskoti"] is True
    negs = negatives_for("proj-A")
    assert len(negs) == 1 and negs[0]["page"] == 1
    row = [x for x in db.list_corrections("proj-A") if x["source"] == "ivertinimas"][0]
    assert sentence_for(row) == "Lapas 1: rastą ženklą pažymėjote — neieškoti tokių"
    c.post("/api/projects/proj-A/feedback", json={"kind": "simbolis", "undo": True, "page": 1, "box_pct": box})
    assert negatives_for("proj-A") == []


def test_the_next_search_drops_what_he_asked_not_to_look_for(env):
    c = _login("owner@x.lt")
    search = {"project_id": "proj-A", "page_idx": 0, "box_pt": _door_box(*DOORS[0])}
    before = c.post("/api/cv/find-symbol", json=search).json()
    strong_before = [x for x in before["candidates"] if x["score"] >= 0.85]
    assert len(strong_before) >= len(DOORS)
    assert before["neieskota"] == 0 and before["neieskota_lt"] is None
    # every door is the same symbol: „neieškoti tokių" on one of them takes the others out too — except the one
    # he boxes now himself
    c.post("/api/projects/proj-A/feedback", json={"kind": "simbolis", "up": False, "page": 1, "box_pct": _pct(_door_box(*DOORS[3]))})
    after = c.post("/api/cv/find-symbol", json=search).json()
    assert after["neieskota"] >= len(DOORS) - 1
    assert "neieškoti" in after["neieskota_lt"]
    left = [(x["x"], x["y"], x["score"], x["is_source"]) for x in after["candidates"] if x["score"] >= 0.85]
    assert all(s for *_, s in left), (left, [(x["x"], x["y"], x["score"]) for x in strong_before])


def test_bad_symbol_body_is_400_and_foreign_project_404(env):
    c = _login("owner@x.lt")
    assert c.post("/api/projects/proj-A/feedback", json={"kind": "simbolis", "page": 1}).status_code == 400
    assert c.post("/api/projects/proj-A/feedback", json={"kind": "simbolis", "page": 1, "box_pct": [0.5, 0.5, 0.4, 0.6]}).status_code == 400
    assert c.post("/api/projects/proj-A/feedback", json={"kind": "kita"}).status_code == 422
    other = _login("other@x.lt")
    assert other.post("/api/projects/proj-A/feedback", json={"kind": "skaitymas", "up": True}).status_code == 404
    assert [x for x in db.list_corrections("proj-A") if x["source"] == "ivertinimas"] == []
