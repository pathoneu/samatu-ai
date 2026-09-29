"""HTTP API for the CV layer. Four endpoints:

  POST /api/cv/upload-pdf     — prime the PDF cache for a session
  POST /api/cv/match-template — click → count similar symbols on a page
  POST /api/cv/magic-wand     — click → suggest room polygon
  POST /api/cv/record-decision — append accept/reject as training data

Each compute endpoint is thin: parse → load page from the in-memory
PDF cache → call CV layer → return. Heavy multi-page jobs (run match
across every floor plan) belong in a future RQ-backed batch route;
out of MVP scope.

PDFs come from `page_raster_cache._PDF_CACHE` (1h LRU). The frontend
primes the cache once via `/upload-pdf`; subsequent JSON calls reuse
it. When the cache has evicted, compute endpoints return 409 so the
frontend can re-upload from local browser state.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form
from pydantic import BaseModel, Field

import auth as _auth
import db as _db
import page_raster_cache as _pdf_cache
from extractor.cv_match import find_similar_symbols
from extractor.cv_render_cache import render_page
from extractor.cv_wand import suggest_room_polygon
from extractor.training_data import KLASS_PATTERN, record_label

router = APIRouter(prefix="/api/cv", tags=["cv-tools"])


def _require_owned_project(user: dict, project_id: str) -> None:
    """N6 (2026-07-04 pentest, pass 2): F4 added require_billable_user to the
    /api/cv/* routes but no ownership check — so tenant A could drive CV compute
    against, and POISON the PDF cache + training data of, tenant B's project_id
    (the cache/record are keyed purely on project_id). Gate every route on
    ownership BEFORE any store_pdf / get_pdf / render / record. Admins bypass the
    filter; a missing or foreign project → 404 (never leak existence)."""
    user_filter = None if user.get("is_admin") else user["id"]
    if _db.get_project(project_id, user_id=user_filter) is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")


# 2026-07-27 audit (finding 8): /api/cv/upload-pdf read the whole upload into RAM
# with NO size cap — main.py's /extract path enforces MAX_PDF_SIZE_BYTES, this one
# didn't, so an authenticated user could push arbitrarily large bodies through it
# and into the process-wide PDF cache. Same limit, read in chunks so an oversize
# body is rejected BEFORE it is fully buffered.
_UPLOAD_CHUNK = 1024 * 1024
_MAX_PDF_BYTES_FALLBACK = 200 * 1024 * 1024  # mirrors main.MAX_PDF_SIZE_BYTES


def _max_pdf_bytes() -> int:
    """main.MAX_PDF_SIZE_BYTES, imported lazily (main includes this router, so a
    module-level import would be circular). Falls back to the same constant."""
    try:
        from main import MAX_PDF_SIZE_BYTES
        return int(MAX_PDF_SIZE_BYTES)
    except Exception:  # noqa: BLE001
        return _MAX_PDF_BYTES_FALLBACK


async def _read_capped(pdf_file: UploadFile) -> bytes:
    cap = _max_pdf_bytes()
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await pdf_file.read(_UPLOAD_CHUNK)
        if not chunk:
            break
        total += len(chunk)
        if total > cap:
            raise HTTPException(
                status_code=413,
                detail=(f"PDF failas per didelis (daugiau nei "
                        f"{cap // (1024 * 1024)} MB). Maksimumas "
                        f"{cap // (1024 * 1024)} MB."),
            )
        chunks.append(chunk)
    return b"".join(chunks)


def _rate_limit(request: Request, endpoint: str) -> None:
    """F4 (2026-07-04 pentest): the /api/cv/* endpoints render pages via OpenCV
    (CPU) and were fully unauthenticated — a DoS lever. They now require a
    billable user (via Depends); on top of that, key the shared sliding-window
    rate limiter (main._check_rate_limit) so one account can't loop the render.
    Imported lazily to avoid a circular import (main includes this router).
    Best-effort: never block a request on a limiter hiccup.

    2026-09-02 review: the key used to be `request.client.host`, which under
    production's ``--forwarded-allow-ips='*'`` is the LEFTMOST X-Forwarded-For
    value — supplied by the caller, so rotating it emptied the bucket every
    request. `main._client_key` takes the rightmost hop, the one our own proxy
    appends, which the caller cannot forge."""
    try:
        from main import _check_rate_limit, _client_key
    except Exception:
        return
    _check_rate_limit(_client_key(request), f"cv-{endpoint}")


class MatchTemplateBody(BaseModel):
    project_id: str
    page_idx: int = Field(ge=0)
    bbox: list[int] = Field(min_length=4, max_length=4)  # [x, y, w, h]
    threshold: float = 0.80
    dpi: int = 200


class MagicWandBody(BaseModel):
    project_id: str
    page_idx: int = Field(ge=0)
    click: list[int] = Field(min_length=2, max_length=2)
    close_kernel: int = 7
    dpi: int = 200


class RecordDecisionBody(BaseModel):
    project_id: str
    page_idx: int
    bbox: list[int]
    klass: str = Field(pattern=KLASS_PATTERN)  # becomes a directory name
    decision: str  # "accept" | "reject"
    confidence: float | None = None
    dpi: int = 200


@router.post("/upload-pdf")
async def upload_pdf(
    request: Request,
    project_id: str = Form(...),
    pdf_file: UploadFile = File(...),
    user: dict = Depends(_auth.require_user),  # OpenCV only, no Anthropic call
) -> dict:
    """Prime the PDF cache for a session. Frontend calls once before the
    first match-template / magic-wand request; subsequent JSON calls
    reuse the cached bytes. Same pattern as /v9/click-to-fill."""
    _rate_limit(request, "upload-pdf")
    _require_owned_project(user, project_id)  # N6: ownership BEFORE store_pdf
    pdf_bytes = await _read_capped(pdf_file)   # 413 before the bytes are buffered
    if not pdf_bytes or not pdf_bytes[:4].startswith(b"%PDF"):
        raise HTTPException(400, "pdf_file is not a valid PDF")
    _pdf_cache.store_pdf(project_id, pdf_bytes)
    return {"status": "ok", "size": len(pdf_bytes)}


def _load_project_pdf(project_id: str) -> bytes:
    pdf = _pdf_cache.get_pdf(project_id)
    if pdf is None:
        # Either the project doesn't exist OR the in-memory cache expired
        # (1h TTL). Frontend's job to re-upload from local state.
        raise HTTPException(
            status_code=409,
            detail=(
                "Project PDF not in server cache (expired or never "
                "uploaded). Re-upload before using CV tools."
            ),
        )
    return pdf


@router.post("/match-template")
def match_template(
    body: MatchTemplateBody,
    request: Request,
    user: dict = Depends(_auth.require_user),  # OpenCV only, no Anthropic call
) -> dict:
    _rate_limit(request, "match-template")
    _require_owned_project(user, body.project_id)  # N6: ownership BEFORE compute
    x, y, w, h = body.bbox
    if w <= 0 or h <= 0 or x < 0 or y < 0:
        raise HTTPException(400, "bbox must be positive [x, y, w, h]")
    pdf = _load_project_pdf(body.project_id)
    page = render_page(pdf, body.page_idx, body.dpi)
    if y + h > page.shape[0] or x + w > page.shape[1]:
        raise HTTPException(400, "bbox out of page bounds")
    template = page[y:y + h, x:x + w]
    candidates = find_similar_symbols(
        page, template, threshold=body.threshold,
    )
    return {"candidates": candidates, "page_size": list(page.shape[::-1])}


@router.post("/magic-wand")
def magic_wand(
    body: MagicWandBody,
    request: Request,
    user: dict = Depends(_auth.require_user),  # OpenCV only, no Anthropic call
) -> dict:
    _rate_limit(request, "magic-wand")
    _require_owned_project(user, body.project_id)  # N6: ownership BEFORE compute
    pdf = _load_project_pdf(body.project_id)
    page = render_page(pdf, body.page_idx, body.dpi)
    cx, cy = body.click
    if cx < 0 or cy < 0 or cy >= page.shape[0] or cx >= page.shape[1]:
        raise HTTPException(400, "click out of page bounds")
    polygon = suggest_room_polygon(
        page, cx, cy, close_kernel=body.close_kernel,
    )
    return {"polygon": polygon, "page_size": list(page.shape[::-1])}


@router.post("/record-decision")
def record_decision(
    body: RecordDecisionBody,
    request: Request,
    user: dict = Depends(_auth.require_user),  # OpenCV only, no Anthropic call
) -> dict:
    _rate_limit(request, "record-decision")
    _require_owned_project(user, body.project_id)  # N6: ownership BEFORE record
    if body.decision not in ("accept", "reject"):
        raise HTTPException(400, "decision must be 'accept' or 'reject'")
    pdf = _load_project_pdf(body.project_id)
    page = render_page(pdf, body.page_idx, body.dpi)
    x, y, w, h = body.bbox
    if w <= 0 or h <= 0 or x < 0 or y < 0:
        raise HTTPException(400, "bbox must be positive [x, y, w, h]")
    if y + h > page.shape[0] or x + w > page.shape[1]:
        raise HTTPException(400, "bbox out of page bounds")
    crop = page[y:y + h, x:x + w]
    if crop.size == 0:
        raise HTTPException(400, "bbox produced empty crop")
    record_label(
        klass=body.klass,
        decision=body.decision,
        crop=crop,
        meta={
            "project_id": body.project_id,
            "page_idx": body.page_idx,
            "bbox": body.bbox,
            "confidence": body.confidence,
        },
    )
    return {"status": "ok"}
