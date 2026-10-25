"""/api/projects/{project_id}/geometry/… — the sheet scale with its provenance (plan 2026-10-24 §3.1, §3.4).

`POST …/geometry/scale-line` — the „Mastelis" gesture: the person drags a line over a dimension string such as
„4280". The string under the line is read from the PDF's text layer (`plan_dimensions.read_dimension_strings`; OCR on
a page with no text layer is a later task — the answer then says so), `m_per_pt = value_m / |p1 − p2|`, and the
scale is stored in `page_scales` (append-only; the newest row per page is in force). The geometry lane takes it as
its sheet's scale on the next read (`geometry_lane.apply_geometry` → `geometry.scale.user_scales_for_project`).

`GET …/geometry/scale?page=N` — the scale in force on a sheet and where it came from (`geometry.scale.scale_for_page`):
the person's line, the dimension strings on their hairlines, the strings matched to the walls, the written „M 1:xx",
a sibling sheet laid over it — or a blank with the reason.

The user's TOTALS calibration (`api/calibrate.py`) is a different thing and is untouched. No Vision call, no cost.
"""
from __future__ import annotations

import collections
import hashlib
import logging
import threading
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from api.free_reread import NO_PDF, _project_for

log = logging.getLogger("samatu.api.geometry")

router = APIRouter(prefix="/api/projects", tags=["geometry"])

_DIMS_CACHE: "collections.OrderedDict[bytes, list[dict]]" = collections.OrderedDict()
_DIMS_LOCK = threading.Lock()
_DIMS_KEEP = 4


class ScaleLine(BaseModel):
    page: int = Field(ge=1)
    p1: list[float] = Field(min_length=2, max_length=2)
    p2: list[float] = Field(min_length=2, max_length=2)
    # "display": points from the sheet's top-left, /Rotate applied — the frame the viewer and the strings use;
    # "pdf": the page's own user space (origin bottom-left, before /Rotate).
    frame: Literal["display", "pdf"] = "display"


def _pdf_of(project_id: str) -> bytes:
    from storage import get_storage, pdf_key
    try:
        pdf_bytes = get_storage().get(pdf_key(project_id))
    except Exception as exc:  # noqa: BLE001 — an R2 hiccup is a 502, not a 500
        log.warning("geometry pdf fetch failed for %s: %r", project_id, exc)
        raise HTTPException(status_code=502, detail="Nepavyko pasiekti brėžinio saugyklos")
    if not pdf_bytes:
        raise HTTPException(status_code=404, detail=NO_PDF)
    return pdf_bytes


def _all_strings(pdf_bytes: bytes) -> list[dict]:
    """Every dimension string of the drawing (the lane's one source), cached per drawing for the next GET."""
    from extractor.geometry_lane import geometry_dimension_strings
    key = hashlib.blake2b(pdf_bytes, digest_size=16).digest()
    with _DIMS_LOCK:
        hit = _DIMS_CACHE.get(key)
        if hit is not None:
            _DIMS_CACHE.move_to_end(key)
            return hit
    dims = geometry_dimension_strings(pdf_bytes)
    with _DIMS_LOCK:
        _DIMS_CACHE[key] = dims
        while len(_DIMS_CACHE) > _DIMS_KEEP:
            _DIMS_CACHE.popitem(last=False)
    return dims


def _page_size(pdf_bytes: bytes, page: int) -> tuple[float, float, int]:
    from extractor.pdf_vectors import page_geometry
    W, H, rot = page_geometry(pdf_bytes, page)
    if W <= 0 or H <= 0:
        raise HTTPException(status_code=400, detail="Tokio lapo brėžinyje nėra")
    return W, H, rot


