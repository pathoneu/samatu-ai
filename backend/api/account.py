"""Account deletion — POST /api/account/delete (2026-10-05).

The privacy page and the terms say an account can be deleted from its
settings; nothing in the app could do it. This router does it, for the
signed-in account only — no user id is ever read from the request.

What goes, in this order:
  1. every project the user owns, one by one, through the same function his
     own DELETE /api/projects/{id} calls
     (project_purge.delete_project_and_files): the owner-scoped row delete —
     which takes the project's extraction archive and correction log with it
     (ON DELETE CASCADE) — then the best-effort purge of its drawing and every
     id-keyed store, held re-reads included. There is deliberately no second
     deletion policy here;
  2. the account itself, in one transaction (db.delete_account): the users row
     becomes a tombstone, and his company details, extraction-job records,
     price lists and sąmata templates are deleted. Every session is void;
  3. a sweep: a save still on its way from another open tab can re-create a
     project between 1 and 2. After 2 nothing can (db.upsert_project refuses a
     deleted owner), so one more pass leaves nothing behind.

What stays: issued invoices and the billing and cost ledgers, still pointing
at the tombstone's id (invoices must be kept by law), and the free-trial marker
keyed by company code. See db.delete_account.

Refused: an admin account (403); a confirmation that is not the account's
email (400); while one of his reads is running (409 — its ending could save a
project under the tombstone); and, only when billing is on, while a paid plan
is active or bought projects are unused (409, saying what to do first). With
billing off that check returns before reading anything.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

import auth as _auth
import db
import project_purge
from billing.flag import billing_enabled

log = logging.getLogger("pathon.account")

router = APIRouter(prefix="/api/account", tags=["account"])

_SUPPORT = "solutions@pathon.eu"

_MISMATCH_LT = ("Įrašytas el. paštas nesutampa su šios paskyros el. paštu. "
                "Paskyra neištrinta.")
_ADMIN_LT = ("Administratoriaus paskyros čia ištrinti negalima — ji reikalinga "
             "programai valdyti.")
_READING_LT = ("Dabar skaitomas jūsų brėžinys. Palaukite, kol skaitymas baigsis, "
               "ir bandykite dar kartą. Paskyra neištrinta.")
_PAID_PLAN_LT = ("Paskyros dar negalima ištrinti: galioja mokamas planas „{plan}“. "
                 f"Pirmiausia parašykite {_SUPPORT} — nutrauksime prenumeratą, kad "
                 "daugiau nebūtų nuskaičiuota. Tada paskyrą galėsite ištrinti čia.")
_CREDITS_LT = ("Paskyros dar negalima ištrinti: liko apmokėtų, bet nepanaudotų "
               "projektų: {n}. Ištrynus paskyrą jie dingtų. Panaudokite juos arba "
               f"parašykite {_SUPPORT}.")
_FAILED_LT = ("Paskyros ištrinti iki galo nepavyko — dalis projektų jau galėjo būti "
              "ištrinta. Bandykite dar kartą; jei nepavyks, parašykite "
              f"{_SUPPORT}.")


class AccountDeletePayload(BaseModel):
    # Any, not str: a missing or non-text value must come back as the plain
    # Lithuanian 400 below, not as pydantic's English 422.
    confirm: Any = None


def _rate_limit(request: Request) -> None:
    """The per-address bucket the other auth-sensitive routes use (login,
    register, change-password). Imported lazily — main includes this router."""
    try:
        from main import _check_rate_limit, _client_key
    except Exception:  # noqa: BLE001 - limiter unavailable in unit-test apps
        return
    _check_rate_limit(_client_key(request), "account-delete")


def _billing_blocker(user: dict) -> str | None:
    """Why the account cannot go yet because of something he paid for, or None
    when nothing paid would be lost. Billing off: returns before reading
    anything, so the flag-off path is what it was before this route existed."""
    if not billing_enabled():
        return None
    from billing.plans import PLAN_BY_ID
    plan_id = user.get("plan") or "free"
    # Anything short of 'canceled' can still charge him (past_due is retried).
    if plan_id != "free" and (user.get("plan_status") or "active") != "canceled":
        name = (PLAN_BY_ID.get(plan_id) or {}).get("name") or plan_id
        return _PAID_PLAN_LT.format(plan=name)
    credits = db.credits_balance(user["id"])
    if credits > 0:
        return _CREDITS_LT.format(n=credits)
    return None


def _delete_projects_of(user_id: str) -> int:
    """Every project the user owns (in the bin too — that is a flag on the
    project, not a separate place), each through the one project delete —
    always scoped to him. Returns how many were deleted."""
    return sum(1 for p in db.list_projects(user_id=user_id)
               if project_purge.delete_project_and_files(p["id"], user_id=user_id))


@router.post("/delete")
# Plain `def`: sqlite and object-storage deletes, all synchronous — the
# threadpool keeps them off the event loop.
def api_delete_account(request: Request,
                       payload: AccountDeletePayload | None = None) -> dict:
    user = _auth.require_user(request)
    _rate_limit(request)
    if user.get("is_admin"):
        raise HTTPException(status_code=403, detail=_ADMIN_LT)
    typed = payload.confirm if payload is not None else None
    email = (user.get("email") or "").strip().lower()
    if not isinstance(typed, str) or not email or typed.strip().lower() != email:
        raise HTTPException(status_code=400, detail=_MISMATCH_LT)
    blocker = _billing_blocker(user)
    if blocker:
        raise HTTPException(status_code=409, detail=blocker)
    uid = user["id"]
    if db.user_has_running_extraction(uid):
        raise HTTPException(status_code=409, detail=_READING_LT)

    # Until the tombstone commits, a failure leaves a live account he can
    # retry from (some projects may already be gone — the message says so).
    try:
        deleted = _delete_projects_of(uid)
        account_rows = db.delete_account(uid)
    except Exception as exc:  # noqa: BLE001
        log.exception("account deletion failed for user=%s", uid)
        raise HTTPException(status_code=500, detail=_FAILED_LT) from exc
    # After it, the account is gone whatever happens next: a failed sweep is
    # for the logs, not for a user who can no longer sign in to retry.
    try:
        deleted += _delete_projects_of(uid)
    except Exception:  # noqa: BLE001
        log.exception("account deletion: project sweep failed for user=%s", uid)
    # v3 M8: what is keyed by the account itself (per-owner architect legends).
    project_purge.purge_account_files(uid)
    # The session cookie is cleared in this response; every other session of
    # his died with the session_version bump in db.delete_account.
    request.session.clear()
    log.info("account deleted: user=%s projects=%d rows=%s",
             uid, deleted, account_rows)
    return {"deleted_projects": deleted}
