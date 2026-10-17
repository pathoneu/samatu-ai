"""api/pdf_revisions.py — a second edition of the drawing laid over the project's own (synthetic plans)."""
from __future__ import annotations

import io

import numpy as np
from fastapi.testclient import TestClient
from PIL import Image

from main import app  # noqa: E402

import auth  # noqa: E402
import db  # noqa: E402
import main  # noqa: E402
import storage  # noqa: E402
import api.pdf_revisions as rev  # noqa: E402
from extractor import cv_render_cache  # noqa: E402
from tests.synthetic_plan import Sheet, build_plan, two_rooms  # noqa: E402

OLD = build_plan([two_rooms(), Sheet(title="FASADAS")])


def _build_revised() -> bytes:
    sheet = two_rooms()
    walls = list(sheet.walls)
    for i in (5, 6):                                       # the partition moved 0,6 m to the right
        x0, y0, x1, y1 = walls[i]
        walls[i] = (x0 + 0.6, y0, x1 + 0.6, y1)
    return build_plan([Sheet(walls=walls, badges=sheet.badges, offset_m=(0.5, 0.3)), Sheet(title="FASADAS")])


REVISED = _build_revised()


def _revised() -> bytes:
    return REVISED


def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "rev.db")
    monkeypatch.setattr(auth, "AUTH_DISABLED", True)
    for k in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("LOCAL_STORAGE_DIR", str(tmp_path / "pdfs"))
    monkeypatch.setattr(cv_render_cache, "CACHE_DIR", tmp_path / "cv_cache")
    storage.reset_storage_for_test()
    db.init_schema()
    db._migrate_schema()
    main._RATE_BUCKET.clear()
    rev._PNG_CACHE.clear()
    db.upsert_project("p1", {"name": "P", "tipas": "interjeras", "_meta": {"model": "x"}})
    storage.get_storage().put(storage.pdf_key("p1"), OLD)


def _upload(client, data=None, name="Planas v2.pdf"):
    return client.post("/api/projects/p1/pdf-revisions",
                       files={"pdf_file": (name, data or _revised(), "application/pdf")})


def _rgba(resp):
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "image/png"
    return np.array(Image.open(io.BytesIO(resp.content)).convert("RGBA"))


