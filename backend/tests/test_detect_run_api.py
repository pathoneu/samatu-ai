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
from tests.synthetic_plan import Sheet, build_plan, pocket_and_room, two_rooms  # noqa: E402

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


LANE_STAGES = ["mastelis", "tekstas", "planas", "konturai", "angos", "sienos", "grindys"]


def test_the_lane_names_its_steps_to_a_listener_in_order():
    seen: list[str] = []
    gl.apply_geometry(copy.deepcopy(_blob()), _drawing(), on_stage=seen.append)
    assert seen == LANE_STAGES


def test_a_listener_changes_nothing_the_lane_reads():
    quiet, heard = copy.deepcopy(_blob()), copy.deepcopy(_blob())
    a = gl.apply_geometry(quiet, _drawing())
    b = gl.apply_geometry(heard, _drawing(), on_stage=lambda _s: None)
    a.pop("seconds"), b.pop("seconds")
    quiet["_meta"]["geometrija"].pop("seconds"), heard["_meta"]["geometrija"].pop("seconds")
    assert a == b and quiet == heard


def test_a_listener_that_raises_changes_nothing_either():
    quiet, loud = copy.deepcopy(_blob()), copy.deepcopy(_blob())

    def boom(_stage):
        raise RuntimeError("listener")
    a = gl.apply_geometry(quiet, _drawing())
    b = gl.apply_geometry(loud, _drawing(), on_stage=boom)
    a.pop("seconds"), b.pop("seconds")
    quiet["_meta"]["geometrija"].pop("seconds"), loud["_meta"]["geometrija"].pop("seconds")
    assert b["status"] == "applied" and a == b and quiet == loud


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
    assert order == ["mastelis", "tekstas", "planas", "konturai", "angos", "sienos", "grindys", "kiekiai"]
    assert [s["id"] for s in out["stages"]] == list(dr.STAGE_IDS)
    assert all(s["label_lt"] and s["about_lt"] for s in out["stages"])
    for sid in dr.LANE_STAGES:
        st = _status(out, sid)
        assert st["status"] == "done" and st["note"] and st["finished"] >= st["started"], sid
    assert _status(out, "kiekiai")["status"] == "perduota", "the browser rebuilds the rows and finishes it"
    assert out["skaitoma_lt"] == dr.SKAITOMA_LT and "visas brėžinys" in out["skaitoma_lt"]
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
    assert _status(out, "planas")["note"] == "Šis lapas nėra patalpų planas — patalpos jame neskaitomos."
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
    assert out["features"] == ["plotai", "konturai", "sienos", "angos"]
    assert out["features_added"] == ["plotai", "konturai", "angos"]
    r1 = next(r for r in out["result"]["patalpos"] if r["nr"] == "01")
    assert r1["polygon_source"] == "vektoriniai_konturai" and r1["perimetras_m"] == 14.0


