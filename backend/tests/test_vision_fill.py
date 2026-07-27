"""POST /api/vision-fill — UNMOUNTED 2026-07-27 (pre-prod audit).

This was a Sprint-2 stub that never received its Sprint-4 implementation: it
answered every click with a hardcoded square covering 20% of the page
(`[[0.4,0.4],[0.4,0.6],[0.6,0.6],[0.6,0.4]]`, confidence "low"), which a user
could unknowingly persist as a room contour. It had zero frontend callers, so
the router is no longer included in main.py.

The old happy-path/validation/error-envelope tests exercised only that stub and
are gone with it. What remains is the guard: the route must stay absent until a
real Vision crop pipeline is wired. api/vision_fill.py is kept on disk (with its
F3 ownership gate intact) for that revival.
"""
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))
from main import app

client = TestClient(app)


def test_vision_fill_route_is_unmounted():
    r = client.post("/api/vision-fill", json={
        "project_id": "proj-1", "page_idx": 0, "click_xy_pct": [0.42, 0.41],
    })
    assert r.status_code == 404, r.text
