"""HTTP API for the CV layer. Five endpoints:

  POST /api/cv/upload-pdf     — prime the PDF cache for a session
  POST /api/cv/match-template — click → count similar symbols on a page
  POST /api/cv/find-symbol    — box in PDF points → similar symbols on a page
                                (the viewer's „Rasti panašius"; shape score)
  POST /api/cv/magic-wand     — click → suggest room polygon
  POST /api/cv/record-decision — append accept/reject as training data

Each compute endpoint is thin: parse → load page from the in-memory
PDF cache → call CV layer → return. Heavy multi-page jobs (run match
across every floor plan) belong in a future RQ-backed batch route;
out of MVP scope.

PDFs come from `page_raster_cache._PDF_CACHE` (1h LRU). The frontend
primes the cache once via `/upload-pdf`; subsequent JSON calls reuse
it. On a cache miss the project's stored drawing (object storage, the
same bytes `/api/projects/{id}/pdf` serves) is loaded into the cache;
only when neither has it do compute endpoints return 409.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form
from pydantic import BaseModel, Field

import auth as _auth
import db as _db
import page_raster_cache as _pdf_cache

import time

import pypdfium2 as pdfium

from extractor.cv_match import (
    find_similar_symbols, find_symbol_by_shape, pt_box_to_px, px_box_to_pt,
    template_ink_px, search_dpi, ink_share, MIN_TEMPLATE_INK_PX, RASTER_INK_SHARE,
)
from extractor.pdfium_guard import PDFIUM_LOCK
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


class FindSymbolBody(BaseModel):
    project_id: str
    # 0-based, like the other /api/cv bodies. The template is cut from
    # template_page_idx and searched on page_idx (the same page by default).
    page_idx: int = Field(ge=0)
    template_page_idx: int | None = Field(default=None, ge=0)
    # [x0, y0, x1, y1] in TOP-LEFT mediabox PDF points (the viewer's measurement space).
    box_pt: list[float] = Field(min_length=4, max_length=4)
    min_score: float = Field(default=0.70, ge=0.5, le=0.99)
    max_results: int = Field(default=300, ge=1, le=500)


class MagicWandBody(BaseModel):
    project_id: str
    page_idx: int = Field(ge=0)
    click: list[int] = Field(min_length=2, max_length=2)
    close_kernel: int = 7
    dpi: int = 200


class RecordDecisionBody(BaseModel):
    project_id: str
    page_idx: int
    # One of the two: `bbox` = [x, y, w, h] raster pixels at `dpi` (the click
    # tools), or `box_pt` = [x0, y0, x1, y1] mediabox points (the box search,
    # converted server side so the viewer never does /Rotate pixel math).
    bbox: list[int] | None = Field(default=None, min_length=4, max_length=4)
    box_pt: list[float] | None = Field(default=None, min_length=4, max_length=4)
    klass: str = Field(pattern=KLASS_PATTERN)  # becomes a directory name
    decision: str  # "accept" | "reject"
    confidence: float | None = None
    source: str | None = Field(default=None, max_length=40)
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


def _stored_project_pdf(project_id: str) -> bytes | None:
    """The drawing the project was saved with (local disk or R2). Callers have
    already checked ownership. A storage hiccup reads as "not there" — the
    409 below then says what to do."""
    try:
        from storage import get_storage, pdf_key
        data = get_storage().get(pdf_key(project_id))
    except Exception:  # noqa: BLE001
        return None
    if not data or not data[:4].startswith(b"%PDF"):
        return None
    return data


def _load_project_pdf(project_id: str) -> bytes:
    pdf = _pdf_cache.get_pdf(project_id)
    if pdf is None:
        pdf = _stored_project_pdf(project_id)
        if pdf is not None:
            _pdf_cache.store_pdf(project_id, pdf)
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


def _pages_geometry(pdf: bytes, *page_idxs: int) -> list[tuple[float, float, int]]:
    """(width_pt, height_pt, /Rotate degrees) per requested page — the UNROTATED
    mediabox size, which is what the viewer's points are relative to. One PDFium
    parse for all of them."""
    with PDFIUM_LOCK:
        doc = pdfium.PdfDocument(pdf)
        try:
            n_pages = len(doc)
            out = []
            for idx in page_idxs:
                if idx >= n_pages:
                    raise HTTPException(400, f"Brėžinyje tik {n_pages} lap.")
                page = doc[idx]
                x0, y0, x1, y1 = page.get_mediabox()
                out.append((float(x1 - x0), float(y1 - y0), int(page.get_rotation() or 0) % 360))
        finally:
            doc.close()
    return out


def _page_geometry(pdf: bytes, page_idx: int) -> tuple[float, float, int]:
    return _pages_geometry(pdf, page_idx)[0]


@router.post("/find-symbol")
def find_symbol(
    body: FindSymbolBody,
    request: Request,
    user: dict = Depends(_auth.require_user),  # OpenCV only, no Anthropic call
) -> dict:
    """Box around one symbol → every similar one on a page, best first.

    Scores are a SHAPE agreement (chamfer, extractor/cv_match), not a
    probability. Everything above `min_score` comes back so the viewer's
    slider can filter without another call; the viewer decides what is shown."""
    _rate_limit(request, "find-symbol")
    _require_owned_project(user, body.project_id)  # ownership BEFORE body checks / compute
    x0, y0, x1, y1 = body.box_pt
    if not (x1 > x0 and y1 > y0) or x0 < 0 or y0 < 0:
        raise HTTPException(400, "Rėmelis turi būti [x0, y0, x1, y1], x1 > x0, y1 > y0")
    started = time.monotonic()
    pdf = _load_project_pdf(body.project_id)
    t_idx = body.page_idx if body.template_page_idx is None else body.template_page_idx
    (tw, th, trot), (pw, ph, prot) = _pages_geometry(pdf, t_idx, body.page_idx)
    if x1 > tw + 1 or y1 > th + 1:
        raise HTTPException(400, "Rėmelis už lapo ribų")
    if (x1 - x0) < 4 or (y1 - y0) < 4:
        raise HTTPException(400, "Rėmelis per mažas — apibrėžkite visą simbolį")
    if (x1 - x0) > tw * 0.25 or (y1 - y0) > th * 0.25:
        raise HTTPException(400, "Rėmelis per didelis — apibrėžkite vieną simbolį, ne plano dalį")
    # Both rasters at the SEARCH page's dpi, so the template's pixels are the same
    # size on paper as the page it is looked for on.
    dpi = search_dpi(pw, ph)
    template_raster = render_page(pdf, t_idx, dpi)
    bx, by, bw, bh = pt_box_to_px(body.box_pt, tw, th, trot,
                                  template_raster.shape[1], template_raster.shape[0])
    bx, by = max(0, bx), max(0, by)
    template = template_raster[by:by + bh, bx:bx + bw]
    if template.size == 0:
        raise HTTPException(400, "Rėmelis tuščias")
    if template_ink_px(template) < MIN_TEMPLATE_INK_PX:
        raise HTTPException(422, "Rėmelyje beveik nėra linijų — apibrėžkite patį simbolį")

    page = template_raster if body.page_idx == t_idx else render_page(pdf, body.page_idx, dpi)
    share = ink_share(page)
    raster = share > RASTER_INK_SHARE
    # On a raster/dark sheet every window scores alike (measured on objektas_g's
    # renders: ~200 "matches"); the search is not run and the answer says why.
    found = ({"candidates": [], "truncated": False} if raster else
             find_symbol_by_shape(page, template, min_score=body.min_score,
                                  max_results=body.max_results, dpi=dpi))
    rh, rw = page.shape[:2]
    candidates = []
    for c in found["candidates"]:
        box = px_box_to_pt(c["bbox"], pw, ph, prot, rw, rh)
        is_source = False
        if body.page_idx == t_idx:
            ix = max(0.0, min(box[2], x1) - max(box[0], x0))
            iy = max(0.0, min(box[3], y1) - max(box[1], y0))
            inter = ix * iy
            union = (box[2] - box[0]) * (box[3] - box[1]) + (x1 - x0) * (y1 - y0) - inter
            is_source = union > 0 and inter / union > 0.3
        candidates.append({
            "x": round((box[0] + box[2]) / 2, 2),
            "y": round((box[1] + box[3]) / 2, 2),
            "box_pt": box,
            "score": c["score"],
            "scale": c["scale"],
            "rotation": c["rotation"],
            "mirrored": c["mirrored"],
            "is_source": is_source,
        })
    return {
        "page_idx": body.page_idx,
        "template_page_idx": t_idx,
        "candidates": candidates,
        "truncated": found["truncated"],
        "min_score": body.min_score,
        "dpi": dpi,
        # Raster honesty: a sheet that is mostly "ink" (a render, a scan, a dark
        # background) makes every window look alike — say so, do not just list.
        "page_ink_share": round(share, 4),
        "skipped": "raster" if raster else None,
        "warning_lt": ("Lapas rastrinis arba tamsus — panašumų paieška nepatikima, šiame lape neieškota"
                       if raster else None),
        "elapsed_s": round(time.monotonic() - started, 2),
    }


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
    if (body.bbox is None) == (body.box_pt is None):
        raise HTTPException(400, "give exactly one of bbox / box_pt")
    pdf = _load_project_pdf(body.project_id)
    page = render_page(pdf, body.page_idx, body.dpi)
    if body.box_pt is not None:
        pw, ph, prot = _page_geometry(pdf, body.page_idx)
        x, y, w, h = pt_box_to_px(body.box_pt, pw, ph, prot, page.shape[1], page.shape[0])
    else:
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
            "bbox": [x, y, w, h],
            "box_pt": body.box_pt,
            "dpi": body.dpi,
            "confidence": body.confidence,
            "source": body.source,
        },
    )
    return {"status": "ok"}
