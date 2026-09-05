"""Sąmatų šablonai — the contractor's own layout, stored and rendered.

Week 2 of `plans/2026-09-04-contractor-trust-4-weeks.md`. Three jobs:

1. CRUD for the template itself (`GET`/`POST`/`DELETE /api/samata-templates`) —
   his section order and, per section, the families he bills. Derived by
   `extractor/samata_template.build_template` from his parsed sąmatas, or
   uploaded/edited by the client.
2. `POST /api/projects/{id}/samata-render` — a project rendered through a
   template. Pure: it reads the saved blob and returns rows, and writes
   NOTHING. The rendered sheet is a view of the project, not a second copy of
   it; persisting it would immediately go stale against the next recompute and
   give two answers to „kiek?".
3. The Excel export in his layout rides on `main.generate_excel` via
   `POST /export/excel?layout=template` — see that handler, not this file.

Ownership follows `api/price_lists` EXACTLY: every route is auth-gated and
scoped to the CALLER's own rows, admins included; a project is reached only
through `auth.require_owned_project`, never a raw `{URL_id}`-keyed read.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from starlette.concurrency import run_in_threadpool

import auth as _auth
import db as _db
from extractor.samata_template import (
    FILL_DONE, FILL_EMPTY, FILL_SUGGESTED, build_template, merge_samata,
    render_samata, validate_template,
)

log = logging.getLogger("pathon.samata_templates")

router = APIRouter(tags=["samata-templates"])

# A template is a few hundred short rows; 2 MB is already an order of magnitude
# more than his six sąmatas produce together.
MAX_BODY_BYTES = 2 * 1024 * 1024
MAX_TEMPLATES_PER_USER = 50
# A render body carries the client's darbu_sarasas WITH ledgers; a 150-row
# interior project is ~1 MB of that. Bounded rows keep the render CPU bounded.
RENDER_BODY_BYTES = 8 * 1024 * 1024
MAX_RENDER_ROWS = 5000


def _rate_limit_user(user: dict, endpoint: str) -> None:
    """Per-ACCOUNT bucket. Every write serialises on db.py's process-global
    _DB_LOCK, so a loop of large PUTs from one account is a self-inflicted stall
    no matter which address it arrives from — key on the one thing an
    authenticated caller cannot rotate."""
    try:
        from main import _check_rate_limit
    except Exception:  # noqa: BLE001 — limiter unavailable in unit-test apps
        return
    _check_rate_limit(f"user:{user.get('id') or 'unknown'}",
                      f"samata-templates-{endpoint}")


async def _read_json_body(request: Request, cap: int = MAX_BODY_BYTES) -> Any:
    """Bounded JSON body. `payload: dict = Body(...)` would buffer and parse
    every byte before a limit of ours could fire — the same F6 lesson
    `api/price_lists` documents."""
    try:
        from main import _read_body_capped
    except Exception as exc:  # noqa: BLE001 — no safe uncapped fallback exists
        log.error("body reader unavailable: %r", exc)
        raise HTTPException(status_code=500,
                            detail="Serverio klaida — bandykite vėliau") from exc
    raw = await _read_body_capped(request, cap)
    if not raw:
        raise HTTPException(status_code=400, detail="Tuščias užklausos turinys")
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
        raise HTTPException(status_code=400,
                            detail="Netinkamas užklausos turinys") from exc


async def _read_optional_json_body(request: Request, cap: int) -> Any:
    """Like `_read_json_body`, but an EMPTY body is `None`, not a 400 — the
    render is legal without one (it then reads the saved blob)."""
    try:
        from main import _read_body_capped
    except Exception as exc:  # noqa: BLE001
        log.error("body reader unavailable: %r", exc)
        raise HTTPException(status_code=500,
                            detail="Serverio klaida — bandykite vėliau") from exc
    raw = await _read_body_capped(request, cap)
    if not raw or not raw.strip():
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
        raise HTTPException(status_code=400,
                            detail="Netinkamas užklausos turinys") from exc


def _template_id(value: Any) -> str:
    """Ids are UUIDs, client-generated like a price list's. Refusing anything
    else keeps the primary key from becoming a free-text sink."""
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(status_code=400,
                            detail="Netinkamas šablono ID") from None


# ── CRUD ─────────────────────────────────────────────────────────────────────
# As with price lists, admins get NO cross-user access: there is no admin view
# of templates, and an asymmetry between list and delete is how an IDOR gets
# written by accident later.

@router.get("/api/samata-templates")
def api_list_templates(request: Request) -> dict[str, Any]:
    user = _auth.require_user(request)
    _rate_limit_user(user, "read")
    try:
        return {"samata_templates": _db.list_samata_templates(user_id=user["id"])}
    except Exception as exc:  # noqa: BLE001
        log.error("template read failed for user=%s: %r", user.get("id"), exc)
        raise HTTPException(status_code=500,
                            detail="Nepavyko nuskaityti šablonų") from exc


@router.post("/api/samata-templates")
async def api_upsert_template(request: Request) -> dict[str, Any]:
    """Create or replace one of the caller's templates.

    Body: `{id?, name?, is_default?, sections[], sources[]}` — an existing
    template's shape. Alternatively `{samatas: [<parsed sąmata>, …]}` derives one
    server-side (the path a new contractor takes: upload one priced sąmata → a
    template), and `{id, samatas: […]}` MERGES those sąmatas into the stored
    template, which is idempotent on the sąmata's own name.
    """
    user = _auth.require_user(request)
    payload = await _read_json_body(request)
    if not isinstance(payload, dict) or not payload:
        raise HTTPException(status_code=400, detail="Tuščias užklausos turinys")

    template_id = (_template_id(payload["id"])
                   if payload.get("id") is not None else str(uuid.uuid4()))

    samatas = payload.get("samatas")
    if samatas is not None:
        if not isinstance(samatas, list) or not samatas:
            raise HTTPException(
                status_code=400,
                detail="Laukas „samatas“ turi būti netuščias sąrašas")
        if any(not isinstance(s, dict) for s in samatas):
            raise HTTPException(status_code=400, detail="Netinkama sąmata")
        existing = _db.get_samata_template(template_id, user_id=user["id"])
        try:
            if existing:
                derived = {"version": 1, "name": existing.get("name"),
                           "sources": existing.get("sources") or [],
                           "n_projects": existing.get("n_projects") or 0,
                           "sections": existing.get("sections") or []}
                for samata in samatas:
                    derived = merge_samata(derived, samata)
            else:
                derived = build_template(
                    samatas,
                    name=str(payload.get("name") or "Rangovo šablonas"))
        except Exception as exc:  # noqa: BLE001
            log.warning("template derivation failed for user=%s: %r",
                        user.get("id"), exc)
            raise HTTPException(
                status_code=400,
                detail="Nepavyko sudaryti šablono iš pateiktų sąmatų") from exc
        payload = {**derived,
                   "name": payload.get("name") or derived.get("name"),
                   "is_default": payload.get("is_default")}

    try:
        clean = validate_template(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    clean["is_default"] = bool(payload.get("is_default"))
    if payload.get("created_date") or payload.get("created_at"):
        clean["created_date"] = payload.get("created_date") or payload.get("created_at")

    _rate_limit_user(user, "write")
    try:
        existing = _db.get_samata_template(template_id, user_id=user["id"])
        if existing is None:
            n = len(_db.list_samata_templates(user_id=user["id"]))
            if n >= MAX_TEMPLATES_PER_USER:
                raise HTTPException(
                    status_code=413,
                    detail=f"Per daug šablonų (daugiau nei "
                           f"{MAX_TEMPLATES_PER_USER}) — ištrinkite nenaudojamus.")
        # SQLite write behind the process-global _DB_LOCK — off the event loop,
        # since this handler had to become async to read its own body.
        return await run_in_threadpool(
            _db.upsert_samata_template, template_id, clean, user["id"])
    except PermissionError as exc:
        # 404, not 403 — never answer "does this id exist?" for a stranger, and
        # keep it symmetric with DELETE.
        log.warning("template write refused id=%s user=%s: %s",
                    template_id, user.get("id"), exc)
        raise HTTPException(status_code=404, detail="Šablonas nerastas") from exc
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        log.error("template write failed id=%s user=%s: %r",
                  template_id, user.get("id"), exc)
        raise HTTPException(status_code=500,
                            detail="Nepavyko išsaugoti šablono") from exc


@router.delete("/api/samata-templates/{template_id}")
def api_delete_template(request: Request, template_id: str) -> dict[str, Any]:
    user = _auth.require_user(request)
    _rate_limit_user(user, "write")
    try:
        deleted = _db.delete_samata_template(template_id, user_id=user["id"])
    except Exception as exc:  # noqa: BLE001
        log.error("template delete failed id=%s: %r", template_id, exc)
        raise HTTPException(status_code=500,
                            detail="Nepavyko ištrinti šablono") from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Šablonas nerastas")
    return {"deleted": template_id}


# ── Rendering a project through a template ───────────────────────────────────

def resolve_template(user: dict, template_id: str | None) -> dict:
    """The caller's template, by id or their default. 404 on anything else.

    Shared with `main.generate_excel`'s `layout=template` branch so both paths
    resolve ownership identically.
    """
    if template_id:
        template = _db.get_samata_template(template_id, user_id=user["id"])
    else:
        template = _db.get_default_samata_template(user_id=user["id"])
    if not template:
        raise HTTPException(
            status_code=404,
            detail="Šablonas nerastas — sudarykite jį iš savo sąmatos.")
    return template


def render_summary(rows: list[dict]) -> dict[str, int]:
    """What the sheet says at a glance — the numbers the UI puts above it."""
    template_rows = [r for r in rows if r.get("_sablonas")]
    return {
        "eilutes": len(rows),
        "sablono_eilutes": len(template_rows),
        "kitos_eilutes": len(rows) - len(template_rows),
        "uzpildyta": sum(1 for r in template_rows
                         if r.get("_pildymas") == FILL_DONE),
        "pasiulyta": sum(1 for r in template_rows
                         if r.get("_pildymas") == FILL_SUGGESTED),
        "tuscia": sum(1 for r in template_rows
                      if r.get("_pildymas") == FILL_EMPTY),
    }


@router.post("/api/projects/{project_id}/samata-render")
async def api_render_project(request: Request, project_id: str) -> dict[str, Any]:
    """Render one project in the contractor's layout. NO persistence.

    `?template_id=` picks the template; omitted, the caller's default (or their
    only) one is used. `?include_optional=0` drops the „kartais" families.

    The body is OPTIONAL. `{darbu_sarasas: [...], patalpos: [...]}` renders the
    rows the CLIENT is holding — what the contractor is looking at while his
    last edit is still on its way to the store (the frontend cache is
    write-through, so the saved blob lags a keystroke by a network round trip;
    rendering the blob made his typed number appear one edit late,
    2026-09-05). Without a body the saved blob is rendered. Either way nothing
    is written, and a body never widens access: ownership is checked first and
    the template is still the caller's own.
    """
    # Auth + ownership FIRST, before anything reads a {URL_id}-keyed store.
    user = _auth.require_owned_project(request, project_id)
    # A blob read plus a full render is real CPU behind a login, and it is a
    # POST a client can loop; same per-account bucket as the writes.
    _rate_limit_user(user, "read")
    template = resolve_template(user, request.query_params.get("template_id"))
    include_optional = request.query_params.get("include_optional") != "0"

    body = await _read_optional_json_body(request, RENDER_BODY_BYTES)
    rows_in: list | None = None
    rooms: list | None = None
    if body is not None:
        if not isinstance(body, dict):
            raise HTTPException(status_code=400, detail="Netinkamas užklausos turinys")
        if body.get("darbu_sarasas") is not None:
            if not isinstance(body["darbu_sarasas"], list):
                raise HTTPException(
                    status_code=400,
                    detail="Laukas „darbu_sarasas“ turi būti sąrašas")
            if len(body["darbu_sarasas"]) > MAX_RENDER_ROWS:
                raise HTTPException(status_code=413, detail="Per daug eilučių")
            rows_in = [r for r in body["darbu_sarasas"] if isinstance(r, dict)]
        if body.get("patalpos") is not None:
            if not isinstance(body["patalpos"], list):
                raise HTTPException(
                    status_code=400, detail="Laukas „patalpos“ turi būti sąrašas")
            rooms = [r for r in body["patalpos"] if isinstance(r, dict)]

    if rows_in is None or rooms is None:
        user_filter = None if user.get("is_admin") else user["id"]
        project = await run_in_threadpool(
            _db.get_project, project_id, user_id=user_filter)
        if project is None:                       # raced with a delete
            raise HTTPException(status_code=404, detail="Projektas nerastas")
        if project.get("_data_corrupt"):
            raise HTTPException(
                status_code=409,
                detail="Projekto duomenys sugadinti — susisiekite su mumis.")
        if rows_in is None:
            saved_rows = project.get("darbu_sarasas") or project.get("pozicijos") or []
            rows_in = saved_rows if isinstance(saved_rows, list) else []
        if rooms is None:
            saved_rooms = project.get("patalpos") or []
            rooms = saved_rooms if isinstance(saved_rooms, list) else []

    try:
        rows = await run_in_threadpool(
            render_samata, template, rows_in, rooms,
            include_optional=include_optional)
    except Exception as exc:  # noqa: BLE001
        log.error("samata render failed project=%s template=%s: %r",
                  project_id, template.get("id"), exc)
        raise HTTPException(status_code=500,
                            detail="Nepavyko sudaryti sąmatos pagal šabloną") from exc

    return {
        "eilutes": rows,
        "santrauka": render_summary(rows),
        "sablonas": {"id": template.get("id"), "name": template.get("name"),
                     "n_projects": template.get("n_projects")},
    }
