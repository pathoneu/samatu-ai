"""Email verification + password reset (v3 W7-A M2), console mail backend.

Pins: the console backend is the default and SMTP is chosen only by SMTP_HOST +
SMTP_FROM; production console logs carry no link; reset and verification
tokens are single use, expire, are stored hashed, and never say whether an
account exists; a reset logs every other session out; the login gate is off by
default and, when on, refuses an unverified inbox only after the right
password; Google sign-in needs Google's email_verified and never merges into
an unverified password account; account deletion removes the tokens.
"""
from __future__ import annotations

import logging
import sqlite3
from unittest.mock import patch

from fastapi.testclient import TestClient

from main import app  # noqa: E402 (must precede `import auth`)

import auth  # noqa: E402
import db  # noqa: E402
import email_sender  # noqa: E402

_PW = "passw0rd123"
_NEW = "naujas-slapt-2026"


def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "auth_email.db")
    monkeypatch.setattr(auth, "AUTH_DISABLED", False)
    for k in ("SMTP_HOST", "SMTP_FROM", "SAMATU_REQUIRE_EMAIL_VERIFIED", "ENV", "PATHON_APP_URL"):
        monkeypatch.delenv(k, raising=False)
    db.init_schema()
    db._migrate_schema()
    email_sender.clear_outbox()


def _token(to: str) -> str:
    sent = [m for m in email_sender.outbox() if m.to == to]
    assert sent, f"no mail to {to}"
    return sent[-1].text.split("token=", 1)[1].split()[0]


def _register(c, email="rimas@x.lt"):
    r = c.post("/api/auth/register", json={"email": email, "password": _PW, "name": "Rimas"})
    assert r.status_code == 200, r.text
    return r.json()


# ── sender ───────────────────────────────────────────────────────────────────

def test_console_is_default_and_smtp_needs_host_and_from(monkeypatch):
    for k in ("SMTP_HOST", "SMTP_FROM"):
        monkeypatch.delenv(k, raising=False)
    assert email_sender.backend_name() == "console" and not email_sender.is_configured()
    monkeypatch.setenv("SMTP_HOST", "smtp.example.invalid")
    assert email_sender.backend_name() == "console"
    monkeypatch.setenv("SMTP_FROM", "noreply@example.invalid")
    assert email_sender.backend_name() == "smtp"


def test_production_console_log_has_no_link(monkeypatch, caplog):
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.setenv("ENV", "production")
    with caplog.at_level(logging.INFO, logger="pathon.email"):
        assert email_sender.send_email("a@x.lt", "Tema", "slapta nuoroda token=abc") is True
    assert "token=abc" not in caplog.text and "a@x.lt" not in caplog.text


