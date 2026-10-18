"""Email verification and password reset (v3 W7-A M2, 2026-10-18).

Replaces the „Pamiršote slaptažodį?" mailto link with a real reset, and adds
the email check the 2026-09-29 audit asked for (backend-security-6, -9):

  POST /api/auth/forgot-password       {email}            → always the same answer
  POST /api/auth/reset-password        {token, new_password}
  POST /api/auth/verify-email          {token}
  POST /api/auth/resend-verification   {email}            → always the same answer
  GET  /api/auth/email-status          what the login page may offer

Tokens: 32 random bytes, only their SHA-256 stored (db.email_tokens), single
use (spent in the same UPDATE that checks them), reset 1 h, verification 48 h.
A reset spends every other open reset link, bumps session_version (every other
signed-in device is logged out) and counts as a verified inbox. At most
3 links per purpose per account per hour, on top of the per-IP rate limit.

The login gate is OFF unless SAMATU_REQUIRE_EMAIL_VERIFIED=1 — with it off,
login, register and Google sign-in behave as before except that Google's own
`email_verified` is now required (that check needs no mail service). Mail goes
through email_sender (console backend until SMTP_* is set).
"""
from __future__ import annotations

import logging
import os

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

import auth as _auth
import db
import email_sender

router = APIRouter(prefix="/api/auth", tags=["auth"])
log = logging.getLogger("pathon.auth_email")

RESET_TTL_S = 3600
VERIFY_TTL_S = 48 * 3600
MAX_LINKS_PER_HOUR = 3

# The answer to forgot-password / resend-verification, whoever asks: never says
# whether an account exists (the login route keeps the same rule).
GENERIC_SENT = ("Jei šiuo el. pašto adresu yra paskyra, išsiuntėme į jį nuorodą. "
                "Patikrinkite el. paštą (ir „Šlamšto“ aplanką). Nuoroda galioja ribotą laiką.")
LINK_INVALID = ("Ši nuoroda nebegalioja: ji jau panaudota, pasibaigė jos laikas arba "
                "nukopijuota ne visa. Paprašykite naujos nuorodos.")
NOT_VERIFIED = ("Jūsų el. pašto adresas dar nepatvirtintas. Atidarykite nuorodą laiške, "
                "kurį išsiuntėme registruojantis, arba paprašykite naujos nuorodos.")


def verification_required() -> bool:
    """The login gate: on only when SAMATU_REQUIRE_EMAIL_VERIFIED is exactly "1"."""
    return os.environ.get("SAMATU_REQUIRE_EMAIL_VERIFIED", "0") == "1"


def _production() -> bool:
    return (os.environ.get("ENV") or "").strip().lower() == "production"


def links_can_be_sent() -> bool:
    """True when an emailed link can reach the person: an SMTP relay is set, or
    this is development (the console backend prints the link to the log)."""
    return email_sender.is_configured() or not _production()


def app_url() -> str:
    return os.environ.get("PATHON_APP_URL", "http://localhost:5173").rstrip("/")


def _rate(request: Request, bucket: str) -> None:
    from main import _check_rate_limit, _client_key  # lazy: main imports this router
    _check_rate_limit(_client_key(request), bucket)


def _admin_allowlisted(email: str) -> bool:
    from main import _admin_allowlist
    return (email or "").lower() in _admin_allowlist()


def on_email_verified(user_id: str) -> None:
    """The inbox is proven: stamp it, and — audit backend-security-6 — only now
    let an address on the SAMATU_ADMIN_EMAIL allowlist become an admin."""
    db.mark_email_verified(user_id)
    user = db.get_user_by_id(user_id)
    if user and not user.get("is_admin") and _admin_allowlisted(user.get("email") or ""):
        db.set_user_admin(user_id, True)
        log.info("admin granted after email verification: user_id=%s", user_id)


