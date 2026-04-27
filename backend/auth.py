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
SECRET_KEY = os.environ.get("SAMATU_SECRET_KEY", "dev-secret-CHANGE-ME-in-production")

# Cookie name + lifetime (30 days)
SESSION_COOKIE = "samatu_session"
SESSION_MAX_AGE_S = 30 * 24 * 3600

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
MIN_PASSWORD_LEN = 8


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
    user_id = request.session.get("user_id") if hasattr(request, "session") else None
    if not user_id:
        return None
    user = db.get_user_by_id(user_id)
    if not user or not user.get("is_active"):
        return None
    user.pop("password_hash", None)
    return user


def require_user(request: Request) -> dict:
    """FastAPI Depends — raises 401 if not logged in."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Reikia prisijungti")
    return user


def require_admin(request: Request) -> dict:
    """FastAPI Depends — raises 401 if not logged in, 403 if not admin."""
    user = require_user(request)
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Reikia administratoriaus teisių")
    return user
