"""POST /api/lasso-rerun — UNMOUNTED 2026-07-27 (pre-prod audit).

Sprint-2 stub whose Sprint-4 implementation never landed: `vision_lasso_extract`
returns `{"symbols": [], "polygons": []}` unconditionally, so the endpoint told
every caller "nothing in your lasso" no matter what they drew. Zero frontend
callers, so the router is no longer included in main.py.

The old tests only proved the stub's plumbing (they mocked the very function
that was the stub) and are gone with it. What remains is the guard: the route
must stay absent until real Vision crop+symbol extraction is wired.
api/lasso_rerun.py is kept on disk, F3 ownership gate intact, for that revival.
"""
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))
from main import app

client = TestClient(app)


def test_lasso_rerun_route_is_unmounted():
    r = client.post("/api/lasso-rerun", json={
        "project_id": "proj-1", "page_idx": 0,
        "lasso_polygon_pct": [[0.3, 0.4], [0.4, 0.4], [0.4, 0.5], [0.3, 0.5]],
    })
    assert r.status_code == 404, r.text