def _send_link(user: dict, purpose: str) -> bool:
    """Mint one link and mail it, unless this account had MAX_LINKS_PER_HOUR
    already. Returns whether a message was handed to the mail backend."""
    if db.count_recent_email_tokens(user["id"], purpose, 3600) >= MAX_LINKS_PER_HOUR:
        log.info("email link throttled: user_id=%s purpose=%s", user["id"], purpose)
        return False
    if purpose == "reset":
        raw = db.create_email_token(user["id"], "reset", RESET_TTL_S)
        link = f"{app_url()}/slaptazodzio-keitimas?token={raw}"
        subject = "Slaptažodžio keitimas — Pathon"
        text = ("Sveiki,\n\ngavome prašymą pakeisti jūsų Pathon slaptažodį. Naują slaptažodį "
                f"nustatysite atidarę šią nuorodą:\n\n{link}\n\nNuoroda galioja 1 valandą ir "
                "tinka vieną kartą. Pakeitus slaptažodį, visuose kituose įrenginiuose iš "
                "paskyros būsite atjungti.\n\nJei prašymo nesiuntėte, šį laišką ištrinkite — "
                "slaptažodis liks toks pat.\n\nPathon\n")
    else:
        raw = db.create_email_token(user["id"], "verify", VERIFY_TTL_S)
        link = f"{app_url()}/el-pasto-patvirtinimas?token={raw}"
        subject = "Patvirtinkite el. pašto adresą — Pathon"
        text = ("Sveiki,\n\nkad patvirtintumėte šį el. pašto adresą savo Pathon paskyrai, "
                f"atidarykite nuorodą:\n\n{link}\n\nNuoroda galioja 48 valandas ir tinka vieną "
                "kartą.\n\nJei Pathon paskyros nekūrėte, šio laiško nepaisykite.\n\nPathon\n")
    return email_sender.send_email(user["email"], subject, text)


def send_verification(user: dict) -> bool:
    """Called by /api/auth/register. Never raises — a mail or token failure must
    not fail the registration (the person can ask for the link again)."""
    try:
        if user.get("email_verified_at"):
            return False
        return _send_link(user, "verify")
    except Exception as exc:  # noqa: BLE001
        log.warning("verification email failed for %s: %r", user.get("id"), exc)
        return False


class EmailBody(BaseModel):
    email: str


class TokenBody(BaseModel):
    token: str


class ResetBody(BaseModel):
    token: str
    new_password: str


def _active_user_by_email(raw_email: str) -> dict | None:
    try:
        email = _auth.validate_email(raw_email)
    except HTTPException:
        return None
    user = db.get_user_by_email(email)
    if not user or not user.get("is_active") or user.get("deleted_at"):
        return None
    return user


@router.get("/email-status")
def email_status() -> dict:
    """What the login page may offer: a reset form (a link can reach the person)
    or the old write-to-us fallback, and whether login waits for verification."""
    return {"links_can_be_sent": links_can_be_sent(),
            "verification_required": verification_required()}


@router.post("/forgot-password")
def forgot_password(body: EmailBody, request: Request) -> dict:
    _rate(request, "forgot-password")
    user = _active_user_by_email(body.email)
    if user and links_can_be_sent():
        try:
            _send_link(user, "reset")
        except Exception as exc:  # noqa: BLE001 — the answer stays the same
            log.warning("reset email failed for %s: %r", user["id"], exc)
    return {"status": "ok", "message": GENERIC_SENT}


@router.post("/resend-verification")
def resend_verification(body: EmailBody, request: Request) -> dict:
    _rate(request, "resend-verification")
    user = _active_user_by_email(body.email)
    if user and not user.get("email_verified_at") and links_can_be_sent():
        send_verification(user)
    return {"status": "ok", "message": GENERIC_SENT}


@router.post("/verify-email")
def verify_email(body: TokenBody, request: Request) -> dict:
    _rate(request, "verify-email")
    user_id = db.consume_email_token(body.token, "verify")
    if not user_id:
        raise HTTPException(status_code=400, detail=LINK_INVALID)
    on_email_verified(user_id)
    return {"status": "ok", "message": "El. pašto adresas patvirtintas. Galite prisijungti."}


@router.post("/reset-password")
# Plain `def`: bcrypt-12 hashing is ~180 ms of CPU (see /api/auth/register).
def reset_password(body: ResetBody, request: Request) -> dict:
    _rate(request, "reset-password")
    _auth.validate_password(body.new_password)  # 400 before the token is spent
    user_id = db.consume_email_token(body.token, "reset")
    if not user_id:
        raise HTTPException(status_code=400, detail=LINK_INVALID)
    user = db.get_user_by_id(user_id)
    if not user or not user.get("is_active") or user.get("deleted_at"):
        raise HTTPException(status_code=400, detail=LINK_INVALID)
    db.set_password_hash(user_id, _auth.hash_password(body.new_password))
    db.spend_email_tokens(user_id, "reset")
    db.bump_session_version(user_id)  # every other device signs in again
    on_email_verified(user_id)        # the link reached this inbox
    log.info("password reset for user_id=%s", user_id)
    return {"status": "ok", "message": "Slaptažodis pakeistas. Prisijunkite nauju slaptažodžiu."}
