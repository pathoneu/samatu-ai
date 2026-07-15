"""Fix 2 — Rate-limiter keys off a spoofable client IP.

With uvicorn's --forwarded-allow-ips='*', request.client.host becomes the
CLIENT-controlled leftmost X-Forwarded-For value, so per-IP login/register
limits are bypassable by rotating that header. _client_key derives the key from
the RIGHTMOST XFF hop (appended by the trusted proxy, not client-controllable),
falling back to request.client.host when no XFF header is present.
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException
from starlette.datastructures import Headers

import main


def _req(xff: str | None = None, client_host: str | None = "9.9.9.9"):
    class _R:
        pass
    r = _R()
    r.headers = Headers({"X-Forwarded-For": xff}) if xff is not None else Headers({})
    r.client = type("C", (), {"host": client_host})() if client_host else None
    return r


def test_rightmost_hop_is_used():
    r = _req("1.1.1.1, 2.2.2.2, 3.3.3.3")
    assert main._client_key(r) == "3.3.3.3"


def test_no_header_falls_back_to_client_host():
    assert main._client_key(_req(None, client_host="9.9.9.9")) == "9.9.9.9"


def test_no_header_no_client_returns_unknown():
    assert main._client_key(_req(None, client_host=None)) == "unknown"


def test_rotating_leftmost_yields_same_key():
    a = main._client_key(_req("10.0.0.1, 2.2.2.2, 3.3.3.3"))
    b = main._client_key(_req("99.99.99.99, 2.2.2.2, 3.3.3.3"))
    assert a == b == "3.3.3.3"


def test_rotating_leftmost_does_not_reset_counter():
    """The counter must accumulate under the rightmost hop even as an attacker
    rotates the leftmost (client-controlled) XFF value."""
    main._RATE_BUCKET.clear()
    for i in range(main._RATE_LIMIT_PER_MIN):
        key = main._client_key(_req(f"{i}.{i}.{i}.{i}, 2.2.2.2, 3.3.3.3"))
        main._check_rate_limit(key, "login")
    # One more, still rotating the leftmost → must 429 (all counted on 3.3.3.3)
    with pytest.raises(HTTPException) as ei:
        main._check_rate_limit(
            main._client_key(_req("240.0.0.1, 2.2.2.2, 3.3.3.3")), "login")
    assert ei.value.status_code == 429
    main._RATE_BUCKET.clear()
