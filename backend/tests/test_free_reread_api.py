"""`/api/projects/{id}/free-reread` — the geometry lane for a project that is
already stored, without a Vision call.

The lane (vector outlines, perimeters ADDED from the written strings, floor
coverings off the floor plan) ran only inside a full — paid — extraction, so a
project read before it existed showed exactly what the founder complained
about on 2026-09-17, and the only free way to refresh it was a localhost dev
script. The lane needs nothing but the stored PDF and the stored rooms.

The server only READS: it answers with the lane's rooms and meta and saves
nothing — merging with his corrections and rebuilding the rows stays on the one
path every other edit takes (mergeReextractRooms → /recompute-interior →
mergeDarbuSarasasEdits → the project store).
"""
from __future__ import annotations

import copy
import threading

import pytest
from fastapi.testclient import TestClient

from main import app  # noqa: E402

import auth  # noqa: E402
import db  # noqa: E402
import storage  # noqa: E402
from api import free_reread as fr  # noqa: E402
from extractor import geometry_lane as gl  # noqa: E402
from tests.synthetic_plan import build_plan, two_rooms  # noqa: E402

_PW = "passw0rd123"


def _isolate(tmp_path, monkeypatch, *, auth_disabled=True):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "free_reread.db")
    monkeypatch.setattr(auth, "AUTH_DISABLED", auth_disabled)
    for k in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("LOCAL_STORAGE_DIR", str(tmp_path / "pdfs"))
    storage.reset_storage_for_test()
    db.init_schema()
    db._migrate_schema()


def _blob(**meta):
    rooms = [
        {"nr": "01", "pavadinimas": "A", "plotas_m2": 12.0, "plotas_saltinis": "eksplikacija", "puslapio_nr": 1,
         "perimetras_m": 13.9, "bbox_pct": {"x": 0.12, "y": 0.10, "w": 0.2, "h": 0.12},
         "polygon_pct": [[0.12, 0.10], [0.32, 0.10], [0.32, 0.22], [0.12, 0.22]], "polygon_source": "synthesized_from_bbox"},
        {"nr": "02", "pavadinimas": "B", "plotas_m2": 9.0, "plotas_saltinis": "eksplikacija", "puslapio_nr": 1,
         "perimetras_m": 12.3},
    ]
    return {"name": "P", "tipas": "interjeras", "patalpos": rooms,
            "puslapiai": [{"nr": 1, "tipas": "floor_plan"}, {"nr": 2, "tipas": "floor_plan"}],
            "_meta": {"model": "x", **meta}}


def _two_sheets() -> bytes:
    a = two_rooms()
    a.dims = []                        # the layout sheet: badges, no wall lengths
    b = two_rooms()
    b.badges = []                      # the wall painting plan: wall lengths, no badges
    return build_plan([a, b])


def _store(project_id="p1", *, user_id=None, blob=None, pdf=True):
    db.upsert_project(project_id, blob or _blob(), user_id=user_id)
    if pdf:
        storage.get_storage().put(storage.pdf_key(project_id), _two_sheets())


def test_the_lane_writes_its_version():
    parsed = copy.deepcopy(_blob())
    gl.apply_geometry(parsed, _two_sheets())
    assert parsed["_meta"]["geometrija"]["versija"] == gl.LANE_VERSION >= 3


