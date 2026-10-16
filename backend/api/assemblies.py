"""/api/assemblies — his „rinkiniai": what a work row is made of (togal-v2 W9).

An assembly binds to a darbu_sarasas line (`taikoma`) and lists its
components — materials by consumption norm per unit of the work row, waste,
labour, machinery — each with an optional unit price. Nothing here computes a
billed quantity: the engine's rows stay the truth, an assembly explains and
prices them (see `api/assemblies_default.py` and the
`…/rows/{row_id}/sudetis` route).

Two kinds:
  * his own — stored in the `assemblies` table, owner-scoped exactly like
    price lists (404 for someone else's id, never 403, so the API never tells
    a stranger that an id exists);
  * „numatyta" — built on every read from the engine's own constants by
    `assemblies_default.build_default_assemblies()`, id `numatyta-<slug>`,
    read-only (403 on PUT/DELETE: copy it first).

Ownership is checked BEFORE the body is read or validated, like every
project-scoped route (tests/test_route_ownership_policy.py).
"""
from __future__ import annotations

import logging
import math
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from starlette.concurrency import run_in_threadpool

import auth as _auth
import db as _db

log = logging.getLogger("samatu.assemblies")

router = APIRouter(prefix="/api/assemblies", tags=["assemblies"])

DEFAULT_PREFIX = "numatyta-"
RUSYS = ("medziaga", "darbas", "mechanizmai")
APVALINIMAI = ("aukstyn", "zemyn", "artimiausias")

MAX_BODY_BYTES = 256 * 1024
MAX_COMPONENTS = 60
MAX_NAME_LEN = 200
MAX_LABEL_LEN = 400
MAX_UNIT_LEN = 32
MAX_CODE_LEN = 32
MAX_ROW_IDS = 500
MAX_NUMBER = 1_000_000.0


def _rate_limit_user(user: dict, endpoint: str) -> None:
    """Per-account bucket, as price lists do (every write takes the db lock)."""
    try:
        from main import _check_rate_limit
    except Exception:  # noqa: BLE001 - limiter unavailable in unit-test apps
        return
    _check_rate_limit(f"user:{user.get('id') or 'unknown'}", f"assemblies-{endpoint}")


async def _read_json_body(request: Request) -> Any:
    from api.price_lists import _read_json_body_capped
    return await _read_json_body_capped(request, MAX_BODY_BYTES)


def _bad(detail: str) -> HTTPException:
    return HTTPException(status_code=400, detail=detail)


def _text(value: Any, field: str, cap: int, *, required: bool = False) -> str | None:
    if value is None or value == "":
        if required:
            raise _bad(f"Laukas „{field}“ privalomas")
        return None
    if not isinstance(value, str):
        raise _bad(f"Laukas „{field}“ turi būti tekstas")
    value = value.strip()
    if required and not value:
        raise _bad(f"Laukas „{field}“ privalomas")
    return value[:cap] or None


def _number(value: Any, field: str, *, lo: float = 0.0, hi: float = MAX_NUMBER,
            allow_none: bool = True) -> float | None:
    if value is None or value == "":
        if allow_none:
            return None
        raise _bad(f"Laukas „{field}“ privalomas")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _bad(f"Laukas „{field}“ turi būti skaičius")
    f = float(value)
    if not math.isfinite(f) or f < lo or f > hi:
        raise _bad(f"Laukas „{field}“ turi būti tarp {lo:g} ir {hi:g}")
    return f


def validate_assembly(payload: Any) -> dict[str, Any]:
    """The one shape we store. Unknown keys are dropped; every value bounded."""
    if not isinstance(payload, dict):
        raise _bad("Netinkamas rinkinys")
    taikoma_in = payload.get("taikoma") or {}
    if not isinstance(taikoma_in, dict):
        raise _bad("Laukas „taikoma“ turi būti objektas")
    row_ids = taikoma_in.get("eilutes_id") or []
    if not isinstance(row_ids, list) or len(row_ids) > MAX_ROW_IDS \
            or not all(isinstance(x, str) and 0 < len(x) <= 64 for x in row_ids):
        raise _bad("Laukas „taikoma.eilutes_id“ turi būti eilučių ID sąrašas")
    taikoma = {
        "aprasymas": _text(taikoma_in.get("aprasymas"), "taikoma.aprasymas", MAX_LABEL_LEN),
        "vnt": _text(taikoma_in.get("vnt"), "taikoma.vnt", MAX_UNIT_LEN),
        "eilutes_id": list(dict.fromkeys(row_ids)),
    }
    if not taikoma["aprasymas"] and not taikoma["eilutes_id"]:
        raise _bad("Nurodykite, kuriai eilutei rinkinys taikomas")

    komps_in = payload.get("komponentai") or []
    if not isinstance(komps_in, list):
        raise _bad("Laukas „komponentai“ turi būti sąrašas")
    if len(komps_in) > MAX_COMPONENTS:
        raise HTTPException(status_code=413,
                            detail=f"Rinkinyje per daug sudedamųjų dalių (daugiau nei {MAX_COMPONENTS})")
    komponentai = []
    for k in komps_in:
        if not isinstance(k, dict):
            raise _bad("Netinkama sudedamoji dalis")
        rusis = k.get("rusis")
        if rusis not in RUSYS:
            raise _bad("Sudedamosios dalies rūšis turi būti medžiaga, darbas arba mechanizmai")
        komponentai.append({
            "rusis": rusis,
            "pavadinimas": _text(k.get("pavadinimas"), "pavadinimas", MAX_NAME_LEN, required=True),
            "norma": _number(k.get("norma"), "norma", allow_none=False),
            "vnt": _text(k.get("vnt"), "vnt", MAX_UNIT_LEN),
            "atliekos_proc": _number(k.get("atliekos_proc"), "atliekos_proc", hi=100.0) or 0.0,
            "kaina": _number(k.get("kaina"), "kaina"),
            # Rounding the engine applies to whole units (sheets, tubes,
            # screws) — kept so a copied default still reproduces its row.
            "apvalinimas": k.get("apvalinimas") if k.get("apvalinimas") in APVALINIMAI else None,
            "minimumas": _number(k.get("minimumas"), "minimumas"),
        })
    return {
        "name": _text(payload.get("name"), "name", MAX_NAME_LEN, required=True),
        "skyrius": _text(payload.get("skyrius"), "skyrius", MAX_NAME_LEN),
        "taikoma": taikoma,
        "vnt": _text(payload.get("vnt"), "vnt", MAX_UNIT_LEN),
        "komponentai": komponentai,
        "kodas": _text(payload.get("kodas"), "kodas", MAX_CODE_LEN),
    }


