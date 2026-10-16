"""POST /api/cv/find-symbol — the viewer's „Rasti panašius" box search.

A synthetic A4 drawing carries six door symbols (leaf + quarter-circle swing)
in four orientations, mirrored too, plus clutter (hatching, text, a dimension
line). The search must find all six from one boxed example, map them back to
the same top-left mediabox points the viewer measures in — also on a /Rotate 90
page — and refuse foreign projects before it looks at the body.
"""
from __future__ import annotations

import io
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from main import app  # noqa: E402  (must precede `import auth`)

import auth  # noqa: E402
import db  # noqa: E402
import page_raster_cache as _pdf_cache  # noqa: E402
import storage  # noqa: E402
from extractor import cv_render_cache  # noqa: E402
from extractor.cv_match import pt_box_to_px, px_box_to_pt  # noqa: E402

_PW = "passw0rd123"
PAGE_W, PAGE_H = A4  # 595.27 x 841.89 pt
DOOR = 30.0          # leaf length / swing radius, pt

# (hinge x, hinge y) in TOP-LEFT points, and the quadrant the swing opens into.
# sx/sy = direction of the leaf (x) and of the swing (y) from the hinge.
DOORS = [
    (100, 120, 1, 1),
    (300, 140, -1, 1),   # mirrored
    (450, 300, 1, -1),   # mirrored
    (150, 520, -1, -1),  # rotated 180
    (380, 600, 1, 1),
    (480, 720, -1, 1),
]


def _door_box(hx, hy, sx, sy, pad=3.0):
    xs = (hx, hx + sx * DOOR)
    ys = (hy, hy + sy * DOOR)
    return [min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad]


def _draw_door(c, hx, hy, sx, sy):
    """Leaf along x, arc from the leaf tip to the wall line along y. Reportlab
    is bottom-left origin; convert."""
    def P(x, y):
        return x, PAGE_H - y
    c.setLineWidth(1.2)
    c.line(*P(hx, hy), *P(hx + sx * DOOR, hy))                 # leaf
    c.setLineWidth(2.5)
    c.line(*P(hx, hy), *P(hx, hy + sy * DOOR))                  # jamb / wall end
    c.setLineWidth(0.5)
    p = c.beginPath()
    import math
    for i in range(0, 91, 3):
        a = math.radians(i)
        x = hx + sx * DOOR * math.cos(a)
        y = hy + sy * DOOR * math.sin(a)
        (p.moveTo if i == 0 else p.lineTo)(*P(x, y))
    c.drawPath(p, stroke=1, fill=0)


def _make_pdf(rotate: int = 0) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    for d in DOORS:
        _draw_door(c, *d)
    # Clutter that must NOT come back as a door.
    c.setLineWidth(0.4)
    for i in range(0, 120, 6):                     # hatched block
        c.line(40 + i, PAGE_H - 400, 40 + i + 40, PAGE_H - 440)
    c.setFont("Helvetica", 9)
    c.drawString(250, PAGE_H - 420, "PATALPU EKSPLIKACIJA 1500 x 2100")
    c.setLineWidth(0.6)
    c.line(60, PAGE_H - 800, 540, PAGE_H - 800)    # dimension line + ticks
    for x in (60, 300, 540):
        c.line(x - 4, PAGE_H - 796, x + 4, PAGE_H - 804)
    c.showPage()
    c.save()
    if not rotate:
        return buf.getvalue()
    # Add /Rotate the way real exports carry it: same portrait mediabox, same
    # content, only the display turned. (reportlab's setPageRotation swaps the
    # mediabox instead, which is not the case the viewer meets.)
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(buf.getvalue())
    doc[0].set_rotation(rotate)
    out = io.BytesIO()
    doc.save(out)
    doc.close()
    return out.getvalue()


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "find_symbol.db")
    monkeypatch.setattr(auth, "AUTH_DISABLED", False)
    monkeypatch.setattr(cv_render_cache, "CACHE_DIR", tmp_path / "cv_cache")
    monkeypatch.setenv("LOCAL_STORAGE_DIR", str(tmp_path / "store"))
    for v in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET",
              "STORAGE_BACKEND", "ENV"):
        monkeypatch.delenv(v, raising=False)
    storage.reset_storage_for_test()
    db.init_schema()
    db._migrate_schema()
    _pdf_cache.clear_pdf_cache()
    owner = db.create_user("owner@x.lt", auth.hash_password(_PW), name="Owner")
    db.create_user("other@x.lt", auth.hash_password(_PW), name="Other")
    db.upsert_project("proj-A", {"name": "A", "tipas": "interjeras"}, user_id=owner["id"])
    db.upsert_project("proj-R", {"name": "R", "tipas": "interjeras"}, user_id=owner["id"])
    _pdf_cache.store_pdf("proj-A", _make_pdf())
    yield
    _pdf_cache.clear_pdf_cache()
    storage.reset_storage_for_test()


