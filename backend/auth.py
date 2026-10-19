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

import logging
import os
import re
from typing import Any

import bcrypt
from fastapi import HTTPException, Request

import db

log = logging.getLogger("pathon.auth")


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


# N4 (2026-07-04 pentest, pass 2): a precomputed bcrypt hash (work factor 12) of
# a fixed throwaway string. The login handler verifies the submitted password
# against THIS when no user row exists, so the ~168ms bcrypt cost is paid on both
# the user-exists and no-user paths — closing the ~120× timing oracle that let an
# attacker enumerate registered emails. It is never a valid credential (no user
# has this hash; the plaintext is not accepted anywhere).
_DUMMY_PASSWORD_HASH = bcrypt.hashpw(
    b"n4-timing-equalizer-not-a-real-password", bcrypt.gensalt(rounds=12)
).decode("utf-8")


def dummy_verify_password(plain: str) -> None:
    """Constant-cost bcrypt verify against a throwaway hash. Return value is
    intentionally discarded — this exists only to equalize login timing between
    the user-exists and no-user branches (N4). Call on the no-user path before
    returning the generic auth error."""
    verify_password(plain, _DUMMY_PASSWORD_HASH)


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


# bcrypt truncates at 72 BYTES; bcrypt 5.x raises ValueError instead of silently
# truncating, so a longer password reached hash_password and 500'd the register /
# change-password endpoints (2026-07-27 audit, finding 5). Reject it here, in the
# same 400-with-LT-detail pattern the length check already uses.
MAX_PASSWORD_BYTES = 72


def validate_password(pw: str) -> None:
    if not pw or len(pw) < MIN_PASSWORD_LEN:
        raise HTTPException(
            status_code=400,
            detail=f"Slaptažodis turi būti ne trumpesnis nei {MIN_PASSWORD_LEN} simbolių",
        )
    if not pw.strip():
        raise HTTPException(
            status_code=400,
            detail="Slaptažodis negali būti sudarytas vien iš tarpų",
        )
    if len(pw.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise HTTPException(
            status_code=400,
            detail=(f"Slaptažodis per ilgas (daugiausia {MAX_PASSWORD_BYTES} baitai — "
                    "apie 35–72 simboliai)"),
        )


# ── What a user row may say about itself in a response ─────────────────────────
# Audit backend-security-12 (fixed 2026-10-18): /me, /login, /register and
# /profile returned the whole row — google_sub, the Stripe ids and the session
# nonce included. Responses carry only what the app shows or decides on.
_PRIVATE_USER_KEYS = ("password_hash", "google_sub", "stripe_customer_id",
                      "stripe_subscription_id", "session_version", "deleted_at")


def public_user(user: dict | None) -> dict | None:
    if not user:
        return user
    return {k: v for k, v in user.items() if k not in _PRIVATE_USER_KEYS}


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
        # Project quota/trial is enforced at the project-CREATING extraction
        # (/extract-interior), NOT on corrections — a correction operates on an
        # already-created, already-counted project, so it keeps spend-cap
        # protection but must not re-consume/enforce project quota or the trial.
        # 2026-06-19 bug-hunt: also record the pre-charge so the cap actually
        # counts these api/* router calls (vision_fill / lasso_rerun / symbols),
        # which previously ran the cap check but never wrote any usage.
        _reserve_billable(user["id"], request.url.path)
    except HTTPException:
        raise  # the 429 spend-cap rejection must propagate
    except Exception:
        # Deliberately fail-OPEN: a cap-machinery hiccup (DB timeout, import
        # error) must never 500 a user's request. But it must NOT be silent —
        # a swallowed failure here means the billable event went unrecorded and
        # the spend cap was not enforced, so LOG it loudly for aggregation.
        # (audit 2026-07-06: previously `except Exception: pass`.)
        log.exception("spend-cap machinery failed for user %s on %s — failing "
                      "open (request allowed, usage NOT recorded)",
                      user.get("id"), request.url.path)
    return user


def require_admin(request: Request) -> dict:
    """FastAPI Depends — raises 401 if not logged in, 403 if not admin."""
    if AUTH_DISABLED:
        return _ensure_dev_user()
    user = require_user(request)
    if not user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Reikia administratoriaus teisių")
    return user


def require_owned_project(request: Request, project_id: str) -> dict:
    """Canonical auth + ownership gate for any per-project route (pass 3
    hardening, 2026-07-04).

    Three passes of the pentest found the SAME recurring class: a router-local
    ``_load_project(project_id, ..., fixture=None)`` helper whose ``fixture``
    branch RETURNED before ``require_user`` ran, so ``?fixture=<name>`` bypassed
    auth; the handler then read a ``{URL_project_id}``-keyed per-user store
    (``data/calibrations/{id}.json``, ``data/annotations/{id}.json``, the PDF
    byte cache) under the ATTACKER's URL id → unauth cross-tenant read.

    This helper is the single place that gets the order right, so new routers
    can't reintroduce the bug: it (1) requires a login (401), (2) scopes
    ``db.get_project`` to the caller (admins see all), (3) returns 404 for a
    missing/foreign project — never leaking existence. Prefer wiring it as a
    route-level ``Depends(require_owned_project)`` in the handler SIGNATURE (runs
    before the body, cannot be short-circuited by a load-helper branch), or —
    when a ``fixture`` may seed reference data — call it FIRST, before the
    fixture branch, so no ``{URL_id}``-keyed store is ever read for an
    unauthenticated/unowned caller.

    Returns the caller's user dict.
    """
    user = require_user(request)  # 401 if not logged in
    user_filter = None if user.get("is_admin") else user["id"]
    if db.get_project(project_id, user_id=user_filter) is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    return user