def test_smtp_backend_retries_three_times_then_gives_up(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.invalid")
    monkeypatch.setenv("SMTP_FROM", "noreply@example.invalid")
    monkeypatch.setenv("SMTP_PORT", "587")
    calls = []

    class Boom:
        def __init__(self, *a, **k):
            calls.append(1)
            raise OSError("unreachable")

    with patch("email_sender.smtplib.SMTP", Boom), patch("email_sender.time.sleep"):
        assert email_sender.send_email("a@x.lt", "T", "x") is False
    assert len(calls) == 3


def test_smtp_backend_sends_with_starttls_and_login(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.invalid")
    monkeypatch.setenv("SMTP_FROM", "noreply@example.invalid")
    monkeypatch.setenv("SMTP_USER", "user")
    monkeypatch.setenv("SMTP_PASSWORD", "placeholder")
    seen = {}

    class Fake:
        def __init__(self, host, port, timeout=None):
            seen["host"], seen["port"] = host, port

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def starttls(self, context=None):
            seen["tls"] = True

        def login(self, u, p):
            seen["login"] = u

        def send_message(self, em):
            seen["to"], seen["subject"] = em["To"], em["Subject"]

    with patch("email_sender.smtplib.SMTP", Fake):
        assert email_sender.send_email("a@x.lt", "Tema", "tekstas") is True
    assert seen == {"host": "smtp.example.invalid", "port": 587, "tls": True, "login": "user",
                    "to": "a@x.lt", "subject": "Tema"}


# ── register + verify ────────────────────────────────────────────────────────

def test_register_sends_link_gate_off_keeps_todays_login(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    c = TestClient(app)
    body = _register(c)
    assert body["user"]["email"] == "rimas@x.lt"          # session started as before
    assert c.get("/api/auth/me").status_code == 200
    tok = _token("rimas@x.lt")
    assert "/el-pasto-patvirtinimas?token=" in email_sender.outbox()[-1].text
    assert c.post("/api/auth/verify-email", json={"token": tok}).status_code == 200
    assert db.get_user_by_email("rimas@x.lt")["email_verified_at"]
    again = c.post("/api/auth/verify-email", json={"token": tok})
    assert again.status_code == 400 and "nebegalioja" in again.json()["detail"]


def test_tokens_are_stored_hashed(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _register(TestClient(app))
    tok = _token("rimas@x.lt")
    con = sqlite3.connect(tmp_path / "auth_email.db")
    stored = [r[0] for r in con.execute("SELECT token_hash FROM email_tokens")]
    con.close()
    assert stored and tok not in stored and all(len(h) == 64 for h in stored)


def test_gate_on_register_starts_no_session_and_login_waits(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    monkeypatch.setenv("SAMATU_REQUIRE_EMAIL_VERIFIED", "1")
    c = TestClient(app)
    body = _register(c)
    assert body["user"] is None and body["verification_required"] is True
    assert c.get("/api/auth/me").status_code == 401

    wrong = c.post("/api/auth/login", json={"email": "rimas@x.lt", "password": "blogas-slapt"})
    assert wrong.status_code == 401                      # no oracle before the password
    r = c.post("/api/auth/login", json={"email": "rimas@x.lt", "password": _PW})
    assert r.status_code == 403 and r.json()["detail"]["error"] == "email_not_verified"

    c.post("/api/auth/verify-email", json={"token": _token("rimas@x.lt")})
    assert c.post("/api/auth/login", json={"email": "rimas@x.lt", "password": _PW}).status_code == 200


def test_resend_is_generic_and_throttled(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _register(TestClient(app))  # 1 link
    c = TestClient(app)
    for _ in range(4):
        r = c.post("/api/auth/resend-verification", json={"email": "rimas@x.lt"})
        assert r.status_code == 200
    ghost = c.post("/api/auth/resend-verification", json={"email": "nera@x.lt"})
    assert ghost.json() == r.json()                      # same answer for no account
    assert len([m for m in email_sender.outbox() if m.to == "rimas@x.lt"]) == 3


# ── reset ────────────────────────────────────────────────────────────────────

def test_reset_flow_single_use_and_logs_out_other_sessions(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    other_device = TestClient(app)
    _register(other_device)
    assert other_device.get("/api/auth/me").status_code == 200

    c = TestClient(app)
    r = c.post("/api/auth/forgot-password", json={"email": "Rimas@X.lt"})
    assert r.status_code == 200
    assert c.post("/api/auth/forgot-password", json={"email": "nera@x.lt"}).json() == r.json()
    tok = _token("rimas@x.lt")
    assert "/slaptazodzio-keitimas?token=" in email_sender.outbox()[-1].text

    short = c.post("/api/auth/reset-password", json={"token": tok, "new_password": "x"})
    assert short.status_code == 400                       # weak password: token not spent
    ok = c.post("/api/auth/reset-password", json={"token": tok, "new_password": _NEW})
    assert ok.status_code == 200, ok.text
    assert c.post("/api/auth/reset-password", json={"token": tok, "new_password": _NEW}).status_code == 400

    assert other_device.get("/api/auth/me").status_code == 401   # logged out everywhere
    assert c.post("/api/auth/login", json={"email": "rimas@x.lt", "password": _PW}).status_code == 401
    assert c.post("/api/auth/login", json={"email": "rimas@x.lt", "password": _NEW}).status_code == 200
    assert db.get_user_by_email("rimas@x.lt")["email_verified_at"]  # the link proved the inbox


def test_reset_token_expires_and_is_purpose_bound(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    u = db.create_user("t@x.lt", auth.hash_password(_PW), name="T")
    expired = db.create_email_token(u["id"], "reset", ttl_s=-5)
    c = TestClient(app)
    assert c.post("/api/auth/reset-password", json={"token": expired, "new_password": _NEW}).status_code == 400
    verify = db.create_email_token(u["id"], "verify", ttl_s=3600)
    assert c.post("/api/auth/reset-password", json={"token": verify, "new_password": _NEW}).status_code == 400
    assert c.post("/api/auth/reset-password", json={"token": "x" * 500, "new_password": _NEW}).status_code == 400


def test_new_reset_link_spends_older_ones(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    u = db.create_user("t@x.lt", auth.hash_password(_PW), name="T")
    first = db.create_email_token(u["id"], "reset", ttl_s=3600)
    second = db.create_email_token(u["id"], "reset", ttl_s=3600)
    c = TestClient(app)
    assert c.post("/api/auth/reset-password", json={"token": second, "new_password": _NEW}).status_code == 200
    assert c.post("/api/auth/reset-password", json={"token": first, "new_password": _NEW}).status_code == 400


def test_production_without_smtp_sends_no_reset_and_says_so(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    db.create_user("t@x.lt", auth.hash_password(_PW), name="T")
    monkeypatch.setenv("ENV", "production")
    c = TestClient(app)
    assert c.get("/api/auth/email-status").json() == {"links_can_be_sent": False,
                                                      "verification_required": False}
    assert c.post("/api/auth/forgot-password", json={"email": "t@x.lt"}).status_code == 200
    assert email_sender.outbox() == []


def test_account_deletion_removes_tokens(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    u = db.create_user("t@x.lt", auth.hash_password(_PW), name="T")
    db.create_email_token(u["id"], "reset", ttl_s=3600)
    counts = db.delete_account(u["id"])
    assert counts["email_tokens"] == 1


# ── Google sign-in (audit backend-security-9) ───────────────────────────────

class _Resp:
    def __init__(self, data, status=200):
        self._d, self.status_code, self.text = data, status, ""

    def json(self):
        return self._d


def _google(monkeypatch, info):
    import main

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **k):
            return _Resp({"access_token": "tok"})

        async def get(self, *a, **k):
            return _Resp(info)

    import httpx
    monkeypatch.setattr(main, "GOOGLE_OAUTH_ENABLED", True)
    monkeypatch.setattr(main, "GOOGLE_CLIENT_ID", "cid")
    monkeypatch.setattr(main, "GOOGLE_CLIENT_SECRET", "csec")
    monkeypatch.setattr(httpx, "AsyncClient", _Client)
    c = TestClient(app, follow_redirects=False)
    r = c.get("/api/auth/google")
    state = r.headers["location"].split("state=", 1)[1].split("&", 1)[0]
    return c, c.get("/api/auth/google/callback", params={"code": "c", "state": state})


def test_google_unverified_email_is_refused(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _c, r = _google(monkeypatch, {"sub": "g1", "email": "g@x.lt", "email_verified": False})
    assert r.status_code == 302 and r.headers["location"] == "/login?oauth_error=email_unverified"
    assert db.get_user_by_email("g@x.lt") is None


def test_google_does_not_merge_into_unverified_password_account(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    squatter = db.create_user("victim@x.lt", auth.hash_password(_PW), name="Kitas")
    _c, r = _google(monkeypatch, {"sub": "g2", "email": "victim@x.lt", "email_verified": True})
    assert r.headers["location"] == "/login?oauth_error=link_needs_password"
    assert db.get_user_by_id(squatter["id"]).get("google_sub") is None

    db.mark_email_verified(squatter["id"])          # the owner proved the inbox
    c2, r2 = _google(monkeypatch, {"sub": "g2", "email": "victim@x.lt", "email_verified": True})
    assert r2.headers["location"] == "/"
    assert db.get_user_by_id(squatter["id"])["google_sub"] == "g2"


def test_google_new_account_is_verified_and_redirects_to_app(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    monkeypatch.setenv("PATHON_APP_URL", "https://app.example.invalid/")
    _c, r = _google(monkeypatch, {"sub": "g3", "email": "naujas@x.lt", "email_verified": True})
    assert r.headers["location"] == "https://app.example.invalid/"
    assert db.get_user_by_email("naujas@x.lt")["email_verified_at"]