def test_a_broken_lane_names_its_stage_and_changes_nothing(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store()

    def broken_trace(*a, **kw):
        raise RuntimeError("no walls")
    # inside the lane's own try: the lane answers `failed`, and the stage it was in is the one named
    monkeypatch.setattr(gl, "trace_vector_rooms", broken_trace)
    out = _run(TestClient(app))
    assert out["failed"] and not out["result_ready"] and "result" not in out
    assert _status(out, "konturai")["status"] == "failed"
    assert _status(out, "konturai")["note"] == dr.LANE_FAILED
    for sid in ("mastelis", "tekstas", "planas"):
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
    r = c.post("/api/projects/p1/detect-run", json={"pages": [99]})
    assert r.status_code == 400 and r.json()["detail"] == "Lapo 99 brėžinyje nėra (lapų: 3)"
    assert not dr._jobs and "p1" not in fr._running


def test_an_outline_brings_its_openings(tmp_path, monkeypatch):
    """The lane writes a room's openings in the frame of its outline: one never lands without the other."""
    _isolate(tmp_path, monkeypatch)
    _store()
    out = _run(TestClient(app), {"features": {"konturai": True}})
    assert out["features"] == ["plotai", "konturai", "angos"] and out["features_added"] == ["plotai", "angos"]
    r1 = next(r for r in out["result"]["patalpos"] if r["nr"] == "01")
    assert r1["polygon_source"] == "vektoriniai_konturai"
    assert r1["_angos_sienose"]["page"] == r1["_konturas"]["page"]


def test_a_second_start_follows_the_running_read(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store()
    release = __import__("threading").Event()
    real = fr.read_drawing

    def slow(*a, **kw):
        release.wait(timeout=10)
        return real(*a, **kw)
    monkeypatch.setattr(fr, "read_drawing", slow)
    c = TestClient(app)
    first = c.post("/api/projects/p1/detect-run", json={})
    again = c.post("/api/projects/p1/detect-run", json={"pages": [1]})
    release.set()
    assert first.status_code == 200 and again.status_code == 200
    assert again.json()["job"] == first.json()["job"] and again.json()["already_running"] is True
    assert len(dr._jobs) == 1
    _wait(c, "p1", first.json()["job"])


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


# ── what the landed record may name (_meta.geometrija) ──────────────────────

def _two_plans() -> bytes:
    a = two_rooms()
    a.badges = [b for b in a.badges if b[0] == "1"]          # plan 1: room 01
    b = pocket_and_room()
    b.badges = [x for x in b.badges if x[0] == "2"]          # plan 2 (other walls): room 02
    return build_plan([a, b])


def _two_plans_blob():
    return {"name": "P", "tipas": "interjeras",
            "patalpos": [{"nr": "01", "pavadinimas": "A", "plotas_m2": 12.0, "plotas_saltinis": "eksplikacija",
                          "puslapio_nr": 1, "perimetras_m": 13.9},
                         {"nr": "02", "pavadinimas": "B", "plotas_m2": 15.0, "plotas_saltinis": "eksplikacija",
                          "puslapio_nr": 2, "perimetras_m": 16.3}],
            "puslapiai": [{"nr": 1, "tipas": "floor_plan"}, {"nr": 2, "tipas": "floor_plan"}],
            "_meta": {"model": "x"}}


def _landed_record_agrees(out):
    rooms = {r["nr"]: r for r in out["result"]["patalpos"]}
    geo = out["result"]["_meta"]["geometrija"]
    for nr in geo["konturai"]:
        assert rooms[nr].get("polygon_source") == "vektoriniai_konturai", nr
    for nr in geo["perimetrai_sudeti"]:
        assert rooms[nr].get("perimetras_saltinis") in dr.FROM_DIMENSIONS, nr
    for nr in geo["angos_sienose"]:
        assert isinstance(rooms[nr].get("_angos_sienose"), dict), nr
    for nr in geo["grindu_dangos"]["perskaityta"]:
        assert rooms[nr].get("grindu_danga_saltinis") == gl.FLOOR_PLAN_SOURCE, nr
    for nr in geo["konturu_priezastys"]:
        assert rooms[nr].get("_konturo_priezastis"), nr
    return rooms, geo


def test_a_sheet_run_names_only_the_rooms_it_landed(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    db.upsert_project("p1", _two_plans_blob())
    storage.get_storage().put(storage.pdf_key("p1"), _two_plans())
    out = _run(TestClient(app), {"pages": [1]})
    rooms, geo = _landed_record_agrees(out)
    assert out["result"]["taikymas"]["patalpos"] == ["01"]
    assert rooms["02"] == db.get_project("p1")["patalpos"][1], "room 02 sits on the other plan: back as stored"
    for key in ("konturai", "perimetrai_sudeti", "perimetrai_tusti", "angos_sienose", "konturu_siulymai"):
        assert "02" not in geo[key], key
    assert "02" not in geo["konturu_priezastys"] and "02" not in geo["grindu_dangos"]["perskaityta"]
    assert geo["konturai"] == ["01"] and geo["perimetrai_sudeti"] == ["01"]
    assert geo["grupes"] == [[1], [2]], "sheet-level facts come from the read"
    assert sum(geo["vietos"].values()) == 1, "room 02 has no stored seat"


def test_a_floors_only_run_names_no_outline_or_wall_it_did_not_land(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    db.upsert_project("p1", _two_plans_blob())
    storage.get_storage().put(storage.pdf_key("p1"), _two_plans())
    out = _run(TestClient(app), {"features": {"grindys": True}})
    rooms, geo = _landed_record_agrees(out)
    assert geo["konturai"] == [] and geo["perimetrai_sudeti"] == [] and geo["angos_sienose"] == []
    assert geo["atviros_erdves"] == [] and geo["ribos"] == []
    assert geo["nupiesta"] == {"langai": 0, "durys": 0, "be_tarpo": 0}
    assert all(r["perimetras_m"] in (13.9, 16.3) for r in rooms.values())


def test_a_plotai_only_run_keeps_an_open_space_estimate(tmp_path, monkeypatch):
    """Every perimeter key the lane writes is in FEATURE_KEYS["sienos"]: a stored open-space estimate rides
    through a run that did not choose walls exactly as it was."""
    _isolate(tmp_path, monkeypatch)
    blob = _blob()
    blob["patalpos"][1].update({"perimetras_m": 11.1, "perimetras_saltinis": "atviros_erdves_ivertis",
                                "_perimetras_priezastis": "atvira erdvė su 01", "_perimetras_ivertis_m": 11.1,
                                "_perimetras_ivertis_saltinis": "atviros_erdves_konturas",
                                "_perimetras_pries_geometrija": 12.3})
    _store(blob=blob)
    stored = copy.deepcopy(db.get_project("p1")["patalpos"][1])
    out = _run(TestClient(app), {"features": {"plotai": True}})
    assert out["features"] == ["plotai"]
    r2 = next(r for r in out["result"]["patalpos"] if r["nr"] == "02")
    for key in dr.FEATURE_KEYS["sienos"]:
        assert r2.get(key) == stored.get(key), key
    for key in ("perimetras_m", "perimetras_saltinis", "_sienos", "_perimetras_suma", "_perimetras_pries_geometrija",
                "_perimetras_priezastis", "_perimetras_ivertis_m", "_perimetras_ivertis_saltinis"):
        assert key in dr.FEATURE_KEYS["sienos"], key
