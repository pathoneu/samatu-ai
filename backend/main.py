from fastapi import FastAPI, UploadFile, File, Form, Body, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, Field
import logging
import os
import time as _time
from collections import defaultdict, deque

# Logger setup — replaces scattered print() calls. Default INFO level.
# In production, swap StreamHandler for FileHandler or pipe to systemd journal.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("samatu_ai")

# ── Production safety helpers ──────────────────────────────────────────────────
# 200 MB max — covers large commercial projects (multi-aukštai apartment buildings,
# 150+ pages with high-res raster scans). Typical LT residential = 5-20 MB.
# Note: Vision pipeline still caps at MAX_PAGES=100 (Anthropic API hard limit).
# A 150-page PDF would have pages 101-150 silently skipped — surface as warning.
MAX_PDF_SIZE_BYTES = 200 * 1024 * 1024
MIN_PDF_SIZE_BYTES = 100               # below = junk

def _validate_pdf_upload(pdf_bytes: bytes, filename: str = "") -> dict:
    """Reject malformed/oversize uploads BEFORE expensive Vision call.
    Raises HTTPException on failure.
    Returns: {"page_count": int, "warning": str | None} on success.
    """
    n = len(pdf_bytes)
    if n < MIN_PDF_SIZE_BYTES:
        raise HTTPException(status_code=400, detail=f"PDF failas tuščias arba per mažas ({n} B). Įkelkite tikrą brėžinį.")
    if n > MAX_PDF_SIZE_BYTES:
        raise HTTPException(status_code=413, detail=f"PDF failas per didelis ({n // (1024*1024)} MB). Maksimumas {MAX_PDF_SIZE_BYTES // (1024*1024)} MB.")
    # Magic bytes check — first 4 bytes of valid PDF = b"%PDF"
    if not pdf_bytes[:4].startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail=f"Failas nėra galiojantis PDF (nerasta %PDF antraštė). Patikrinkite, ar įkėlėte PDF, ne kitą formatą.")
    # Filename sanity (defense in depth — filenames may contain path traversal etc)
    if filename and (".." in filename or filename.startswith("/")):
        log.warning("suspicious filename rejected: %r", filename)
        raise HTTPException(status_code=400, detail="Neleistinas failo pavadinimas.")

    # Quick page count via pdfplumber (fast — only reads metadata)
    try:
        import io as _io
        with pdfplumber.open(_io.BytesIO(pdf_bytes)) as _pdf:
            page_count = len(_pdf.pages)
    except Exception as e:
        log.warning("pdf page count probe failed: %s", e)
        page_count = 0

    warning = None
    # MAX_PAGES is the Vision pipeline cap (defined in extractor/prompt.py = 100)
    if page_count > 100:
        warning = (
            f"PDF turi {page_count} puslapių. AI analizuos tik pirmus 100 — "
            f"jei svarbi info (pvz. eksplikacija) yra vėlesniuose puslapiuose, "
            f"perorganizuokite PDF arba įkelkite atskirai pirmus 100 + likusius."
        )
        log.info("large PDF: %d pages (will cap at 100)", page_count)

    return {"page_count": page_count, "warning": warning}


# In-memory rate limiter — per-IP request counter with sliding 60s window.
# Production should use Redis or nginx-level rate limit. This guards single-instance
# dev/staging from abusive clients (eg. accidental script loops).
_RATE_BUCKET: dict[str, deque] = defaultdict(deque)
_RATE_LIMIT_PER_MIN = 30  # generous; one estimator might do 5-10/hour normally
_RATE_BUCKET_LAST_GC = [0.0]  # mutable cell so we can update from inside func

# M5 (2026-05-06): per-user daily Vision spend cap. Default disabled; set
# SAMATU_USER_DAILY_SPEND_EUR=0.50 in production .env to cap each user.
_USER_DAILY_SPEND_CAP_EUR = float(os.environ.get("SAMATU_USER_DAILY_SPEND_EUR", "0") or 0)
_USER_HOURLY_EXTRACTS = int(os.environ.get("SAMATU_USER_HOURLY_EXTRACTS", "20") or 20)


def _check_user_spend_cap(user_id: str | None) -> None:
    """Raise 429 if user is over daily Vision spend cap or hourly extract count.
    Anonymous (no user_id) requests are not capped here — they hit per-IP
    rate limit instead. Cap enabled only when env var set > 0."""
    if not user_id:
        return
    try:
        spend_24h, n_24h = db.user_recent_spend_eur(user_id, hours=24)
        spend_1h, n_1h = db.user_recent_spend_eur(user_id, hours=1)
    except Exception:
        return  # never block on spend-check failure
    if _USER_DAILY_SPEND_CAP_EUR > 0 and spend_24h >= _USER_DAILY_SPEND_CAP_EUR:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Pasiekta dienos AI biudžeto riba ({spend_24h:.2f} € / "
                f"{_USER_DAILY_SPEND_CAP_EUR:.2f} €). Bandykite rytoj arba "
                "kreipkitės į administratorių."
            ),
        )
    if _USER_HOURLY_EXTRACTS > 0 and n_1h >= _USER_HOURLY_EXTRACTS:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Per daug analizių per valandą ({n_1h} / {_USER_HOURLY_EXTRACTS}). "
                "Palaukite valandą."
            ),
        )

def _check_rate_limit(client_ip: str, endpoint: str) -> None:
    """Sliding-window rate limit. Raises 429 on overflow.

    Sprint §AUDIT (2026-04-29): periodic janitor evicts empty buckets so the
    dict doesn't grow unbounded over weeks of unique IPs. Runs at most every
    10 minutes; cheap O(n) scan over keys.
    """
    now = _time.time()
    bucket = _RATE_BUCKET[f"{client_ip}:{endpoint}"]
    # Drop entries older than 60s
    while bucket and now - bucket[0] > 60:
        bucket.popleft()
    if len(bucket) >= _RATE_LIMIT_PER_MIN:
        log.warning("rate limit hit: ip=%s endpoint=%s count=%d", client_ip, endpoint, len(bucket))
        raise HTTPException(status_code=429, detail=f"Per daug užklausų. Palaukite minutę. (limitas: {_RATE_LIMIT_PER_MIN}/min)")
    bucket.append(now)
    # Janitor: evict stale entries every 10 minutes. Cheap because most buckets
    # already empty after a minute of inactivity.
    if now - _RATE_BUCKET_LAST_GC[0] > 600:
        _RATE_BUCKET_LAST_GC[0] = now
        stale_keys = []
        for key, deq in _RATE_BUCKET.items():
            while deq and now - deq[0] > 60:
                deq.popleft()
            if not deq:
                stale_keys.append(key)
        for key in stale_keys:
            del _RATE_BUCKET[key]
        if stale_keys:
            log.info("rate-limiter GC: evicted %d empty buckets, %d remaining",
                     len(stale_keys), len(_RATE_BUCKET))
import pdfplumber
import anthropic
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Register Unicode-capable fonts for Lithuanian characters
_ARIAL_PATH      = "/System/Library/Fonts/Supplemental/Arial.ttf"
_ARIAL_BOLD_PATH = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
try:
    pdfmetrics.registerFont(TTFont("ArialUni",     _ARIAL_PATH))
    pdfmetrics.registerFont(TTFont("ArialUniBold", _ARIAL_BOLD_PATH))
    _FONT_NORMAL = "ArialUni"
    _FONT_BOLD   = "ArialUniBold"
except Exception:
    _FONT_NORMAL = "Helvetica"
    _FONT_BOLD   = "Helvetica-Bold"
import json
import re
import io
import os
import math
import asyncio
import hashlib
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any
from dotenv import load_dotenv

# ── API router imports (Sprint 0 Task 1 + Sprint 2 G1/G5) ────────────────────
# Consolidated to top of file in Sprint 2 Task 21 (Sprint 0 follow-up #2).
# Safe at module-top: routers depend only on FastAPI + sibling internal modules,
# not on app instance, env vars, or load_dotenv() side effects.
from api.config import router as config_router
from api.recompute_quantities import router as recompute_router
from api.telemetry import router as telemetry_router
from api.vision_fill import router as vision_fill_router
from api.lasso_rerun import router as lasso_rerun_router

load_dotenv()

# ── PDF result cache (in-memory, keyed by sha256 of PDF bytes) ───────────────
_PDF_CACHE: dict[str, dict] = {}

# ── App ──────────────────────────────────────────────────────────────────────

app = FastAPI()

from starlette.middleware.sessions import SessionMiddleware
import auth as _auth  # noqa: E402  imports + initializes
import db as _db  # noqa: E402

# M5 (2026-05-06): production hardening flags via ENV
_PROD_ENV = (os.environ.get("ENV") or os.environ.get("ENVIRONMENT") or "").lower() in (
    "prod", "production"
)

# Session middleware FIRST (before CORS) — signed HTTPOnly cookies for auth.
# In production, set SAMATU_SECRET_KEY env to a strong random string.
app.add_middleware(
    SessionMiddleware,
    secret_key=_auth.SECRET_KEY,
    session_cookie=_auth.SESSION_COOKIE,
    max_age=_auth.SESSION_MAX_AGE_S,
    same_site="lax",
    https_only=_PROD_ENV,  # secure cookies only when ENV=production
)

# CORS — for cross-origin frontend (Vite dev on :5173, prod same-origin)
# allow_credentials=True so session cookie traverses the proxy
_CORS_ORIGINS_ENV = os.environ.get("SAMATU_CORS_ORIGINS", "")
_CORS_ORIGINS = (
    [o.strip() for o in _CORS_ORIGINS_ENV.split(",") if o.strip()]
    if _CORS_ORIGINS_ENV
    else ["http://localhost:5173", "http://127.0.0.1:5173"]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# M5: Security response headers — defense-in-depth for clickjacking,
# MIME-sniffing, and referrer leakage. CSP is intentionally relaxed during
# development (allows inline styles for shadcn) but tightens in production.
@app.middleware("http")
async def _security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if _PROD_ENV:
        response.headers.setdefault(
            "Strict-Transport-Security",
            "max-age=31536000; includeSubDomains",
        )
        # CSP — adjust as the app evolves. 'unsafe-inline' for styles is
        # required by shadcn/ui radix components; eval is forbidden.
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob: https:; "
            "font-src 'self' data:; "
            "connect-src 'self' https://accounts.google.com https://oauth2.googleapis.com; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self' https://accounts.google.com",
        )
    return response


# ── Global unhandled-exception handler ─────────────────────────────────────────
# Catches any unhandled exception in route handlers, logs with traceback, returns
# generic 500 (no stack trace leak to client). Prevents the FastAPI default which
# echoes back the exception type in debug mode.
@app.exception_handler(Exception)
async def _global_exception_handler(request, exc):
    import traceback as _tb
    tid = f"err-{int(_time.time())}-{hash(str(exc)) & 0xFFFF:04x}"
    log.error("[%s] Unhandled %s on %s: %s\n%s",
              tid, type(exc).__name__, request.url.path, exc, _tb.format_exc())
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "_error": f"Vidinė serverio klaida (ref: {tid})",
            "ref": tid,
        },
    )


# ── Register routers (imports consolidated to top — Sprint 2 Task 21) ────────
app.include_router(config_router)
app.include_router(recompute_router)
app.include_router(telemetry_router)
app.include_router(vision_fill_router)
app.include_router(lasso_rerun_router)


# ── /api/log-error — frontend error reporting ─────────────────────────────────
class FrontendErrorPayload(BaseModel):
    message: str
    stack: str | None = None
    component: str | None = None
    url: str | None = None
    user_agent: str | None = None


@app.post("/api/log-error")
async def log_frontend_error(payload: FrontendErrorPayload, request: Request):
    """Frontend ErrorBoundary + manual try/catch can POST here.
    Lightweight error sink — production should swap for Sentry SDK.
    """
    client_ip = request.client.host if request.client else "unknown"
    log.error(
        "[FRONTEND] component=%s url=%s ip=%s msg=%s\nstack: %s",
        payload.component or "?",
        payload.url or "?",
        client_ip,
        payload.message,
        (payload.stack or "")[:2000],
    )
    return {"status": "ok", "logged": True}


# ── DB-backed projects (Phase 12.3) ──────────────────────────────────────────
# Replaces frontend localStorage as durable source of truth.
# Frontend keeps localStorage as offline cache (write-through).

import db  # noqa: E402  — initializes schema on import
from fastapi import Depends  # noqa: E402


class CorrectionPayload(BaseModel):
    field_path: str
    old_value: Any = None
    new_value: Any = None
    source: str = "inline_edit"
    room_nr: str | None = None
    note: str | None = None


# ── AUTH endpoints (Phase 13) ────────────────────────────────────────────────

class RegisterPayload(BaseModel):
    email: str
    password: str
    name: str | None = None
    company_name: str | None = None


class LoginPayload(BaseModel):
    email: str
    password: str


@app.post("/api/auth/register")
async def api_register(payload: RegisterPayload, request: Request):
    """Register new user. Validates email + password, hashes password, creates DB row,
    starts session. First-ever registered user becomes admin automatically."""
    _check_rate_limit(request.client.host if request.client else "unknown", "register")
    email = _auth.validate_email(payload.email)
    _auth.validate_password(payload.password)
    if db.get_user_by_email(email):
        raise HTTPException(status_code=409, detail="Vartotojas su šiuo el. paštu jau egzistuoja")

    # First user → admin (self-bootstrap)
    is_first = len(db.list_users()) == 0
    pw_hash = _auth.hash_password(payload.password)
    user = db.create_user(
        email=email, password_hash=pw_hash,
        name=payload.name, company_name=payload.company_name,
        is_admin=is_first,
    )
    request.session["user_id"] = user["id"]
    log.info("registered user: id=%s email=%s admin=%s", user["id"], email, is_first)
    user.pop("password_hash", None)
    return {"user": user, "is_first_admin": is_first}


@app.post("/api/auth/login")
async def api_login(payload: LoginPayload, request: Request):
    """Email + password → session cookie. Generic error message (avoid user enumeration)."""
    _check_rate_limit(request.client.host if request.client else "unknown", "login")
    email = _auth.validate_email(payload.email)
    user = db.get_user_by_email(email)
    if not user or not user.get("is_active"):
        raise HTTPException(status_code=401, detail="Neteisingas el. paštas arba slaptažodis")
    if not _auth.verify_password(payload.password, user.get("password_hash", "")):
        log.warning("failed login: email=%s ip=%s", email,
                    request.client.host if request.client else "?")
        raise HTTPException(status_code=401, detail="Neteisingas el. paštas arba slaptažodis")
    request.session["user_id"] = user["id"]
    db.update_user_login(user["id"])
    user.pop("password_hash", None)
    return {"user": user}


@app.post("/api/auth/logout")
async def api_logout(request: Request):
    request.session.clear()
    return {"status": "logged_out"}


@app.get("/api/auth/me")
async def api_me(request: Request):
    """Return current user (or 401)."""
    user = _auth.get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Nesate prisijungę")
    return {"user": user}


class PasswordChangePayload(BaseModel):
    current_password: str
    new_password: str


@app.post("/api/auth/change-password")
async def api_change_password(payload: PasswordChangePayload, request: Request):
    """Change user's password. Verifies current_password first.
    Generic error message on wrong current password (no enumeration helper)."""
    user = _auth.require_user(request)
    _check_rate_limit(request.client.host if request.client else "unknown", "change-password")
    _auth.validate_password(payload.new_password)

    full_user = db.get_user_by_id(user["id"])
    if not full_user or not _auth.verify_password(payload.current_password, full_user.get("password_hash", "")):
        log.warning("failed password change: user_id=%s", user["id"])
        raise HTTPException(status_code=401, detail="Neteisingas dabartinis slaptažodis")

    new_hash = _auth.hash_password(payload.new_password)
    with db._conn() as c:
        c.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, user["id"]))
    log.info("password changed for user_id=%s", user["id"])
    return {"status": "ok"}


class ProfileUpdatePayload(BaseModel):
    name: str | None = None
    company_name: str | None = None


@app.put("/api/auth/profile")
async def api_update_profile(payload: ProfileUpdatePayload, request: Request):
    """Update user's display name + company. Email NOT changeable here
    (would need verification flow)."""
    user = _auth.require_user(request)
    with db._conn() as c:
        c.execute(
            "UPDATE users SET name = ?, company_name = ? WHERE id = ?",
            (payload.name, payload.company_name, user["id"]),
        )
    return {"user": db.get_user_by_id(user["id"]) or {}}


# ── M4: Google OAuth (2026-05-06) ──────────────────────────────────────
# Lights up only when GOOGLE_CLIENT_ID + GOOGLE_CLIENT_SECRET env vars are
# set. Without them, /api/auth/google returns 503 and the frontend hides
# the button. User-supplied env vars stay out of the repo (.env).

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.environ.get(
    "GOOGLE_REDIRECT_URI", "http://localhost:8000/api/auth/google/callback"
)
GOOGLE_OAUTH_ENABLED = bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)


@app.get("/api/auth/google/status")
async def api_google_oauth_status():
    """Frontend polls this to decide whether to show Sign-in-with-Google."""
    return {"enabled": GOOGLE_OAUTH_ENABLED}


@app.get("/api/auth/google")
async def api_google_login(request: Request):
    """Start Google OAuth flow. Redirects to Google's consent screen."""
    if not GOOGLE_OAUTH_ENABLED:
        raise HTTPException(status_code=503, detail="Google OAuth not configured")
    import secrets
    state = secrets.token_urlsafe(24)
    request.session["google_oauth_state"] = state
    # Capture intended redirect after success (default = "/")
    next_url = request.query_params.get("next", "/")
    request.session["google_oauth_next"] = next_url
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }
    from urllib.parse import urlencode
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)
    return RedirectResponse(url=url, status_code=302)