def _defaults() -> list[dict]:
    from api.assemblies_default import build_default_assemblies
    return build_default_assemblies()


def _refuse_default(assembly_id: str) -> None:
    if str(assembly_id).startswith(DEFAULT_PREFIX):
        raise HTTPException(
            status_code=403,
            detail="Numatytas rinkinys keičiamas tik nukopijavus — „Kopijuoti ir keisti“")


def _check_owner_before_body(assembly_id: str, user: dict) -> bool:
    """True when the id exists (and is his). 404 for someone else's — checked
    before the body is read, so a stranger learns nothing from validation."""
    exists, owner = _db.assembly_owner(assembly_id)
    if exists and owner != user["id"]:
        raise HTTPException(status_code=404, detail="Rinkinys nerastas")
    return exists


@router.get("")
def api_list_assemblies(request: Request) -> dict[str, Any]:
    user = _auth.require_user(request)
    _rate_limit_user(user, "read")
    try:
        own = _db.list_assemblies(user_id=user["id"])
        from api.assemblies_default import SKYRIUS_KODAI
        # `kodai`: the section codes (skyrius_enum → kodas) a row falls back to,
        # so the browser and the exports share ONE table.
        return {"assemblies": own + _defaults(),
                "kodai": {k: v[0] for k, v in SKYRIUS_KODAI.items()}}
    except Exception as exc:  # noqa: BLE001
        log.error("assemblies read failed user=%s: %r", user.get("id"), exc)
        raise HTTPException(status_code=500, detail="Nepavyko nuskaityti rinkinių") from exc


@router.get("/{assembly_id}")
def api_get_assembly(request: Request, assembly_id: str) -> dict[str, Any]:
    user = _auth.require_user(request)
    if assembly_id.startswith(DEFAULT_PREFIX):
        for a in _defaults():
            if a["id"] == assembly_id:
                return a
        raise HTTPException(status_code=404, detail="Rinkinys nerastas")
    try:
        found = _db.get_assembly(assembly_id, user_id=user["id"])
    except Exception as exc:  # noqa: BLE001
        log.error("assembly read failed id=%s: %r", assembly_id, exc)
        raise HTTPException(status_code=500, detail="Nepavyko nuskaityti rinkinio") from exc
    if not found:
        raise HTTPException(status_code=404, detail="Rinkinys nerastas")
    return found


async def _write(request: Request, user: dict, assembly_id: str) -> dict[str, Any]:
    payload = validate_assembly(await _read_json_body(request))
    _rate_limit_user(user, "write")
    try:
        return await run_in_threadpool(_db.upsert_assembly, assembly_id, payload, user["id"])
    except PermissionError as exc:
        raise HTTPException(status_code=404, detail="Rinkinys nerastas") from exc
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        log.error("assembly write failed id=%s user=%s: %r", assembly_id, user.get("id"), exc)
        raise HTTPException(status_code=500, detail="Nepavyko išsaugoti rinkinio") from exc


@router.post("")
async def api_create_assembly(request: Request) -> dict[str, Any]:
    user = _auth.require_user(request)
    return await _write(request, user, str(uuid.uuid4()))


@router.put("/{assembly_id}")
async def api_update_assembly(request: Request, assembly_id: str) -> dict[str, Any]:
    user = _auth.require_user(request)
    _refuse_default(assembly_id)
    try:
        uuid.UUID(str(assembly_id))
    except ValueError:
        raise HTTPException(status_code=400, detail="Netinkamas rinkinio ID")
    _check_owner_before_body(assembly_id, user)
    return await _write(request, user, assembly_id)


@router.delete("/{assembly_id}")
def api_delete_assembly(request: Request, assembly_id: str) -> dict[str, Any]:
    user = _auth.require_user(request)
    _refuse_default(assembly_id)
    _rate_limit_user(user, "write")
    try:
        deleted = _db.delete_assembly(assembly_id, user_id=user["id"])
    except Exception as exc:  # noqa: BLE001
        log.error("assembly delete failed id=%s: %r", assembly_id, exc)
        raise HTTPException(status_code=500, detail="Nepavyko ištrinti rinkinio") from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Rinkinys nerastas")
    return {"deleted": assembly_id}
