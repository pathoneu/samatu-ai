"""D4 / D5 (Pathon v3 W5-D): the paid readers for a raster legend or schedule — off by default, a per-run OK,
the owner first, a proposal only. The model is STUBBED in every test: nothing here calls Vision."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from main import app  # noqa: E402

import auth  # noqa: E402
import db  # noqa: E402
import main  # noqa: E402
import storage  # noqa: E402
from api import vision_readers as vr  # noqa: E402
from synthetic_plan import build_plan, two_rooms  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "vr.db")
    monkeypatch.setattr(auth, "AUTH_DISABLED", True)
    for k in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("LOCAL_STORAGE_DIR", str(tmp_path / "pdfs"))
    storage.reset_storage_for_test()
    db.init_schema()
    db._migrate_schema()
    db.upsert_project("p1", {"name": "P", "patalpos": []})
    storage.get_storage().put(storage.pdf_key("p1"), build_plan([two_rooms()]))
    monkeypatch.setattr(main, "_billable_user", lambda request: {"id": "u1"})
    return TestClient(app)


BODY = {"page": 1, "bbox_pct": [0.5, 0.1, 0.8, 0.3]}


def _stub_models(monkeypatch, calls):
    from extractor import legend_injection
    from extractor.vision import schedule_extractor as se

    def legend(image_b64, client=None):
        calls.append(("legend", len(image_b64)))
        return {"symbols": [{"glyph": "⊗", "meaning": "Šviestuvas lubose"}, {"meaning": ""}], "_meta": {"model": "stub"}}

    def schedule(*, image_b64, **kw):
        calls.append(("schedule", len(image_b64)))
        return se.Schedule(durys=[se.ScheduleEntry(id="D1", width_mm=900, height_mm=2100, count=3)])
    monkeypatch.setattr(legend_injection, "extract_legend", legend)
    monkeypatch.setattr(se, "extract_schedule", schedule)


def test_off_by_default_nothing_is_called(client, monkeypatch):
    calls = []
    _stub_models(monkeypatch, calls)
    monkeypatch.delenv(vr.FLAG_ENV, raising=False)
    assert client.get("/api/projects/p1/vision-readers").json()["enabled"] is False
    r = client.post("/api/projects/p1/legend/vision-read", json={**BODY, "patvirtinta": True})
    assert r.status_code == 403 and calls == []
    assert client.post("/api/projects/p1/schedule/vision-read", json={**BODY, "patvirtinta": True}).status_code == 403


def test_with_the_flag_a_run_needs_its_own_ok_that_names_the_cost(client, monkeypatch):
    calls = []
    _stub_models(monkeypatch, calls)
    monkeypatch.setenv(vr.FLAG_ENV, "1")
    ask = client.post("/api/projects/p1/legend/vision-read", json=BODY)
    assert ask.status_code == 409 and "€" in ask.json()["detail"]["kaina"] and calls == []
    ok = client.post("/api/projects/p1/legend/vision-read", json={**BODY, "patvirtinta": True}).json()
    assert ok["perziureti"] is True and ok["irasyta"] is False
    assert [r["text"] for r in ok["rows"]] == ["Šviestuvas lubose"] and ok["rows"][0]["saltinis"] == "modelis"
    sched = client.post("/api/projects/p1/schedule/vision-read", json={**BODY, "patvirtinta": True}).json()
    assert sched["rows"][0] | {} == {**sched["rows"][0], "kodas": "D1", "kiekis": 3, "rusis": "durys"}
    assert [c[0] for c in calls] == ["legend", "schedule"] and all(n > 100 for _, n in calls)


def test_owner_first_and_bad_boxes(client, monkeypatch):
    monkeypatch.setenv(vr.FLAG_ENV, "1")
    assert client.post("/api/projects/nope/legend/vision-read", json={**BODY, "patvirtinta": True}).status_code == 404
    calls = []
    _stub_models(monkeypatch, calls)
    bad = client.post("/api/projects/p1/legend/vision-read", json={"page": 1, "bbox_pct": [0.8, 0.1, 0.5, 0.3], "patvirtinta": True})
    assert bad.status_code == 400 and calls == []
