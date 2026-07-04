"""Authentication module — password hashing + session-based auth.

Strategy:
- Passwords: bcrypt (work factor 12). Industry standard, slow enough.
- Sessions: signed HTTPOnly cookie via Starlette SessionMiddleware. user_id only.
- Auth dep: `current_user(request)` reads session cookie, returns user dict or 401.
- Admin dep: `require_admin(user)` adds is_admin check, returns 403.

Privacy notes:
- Cookie stores ONLY user_id. No PII in cookie.
- bcrypt hash is one-way (no plaintext password recovery — by design).
- Session cookie SameSite=lax (CSRF safer than 'none', allows top-level nav).
- Cookie expires after 30 days idle; user_id rotates on logout.

Production hardening (TODO):
- Move SECRET_KEY to env var (currently dev-default)
- Force Secure cookie in production (currently allows http for dev)
- Email verification before activation
- Rate-limit login endpoint to prevent brute force
- 2FA for admin accounts
"""
from __future__ import annotations

import os
import re
from typing import Any

import bcrypt
from fastapi import HTTPException, Request

import db


# Read secret from env (production) OR generate a stable fallback for dev.
# CRITICAL: in production, SAMATU_SECRET_KEY must be set to a 32+ byte random string.
_DEV_SECRET_FALLBACK = "dev-secret-CHANGE-ME-in-production"
SECRET_KEY = os.environ.get("SAMATU_SECRET_KEY", _DEV_SECRET_FALLBACK)

# Pre-launch audit (2026-05-07): refuse to boot in production with the dev
# fallback secret. A typo in the env var name would otherwise leave attackers
# able to forge session cookies signed with a public, well-known key.
_BOOT_ENV = (os.environ.get("ENV") or os.environ.get("ENVIRONMENT") or "").lower()
if _BOOT_ENV in ("production", "prod") and SECRET_KEY == _DEV_SECRET_FALLBACK:
    import sys
    sys.stderr.write(
        "\n\n!!! FATAL: SAMATU_SECRET_KEY is unset (or equals the dev fallback) "
        "with ENV=production. Refusing to start — set SAMATU_SECRET_KEY to a "
        "32+ byte random string before retrying.\n\n"
    )
    sys.exit(2)

# Cookie name + lifetime (30 days)
SESSION_COOKIE = "samatu_session"
SESSION_MAX_AGE_S = 30 * 24 * 3600

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
MIN_PASSWORD_LEN = 8

# Dev bypass — when SAMATU_AUTH_DISABLED=1, require_user/require_admin return a
# real (persisted) admin row instead of enforcing session cookies. Used for
# local testing only. NEVER enable in production.
#
# Sprint §AUDIT (2026-04-29): hard fail-fast if accidentally combined with
# production env. Catches misconfigured Docker secrets, .env symlinks, etc.
AUTH_DISABLED = os.environ.get("SAMATU_AUTH_DISABLED") == "1"
_ENV = (os.environ.get("ENV") or os.environ.get("ENVIRONMENT") or "").lower()
if AUTH_DISABLED and _ENV in ("production", "prod"):
    import sys
    sys.stderr.write(
        "\n\n!!! FATAL: SAMATU_AUTH_DISABLED=1 detected with ENV=production. "
        "This combination is forbidden — refusing to start. Unset "
        "SAMATU_AUTH_DISABLED or change ENV before retrying.\n\n"
    )
    sys.exit(2)
_DEV_USER_ID = "00000000-0000-0000-0000-000000000001"
_DEV_USER_EMAIL = "dev@samatu.local"


def _ensure_dev_user() -> dict:
    """Idempotent — make sure the dev user row exists so project FKs resolve."""
    user = db.get_user_by_id(_DEV_USER_ID)
    if user:
        user.pop("password_hash", None)
        return user
    with db._conn() as c:
        c.execute(
            """INSERT OR IGNORE INTO users
               (id, email, password_hash, name, company_name,
                is_admin, is_active, created_at)
               VALUES (?, ?, '', 'Dev', '', 1, 1, ?)""",
            (_DEV_USER_ID, _DEV_USER_EMAIL, db._now_iso()),
        )
    user = db.get_user_by_id(_DEV_USER_ID) or {}
    user.pop("password_hash", None)
    return user


def hash_password(plain: str) -> str:
    """bcrypt hash with work factor 12 (~250ms on modern CPU)."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Constant-time bcrypt verify."""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def validate_email(email: str) -> str:
    """Returns normalized lowercase email or raises HTTPException."""
    e = (email or "").strip().lower()
    if not EMAIL_RE.match(e):
        raise HTTPException(status_code=400, detail="Neteisingas el. pašto formatas")
    return e


def validate_password(pw: str) -> None:
    if not pw or len(pw) < MIN_PASSWORD_LEN:
        raise HTTPException(
            status_code=400,
            detail=f"Slaptažodis turi būti ne trumpesnis nei {MIN_PASSWORD_LEN} simbolių",
        )


# ── FastAPI dependencies ──────────────────────────────────────────────────────

def get_current_user(request: Request) -> dict | None:
    """Returns user dict (sans password_hash) if logged in, else None."""
    if AUTH_DISABLED:
        return _ensure_dev_user()
    session = request.session if hasattr(request, "session") else {}
    user_id = session.get("user_id")
    if not user_id:
        return None
    user = db.get_user_by_id(user_id)
    if not user or not user.get("is_active"):
        return None
    # F2 (2026-07-04 pentest): reject sessions minted against a stale
    # session_version. Logout / change-password bump the user row's version, so a
    # captured pre-logout cookie (cryptographically valid for 30 days) no longer
    # matches and is refused. A cookie with no "sv" at all is a pre-F2 legacy
    # session — treat it as stale and force a fresh login.
    cookie_sv = session.get("sv")
    current_sv = user.get("session_version")
    if current_sv is None:
        current_sv = 1  # rows predating the migration default to 1
    if cookie_sv != current_sv:
        return None
    user.pop("password_hash", None)
    return user


def require_user(request: Request) -> dict:
    """FastAPI Depends — raises 401 if not logged in."""
    if AUTH_DISABLED:
        return _ensure_dev_user()
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Reikia prisijungti")
    return user


def require_billable_user(request: Request) -> dict:
    """FastAPI Depends — require_user PLUS the per-user Vision spend cap.

    Use on every endpoint that triggers an Anthropic call. Without it, a paid
    Vision endpoint authenticated by plain require_user bypasses the spend cap
    entirely, so a single account can loop it and drain the API key (2026-05-07
    audit found this on several endpoints; 2026-06-19 closed the api/* routers
    — vision_fill / lasso_rerun / symbols). The cap helper lives in main.py;
    it is imported lazily so this module stays free of a circular import."""
    user = require_user(request)
    try:
        from main import _check_user_spend_cap, _reserve_billable
        _check_user_spend_cap(user["id"])
        # 2026-06-19 bug-hunt: also record the pre-charge so the cap actually
        # counts these api/* router calls (vision_fill / lasso_rerun / symbols),
        # which previously ran the cap check but never wrote any usage.
        _reserve_billable(user["id"], request.url.path)
    except HTTPException:
        raise  # the 429 spend-cap rejection must propagate
    except Exception:
        pass   # never block a request on a cap-machinery hiccup
    return user


def require_admin(request: Request) -> dict:
    """FastAPI Depends — raises 401 if not logged in, 403 if not admin."""
    if AUTH_DISABLED:
        return _ensure_dev_user()
    user = require_user(request)
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Reikia administratoriaus teisių")
    return user