def test_status_a_project_read_before_the_lane_can_be_read_again_for_free(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store()
    r = TestClient(app).get("/api/projects/p1/free-reread")
    assert r.status_code == 200
    assert r.json() == {"available": True, "needed": True, "versija": gl.LANE_VERSION,
                        "projekto_versija": None, "reason": None}


def test_status_an_older_lane_version_is_offered_the_newer_one(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store(blob=_blob(geometrija={"versija": gl.LANE_VERSION - 1}))
    body = TestClient(app).get("/api/projects/p1/free-reread").json()
    assert body["needed"] is True and body["projekto_versija"] == gl.LANE_VERSION - 1


def test_status_a_project_the_current_lane_has_read_is_not_offered_again(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store(blob=_blob(geometrija={"versija": gl.LANE_VERSION}))
    body = TestClient(app).get("/api/projects/p1/free-reread").json()
    assert body["available"] is True and body["needed"] is False


def test_status_without_the_drawing_there_is_nothing_to_read(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store(pdf=False)
    body = TestClient(app).get("/api/projects/p1/free-reread").json()
    assert body["available"] is False and body["needed"] is False
    assert body["reason"] == "Šio projekto brėžinio saugykloje nėra — perskaityti iš naujo galima tik įkėlus PDF."


def test_the_read_returns_the_lanes_rooms_and_saves_nothing(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store()
    before = copy.deepcopy(db.get_project("p1"))
    r = TestClient(app).post("/api/projects/p1/free-reread")
    assert r.status_code == 200
    out = r.json()
    assert out["status"] == "ok" and out["lane"] == "applied"
    r1, r2 = out["patalpos"]
    assert r1["perimetras_m"] == 14.0 and r1["perimetras_saltinis"] == "matmenu_eilutes"
    assert r1["polygon_source"] == "vektoriniai_konturai" and r2["perimetras_m"] == 12.0
    assert out["_meta"]["geometrija"]["versija"] == gl.LANE_VERSION
    assert out["_meta"]["model"] == "x", "the rest of the project's meta rides along"
    assert out["santrauka"] == {"konturai": 2, "perimetrai_sudeti": 2, "perimetrai_tusti": 0, "grindu_dangos": 0,
                                "sekundes": out["santrauka"]["sekundes"]}
    after = db.get_project("p1")
    assert after["patalpos"] == before["patalpos"] and after.get("_meta") == before.get("_meta")


def test_a_project_without_its_drawing_says_so(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store(pdf=False)
    r = TestClient(app).post("/api/projects/p1/free-reread")
    assert r.status_code == 404 and "brėžinio saugykloje nėra" in r.json()["detail"]


def test_a_lane_that_breaks_changes_nothing_and_says_so(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store()

    def boom(parsed, pdf_bytes, dims=None, **kw):
        raise RuntimeError("no")
    monkeypatch.setattr(fr, "apply_geometry", boom)
    r = TestClient(app).post("/api/projects/p1/free-reread")
    assert r.status_code == 200
    out = r.json()
    assert out["status"] == "ok" and out["lane"] == "failed"
    assert out["patalpos"] == db.get_project("p1")["patalpos"]


def test_one_read_per_project_at_a_time(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _store()
    started, release = threading.Event(), threading.Event()
    real = fr.apply_geometry

    def slow(parsed, pdf_bytes, dims=None, **kw):
        started.set()
        release.wait(timeout=10)
        return real(parsed, pdf_bytes, dims)
    monkeypatch.setattr(fr, "apply_geometry", slow)
    c = TestClient(app)
    first: dict = {}
    t = threading.Thread(target=lambda: first.update(code=c.post("/api/projects/p1/free-reread").status_code))
    t.start()
    assert started.wait(timeout=10)
    try:
        assert c.post("/api/projects/p1/free-reread").status_code == 409
    finally:
        release.set()
        t.join(timeout=20)
    assert first["code"] == 200
    assert c.post("/api/projects/p1/free-reread").status_code == 200, "the guard is released afterwards"


def test_anonymous_callers_get_401(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch, auth_disabled=False)
    _store()
    c = TestClient(app)
    assert c.get("/api/projects/p1/free-reread").status_code == 401
    assert c.post("/api/projects/p1/free-reread").status_code == 401


def test_a_stranger_cannot_read_someone_elses_project(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch, auth_disabled=False)
    owner = db.create_user("owner@x.lt", auth.hash_password(_PW), name="O")
    db.create_user("thief@x.lt", auth.hash_password(_PW), name="T")
    _store(user_id=owner["id"])
    c = TestClient(app)
    assert c.post("/api/auth/login", json={"email": "thief@x.lt", "password": _PW}).status_code == 200
    assert c.get("/api/projects/p1/free-reread").status_code == 404
    assert c.post("/api/projects/p1/free-reread").status_code == 404


@pytest.mark.parametrize("bad", ["..%2F..%2Fetc", "a b"])
def test_a_strange_project_id_is_rejected(tmp_path, monkeypatch, bad):
    _isolate(tmp_path, monkeypatch)
    assert TestClient(app).get(f"/api/projects/{bad}/free-reread").status_code in (400, 404)


def test_status_a_project_read_at_lane_version_11_is_offered_the_evidence_refresh(tmp_path, monkeypatch):
    """LANE_VERSION 12 (2026-10-16): the walls' strings carry `ilgis_pt` for the viewer's scale check — a
    project read at 11 is offered the free re-read."""
    _isolate(tmp_path, monkeypatch)
    _store(blob=_blob(geometrija={"versija": 11}))
    body = TestClient(app).get("/api/projects/p1/free-reread").json()
    assert gl.LANE_VERSION >= 12
    assert body["needed"] is True and body["projekto_versija"] == 11


def test_status_a_project_read_at_lane_version_12_is_offered_the_reader_frame_reread(tmp_path, monkeypatch):
    """LANE_VERSION 13 (2026-10-18): the readers take the display frame from the page — a turned sheet whose
    drawing sits inside the short side was read in the wrong orientation; a project read at 12 is offered the
    free re-read."""
    _isolate(tmp_path, monkeypatch)
    _store(blob=_blob(geometrija={"versija": 12}))
    body = TestClient(app).get("/api/projects/p1/free-reread").json()
    assert gl.LANE_VERSION >= 13                 # 14 (2026-10-24): every scale from geometry/scale.py
    assert body["needed"] is True and body["projekto_versija"] == 12



# ── Pathon v3 W5-D D6: figures + heights behind SAMATU_REREAD_FIGURES ──────────────────────────────────

def test_figures_and_heights_are_off_by_default_and_read_with_the_flag(monkeypatch):
    from extractor import plan_area_annotations as pa
    calls = []

    def fake_scan(pdf, pages=None):
        calls.append(pages)
        return {"figures": [{"page": 2, "label": "Sienų dažai", "value": 120, "unit": "m2", "family": "sienu_dazymas"}],
                "heights": [], "annotations": []}
    monkeypatch.setattr(pa, "scan_text_layer", fake_scan)
    parsed = {"patalpos": [{"nr": "1"}], "puslapiai": []}
    monkeypatch.delenv(fr.FIGURES_FLAG, raising=False)
    assert fr.read_figures_and_heights(parsed, b"%PDF", "p") == {} and calls == []
    monkeypatch.setenv(fr.FIGURES_FLAG, "1")
    out = fr.read_figures_and_heights(parsed, b"%PDF", "p")
    assert out["_autoriaus_kiekiai"][0]["value"] == 120
    assert parsed["_meta"]["plan_height_statement"]["status"] == "none"


def test_figures_never_fail_the_read(monkeypatch):
    from extractor import plan_area_annotations as pa
    monkeypatch.setenv(fr.FIGURES_FLAG, "1")
    monkeypatch.setattr(pa, "scan_text_layer", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    assert fr.read_figures_and_heights({"patalpos": []}, b"%PDF", "p") == {}
