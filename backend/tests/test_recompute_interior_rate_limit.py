"""/recompute-interior has its own rate bucket (v3 W7-A M7, DEVELOPING.md › Limits).

Measured 2026-10-18: ~50 ms for an 11-room project and ~390 ms for 110 rooms on
the single worker. 120 calls per minute per client; the 121st is a 429. The
bucket is separate from the 30/min default, so an edit burst never eats into
login or registration and vice versa."""
from __future__ import annotations

from fastapi.testclient import TestClient

import main
from main import app


def test_recompute_interior_limit_is_its_own_bucket(monkeypatch):
    assert main.RECOMPUTE_INTERIOR_PER_MIN == 120
    monkeypatch.setattr(main, "RECOMPUTE_INTERIOR_PER_MIN", 3)
    c = TestClient(app)
    for _ in range(3):
        r = c.post("/recompute-interior", json={"patalpos": []})
        assert r.status_code != 429, r.text
    r = c.post("/recompute-interior", json={"patalpos": []})
    assert r.status_code == 429
    # other buckets untouched
    assert c.post("/api/auth/login", json={"email": "x@x.lt", "password": "nera-tokio"}).status_code != 429


def test_default_limit_still_applies_elsewhere():
    calls = []
    for _ in range(main._RATE_LIMIT_PER_MIN):
        main._check_rate_limit("1.2.3.4", "probe")
        calls.append(1)
    try:
        main._check_rate_limit("1.2.3.4", "probe")
    except Exception as exc:  # HTTPException 429
        assert getattr(exc, "status_code", None) == 429
    else:
        raise AssertionError("31st call was not limited")