@app.get("/api/auth/google/callback")
async def api_google_callback(request: Request, code: str | None = None,
                              state: str | None = None, error: str | None = None):
    """Google OAuth redirect target. Exchanges code → token → user info,
    then creates/links the local user and starts a session."""
    if error:
        return RedirectResponse(url=f"/login?oauth_error={error}", status_code=302)
    if not GOOGLE_OAUTH_ENABLED:
        raise HTTPException(status_code=503, detail="Google OAuth not configured")
    expected_state = request.session.pop("google_oauth_state", None)
    next_url = request.session.pop("google_oauth_next", "/")
    if not state or state != expected_state:
        raise HTTPException(status_code=400, detail="Invalid OAuth state")
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")

    import httpx  # lazy import — only loaded when OAuth is used
    async with httpx.AsyncClient(timeout=10) as client:
        token_resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": GOOGLE_REDIRECT_URI,
            },
        )
        if token_resp.status_code != 200:
            log.error("Google token exchange failed: %s", token_resp.text[:300])
            raise HTTPException(status_code=502, detail="Token exchange failed")
        access_token = token_resp.json().get("access_token")
        if not access_token:
            raise HTTPException(status_code=502, detail="No access token returned")
        userinfo = await client.get(
            "https://openidconnect.googleapis.com/v1/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if userinfo.status_code != 200:
            raise HTTPException(status_code=502, detail="Failed to fetch userinfo")
        info = userinfo.json()

    google_sub = info.get("sub")
    email = (info.get("email") or "").lower().strip()
    name = info.get("name")
    avatar = info.get("picture")
    if not google_sub or not email:
        raise HTTPException(status_code=502, detail="Incomplete userinfo")

    # Match priority: existing google_sub → existing email → create new user.
    user = db.get_user_by_google_sub(google_sub)
    if user is None:
        existing = db.get_user_by_email(email)
        if existing:
            db.link_google_to_user(existing["id"], google_sub, avatar)
            user = db.get_user_by_id(existing["id"])
        else:
            # First-ever user becomes admin (matches /api/auth/register policy).
            is_first = len(db.list_users()) == 0
            user = db.create_user_oauth(
                email=email, google_sub=google_sub, name=name,
                avatar_url=avatar, is_admin=is_first,
            )
    request.session["user_id"] = user["id"]
    db.update_user_login(user["id"])
    return RedirectResponse(url=next_url or "/", status_code=302)


# ── Project endpoints (per-user isolation) ──────────────────────────────────

@app.get("/api/projects")
async def api_list_projects(request: Request):
    """List CURRENT user's projects (admin sees all)."""
    user = _auth.require_user(request)
    if user.get("is_admin") and request.query_params.get("all") == "1":
        return {"projects": db.list_projects(user_id=None), "scope": "all"}
    return {"projects": db.list_projects(user_id=user["id"]), "scope": "own"}


@app.get("/api/projects/{project_id}")
async def api_get_project(request: Request, project_id: str):
    user = _auth.require_user(request)
    # Admin can read any; regular users only their own
    user_filter = None if user.get("is_admin") else user["id"]
    p = db.get_project(project_id, user_id=user_filter)
    if not p:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    return p


@app.put("/api/projects/{project_id}")
async def api_upsert_project(request: Request, project_id: str, payload: dict = Body(...)):
    user = _auth.require_user(request)
    if not payload:
        raise HTTPException(status_code=400, detail="Empty payload")
    try:
        return db.upsert_project(project_id, payload, user_id=user["id"])
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@app.delete("/api/projects/{project_id}")
async def api_delete_project(request: Request, project_id: str):
    user = _auth.require_user(request)
    user_filter = None if user.get("is_admin") else user["id"]
    if not db.delete_project(project_id, user_id=user_filter):
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    return {"deleted": project_id}


# ── SM04: read-only share links ──────────────────────────────────────────────

@app.post("/api/projects/{project_id}/share")
async def api_create_share(request: Request, project_id: str, payload: dict | None = None):
    """Issue (or refresh) a UUID share token for read-only viewing. Auth required.

    Sprint §36 (2026-04-29): supports `expires_in_days` (default 30, 0 = no expiry).
    Returns: {token, url, expires_at, view_count}
    """
    from datetime import datetime, timedelta, timezone
    user = _auth.require_user(request)
    user_filter = None if user.get("is_admin") else user["id"]
    if not db.get_project(project_id, user_id=user_filter):
        raise HTTPException(status_code=404, detail="Project not found")

    # Parse expires_in_days from body (default 30 days)
    expires_in = 30
    if payload and isinstance(payload, dict):
        try:
            expires_in = int(payload.get("expires_in_days", 30))
        except (ValueError, TypeError):
            expires_in = 30
    expires_at = None
    if expires_in > 0:
        exp_dt = datetime.now(timezone.utc) + timedelta(days=expires_in)
        expires_at = exp_dt.isoformat()

    import uuid
    token = uuid.uuid4().hex
    db.set_share_token(project_id, token, expires_at=expires_at)
    log.info("share token issued: project=%s by user=%s expires=%s",
             project_id, user["id"], expires_at)
    return {
        "token": token,
        "url": f"/share/{token}",
        "expires_at": expires_at,
        "view_count": 0,
    }


@app.get("/api/projects/{project_id}/share")
async def api_get_share_status(request: Request, project_id: str):
    """Get current share token state (token, expires_at, view_count, last_viewed_at).
    Returns null fields if no active token."""
    user = _auth.require_user(request)
    user_filter = None if user.get("is_admin") else user["id"]
    if not db.get_project(project_id, user_id=user_filter):
        raise HTTPException(status_code=404, detail="Project not found")
    status = db.get_share_status(project_id) or {}
    return {
        "token": status.get("token"),
        "url": f"/share/{status['token']}" if status.get("token") else None,
        "expires_at": status.get("expires_at"),
        "view_count": status.get("view_count", 0),
        "last_viewed_at": status.get("last_viewed_at"),
        "active": bool(status.get("token")),
    }


# ── Sprint E3 — On-demand material specs per room ────────────────────────────
#
# When user clicks "Dizainerio medžiagos" on RoomCard, frontend POSTs the PDF
# blob (from IndexedDB) + room_nr. We pick spec-rich pages for that room and
# run a focused Vision call. Result cached in project DB so second click is
# free. ~$0.20 per first-time click.


def _pick_spec_pages_for_room(target_room: dict, puslapiai: list[dict]) -> list[int]:
    """Heuristic: pick up to 3 designer-spec pages most relevant to this room.

    Priority:
    1. material_spec_per_room with title matching room name (e.g. "VAIKŲ VONIOS SPALVOS")
    2. wall_elevation_with_tiles matching room name or room nr
    3. specification (broader) — fallback for projects without dedicated per-room pages
    """
    if not puslapiai:
        return []
    room_name = (target_room.get("pavadinimas") or "").lower().strip()
    room_nr = (target_room.get("nr") or "").lower().strip()
    name_tokens = [t for t in room_name.split() if len(t) >= 4]

    def _matches(page_title: str) -> bool:
        title = (page_title or "").lower()
        if not title:
            return False
        if room_nr and f"({room_nr})" in title or f" {room_nr} " in title:
            return True
        return any(tok in title for tok in name_tokens) if name_tokens else False

    by_priority: list[int] = []
    spec_pages = [p for p in puslapiai
                  if (p.get("tipas") or "") in ("specification", "wall_elevation",
                                                  "finish_schedule")]
    # Pri 1 — title match
    for p in spec_pages:
        if _matches(p.get("pavadinimas", "")):
            nr = p.get("nr")
            if nr and nr not in by_priority:
                by_priority.append(nr)
    # Pri 2 — wall_elevation pages (often have tile spec for the room they show)
    for p in spec_pages:
        if (p.get("tipas") or "") == "wall_elevation":
            nr = p.get("nr")
            if nr and nr not in by_priority and len(by_priority) < 3:
                by_priority.append(nr)
    return by_priority[:3]


@app.post("/api/projects/{project_id}/material-specs")
async def api_extract_room_material_specs(
    request: Request,
    project_id: str,
    files: list[UploadFile] = File(...),
    room_nr: str = Form(...),
):
    """Extract designer material specs for ONE room. Frontend POSTs PDF blob."""
    user = _auth.require_user(request)
    user_filter = None if user.get("is_admin") else user["id"]
    project = db.get_project(project_id, user_id=user_filter)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    data = project.get("data") or {}
    rooms = data.get("patalpos") or []
    target_room = next((r for r in rooms if r.get("nr") == room_nr), None)
    if not target_room:
        raise HTTPException(status_code=404, detail=f"Room {room_nr} not found")

    # Cache check
    cached = (data.get("_material_specs") or {}).get(room_nr)
    if cached and not cached.get("_error"):
        return {**cached, "_cached": True}

    # Pick relevant pages
    puslapiai = data.get("puslapiai") or []
    spec_pages = _pick_spec_pages_for_room(target_room, puslapiai)
    if not spec_pages:
        return {
            "paint": None, "sienos_plyteles": None,
            "grindys_plyteles": None, "grindys_medines": None,
            "_meta": {"pages_inspected": [], "_warning": "no_spec_pages_found"},
        }

    if not files:
        raise HTTPException(status_code=400, detail="PDF file required")
    pdf_bytes = await files[0].read()

    # Run extraction (sync — wrapped in to_thread)
    from extractor.material_specs import extract_room_material_specs
    result = await asyncio.to_thread(
        extract_room_material_specs, pdf_bytes, spec_pages,
        target_room.get("pavadinimas") or room_nr,
    )

    # Cache in project data
    try:
        data.setdefault("_material_specs", {})[room_nr] = result
        db.upsert_project(project_id, {**project, "data": data},
                           user_id=user["id"])
    except Exception as exc:
        log.warning("material specs cache failed: %s", exc)

    return result


@app.delete("/api/projects/{project_id}/share")
async def api_revoke_share(request: Request, project_id: str):
    user = _auth.require_user(request)
    user_filter = None if user.get("is_admin") else user["id"]
    if not db.get_project(project_id, user_id=user_filter):
        raise HTTPException(status_code=404, detail="Project not found")
    db.clear_share_token(project_id)
    log.info("share token revoked: project=%s by user=%s", project_id, user["id"])
    return {"status": "revoked"}


@app.get("/api/share/{token}")
async def api_get_shared(token: str):
    """Public — return read-only project payload by share token. No auth needed.

    Strips owner-internal fields (_meta cost data, user_id) before returning.
    """
    project = db.get_project_by_share_token(token)
    if not project:
        raise HTTPException(status_code=404, detail="Share link netinkamas, atšauktas arba pasibaigęs galiojimas")
    # Sprint §36: bump view count on every successful access
    try:
        db.increment_share_view(token)
    except Exception as exc:
        log.warning("share view counter bump failed: %s", exc)
    data = project.get("data") or {}
    # Strip cost / token-level metadata so viewers can't see API spend.
    if isinstance(data, dict):
        meta = data.get("_meta")
        if isinstance(meta, dict):
            for k in ("input_tokens", "output_tokens", "cache_read_tokens",
                       "cache_write_tokens", "cost_eur", "zoom_input_tokens",
                       "zoom_output_tokens"):
                meta.pop(k, None)
    return {
        "id": project["id"],
        "name": project.get("name"),
        "company_name": project.get("company_name"),
        "tipas": project.get("tipas"),
        "archetipas": project.get("archetipas"),
        "bendras_plotas_m2": project.get("bendras_plotas_m2"),
        "vat_rate": project.get("vat_rate"),
        "created_at": project.get("created_at"),
        "data": data,
        "shared": True,
    }


@app.post("/api/projects/{project_id}/corrections")
async def api_log_correction(request: Request, project_id: str, payload: CorrectionPayload):
    """Append correction. Implicit ownership via project (only project owner can post)."""
    user = _auth.require_user(request)
    user_filter = None if user.get("is_admin") else user["id"]
    if not db.get_project(project_id, user_id=user_filter):
        raise HTTPException(status_code=404, detail="Project not found")
    db.log_correction(
        project_id=project_id, field_path=payload.field_path,
        old_value=payload.old_value, new_value=payload.new_value,
        source=payload.source, room_nr=payload.room_nr, note=payload.note,
    )
    return {"status": "logged"}


@app.get("/api/projects/{project_id}/corrections")
async def api_list_corrections(request: Request, project_id: str, limit: int = 500):
    user = _auth.require_user(request)
    user_filter = None if user.get("is_admin") else user["id"]
    if not db.get_project(project_id, user_id=user_filter):
        raise HTTPException(status_code=404, detail="Project not found")
    return {"corrections": db.list_corrections(project_id, limit=limit)}


@app.get("/api/projects/{project_id}/extractions")
async def api_list_extractions(request: Request, project_id: str):
    user = _auth.require_user(request)
    user_filter = None if user.get("is_admin") else user["id"]
    if not db.get_project(project_id, user_id=user_filter):
        raise HTTPException(status_code=404, detail="Project not found")
    return {"extractions": db.list_extractions(project_id)}


# ── ADMIN endpoints (require is_admin) ───────────────────────────────────────

@app.get("/api/admin/corrections-summary")
async def api_corrections_summary(request: Request):
    """Aggregated counts per field_path — input to manual prompt iteration.
    Shows which fields users override most often → indicates Vision bias."""
    _auth.require_admin(request)
    return {"summary": db.corrections_summary()}


@app.get("/api/admin/users")
async def api_admin_list_users(request: Request):
    _auth.require_admin(request)
    return {"users": db.list_users()}


@app.get("/api/admin/stats")
async def api_admin_stats(request: Request):
    """Cost + project counts across all users."""
    _auth.require_admin(request)
    with db._conn() as c:
        users_count = c.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
        projects_count = c.execute("SELECT COUNT(*) AS n FROM projects").fetchone()["n"]
        extractions_count = c.execute("SELECT COUNT(*) AS n FROM extractions").fetchone()["n"]
        cost_row = c.execute("SELECT SUM(cost_eur) AS total, AVG(cost_eur) AS avg FROM extractions").fetchone()
        corrections_count = c.execute("SELECT COUNT(*) AS n FROM corrections").fetchone()["n"]
    return {
        "users_count": users_count,
        "projects_count": projects_count,
        "extractions_count": extractions_count,
        "total_cost_eur": round(cost_row["total"] or 0, 2),
        "avg_cost_per_extract_eur": round(cost_row["avg"] or 0, 4),
        "corrections_count": corrections_count,
    }


@app.get("/api/admin/recent-projects")
async def api_admin_recent_projects(request: Request, limit: int = 50):
    """All projects across all users — admin overview."""
    _auth.require_admin(request)
    return {"projects": db.list_projects(user_id=None)[:limit]}

client = anthropic.Anthropic(
    api_key=os.environ["ANTHROPIC_API_KEY"],
    max_retries=1,
    timeout=120.0,
)

# ── PDF extraction ────────────────────────────────────────────────────────────

CHUNK_SIZE = 15  # pages per Claude call (used for fallback AI path only)

# When total extracted text exceeds this threshold, filter to KŽ-candidate pages
# before sending to Claude. Avoids processing entire 100+ page TS documents.
_LARGE_PDF_CHARS = 40_000   # ~10 k tokens

# Regex scoring KŽ-like content: a valid unit appearing near a number
_KZ_SCORE_RE = re.compile(
    r'(?:'
    r'\d[\d\s]*[,\.]\d+\s*(?:m2|m²|m3|m³|m\'|vnt\.?|kompl\.?|kg\b)|'  # qty then unit
    r'(?:m2|m²|m3|m³|m\'|vnt\.?|kompl\.?)\s*\|?\s*\d[\d,\.]*'           # unit then qty
    r')',
    re.IGNORECASE,
)

# Markers that identify a page as part of the KŽ (Kiekių Žiniaraštis) table
_KZ_MARKERS = [
    "DARBŲ KIEKIŲ ŽINIARAŠTIS",
    "KIEKIŲ ŽINIARAŠTIS",
    "/SK.KŽ",
    "/SP.KŽ",
    "SA/KŽ",
    "TDP-SA.KŽ",
    "TDP-SS.KŽ",
    "TDP-VK.KŽ",
]

_VALID_UNITS = {"m2", "m²", "m", "m'", "vnt", "vnt.", "t", "kompl", "kompl.", "m3", "m³", "kg", "h", "eur"}

# Match "1.1" style (standard KŽ) OR plain integer "1"-"999" (some PDFs use sequential numbering)
_NR_RE = re.compile(r'^\d+\.\d+$|^\d{1,3}$')
_SECTION_HDR_RE = re.compile(r'^\d+\.\s+[A-ZŠŽŲĖĮŪĄ]')
# Matches a bare section-number cell: "1." or "2." etc.
_SEC_NR_CELL_RE = re.compile(r'^\d+\.$')

# Page-footer content that should never be parsed as KŽ data
_FOOTER_SKIP = re.compile(
    r'^(LAIDA|lapas|lapų|LAPAS|LAPŲ|IŠLEIDIMO|UAB\s|MB\s|PROJEKTERA|STATYTOJAS|'
    r'UŽSAKOVAS|KVALIF|ARCH\s|STATINIO PROJEKTO|DOKUMENTO\s|P\d{4}[-/]|'
    r'[A-Z]\s\d{3}|LT\s+\d{3})',
    re.I,
)


def _parse_qty(s: str):
    """Convert '17,90' → 17.9  or  '1' → 1.0.  Returns None for invalid/blank/dash."""
    if not s:
        return None
    s = str(s).strip().replace(',', '.')
    if s in ('---', '--', '-', ''):
        return None
    try:
        v = float(s)
        return v if v > 0 else None
    except ValueError:
        return None


def _is_dash_qty(s: str) -> bool:
    """Return True when the quantity cell explicitly shows '---' / '--' (TBD quantity)."""
    return bool(s) and str(s).strip().replace('-', '') == ''


def _is_footer_row(cells: list) -> bool:
    non_empty = [c for c in cells if c]
    if not non_empty:
        return True
    first = non_empty[0]
    return bool(_FOOTER_SKIP.match(first))


def _text_sections(page_text: str) -> dict:
    """
    Scan page text for section headers like "5. GAMINIAI" or "1. NUOGRINDOS ĮRENGIMAS, KITI DARBAI".
    Returns dict: nr_prefix (str) → section_name (str).
    """
    result = {}
    for line in page_text.splitlines():
        line = line.strip()
        # Allow commas and mixed-case for wider PDF format compatibility
        m = re.match(r'^(\d+)\.\s+([A-ZŠŽŲĖĮŪĄĖ][A-ZŠŽŲĖĮŪĄa-zšžųėįūą\s\-,()]+)$', line)
        if m and len(m.group(2).strip()) > 3:
            result[m.group(1)] = m.group(2).strip().upper()
    return result


def _text_row_fallback(
    page_text: str,
    already_nrs: set,
    default_skyrius: str,
) -> list[dict]:
    """
    Secondary scan of raw page text to recover KŽ rows that pdfplumber's table
    extractor missed (typically rows that physically span a page boundary).

    Strategy: tokenise each line, scan right-to-left for a (unit, kiekis) pair,
    treat everything between nr and unit as the description.  When the description
    is empty, check the immediately preceding text line.

    default_skyrius: the skyrius in effect at the START of this page (before table
    processing updates it). The fallback tracks section headers encountered in the
    page TEXT to update the attribution per-row, so rows appearing before a section
    header are attributed to default_skyrius and rows after are attributed to the
    newly-seen section.
    """
    rows = []
    _units_lower = {u.lower().rstrip('.') for u in _VALID_UNITS}
    _sec_hdr_re = re.compile(
        r'^(\d+)\.\s+([A-ZŠŽŲĖĮŪĄĖ][A-ZŠŽŲĖĮŪĄa-zšžųėįūą\s\-,()]+)$'
    )
    lines = [l.strip() for l in page_text.splitlines()]

    current_fallback_skyrius = default_skyrius

    for i, line in enumerate(lines):
        # Track section headers encountered in text (position-aware attribution)
        sec_m = _sec_hdr_re.match(line)
        if sec_m and len(sec_m.group(2).strip()) > 3:
            current_fallback_skyrius = sec_m.group(2).strip().upper()
            continue

        tokens = line.split()
        if not tokens:
            continue

        # Line must start with an X.Y nr
        if not _NR_RE.match(tokens[0]) or '.' not in tokens[0]:
            continue
        nr = tokens[0]
        if nr in already_nrs:
            continue

        # Scan tokens right-to-left for the rightmost valid (unit, kiekis) pair
        unit = None
        unit_pos = -1
        kiekis = None
        kiekis_is_dash = False

        for j in range(len(tokens) - 1, 0, -1):
            tok = tokens[j]
            prev = tokens[j - 1]
            prev_lower = prev.lower().rstrip('.')
            if prev_lower not in _units_lower:
                continue
            # tok must be a number or a dash sequence
            if re.match(r'^[\d,]+\.?[\d]*$', tok):
                kiekis = _parse_qty(tok)
                unit = prev
                unit_pos = j - 1
                break
            elif _is_dash_qty(tok):
                kiekis_is_dash = True
                unit = prev
                unit_pos = j - 1
                break

        if unit is None:
            continue

        # Description is tokens between nr and unit
        desc = ' '.join(tokens[1:unit_pos]).strip()

        # If description is empty, look at the preceding non-empty text line
        if not desc:
            for k in range(i - 1, max(i - 3, -1), -1):
                prev_line = lines[k].strip()
                if not prev_line:
                    continue
                # Skip if it looks like a row, header, or footer
                if (re.match(r'^\d+[\.\d]', prev_line) or
                        re.match(r'^(LAIDA|lapas|UAB\s|P\d{4}|LT\s)', prev_line, re.I)):
                    break
                desc = prev_line
                break

        if not desc or len(desc) < 4:
            continue

        # Check the line immediately AFTER this line for a description continuation.
        # Happens when a long description wraps: preceding line has part 1, the nr
        # line has the unit/kiekis, and the next line has part 2 (e.g. "EPS70 arba
        # analogas Det. STD-").  Append the non-reference portion if present.
        if i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            # Reject if it looks like a new row, section header, footer, or TS ref
            if next_line and not re.match(r'^\d+[\.\d]', next_line) and \
               not re.match(r'^(LAIDA|lapas|UAB\s|P\d{4}|LT\s)', next_line, re.I):
                # Strip trailing TS/Det./STD reference codes before appending
                cont = re.sub(r'\s*(Det\.|TS[-\s]\d\S*|STD-\S*).*$', '', next_line).strip()
                if cont and len(cont) >= 3:
                    desc = desc + ' ' + cont

        rows.append({
            'nr': nr,
            'aprasymas': desc,
            'mato_vnt': unit,
            'kiekis': kiekis if not kiekis_is_dash else None,
            'skyrius': current_fallback_skyrius,
        })

    return rows


def _extract_kz_direct(pdf_bytes: bytes) -> tuple | None:
    """
    Primary extraction path: locate the DARBŲ KIEKIŲ ŽINIARAŠTIS pages using
    pdfplumber and parse their structured tables directly — no AI involved.

    Returns (projektas, eilutes) on success, or None to signal the AI fallback.
    """
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        total = len(pdf.pages)
        if not total:
            return None

        first_text = (pdf.pages[0].extract_text() or "") if total else ""
        projektas = _find_projektas(first_text)

        # ── Step 1: find KŽ pages ─────────────────────────────────────────────
        kz_indices = []
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            if any(marker in text for marker in _KZ_MARKERS):
                kz_indices.append(i)

        if not kz_indices:
            return None

        # ── Step 1b: extend to consecutive continuation pages ─────────────────
        # Many PDFs only mark the first KŽ page; subsequent pages continue the
        # same table without repeating the header text.
        _valid_units_lower = {u.lower().rstrip('.') for u in _VALID_UNITS}

        def _page_has_kz_data(page) -> bool:
            """Return True if the page contains table cells with valid KŽ units."""
            for table in (page.extract_tables() or []):
                for row in table:
                    for c in row:
                        if c and str(c).strip().lower().rstrip('.') in _valid_units_lower:
                            return True
            return False

        extended = set(kz_indices)
        max_kz = max(kz_indices)
        for i in range(max_kz + 1, min(max_kz + 25, total)):
            page = pdf.pages[i]
            text = page.extract_text() or ""
            # Stop if this looks like a new non-KŽ document section
            if re.search(
                r'TECHNINĖ SPECIFIKACIJA|TECHNINIAI REIKALAVIMAI|BRĖŽINYS|PIEŠ\.',
                text, re.I,
            ):
                break
            if _page_has_kz_data(page):
                extended.add(i)
            else:
                break  # gap in table data — assume KŽ ended

        kz_indices = sorted(extended)

        # ── Step 2: extract rows from KŽ pages ───────────────────────────────
        eilutes: list[dict] = []
        current_skyrius = "KITI DARBAI"
        current_section_prefix: str | None = None  # e.g. '4' for section 4
        last_data: dict | None = None  # for dual-unit continuation rows

        for pi in kz_indices:
            page = pdf.pages[pi]
            page_text = page.extract_text() or ""

            # Save skyrius BEFORE table processing so the text fallback can
            # start from the correct section state at the top of the page.
            skyrius_at_page_start = current_skyrius

            # Pre-build section map from page text (handles headers not in tables)
            sec_map = _text_sections(page_text)

            for table in (page.extract_tables() or []):
                for raw_row in table:
                    cells = [
                        str(c).replace('\n', ' ').strip() if c else ''
                        for c in raw_row
                    ]

                    if _is_footer_row(cells):
                        continue

                    non_empty = [c for c in cells if c]
                    if not non_empty:
                        continue

                    # ── Section header row ────────────────────────────────
                    # Form A: single cell "1. SECTION NAME" (standard format)
                    # Form B: two cells ["1.", "SECTION NAME"] (some PDFs)
                    # Only skip the row if it truly is a section header.
                    # Rows with ≤ 2 non-empty cells that DON'T match any header
                    # pattern (e.g. dual-unit continuation rows like ['vnt.', '1'])
                    # must fall through to the unit-finding logic below.
                    if len(non_empty) <= 2:
                        cand = non_empty[0]
                        is_header = False
                        # Form A: "1. SECTION NAME" all in one cell
                        if _SECTION_HDR_RE.match(cand) and cand.upper() == cand:
                            m_sec = re.match(r'^(\d+)\.', cand)
                            if m_sec:
                                current_section_prefix = m_sec.group(1)
                            current_skyrius = re.sub(r'^\d+\.\s*', '', cand).strip()
                            last_data = None
                            is_header = True
                        # Form B: "1." + "SECTION NAME" in separate cells
                        elif _SEC_NR_CELL_RE.match(cand) and len(non_empty) == 2:
                            name = non_empty[1].strip()
                            if len(name) > 3:
                                m_sec = re.match(r'^(\d+)\.', cand)
                                if m_sec:
                                    current_section_prefix = m_sec.group(1)
                                current_skyrius = name.upper()
                                last_data = None
                                is_header = True
                        if is_header:
                            continue
                        # Not a header — fall through so dual-unit continuation
                        # rows (e.g. ['', '', '', '', 'vnt.', '1', '']) are
                        # processed by the unit/kiekis/nr logic below.

                    # ── Find unit ─────────────────────────────────────────
                    # Also handles multi-unit cells: "m m2" or "vnt. m3" where
                    # both units are packed into one cell and the next cell holds
                    # the corresponding space-separated quantities ("126,5 16,0").
                    unit = None
                    unit_idx = -1
                    multi_units: list[tuple] = []  # [(unit_str, kiekis_val), ...]

                    for i, c in enumerate(cells):
                        c_val = c.strip()
                        if not c_val:
                            continue
                        if c_val.lower().rstrip('.') in _valid_units_lower:
                            unit = c_val
                            unit_idx = i
                            break
                        # Multi-unit cell: all space-separated tokens are valid units
                        parts = c_val.split()
                        if len(parts) >= 2 and all(
                            p.lower().rstrip('.') in _valid_units_lower for p in parts
                        ):
                            next_i = i + 1
                            if next_i < len(cells):
                                qty_parts = cells[next_i].split()
                                if len(qty_parts) == len(parts):
                                    multi_units = [
                                        (p, _parse_qty(q))
                                        for p, q in zip(parts, qty_parts)
                                    ]
                                    unit_idx = i
                                    break

                    if unit is None and not multi_units:
                        continue

                    # ── Find kiekis (cell immediately after unit) ─────────
                    # (Not used for multi-unit rows — quantities already parsed above)
                    kiekis = None
                    kiekis_is_dash = False
                    if not multi_units:
                        for offset in (1, 2):
                            idx = unit_idx + offset
                            if idx < len(cells):
                                c = cells[idx]
                                if _is_dash_qty(c):
                                    kiekis_is_dash = True
                                    break
                                v = _parse_qty(c)
                                if v is not None:
                                    kiekis = v
                                    break

                        # Skip only if kiekis is completely absent (not even a dash marker)
                        if kiekis is None and not kiekis_is_dash:
                            continue

                    # ── Find nr ───────────────────────────────────────────
                    # Nr always appears in the first 1–3 columns (before the
                    # description and unit). Restricting the search window avoids
                    # mistaking kiekis for nr when both happen to be the same integer.
                    nr = None
                    nr_idx = -1
                    search_up_to = min(3, unit_idx)
                    for i, c in enumerate(cells[:search_up_to]):
                        if _NR_RE.match(c):
                            nr = c
                            nr_idx = i
                            break

                    # ── Update skyrius from sec_map for X.Y nrs only ─────────
                    # sec_map is derived from page TEXT — it can include section
                    # headers that appear LATER on the same page, so we only apply
                    # it for dotted nrs (e.g. "5.1") where the section is named by
                    # the page header text rather than a table row.  Plain integers
                    # (e.g. "6") are handled entirely by table section-header rows
                    # to avoid premature section switches.
                    if nr and '.' in nr:
                        prefix = nr.split('.')[0]
                        if prefix in sec_map:
                            current_skyrius = sec_map[prefix]

                    # ── Find description ──────────────────────────────────
                    aprasymas = None
                    skip_vals = {unit or '', '---', '--', '-', ''}
                    start = nr_idx + 1 if nr_idx >= 0 else 0
                    for c in cells[start:unit_idx]:
                        if not c or c in skip_vals:
                            continue
                        if _NR_RE.match(c):
                            continue
                        if _parse_qty(c) is not None:
                            continue
                        # Skip TS-reference codes: "TS-01", "TS 01R", "TS 01R TS 02R", etc.
                        if re.match(r'^TS[-\s]\d|^(Det\.|STD-|[A-Z]{1,3}-\d)', c):
                            continue
                        if len(c) > 3:
                            aprasymas = c
                            break

                    # ── Emit ──────────────────────────────────────────────
                    if multi_units:
                        # Multi-unit cell: emit one row per (unit, kiekis) pair
                        if nr and aprasymas:
                            for u, k in multi_units:
                                eilutes.append({
                                    'nr': nr,
                                    'aprasymas': aprasymas,
                                    'mato_vnt': u,
                                    'kiekis': k,
                                    'skyrius': current_skyrius,
                                })
                            last_data = {'nr': nr, 'aprasymas': aprasymas}
                        elif nr is None and last_data:
                            for u, k in multi_units:
                                eilutes.append({
                                    'nr': last_data['nr'],
                                    'aprasymas': last_data['aprasymas'],
                                    'mato_vnt': u,
                                    'kiekis': k,
                                    'skyrius': current_skyrius,
                                })

                    elif nr and aprasymas:
                        row = {
                            'nr': nr,
                            'aprasymas': aprasymas,
                            'mato_vnt': unit,
                            'kiekis': kiekis,
                            'skyrius': current_skyrius,
                        }
                        eilutes.append(row)
                        last_data = {'nr': nr, 'aprasymas': aprasymas}

                    elif nr is None and last_data:
                        # Dual-unit continuation row (e.g. vnt. after m2)
                        eilutes.append({
                            'nr': last_data['nr'],
                            'aprasymas': last_data['aprasymas'],
                            'mato_vnt': unit,
                            'kiekis': kiekis,
                            'skyrius': current_skyrius,
                        })
                        # do NOT reset last_data — a row can have >2 units in theory

            # ── Text fallback: recover page-boundary rows ──────────────────
            already_nrs = {r['nr'] for r in eilutes}
            for fb_row in _text_row_fallback(
                page_text, already_nrs, skyrius_at_page_start
            ):
                eilutes.append(fb_row)
                last_data = {'nr': fb_row['nr'], 'aprasymas': fb_row['aprasymas']}

        # ── Sort rows by nr numerically (X.Y) so page-boundary fallback rows
        # inserted at the end end up in their correct position.
        def _nr_sort_key(r: dict) -> tuple:
            parts = r.get('nr', '0').split('.')
            try:
                return (int(parts[0]), int(parts[1]) if len(parts) > 1 else 0)
            except (ValueError, IndexError):
                return (0, 0)

        eilutes.sort(key=_nr_sort_key)

        # Success only if we found meaningful content
        if len(eilutes) >= 5:
            return projektas, eilutes

        return None


# ── Claude fallback prompt ────────────────────────────────────────────────────
# Used only when pdfplumber cannot find a structured KŽ table.

CHUNK_PROMPT = """\
You are reading pages {pages} of a Lithuanian construction project PDF.

IMPORTANT CONTEXT: Lithuanian construction PDFs contain multiple sections —
technical specifications (TS-xx), drawings, material lists, and the KŽ table.
You must ONLY extract rows from the DARBŲ KIEKIŲ ŽINIARAŠTIS (KŽ) table.
If these pages contain TS sections, drawings or material specs but NO KŽ rows — return [].

CRITICAL SPELLING RULE:
Copy all text EXACTLY as it appears in the PDF.
Do NOT correct, fix, or alter ANY Lithuanian word, character, or diacritic.
If the PDF says "vazido" — write "vazido". If it says "langų" — write "langų".
Never substitute one word for another, even if you believe there is a typo.

KŽ row pattern:
  <nr>  <aprasymas>  <mato_vnt>  <kiekis>

Rules for nr:
- digits-with-dot: 1.1, 2.3, 4.10, 1.14
- Waste codes like "17 01 07" or "17-02-01" — SKIP
- Section heading rows like "5. GAMINIAI" — use as skyrius, do NOT emit as a row

Rules for aprasymas:
- Lithuanian work description phrase
- SKIP: section headings, material spec lines ("Storis 10mm"), TS reference codes

Rules for mato_vnt:
- One of: m2, m², m, vnt, vnt., t, kompl, kompl., m3, m³, kg, h

Rules for kiekis:
- Positive number; comma decimal → dot: 17,90 → 17.90
- SKIP rows with "---", blank, or dash-only quantity

DUAL-UNIT RULE — apply consistently to ALL rows including 5.1, 5.2, 5.3, 5.4:
When a single KŽ row has BOTH an area quantity (m2) AND a count (vnt.),
extract TWO separate rows with the same nr and aprasymas:
  Row A: mato_vnt="m2",   kiekis=<area value>
  Row B: mato_vnt="vnt.", kiekis=<count value>
Apply this to EVERY such row without exception.

skyrius field:
- The nearest ALL-CAPS section heading above the item within the KŽ table
- Strip leading number: "5. GAMINIAI" → "GAMINIAI", "1. ARDYMO DARBAI" → "ARDYMO DARBAI"
- Never leave empty — use "KITI DARBAI" if no heading found

Return ONLY a raw JSON array. No markdown. No explanation.
If no KŽ rows on these pages: return []

Example:
[{"nr":"1.1","aprasymas":"Langų demontavimas","mato_vnt":"m2","kiekis":17.9,"skyrius":"ARDYMO DARBAI"},
 {"nr":"5.1","aprasymas":"PVC lango montavimas 1600x1500 (3 varstymo padėtys) (L-1)","mato_vnt":"m2","kiekis":2.4,"skyrius":"GAMINIAI"},
 {"nr":"5.1","aprasymas":"PVC lango montavimas 1600x1500 (3 varstymo padėtys) (L-1)","mato_vnt":"vnt.","kiekis":1,"skyrius":"GAMINIAI"}]

Pages {pages} text:
{text}"""


def _find_projektas(full_text: str) -> str:
    """Extract project name from the first pages of text."""
    skip = re.compile(
        r"^(UAB|MB\.|mob\.|tel\.|www\.|Į\.k\.|A\.s\.|PVM|Fax|Email|El\.\s*pašt|Lapas|Laida)",
        re.I,
    )
    only_short = re.compile(r"^[\d\s\.\-\+\/\(\)]{1,20}$")
    postal = re.compile(r"LT-\d{5}|^\+370")
    project_kw = re.compile(
        r"(projektas|statybos|rekonstrukcij|atnaujinimo|modernizav|"
        r"kapitalin|įrengim|statyba|pastato|namo\s+\w|namų)",
        re.I,
    )
    candidates = []
    for line in full_text.splitlines():
        line = line.strip()
        if len(line) < 12:
            continue
        if skip.match(line) or only_short.match(line) or postal.search(line):
            continue
        candidates.append(line)

    for line in candidates:
        if project_kw.search(line):
            return line
    return candidates[0] if candidates else ""


def _pdf_to_chunks(pdf_bytes: bytes) -> tuple[str, list[dict]]:
    """Read pages from the PDF, extract text + tables, split into chunks.

    For large PDFs (total extracted text > _LARGE_PDF_CHARS), only pages that
    score as KŽ candidates (contain unit/quantity patterns) are included.
    If no candidate pages are found in a large PDF, returns an empty list so
    the caller skips Claude entirely rather than processing 100+ irrelevant pages.

    Returns (project_name, [{"pages": "1-15", "text": "..."}]).
    """
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        total = len(pdf.pages)
        first_text = (pdf.pages[0].extract_text() or "") if total else ""
        projektas = _find_projektas(first_text)

        # ── Extract text + table content for every page ───────────────────
        page_data: list[tuple[int, str]] = []   # (1-based page number, combined text)
        total_chars = 0
        for i, page in enumerate(pdf.pages):
            page_text = page.extract_text() or ""
            table_rows = []
            for table in (page.extract_tables() or []):
                for row in table:
                    cells = [str(c).strip() for c in (row or []) if c and str(c).strip()]
                    if len(cells) >= 2:
                        table_rows.append(" | ".join(cells))
            combined = page_text
            if table_rows:
                combined = combined + "\n" + "\n".join(table_rows)
            combined = combined.strip()
            if combined:
                page_data.append((i + 1, combined))
                total_chars += len(combined)

        # ── For large PDFs, filter to KŽ-candidate pages ─────────────────
        if total_chars > _LARGE_PDF_CHARS:
            candidate_pages = [
                (pno, text) for pno, text in page_data
                if len(_KZ_SCORE_RE.findall(text)) >= 5
            ]
            # If no candidates found, skip Claude entirely (empty chunks)
            if not candidate_pages:
                return projektas, []
            page_data = candidate_pages

        # ── Group into chunks by CHUNK_SIZE consecutive pages ─────────────
        chunks = []
        for i in range(0, len(page_data), CHUNK_SIZE):
            group = page_data[i: i + CHUNK_SIZE]
            chunk_text = "\n".join(text for _, text in group).strip()
            if not chunk_text:
                continue
            pages_label = f"{group[0][0]}-{group[-1][0]}"
            chunks.append({
                "pages": pages_label,
                "text": chunk_text,
            })

    return projektas, chunks


def _parse_eilutes(raw: str) -> list:
    """Parse Claude response into a list of rows.
    Handles: markdown code fences, truncated JSON, object wrapper."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```\s*$", "", raw).strip()

    # Try full parse first
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict):
            for key in ("eilutes", "items", "pozicijos", "data", "result"):
                if isinstance(parsed.get(key), list):
                    return parsed[key]
        return []
    except json.JSONDecodeError:
        pass

    # Response was truncated — salvage every complete {...} object
    items = []
    for m in re.finditer(r'\{[^{}]+\}', raw, re.DOTALL):
        try:
            obj = json.loads(m.group())
            if "aprasymas" in obj and "kiekis" in obj:
                items.append(obj)
        except json.JSONDecodeError:
            continue
    return items


# Model used for the Claude fallback extraction path.
# Opus delivers the highest accuracy; override with the env var for cost/speed
# trade-offs (e.g. EXTRACTION_MODEL=claude-haiku-4-5-20251001 for fast/cheap).
EXTRACTION_MODEL = os.getenv("EXTRACTION_MODEL", "claude-opus-4-7")


def _call_claude(prompt: str) -> str:
    msg = client.messages.create(
        model=EXTRACTION_MODEL,
        max_tokens=8096,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text


# ── /extract ─────────────────────────────────────────────────────────────────

def _postprocess_eilutes(all_eilutes: list) -> list:
    """
    Shared post-processing for both direct and Claude extraction paths:
    1. Carry skyrius forward for rows with empty skyrius
    2. Deduplicate exact clones
    """
    # 1. Carry skyrius forward
    last_skyrius = ""
    for e in all_eilutes:
        sky = (e.get("skyrius") or "").strip()
        if sky:
            sky = re.sub(r"^\d+\.\s*", "", sky).strip()
            e["skyrius"] = sky
            last_skyrius = sky
        elif last_skyrius:
            e["skyrius"] = last_skyrius
        else:
            e["skyrius"] = "KITI DARBAI"

    # 2. Deduplicate exact clones
    seen: set = set()
    deduped: list = []
    for e in all_eilutes:
        key = (
            e.get("nr", ""),
            e.get("aprasymas", ""),
            e.get("mato_vnt", ""),
            e.get("kiekis", 0),
            e.get("skyrius", ""),
        )
        if key not in seen:
            seen.add(key)
            deduped.append(e)
    return deduped


@app.post("/extract")
async def extract(file: UploadFile = File(...)):
    try:
        async with asyncio.timeout(300):  # 5 min – daug chunks gali užtrukti

            contents = await file.read()

            # ── Path 1: pdfplumber direct extraction ─────────────────────────
            try:
                direct = await asyncio.to_thread(_extract_kz_direct, contents)
            except Exception:
                direct = None

            if direct is not None:
                projektas, eilutes = direct
                eilutes = _enrich_eilutes(_postprocess_eilutes(eilutes))
                return {
                    "projektas": projektas,
                    "eilutes": eilutes,
                    "meta": {
                        "total_pages": None,
                        "chunks_processed": 0,
                        "chunks_with_data": 0,
                        "extraction_method": "direct",
                    },
                }

            # ── Path 2: Claude chunked fallback ──────────────────────────────
            # 1 etapas – PDF → chunks
            try:
                projektas, chunks = await asyncio.to_thread(
                    _pdf_to_chunks, contents
                )
            except Exception as e:
                return {"error": f"PDF nepavyko nuskaityti: {type(e).__name__}: {e}"}

            if not chunks:
                return {"error": "PDF tekstas nerastas — galbūt skanuotas vaizdas?"}

            total_pages = int(chunks[-1]["pages"].split("-")[-1])

            # 2 etapas – kiekvieną chunk į Claude
            all_eilutes: list = []
            chunks_with_data = 0
            prev_tail = ""          # last ~1000 chars of previous chunk for cross-boundary context

            MAX_CHARS  = 16000
            TAIL_CHARS = 1000      # how much of the previous chunk to prepend as context
            WIN_OVERLAP = 500      # overlap between sequential windows to avoid missing boundary rows

            for chunk in chunks:
                full_text = chunk["text"]
                pages     = chunk["pages"]

                # Prepend prev_tail so section headers at the end of one chunk
                # are visible at the start of the next.
                ctx     = (prev_tail + "\n--- (context from previous pages) ---\n") if prev_tail else ""
                ctx_len = len(ctx)
                available = MAX_CHARS - ctx_len

                # Store tail of the FULL (untruncated) chunk for the next iteration
                prev_tail = full_text[-TAIL_CHARS:]

                if len(full_text) <= available:
                    # Fits in a single Claude call
                    windows = [(ctx + full_text, pages)]
                else:
                    # Chunk is too large — slide sequential windows through the FULL text
                    # so the middle is never skipped.  The first window gets the ctx prefix;
                    # subsequent windows use the full MAX_CHARS budget.
                    windows = []
                    pos = 0
                    first = True
                    while pos < len(full_text):
                        if first:
                            win = full_text[pos : pos + available]
                            send = ctx + win
                            first = False
                        else:
                            win = full_text[pos : pos + MAX_CHARS]
                            send = win
                        windows.append((send, pages))
                        advance = len(win) - WIN_OVERLAP
                        if advance <= 0 or pos + len(win) >= len(full_text):
                            break
                        pos += advance

                for send_text, pg in windows:
                    prompt = (
                        CHUNK_PROMPT
                        .replace("{pages}", pg)
                        .replace("{text}",  send_text)
                    )
                    try:
                        raw = await asyncio.to_thread(_call_claude, prompt)
                        eilutes = _parse_eilutes(raw)
                        if eilutes:
                            all_eilutes.extend(eilutes)
                            chunks_with_data += 1
                    except Exception:
                        continue  # šiame chunk'e duomenų nėra arba API klaida

            # ── Post-process ──────────────────────────────────────────────
            all_eilutes = _enrich_eilutes(_postprocess_eilutes(all_eilutes))

            return {
                "projektas": projektas,
                "eilutes": all_eilutes,
                "meta": {
                    "total_pages": total_pages,
                    "chunks_processed": len(chunks),
                    "chunks_with_data": chunks_with_data,
                    "extraction_method": "claude",
                    "extraction_model": EXTRACTION_MODEL,
                },
            }

    except asyncio.TimeoutError:
        return {"error": "Timeout — PDF per didelis arba API neatsakė laiku."}
    except Exception as e:
        return {"error": f"Nenumatyta klaida: {type(e).__name__}: {e}"}


# ── Interior project extraction ───────────────────────────────────────────────

import base64

VISION_MODEL = os.getenv("VISION_MODEL", "claude-opus-4-7")

_INTERIOR_MARKERS = [
    "INTERJERO PROJEKTAS", "IŠKLOTINĖ", "IŠKLOTINIŲ",
    "LUBŲ PLANAS", "GRINDŲ PLANAS", "PERTVARŲ PLANAS",
    "PATALPŲ EKSPLIKACIJA", "BALDŲ PLANAS", "APDAILŲ PLANAS",
]

# Map page type name → (regex, confidence, lithuanian_label)
# IMPORTANT: "PATALPŲ EKSPLIKACIJA" appears in the title block footer of EVERY drawing page
# in many Lithuanian interior design PDFs, so it must NOT be used for classification.
# Each pattern also includes content-based keywords (visible in pdfplumber text) as fallback
# because page-title headers are often rendered as vectors and not extractable as text.
_PAGE_TYPE_PATTERNS: dict[str, tuple] = {
    "vizualizacija": (re.compile(r"VIZUALIZACIJ|3D VAIZDAS|PERSPEKTYVINIS|TITULINIS", re.I), "high", "Vizualizacija"),
    "cover":         (re.compile(r"INTERJERO PROJEKTAS|TITULINIS LAPAS", re.I), "high", "Viršelis"),
    # išklotinė before specifikacija: "IŠKLOTINĖS" appears in footer of wall elevation pages
    "išklotinė":     (re.compile(r"IŠKLOTINĖ\b|IŠKLOTINĖS\b|WALL ELEVATION|SIENŲ PLĖTINYS", re.I), "high", "Išklotinė"),
    # specifikacija: do NOT include EKSPLIKACIJ — room schedule table appears on every drawing page
    "specifikacija": (re.compile(r"\bSPECIFIKACIJ\b|ŽINIARAŠTIS|SCHEDULE|SĄRAŠAS", re.I), "high", "Specifikacija"),
    # lubų: title OR content keywords (curtain niches, LED types, ceiling height annotations)
    "lubų":          (re.compile(r"LUBŲ PLANAS|CEILING PLAN|Formuojamos nišos|LD-[123]\b|\+[23]\d{3}", re.I), "high", "Lubų planas"),
    # rozecių: title OR legend keywords specific to outlet plans
    "rozecių":       (re.compile(r"ROZEČIŲ PLANAS|ELEKTROS INSTALIACIJ|OUTLETS PLAN|Interneto rozetė|USB-C\b", re.I), "high", "Rozečių planas"),
    # apšvietimo: title OR lighting-specific keywords (DIM annotations, LED lighting text)
    "apšvietimo":    (re.compile(r"APŠVIETIMO PLANAS|ELEKTROS APŠVIET|LIGHTING PLAN|LED apšviet|\dDIM\b", re.I), "high", "Apšvietimo planas"),
    # santechnikos: title OR plumbing-specific content
    "santechnikos":  (re.compile(r"SANTECHNIKOS PLANAS|VANDENTIEKIO|KANALIZACIJ|Maišytuvo pajungimas", re.I), "high", "Santechnikos planas"),
    # pertvarų: title OR floor plan content (wc frame symbol text, partition wall keywords)
    "pertvarų":      (re.compile(r"PERTVARŲ PLANAS|BALDŲ PLANAS|PARTITION PLAN|FLOOR PLAN|wc rėmas", re.I), "high", "Pertvarų planas"),
    # grindų: title OR floor material keywords
    "grindų":        (re.compile(r"GRINDŲ PLANAS|FLOOR FINISHES|Parketlentės|Grindjuostės", re.I), "high", "Grindų planas"),
    # apdailų: title OR wall finish legend keywords
    "apdailų":       (re.compile(r"IŠKLOTINIŲ IR APDAILŲ|APDAILŲ PLANAS|FINISHES PLAN|Siena dengiama plokšte|Vaikiški tapetai", re.I), "high", "Apdailų planas"),
    "pririšimo":     (re.compile(r"PRIRIŠIMO PLANAS|REFERENCE PLAN", re.I), "high", "Pririšimo planas"),
    "fasadas":       (re.compile(r"FASAD[AS]\b|PIETŲ FASAD|ŠIAURĖS FASAD|RYTŲ FASAD|VAKARŲ FASAD", re.I), "high", "Fasadas"),
    "pjūvis":        (re.compile(r"\bPJŪVIS\b|SKERSPJŪVIS", re.I), "high", "Pjūvis"),
}

# Confidence for fallback text-based classification
_PAGE_TYPE_LABELS_LT: dict[str, str] = {
    "vizualizacija": "Vizualizacija",
    "cover":         "Viršelis",
    "specifikacija": "Specifikacija",
    "pertvarų":      "Pertvarų planas",
    "santechnikos":  "Santechnikos planas",
    "rozecių":       "Rozečių planas",
    "lubų":          "Lubų planas",
    "pririšimo":     "Pririšimo planas",
    "apšvietimo":    "Apšvietimo planas",
    "grindų":        "Grindų planas",
    "apdailų":       "Apdailų planas",
    "išklotinė":     "Išklotinė",
    "fasadas":       "Fasadas",
    "pjūvis":        "Pjūvis",
    "kita":          "Kita",
}

# Only these page types are sent to Vision API
_VISION_PAGE_TYPES = {
    "lubų", "grindų", "apdailų", "išklotinė", "pertvarų",
    "santechnikos", "rozecių", "apšvietimo",
}

# Page types that have no meaningful data to extract (skip for most processing)
_SKIP_PAGE_TYPES = {"vizualizacija", "cover", "kita"}

# Fallback: infer room number from wall-section letter when Vision doesn't provide room_nr.
# This mapping is typical for standard Lithuanian apartment layouts but may vary per project.
# Vision's explicit room_nr field always takes priority over this.
_ROOM_LETTER_MAP: dict[str, str] = {
    'a': '102', 'b': '104', 'c': '106', 'd': '107',
    'e': '108', 'f': '109', 'g': '110', 'h': '111',
}

# Room list line: "101  Tambūras  11.01" or "101  Svetainė/Virtuvė  50.54"
_EKSPLIKACIJA_RE = re.compile(
    r'\b(\d{3})\b\s{1,5}'
    r'([A-ZŠŽŲĖĮŪĄ][A-Za-zšžųėįūąŠŽŲĖĮŪĄ/\s,\.]{2,40}?)\s{1,5}'
    r'(\d{1,3}[,\.]\d{2})\s*(?:m[²2])?',
    re.M,
)

# Ceiling height: "101  +3400" or just "+2800" on lubų page
_CEILING_HT_RE  = re.compile(r'\b(\d{3})\b[^\n]{0,40}\+(\d{4})', re.M)
_CEILING_MARK_RE = re.compile(r'\+(\d{4})')

# Vision prompts keyed by page type
_VISION_PROMPTS: dict[str, str] = {
    "pertvarų": (
        "Analyze this Lithuanian interior design floor plan (PERTVARŲ PLANAS).\n\n"
        "Extract FOUR things:\n\n"
        "1. ROOM TABLE (PATALPŲ EKSPLIKACIJA): room number, name, floor area m².\n\n"
        "2. ALL VERTICAL WALL CORNERS — count EVERY corner where two wall surfaces meet "
        "at an angle (both inner/concave AND outer/convex corners). These are the plaster "
        "corner bead positions (glaistymo kampai) that a finishing contractor must treat.\n"
        "   Count systematically by tracing every room:\n"
        "   - Each RECTANGULAR room has 4 inner corners.\n"
        "   - L-shaped or irregular rooms have 5–6 corners.\n"
        "   - Each FREE END of a partition wall → 2 outer corners (one on each side).\n"
        "   - WALL STEP or notch → 2 outer + 2 inner = 4 corners per step.\n"
        "   - COLUMNS or rectangular protrusions → 4 outer corners each.\n"
        "   For a 10-room apartment expect 60–120 total corners.\n"
        "   Report separately: isoriniu_kampu_vnt (outer/convex) and visu_kampu_vnt (ALL corners).\n"
        "   List each group with a short location description and the count it contributes.\n\n"
        "3. ALL DOOR OPENINGS — every door arc or labeled door opening visible on the plan.\n"
        "   For each door:\n"
        "   - Width in mm (read dimension lines; typical: 700, 800, 900, 1000 mm)\n"
        "   - Height in mm: if labeled 'iki lubų' or 'iki perdangos' use ceiling height "
        "(2800 or 3400); otherwise use 2200 mm\n"
        "   - Which two rooms it connects\n"
        "   - Type label if shown (e.g. 'Durų anga iki lubų', 'Anga stiklinei pertvarai')\n"
        "   Count every room: tambūras (101), koridorius (103), garažas (105) each have at "
        "least 1–2 doors; living/bedroom rooms usually have 1 door each. Total 10–15 doors "
        "is typical for this size house.\n\n"
        "4. For rooms 101, 103, 105 (no wall elevation drawings): read their wall perimeter "
        "in mm from the dimension lines on this plan.\n\n"
        "Return ONLY valid JSON (no markdown):\n"
        '{"patalpos":[{"nr":"101","pavadinimas":"Tambūras","plotas_m2":11.01}],'
        '"visu_kampu_vnt":84,'
        '"isoriniu_kampu_vnt":18,'
        '"isoriniu_kampai":['
        '{"vieta":"free end of partition between 102 and 103","corner_count":2},'
        '{"vieta":"corridor wall step near 103/104","corner_count":2}],'
        '"doors":['
        '{"between":["101","102"],"width_mm":900,"height_mm":2800,"tipas":"iki lubų"},'
        '{"between":["102","103"],"width_mm":800,"height_mm":2200,"tipas":"standartinės"},'
        '{"between":["103","108"],"width_mm":800,"height_mm":2200,"tipas":"standartinės"}],'
        '"room_perimeters_without_iskl":{'
        '"101":{"estimated_perimeter_mm":13500},'
        '"103":{"estimated_perimeter_mm":12700},'
        '"105":{"estimated_perimeter_mm":13300}}}'
    ),
    "santechnikos": (
        "Analyze this Lithuanian plumbing plan (SANTECHNIKOS PLANAS). "
        "Count all plumbing fixtures using the legend: "
        "WC rėmas (toilet frame/potinkinis WC rėmas), "
        "dušo sistema (shower — potinkinės dušo dalys), "
        "praustuvė/kriauklė (sink/basin), "
        "vonios maišytuvas (bath mixer/vonia), "
        "skalbimo mašinos pajungimas (washing machine connection), "
        "trapas/linijinis trapas (floor drain), "
        "kondicionierius (AC unit — marked 'kondic.'), "
        "maišytuvo pajungimas (mixer tap connection). "
        "Return ONLY valid JSON (no markdown):\n"
        '{"wc_remai_vnt":2,"duso_sistemos_vnt":2,"praustuves_vnt":3,'
        '"vonios_maistuvai_vnt":1,"skalbimo_masinos_vnt":1,"trapai_vnt":2,'
        '"kondicionieriai_vnt":5,"maistuvai_vnt":4}'
    ),
    "rozecių": (
        "Analyze this Lithuanian electrical outlets plan (ROZEČIŲ PLANAS). "
        "Count ALL instances of each symbol type using the legend (Sutartiniai žymėjimai): "
        "Rozetė (electrical outlet — circle with lines), "
        "Jungiklis (switch — triangle symbol), "
        "Interneto rozetė (internet socket — marked I or INT), "
        "Antena (antenna — marked A), "
        "USB-C socket (marked U or USB-C), "
        "Termostatas (thermostat — marked T), "
        "Pajungimas prietaisui (appliance connection — solid dot), "
        "Vartai (gate control — marked V). "
        "Note: groups like 'Rozetės (3vnt) + INT' count as 3 outlets + 1 internet. "
        "Return ONLY valid JSON (no markdown):\n"
        '{"rozetes_vnt":45,"jungikliai_vnt":18,"interneto_rozetes_vnt":8,'
        '"antenos_vnt":2,"usb_c_vnt":1,"termostatai_vnt":10,'
        '"prietaisu_pajungimai_vnt":6,"vartai_vnt":1}'
    ),
    "lubų": (
        "Analyze this Lithuanian ceiling plan (LUBŲ PLANAS). Extract:\n\n"
        "1. Per room (3-digit codes): ceiling height (+XXXX = mm from floor), "
        "ceiling type (GKP = hatched gypsum board zone, or standard plaster).\n\n"
        "2. CURTAIN NICHES (užuolaidų nišos) — THIS IS CRITICAL. "
        "These are ceiling recesses near windows used to hide curtain rods.\n"
        "   - Shown as dashed or dotted rectangles running along exterior walls\n"
        "   - Legend entry: 'Formuojamos nišos užuolaidoms, plotis 10–25 cm'\n"
        "   - Appear near EVERY window in EVERY room\n"
        "   CHECK EVERY EXTERIOR WALL of every room:\n"
        "   Room 102 (Svetainė/virtuvė) — likely has niches on south and/or west wall\n"
        "   Room 104 (Darbo kambarys) — likely has a niche\n"
        "   Rooms 108, 109 (Berniukų kambariai) — likely have niches on east/south wall\n"
        "   Room 110 (Miegamasis) — likely has a niche\n"
        "   Room 111 (Tėvų vonia) — may have a small niche\n"
        "   For EACH niche: read the LENGTH (parallel to wall) in mm from dimension lines.\n"
        "   A house with 6–8 windows typically has 8–15 m of curtain niches total.\n"
        "   List EACH niche as a separate entry.\n\n"
        "3. LED niches (LD-1, LD-2, LD-3): estimate total length in meters for each type.\n\n"
        "4. GKP ceiling boxes/drops (dėžutės): estimate total perimeter in meters.\n\n"
        "Return ONLY valid JSON (no markdown):\n"
        '{"patalpos":[{"nr":"101","lubu_aukstis_mm":3400,"lubu_tipas":"GKP"}],'
        '"curtain_niches":['
        '{"room":"102","wall":"south","length_mm":3500},'
        '{"room":"102","wall":"west","length_mm":2500},'
        '{"room":"110","wall":"south","length_mm":2200}],'
        '"total_curtain_niches_m":12.5,'
        '"led_niches":{"LD-1":{"total_m":15},"LD-2":{"total_m":8}},'
        '"gkp_dezuciu_m":12.0}'
    ),
    "apšvietimo": (
        "Analyze this Lithuanian lighting plan (ELEKTROS APŠVIETIMO PLANAS). "
        "Count ALL light fixtures and electrical items using the legend (Sutartiniai žymėjimai): "
        "pakabinamas lubinis šviestuvas (pendant ceiling light), "
        "įleidžiamas halogeninis/LED šviestuvas (recessed light), "
        "sieninis šviestuvas (wall light sconce), "
        "įleistos LED juostos (recessed LED strips — estimate TOTAL linear meters), "
        "paviršinis šviestuvas (surface mounted light), "
        "JD judesio daviklis (motion sensor), "
        "gaisro daviklis (fire/smoke detector), "
        "garso kolonėlė (speaker), "
        "U elektrinės užuolaidos (electric curtain motor). "
        "Return ONLY valid JSON (no markdown):\n"
        '{"pakabinami_sviestuvai_vnt":4,"ileidziami_sviestuvai_vnt":35,'
        '"sieniniai_sviestuvai_vnt":8,"led_juostos_m":45,'
        '"pavirsiniai_sviestuvai_vnt":2,"judesio_davikliai_vnt":3,'
        '"gaisro_davikliai_vnt":6,"garso_koloneles_vnt":4,"elektrines_uzuolaidos_vnt":6}'
    ),
    "grindų": (
        "Analyze this Lithuanian floor plan (GRINDŲ PLANAS). "
        "Extract ALL floor material zones: "
        "parketlentės (parquet/hardwood — note total area m2 if shown), "
        "plytelės (tiles — note full tile name, size, and piece count if shown), "
        "vinilo danga (vinyl flooring). "
        "For each zone list the room numbers it covers. "
        "Also note grindjuostės (baseboard/skirting) total length in meters if given. "
        "Return ONLY valid JSON (no markdown):\n"
        '{"grindų_zonos":['
        '{"patalpos_nr":["102","103"],"medžiaga":"parketlentės","plotas_m2":135},'
        '{"patalpos_nr":["107","111"],"medžiaga":"plytelės Living ceramics Vonn Light 120x120cm","kiekis_vnt":14}],'
        '"grindjuostes_m":56}'
    ),
    "apdailų": (
        "Analyze this Lithuanian wall finishes overview (IŠKLOTINIŲ IR APDAILŲ PLANAS). "
        "Find the SUTARTINIAI ŽYMĖJIMAI (legend) and map each hatching/pattern to its material. "
        "Typical materials: plytelės kronosceramiche (tiles), dažymas balta spalva (white paint), "
        "siena dengiama plokšte (panel), vaikiški tapetai (wallpaper), veidrodis (mirror). "
        "For each room/zone map, note which wall codes (a1-a9, b1-b3, etc.) use which finish. "
        "Return ONLY valid JSON (no markdown):\n"
        '{"sienu_zonos":[{"kodas":"a1","patalpas_nr":"102","apdaila":"dažymas"}],'
        '"legenda":{"diagonal_lines":"plytelės kronosceramiche","crosshatch":"medinė plokštė",'
        '"white":"dažymas balta spalva"}}'
    ),
    "išklotinė": (
        "You are analyzing a Lithuanian interior wall elevation drawing (IŠKLOTINĖ). "
        "These are STRAIGHT-ON wall views with EXACT dimensions in millimeters.\n\n"
        "For EACH wall section (labeled a1, a2, b1, c1, d1, g5, h2, etc.):\n"
        "1. DIMENSIONS: total WIDTH in mm from the bottom dimension line; "
        "HEIGHT in mm from the side dimension (usually 2800 or 3400).\n"
        "2. ROOM NUMBER: read from labels or nearby text. "
        "Common: a→room 102, b→104, c→106, d→107, e→108, f→109, g→110, h→111.\n"
        "3. ZONES — for each distinct material zone, read its area from dimension lines:\n"
        "   - Empty/white = dažymas (paint)\n"
        "   - Diagonal lines (///) = plytelės (tiles, note tile name)\n"
        "   - Wood grain / cross-hatch = medžio_lukštas or plokštė (panel)\n"
        "   - Dots/grid = tapetai or tekstilė\n"
        "   - Labeled 'Lentynos','Stalčiai','Gaminama iš plokštės' = baldai (furniture/built-in)\n"
        "   - Mirror symbol = veidrodis\n"
        "   For each zone: type, width_mm, height_mm, area_m2 (=w*h/1e6), note if labeled.\n"
        "4. OPENINGS: doors (durys) and windows (langas) with width_mm × height_mm.\n\n"
        "CRITICAL: width and height come from the dimension LINES on the drawing, not guesses.\n\n"
        "Return ONLY valid JSON (no markdown):\n"
        '{"wall_sections":['
        '{"id":"a1","room_nr":"102","width_mm":3200,"height_mm":2800,"gross_area_m2":8.96,'
        '"zones":['
        '{"type":"dažymas","width_mm":3200,"height_mm":1500,"area_m2":4.80},'
        '{"type":"plytelės","width_mm":3200,"height_mm":1000,"area_m2":3.20,"note":"kronosceramiche lux venna"},'
        '{"type":"baldai","width_mm":2400,"height_mm":800,"area_m2":1.92}],'
        '"openings":[{"type":"durys","width_mm":900,"height_mm":2200}]}]}'
    ),
}


def _detect_project_type(pdf_bytes: bytes) -> str:
    """Scan first 10 pages and return 'kz', 'interior', or 'unknown'."""
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages[:10]:
            text = page.extract_text() or ""
            if any(m in text for m in _KZ_MARKERS):
                return "kz"
            if any(m in text for m in _INTERIOR_MARKERS):
                return "interior"
    return "unknown"


def _classify_page(text: str) -> str:
    for pt, (pat, conf, label) in _PAGE_TYPE_PATTERNS.items():
        if pat.search(text):
            return pt
    return "kita"


def _classify_page_with_confidence(text: str) -> tuple[str, str]:
    """Returns (page_type, confidence): confidence is high/medium/low."""
    for pt, (pat, conf, label) in _PAGE_TYPE_PATTERNS.items():
        if pat.search(text):
            return pt, conf
    # Low confidence fallback: check for partial hints
    tl = text.lower()
    if any(k in tl for k in ("planas", "plan")):
        return "kita", "medium"
    return "kita", "low"


def _extract_eksplikacija(text: str) -> list[dict]:
    rooms = []
    seen_nrs = set()
    for m in _EKSPLIKACIJA_RE.finditer(text):
        nr = m.group(1)
        if nr in seen_nrs:
            continue
        pavadinimas = m.group(2).strip().rstrip('.')
        try:
            plotas = float(m.group(3).replace(',', '.'))
        except ValueError:
            continue
        if plotas > 500:   # sanity: no single room > 500 m²
            continue
        rooms.append({"nr": nr, "pavadinimas": pavadinimas, "plotas_m2": plotas})
        seen_nrs.add(nr)
    return rooms


def _extract_ceiling_heights(text: str) -> dict[str, int]:
    heights: dict[str, int] = {}
    # Pattern: "102  +3400" or "102 (Svetainė): +3400"
    for m in _CEILING_HT_RE.finditer(text):
        heights[m.group(1)] = int(m.group(2))
    return heights


def _extract_floor_materials(text: str) -> list[str]:
    materials = []
    kw = ('parketlentė', 'parketas', 'plytelė', 'plytele',
          'grindjuost', 'vinilo', 'laminat', 'medžio masyvo')
    for line in text.splitlines():
        line = line.strip()
        if any(k in line.lower() for k in kw) and len(line) > 4:
            materials.append(line)
    return materials


def _extract_interior_text(pdf_bytes: bytes) -> dict:
    """
    First pass: pdfplumber text extraction.
    Returns: projektas, patalpos (room list), ceiling_heights,
             floor_materials, page_types, pages_text, page_classifications.
    """
    result: dict = {
        "projektas": "",
        "patalpos": [],
        "page_types": {},
        "ceiling_heights": {},
        "floor_materials": [],
        "pages_text": {},
        "page_classifications": [],  # Task 1: full classification list
    }

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            pno = i + 1
            result["pages_text"][pno] = text

            pt, conf = _classify_page_with_confidence(text)
            result["page_types"][pno] = pt
            result["page_classifications"].append({
                "page_number": pno,
                "page_type":   pt,
                "label_lt":    _PAGE_TYPE_LABELS_LT.get(pt, "Kita"),
                "confidence":  conf,
            })

            # Project name from cover/first pages
            if pno <= 3 and not result["projektas"]:
                for line in text.splitlines():
                    line = line.strip()
                    if re.search(r'g\.\s*\d+|al\.\s*\d+|interjero\s+projektas', line, re.I):
                        if 5 < len(line) < 80:
                            result["projektas"] = line
                            break

            # Room list — try every page until found
            if not result["patalpos"]:
                rooms = _extract_eksplikacija(text)
                if len(rooms) >= 3:   # need at least 3 rooms to trust extraction
                    result["patalpos"] = rooms

            # Ceiling heights
            if pt == "lubų":
                result["ceiling_heights"].update(_extract_ceiling_heights(text))

            # Floor materials
            if pt == "grindų":
                mats = _extract_floor_materials(text)
                if mats:
                    result["floor_materials"] = mats

    return result


def _pdf_to_images(pdf_bytes: bytes, dpi: int = 200) -> list[tuple[int, str]]:
    """
    Convert each PDF page to a base64 JPEG string.
    Returns [(1-based page_num, base64_str), ...].
    Requires poppler (pdftoppm).
    """
    from pdf2image import convert_from_bytes
    images = convert_from_bytes(pdf_bytes, dpi=dpi, fmt="jpeg")
    result = []
    for i, img in enumerate(images):
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        result.append((i + 1, b64))
    return result


def _call_vision(b64_image: str, prompt: str) -> str:
    """Send a base64 JPEG + prompt to Claude Vision. Returns raw text."""
    msg = client.messages.create(
        model=VISION_MODEL,
        max_tokens=4096,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": b64_image,
                    },
                },
                {"type": "text", "text": prompt},
            ],
        }],
    )
    return msg.content[0].text


def _parse_json_safe(text: str) -> dict | list | None:
    text = text.strip()
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```\s*$', '', text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r'\{[\s\S]*\}|\[[\s\S]*\]', text)
        if m:
            try:
                return json.loads(m.group())
            except Exception:
                pass
    return None


def _apply_vision_result(rooms_by_nr: dict, vr: dict) -> None:
    page_type = vr.get("type", "")
    data = _parse_json_safe(vr.get("raw", ""))
    if not data or not isinstance(data, dict):
        return

    if page_type == "pertvarų":
        for r in data.get("patalpos", []):
            nr = str(r.get("nr", ""))
            if nr and nr not in rooms_by_nr:
                rooms_by_nr[nr] = {
                    "nr": nr,
                    "pavadinimas": r.get("pavadinimas", ""),
                    "plotas_m2": r.get("plotas_m2"),
                }
        meta = rooms_by_nr.setdefault("__meta__", {})
        if data.get("visu_kampu_vnt") is not None:
            meta["visu_kampu_vnt"] = int(data["visu_kampu_vnt"])
        if data.get("isoriniu_kampu_vnt") is not None:
            meta["isoriniu_kampu_vnt"] = int(data["isoriniu_kampu_vnt"])
        if data.get("isoriniu_kampai"):
            meta["isoriniu_kampai"] = data["isoriniu_kampai"]
        if data.get("doors"):
            meta["doors"] = data["doors"]
        if data.get("room_perimeters_without_iskl"):
            meta["room_perimeters_without_iskl"] = data["room_perimeters_without_iskl"]

    elif page_type == "santechnikos":
        rooms_by_nr["__santechnika__"] = {
            k: v for k, v in data.items()
            if isinstance(v, (int, float)) and v >= 0
        }

    elif page_type == "rozecių":
        rooms_by_nr["__elektra__"] = {
            k: v for k, v in data.items()
            if isinstance(v, (int, float)) and v >= 0
        }

    elif page_type == "apšvietimo":
        rooms_by_nr["__apsvietimas__"] = {
            k: v for k, v in data.items()
            if isinstance(v, (int, float)) and v >= 0
        }

    elif page_type == "lubų":
        for r in data.get("patalpos", []):
            nr = str(r.get("nr", ""))
            if nr in rooms_by_nr:
                if r.get("lubu_aukstis_mm"):
                    rooms_by_nr[nr].setdefault("lubu_aukstis_mm", r["lubu_aukstis_mm"])
                if r.get("lubu_tipas"):
                    rooms_by_nr[nr]["lubu_tipas"] = r["lubu_tipas"]
                if r.get("led_nisa") is not None:
                    rooms_by_nr[nr]["led_nisa"] = r["led_nisa"]
                if r.get("uzuolaidu_nisa") is not None:
                    rooms_by_nr[nr]["uzuolaidu_nisa"] = r["uzuolaidu_nisa"]
        meta = rooms_by_nr.setdefault("__meta__", {})
        if data.get("led_nisu_total_m") is not None:
            meta["led_nisu_m"] = data["led_nisu_total_m"]
        if data.get("gkp_dezuciu_m") is not None:
            meta["gkp_dezuciu_m"] = data["gkp_dezuciu_m"]
        # Curtain niches — new format uses "curtain_niches" key with length_mm per niche
        niches = data.get("curtain_niches") or data.get("uzuolaidu_nisos") or []
        if niches:
            meta["uzuolaidu_nisos_details"] = niches
            # Sum all per-niche lengths (key is length_mm or ilgis_mm)
            total_mm = sum(
                (n.get("length_mm") or n.get("ilgis_mm") or 0)
                for n in niches if isinstance(n, dict)
            )
            if total_mm > 0:
                meta["uzuolaidu_nisu_m"] = round(total_mm / 1000, 2)
        # Flat total fallback (old prompt format)
        flat = data.get("total_curtain_niches_m") or data.get("uzuolaidu_nisu_total_m")
        if flat is not None and not meta.get("uzuolaidu_nisu_m"):
            meta["uzuolaidu_nisu_m"] = flat
        # LED niches — may now be structured {"LD-1": {"total_m": 15}, ...}
        led_niches = data.get("led_niches")
        if isinstance(led_niches, dict):
            total_led = sum(
                v.get("total_m", 0) if isinstance(v, dict) else v
                for v in led_niches.values()
            )
            meta["led_nisu_m"] = round(total_led, 1)

    elif page_type == "grindų":
        for zone in data.get("grindų_zonos", []):
            medžiaga = zone.get("medžiaga") or zone.get("tipas", "")
            for nr in zone.get("patalpos_nr", []):
                nr = str(nr)
                if nr in rooms_by_nr:
                    rooms_by_nr[nr]["grindu_danga"] = medžiaga
        meta = rooms_by_nr.setdefault("__meta__", {})
        if data.get("grindjuostes_m"):
            meta["grindjuostes_m"] = data["grindjuostes_m"]
        if data.get("grindų_zonos"):
            meta.setdefault("grindų_zonos", []).extend(data["grindų_zonos"])

    elif page_type == "apdailų":
        for zone in data.get("sienu_zonos", []):
            nr = str(zone.get("patalpas_nr", ""))
            if nr in rooms_by_nr:
                rooms_by_nr[nr].setdefault("sienu_apdaila", []).append({
                    "kodas": zone.get("kodas"),
                    "tipas": zone.get("apdaila"),
                })

    elif page_type == "išklotinė":
        sections = data.get("wall_sections") or data.get("sienu_sekcijos", [])
        for sec in sections:
            kodas = sec.get("id") or sec.get("kodas", "")
            if not kodas:
                continue

            # Normalize zone/finish list — support both key names
            items = sec.get("zones") or sec.get("finishes", [])
            sec = dict(sec)           # shallow copy so we can normalise in-place
            sec["zones"] = items      # always store as "zones"

            # Infer room_nr if Vision didn't provide it
            if not sec.get("room_nr"):
                letter = kodas[0].lower() if kodas else ""
                inferred = _ROOM_LETTER_MAP.get(letter, "")
                if inferred:
                    sec["room_nr"] = inferred

            rooms_by_nr.setdefault("__sekcijos__", {})[kodas] = sec

            # Accumulate finish areas into __meta__.sienu_apdaila (for backward compat)
            meta = rooms_by_nr.setdefault("__meta__", {})
            finish_totals = meta.setdefault("sienu_apdaila", {})
            for f in items:
                ftype = (f.get("type") or "").strip()
                farea = f.get("area_m2") or 0
                if ftype and farea > 0:
                    finish_totals[ftype] = round(
                        finish_totals.get(ftype, 0) + farea, 3
                    )


_NON_PAINT_KEYS = ("plytel", "plokšt", "medž", "tekst", "tapetai", "bald", "veidrod")


def _zone_category(ztype: str) -> str:
    t = ztype.lower()
    if "daž" in t:
        return "paint"
    if "plytel" in t:
        return "tiles"
    if any(k in t for k in _NON_PAINT_KEYS):
        return "panel"
    return "other"


_Q_RATES = {'Q1': 0.8, 'Q2': 1.0, 'Q3': 1.2, 'Q4': 1.5}
_Q_THICK = {'Q1': 1.2, 'Q2': 1.25, 'Q3': 1.75, 'Q4': 2.5}


def _calculate_finishing_quantities(
    final_rooms: list,
    sekcijos: dict,
    meta: dict,
    sienu_apdaila: dict,
    sienos_storis_m: float = 0.10,
    glaistimo_lygis: str = 'Q2',
    gk_metodas: str = 'tikslus',   # Task 9: 'tikslus' or 'praktinis'
) -> dict:
    """
    Calculate the 5 key finishing contractor quantities.

    DAŽOMAS PLOTAS algorithm:
    - Rooms WITH wall sections (išklotinės): gross = Σ(w×h) per section;
      subtract tiles, panels, openings. Use explicit 'dažymas' zone sum
      if Vision provided it, otherwise use gross−non_paint−openings.
    - Rooms WITHOUT sections (e.g. 101, 103, 105): estimate perimeter from
      partition plan data or 4.1√area; subtract door areas.
    """
    # Group sections by room_nr (Vision-provided or letter-prefix fallback)
    sections_by_room: dict[str, list] = defaultdict(list)
    for kodas, sec in sekcijos.items():
        room_nr = sec.get("room_nr") or ""
        if not room_nr:
            letter = kodas[0].lower() if kodas else ""
            room_nr = _ROOM_LETTER_MAP.get(letter, "")
        if room_nr:
            sections_by_room[room_nr].append(sec)

    # ── 1. DAŽOMAS PLOTAS ────────────────────────────────────────────────────
    paint_walls_m2 = 0.0
    tiles_m2       = 0.0
    panels_m2      = 0.0

    for room in final_rooms:
        nr   = room["nr"]
        h_mm = room.get("lubu_aukstis_mm") or 2800
        h_m  = h_mm / 1000
        a_m2 = room.get("plotas_m2") or 0
        sections = sections_by_room.get(nr, [])

        if sections:
            room_gross    = 0.0
            room_paint    = 0.0
            room_tiles    = 0.0
            room_panels   = 0.0
            room_openings = 0.0

            for sec in sections:
                w_mm   = sec.get("width_mm")  or 0
                s_h_mm = sec.get("height_mm") or h_mm
                room_gross += (w_mm * s_h_mm) / 1_000_000

                items = sec.get("zones") or sec.get("finishes", [])
                for z in items:
                    ztype = (z.get("type") or "").strip()
                    zarea = z.get("area_m2") or 0
                    if not ztype or zarea <= 0:
                        continue
                    cat = _zone_category(ztype)
                    if cat == "paint":
                        room_paint  += zarea
                    elif cat == "tiles":
                        room_tiles  += zarea
                    elif cat == "panel":
                        room_panels += zarea

                for opening in (sec.get("openings") or []):
                    ow = (opening.get("width_mm")  or 0)    / 1000
                    oh = (opening.get("height_mm") or h_mm) / 1000
                    room_openings += ow * oh

            # Prefer explicit dažymas zones; fall back to gross-minus-other
            if room_paint > 0:
                room_dazymas = room_paint
            else:
                room_dazymas = max(0.0, room_gross - room_tiles - room_panels - room_openings)

            paint_walls_m2 += room_dazymas
            tiles_m2       += room_tiles
            panels_m2      += room_panels

        else:
            # No sections → 100% painted; estimate perimeter
            perims = meta.get("room_perimeters_without_iskl", {})
            if nr in perims:
                perim_m = (perims[nr].get("estimated_perimeter_mm") or 0) / 1000
            else:
                perim_m = 4.1 * (a_m2 ** 0.5) if a_m2 > 0 else 0

            door_area = sum(
                (d.get("width_mm") or 900) / 1000 * (d.get("height_mm") or h_mm) / 1000
                for d in (meta.get("doors") or [])
                if nr in (d.get("between") or [])
            )
            paint_walls_m2 += max(0.0, perim_m * h_m - door_area)

    lubos_m2 = round(sum(r.get("plotas_m2") or 0 for r in final_rooms), 2)

    # ── 2. GLAISTYMO KAMPAI ──────────────────────────────────────────────────
    # Prefer visu_kampu_vnt (all corners) extracted by Vision from the floor plan.
    # Fall back to outer-corners × 3.5 heuristic (ratio derived from 5 real projects).
    # Last resort: ratio of 0.70 m per m² of total paintable area (training-data average).
    visu_kampai_vnt  = meta.get("visu_kampu_vnt", 0) or 0
    isoriniu_kampai_vnt = meta.get("isoriniu_kampu_vnt", 0) or 0
    avg_h = (
        sum(r.get("lubu_aukstis_mm", 2800) for r in final_rooms) / len(final_rooms) / 1000
        if final_rooms else 2.8
    )
    if visu_kampai_vnt > 0:
        kampai_vnt = visu_kampai_vnt
        kampai_source = "vision_total"
    elif isoriniu_kampai_vnt > 0:
        kampai_vnt = round(isoriniu_kampai_vnt * 3.5)
        kampai_source = "outer_x3.5"
    else:
        # Estimate from paintable area: 0.70 m kampų per m² (training-data average)
        dazymas_total_m2 = paint_walls_m2 + lubos_m2
        kampai_vnt = round(dazymas_total_m2 * 0.70 / avg_h) if avg_h > 0 else 0
        kampai_source = "ratio_estimate"
    kampai_m = round(kampai_vnt * avg_h, 1)

    # ── 3. ANGOKRAŠČIAI ──────────────────────────────────────────────────────
    # WINDOWS: use section openings from wall elevations (exact dimensions)
    # DOORS: use meta["doors"] from partition plan (comprehensive list)
    langu_vnt      = 0
    duru_vnt       = 0
    angokrasciai_m = 0.0
    angokrasciai_details: list[dict] = []

    for sec in sekcijos.values():
        for opening in (sec.get("openings") or []):
            tip = (opening.get("type") or "").lower()
            if "lang" not in tip:
                continue  # doors handled via meta["doors"] below
            h = (opening.get("height_mm") or 1400) / 1000
            w = (opening.get("width_mm")  or 1200) / 1000
            perim = 2 * h + w
            angokrasciai_m += perim
            langu_vnt += 1
            angokrasciai_details.append({
                "tipas":        "langas",
                "plotis_m":     round(w, 2),
                "aukstis_m":    round(h, 2),
                "perimetras_m": round(perim, 2),
            })

    meta_doors = meta.get("doors") or []
    if meta_doors:
        # Partition plan is the authoritative source for ALL doors
        for d in meta_doors:
            dh = (d.get("height_mm") or 2200) / 1000
            dw = (d.get("width_mm")  or  900) / 1000
            perim = 2 * dh + dw
            angokrasciai_m += perim
            duru_vnt += 1
            angokrasciai_details.append({
                "tipas":        "durys",
                "plotis_m":     round(dw, 2),
                "aukstis_m":    round(dh, 2),
                "perimetras_m": round(perim, 2),
            })
    else:
        # Fallback: extract doors from section openings if partition plan had none
        for sec in sekcijos.values():
            for opening in (sec.get("openings") or []):
                tip = (opening.get("type") or "").lower()
                if "lang" in tip:
                    continue  # already counted as window above
                h = (opening.get("height_mm") or 2200) / 1000
                w = (opening.get("width_mm")  or  900) / 1000
                perim = 2 * h + w
                angokrasciai_m += perim
                duru_vnt += 1
                angokrasciai_details.append({
                    "tipas":        "durys",
                    "plotis_m":     round(w, 2),
                    "aukstis_m":    round(h, 2),
                    "perimetras_m": round(perim, 2),
                })

    # ── 4. LUBŲ PERIMETRAS ───────────────────────────────────────────────────
    lubu_perimetras_m = 0.0
    for room in final_rooms:
        nr = room["nr"]
        sections = sections_by_room.get(nr, [])
        if sections:
            perim_m = sum((s.get("width_mm") or 0) for s in sections) / 1000
        else:
            perims = meta.get("room_perimeters_without_iskl", {})
            if nr in perims:
                perim_m = (perims[nr].get("estimated_perimeter_mm") or 0) / 1000
            else:
                perim_m = 4.1 * ((room.get("plotas_m2") or 0) ** 0.5)
        lubu_perimetras_m += perim_m

    perimetras_src = "iš išklotinių matmenų" if sekcijos else "apytiksliai (4√plotas)"

    # ── 5. UŽUOLAIDŲ NIŠOS ───────────────────────────────────────────────────
    uzuolaidu_m       = meta.get("uzuolaidu_nisu_m", 0) or 0
    uzuolaidu_details = meta.get("uzuolaidu_nisos_details", [])

    # ── 6. GRINDJUOSTĖS ──────────────────────────────────────────────────────
    grindjuostes_m = 0.0
    for room in final_rooms:
        nr = room["nr"]
        sections = sections_by_room.get(nr, [])
        if sections:
            perim_m = sum((s.get("width_mm") or 0) for s in sections) / 1000
        else:
            perims = meta.get("room_perimeters_without_iskl", {})
            if nr in perims:
                perim_m = (perims[nr].get("estimated_perimeter_mm") or 0) / 1000
            else:
                perim_m = 4.1 * ((room.get("plotas_m2") or 0) ** 0.5)
        door_widths = sum(
            (d.get("width_mm") or 900) / 1000
            for d in (meta.get("doors") or [])
            if nr in (d.get("between") or [])
        )
        grindjuostes_m += max(0.0, perim_m - door_widths)

    # ── 7. ANGOKRAŠČIŲ PLOTAS (sienos_storis) ────────────────────────────────
    angokrasciai_area_m2 = round(angokrasciai_m * sienos_storis_m, 2)

    # ── 8. DAŽŲ KIEKIS (litrais) ─────────────────────────────────────────────
    dazymas_viso_m2  = paint_walls_m2 + lubos_m2
    dazai_sienoms_l  = round(paint_walls_m2 * 2 / 9, 1)
    dazai_luboms_l   = round(lubos_m2 * 2 / 10, 1)
    gruntas_l        = round(dazymas_viso_m2 * 0.15, 1)

    # ── 9. GK LAPAI ──────────────────────────────────────────────────────────
    # Task 9: tikslus = deduct openings; praktinis = full perimeter (no deductions)
    if gk_metodas == 'praktinis':
        gk_base_m2 = 0.0
        for room in final_rooms:
            nr = room["nr"]
            sections = sections_by_room.get(nr, [])
            if sections:
                h_mm = room.get("lubu_aukstis_mm") or 2800
                for sec in sections:
                    w_mm   = sec.get("width_mm") or 0
                    s_h_mm = sec.get("height_mm") or h_mm
                    gk_base_m2 += (w_mm * s_h_mm) / 1_000_000
            else:
                perims = meta.get("room_perimeters_without_iskl", {})
                h_m = (room.get("lubu_aukstis_mm") or 2800) / 1000
                if nr in perims:
                    perim_m = (perims[nr].get("estimated_perimeter_mm") or 0) / 1000
                else:
                    a_m2 = room.get("plotas_m2") or 0
                    perim_m = 4.1 * (a_m2 ** 0.5) if a_m2 > 0 else 0
                gk_base_m2 += perim_m * h_m
        gk_lapai_vnt = math.ceil(gk_base_m2 / 3.0 * 1.1)
    else:
        gk_lapai_vnt = math.ceil(paint_walls_m2 / 3.0 * 1.1)

    # ── 10. GLAISTO MIŠINYS ──────────────────────────────────────────────────
    q_rate   = _Q_RATES.get(glaistimo_lygis, 1.0)
    q_thick  = _Q_THICK.get(glaistimo_lygis, 1.25)
    glaistas_kg    = round(dazymas_viso_m2 * q_thick * q_rate)
    glaisto_maisai = math.ceil(glaistas_kg / 25)

    # ── VALIDATION NOTES ─────────────────────────────────────────────────────
    validation_notes = []
    if lubos_m2 > 0:
        ratio = paint_walls_m2 / lubos_m2
        if ratio < 2.0:
            validation_notes.append(f"Patikrink: sienų/lubų santykis = {ratio:.1f}× (norma: 2.5–4×) — gali būti per mažas dažomas plotas")
        elif ratio > 5.0:
            validation_notes.append(f"Patikrink: sienų/lubų santykis = {ratio:.1f}× (norma: 2.5–4×) — gali būti per didelis dažomas plotas")

    # ── Task 5: CONFIDENCE LEVELS ────────────────────────────────────────────
    # high = read directly from drawings; medium = calculated from partial data; low = fallback
    has_sections   = bool(sekcijos)
    has_meta_doors = bool(meta.get("doors"))
    windows_found  = langu_vnt > 0
    has_corners    = kampai_vnt > 0

    conf_dazomas   = "high"   if has_sections   else ("medium" if meta.get("room_perimeters_without_iskl") else "low")
    conf_kampai    = "high"   if kampai_source == "vision_total" else ("medium" if kampai_source == "outer_x3.5" else "low")
    conf_angokr    = "high"   if (has_sections and windows_found) else ("medium" if (has_meta_doors and windows_found) else "low")
    conf_lubos_per = "high"   if has_sections   else ("medium" if meta.get("room_perimeters_without_iskl") else "low")
    conf_grindjus  = conf_lubos_per
    conf_dazai     = "medium" if has_sections   else "low"

    return {
        "dazomas_plotas": {
            "sienos_m2":  round(paint_walls_m2, 1),
            "lubos_m2":   lubos_m2,
            "viso_m2":    round(paint_walls_m2 + lubos_m2, 1),
            "confidence": conf_dazomas,
            "pastaba": (
                "Bruto atėmus plytelių/plokščių/angų zonas (iš išklotinių matmenų)"
                if sekcijos else
                "Apytiksliai — trūksta išklotinių"
            ),
        },
        "plyteles_m2":  round(tiles_m2, 1),
        "plokstes_m2":  round(panels_m2, 1),
        "glaistymo_kampai": {
            "kampai_vnt":          kampai_vnt,
            "isoriniu_kampu_vnt":  isoriniu_kampai_vnt,
            "vidutinis_aukstis_m": round(avg_h, 2),
            "viso_m":              kampai_m,
            "confidence":          conf_kampai,
            "skaiciavimo_budas":   kampai_source,
        },
        "angokrasciai": {
            "langu_vnt":  langu_vnt,
            "duru_vnt":   duru_vnt,
            "viso_m":     round(angokrasciai_m, 1),
            "viso_m_x2":  round(angokrasciai_m * 2, 1),
            "area_m2":    angokrasciai_area_m2,
            "details":    angokrasciai_details,
            "confidence": conf_angokr,
        },
        "lubu_perimetras": {
            "viso_m":            round(lubu_perimetras_m, 1),
            "skaiciavimo_budas": perimetras_src,
            "confidence":        conf_lubos_per,
        },
        "uzuolaidu_nisos": {
            "viso_m":     round(uzuolaidu_m, 1),
            "details":    uzuolaidu_details,
            "confidence": "high" if uzuolaidu_details else "low",
        },
        "grindjuostes": {
            "viso_m":     round(grindjuostes_m, 1),
            "confidence": conf_grindjus,
        },
        "dazai": {
            "sienos_l":   dazai_sienoms_l,
            "lubos_l":    dazai_luboms_l,
            "gruntas_l":  gruntas_l,
            "viso_l":     round(dazai_sienoms_l + dazai_luboms_l + gruntas_l, 1),
            "confidence": conf_dazai,
        },
        "gk_lapai": {
            "vnt":        gk_lapai_vnt,
            "metodas":    gk_metodas,
            "confidence": "medium" if has_sections else "low",
        },
        "glaistas": {
            "lygis":       glaistimo_lygis,
            "kg":          int(glaistas_kg),
            "maisai_25kg": glaisto_maisai,
            "confidence":  "medium",
        },
        "validation_notes": validation_notes,
    }


def _merge_interior_results(text_data: dict, vision_results: list[dict]) -> dict:
    patalpos = text_data.get("patalpos", [])
    heights  = text_data.get("ceiling_heights", {})

    rooms_by_nr: dict[str, dict] = {}
    for r in patalpos:
        rooms_by_nr[r["nr"]] = dict(r)

    for nr, ht in heights.items():
        if nr in rooms_by_nr:
            rooms_by_nr[nr]["lubu_aukstis_mm"] = ht

    type_order = [
        "pertvarų", "lubų", "grindų", "apdailų", "išklotinė",
        "santechnikos", "rozecių", "apšvietimo",
    ]
    vision_sorted = sorted(
        vision_results,
        key=lambda v: type_order.index(v["type"]) if v["type"] in type_order else 99,
    )
    for vr in vision_sorted:
        _apply_vision_result(rooms_by_nr, vr)

    meta        = rooms_by_nr.pop("__meta__", {})
    sekcijos    = rooms_by_nr.pop("__sekcijos__", {})
    santechnika = rooms_by_nr.pop("__santechnika__", {})
    elektra     = rooms_by_nr.pop("__elektra__", {})
    apsvietimas = rooms_by_nr.pop("__apsvietimas__", {})

    # If text extraction found no rooms but Vision did (image-based PDFs), promote
    # Vision-extracted rooms to the patalpos list so they appear in final_rooms.
    if not patalpos and rooms_by_nr:
        patalpos = [
            {"nr": nr, "pavadinimas": r.get("pavadinimas", ""), "plotas_m2": r.get("plotas_m2")}
            for nr, r in sorted(rooms_by_nr.items())
            if not nr.startswith("__") and (r.get("nr") or r.get("plotas_m2"))
        ]

    # Last resort: if still no rooms but sekcijos (wall sections) exist, infer rooms
    # from the section room_nr values so at least dažomas plotas is calculated correctly.
    if not patalpos and sekcijos:
        seen: dict[str, dict] = {}
        for sec in sekcijos.values():
            nr = sec.get("room_nr", "")
            if not nr or nr in seen:
                continue
            seen[nr] = {"nr": nr, "pavadinimas": f"Patalpa {nr}", "plotas_m2": None}
        # Estimate floor area from accumulated section perimeters (sum of wall widths / 4)²
        perim_by_room: dict[str, float] = {}
        for sec in sekcijos.values():
            nr = sec.get("room_nr", "")
            if nr:
                perim_by_room[nr] = perim_by_room.get(nr, 0) + (sec.get("width_mm") or 0)
        for nr, r in seen.items():
            perim_m = perim_by_room.get(nr, 0) / 1000
            if perim_m > 0:
                r["plotas_m2"] = round((perim_m / 4) ** 2, 1)
        patalpos = sorted(seen.values(), key=lambda x: x["nr"])
        for r in patalpos:
            rooms_by_nr.setdefault(r["nr"], {}).update(r)

    # Build final room list
    final_rooms = []
    for r in patalpos:
        nr   = r["nr"]
        room = rooms_by_nr.get(nr, dict(r))
        room.setdefault("lubu_aukstis_mm", 2800)
        room.setdefault("lubu_tipas", None)
        room.setdefault("grindu_danga", None)
        room.setdefault("grindu_plotas_m2", room.get("plotas_m2"))
        room.setdefault("sienu_apdaila", [])
        final_rooms.append(room)

    total_plotas = sum(r.get("plotas_m2") or 0 for r in final_rooms)
    uses_vision  = bool(vision_results)

    # ── Wall finish totals from IŠKLOTINĖS ───────────────────────────────────
    sienu_apdaila: dict[str, float] = meta.get("sienu_apdaila", {})

    # Fallback: approximate from room geometry when no elevation drawings
    if not sienu_apdaila:
        sienu_dazymas = 0.0
        sienu_plyteles = 0.0
        for room in final_rooms:
            a = room.get("plotas_m2") or 0
            h = (room.get("lubu_aukstis_mm") or 2800) / 1000
            perim = 4 * (a ** 0.5) if a > 0 else 0
            wall_total = perim * h
            apdaila_list = room.get("sienu_apdaila", [])
            if apdaila_list:
                paint_z = sum(1 for x in apdaila_list if "daž" in (x.get("tipas") or "").lower())
                tile_z  = sum(1 for x in apdaila_list if "plytel" in (x.get("tipas") or "").lower())
                total_z = len(apdaila_list) or 1
                sienu_dazymas  += wall_total * (paint_z / total_z)
                sienu_plyteles += wall_total * (tile_z  / total_z)
            else:
                sienu_dazymas += wall_total
        sienu_apdaila = {"dažymas": round(sienu_dazymas, 1)}
        if sienu_plyteles > 0:
            sienu_apdaila["plytelės"] = round(sienu_plyteles, 1)
    else:
        sienu_apdaila = {k: round(v, 2) for k, v in sienu_apdaila.items()}

    # ── Ceiling ───────────────────────────────────────────────────────────────
    gkp_rooms   = [r for r in final_rooms if (r.get("lubu_tipas") or "").upper() == "GKP"]
    lubu_gkp_m2 = round(sum(r.get("plotas_m2") or 0 for r in gkp_rooms), 2)

    lubu_data = {
        "gkp_m2":              lubu_gkp_m2 or None,
        "led_nisu_m":          meta.get("led_nisu_m"),
        "uzuolaidu_nisu_m":    meta.get("uzuolaidu_nisu_m"),
        "gkp_dezuciu_m":       meta.get("gkp_dezuciu_m"),
    }

    # ── Floors ────────────────────────────────────────────────────────────────
    floor_zones = meta.get("grindų_zonos", [])
    floor_materials_structured = []
    for zone in floor_zones:
        floor_materials_structured.append({
            "medžiaga":  zone.get("medžiaga", ""),
            "plotas_m2": zone.get("plotas_m2"),
            "kiekis_vnt": zone.get("kiekis_vnt"),
            "patalpos":  zone.get("patalpos_nr", []),
        })

    parketlentes_m2 = sum(
        z.get("plotas_m2") or 0 for z in floor_zones
        if "parket" in z.get("medžiaga", "").lower()
    ) or None

    grindys = {
        "medžiagos":      floor_materials_structured,
        "grindjuostes_m": meta.get("grindjuostes_m"),
        "parketlentes_m2": parketlentes_m2,
    }

    # ── Task 2: HIDROIZOLIACIJA ───────────────────────────────────────────────
    # Detect wet rooms by name keywords
    _WET_ROOM_KW = ("vonia", "vonios", "wc", "tualetas", "dušas", "dušo",
                    "higien", "skalbykla", "skalbimo", "bathrom", "toilet", "shower")
    wet_rooms = [
        r for r in final_rooms
        if any(k in (r.get("pavadinimas") or "").lower() for k in _WET_ROOM_KW)
    ]
    hidro_grindys_m2    = round(sum(r.get("plotas_m2") or 0 for r in wet_rooms), 2)
    hidro_sienos_m2     = 0.0
    hidro_perimetras_m  = 0.0
    for r in wet_rooms:
        a = r.get("plotas_m2") or 0
        perim_m = 4 * (a ** 0.5) if a > 0 else 0
        # splash zone 0.30 m height (non-shower walls)
        hidro_sienos_m2    += round(perim_m * 0.30, 2)
        hidro_perimetras_m += perim_m
    # Check if any shower found from santechnika
    has_shower = (santechnika.get("duso_sistemos_vnt") or 0) > 0
    hidro_dus_zona_m2 = 0.0
    if has_shower:
        dus_vnt = santechnika.get("duso_sistemos_vnt", 1)
        avg_wet_h = (
            sum((r.get("lubu_aukstis_mm") or 2800) for r in wet_rooms) / max(len(wet_rooms), 1) / 1000
            if wet_rooms else 2.8
        )
        # Typical shower zone: 1.0×1.0 m perimeter = 4 m × ceiling height
        hidro_dus_zona_m2 = round(dus_vnt * 4.0 * avg_wet_h, 1)

    hidroizoliacija = {
        "grindys_m2":       hidro_grindys_m2 or None,
        "sienos_m2":        round(hidro_sienos_m2 + hidro_dus_zona_m2, 2) or None,
        "juosta_m":         round(hidro_perimetras_m, 1) or None,
        "membrana_kg":      round((hidro_grindys_m2 + hidro_sienos_m2 + hidro_dus_zona_m2) * 1.5 * 2, 1) or None,
        "dregnas_patalpos": [r.get("pavadinimas", "") for r in wet_rooms],
    } if wet_rooms else {}

    # ── samatos_kiekiai — flat totals matching xlsx template ──────────────────
    total_dazymas  = sienu_apdaila.get("dažymas", 0) or 0
    total_plyteles = sum(v for k, v in sienu_apdaila.items() if "plytel" in k.lower())

    samatos_kiekiai = {
        "gkp_lubos_m2":           lubu_gkp_m2 or None,
        "gkp_dezutes_m":          meta.get("gkp_dezuciu_m"),
        "led_nisos_m":            meta.get("led_nisu_m"),
        "uzuolaidu_nisos_m":      meta.get("uzuolaidu_nisu_m"),
        "dazymas_m2":             round(total_dazymas, 1)  if total_dazymas  else None,
        "plyteles_m2":            round(total_plyteles, 1) if total_plyteles else None,
        "grindys_parketlentes_m2": parketlentes_m2,
        "grindjuostes_m":         meta.get("grindjuostes_m"),
        "rozetes_vnt":            elektra.get("rozetes_vnt"),
        "jungikliai_vnt":         elektra.get("jungikliai_vnt"),
        "interneto_rozetes_vnt":  elektra.get("interneto_rozetes_vnt"),
        "termostatai_vnt":        elektra.get("termostatai_vnt"),
        "ileidziami_sviestuvai_vnt": apsvietimas.get("ileidziami_sviestuvai_vnt"),
        "pakabinami_sviestuvai_vnt": apsvietimas.get("pakabinami_sviestuvai_vnt"),
        "sieniniai_sviestuvai_vnt":  apsvietimas.get("sieniniai_sviestuvai_vnt"),
        "led_juostos_m":          apsvietimas.get("led_juostos_m"),
        "wc_remai_vnt":           santechnika.get("wc_remai_vnt"),
        "duso_sistemos_vnt":      santechnika.get("duso_sistemos_vnt"),
        "kondicionieriai_vnt":    santechnika.get("kondicionieriai_vnt"),
    }

    # ── Notes ─────────────────────────────────────────────────────────────────
    pastabos = ["Patalpų plotai — iš patalpų eksplikacijos"]
    if heights:
        pastabos.append("Lubų aukščiai — iš teksto analizės")
    else:
        pastabos.append("Lubų aukščiai — numatytasis 2800 mm (nepavyko išskirti)")
    if sekcijos:
        pastabos.append(f"Sienų plotai — iš {len(sekcijos)} išklotinių sekcijų (tikslūs matmenys)")
    elif uses_vision:
        pastabos.append("Sienų plotai — apytiksliai (išklotinės neanalizuotos)")
    else:
        pastabos.append("Sienų plotai — apytiksliai (formulė: 4√plotas × aukštis)")
    if not uses_vision:
        pastabos.append("Vizualinė analizė nebuvo atlikta (poppler neįdiegtas)")

    confidence = "high" if sekcijos else ("medium" if uses_vision else "low")

    # Default assumptions
    SIENOS_STORIS_M = 0.10
    GLAISTIMO_LYGIS = 'Q2'

    # ── Finishing contractor calculations (all key quantities) ────────────────
    skaiciavimai = _calculate_finishing_quantities(
        final_rooms, sekcijos, meta, sienu_apdaila,
        sienos_storis_m=SIENOS_STORIS_M,
        glaistimo_lygis=GLAISTIMO_LYGIS,
    )

    # ── Window fallback — Task 10: niches → standard ─────────────────────────
    langai_fallback = skaiciavimai.get("angokrasciai", {}).get("langu_vnt", 0) == 0
    suggested_windows: list[dict] = []
    langai_source = "drawings"   # will update if fallback used

    if langai_fallback:
        # Step 1: try to derive windows from curtain niches (Task 10)
        niche_details = meta.get("uzuolaidu_nisos_details", [])
        if niche_details:
            for niche in niche_details:
                if not isinstance(niche, dict):
                    continue
                niche_mm = niche.get("length_mm") or niche.get("ilgis_mm") or 0
                if niche_mm <= 0:
                    continue
                # Window width = niche width − 400 mm (200 mm each side overhang)
                win_w = max(int(niche_mm) - 400, 600)
                room_nr  = niche.get("room") or niche.get("room_nr", "")
                patalpa  = ""
                if room_nr:
                    found = next((r for r in final_rooms if r["nr"] == str(room_nr)), None)
                    patalpa = found.get("pavadinimas", "") if found else ""
                suggested_windows.append({
                    "width_mm":  win_w,
                    "height_mm": 1500,
                    "room_nr":   str(room_nr) if room_nr else "",
                    "patalpa":   patalpa,
                    "suggested": True,
                    "source":    "uzuolaidu_nisa",
                })
            if suggested_windows:
                langai_source = "niches"
                pastabos.append(
                    "⚠ Langai nerasti išklotinėse — panaudotos užuolaidų nišos langų skaičiui nustatyti. "
                    "Patikrink prielaidų skyriuje."
                )

        # Step 2: room-type fallback if niches also absent
        if not suggested_windows:
            _WINDOW_DEFAULTS = [
                (('miegam',),                           [{"width_mm": 1200, "height_mm": 1500}]),
                (('svetain', 'salon', 'bendra', 'gyv'), [{"width_mm": 1500, "height_mm": 1500},
                                                          {"width_mm": 1500, "height_mm": 1500}]),
                (('virtuv', 'kitchen'),                 [{"width_mm": 1200, "height_mm": 1500}]),
                (('darb', 'kabinet', 'studio', 'biur'), [{"width_mm": 1200, "height_mm": 1500}]),
            ]
            for room in final_rooms:
                name_lower = room.get("pavadinimas", "").lower()
                for keys, wins in _WINDOW_DEFAULTS:
                    if any(k in name_lower for k in keys):
                        for w in wins:
                            suggested_windows.append({
                                **w,
                                "room_nr":  room["nr"],
                                "patalpa":  room.get("pavadinimas", ""),
                                "suggested": True,
                                "source":   "room_type_default",
                            })
                        break
            if suggested_windows:
                langai_source = "room_defaults"
                pastabos.append(
                    "⚠ Langai nerasti brėžiniuose — pateikiami standartiniai pasiūlymai. "
                    "Patikrink prielaidų skyriuje ir pakoreguok."
                )

    # ── Task 6: FORGOTTEN ITEMS WARNINGS ────────────────────────────────────
    perspejimani: list[dict] = []
    has_wet = bool(wet_rooms)
    has_gk  = bool(gk_lapai := skaiciavimai.get("gk_lapai", {}).get("vnt", 0))
    has_led = bool(meta.get("led_nisu_m") or apsvietimas.get("led_juostos_m"))
    has_miegamasis = any(
        any(k in (r.get("pavadinimas") or "").lower() for k in ("miegam", "vaiku", "berniuk", "mergait", "bedroom"))
        for r in final_rooms
    )
    # Check if any wall longer than 8m (deformation joint warning)
    has_long_wall = any(
        any((s.get("width_mm") or 0) > 8000 for s in (sekcijos or {}).values())
        for _ in [True]
    )
    has_outer_corners = (meta.get("isoriniu_kampu_vnt") or 0) > 0

    if has_wet:
        perspejimani.append({
            "id": "hidroizoliacija",
            "tekstas": "Ar įtraukėte hidroizoliaciją drėgnoms patalpoms?",
            "kategorija": "kritiška",
            "patalpos": [r.get("pavadinimas") for r in wet_rooms],
        })
    perspejimani.append({
        "id": "gruntas",
        "tekstas": "Ar įtraukėte gruntavimą prieš dažymą?",
        "kategorija": "standartinė",
        "patalpos": [],
    })
    perspejimani.append({
        "id": "glaistimas",
        "tekstas": "Ar įtraukėte glaistymo darbus?",
        "kategorija": "standartinė",
        "patalpos": [],
    })
    if has_long_wall:
        perspejimani.append({
            "id": "deformacine_siule",
            "tekstas": "Ar įtraukėte deformacinę siūlę? (siena ilgesnė nei 8 m)",
            "kategorija": "techninė",
            "patalpos": [],
        })
    if has_outer_corners:
        perspejimani.append({
            "id": "kampu_profiliai",
            "tekstas": "Ar įtraukėte kampų profilius (angokraščiai, išoriniai kampai)?",
            "kategorija": "standartinė",
            "patalpos": [],
        })
    if has_gk:
        perspejimani.append({
            "id": "gk_sandarinimas",
            "tekstas": "Ar įtraukėte sandarinimo juostas GK plokščių sandūrose?",
            "kategorija": "standartinė",
            "patalpos": [],
        })
    if has_led:
        perspejimani.append({
            "id": "led_transformatoriai",
            "tekstas": "Ar numatėte LED juostų transformatorių vietas ir kiekius?",
            "kategorija": "techninė",
            "patalpos": [],
        })
    if has_miegamasis:
        perspejimani.append({
            "id": "gaisro_davikliai",
            "tekstas": "Ar įtraukėte gaisro detektorius miegamuosiuose?",
            "kategorija": "techninė",
            "patalpos": [],
        })

    # Additional material quantities for the contractor
    papildomi_kiekiai = {
        "plyteles_m2":         round(total_plyteles, 1) if total_plyteles else None,
        "parketlentes_m2":     parketlentes_m2,
        "grindjuostes_m":      skaiciavimai.get("grindjuostes", {}).get("viso_m") or meta.get("grindjuostes_m"),
        "led_juostos_m":       apsvietimas.get("led_juostos_m"),
        "gkp_lubos_m2":        lubu_gkp_m2 or None,
        "led_nisos_m":         meta.get("led_nisu_m"),
    }

    # ── Prielaidos (for frontend display and recalculation) ───────────────────
    prielaidos = {
        "lubu_aukstis_m":   round(
            sum(r.get("lubu_aukstis_mm", 2800) for r in final_rooms) / max(len(final_rooms), 1) / 1000, 2
        ),
        "sienos_storis_m":  SIENOS_STORIS_M,
        "glaistimo_lygis":  GLAISTIMO_LYGIS,
        "langai_fallback":  langai_fallback,
        "langai_source":    langai_source,    # Task 10: drawings/niches/room_defaults
        "langai_suggested": suggested_windows,
        "durys_vnt":        len(meta.get("doors") or []),
        "langai_vnt":       skaiciavimai.get("angokrasciai", {}).get("langu_vnt", 0),
    }

    # ── Raw calculation data (for frontend real-time recalculation) ───────────
    raw_calc_data = {
        "patalpos": final_rooms,
        "sekcijos": sekcijos,
        "meta": {
            "doors":                       meta.get("doors", []),
            "visu_kampu_vnt":              meta.get("visu_kampu_vnt", 0),
            "isoriniu_kampu_vnt":          meta.get("isoriniu_kampu_vnt", 0),
            "isoriniu_kampai":             meta.get("isoriniu_kampai", []),
            "room_perimeters_without_iskl": meta.get("room_perimeters_without_iskl", {}),
            "uzuolaidu_nisos_details":     meta.get("uzuolaidu_nisos_details", []),
            "uzuolaidu_nisu_m":            meta.get("uzuolaidu_nisu_m"),
            "led_nisu_m":                  meta.get("led_nisu_m"),
            "gkp_dezuciu_m":               meta.get("gkp_dezuciu_m"),
            "grindjuostes_m":              meta.get("grindjuostes_m"),
            "grindų_zonos":                meta.get("grindų_zonos", []),
        },
    }

    return {
        "projektas":       text_data.get("projektas") or "Interjero projektas",
        "tipas":           "interjeras",
        "patalpos":        final_rooms,
        "skaiciavimai":    skaiciavimai,
        "papildomi_kiekiai": papildomi_kiekiai,
        "sienu_apdaila":   sienu_apdaila,
        "lubu_data":       lubu_data,
        "grindys":         grindys,
        "elektra":         elektra,
        "santechnika":     santechnika,
        "apsvietimas":     apsvietimas,
        "samatos_kiekiai": samatos_kiekiai,
        "sienu_sekcijos":  sekcijos,
        "prielaidos":      prielaidos,
        "raw_calc_data":     raw_calc_data,
        "page_classifications": text_data.get("page_classifications", []),  # Task 1
        "hidroizoliacija":   hidroizoliacija,   # Task 2
        "perspejimani":      perspejimani,      # Task 6
        # backward-compat for old frontend
        "bendri_kiekiai": {
            "grindu_plotas_m2":       round(total_plotas, 2),
            "grindu_parketlentes_m2": parketlentes_m2,
            "grindu_plyteles_m2":     None,
            "grindjuostes_m":         meta.get("grindjuostes_m"),
            "lubu_plotas_m2":         round(lubu_gkp_m2 or total_plotas, 2),
            "sienu_dazymas_m2":       round(total_dazymas, 1)  if total_dazymas  else None,
            "sienu_plyteles_m2":      round(total_plyteles, 1) if total_plyteles else None,
            "duru_vnt":               None,
            "rozeciu_vnt":            elektra.get("rozetes_vnt"),
            "jungikliu_vnt":          elektra.get("jungikliai_vnt"),
        },
        "grindų_medziagos": text_data.get("floor_materials", []),
        "vizualine_analize": uses_vision,
        "confidence":       confidence,
        "pastabos":         pastabos,
    }


@app.post("/detect-type")
async def detect_type(file: UploadFile = File(...)):
    """Quick peek — classify PDF as 'kz', 'interior', or 'unknown'."""
    contents = await file.read()
    proj_type = await asyncio.to_thread(_detect_project_type, contents)
    return {"type": proj_type}


# ── TASK 7: KŽ row category detection ────────────────────────────────────────

_KZ_CATEGORY_KEYWORDS: list[tuple[str, list[str]]] = [
    ("ŽEMĖS DARBAI",         ["žemės", "iškasa", "tranšėja", "grunto", "planav", "supilim", "pjovim žemę"]),
    ("KONSTRUKCIJOS",        ["betona", "armatūr", "klojin", "mūro", "blokel", "sija", "kolona", "pamato", "pamatas", "monolitas"]),
    ("STOGO DARBAI",         ["stogo", "latai", "kraigo", "latakas", "lietvamzd", "stog", "čerpė", "skarda stog"]),
    ("FASADŲ DARBAI",        ["fasad", "izoliacij tinko", "etics", "smeig", "armavimo tinkl", "dekoratyvin tinkas", "cokolinis"]),
    ("INŽINERINIAI TINKLAI", ["vandentiek", "kanalizacij", "vamzd", "šildym", "elektr", "kabel", "instaliaci"]),
    ("VIDAUS APDAILA",       ["daž", "plytel", "parketas", "grindjuost", "gipskar", "glaist", "dažym", "tapetuot"]),
    ("GAMINIAI",             ["lang", "duri", "vort", "garaž", "rėm", "santech"]),
    ("GRIOVIMO DARBAI",      ["ardym", "griovim", "nugriovim", "išmontuot", "demontav"]),
    ("PASTOLIAI",            ["pastol", "scaffold"]),
]

def _detect_row_category(aprasymas: str, skyrius: str) -> str:
    text = (aprasymas + " " + skyrius).lower()
    for cat, kws in _KZ_CATEGORY_KEYWORDS:
        if any(kw in text for kw in kws):
            return cat
    return skyrius or "KITI DARBAI"


# ── TASK 6: New construction type modules ─────────────────────────────────────

_FACADE_PAGE_RE = re.compile(
    r'FASAD[AS]|PIETŲ FASAD|ŠIAURĖS FASAD|RYTŲ FASAD|VAKARŲ FASAD|PAGRINDINIS FASAD',
    re.I,
)

_FACADE_VISION_PROMPT = """\
You are analyzing a Lithuanian building facade elevation drawing (FASADAS).

Extract from this drawing:
1. FACADE LABEL: direction (Šiaurės/N, Pietų/S, Rytų/E, Vakarų/W) or label (A, B, etc.)
2. OVERALL DIMENSIONS from dimension lines: total width_mm and total height_mm
3. ALL WINDOWS: for each distinct size — width_mm, height_mm, count
4. ALL DOORS/ENTRANCES: width_mm, height_mm, count
5. BALCONIES or LOGGIAS: width_mm, height_mm, count
6. GABLE TRIANGLE if present: base_mm and height_mm

IMPORTANT: Read all numbers from dimension lines (arrows + numbers). If a dimension is not clearly readable, omit it.

Return ONLY valid JSON (no markdown):
{"label":"Pietų fasadas","width_mm":12500,"height_mm":8200,\
"windows":[{"width_mm":1200,"height_mm":1500,"count":4},{"width_mm":900,"height_mm":2100,"count":2}],\
"doors":[{"width_mm":1200,"height_mm":2200,"count":1}],\
"balconies":[{"width_mm":3000,"height_mm":2800,"count":1}],\
"gable_triangle":null}"""

_ROOF_PAGE_RE = re.compile(
    r'STOGO PLANAS|STOGO BRĖŽINYS|ROOF PLAN|STOGO PJŪVIS',
    re.I,
)

_ROOF_VISION_PROMPT = """\
You are analyzing a Lithuanian roof drawing (STOGO PLANAS or STOGO PJŪVIS).

For ROOF PLAN (top-down view):
- plan_length_mm, plan_width_mm (building footprint dimensions)
- roof_type: dvišlaitis (gable), keturšlaitis (hip), mansarda, plokščias (flat)
- ridge_length_mm (kraigo ilgis)
- overhang_mm (iškyša)
- pitch_degrees: roof slope angle in degrees (if labeled on plan)

For ROOF SECTION (cross-section):
- pitch_degrees: angle in degrees from section label or calculated from rise/run
- rafter_length_mm: actual rafter length
- insulation_thickness_mm if shown

Return ONLY valid JSON (no markdown):
{"drawing_type":"plan","roof_type":"dvišlaitis",\
"plan_length_mm":12000,"plan_width_mm":8000,\
"pitch_degrees":30,"ridge_length_mm":8000,\
"overhang_mm":500,"rafter_length_mm":5196,\
"insulation_thickness_mm":200}"""

_EARTHWORKS_PAGE_RE = re.compile(
    r'ŽEMĖS DARBAI|SITUACIJ[AO]|INŽINERINIS PLANAS|SITE PLAN|SKLYP[AO]',
    re.I,
)

_EARTHWORKS_VISION_PROMPT = """\
You are analyzing a Lithuanian earthworks/site plan drawing (ŽEMĖS DARBAI / SITUACIJA).

Extract:
1. BUILDING FOOTPRINT: length_mm × width_mm (from outer walls on plan)
2. FOUNDATION depth_mm from section (typically 800–2000 mm)
3. EXCAVATION pit: length_mm × width_mm × depth_mm (usually 300 mm larger per side than footprint)
4. TRENCHES: for each trench — type (vandentiekis/kanalizacija/šildymas), bottom_width_mm, depth_mm, length_mm
5. SOIL TYPE if labeled: smėlis, molis, žvyras, priemolis
6. GROUNDWATER level_mm below surface if marked

Return ONLY valid JSON (no markdown):
{"building_footprint":{"length_mm":15000,"width_mm":10000},\
"foundation_depth_mm":1500,\
"excavation":{"length_mm":15600,"width_mm":10600,"depth_mm":1800},\
"trenches":[{"type":"vandentiekis","bottom_width_mm":600,"depth_mm":1200,"length_mm":25000}],\
"soil_type":"smėlis","groundwater_depth_mm":3000}"""

_CONCRETE_PAGE_RE = re.compile(
    r'KONSTRUKCIJŲ BRĖŽINYS|GELŽBETONINIŲ|ARMATŪROS|PAMATO PLANAS|K-\d|KONSTRUKCINIS',
    re.I,
)

_CONCRETE_VISION_PROMPT = """\
You are analyzing a Lithuanian structural/concrete drawing (KONSTRUKCIJŲ BRĖŽINYS).

Extract ALL concrete elements with their dimensions:
1. SLABS (plokštės/perdangos): length_mm × width_mm × thickness_mm, count
2. BEAMS (sijos): width_mm × height_mm × length_mm, count
3. COLUMNS (kolonos): width_mm × depth_mm × height_mm (or diameter_mm × height_mm), count
4. STRIP FOUNDATION (juostinis pamatas): width_mm × height_mm × perimeter_mm
5. PAD FOUNDATION (stulpinis pamatas): length_mm × width_mm × height_mm × count
6. SLAB FOUNDATION (plokštinis pamatas): length_mm × width_mm × thickness_mm
7. WALLS (betoninės sienos): length_mm × height_mm × thickness_mm × count
8. CONCRETE CLASS: C20/25, C25/30, C30/37, etc. if labeled
9. REBAR: main bar diameter_mm if shown

Return ONLY valid JSON (no markdown):
{"slabs":[{"length_mm":12000,"width_mm":8000,"thickness_mm":200,"count":1}],\
"beams":[{"width_mm":250,"height_mm":500,"length_mm":6000,"count":4}],\
"columns":[{"width_mm":300,"depth_mm":300,"height_mm":3200,"count":6}],\
"strip_foundation":{"width_mm":600,"height_mm":400,"perimeter_mm":40000},\
"concrete_walls":[],\
"concrete_class":"C25/30","rebar_diameter_mm":12}"""


# ── Facade calculations ───────────────────────────────────────────────────────

def _calculate_facade_quantities(facades: list[dict]) -> dict:
    total_gross = 0.0
    total_net   = 0.0
    total_windows = 0
    total_doors   = 0
    total_win_area  = 0.0
    total_door_area = 0.0
    facade_widths_m = []
    facades_detailed = []

    for f in facades:
        w_m  = (f.get("width_mm")  or 0) / 1000
        h_m  = (f.get("height_mm") or 0) / 1000
        if not w_m or not h_m:
            continue
        gross = w_m * h_m

        win_area = sum(
            (win.get("width_mm") or 0) / 1000 *
            (win.get("height_mm") or 0) / 1000 *
            max(win.get("count") or 1, 1)
            for win in (f.get("windows") or [])
        )
        door_area = sum(
            (d.get("width_mm") or 0) / 1000 *
            (d.get("height_mm") or 0) / 1000 *
            max(d.get("count") or 1, 1)
            for d in (f.get("doors") or [])
        )
        balcony_area = sum(
            (b.get("width_mm") or 0) / 1000 *
            (b.get("height_mm") or 0) / 1000 *
            max(b.get("count") or 1, 1)
            for b in (f.get("balconies") or [])
        )
        gt = f.get("gable_triangle")
        gable_area = (
            0.5 * (gt.get("base_mm") or 0) / 1000 * (gt.get("height_mm") or 0) / 1000
            if gt else 0
        )
        gross_total = gross + gable_area
        net = max(0.0, gross_total - win_area - door_area - balcony_area)

        wins_vnt  = sum(max(w.get("count") or 1, 1) for w in (f.get("windows") or []))
        doors_vnt = sum(max(d.get("count") or 1, 1) for d in (f.get("doors") or []))

        total_gross   += gross_total
        total_net     += net
        total_windows += wins_vnt
        total_doors   += doors_vnt
        total_win_area  += win_area
        total_door_area += door_area
        facade_widths_m.append(w_m)

        facades_detailed.append({
            "label":         f.get("label") or f.get("facade_direction") or "",
            "bruto_m2":      round(gross_total, 2),
            "neto_m2":       round(net, 2),
            "langu_vnt":     wins_vnt,
            "duru_vnt":      doors_vnt,
            "langu_plotas_m2":  round(win_area, 2),
            "duru_plotas_m2":   round(door_area, 2),
        })

    building_perimeter_m = sum(facade_widths_m)
    A = total_net  # insulation area

    etics = {
        "izoliacijos_plotas_m2":   round(A, 1),
        "klijai_kg":               round(A * 5.5),
        "smeiges_vnt":             round(A * 7),
        "armavimo_tinklelis_m2":   round(A * 1.1, 1),
        "armavimo_misinys_kg":     round(A * 4.5),
        "gruntas_l":               round(A * 0.25, 1),
        "dekoratyvinis_tinkas_kg": round(A * 3.0),
        "cokolinis_profilis_m":    round(building_perimeter_m, 1),
        "kampiniai_profiliai_m":   round(len(facades) * 2 * 3.0, 1),
        "palanges_m":              round(total_windows * 1.2, 1),
    }

    return {
        "fasadai":    facades_detailed,
        "bendra": {
            "bruto_m2":     round(total_gross, 1),
            "neto_m2":      round(total_net, 1),
            "langu_vnt":    total_windows,
            "duru_vnt":     total_doors,
            "perimetras_m": round(building_perimeter_m, 1),
        },
        "etics": etics,
    }


# ── Roof calculations ─────────────────────────────────────────────────────────

def _calculate_roof_quantities(roof_data: dict) -> dict:
    pitch_deg = float(roof_data.get("pitch_degrees") or 30)
    slope_factor = 1 / math.cos(math.radians(pitch_deg))

    plan_l = (roof_data.get("plan_length_mm") or 0) / 1000
    plan_w = (roof_data.get("plan_width_mm")  or 0) / 1000
    plan_area   = plan_l * plan_w
    actual_area = plan_area * slope_factor

    ridge_l   = (roof_data.get("ridge_length_mm") or 0) / 1000 or plan_l
    overhang  = (roof_data.get("overhang_mm") or 500) / 1000
    eaves_perim = 2 * (plan_l + plan_w) + 4 * overhang if plan_l and plan_w else 0

    return {
        "plano_plotas_m2":    round(plan_area, 1),
        "slope_factor":       round(slope_factor, 3),
        "tikrasis_plotas_m2": round(actual_area, 1),
        "kampas_laipsniais":  pitch_deg,
        "kraigo_ilgis_m":     round(ridge_l, 1),
        "latakų_perimetras_m": round(eaves_perim, 1),
        "medžiagos": {
            "stogo_danga_m2":       round(actual_area * 1.10, 1),
            "hidroizoliacijos_m2":  round(actual_area * 1.15, 1),
            "latai_m":              round(actual_area / 0.33) if actual_area else 0,
            "sniegolauziai_m":      round(ridge_l, 1),
            "lietvamzdžiai_m":      round(eaves_perim, 1),
            "latakai_m":            round(eaves_perim, 1),
        },
    }


# ── Earthworks calculations ───────────────────────────────────────────────────

def _calculate_earthworks_quantities(data: dict) -> dict:
    exc  = data.get("excavation") or {}
    L    = (exc.get("length_mm") or 0) / 1000
    W    = (exc.get("width_mm")  or 0) / 1000
    D    = (exc.get("depth_mm")  or 0) / 1000
    pit_volume = L * W * D if (L and W and D) else 0

    soil = (data.get("soil_type") or "smėlis").lower()
    if any(k in soil for k in ("smėl", "žvyr")):
        swell = 0.12
    elif "mol" in soil:
        swell = 0.25
    else:
        swell = 0.15

    trench_items = []
    total_trench = 0.0
    for t in (data.get("trenches") or []):
        bw     = (t.get("bottom_width_mm") or 0) / 1000
        depth  = (t.get("depth_mm")        or 0) / 1000
        length = (t.get("length_mm")       or 0) / 1000
        top_w  = bw + 2 * depth  # 1:1 slope
        cross  = (bw + top_w) / 2 * depth
        vol    = cross * length
        total_trench += vol
        trench_items.append({
            "tipas":      t.get("type", ""),
            "tūris_m3":   round(vol, 2),
            "ilgis_m":    round(length, 1),
            "gylis_m":    round(depth, 2),
        })

    fp   = data.get("building_footprint") or {}
    fl   = (fp.get("length_mm") or 0) / 1000
    fw   = (fp.get("width_mm")  or 0) / 1000
    fd   = (data.get("foundation_depth_mm") or 800) / 1000
    perim_m = 2 * (fl + fw) if fl and fw else 0
    found_vol = perim_m * 0.6 * fd if perim_m else 0  # 0.6 m typical strip width

    backfill     = max(0.0, pit_volume - found_vol)
    hauling_vol  = pit_volume * (1 + swell)
    compact_vol  = backfill * (1 - 0.08)  # 8% shrinkage

    return {
        "iskasa": {
            "tūris_m3":       round(pit_volume, 1),
            "išvežimas_m3":   round(hauling_vol, 1),
            "grunto_tipas":   soil,
            "išbrinkimo_koef": swell,
        },
        "tranšėjos":          trench_items,
        "tranšejų_tūris_m3":  round(total_trench, 1),
        "užpylimas_m3":       round(backfill, 1),
        "sutankinimas_m3":    round(compact_vol, 1),
    }


# ── Concrete calculations ─────────────────────────────────────────────────────

def _calculate_concrete_quantities(data: dict) -> dict:
    total_volume   = 0.0
    total_formwork = 0.0
    elements = []

    for s in (data.get("slabs") or []):
        L = (s.get("length_mm")    or 0) / 1000
        W = (s.get("width_mm")     or 0) / 1000
        T = (s.get("thickness_mm") or 0) / 1000
        n = s.get("count") or 1
        vol = L * W * T * n
        fw  = L * W * n
        total_volume   += vol
        total_formwork += fw
        elements.append({"tipas": "plokštė", "tūris_m3": round(vol, 3), "klojiniai_m2": round(fw, 2)})

    for b in (data.get("beams") or []):
        bw = (b.get("width_mm")  or 0) / 1000
        bh = (b.get("height_mm") or 0) / 1000
        bl = (b.get("length_mm") or 0) / 1000
        n  = b.get("count") or 1
        vol = bw * bh * bl * n
        fw  = (2 * bh + bw) * bl * n
        total_volume   += vol
        total_formwork += fw
        elements.append({"tipas": "sija", "tūris_m3": round(vol, 3), "klojiniai_m2": round(fw, 2)})

    for c in (data.get("columns") or []):
        ch = (c.get("height_mm") or 0) / 1000
        n  = c.get("count") or 1
        if c.get("diameter_mm"):
            r    = (c["diameter_mm"] / 2) / 1000
            area = math.pi * r * r
            fw_u = math.pi * (c["diameter_mm"] / 1000)
        else:
            cw   = (c.get("width_mm")  or 0) / 1000
            cd   = (c.get("depth_mm")  or cw) / 1000
            area = cw * cd
            fw_u = 2 * (cw + cd)
        vol = area * ch * n
        fw  = fw_u * ch * n
        total_volume   += vol
        total_formwork += fw
        elements.append({"tipas": "kolona", "tūris_m3": round(vol, 3), "klojiniai_m2": round(fw, 2)})

    sf = data.get("strip_foundation")
    if sf:
        fw2 = (sf.get("width_mm") or 0) / 1000
        fh  = (sf.get("height_mm") or 0) / 1000
        fp  = (sf.get("perimeter_mm") or 0) / 1000
        vol = fw2 * fh * fp
        total_volume += vol
        elements.append({"tipas": "juostinis pamatas", "tūris_m3": round(vol, 3), "klojiniai_m2": 0})

    for w in (data.get("concrete_walls") or []):
        wl = (w.get("length_mm")    or 0) / 1000
        wh = (w.get("height_mm")    or 0) / 1000
        wt = (w.get("thickness_mm") or 0) / 1000
        n  = w.get("count") or 1
        vol = wl * wh * wt * n
        fw  = 2 * wl * wh * n
        total_volume   += vol
        total_formwork += fw
        elements.append({"tipas": "siena", "tūris_m3": round(vol, 3), "klojiniai_m2": round(fw, 2)})

    vol_waste  = total_volume * 1.07
    rebar_kg   = total_volume * 120  # avg 120 kg/m³

    return {
        "elementai":           elements,
        "betono_turis_m3":     round(total_volume, 2),
        "su_atliekomis_m3":    round(vol_waste, 2),
        "klojiniai_m2":        round(total_formwork, 1),
        "armatūra_kg":         round(rebar_kg),
        "armatūra_t":          round(rebar_kg / 1000, 2),
        "betono_klase":        data.get("concrete_class") or "C25/30",
    }


# ── Generic vision-extraction helper ─────────────────────────────────────────

async def _run_vision_on_pages(
    contents: bytes,
    page_filter_re: re.Pattern | None,
    vision_prompt: str,
    max_concurrent: int = 4,
) -> list[dict]:
    """Convert PDF → images, filter pages, run vision, return list of parsed JSON dicts."""
    images = await asyncio.to_thread(_pdf_to_images, contents)

    if page_filter_re:
        # Identify relevant pages by text
        relevant_pages: set[int] = set()
        with pdfplumber.open(io.BytesIO(contents)) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                if page_filter_re.search(text):
                    relevant_pages.add(i + 1)
        # If none matched, use all pages (document might not have text layer)
        if not relevant_pages:
            relevant_pages = {pno for pno, _ in images}
    else:
        relevant_pages = {pno for pno, _ in images}

    sem = asyncio.Semaphore(max_concurrent)

    async def _one(pno: int, b64: str) -> dict | None:
        async with sem:
            for attempt in range(3):
                try:
                    raw  = await asyncio.to_thread(_call_vision, b64, vision_prompt)
                    data = _parse_json_safe(raw)
                    if data and isinstance(data, dict):
                        return data
                    return None
                except Exception:
                    if attempt == 2:
                        return None
                    await asyncio.sleep(2 ** attempt)
        return None

    results = await asyncio.gather(
        *[_one(pno, b64) for pno, b64 in images if pno in relevant_pages],
        return_exceptions=True,
    )
    return [r for r in results if isinstance(r, dict)]


# ── /extract-facade ───────────────────────────────────────────────────────────

@app.post("/extract-facade")
async def extract_facade(file: UploadFile = File(...)):
    try:
        async with asyncio.timeout(300):
            contents = await file.read()
            projektas = ""
            with pdfplumber.open(io.BytesIO(contents)) as pdf:
                projektas = _find_projektas((pdf.pages[0].extract_text() or "") if pdf.pages else "")

            try:
                facades = await _run_vision_on_pages(contents, _FACADE_PAGE_RE, _FACADE_VISION_PROMPT)
            except ImportError:
                return {"error": "Nepavyko konvertuoti PDF — įdiekite poppler (pdf2image)."}

            if not facades:
                return {"error": "Fasadų brėžiniai nerasti arba nepavyko nuskaityti matmenų."}

            quantities = _calculate_facade_quantities(facades)
            return {
                "projektas": projektas or "Fasadų projektas",
                "tipas":     "fasadas",
                "fasadu_skaicius": len(facades),
                **quantities,
            }
    except asyncio.TimeoutError:
        return {"error": "Timeout — PDF per didelis arba API neatsakė laiku."}
    except Exception as e:
        return {"error": f"Nenumatyta klaida: {type(e).__name__}: {e}"}


# ── /extract-roof ─────────────────────────────────────────────────────────────

@app.post("/extract-roof")
async def extract_roof(file: UploadFile = File(...)):
    try:
        async with asyncio.timeout(300):
            contents = await file.read()
            projektas = ""
            with pdfplumber.open(io.BytesIO(contents)) as pdf:
                projektas = _find_projektas((pdf.pages[0].extract_text() or "") if pdf.pages else "")

            try:
                roof_pages = await _run_vision_on_pages(contents, _ROOF_PAGE_RE, _ROOF_VISION_PROMPT)
            except ImportError:
                return {"error": "Nepavyko konvertuoti PDF — įdiekite poppler (pdf2image)."}

            if not roof_pages:
                return {"error": "Stogo brėžiniai nerasti arba nepavyko nuskaityti matmenų."}

            # Merge data: prefer plan page for dimensions, section for pitch
            merged: dict = {}
            for rd in roof_pages:
                for k, v in rd.items():
                    if v is not None and k not in merged:
                        merged[k] = v

            quantities = _calculate_roof_quantities(merged)
            return {
                "projektas": projektas or "Stogo projektas",
                "tipas":     "stogas",
                "stogo_duomenys": merged,
                **quantities,
            }
    except asyncio.TimeoutError:
        return {"error": "Timeout — PDF per didelis arba API neatsakė laiku."}
    except Exception as e:
        return {"error": f"Nenumatyta klaida: {type(e).__name__}: {e}"}


# ── /extract-earthworks ───────────────────────────────────────────────────────

@app.post("/extract-earthworks")
async def extract_earthworks(file: UploadFile = File(...)):
    try:
        async with asyncio.timeout(300):
            contents = await file.read()
            projektas = ""
            with pdfplumber.open(io.BytesIO(contents)) as pdf:
                projektas = _find_projektas((pdf.pages[0].extract_text() or "") if pdf.pages else "")

            try:
                pages_data = await _run_vision_on_pages(
                    contents, _EARTHWORKS_PAGE_RE, _EARTHWORKS_VISION_PROMPT
                )
            except ImportError:
                return {"error": "Nepavyko konvertuoti PDF — įdiekite poppler (pdf2image)."}

            if not pages_data:
                return {"error": "Žemės darbų brėžiniai nerasti arba nepavyko nuskaityti matmenų."}

            merged: dict = {}
            for pd_item in pages_data:
                for k, v in pd_item.items():
                    if v is not None and k not in merged:
                        merged[k] = v
                    elif isinstance(v, list) and k in merged and isinstance(merged[k], list):
                        merged[k].extend(v)

            quantities = _calculate_earthworks_quantities(merged)
            return {
                "projektas":  projektas or "Žemės darbų projektas",
                "tipas":      "zeme",
                "raw_duomenys": merged,
                **quantities,
            }
    except asyncio.TimeoutError:
        return {"error": "Timeout — PDF per didelis arba API neatsakė laiku."}
    except Exception as e:
        return {"error": f"Nenumatyta klaida: {type(e).__name__}: {e}"}


# ── /extract-concrete ─────────────────────────────────────────────────────────

@app.post("/extract-concrete")
async def extract_concrete(file: UploadFile = File(...)):
    try:
        async with asyncio.timeout(300):
            contents = await file.read()
            projektas = ""
            with pdfplumber.open(io.BytesIO(contents)) as pdf:
                projektas = _find_projektas((pdf.pages[0].extract_text() or "") if pdf.pages else "")

            try:
                pages_data = await _run_vision_on_pages(
                    contents, _CONCRETE_PAGE_RE, _CONCRETE_VISION_PROMPT
                )
            except ImportError:
                return {"error": "Nepavyko konvertuoti PDF — įdiekite poppler (pdf2image)."}

            if not pages_data:
                return {"error": "Konstrukcijų brėžiniai nerasti arba nepavyko nuskaityti matmenų."}

            # Merge: lists extend, scalars take first non-null
            merged: dict = {"slabs": [], "beams": [], "columns": [], "concrete_walls": []}
            for pd_item in pages_data:
                for k, v in pd_item.items():
                    if isinstance(v, list):
                        merged.setdefault(k, []).extend(v)
                    elif v is not None and not merged.get(k):
                        merged[k] = v

            quantities = _calculate_concrete_quantities(merged)
            return {
                "projektas":  projektas or "Betono darbų projektas",
                "tipas":      "betonas",
                "raw_duomenys": merged,
                **quantities,
            }
    except asyncio.TimeoutError:
        return {"error": "Timeout — PDF per didelis arba API neatsakė laiku."}
    except Exception as e:
        return {"error": f"Nenumatyta klaida: {type(e).__name__}: {e}"}


# ── Task 7: update /extract to add kategorija + improve auto-detection ─────────
# _postprocess_eilutes already deduplicates; add kategorija field here.

def _enrich_eilutes(eilutes: list[dict]) -> list[dict]:
    """Add kategorija field to each row and improve skyrius normalisation."""
    for e in eilutes:
        sky = e.get("skyrius") or ""
        apr = e.get("aprasymas") or ""
        e["kategorija"] = _detect_row_category(apr, sky)
    return eilutes


# ── /generate-excel ───────────────────────────────────────────────────────────

@app.post("/generate-excel")
async def generate_excel(request: Request, data: dict):
    # Sprint §AUDIT (2026-04-29): require auth — was open endpoint, vulnerable
    # to abuse (each call spins up openpyxl + heavy I/O).
    _auth.require_user(request)
    from datetime import date as _date

    C_DARK   = "1F3864"
    C_MID    = "2E4D7B"
    C_SEC    = "D6E4F0"
    C_ORANGE = "E67E22"
    C_GRAY   = "F5F5F5"
    C_GREEN  = "1A7F37"
    C_TOTBG  = "FFF8F0"
    C_SHEET_HDR = "E8F0FB"

    thin   = Side(style="thin",   color="CCCCCC")
    thick  = Side(style="medium", color="AAAAAA")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    projektas    = data.get("projektas", "Projektas")
    imone        = (data.get("imone") or data.get("company_name") or "").strip()
    eilutes      = data.get("eilutes", [])
    prielaidos   = data.get("prielaidos") or {}
    patalpos     = data.get("patalpos") or []
    perspejimani = data.get("perspejimani") or []
    today_str    = _date.today().strftime("%Y-%m-%d")

    wb = openpyxl.Workbook()

    # ─────────────────────────────────────────────────────────────────────────
    # Helper: write a standard section header row on any sheet
    # ─────────────────────────────────────────────────────────────────────────
    def _write_sheet_header(ws, title: str, data_row: int = 3):
        # Sprint §FIX-3 (2026-04-29): merge A1:F1 (was A1:G1) — Conf column
        # removed from data rows; header banner shouldn't extend past Suma.
        ws.merge_cells(f"A1:F1")
        c = ws["A1"]
        # 2026-05-06: prepend imone if set so the company appears in the
        # banner: 'UAB Statyba · Pasiūlymas · Projekto pavadinimas'.
        prefix = f"{imone}  ·  " if imone else ""
        c.value     = f"{prefix}{title}  ·  {projektas}"
        c.font      = Font(bold=True, size=12, color="FFFFFF")
        c.fill      = PatternFill("solid", fgColor=C_DARK)
        c.alignment = Alignment(horizontal="left", vertical="center", indent=2)
        ws.row_dimensions[1].height = 26

        ws.merge_cells("A2:D2")
        ws["A2"].value = today_str
        ws["A2"].font  = Font(size=8, color="888888")
        ws.row_dimensions[2].height = 14

        # Sprint §FIX-3 (2026-04-29): Conf. stulpelis pašalintas iš header'io
        # ir _write_rows. User reported: client-facing Excel turi būti clean
        # be vidaus debug indikatorių.
        HDR = [
            ("Nr.",        "left",   "A", 9),
            ("Aprašymas",  "left",   "B", 50),
            ("Mat. vnt.",  "center", "C", 11),
            ("Kiekis",     "right",  "D", 13),
            ("Kaina €",    "right",  "E", 14),
            ("Suma €",     "right",  "F", 16),
        ]
        for col, (label, align, col_letter, width) in enumerate(HDR, 1):
            c = ws.cell(row=data_row, column=col, value=label)
            c.font      = Font(bold=True, size=9, color="FFFFFF")
            c.fill      = PatternFill("solid", fgColor=C_MID)
            c.alignment = Alignment(horizontal=align, vertical="center")
            c.border    = border
            ws.column_dimensions[col_letter].width = width
        ws.row_dimensions[data_row].height = 18
        ws.freeze_panes = f"A{data_row + 1}"

    # ─────────────────────────────────────────────────────────────────────────
    # Helper: write rows + totals block on a sheet starting at row `r`
    # Returns the next free row.
    # ─────────────────────────────────────────────────────────────────────────
    def _write_rows(ws, rows: list[dict], start_row: int = 4) -> int:
        current_section = None
        data_row_idx    = 0
        r = start_row

        for e in rows:
            sec = (e.get("skyrius") or "").strip()
            if sec and sec != current_section:
                current_section = sec
                ws.merge_cells(f"A{r}:F{r}")
                sc = ws[f"A{r}"]
                sc.value     = sec
                sc.font      = Font(bold=True, size=9, color=C_MID)
                sc.fill      = PatternFill("solid", fgColor=C_SEC)
                sc.alignment = Alignment(horizontal="left", vertical="center", indent=1)
                sc.border    = Border(
                    left=thick, right=thick,
                    top=Side(style="medium", color=C_MID),
                    bottom=Side(style="medium", color=C_MID),
                )
                ws.row_dimensions[r].height = 16
                r += 1
                data_row_idx = 0

            bg   = "FFFFFF" if data_row_idx % 2 == 0 else C_GRAY
            fill = PatternFill("solid", fgColor=bg)

            kiekis = e.get("kiekis", 0)
            kaina  = e.get("kaina",  0)

            # Sprint §FIX-3 (2026-04-29): user reported confidence dots in
            # Excel are noise — exported sąmata should look clean for clients.
            # Removed the 7th column entirely. Internal confidence still
            # available in JSON / UI peržiūra queue.
            for col, (val, align, wrap) in enumerate([
                (e.get("nr",        ""),  "left",   False),
                (e.get("aprasymas", ""),  "left",   True),
                (e.get("mato_vnt",  ""),  "center", False),
                (kiekis,                  "right",  False),
                (kaina,                   "right",  False),
                (None,                    "right",  False),   # formula placeholder
            ], 1):
                if col == 6:
                    # Excel formula: Suma = Kiekis × Kaina
                    fc = ws.cell(row=r, column=6)
                    fc.value        = f"=D{r}*E{r}"
                    fc.fill         = fill
                    fc.border       = border
                    fc.alignment    = Alignment(horizontal="right", vertical="center")
                    fc.number_format = "#,##0.00"
                    fc.font         = Font(bold=True, color=C_GREEN)
                else:
                    c = ws.cell(row=r, column=col, value=val)
                    c.fill      = fill
                    c.border    = border
                    c.alignment = Alignment(horizontal=align, vertical="center", wrap_text=wrap)
                    if col in (4, 5) and isinstance(val, (int, float)):
                        c.number_format = "#,##0.00"
            ws.row_dimensions[r].height = 18
            r += 1
            data_row_idx += 1

        return r

    def _write_totals(ws, rows: list[dict], r: int):
        ws.row_dimensions[r].height = 6
        r += 1

        data_start = 4
        data_end   = r - 2  # last data row

        def _tot(sheet_row, label, formula_or_val, lcolor="444444", vcolor="444444",
                 fsize=10, top=False):
            ws.merge_cells(f"A{sheet_row}:E{sheet_row}")
            lc              = ws[f"A{sheet_row}"]
            lc.value        = label
            lc.font         = Font(bold=True, size=fsize, color=lcolor)
            lc.fill         = PatternFill("solid", fgColor=C_TOTBG)
            lc.alignment    = Alignment(horizontal="right", vertical="center")
            tb = Side(style="medium", color="AAAAAA") if top else thin
            lc.border       = Border(left=thin, right=thin, top=tb, bottom=thin)

            vc              = ws.cell(row=sheet_row, column=6, value=formula_or_val)
            vc.font         = Font(bold=True, size=fsize, color=vcolor)
            vc.fill         = PatternFill("solid", fgColor=C_TOTBG)
            vc.alignment    = Alignment(horizontal="right", vertical="center")
            vc.number_format = '#,##0.00 "€"'
            vc.border       = Border(left=thin, right=thin, top=tb, bottom=thin)
            ws.row_dimensions[sheet_row].height = 20 if fsize <= 10 else 24

        sum_formula = f"=SUM(F{data_start}:F{data_end})"

        _tot(r,     "Suma be PVM:",  sum_formula,                  top=True)
        _tot(r + 1, "PVM 21%:",      f"=ROUND(F{r}*0.21,2)")
        _tot(r + 2, "VISO su PVM:",  f"=F{r}+F{r+1}",
             lcolor=C_ORANGE, vcolor=C_ORANGE, fsize=12)

    # ─────────────────────────────────────────────────────────────────────────
    # Sheet 1: Sąmata (full combined list)
    # ─────────────────────────────────────────────────────────────────────────
    ws_main = wb.active
    ws_main.title = "Sąmata"
    _write_sheet_header(ws_main, "SĄMATA")
    last_r = _write_rows(ws_main, eilutes, start_row=4)
    _write_totals(ws_main, eilutes, last_r)

    # ─────────────────────────────────────────────────────────────────────────
    # Sheets 2..N: one sheet per section (skyrius).
    # Sprint §FIX-2 (2026-04-29): normalize skyrius via SKYRIUS_LEGACY_MIGRATION
    # before grouping so legacy variants ("GKP", "Gipso kartono montavimas",
    # "Glaistymas dazymas", etc.) collapse into one canonical sheet.
    # ─────────────────────────────────────────────────────────────────────────
    from collections import OrderedDict
    from extractor.vision_call import SKYRIUS_LEGACY_MIGRATION
    sections: dict[str, list] = OrderedDict()
    for e in eilutes:
        sec_raw = (e.get("skyrius") or "KITI DARBAI").strip()
        sec = SKYRIUS_LEGACY_MIGRATION.get(sec_raw, sec_raw)
        # Mutate the row's skyrius to canonical so the section header in
        # _write_rows shows the normalized name too.
        e["skyrius"] = sec
        sections.setdefault(sec, []).append(e)

    for sec_name, sec_rows in sections.items():
        safe_name = re.sub(r"[/\\?*:\[\]]", "_", sec_name)[:28]
        ws_sec = wb.create_sheet(title=safe_name)
        _write_sheet_header(ws_sec, sec_name)
        last_r2 = _write_rows(ws_sec, sec_rows, start_row=4)
        _write_totals(ws_sec, sec_rows, last_r2)

    # ─────────────────────────────────────────────────────────────────────────
    # Sheet: Prielaidos
    # ─────────────────────────────────────────────────────────────────────────
    if prielaidos:
        ws_pr = wb.create_sheet(title="Prielaidos")
        ws_pr.merge_cells("A1:C1")
        t = ws_pr["A1"]
        t.value     = f"Prielaidos  ·  {projektas}"
        t.font      = Font(bold=True, size=11, color="FFFFFF")
        t.fill      = PatternFill("solid", fgColor=C_DARK)
        t.alignment = Alignment(horizontal="left", vertical="center", indent=2)
        ws_pr.row_dimensions[1].height = 24

        ws_pr.column_dimensions["A"].width = 30
        ws_pr.column_dimensions["B"].width = 20
        ws_pr.column_dimensions["C"].width = 15

        pr_rows = [
            ("Parametras", "Reikšmė", "Vienetas"),
            ("Lubų aukštis (vid.)",   prielaidos.get("lubu_aukstis_m"),   "m"),
            ("Sienos storis",          prielaidos.get("sienos_storis_m"),  "m"),
            ("Glaistymo lygis",        prielaidos.get("glaistimo_lygis"),  ""),
            ("Langų skaičius",         prielaidos.get("langai_vnt"),       "vnt."),
            ("Durų skaičius",          prielaidos.get("durys_vnt"),        "vnt."),
            ("Langai — prielaida",     "Taip" if prielaidos.get("langai_fallback") else "Ne", ""),
            ("Data",                   today_str,                          ""),
        ]

        for ri, (param, val, unit) in enumerate(pr_rows, 2):
            is_hdr = ri == 2
            ws_pr.cell(row=ri, column=1, value=param).font = Font(bold=is_hdr, size=9)
            ws_pr.cell(row=ri, column=2, value=val).font   = Font(size=9)
            ws_pr.cell(row=ri, column=3, value=unit).font  = Font(size=9, color="888888")
            if is_hdr:
                for ci in range(1, 4):
                    ws_pr.cell(row=ri, column=ci).fill = PatternFill("solid", fgColor=C_SHEET_HDR)
            for ci in range(1, 4):
                ws_pr.cell(row=ri, column=ci).border = border
            ws_pr.row_dimensions[ri].height = 16

    # ─────────────────────────────────────────────────────────────────────────
    # Sheet: Patalpos (Task 7)
    # ─────────────────────────────────────────────────────────────────────────
    if patalpos:
        ws_pat = wb.create_sheet(title="Patalpos")
        ws_pat.merge_cells("A1:D1")
        t = ws_pat["A1"]
        t.value     = f"Patalpos  ·  {projektas}"
        t.font      = Font(bold=True, size=11, color="FFFFFF")
        t.fill      = PatternFill("solid", fgColor=C_DARK)
        t.alignment = Alignment(horizontal="left", vertical="center", indent=2)
        ws_pat.row_dimensions[1].height = 24

        pat_hdr = [("Nr.", "A", 8), ("Pavadinimas", "B", 35), ("Plotas m²", "C", 14), ("Lubų aukštis", "D", 15)]
        for ci, (lbl, col, w) in enumerate(pat_hdr, 1):
            c = ws_pat.cell(row=2, column=ci, value=lbl)
            c.font  = Font(bold=True, size=9, color="FFFFFF")
            c.fill  = PatternFill("solid", fgColor=C_MID)
            c.alignment = Alignment(horizontal="center", vertical="center")
            c.border = border
            ws_pat.column_dimensions[col].width = w
        ws_pat.row_dimensions[2].height = 16

        for ri, room in enumerate(patalpos, 3):
            fill = PatternFill("solid", fgColor="FFFFFF" if (ri % 2 == 1) else C_GRAY)
            h_mm = room.get("lubu_aukstis_mm") or 2800
            h_str = f"{h_mm/1000:.2f} m"
            for ci, val in enumerate([
                room.get("nr", ""),
                room.get("pavadinimas", ""),
                room.get("plotas_m2"),
                h_str,
            ], 1):
                c = ws_pat.cell(row=ri, column=ci, value=val)
                c.fill   = fill
                c.border = border
                c.font   = Font(size=9)
                if ci == 3 and isinstance(val, (int, float)):
                    c.number_format = "#,##0.00"
            ws_pat.row_dimensions[ri].height = 16

    # ─────────────────────────────────────────────────────────────────────────
    # Sheet: Pastabos (Task 7) — forgotten items warnings
    # ─────────────────────────────────────────────────────────────────────────
    if perspejimani:
        ws_past = wb.create_sheet(title="Pastabos")
        ws_past.merge_cells("A1:C1")
        t = ws_past["A1"]
        t.value     = f"Nepamirškite patikrinti  ·  {projektas}"
        t.font      = Font(bold=True, size=11, color="FFFFFF")
        t.fill      = PatternFill("solid", fgColor="B45309")  # amber
        t.alignment = Alignment(horizontal="left", vertical="center", indent=2)
        ws_past.row_dimensions[1].height = 24
        ws_past.column_dimensions["A"].width = 8
        ws_past.column_dimensions["B"].width = 60
        ws_past.column_dimensions["C"].width = 18

        for ci, lbl in enumerate(["#", "Perspėjimas", "Kategorija"], 1):
            c = ws_past.cell(row=2, column=ci, value=lbl)
            c.font  = Font(bold=True, size=9, color="FFFFFF")
            c.fill  = PatternFill("solid", fgColor="D97706")
            c.border = border
        ws_past.row_dimensions[2].height = 16

        for ri, w in enumerate(perspejimani, 3):
            fill = PatternFill("solid", fgColor="FFFBEB" if ri % 2 == 1 else "FEF3C7")
            for ci, val in enumerate([ri - 2, w.get("tekstas", ""), w.get("kategorija", "")], 1):
                c = ws_past.cell(row=ri, column=ci, value=val)
                c.fill   = fill
                c.border = border
                c.font   = Font(size=9)
            ws_past.row_dimensions[ri].height = 16

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    fname = "samata_" + re.sub(r"[^\w]", "_", projektas[:30], flags=re.ASCII) + ".xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


# ── /generate-pdf ─────────────────────────────────────────────────────────────

@app.post("/generate-pdf")
async def generate_pdf(request: Request, data: dict):
    # Sprint §AUDIT (2026-04-29): require auth — was open endpoint.
    _auth.require_user(request)
    from reportlab.platypus import HRFlowable
    from reportlab.lib.units import mm
    from reportlab.pdfgen.canvas import Canvas as _RLCanvas

    DARK   = colors.HexColor("#1F3864")
    MID    = colors.HexColor("#2E4D7B")
    SEC_BG = colors.HexColor("#D6E4F0")
    SEC_FG = colors.HexColor("#1F3864")
    ORANGE = colors.HexColor("#E67E22")
    LGRAY  = colors.HexColor("#F5F5F5")
    GREEN  = colors.HexColor("#1A7F37")
    TOTBG  = colors.HexColor("#FFF8F0")
    GRID_C = colors.HexColor("#DDDDDD")

    PAGE_W = A4[0] - 3 * cm   # usable width

    # ── Numbered canvas for page X / Y footer ────────────────────────────────
    class _NumberedCanvas(_RLCanvas):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._saved_page_states: list = []

        def showPage(self):
            self._saved_page_states.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            total = len(self._saved_page_states)
            for state in self._saved_page_states:
                self.__dict__.update(state)
                self._draw_page_footer(total)
                super().showPage()
            super().save()

        def _draw_page_footer(self, total: int):
            self.saveState()
            self.setFont(_FONT_NORMAL, 7)
            self.setFillColor(colors.HexColor("#888888"))
            footer_y = 0.8 * cm
            self.drawRightString(A4[0] - 1.5 * cm, footer_y,
                                 f"Puslapis {self._pageNumber} / {total}")
            self.drawString(1.5 * cm, footer_y, "Sąmatų AI · samatu.ai")
            self.setStrokeColor(colors.HexColor("#DDDDDD"))
            self.setLineWidth(0.5)
            self.line(1.5 * cm, footer_y + 0.35 * cm, A4[0] - 1.5 * cm, footer_y + 0.35 * cm)
            self.restoreState()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=1.5*cm, rightMargin=1.5*cm,
        topMargin=1.5*cm,  bottomMargin=1.8*cm,
    )

    # Styles
    n_  = ParagraphStyle("n",  fontName=_FONT_NORMAL, fontSize=8,  leading=10)
    n_r = ParagraphStyle("nr", fontName=_FONT_NORMAL, fontSize=8,  leading=10, alignment=TA_RIGHT)
    n_c = ParagraphStyle("nc", fontName=_FONT_NORMAL, fontSize=8,  leading=10, alignment=TA_CENTER)
    b_  = ParagraphStyle("b",  fontName=_FONT_BOLD,   fontSize=8,  leading=10)
    b_r = ParagraphStyle("br", fontName=_FONT_BOLD,   fontSize=8,  leading=10, alignment=TA_RIGHT)
    b_c = ParagraphStyle("bc", fontName=_FONT_BOLD,   fontSize=8,  leading=10, alignment=TA_CENTER)

    from datetime import date as _date
    projektas    = data.get("projektas", "Projektas")
    imone        = (data.get("imone") or data.get("company_name") or "").strip()
    doc_date     = _date.today().strftime("%Y-%m-%d")
    eilutes      = data.get("eilutes", [])
    prielaidos   = data.get("prielaidos") or {}
    perspejimani = data.get("perspejimani") or []
    tipas_pdf    = data.get("tipas", "kz")
    viso_be_pvm  = sum(e.get("suma", 0) for e in eilutes)
    pvm          = round(viso_be_pvm * 0.21, 2)
    viso_su_pvm  = round(viso_be_pvm + pvm, 2)
    doc_title    = "VIDAUS APDAILOS KIEKIAI" if tipas_pdf == "interjeras" else "KIEKIŲ ŽINIARAŠTIS"

    def _n(v):
        if not isinstance(v, (int, float)):
            return str(v)
        return f"{v:,.2f}".replace(",", "\u202f").replace(".", ",")

    story = []

    # ── Logo + header bar ─────────────────────────────────────────────────────
    logo_style = ParagraphStyle(
        "logo_ph", fontName=_FONT_NORMAL, fontSize=8,
        textColor=colors.HexColor("#888888"), alignment=TA_CENTER,
    )
    title_style = ParagraphStyle(
        "htitle", fontName=_FONT_BOLD, fontSize=18,
        textColor=colors.white, leading=22,
    )
    sub_style = ParagraphStyle(
        "hsub", fontName=_FONT_NORMAL, fontSize=8,
        textColor=colors.HexColor("#BBCCDD"), leading=11,
    )

    # Task 8: Cover page title from doc_title
    # Logo placeholder box
    logo_box = Table(
        [[Paragraph("ĮMONĖS\nLOGOTIPAS", logo_style)]],
        colWidths=[3.5*cm], rowHeights=[2.0*cm],
    )
    logo_box.setStyle(TableStyle([
        ("BOX",         (0,0), (-1,-1), 1, colors.HexColor("#AAAAAA")),
        ("VALIGN",      (0,0), (-1,-1), "MIDDLE"),
        ("BACKGROUND",  (0,0), (-1,-1), colors.HexColor("#F0F0F0")),
        ("TOPPADDING",  (0,0), (-1,-1), 4),
        ("BOTTOMPADDING",(0,0),(-1,-1), 4),
    ]))

    # 2026-05-06: surface company name in header sub-line if provided.
    header_sub = f"{imone} · {projektas} · {doc_date}" if imone else f"{projektas} · Sąmatų AI · {doc_date}"
    title_block = Table(
        [[Paragraph(doc_title, title_style)],
         [Paragraph(header_sub, sub_style)]],
        colWidths=[PAGE_W - 4*cm],
    )
    title_block.setStyle(TableStyle([
        ("BACKGROUND",   (0,0), (-1,-1), DARK),
        ("LEFTPADDING",  (0,0), (-1,-1), 14),
        ("RIGHTPADDING", (0,0), (-1,-1), 14),
        ("TOPPADDING",   (0,0), (0, 0),  12),
        ("BOTTOMPADDING",(0,-1),(-1,-1), 12),
        ("VALIGN",       (0,0), (-1,-1), "MIDDLE"),
    ]))

    header_row = Table(
        [[logo_box, title_block]],
        colWidths=[3.8*cm, PAGE_W - 3.8*cm],
    )
    header_row.setStyle(TableStyle([
        ("VALIGN",       (0,0), (-1,-1), "MIDDLE"),
        ("LEFTPADDING",  (0,0), (-1,-1), 0),
        ("RIGHTPADDING", (0,0), (-1,-1), 0),
        ("TOPPADDING",   (0,0), (-1,-1), 0),
        ("BOTTOMPADDING",(0,0), (-1,-1), 0),
        ("BACKGROUND",   (1,0), (1, 0),  DARK),
    ]))
    story.append(header_row)
    story.append(Spacer(1, 0.5*cm))

    # ── Project name ──────────────────────────────────────────────────────────
    story.append(Paragraph(projektas, ParagraphStyle(
        "pname", fontName=_FONT_BOLD, fontSize=11, textColor=DARK, leading=15,
    )))
    story.append(Spacer(1, 0.4*cm))

    # ── Table ─────────────────────────────────────────────────────────────────
    COL_W = [1.1*cm, 8.8*cm, 1.5*cm, 1.8*cm, 2.0*cm, 2.2*cm]

    hdr_l = ParagraphStyle("hl", fontName=_FONT_BOLD, fontSize=8, textColor=colors.white)
    hdr_c = ParagraphStyle("hc", fontName=_FONT_BOLD, fontSize=8, textColor=colors.white, alignment=TA_CENTER)
    hdr_r = ParagraphStyle("hr", fontName=_FONT_BOLD, fontSize=8, textColor=colors.white, alignment=TA_RIGHT)

    table_data  = []
    style_cmds  = []

    # Column header row (row 0)
    table_data.append([
        Paragraph("Nr.",       hdr_l),
        Paragraph("Aprašymas", hdr_l),
        Paragraph("Vnt.",      hdr_c),
        Paragraph("Kiekis",    hdr_r),
        Paragraph("Kaina €",   hdr_r),
        Paragraph("Suma €",    hdr_r),
    ])
    style_cmds += [
        ("BACKGROUND",   (0,0), (-1,0), DARK),
        ("TOPPADDING",   (0,0), (-1,0), 6),
        ("BOTTOMPADDING",(0,0), (-1,0), 6),
    ]

    current_section = None
    data_idx        = 0   # for alternating rows

    for e in eilutes:
        sec = (e.get("skyrius") or "").strip()
        ri  = len(table_data)

        # Section header row
        if sec and sec != current_section:
            current_section = sec
            table_data.append([
                Paragraph(sec, ParagraphStyle(
                    "sec", fontName=_FONT_BOLD, fontSize=8,
                    textColor=SEC_FG,
                )),
                "", "", "", "", "",
            ])
            style_cmds += [
                ("SPAN",        (0, ri), (-1, ri)),
                ("BACKGROUND",  (0, ri), (-1, ri), SEC_BG),
                ("TOPPADDING",  (0, ri), (-1, ri), 5),
                ("BOTTOMPADDING",(0,ri), (-1, ri), 5),
                ("LINEABOVE",   (0, ri), (-1, ri), 0.8, MID),
            ]
            data_idx = 0

        # Data row
        ri = len(table_data)
        bg = colors.white if data_idx % 2 == 0 else LGRAY
        suma_val = e.get("suma", 0)
        table_data.append([
            Paragraph(str(e.get("nr",        "")), n_),
            Paragraph(str(e.get("aprasymas", "")), n_),
            Paragraph(str(e.get("mato_vnt",  "")), n_c),
            Paragraph(_n(e.get("kiekis", 0)),       n_r),
            Paragraph(_n(e.get("kaina",  0)),       n_r),
            Paragraph(_n(suma_val),
                      b_r if isinstance(suma_val, (int,float)) and suma_val > 0
                      else n_r),
        ])
        style_cmds += [
            ("BACKGROUND",   (0, ri), (-1, ri), bg),
            ("TOPPADDING",   (0, ri), (-1, ri), 3),
            ("BOTTOMPADDING",(0, ri), (-1, ri), 3),
        ]
        if isinstance(suma_val, (int, float)) and suma_val > 0:
            style_cmds.append(("TEXTCOLOR", (5, ri), (5, ri), GREEN))
        data_idx += 1

    n_data_rows = len(table_data)

    # ── Totals ────────────────────────────────────────────────────────────────
    def tot_row(label, value, bold=False, orange=False):
        ls = ParagraphStyle("tl",
            fontName=_FONT_BOLD, fontSize=9 if not bold else 11,
            textColor=ORANGE if orange else colors.HexColor("#333333"),
            alignment=TA_RIGHT,
        )
        vs = ParagraphStyle("tv",
            fontName=_FONT_BOLD, fontSize=9 if not bold else 11,
            textColor=ORANGE if orange else colors.HexColor("#333333"),
            alignment=TA_RIGHT,
        )
        ri = len(table_data)
        table_data.append(["", "", "", "", Paragraph(label, ls), Paragraph(_n(value) + "\u202f€", vs)])
        style_cmds.extend([
            ("BACKGROUND",   (0, ri), (-1, ri), TOTBG),
            ("TOPPADDING",   (0, ri), (-1, ri), 5 if not bold else 7),
            ("BOTTOMPADDING",(0, ri), (-1, ri), 5 if not bold else 7),
            ("SPAN",         (0, ri), (3,  ri)),
        ])
        if bold:
            style_cmds.append(("LINEABOVE", (0, ri), (-1, ri), 1.5, ORANGE))

    ri_before_totals = len(table_data)
    tot_row("Suma be PVM:",  viso_be_pvm)
    tot_row("PVM 21%:",      pvm)
    tot_row("VISO su PVM:",  viso_su_pvm, bold=True, orange=True)

    # Global style
    style_cmds += [
        ("FONTSIZE",     (0, 0), (-1, -1), 8),
        ("LEFTPADDING",  (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ("GRID",         (0, 0), (-1, n_data_rows - 1), 0.3, GRID_C),
        ("LINEBELOW",    (0, n_data_rows - 1), (-1, n_data_rows - 1), 0.8, colors.HexColor("#AAAAAA")),
    ]

    tbl = Table(table_data, colWidths=COL_W, repeatRows=1)
    tbl.setStyle(TableStyle(style_cmds))
    story.append(tbl)

    # ── Task 8: Assumptions + warnings page at the end ────────────────────────
    from reportlab.platypus import PageBreak
    story.append(PageBreak())

    sect_style = ParagraphStyle("sect", fontName=_FONT_BOLD, fontSize=10,
                                textColor=DARK, leading=14, spaceAfter=6)
    small_style = ParagraphStyle("small", fontName=_FONT_NORMAL, fontSize=8,
                                 textColor=colors.HexColor("#444444"), leading=11)

    if prielaidos:
        story.append(Paragraph("Skaičiavimo prielaidos", sect_style))
        pr_rows = [["Parametras", "Reikšmė"]]
        pr_map = {
            "lubu_aukstis_m":  ("Lubų aukštis (vid.)", "m"),
            "sienos_storis_m": ("Sienos storis", "m"),
            "glaistimo_lygis": ("Glaistymo lygis", ""),
            "langai_vnt":      ("Langų skaičius", "vnt."),
            "durys_vnt":       ("Durų skaičius", "vnt."),
        }
        for k, (lbl, unit) in pr_map.items():
            v = prielaidos.get(k)
            if v is not None:
                pr_rows.append([lbl, f"{v} {unit}".strip()])
        pr_tbl = Table(pr_rows, colWidths=[9*cm, 5*cm])
        pr_tbl.setStyle(TableStyle([
            ("BACKGROUND",  (0,0), (-1,0), DARK),
            ("TEXTCOLOR",   (0,0), (-1,0), colors.white),
            ("FONTNAME",    (0,0), (-1,0), _FONT_BOLD),
            ("FONTSIZE",    (0,0), (-1,-1), 8),
            ("GRID",        (0,0), (-1,-1), 0.3, GRID_C),
            ("LEFTPADDING", (0,0), (-1,-1), 6),
            ("VALIGN",      (0,0), (-1,-1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), ["FFFFFF", colors.HexColor("#F5F5F5")]),
        ]))
        story.append(pr_tbl)
        story.append(Spacer(1, 0.4*cm))

    if perspejimani:
        story.append(Paragraph("Nepamirškite patikrinti:", sect_style))
        for w in perspejimani:
            story.append(Paragraph(f"• {w.get('tekstas', '')}", small_style))
        story.append(Spacer(1, 0.4*cm))

    story.append(Paragraph(
        "Pastaba: šie kiekiai sugeneruoti AI ir turi būti patikrinti kvalifikuoto specialisto.",
        ParagraphStyle("warn", fontName=_FONT_NORMAL, fontSize=7,
                       textColor=colors.HexColor("#888888"), leading=10, spaceAfter=4)
    ))

    doc.build(story, canvasmaker=_NumberedCanvas)
    buf.seek(0)

    fname = "samata_" + re.sub(r"[^\w]", "_", projektas[:30], flags=re.ASCII) + ".pdf"
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


# ── /extract-interior (new extractor package — Phase 2) ───────────────────────

@app.post("/extract-interior")
async def extract_interior_endpoint(
    request: Request,
    files: list[UploadFile] = File(...),
    rules_override: str | None = Form(None),
):
    """Vidaus apdailos ekstrakcijos endpoint'as.

    Vienas Vision call'as → struktūruotas takeoff JSON. Jokio V7/V8/V9
    versijavimo, jokių pipeline'ų, jokių Tier-fallback'ų. Gali būti
    used backend'ui ir tiesiogiai (Python import).
    """
    client_ip = request.client.host if request.client else "unknown"
    _check_rate_limit(client_ip, "extract-interior")
    # M5: per-user daily Vision spend cap (when configured)
    _user = _auth.get_current_user(request)
    _check_user_spend_cap(_user["id"] if _user else None)

    if not files:
        raise HTTPException(status_code=400, detail="Nepateikta jokio failo")
    pdf_bytes = await files[0].read()
    validation = _validate_pdf_upload(pdf_bytes, files[0].filename or "")

    overrides_dict: dict | None = None
    if rules_override:
        try:
            overrides_dict = json.loads(rules_override)
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"rules_override JSON klaida: {e}")

    log.info("extract-interior: ip=%s file=%s size=%dKB pages=%d has_overrides=%s",
             client_ip, files[0].filename, len(pdf_bytes) // 1024,
             validation.get("page_count", 0), overrides_dict is not None)
    from extractor import extract_interior
    result = await asyncio.to_thread(extract_interior, pdf_bytes, overrides_dict)

    # Propagate large-PDF warning into result.warnings[] so SanityWarningsBanner shows it.
    if isinstance(result, dict) and validation.get("warning"):
        existing = result.get("warnings") or []
        existing.append({"level": "WARN", "message": validation["warning"]})
        result["warnings"] = existing
        # Rebuild lt_sanity mirror to include this warning
        if isinstance(result.get("lt_sanity"), dict):
            ls = result["lt_sanity"]
            ls.setdefault("warnings", []).append({
                "level": "WARNING", "message": validation["warning"], "room": ""
            })
            ls["summary"]["warnings_count"] = ls["summary"].get("warnings_count", 0) + 1
            ls["summary"]["warnings"] = ls["summary"].get("warnings", 0) + 1
        result["_pdf_page_count"] = validation.get("page_count", 0)

    return result


# ── /extract-interior-stream — SSE progressive extraction (SM01) ─────────────
#
# Same input as /extract-interior, but the response is text/event-stream.
# Events: rendering_pdf, started, pass1_started, pass1_completed, zoom_started,
# zoom_room_started, zoom_room_completed, zoom_completed, post_processing,
# done (carrying full result), error.
#
# We run the sync pipeline on a worker thread (extractor.stream wraps that)
# and forward queue items to the client as they appear. Heartbeat comments
# every 10s keep proxies + browsers from closing the connection mid-extraction.

@app.post("/extract-interior-stream")
async def extract_interior_stream_endpoint(
    request: Request,
    files: list[UploadFile] = File(...),
    rules_override: str | None = Form(None),
):
    client_ip = request.client.host if request.client else "unknown"
    _check_rate_limit(client_ip, "extract-interior")
    # M5: per-user daily Vision spend cap (when configured)
    _user = _auth.get_current_user(request)
    _check_user_spend_cap(_user["id"] if _user else None)

    if not files:
        raise HTTPException(status_code=400, detail="Nepateikta jokio failo")
    pdf_bytes = await files[0].read()
    validation = _validate_pdf_upload(pdf_bytes, files[0].filename or "")

    overrides_dict: dict | None = None
    if rules_override:
        try:
            overrides_dict = json.loads(rules_override)
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"rules_override JSON klaida: {e}")

    log.info("extract-interior-stream: ip=%s file=%s size=%dKB pages=%d",
             client_ip, files[0].filename, len(pdf_bytes) // 1024,
             validation.get("page_count", 0))
    from extractor import extract_interior_stream

    def _format_sse(ev: dict) -> bytes:
        return f"data: {json.dumps(ev, ensure_ascii=False)}\n\n".encode("utf-8")

    async def event_source():
        # Push file-validation warning early so the UI can show it before pass-1.
        if validation.get("warning"):
            yield _format_sse({
                "event": "validation_warning",
                "message": validation["warning"],
                "page_count": validation.get("page_count", 0),
            })

        loop = asyncio.get_event_loop()
        gen = extract_interior_stream(pdf_bytes, overrides_dict)

        # Bridge the sync generator to async — pull items in a worker thread
        # one-at-a-time so cancellations propagate quickly.
        sentinel = object()
        while True:
            try:
                ev = await loop.run_in_executor(None, lambda: next(gen, sentinel))
            except Exception as exc:
                yield _format_sse({"event": "error", "message": str(exc)})
                yield _format_sse({"event": "done", "result": {
                    "status": "error", "_error": str(exc),
                }})
                return
            if ev is sentinel:
                return

            # Augment terminal event with the page-count warning the same way
            # the non-streaming endpoint does, so the UI banner still fires.
            if ev.get("event") == "done" and isinstance(ev.get("result"), dict):
                result = ev["result"]
                if validation.get("warning"):
                    existing = result.get("warnings") or []
                    existing.append({"level": "WARN", "message": validation["warning"]})
                    result["warnings"] = existing
                    if isinstance(result.get("lt_sanity"), dict):
                        ls = result["lt_sanity"]
                        ls.setdefault("warnings", []).append({
                            "level": "WARNING", "message": validation["warning"], "room": ""
                        })
                        ls["summary"]["warnings_count"] = ls["summary"].get("warnings_count", 0) + 1
                        ls["summary"]["warnings"] = ls["summary"].get("warnings", 0) + 1
                    result["_pdf_page_count"] = validation.get("page_count", 0)

            yield _format_sse(ev)

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering
            "Connection": "keep-alive",
        },
    )


# ── /recompute-interior — pure-math recompute with new rules_override ───────
# (Phase 10 — AssumptionsPanel reactivation. No Vision call, no PDF re-render.
# User edits per-paskirtis preferences in the UI; we re-apply formulas to the
# already-extracted patalpos[]. Sub-second roundtrip vs minutes for full re-extract.)

class RecomputePayload(BaseModel):
    patalpos: list[dict]
    rules_override: dict = Field(default_factory=dict)
    # Optional per-room overrides keyed by patalpa.nr (e.g. force tile vs parquet)
    per_room_overrides: dict = Field(default_factory=dict)
    archetipas: str | None = None
    bendras_plotas_m2: float | None = None


@app.post("/recompute-interior")
async def recompute_interior(payload: RecomputePayload):
    """Re-apply universal formulas + user overrides to already-extracted patalpos.

    Returns the same shape as /extract-interior (sans _meta zoom/cost stats).
    Used by AssumptionsPanel — user edits a toggle, we recompute synchronously.
    """
    from extractor.universal_rules import (
        calc_room_quantities, normalize_paskirtis,
        ROOM_TYPE_RULES, translate_user_prefs_to_room_rules, UNIVERSAL_RULES,
    )

    rules = translate_user_prefs_to_room_rules(payload.rules_override) or {}

    # Per-room overrides (e.g. force koridorius floor=tile)
    per_room = payload.per_room_overrides or {}

    out_rooms: list[dict] = []
    for room in payload.patalpos:
        # Preserve Vision-emitted fields we don't recompute
        preserved = {
            "nr": room.get("nr"),
            "pavadinimas": room.get("pavadinimas"),
            "paskirtis": room.get("paskirtis"),
            "puslapio_nr": room.get("puslapio_nr"),
            "bbox_pct": room.get("bbox_pct"),
            "plotas_saltinis": room.get("plotas_saltinis"),
            "lubu_aukstis_saltinis": room.get("lubu_aukstis_saltinis"),
            "lubu_tipas": room.get("lubu_tipas"),
            "calculation_trace": room.get("calculation_trace"),
            "confidence": room.get("confidence"),
            "elementai": room.get("elementai"),
            "_zoom": room.get("_zoom"),
            "_zoom_changes": room.get("_zoom_changes"),
        }

        nr = room.get("nr") or ""
        room_override = per_room.get(nr) or {}

        # Rules for this paskirtis — start from translated, apply per-room override
        paskirtis = normalize_paskirtis(room.get("paskirtis") or "")
        rt_rules = dict((rules.get(paskirtis)
                         or ROOM_TYPE_RULES.get(paskirtis)
                         or ROOM_TYPE_RULES["gyvenamoji"]))
        # Per-room flags can flip floor type or paint
        if "tile_floor" in room_override:
            rt_rules["tile_floor"] = bool(room_override["tile_floor"])
        if "walls_paint" in room_override:
            rt_rules["walls_paint"] = float(room_override["walls_paint"])

        # Build a single-room rules dict that calc_room_quantities expects
        single_rules = {paskirtis: rt_rules}

        recalc = calc_room_quantities(room, rules=single_rules)

        merged = {**room, **recalc, **preserved}
        out_rooms.append(merged)

    # Recompute santrauka + emit V8-compat + lt_sanity mirror
    parsed = {
        "archetipas": payload.archetipas or "standart",
        "bendras_plotas_m2": payload.bendras_plotas_m2 or sum(
            r.get("plotas_m2", 0) for r in out_rooms
            if normalize_paskirtis(r.get("paskirtis") or "") not in ("garazas", "tamburas")
        ),
        "patalpos": out_rooms,
        "pozicijos": [],  # rebuilt below by emit_v8_compat? No — pozicijos come from Vision narrative
        "_overrides": payload.rules_override,
    }

    # Reuse extractor's post-processing helpers
    from extractor.vision_call import (
        _recompute_santrauka, _emit_v8_compat_fields,
    )
    from extractor.lt_rules import apply_lt_sanity

    parsed = _recompute_santrauka(parsed)
    parsed = apply_lt_sanity(parsed)

    # Emit lt_sanity:{warnings,summary} mirror so SanityWarningsBanner renders
    # (same mirror the main /extract-interior emits in step 4.1).
    flat_warnings = parsed.get("_lt_warnings") or []
    ui_warnings = []
    for w in flat_warnings:
        level = w.get("level", "INFO")
        if level == "WARN":
            level = "WARNING"
        ui_warnings.append({
            "level": level,
            "room": w.get("patalpa_nr") or w.get("room") or "",
            "field": w.get("field", ""),
            "value": w.get("value"),
            "expected": w.get("expected"),
            "message": w.get("message", ""),
        })
    n_err = sum(1 for w in ui_warnings if w["level"] == "ERROR")
    n_warn = sum(1 for w in ui_warnings if w["level"] == "WARNING")
    n_info = sum(1 for w in ui_warnings if w["level"] == "INFO")
    parsed["lt_sanity"] = {
        "warnings": ui_warnings,
        "summary": {
            "rooms_count": len(out_rooms),
            "total_area_m2": round(parsed.get("bendras_plotas_m2", 0), 1),
            "warnings_count": n_err + n_warn,
            "errors": n_err,
            "warnings": n_warn,
            "info": n_info,
        },
    }

    # Sprint §FIX (2026-04-29): use the FULL deterministic pozicijų generator
    # (~70+ lines per residential project) instead of the prior 13-line summary.
    # Earlier code was lossy: every Prielaidos toggle dropped 56→10 positions.
    # _build_pozicijos_from_rooms() reads parsed["_overrides"] (set above) for
    # NRM2/VOB/LT deduction standard + Q-level + paint class.
    from extractor.vision_call import _build_pozicijos_from_rooms
    try:
        parsed = _build_pozicijos_from_rooms(parsed)
    except Exception as exc:
        print(f"[recompute-interior] pozicijos build failed: {exc}")
        parsed["pozicijos"] = parsed.get("pozicijos") or []
    parsed = _emit_v8_compat_fields(parsed)
    parsed["status"] = "ok"
    parsed["_recomputed"] = True
    return parsed


@app.post("/v9/symbols/detect")
async def v9_symbols_detect(
    files: list[UploadFile] = File(...),
    symbol_type: str = Form(...),
    page_nr: int = Form(1),
):
    """V9 simbolių detection: surandam visus tipo simbolius (durys/langai/rozetes/...).

    symbol_type: durys | langai | rozetes | jungikliai | sviestuvai | trapai | radiatoriai
    """
    if not files:
        return {"status": "error", "error": "Nepateiktas PDF"}
    pdf_bytes = await files[0].read()

    try:
        from interior_v9 import detect_symbols
    except ImportError as e:
        return {"status": "error", "error": f"V9 import: {e}"}

    import asyncio
    loop = asyncio.get_running_loop()
    try:
        result = await loop.run_in_executor(
            None,
            lambda: detect_symbols(pdf_bytes, symbol_type, page_nr),
        )
    except Exception as e:
        return {"status": "error", "error": str(e)}

    return {"status": "ok", **result}


@app.post("/v9/symbols/detect-page")
async def v9_symbols_detect_page(
    files: list[UploadFile] = File(...),
    page_nr: int = Form(1),
    page_type: str = Form(""),
):
    """Detect all likely symbol types on one page in a single Vision call.

    Used by PlanViewer 'AI nuskaityti puslapį' button — bundles
    rozetes/jungikliai/sviestuvai/etc. detection so the user gets one
    response with all symbol types at once.
    """
    if not files:
        return {"status": "error", "error": "Nepateiktas PDF"}
    pdf_bytes = await files[0].read()

    try:
        from interior_v9 import (
            detect_symbols_bundled,
            list_symbol_types_for_page_type,
            SYMBOL_TYPES,
        )
    except ImportError as e:
        return {"status": "error", "error": f"V9 import: {e}"}

    symbol_types = list_symbol_types_for_page_type(page_type)
    if not symbol_types:
        # Default: electrical-plan symbols (most common interior project request).
        symbol_types = [
            "rozetes", "jungikliai", "sviestuvai", "pakabinami_sviestuvai",
            "led_juostos", "difuzoriai",
        ]
    symbol_types = [st for st in symbol_types if st in SYMBOL_TYPES]

    import asyncio
    loop = asyncio.get_running_loop()
    try:
        by_type = await loop.run_in_executor(
            None,
            lambda: detect_symbols_bundled(pdf_bytes, page_nr, symbol_types),
        )
    except Exception as e:
        return {"status": "error", "error": str(e)}

    if isinstance(by_type, dict) and by_type.get("_error"):
        return {"status": "error", "error": by_type["_error"]}
    summary = {st: info.get("count", 0) for st, info in (by_type or {}).items()}
    return {
        "status": "ok",
        "page_nr": page_nr,
        "page_type": page_type,
        "symbol_types": symbol_types,
        "by_type": by_type or {},
        "summary": summary,
    }


@app.post("/v9/symbols/count-by-template")
async def v9_symbols_count_by_template(
    files: list[UploadFile] = File(...),
    template_x_pct: float = Form(...),
    template_y_pct: float = Form(...),
    template_size_pct: float = Form(0.05),
    page_nr: int = Form(1),
):
    """Togal-style "click on symbol → count similar".

    Vartotojas paspauskite ant simbolio brėžinyje, sistema suranda visus panašius.
    """
    if not files:
        return {"status": "error", "error": "Nepateiktas PDF"}
    pdf_bytes = await files[0].read()

    try:
        from interior_v9 import count_symbols_by_template
    except ImportError as e:
        return {"status": "error", "error": f"V9 import: {e}"}

    import asyncio
    loop = asyncio.get_running_loop()
    try:
        result = await loop.run_in_executor(
            None,
            lambda: count_symbols_by_template(
                pdf_bytes, template_x_pct, template_y_pct,
                template_size_pct, page_nr,
            ),
        )
    except Exception as e:
        return {"status": "error", "error": str(e)}

    return {"status": "ok", **result}


@app.post("/pdf-lines")
async def pdf_lines(
    files: list[UploadFile] = File(...),
    page: int = Form(1),
    all_pages: str | None = Form(None),
):
    """Iš PDF puslapio ekstrahuoja vector linijas snap-to-lines įrankiui.

    Form:
      files: PDF failas (vienas)
      page: puslapio nr (1-indexed), default 1
      all_pages: "1" jei reikia visų puslapių (max 30)
    """
    if not files:
        return {"status": "error", "error": "Nepateiktas PDF"}
    pdf_bytes = await files[0].read()

    try:
        from interior_v8 import extract_lines_for_page, extract_lines_all_pages
    except ImportError as e:
        return {"status": "error", "error": str(e)}

    if all_pages == "1":
        result = extract_lines_all_pages(pdf_bytes, max_pages=30)
        result["status"] = "ok"
        return result

    result = extract_lines_for_page(pdf_bytes, page)
    result["status"] = "ok"
    return result


def _build_chat_context(project: dict) -> dict:
    """Build comprehensive grounded context for /chat-project from a full project dict.

    Includes EVERYTHING the AI needs to answer LT estimator questions accurately:
    - Project metadata (name, archetipas, bendras_plotas, status)
    - Per-room: all geometric + finishing fields + calc traces + zoom audit + warnings
    - Per-position: skyrius/aprašymas/vnt/kiekis/saltinis (LT-style pozicijos)
    - Santrauka totals (every metric)
    - lt_sanity warnings (so AI can answer "ar yra warning'ų?")

    Internal cost/savikaina (_meta tokens, cache stats, cost_eur) is REDACTED
    before injection — AI must never reveal extraction cost to end users
    (retail pricing TBD; current numbers are internal API cost only).
    """
    rooms = project.get("v8_rooms") or project.get("patalpos") or []
    pozicijos = project.get("pozicijos") or []
    darbai = project.get("darbu_sarasas") or []
    sanity = project.get("lt_sanity") or {}

    return {
        "projektas": {
            "pavadinimas": project.get("name") or project.get("projektas"),
            "archetipas": project.get("archetipas"),
            "tipas": project.get("tipas"),
            "bendras_plotas_m2": project.get("bendras_plotas_m2"),
            "status": project.get("status"),
            "vat_rate": project.get("vat_rate", 21),
        },
        "patalpos": [
            {
                "nr": r.get("nr"),
                "pavadinimas": r.get("pavadinimas"),
                "paskirtis": r.get("paskirtis"),
                "puslapis": r.get("puslapio_nr"),
                "plotas_m2": r.get("plotas_m2"),
                "plotas_saltinis": r.get("plotas_saltinis"),
                "perimetras_m": r.get("perimetras_m"),
                "lubu_aukstis_m": r.get("lubu_aukstis_m"),
                "lubu_tipas": r.get("lubu_tipas"),
                "dazymo_plotas_m2": r.get("dazymo_plotas_m2"),
                "kampu_metrai": r.get("kampu_metrai"),
                "angokrasciu_gkp_m": r.get("angokrasciu_gkp_m"),
                "pasleptu_duru_staktu_m": r.get("pasleptu_duru_staktu_m"),
                "nisu_metrai": r.get("nisu_metrai"),
                "plyteles_grindys_m2": r.get("plyteles_grindys_m2"),
                "plyteles_sienos_m2": r.get("plyteles_sienos_m2"),
                "plyteles_sienos_aukstis_m": r.get("plyteles_sienos_aukstis_m"),
                "pvc_grindys_m2": r.get("pvc_grindys_m2"),
                "isliginamasis_m2": r.get("isliginamasis_m2"),
                "grindjuosciu_m": r.get("grindjuosciu_m"),
                "hidroizoliacija_m2": r.get("hidroizoliacija_m2"),
                "elementai": r.get("elementai"),
                "calculation_trace": r.get("calculation_trace"),
                "confidence": r.get("confidence"),
                "_zoom_changes": r.get("_zoom_changes"),
                "pastabos": r.get("pastabos"),
            }
            for r in rooms[:50]
        ],
        "santrauka": project.get("santrauka") or project.get("v8_totals") or {},
        "pozicijos": [
            {
                "skyrius": p.get("skyrius"),
                "aprasymas": p.get("aprasymas"),
                "vnt": p.get("vnt"),
                "kiekis": p.get("kiekis"),
                "pastaba": p.get("pastaba"),
                "saltinis": p.get("saltinis"),
            }
            for p in pozicijos[:100]
        ],
        # darbu_sarasas mirror — frontend uses both names; AI may match either
        "darbai": [
            {
                "skyrius": it.get("skyrius"),
                "aprasymas": it.get("aprasymas"),
                "vnt": it.get("mato_vnt") or it.get("vnt"),
                "kiekis": it.get("kiekis"),
            }
            for it in (darbai or pozicijos)[:100]
        ],
        "warnings": [
            {"level": w.get("level"), "room": w.get("room"), "message": w.get("message")}
            for w in (sanity.get("warnings") or [])[:30]
        ],
        "warnings_summary": sanity.get("summary"),
        # _meta with token/cost fields STRIPPED. We share elapsed_s + model name
        # only — these are OK to discuss. tokens/cache/cost_eur are internal
        # savikaina, never revealed to end users.
        "_meta_safe": {
            "elapsed_s": (project.get("_meta") or {}).get("elapsed_s"),
            "pages_sent": (project.get("_meta") or {}).get("pages_sent"),
            "zoom_attempted": (project.get("_meta") or {}).get("zoom_attempted"),
            "zoom_applied": (project.get("_meta") or {}).get("zoom_applied"),
            "model": (project.get("_meta") or {}).get("model"),
        },
        "_overrides": project.get("_overrides") or {},
    }


_CHAT_SYSTEM_PROMPT = """Tu esi profesionalaus LT vidaus apdailos sąmatininko AI padėjėjas.

Tavo tikslas — tiksliai atsakyti į vartotojo klausimus apie KONKRETŲ projektą,
remiantis pateiktais duomenimis. Niekada neišgalvok skaičių, niekada
nehallucinuok. Jei duomenų neužtenka — aiškiai pasakyk.

Atsakymo principai:
- LIETUVIŠKAI
- Konkrečiai: nurodyk patalpos numerį, pavadinimą, kiekius
- Glaustai: 1-4 sakiniai. Tik jei klausia detalių — ilgesni.
- Cituok duomenis: "Pagal eksplikaciją 02 Vonia turi 6.4 m²..."
- Kontekstas: jei klausia "kuriuose kambariuose plytelės?", patikrink
  `plyteles_sienos_m2 > 0` arba `plyteles_grindys_m2 > 0` per visas patalpas
- Skaičiavimai: jei klausia "kiek dažų reikės?", paimk dazymo_plotas_total
  iš santraukos arba sumuok per kambarius. Naudok formulę:
  `dažai_litrai = plotas × 1.8 / 9 m²/L` (pirmas sluoksnis × 1.8, ne 2.0)
- Warnings: jei klausia "kokie warning'ai?" arba "ar yra problemų?", paimk
  iš `warnings` array. Jei jų 0 — pasakyk "warning'ų nerasta".
- Patalpu rūšiavimas: paskirtis enum'as: gyvenamoji, miegamoji, virtuve, vonia,
  wc, san, koridorius, holas, drabuzine, katiline, skalbykla, valgomasis,
  tamburas, garazas, sandeliukas, kabinetas, terasa, lodzija
- Formulės šaltinis: NRM2 §29 (paint), §27 (floors). Plytelinė juosta
  vonia/wc default 2.0m. Atimame angas ≥1.0m². Mansardinis svoris STR 1.05.06.

PRIVATU — JOKIO KAINOS / SĄNAUDŲ ATSKLEIDIMO:
Jei vartotojas klausia "kiek kainavo?", "kokia AI savikaina?", "kiek tokenų?",
"kiek mokejau?", "ar brangu?" arba bet kokio panašaus klausimo apie sistemos
sąnaudas / API mokesčius / tokenų skaičių / savikainą — VISADA atsakyk:
"Sąnaudų informacija nepasiekiama. Galutinė paslaugos kaina nustatoma per
prenumeratą ar pagal tarifą — susisiekite su pardavimo komanda."
NIEKADA nepasakok apie input_tokens, output_tokens, cache_read, cost_eur,
$/M tokens, ar bet kokius API kaštus. Šie duomenys yra konfidencialūs.

Statybos kainos klausimai (vadinami klausimai "kiek kainuos sąmata", "kiek kainuos
medžiagos / darbai") — TAIP, atsakyk jei project'e yra `kaina` laukai darbu_sarasas
eilutėse. Tai vartotojo įvestos statybos kainos, ne AI savikaina.

Niekada nesakyk "neturiu prieigos prie projekto" — visi duomenys pateikti
JSON formatu user'io pranešime.
"""


@app.post("/chat-project")
async def chat_project(request: Request, payload: dict = Body(...)):
    """AI CHAT — vartotojas klausia natural language apie projektą.

    Payload variants:
    - {"project_id": "...", "question": "..."}                    (preferred — fetches fresh from DB)
    - {"project_id": "...", "messages": [{role, content}, ...]}   (with conversation history)
    - {"project_context": {...}, "question": "..."}               (legacy fallback — uses passed data)
    """
    user = _auth.require_user(request)
    _check_rate_limit(request.client.host if request.client else "unknown", "chat")

    question = (payload.get("question") or "").strip()
    history = payload.get("messages") or []  # [{role: "user"|"assistant", content: "..."}]
    project_id = payload.get("project_id")
    ctx = payload.get("project_context") or {}

    if not question and not history:
        return {"status": "error", "error": "Klausimas tuščias"}

    # If project_id provided, fetch fresh from DB (preferred — DB is source of truth).
    # Otherwise fall back to passed context (legacy frontend support).
    if project_id:
        user_filter = None if user.get("is_admin") else user["id"]
        full_project = db.get_project(project_id, user_id=user_filter)
        if not full_project:
            raise HTTPException(status_code=404, detail="Projektas nerastas")
    else:
        full_project = ctx
        if not full_project:
            return {"status": "error", "error": "Nepateiktas projektas"}

    grounded_ctx = _build_chat_context(full_project)
    ctx_json = json.dumps(grounded_ctx, ensure_ascii=False, indent=2)

    # Build messages: project context as first user turn (cached if repeated),
    # then prior history, then current question.
    messages: list[dict] = [
        {
            "role": "user",
            "content": f"Projekto duomenys:\n```json\n{ctx_json}\n```\n\n(Atsakyk į klausimą po šito.)",
        },
        {"role": "assistant", "content": "Suprantu projekto kontekstą. Klausk."},
    ]
    for m in history:
        if m.get("role") in ("user", "assistant") and m.get("content"):
            messages.append({"role": m["role"], "content": str(m["content"])})
    if question:
        messages.append({"role": "user", "content": question})

    log.info("chat: user=%s project=%s history_len=%d ctx_size=%dKB",
             user["id"], project_id or "(passed)", len(history), len(ctx_json) // 1024)

    loop = asyncio.get_running_loop()

    def _call():
        return client.messages.create(
            model="claude-opus-4-7",
            max_tokens=2000,
            system=_CHAT_SYSTEM_PROMPT,
            messages=messages,
        )

    try:
        msg = await loop.run_in_executor(None, _call)
        text = "".join(b.text for b in msg.content if hasattr(b, "text"))
        # Token usage logged for our analytics but NOT exposed to client.
        # We don't want to reveal AI savikaina to end users.
        usage = msg.usage
        log.info("chat-project tokens: in=%s out=%s",
                 getattr(usage, "input_tokens", 0), getattr(usage, "output_tokens", 0))
        return {"status": "ok", "answer": text}
    except Exception as e:
        log.exception("chat-project failed")
        return {"status": "error", "error": f"AI klaida: {e}"}


@app.post("/export/excel")
async def export_excel_alias(request: Request, data: dict):
    return await generate_excel(request, data)

@app.post("/export/pdf")
async def export_pdf_alias(request: Request, data: dict):
    return await generate_pdf(request, data)



# ── /detect-scale-hint — Sprint G5 (2026-04-29) ──────────────────────────
# Scans PDF text layer for "M 1:50" / "1:100" / "Skalė 1:50" patterns and
# returns the suggested scale ratio. Frontend uses this to pre-fill the
# ScaleCalibrationModal so users don't have to eyeball it.

class DetectScalePayload(BaseModel):
    pdf_url: str | None = None  # data URL or backend-served URL
    pdf_b64: str | None = None  # base64-encoded PDF bytes


@app.post("/detect-scale-hint")
async def detect_scale_hint(payload: DetectScalePayload):
    """Returns {found: bool, page: int|null, scale_ratio: int|null, scale_text: str|null,
    confidence: 'high'|'medium'|'low'} after scanning PDF text layer for scale annotations."""
    import re as _re_local
    import base64
    import pdfplumber

    raw = None
    if payload.pdf_b64:
        try:
            raw = base64.b64decode(payload.pdf_b64)
        except Exception as e:
            return {"found": False, "error": f"base64 decode failed: {e}"}
    if not raw:
        return {"found": False, "error": "pdf_b64 required"}

    SCALE_PATTERNS = [
        # "M 1:50", "Skalė 1:100", "M1:50", "1:50"
        _re_local.compile(r"(?:^|[\s])M[\s]?1\s*:\s*(\d{2,4})\b", _re_local.IGNORECASE),
        _re_local.compile(r"Skal[ėe]\s*1\s*:\s*(\d{2,4})\b", _re_local.IGNORECASE),
        _re_local.compile(r"Mastelis\s*1\s*:\s*(\d{2,4})\b", _re_local.IGNORECASE),
        _re_local.compile(r"\b1\s*:\s*(50|75|100|125|150|200|250|500|1000)\b"),
    ]

    try:
        with pdfplumber.open(io.BytesIO(raw)) as pdf:
            for page_idx, page in enumerate(pdf.pages, 1):
                txt = page.extract_text() or ""
                for pat in SCALE_PATTERNS:
                    for m in pat.finditer(txt):
                        ratio = int(m.group(1))
                        if 20 <= ratio <= 2000:  # sanity
                            return {
                                "found": True,
                                "page": page_idx,
                                "scale_ratio": ratio,
                                "scale_text": f"1:{ratio}",
                                "confidence": "high" if pat is SCALE_PATTERNS[0] or pat is SCALE_PATTERNS[1] or pat is SCALE_PATTERNS[2] else "medium",
                            }
    except Exception as e:
        return {"found": False, "error": str(e)}
    return {"found": False, "page": None, "scale_ratio": None, "scale_text": None, "confidence": "low"}


# ── Phase C-3: click-to-fill walls (OpenCV flood-fill) ───────────────────────

@app.post("/api/click-to-fill")
async def click_to_fill_endpoint(
    request: Request,
    project_id: str = Form(...),
    page_nr: int = Form(...),
    click_x_pct: float = Form(...),
    click_y_pct: float = Form(...),
    sensitivity: float = Form(0.7),
    pdf_file: UploadFile | None = File(None),
):
    """Phase C-3 — server-side OpenCV flood-fill from a user's click.

    Accepts multipart form: project_id, page_nr, click coords, sensitivity,
    optional pdf_file. If pdf_file is provided, it's cached server-side for
    this project_id. Subsequent clicks for the same project can omit pdf_file
    and reuse the cached PDF (~1h TTL). Returns polygon in PDF point space.
    """
    _user = _auth.get_current_user(request)
    _check_rate_limit(
        request.client.host if request.client else "unknown",
        "click-to-fill",
    )

    from extractor.cv_polygon import (
        click_to_fill_pipeline, PolygonValidationError,
    )
    import page_raster_cache as _cache

    pdf_bytes: bytes | None = None
    if pdf_file is not None:
        pdf_bytes = await pdf_file.read()
        if pdf_bytes:
            _cache.store_pdf(project_id, pdf_bytes)
    if pdf_bytes is None:
        pdf_bytes = _cache.get_pdf(project_id)
    if pdf_bytes is None:
        raise HTTPException(
            status_code=400,
            detail=(
                "PDF byte cache nerasta — pridėkite pdf_file laukelį pirmoje "
                "click-to-fill užklausoje. Vėliau client'as gali kviesti be PDF."
            ),
        )
    if not pdf_bytes[:4].startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="pdf_file nėra galiojantis PDF")

    try:
        raster = _cache.render_grayscale_from_bytes(pdf_bytes, page_nr=page_nr)
    except Exception as e:
        log.exception("click-to-fill page render failed")
        raise HTTPException(status_code=500, detail=f"page render failed: {e}")

    try:
        result = click_to_fill_pipeline(
            raster=raster,
            click_x_pct=click_x_pct,
            click_y_pct=click_y_pct,
            sensitivity=sensitivity,
        )
    except PolygonValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # pdf2image with grayscale=True still returns 3-channel RGB on some PDFs
    # (depends on Poppler version + source PDF color profile). Take h,w from
    # the first 2 dims only.
    h, w = raster.shape[:2]
    px_to_pt = 72.0 / _cache.PAGE_RENDER_DPI
    polygon_pdf = [[float(x) * px_to_pt, float(y) * px_to_pt]
                   for x, y in result.polygon_px]
    page_width_pdf = float(w) * px_to_pt
    page_height_pdf = float(h) * px_to_pt

    log.info(
        "click-to-fill: project=%s page=%d click=(%.3f,%.3f) sens=%.2f "
        "vertices=%d confidence=%s user=%s",
        project_id, page_nr, click_x_pct, click_y_pct, sensitivity,
        len(polygon_pdf), result.confidence,
        (_user or {}).get("id", "anon"),
    )

    return {
        "polygon_pdf": polygon_pdf,
        "page_width_pdf": page_width_pdf,
        "page_height_pdf": page_height_pdf,
        "confidence": result.confidence,
        "fill_method": result.fill_method,
    }


# ── /health ───────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"status": "veikia"}