def _to_display(pt: list[float], W: float, H: float, rotation: int) -> list[float]:
    """A point in the page's user space → the display frame (`pdf_vectors._to_display` takes the unrotated size)."""
    from extractor.pdf_vectors import _to_display as conv
    k = (int(rotation) // 90) % 4
    Wu, Hu = (H, W) if k % 2 else (W, H)
    x, y = conv(float(pt[0]), float(pt[1]), Wu, Hu, k)
    return [x, y]


@router.post("/{project_id}/geometry/scale-line")
def api_scale_line(request: Request, project_id: str, body: ScaleLine):
    _project_for(request, project_id)
    from main import _check_rate_limit, _client_key
    _check_rate_limit(_client_key(request), "geometry_scale")
    import auth as _auth
    import db as _db
    from extractor.plan_dimensions import read_dimension_strings
    from geometry.scale import scale_from_line

    pdf_bytes = _pdf_of(project_id)
    W, H, rot = _page_size(pdf_bytes, body.page)
    p1, p2 = list(body.p1), list(body.p2)
    if body.frame == "pdf":
        p1, p2 = _to_display(p1, W, H, rot), _to_display(p2, W, H, rot)
    try:
        dims = read_dimension_strings(pdf_bytes, pages=[body.page])
    except Exception as exc:  # noqa: BLE001 — an unreadable page has no text: say so, never 500
        log.warning("scale-line text read failed project=%s page=%s: %r", project_id, body.page, exc)
        dims = []
    if not dims:
        return {"status": "blank", "page": body.page,
                "reason": ("Šiame lape neradau matmenų teksto — brėžinys gali būti nuskenuotas. Matmens atpažinimas "
                           "iš paveikslėlio bus vėliau; kol kas mastelį nustatykite kitame to paties plano lape.")}
    sc, reason = scale_from_line(dims, p1, p2)
    if sc is None:
        return {"status": "blank", "page": body.page, "reason": reason}
    user = _auth.require_user(request)
    row = _db.add_page_scale(project_id, body.page, sc.m_per_pt, sc.source.value, sc.source_text,
                             details={k: v for k, v in sc.details.items()} | {"p1": p1, "p2": p2},
                             user_id=user.get("id"))
    sc.details["created_at"] = row["created_at"]
    return {"status": "ok", "page": body.page, "scale": sc.to_dict()}


@router.get("/{project_id}/geometry/scale")
def api_scale(request: Request, project_id: str, page: int = Query(ge=1)):
    _project_for(request, project_id)
    from main import _check_rate_limit, _client_key
    _check_rate_limit(_client_key(request), "geometry_scale")
    import db as _db
    from geometry.scale import ScaleContext, scale_for_page

    pdf_bytes = _pdf_of(project_id)
    _page_size(pdf_bytes, page)
    ctx = ScaleContext(pdf_bytes, dims=_all_strings(pdf_bytes), user_scales=_db.get_page_scales(project_id))
    sc = scale_for_page(ctx, page)
    return {"status": "ok" if sc.found else "blank", "page": page, "scale": sc.to_dict()}


@router.delete("/{project_id}/geometry/scale")
def api_scale_withdraw(request: Request, project_id: str, page: int = Query(ge=1)):
    """„Atšaukti" on the „Skaičius" tool: his scale line for the page stops being in force (a tombstone row in the
    append-only `page_scales`, db.withdraw_page_scale); answers the scale now in force with its provenance."""
    _project_for(request, project_id)
    from main import _check_rate_limit, _client_key
    _check_rate_limit(_client_key(request), "geometry_scale")
    import auth as _auth
    import db as _db
    from geometry.scale import ScaleContext, scale_for_page

    pdf_bytes = _pdf_of(project_id)
    _page_size(pdf_bytes, page)
    had = page in _db.get_page_scales(project_id)
    if had:
        _db.withdraw_page_scale(project_id, page, user_id=_auth.require_user(request).get("id"))
    ctx = ScaleContext(pdf_bytes, dims=_all_strings(pdf_bytes), user_scales=_db.get_page_scales(project_id))
    sc = scale_for_page(ctx, page)
    return {"status": "ok" if sc.found else "blank", "page": page, "atsaukta": had, "scale": sc.to_dict()}