def _login(email):
    c = TestClient(app)
    r = c.post("/api/auth/login", json={"email": email, "password": _PW})
    assert r.status_code == 200, r.text
    return c


def _near(cand, box, tol=4.0):
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    return abs(cand["x"] - cx) <= tol and abs(cand["y"] - cy) <= tol


def _assert_finds_all_doors(cands, min_score=0.85):
    strong = [c for c in cands if c["score"] >= min_score]
    for d in DOORS:
        box = _door_box(*d)
        assert any(_near(c, box) for c in strong), (d, [(c["x"], c["y"], c["score"]) for c in cands[:12]])
    # Nothing strong that is not a door (precision on the synthetic sheet).
    for c in strong:
        assert any(_near(c, _door_box(*d)) for d in DOORS), c


def test_box_search_finds_every_door_and_marks_the_source(env):
    cl = _login("owner@x.lt")
    box = _door_box(*DOORS[0])
    r = cl.post("/api/cv/find-symbol", json={"project_id": "proj-A", "page_idx": 0, "box_pt": box})
    assert r.status_code == 200, r.text
    out = r.json()
    cands = out["candidates"]
    _assert_finds_all_doors(cands)
    assert cands == sorted(cands, key=lambda c: -c["score"])
    sources = [c for c in cands if c["is_source"]]
    assert len(sources) == 1 and _near(sources[0], box)
    assert out["truncated"] is False


def test_box_search_on_a_rotated_page_answers_in_mediabox_points(env):
    """/Rotate 90: PDFium rasters the page turned; the viewer still boxes and
    reads in unrotated top-left points. The round trip must land on the doors."""
    _pdf_cache.store_pdf("proj-R", _make_pdf(rotate=90))
    cl = _login("owner@x.lt")
    r = cl.post("/api/cv/find-symbol", json={
        "project_id": "proj-R", "page_idx": 0, "box_pt": _door_box(*DOORS[4]),
    })
    assert r.status_code == 200, r.text
    _assert_finds_all_doors(r.json()["candidates"])


def test_template_from_another_page(env):
    cl = _login("owner@x.lt")
    r = cl.post("/api/cv/find-symbol", json={
        "project_id": "proj-A", "page_idx": 0, "template_page_idx": 0,
        "box_pt": _door_box(*DOORS[2]),
    })
    assert r.status_code == 200
    r2 = cl.post("/api/cv/find-symbol", json={
        "project_id": "proj-A", "page_idx": 3, "box_pt": _door_box(*DOORS[2]),
    })
    assert r2.status_code == 400  # one-page PDF: page 4 does not exist
    assert "lap" in r2.json()["detail"]


def test_foreign_project_is_404_before_the_body_is_checked(env):
    other = _login("other@x.lt")
    with patch("api.cv_tools.render_page") as spy:
        r = other.post("/api/cv/find-symbol", json={
            "project_id": "proj-A", "page_idx": 0, "box_pt": [50, 50, 10, 10],  # invalid box
        })
    assert r.status_code == 404, r.text
    spy.assert_not_called()