def test_upload_matches_sheets_keeps_the_drawing_and_is_a_version(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    client = TestClient(app)
    r = _upload(client)
    assert r.status_code == 200, r.text
    rec = r.json()["leidimas"]
    assert rec["puslapiai"] == 2 and rec["pavadinimas"] == "Planas v2.pdf"
    assert rec["lapai"]["1"]["budas"] == "sienos" and rec["lapai"]["1"]["old_page"] == 1
    assert rec["lapai"]["2"]["budas"] == "lapo_krastai"
    assert rec["pagal_sena"]["1"]["naujas_lapas"] == 1
    # the project's own drawing is untouched; the new one has its own key
    st = storage.get_storage()
    assert st.get(storage.pdf_key("p1")) == OLD
    assert st.get(rev.revision_key("p1", rec["id"])) == _revised()
    # the record rides the project, as a version of its own
    saved = r.json()["project"]
    assert saved["_meta"]["brezinio_leidimai"][0]["id"] == rec["id"] and saved["_meta"]["model"] == "x"
    versions = db.list_project_versions("p1")
    assert (versions[0]["saltinis"], versions[0]["pavadinimas"]) == ("kita", "Įkeltas naujas brėžinio leidimas")
    listed = client.get("/api/projects/p1/pdf-revisions").json()["leidimai"]
    assert [x["id"] for x in listed] == [rec["id"]]


def test_upload_refuses_non_pdf_and_a_project_without_a_drawing(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    client = TestClient(app)
    assert _upload(client, data=b"not a pdf").status_code == 400
    storage.get_storage().delete(storage.pdf_key("p1"))
    r = _upload(client)
    assert r.status_code == 404 and "pirmąjį brėžinį" in r.json()["detail"]
    assert client.get("/api/projects/p1/pdf-revisions").json()["leidimai"] == []


def test_skirtumas_shows_the_moved_partition_in_two_tints(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    client = TestClient(app)
    rid = _upload(client).json()["leidimas"]["id"]
    img = _rgba(client.get(f"/api/projects/p1/pdf-revisions/{rid}/overlay/1?mode=skirtumas&dpi=72"))
    old = cv_render_cache.render_page(OLD, 0, 72)
    assert img.shape[:2] == old.shape[:2]                       # in the OLD sheet's frame
    green = (img[..., 3] == 255) & (img[..., 0] == rev.NAUJA_RGB[0]) & (img[..., 1] == rev.NAUJA_RGB[1])
    clay = (img[..., 3] == 255) & (img[..., 0] == rev.ISBRAUKTA_RGB[0]) & (img[..., 1] == rev.ISBRAUKTA_RGB[1])
    # at 72 dpi one point is one pixel: the old partition stands at x ≈ 179–185, the moved one at ≈ 196–202,
    # its lower piece at y ≈ 134–164 (ORIGIN + metres × 28,35)
    rows = slice(140, 160)
    assert clay[rows, 176:190].any(axis=1).all()              # where it was: „išbraukta"
    assert green[rows, 193:207].any(axis=1).all()             # where it is now: „nauja"
    assert not green[rows, 176:190].any() and not clay[rows, 193:207].any()
    # the outer top wall is in both editions, laid over each other: nothing drawn over it
    painted = img[..., 3] > 0
    assert not painted[81:85, 70:260].any()
    assert (old < rev.INK)[81:85, 70:260].all()
    naujas = _rgba(client.get(f"/api/projects/p1/pdf-revisions/{rid}/overlay/1?mode=naujas&dpi=72"))
    assert (naujas[..., 3] > 0).sum() > painted.sum()          # every new line, not only the changed ones


def test_compose_overlay_lays_the_new_sheet_by_the_transform():
    old = np.full((100, 100), 255, np.uint8)
    old[40:42, 10:90] = 0                                       # a line at y = 40
    new = np.full((100, 100), 255, np.uint8)
    new[30:32, 10:90] = 0                                       # the same line, drawn 10 px higher
    lapas = {"k": 1.0, "dx": 0.0, "dy": 10.0}                   # old = new + 10 (at 72 dpi, 1 pt = 1 px)
    out = rev.compose_overlay(old, new, lapas, 72, "skirtumas")
    assert (out[..., 3] > 0).sum() == 0                         # laid right, nothing changed


def test_render_cache_rate_limit_and_errors(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    client = TestClient(app)
    rid = _upload(client).json()["leidimas"]["id"]
    page = _rgba(client.get(f"/api/projects/p1/pdf-revisions/{rid}/pages/1/render?dpi=999"))
    assert abs(page.shape[1] - 595.28 * rev.MAX_DPI / 72) <= 1  # dpi capped at 150
    calls = []
    real = rev.compose_overlay
    monkeypatch.setattr(rev, "compose_overlay", lambda *a, **k: calls.append(1) or real(*a, **k))
    for _ in range(3):
        client.get(f"/api/projects/p1/pdf-revisions/{rid}/overlay/1?dpi=72")
    assert len(calls) == 1                                      # composed once, then cached
    assert client.get(f"/api/projects/p1/pdf-revisions/{rid}/overlay/1?mode=blend").status_code == 400
    assert client.get(f"/api/projects/p1/pdf-revisions/{rid}/overlay/9").status_code == 404
    assert client.get("/api/projects/p1/pdf-revisions/nope/overlay/1").status_code == 404
    assert client.get(f"/api/projects/p1/pdf-revisions/{rid}/pages/9/render").status_code == 404
    main._RATE_BUCKET.clear()
    codes = [client.get(f"/api/projects/p1/pdf-revisions/{rid}/overlay/1?dpi=72").status_code for _ in range(40)]
    assert 429 in codes


def test_delete_drops_record_and_file_and_project_delete_purges(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    client = TestClient(app)
    a = _upload(client).json()["leidimas"]["id"]
    b = _upload(client, name="v3.pdf").json()["leidimas"]["id"]
    r = client.delete(f"/api/projects/p1/pdf-revisions/{a}")
    assert r.status_code == 200
    assert [x["id"] for x in client.get("/api/projects/p1/pdf-revisions").json()["leidimai"]] == [b]
    st = storage.get_storage()
    assert st.get(rev.revision_key("p1", a)) is None and st.get(rev.revision_key("p1", b)) is not None
    assert client.delete("/api/projects/p1").status_code == 200
    assert st.get(rev.revision_key("p1", b)) is None
    assert list(st.list_keys(rev.revision_prefix("p1"))) == []


def test_file_name_is_scrubbed_where_served(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    monkeypatch.setattr(rev.user_text, "scrub_text", lambda text, fallback="": fallback if "SLAPTA" in text else text)
    client = TestClient(app)
    rec = _upload(client, name="SLAPTA klientas.pdf").json()["leidimas"]
    assert rec["pavadinimas"] == "Naujas leidimas"
    assert client.get("/api/projects/p1/pdf-revisions").json()["leidimai"][0]["pavadinimas"] == "Naujas leidimas"
