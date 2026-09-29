"""Spend metering, direction 1 — endpoints that never call Anthropic must not
write a spend reservation and must not be blocked by the daily € cap.

Audit 2026-09-29 (llm-api-2 / data-ops-infra-2): /recompute-interior, the
OpenCV routes (/api/click-to-fill, detect-room-polygons, /api/cv/*) and
/detect-type (a pdfplumber text scan) went through the billable dependency,
which writes a 0.15 € `reserve:` row per call. With a daily cap switched on, a
contractor editing rooms would be locked out after a few edits without any AI
being used. Paid endpoints must keep reserving and keep being blocked.

Real auth (a logged-in user), a hermetic DB per test, no Anthropic call: the
one paid endpoint exercised here has its Vision function stubbed.
"""
from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient

import main  # noqa: E402  (must precede `import auth` so load_dotenv runs first)
from main import app  # noqa: E402

import auth  # noqa: E402
import db  # noqa: E402
import page_raster_cache as _pdf_cache  # noqa: E402

_PW = "passw0rd123"
_PROJECT = "proj-free-1"


@pytest.fixture()
def user(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "free_endpoints.db")
    monkeypatch.setattr(auth, "AUTH_DISABLED", False)
    db.init_schema()
    db._migrate_schema()
    _pdf_cache.clear_pdf_cache()
    u = db.create_user("free@x.lt", auth.hash_password(_PW), name="Free")
    db.upsert_project(_PROJECT, {"name": "P", "tipas": "interjeras"}, user_id=u["id"])
    yield u
    _pdf_cache.clear_pdf_cache()


def _login():
    c = TestClient(app)
    r = c.post("/api/auth/login", json={"email": "free@x.lt", "password": _PW})
    assert r.status_code == 200, r.text
    return c


def _exhaust_daily_cap(monkeypatch, user_id):
    monkeypatch.setattr(main, "_USER_DAILY_SPEND_CAP_EUR", 0.50)
    db.record_reservation(user_id, 1.00, kind="reserve:/extract")


def _rows(user_id):
    with db._conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT kind, cost_eur FROM usage_events WHERE user_id = ?", (user_id,))]


def _tiny_pdf() -> bytes:
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    cv = canvas.Canvas(buf)
    cv.drawString(72, 720, "Patalpu eksplikacija")
    cv.save()
    return buf.getvalue()


_ROOM = {"nr": "1", "pavadinimas": "Kambarys", "paskirtis": "gyvenamoji",
         "plotas_m2": 12.0, "perimetras_m": 14.0, "lubu_aukstis_m": 2.7}


def _call_free(c, name):
    if name == "recompute-interior":
        return c.post("/recompute-interior", json={"patalpos": [dict(_ROOM)]})
    if name == "detect-type":
        return c.post("/detect-type",
                      files={"file": ("plan.pdf", _tiny_pdf(), "application/pdf")})
    if name == "click-to-fill":
        return c.post("/api/click-to-fill", data={
            "project_id": _PROJECT, "page_nr": "1",
            "click_x_pct": "0.5", "click_y_pct": "0.5"})
    if name == "detect-room-polygons":
        return c.post(f"/api/projects/{_PROJECT}/detect-room-polygons",
                      data={"page_nr": "1", "rooms_json": "[]"})
    if name == "cv-match-template":
        return c.post("/api/cv/match-template", json={
            "project_id": _PROJECT, "page_idx": 0, "bbox": [10, 10, 30, 30], "dpi": 100})
    if name == "cv-magic-wand":
        return c.post("/api/cv/magic-wand", json={
            "project_id": _PROJECT, "page_idx": 0, "click": [10, 10], "dpi": 100})
    raise AssertionError(name)


_FREE = ("recompute-interior", "detect-type", "click-to-fill",
         "detect-room-polygons", "cv-match-template", "cv-magic-wand")


@pytest.mark.parametrize("name", _FREE)
def test_free_endpoint_writes_no_reservation_and_ignores_the_cap(user, monkeypatch, name):
    _exhaust_daily_cap(monkeypatch, user["id"])
    before = _rows(user["id"])
    r = _call_free(_login(), name)
    # Not the spend-cap 429. (The OpenCV routes answer 400/409 here because no
    # PDF is cached — that is their own validation, reached AFTER auth.)
    assert r.status_code != 429, r.text
    assert r.status_code in (200, 400, 409), r.text
    assert _rows(user["id"]) == before, "a free endpoint wrote a spend row"


@pytest.mark.parametrize("name", _FREE)
def test_free_endpoint_still_requires_login(user, name):
    r = _call_free(TestClient(app), name)
    assert r.status_code == 401, r.text


def test_paid_endpoint_still_blocked_by_the_cap(user, monkeypatch):
    import interior_v9
    called = []
    monkeypatch.setattr(interior_v9, "detect_symbols",
                        lambda *a, **k: called.append(1) or {"count": 0})
    _exhaust_daily_cap(monkeypatch, user["id"])
    r = _login().post("/v9/symbols/detect",
                      files={"files": ("plan.pdf", _tiny_pdf(), "application/pdf")},
                      data={"symbol_type": "rozetes", "page_nr": "1"})
    assert r.status_code == 429, r.text
    assert not called


def test_paid_endpoint_still_reserves(user, monkeypatch):
    import interior_v9
    monkeypatch.setattr(interior_v9, "detect_symbols", lambda *a, **k: {"count": 0})
    monkeypatch.setattr(main, "_USER_DAILY_SPEND_CAP_EUR", 0.0)
    r = _login().post("/v9/symbols/detect",
                      files={"files": ("plan.pdf", _tiny_pdf(), "application/pdf")},
                      data={"symbol_type": "rozetes", "page_nr": "1"})
    assert r.status_code == 200, r.text
    kinds = [row["kind"] for row in _rows(user["id"])]
    assert kinds == ["reserve:/v9/symbols/detect"]


def test_unmounted_stub_routes_are_not_billable():
    """vision-fill and lasso-rerun are unmounted stubs with no Anthropic call
    (a placeholder square, an empty list). If they are mounted again as they
    are, they must not charge; wiring a real Vision call there means switching
    them back to require_billable_user."""
    from api import lasso_rerun, vision_fill
    for router in (vision_fill.router, lasso_rerun.router):
        for route in router.routes:
            calls = [d.call for d in route.dependant.dependencies]
            assert auth.require_billable_user not in calls, route.path
            assert auth.require_user in calls, route.path
