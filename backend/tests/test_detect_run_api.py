"""`/api/projects/{id}/detect-run` — „Perskaityti lapą": the free re-read as a
job with named stages, per sheet and per feature (api/detect_run.py).

What is pinned: the stages arrive in the lane's own order and end with the
browser's „kiekiai"; an outline he corrected survives the run; a sheet that is
not the rooms' plan changes no room; a feature he did not choose keeps its
stored keys; a broken lane names the stage it broke in and changes nothing; the
server saves nothing; ownership is checked before the body is looked at.
"""
from __future__ import annotations

import copy
import time

from fastapi.testclient import TestClient

from main import app  # noqa: E402

import auth  # noqa: E402
import db  # noqa: E402
import storage  # noqa: E402
from api import detect_run as dr  # noqa: E402
from api import free_reread as fr  # noqa: E402
from extractor import geometry_lane as gl  # noqa: E402
from tests.synthetic_plan import Sheet, build_plan, two_rooms  # noqa: E402

_PW = "passw0rd123"
CORRECTED = [[0.13, 0.11], [0.31, 0.11], [0.31, 0.21], [0.13, 0.21]]


def _isolate(tmp_path, monkeypatch, *, auth_disabled=True):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "detect_run.db")
    monkeypatch.setattr(auth, "AUTH_DISABLED", auth_disabled)
    for k in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("LOCAL_STORAGE_DIR", str(tmp_path / "pdfs"))
    storage.reset_storage_for_test()
    db.init_schema()
    db._migrate_schema()
    dr._jobs.clear()
    fr._running.clear()


def _blob(*, corrected=False):
    r1 = {"nr": "01", "pavadinimas": "A", "plotas_m2": 12.0, "plotas_saltinis": "eksplikacija", "puslapio_nr": 1,
          "perimetras_m": 13.9, "bbox_pct": {"x": 0.12, "y": 0.10, "w": 0.2, "h": 0.12},
          "polygon_pct": [[0.12, 0.10], [0.32, 0.10], [0.32, 0.22], [0.12, 0.22]], "polygon_source": "synthesized_from_bbox"}
    if corrected:
        r1["polygon_pct"] = copy.deepcopy(CORRECTED)
        r1["polygon_source"] = "corrected"
    r2 = {"nr": "02", "pavadinimas": "B", "plotas_m2": 9.0, "plotas_saltinis": "eksplikacija", "puslapio_nr": 1,
          "perimetras_m": 12.3}
    return {"name": "P", "tipas": "interjeras", "patalpos": [r1, r2],
            "puslapiai": [{"nr": 1, "tipas": "floor_plan"}, {"nr": 2, "tipas": "floor_plan"}, {"nr": 3, "tipas": "other"}],
            "_meta": {"model": "x"}}


def _drawing() -> bytes:
    a = two_rooms()
    a.dims = []                        # the layout sheet: badges, no wall lengths
    b = two_rooms()
    b.badges = []                      # the wall painting plan: wall lengths, no badges
    return build_plan([a, b, Sheet()])  # sheet 3: a title page — no plan on it


def _store(project_id="p1", *, user_id=None, blob=None, pdf=True):
    db.upsert_project(project_id, blob or _blob(), user_id=user_id)
    if pdf:
        storage.get_storage().put(storage.pdf_key(project_id), _drawing())


def _wait(client, project_id, job, timeout=60.0):
    end = time.time() + timeout
    while time.time() < end:
        s = client.get(f"/api/projects/{project_id}/detect-run/{job}")
        assert s.status_code == 200, s.text
        body = s.json()
        if body["result_ready"] or body["failed"]:
            return body
        time.sleep(0.02)
    raise AssertionError("the job never finished")


def _run(client, body=None, project_id="p1"):
    r = client.post(f"/api/projects/{project_id}/detect-run", json=body if body is not None else {})
    assert r.status_code == 200, r.text
    return _wait(client, project_id, r.json()["job"])


def _status(out, sid):
    return next(s for s in out["stages"] if s["id"] == sid)


def test_the_lanes_steps_are_hooked_and_pass_through():
    for name, stage in dr._HOOKED.items():
        assert getattr(getattr(gl, name), "_detect_run_stage", None) == stage, name
    parsed = copy.deepcopy(_blob())
    assert gl.apply_geometry(parsed, _drawing())["status"] == "applied"     # no listener: the lane as ever