@pytest.mark.parametrize("box,status", [
    ([50, 50, 40, 60], 400),          # x1 < x0
    ([10, 10, 12, 12], 400),          # too small
    ([10, 10, 400, 400], 400),        # a quarter of the sheet, not one symbol
    ([560, 30, 590, 60], 422),        # empty corner — no lines
    ([500, 800, 700, 840], 400),      # off the sheet
])
def test_bad_boxes_are_refused_in_lithuanian(env, box, status):
    cl = _login("owner@x.lt")
    r = cl.post("/api/cv/find-symbol", json={"project_id": "proj-A", "page_idx": 0, "box_pt": box})
    assert r.status_code == status, r.text
    assert r.json()["detail"]


def test_cache_miss_loads_the_stored_drawing(env):
    storage.get_storage().put(storage.pdf_key("proj-R"), _make_pdf(), "application/pdf")
    assert _pdf_cache.get_pdf("proj-R") is None
    cl = _login("owner@x.lt")
    r = cl.post("/api/cv/find-symbol", json={
        "project_id": "proj-R", "page_idx": 0, "box_pt": _door_box(*DOORS[0]),
    })
    assert r.status_code == 200, r.text
    assert _pdf_cache.get_pdf("proj-R") is not None


def test_no_drawing_anywhere_is_409(env):
    cl = _login("owner@x.lt")
    r = cl.post("/api/cv/find-symbol", json={
        "project_id": "proj-R", "page_idx": 0, "box_pt": _door_box(*DOORS[0]),
    })
    assert r.status_code == 409


def test_record_decision_accepts_a_box_in_points(env):
    cl = _login("owner@x.lt")
    with patch("api.cv_tools.record_label") as rec:
        r = cl.post("/api/cv/record-decision", json={
            "project_id": "proj-A", "page_idx": 0, "box_pt": _door_box(*DOORS[1]),
            "klass": "durys-ai", "decision": "reject", "confidence": 0.81,
            "source": "symbol_search",
        })
    assert r.status_code == 200, r.text
    kw = rec.call_args.kwargs
    assert kw["klass"] == "durys-ai" and kw["decision"] == "reject"
    assert kw["meta"]["source"] == "symbol_search"
    x, y, w, h = kw["meta"]["bbox"]
    assert w > 0 and h > 0 and kw["crop"].shape == (h, w)
    # 200 dpi → ~2.78 px per point
    assert abs(x - _door_box(*DOORS[1])[0] * 200 / 72) < 3


def test_record_decision_needs_exactly_one_box(env):
    cl = _login("owner@x.lt")
    with patch("api.cv_tools.record_label") as rec:
        r = cl.post("/api/cv/record-decision", json={
            "project_id": "proj-A", "page_idx": 0, "klass": "durys", "decision": "accept",
        })
    assert r.status_code == 400
    rec.assert_not_called()


def test_old_pixel_match_template_still_answers(env):
    cl = _login("owner@x.lt")
    box = _door_box(*DOORS[0])
    f = 200 / 72
    r = cl.post("/api/cv/match-template", json={
        "project_id": "proj-A", "page_idx": 0,
        "bbox": [int(box[0] * f), int(box[1] * f), int((box[2] - box[0]) * f), int((box[3] - box[1]) * f)],
    })
    assert r.status_code == 200, r.text
    assert r.json()["candidates"]


@pytest.mark.parametrize("rot", [0, 90, 180, 270])
def test_point_pixel_round_trip(rot):
    W, H = 595.0, 842.0
    rw, rh = (1754, 1240) if rot in (90, 270) else (1240, 1754)
    box = [100.0, 200.0, 140.0, 260.0]
    px = pt_box_to_px(box, W, H, rot, rw, rh)
    back = px_box_to_pt(px, W, H, rot, rw, rh)
    assert all(abs(a - b) < 1.0 for a, b in zip(box, back)), (rot, px, back)
