"""After Google sign-in the browser returns to the page that asked for it —
path, query and hash (2026-10-05).

ProtectedRoute sends a signed-out visitor to /login with the page in router
state, and Login now hands the WHOLE address (``/project/x?step=samata``,
``/project/x/patikra?kambarys=02#a``) to the Google button as ``next``; before,
only the pathname went, so ?step=…, ?kambarys=… and the hash were lost.

``main._safe_next_path`` is the open-redirect guard on that value. It already
let a query and hash through, but it also let through ``/%2F%2Fhost`` (only the
lower-case spelling was refused), ``/%5Chost``, double-encoded slashes, NUL and
DEL, percent-encoded control characters and ``/.//host``. Pinned here: each of
those comes back as "/", and the round trip /api/auth/google?next=… → callback
→ Location keeps a same-site address intact. No network (Google is faked), and
the database is a temp file.
"""
import re

import pytest
from fastapi.testclient import TestClient

import main  # noqa: E402  (first: main loads .env before auth reads its flags)
from main import _NEXT_PATH_MAX, _safe_next_path, app  # noqa: E402

import auth  # noqa: E402
import db  # noqa: E402


SAME_SITE = [
    "/project/x?step=samata",
    "/project/x/patikra?kambarys=02#a",
    "/dashboard",
    "/project/abc-123/patikra?kambarys=1.02&tab=sienos#siena-2",
    "/project/x?q=%2F%2Fevil.example",     # an encoded slash in the QUERY is data
    "/project/x#//not-a-host",              # so is anything in the hash
    "/project/%C4%85",                      # an encoded letter is a letter
]

REFUSED = {
    "absolute https": "https://evil.example/project/x",
    "absolute http": "http://evil.example",
    "a scheme": "javascript:alert(1)",
    "no leading slash": "evil.example/project/x",
    "protocol-relative": "//evil.example",
    "three slashes": "///evil.example",
    "backslash after the slash": "/\\evil.example",
    "two backslashes": "\\\\evil.example",
    "backslash deeper in the path": "/project\\evil.example",
    "encoded slashes": "/%2F%2Fevil.example",
    "encoded slashes, lower case": "/%2f%2fevil.example",
    "one encoded slash": "/%2F/evil.example",
    "encoded backslash": "/%5Cevil.example",
    "encoded backslash, lower case": "/%5cevil.example",
    "double-encoded slashes": "/%252F%252Fevil.example",
    "triple-encoded slashes": "/%25252F%25252Fevil.example",
    "tab": "/\t/evil.example",
    "newline": "/\n/evil.example",
    "CR LF (header splitting)": "/x\r\nSet-Cookie: a=b",
    "NUL": "/\x00/evil.example",
    "DEL": "/x\x7f",
    "encoded tab": "/%09/evil.example",
    "encoded CR LF": "/%0D%0A/evil.example",
    "encoded NUL": "/%00/evil.example",
    "space before //": " //evil.example",
    "space inside": "/a b",
    "fullwidth solidus": "/／／evil.example",
    "dot segment": "/.//evil.example",
    "dot-dot segment": "/project/../evil.example",
    "longer than the cap": "/" + "a" * _NEXT_PATH_MAX,
    "empty": "",
}


@pytest.mark.parametrize("raw", SAME_SITE)
def test_a_same_site_address_is_kept_whole(raw):
    assert _safe_next_path(raw) == raw


@pytest.mark.parametrize("raw", list(REFUSED.values()), ids=list(REFUSED))
def test_anything_else_falls_back_to_the_start_page(raw):
    assert _safe_next_path(raw) == "/"


@pytest.mark.parametrize("raw", [None, 123, ["/project/x"], b"/project/x"])
def test_a_value_that_is_not_text_falls_back_too(raw):
    assert _safe_next_path(raw) == "/"


def test_the_cap_itself_is_still_allowed():
    at_cap = "/" + "a" * (_NEXT_PATH_MAX - 1)
    assert len(at_cap) == _NEXT_PATH_MAX
    assert _safe_next_path(at_cap) == at_cap


# ── the round trip through Google ────────────────────────────────────────────

class _Resp:
    def __init__(self, body):
        self.status_code, self._body, self.text = 200, body, ""

    def json(self):
        return self._body


class _FakeGoogle:
    """Stands in for httpx.AsyncClient inside the callback: a token, then a
    profile. Nothing leaves the machine."""

    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, *a, **k):
        return _Resp({"access_token": "tok"})

    async def get(self, *a, **k):
        return _Resp({"sub": "google-sub-1", "email": "grizta@x.lt", "name": "Grįžta"})


@pytest.fixture()
def google(tmp_path, monkeypatch):
    import httpx

    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "oauth_next.db")
    db.init_schema()
    db._migrate_schema()
    # Real sessions even when the suite runs with SAMATU_AUTH_DISABLED=1.
    monkeypatch.setattr(auth, "AUTH_DISABLED", False)
    monkeypatch.setattr(httpx, "AsyncClient", _FakeGoogle)
    monkeypatch.setattr(main, "GOOGLE_OAUTH_ENABLED", True)
    monkeypatch.setattr(main, "GOOGLE_CLIENT_ID", "cid")
    monkeypatch.setattr(main, "GOOGLE_CLIENT_SECRET", "csec")


def _lands_on(next_value: str) -> str:
    """Start a Google sign-in with `next`, finish it, return where it sends the
    browser."""
    c = TestClient(app, follow_redirects=False)
    start = c.get("/api/auth/google", params={"next": next_value})
    assert start.status_code == 302, start.text
    state = re.search(r"state=([^&]+)", start.headers["location"]).group(1)
    r = c.get("/api/auth/google/callback", params={"state": state, "code": "x"})
    assert r.status_code == 302, r.text
    me = c.get("/api/auth/me")                             # signed in for real
    assert me.status_code == 200 and me.json()["user"]["email"] == "grizta@x.lt"
    return r.headers["location"]


@pytest.mark.parametrize("target", [
    "/project/x?step=samata",
    "/project/x/patikra?kambarys=02#a",
])
def test_google_sign_in_returns_to_the_whole_address(google, target):
    assert _lands_on(target) == target


@pytest.mark.parametrize("target", [
    "https://evil.example",
    "//evil.example",
    "/\\evil.example",
    "/%2F%2Fevil.example",
    "/%5Cevil.example",
    "/\t/evil.example",
])
def test_google_sign_in_never_leaves_the_site(google, target):
    assert _lands_on(target) == "/"