def test_the_stages_arrive_in_the_lanes_order_and_end_in_the_browser(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store()
    entered: list[str] = []
    real = dr._Job.enter

    def spy(self, sid):
        entered.append(sid)
        return real(self, sid)
    monkeypatch.setattr(dr._Job, "enter", spy)
    out = _run(TestClient(app), {"pages": [1]})
    order = [s for i, s in enumerate(entered) if s not in entered[:i]]
    assert order == ["mastelis", "tekstas", "patalpos", "konturai", "angos", "sienos", "grindys", "kiekiai"]
    assert [s["id"] for s in out["stages"]] == list(dr.STAGE_IDS)
    assert all(s["label_lt"] and s["about_lt"] for s in out["stages"])
    for sid in dr.LANE_STAGES:
        st = _status(out, sid)
        assert st["status"] == "done" and st["note"] and st["finished"] >= st["started"], sid
    assert _status(out, "kiekiai")["status"] == "running", "the browser rebuilds the rows and finishes it"
    assert out["result_ready"] and not out["failed"] and out["stage"] == "kiekiai"
    assert _status(out, "konturai")["note"] == "2 kontūrai iš sienų."
    assert _status(out, "sienos")["note"] == "2 perimetrai iš matmenų."
    res = out["result"]
    r1, r2 = res["patalpos"]
    assert r1["polygon_source"] == "vektoriniai_konturai" and r1["perimetras_m"] == 14.0 and r2["perimetras_m"] == 12.0
    assert res["taikymas"] == {"puslapiai": [1], "funkcijos": list(dr.FEATURES), "patalpos": ["01", "02"]}
    assert out["per_page"]["1"]["patalpos"] == ["01", "02"] and out["per_page"]["1"]["konturai"] == 2
    # the sheet's plan holds every room: this is the whole read, and the project takes the lane's version
    assert res["_meta"]["geometrija"]["versija"] == gl.LANE_VERSION


def test_the_result_has_the_free_rereads_shape_and_the_server_saves_nothing(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store()
    before = copy.deepcopy(db.get_project("p1"))
    out = _run(TestClient(app))
    res = out["result"]
    for key in ("status", "lane", "patalpos", "_meta", "santrauka"):
        assert key in res, key
    assert res["lane"] == "applied" and res["_meta"]["geometrija"]["versija"] == gl.LANE_VERSION
    after = db.get_project("p1")
    assert after["patalpos"] == before["patalpos"] and after.get("_meta") == before.get("_meta")


def test_rereading_keeps_the_outline_he_corrected(tmp_path, monkeypatch):
    """„Perskaityti iš naujo" (Togal's Re-Togal) never replaces an outline a person corrected — the lane keeps
    `corrected` / `manual`; this pins that the job hands it back untouched, twice in a row."""
    _isolate(tmp_path, monkeypatch)
    _store(blob=_blob(corrected=True))
    client = TestClient(app)
    for _ in range(2):
        out = _run(client, {"pages": [1]})
        r1 = next(r for r in out["result"]["patalpos"] if r["nr"] == "01")
        assert r1["polygon_source"] == "corrected" and r1["polygon_pct"] == CORRECTED
        assert _status(out, "konturai")["note"] == "1 kontūras iš sienų, jūsų pataisytų palikta: 1."


def test_a_sheet_that_is_not_the_rooms_plan_changes_no_room(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store()
    out = _run(TestClient(app), {"pages": [3]})
    stored = db.get_project("p1")["patalpos"]
    assert out["result"]["patalpos"] == stored
    assert out["result"]["taikymas"]["patalpos"] == []
    assert _status(out, "patalpos")["note"] == "Šis lapas nėra patalpų planas — patalpos jame neskaitomos."
    # a narrowed read keeps the project's lane version: the full free re-read is still offered
    assert out["result"]["_meta"]["geometrija"]["versija"] is None


def test_a_feature_he_did_not_choose_keeps_its_stored_keys(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store()
    out = _run(TestClient(app), {"features": {"grindys": True}})
    assert out["features"] == ["plotai", "grindys"] and out["features_added"] == ["plotai"]
    r1 = next(r for r in out["result"]["patalpos"] if r["nr"] == "01")
    assert r1["polygon_source"] == "synthesized_from_bbox" and r1["perimetras_m"] == 13.9
    assert "_konturas" not in r1 and "_angos_sienose" not in r1
    for sid in ("konturai", "angos", "sienos"):
        st = _status(out, sid)
        assert st["status"] == "skipped" and st["note"] == dr.NOT_CHOSEN, sid


def test_walls_bring_the_outlines_they_are_added_along(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store()
    out = _run(TestClient(app), {"features": {"sienos": True}})
    assert out["features"] == ["plotai", "konturai", "sienos"] and out["features_added"] == ["plotai", "konturai"]
    r1 = next(r for r in out["result"]["patalpos"] if r["nr"] == "01")
    assert r1["polygon_source"] == "vektoriniai_konturai" and r1["perimetras_m"] == 14.0


def test_a_broken_lane_names_its_stage_and_changes_nothing(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store()

    def broken_trace(*a, **kw):
        raise RuntimeError("no walls")
    # inside the lane's own try: the lane answers `failed`, and the stage it was in is the one named. The broken
    # step is hooked like the real one (monkeypatch puts the real one back afterwards).
    monkeypatch.setattr(gl, "trace_vector_rooms", broken_trace)
    dr._install_stage_hooks()
    out = _run(TestClient(app))
    assert out["failed"] and not out["result_ready"] and "result" not in out
    assert _status(out, "konturai")["status"] == "failed"
    assert _status(out, "konturai")["note"] == dr.LANE_FAILED
    for sid in ("mastelis", "tekstas", "patalpos"):
        assert _status(out, sid)["status"] == "done", sid
    for sid in ("angos", "sienos", "grindys", "kiekiai"):
        assert _status(out, sid)["status"] == "skipped" and _status(out, sid)["note"] == dr.FAILED_BEFORE, sid
    assert "p1" not in fr._running, "a failed run frees the project"


def test_without_the_drawing_it_says_so(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store(pdf=False)
    r = TestClient(app).post("/api/projects/p1/detect-run", json={})
    assert r.status_code == 404 and "brėžinio saugykloje nėra" in r.json()["detail"]
    assert "p1" not in fr._running


def test_the_body_is_checked(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store()
    c = TestClient(app)
    for body in ({"pages": []}, {"pages": [0]}, {"pages": "1"}, {"features": {"stogas": True}},
                 {"features": {"grindys": "taip"}}, {"features": {"grindys": False}}, {"kas": 1}, [1]):
        r = c.post("/api/projects/p1/detect-run", json=body)
        assert r.status_code == 400, (body, r.text)
    assert not dr._jobs


def test_a_running_read_of_the_project_is_followed_not_doubled(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store()
    fr._running.add("p1")                     # the plain free re-read is reading it
    r = TestClient(app).post("/api/projects/p1/detect-run", json={})
    assert r.status_code == 409
    fr._running.discard("p1")


def test_an_unknown_job_or_another_projects_job_is_not_found(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store("p1")
    _store("p2")
    c = TestClient(app)
    out = _run(c, project_id="p1")
    assert c.get("/api/projects/p1/detect-run/nera").status_code == 404
    assert c.get(f"/api/projects/p2/detect-run/{out['job']}").status_code == 404


def test_finished_jobs_expire(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store()
    c = TestClient(app)
    out = _run(c)
    dr._purge(now=time.time() + dr.JOB_TTL_S + 1)
    assert c.get(f"/api/projects/p1/detect-run/{out['job']}").status_code == 404


def test_another_users_project_is_not_found_before_the_body_is_read(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch, auth_disabled=False)
    owner = db.create_user("owner@x.lt", auth.hash_password(_PW), name="O")
    db.create_user("thief@x.lt", auth.hash_password(_PW), name="T")
    _store(user_id=owner["id"])
    mine, other = TestClient(app), TestClient(app)
    assert mine.post("/api/auth/login", json={"email": "owner@x.lt", "password": _PW}).status_code == 200
    assert other.post("/api/auth/login", json={"email": "thief@x.lt", "password": _PW}).status_code == 200
    out = _run(mine, {"pages": [1]})
    # a malformed body from someone else still answers 404, never 400: the gate comes first
    assert other.post("/api/projects/p1/detect-run", json={"pages": "bad"}).status_code == 404
    assert other.post("/api/projects/p1/detect-run", json={}).status_code == 404
    assert other.get(f"/api/projects/p1/detect-run/{out['job']}").status_code == 404
    assert TestClient(app).post("/api/projects/p1/detect-run", json={}).status_code == 401
    assert TestClient(app).get(f"/api/projects/p1/detect-run/{out['job']}").status_code == 401
