"""Company details + logo per user — GET/PUT /api/settings (2026-09-29).

The export header (company name, logo, company and PVM codes, IBAN, address,
default values) used to live only in the browser's `samatu_settings`. The auth
layer purges that key at every login and logout on purpose — the next person on
a shared browser must not inherit another company's details — so every
re-login silently took the logo, IBAN and codes out of his exports. This router
is the durable copy; the browser keeps a cache in front of it.

Both routes are signed-in only and ALWAYS scoped to the session's user id; no
user id is ever read from the request. The body must be a JSON object and is
stored and returned as given — the server does not interpret it. The logo is a
data URL inside that object, hence the 1.5 MB cap.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from starlette.concurrency import run_in_threadpool

import auth as _auth
import db as _db

log = logging.getLogger("pathon.user_settings")

router = APIRouter(prefix="/api/settings", tags=["settings"])

# The Settings page refuses a logo file over 500 KB, which is ~670 KB once
# base64-encoded; the text fields add a few KB. 1.5 MB leaves room without
# turning the row into a storage sink.
MAX_SETTINGS_BYTES = 1536 * 1024

_TOO_LARGE_LT = ("Įmonės duomenys per dideli (daugiau nei 1,5 MB). "
                 "Įkelkite mažesnį logotipą.")
_BAD_BODY_LT = "Netinkami įmonės duomenys — tikėtasi JSON objekto."


def _rate_limit_user(user: dict, endpoint: str) -> None:
    """Per-account bucket, same shape as the price-list writes: every write
    serialises on db._DB_LOCK, and an account id cannot be rotated the way an
    address can. Imported lazily — main includes this router."""
    try:
        from main import _check_rate_limit
    except Exception:  # noqa: BLE001 - limiter unavailable in unit-test apps
        return
    _check_rate_limit(f"user:{user.get('id') or 'unknown'}", f"settings-{endpoint}")


@router.get("")
def api_get_settings(request: Request) -> dict[str, Any]:
    user = _auth.require_user(request)
    try:
        return _db.get_user_settings(user["id"])
    except Exception as exc:  # noqa: BLE001
        log.error("settings read failed for user=%s: %r", user.get("id"), exc)
        raise HTTPException(status_code=500,
                            detail="Nepavyko nuskaityti įmonės duomenų") from exc


@router.put("")
async def api_put_settings(request: Request) -> dict[str, Any]:
    user = _auth.require_user(request)
    _rate_limit_user(user, "write")
    try:
        from main import _read_body_capped
    except Exception as exc:  # noqa: BLE001 - no safe uncapped fallback exists
        log.error("body reader unavailable: %r", exc)
        raise HTTPException(status_code=500,
                            detail="Serverio klaida — bandykite vėliau") from exc
    try:
        raw = await _read_body_capped(request, MAX_SETTINGS_BYTES)
    except HTTPException as exc:
        if exc.status_code == 413:
            raise HTTPException(status_code=413, detail=_TOO_LARGE_LT) from exc
        raise
    try:
        data = json.loads(raw) if raw else None
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=_BAD_BODY_LT) from exc
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail=_BAD_BODY_LT)
    try:
        updated_at = await run_in_threadpool(_db.put_user_settings, user["id"], data)
    except Exception as exc:  # noqa: BLE001
        log.error("settings write failed for user=%s: %r", user.get("id"), exc)
        raise HTTPException(status_code=500,
                            detail="Nepavyko išsaugoti įmonės duomenų") from exc
    return {"ok": True, "updated_at": updated_at}
