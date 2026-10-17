"""A second edition of the drawing, laid over the project's own (togal-v2 W10, comparison overlay).

    POST   /api/projects/{id}/pdf-revisions                        multipart `pdf_file` → the record +
                                                                   the saved project
    GET    /api/projects/{id}/pdf-revisions                        → the records, per old sheet
    DELETE /api/projects/{id}/pdf-revisions/{rid}                  → drops the file and the record
    GET    /api/projects/{id}/pdf-revisions/{rid}/pages/{n}/render?dpi=   PNG of the new edition's sheet n
    GET    /api/projects/{id}/pdf-revisions/{rid}/overlay/{page}?mode=skirtumas|naujas&dpi=
                                                                   transparent PNG in the PROJECT sheet's
                                                                   display frame (/Rotate applied)

The new PDF lives under its own storage key and never replaces the project's drawing (`pdf_key`). Every
sheet of it is matched to an old sheet by extractor/revision_alignment.match_revision; the record goes in
`_meta.brezinio_leidimai` through the ordinary save path, so it is a project version of its own.

„skirtumas" (the default): lines only in the new edition in the theme's evergreen, lines only in the old
one in muted clay, lines in both left out — composed on the server from the two renders, so the browser
lays one picture over the sheet and does no geometry. „naujas": the new edition's lines, evergreen. The
overlay is a picture: it changes no quantity.

Ownership is checked before anything else on every route; renders are rate-limited per user and cached
(the page renders on disk in cv_render_cache, the composed PNG in a small in-process LRU).
"""
from __future__ import annotations

import asyncio
import io
import logging
import threading
import time
import uuid
from collections import OrderedDict

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response

import db as _db
from api.free_reread import _project_for
from extractor import user_text

log = logging.getLogger("samatu.pdf_revisions")

router = APIRouter(prefix="/api/projects", tags=["pdf-revisions"])

MAX_PDF_BYTES = 200 * 1024 * 1024
MAX_DPI = 150
MIN_DPI = 48
MODES = ("skirtumas", "naujas")
INK = 245                         # anything darker than paper is drawn: walls are often light grey fills (0,91)
FORGIVE_PX = 2                    # a line moved less than this (anti-aliasing, rounding) is not a change
NAUJA_RGB = (47, 107, 79)         # --primary evergreen (index.css), the „nauja" tint
ISBRAUKTA_RGB = (176, 92, 70)     # muted clay, the „išbraukta" tint
NO_PDF = "Projekto brėžinio saugykloje nėra — palyginti galima tik įkėlus pirmąjį brėžinį."
NO_REVISION = "Tokio brėžinio leidimo nėra"
NO_SHEET = "Šis lapas naujame leidime neturi atitikmens"
UPLOADED = "Įkeltas naujas brėžinio leidimas"
REMOVED = "Pašalintas brėžinio leidimas"

_PNG_CACHE: "OrderedDict[tuple, bytes]" = OrderedDict()
_PNG_CACHE_MAX = 24
_PNG_LOCK = threading.Lock()


def revision_key(project_id: str, rid: str) -> str:
    return f"projects/{project_id}/revisions/{rid}.pdf"


def revision_prefix(project_id: str) -> str:
    return f"projects/{project_id}/revisions/"


def _owner_filter(request: Request) -> str | None:
    import auth as _auth
    user = _auth.require_user(request)
    return None if user.get("is_admin") else user["id"]


def _records(project: dict) -> list[dict]:
    meta = project.get("_meta") if isinstance(project.get("_meta"), dict) else {}
    recs = meta.get("brezinio_leidimai")
    return [r for r in recs if isinstance(r, dict) and r.get("id")] if isinstance(recs, list) else []


def _record(project: dict, rid: str) -> dict:
    for r in _records(project):
        if r["id"] == rid:
            return r
    raise HTTPException(status_code=404, detail=NO_REVISION)


def _served(rec: dict) -> dict:
    """The record as the screen gets it: the file name scrubbed like any prose, plus the sheets keyed by
    the OLD sheet (what the viewer is on) with the best new sheet for it."""
    out = dict(rec)
    out["pavadinimas"] = user_text.scrub_text(str(rec.get("pavadinimas") or ""), fallback="Naujas leidimas") \
        or "Naujas leidimas"
    by_old: dict[str, dict] = {}
    for n, lapas in (rec.get("lapai") or {}).items():
        if not isinstance(lapas, dict):
            continue
        key = str(lapas.get("old_page"))
        cur = by_old.get(key)
        mine = (lapas.get("budas") == "sienos", lapas.get("sutapimas") or 0.0)
        if cur is None or mine > (cur["budas"] == "sienos", cur.get("sutapimas") or 0.0):
            by_old[key] = {"naujas_lapas": int(n), **{k: lapas.get(k) for k in ("budas", "sutapimas", "geriausias")}}
    out["pagal_sena"] = by_old
    return out


def _storage():
    from storage import get_storage
    return get_storage()


def _get_pdf(key: str, missing: str) -> bytes:
    try:
        data = _storage().get(key)
    except Exception as exc:  # noqa: BLE001 — an R2 hiccup is a 502, not a 500
        log.warning("pdf-revisions storage read failed for %s: %r", key, exc)
        raise HTTPException(status_code=502, detail="Nepavyko pasiekti brėžinio saugyklos")
    if not data:
        raise HTTPException(status_code=404, detail=missing)
    return data


def _rate(request: Request, endpoint: str) -> None:
    from main import _check_rate_limit, _client_key
    _check_rate_limit(_client_key(request), endpoint)


def _save(project_id: str, project: dict, records: list[dict], user_filter: str | None, name: str) -> dict:
    meta = dict(project.get("_meta") or {}) if isinstance(project.get("_meta"), dict) else {}
    meta["brezinio_leidimai"] = records
    try:
        return _db.upsert_project(project_id, {**project, "_meta": meta}, user_id=user_filter,
                                  version_source="kita", version_name=name)
    except PermissionError:
        raise HTTPException(status_code=404, detail="Projektas nerastas")


# ── upload / list / delete ──────────────────────────────────────────────────

@router.post("/{project_id}/pdf-revisions")
async def upload_revision(request: Request, project_id: str, pdf_file: UploadFile = File(...)):
    project = _project_for(request, project_id)          # ownership before the body is looked at
    user_filter = _owner_filter(request)
    _rate(request, "pdf_revision_upload")
    data = await pdf_file.read()
    if not data or not data[:5].startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="Netinkamas PDF failas")
    if len(data) > MAX_PDF_BYTES:
        raise HTTPException(status_code=413, detail="Failas per didelis (max 200 MB)")
    from storage import pdf_key
    old = await asyncio.to_thread(_get_pdf, pdf_key(project_id), NO_PDF)
    from extractor.revision_alignment import match_revision
    try:
        lapai = await asyncio.to_thread(match_revision, old, data)
    except Exception as exc:  # noqa: BLE001 — a PDF PDFium cannot open
        log.warning("pdf-revisions alignment failed for %s: %r", project_id, exc)
        raise HTTPException(status_code=400, detail="Nepavyko perskaityti naujo brėžinio PDF")
    if not lapai:
        raise HTTPException(status_code=400, detail="Naujame PDF nėra lapų")
    rid = uuid.uuid4().hex[:12]
    try:
        await asyncio.to_thread(_storage().put, revision_key(project_id, rid), data, "application/pdf")
    except Exception as exc:  # noqa: BLE001
        log.warning("pdf-revisions persist failed for %s: %r", project_id, exc)
        raise HTTPException(status_code=502, detail="Nepavyko išsaugoti brėžinio")
    rec = {
        "id": rid,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "pavadinimas": (pdf_file.filename or "")[:160],
        "puslapiai": len(lapai),
        "dydis": len(data),
        "lapai": {str(n): v for n, v in sorted(lapai.items())},
    }
    saved = await asyncio.to_thread(_save, project_id, project, [*_records(project), rec], user_filter, UPLOADED)
    return {"leidimas": _served(rec), "project": user_text.scrub_prose(saved)}


@router.get("/{project_id}/pdf-revisions")
def list_revisions(request: Request, project_id: str):
    project = _project_for(request, project_id)
    return {"leidimai": [_served(r) for r in _records(project)]}


@router.delete("/{project_id}/pdf-revisions/{rid}")
def delete_revision(request: Request, project_id: str, rid: str):
    project = _project_for(request, project_id)
    user_filter = _owner_filter(request)
    _record(project, rid)
    saved = _save(project_id, project, [r for r in _records(project) if r["id"] != rid], user_filter, REMOVED)
    try:
        _storage().delete(revision_key(project_id, rid))
    except Exception as exc:  # noqa: BLE001 — the record is gone; the file is best-effort
        log.warning("pdf-revisions delete failed for %s/%s: %r", project_id, rid, exc)
    _forget(project_id, rid)
    return {"deleted": rid, "project": user_text.scrub_prose(saved)}


# ── renders ─────────────────────────────────────────────────────────────────

def _dpi(requested: int) -> int:
    return max(MIN_DPI, min(MAX_DPI, int(requested)))


def _gray(pdf: bytes, page: int, dpi: int):
    from extractor import cv_render_cache
    return cv_render_cache.render_page(pdf, page - 1, dpi)


def _page_count(pdf: bytes) -> int:
    import pypdfium2 as pdfium
    from extractor.pdfium_guard import PDFIUM_LOCK
    with PDFIUM_LOCK:
        doc = pdfium.PdfDocument(pdf)
        try:
            return len(doc)
        finally:
            doc.close()


def _png(rgba) -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.fromarray(rgba, mode="RGBA" if rgba.ndim == 3 else "L").save(buf, format="PNG", optimize=False)
    return buf.getvalue()


def compose_overlay(old_gray, new_gray, lapas: dict, dpi: int, mode: str):
    """RGBA (h, w, 4) uint8 in the OLD sheet's frame. Pure numpy/cv2 on two grayscale renders at `dpi`."""
    import cv2
    import numpy as np
    h, w = old_gray.shape[:2]
    s = dpi / 72.0
    k = float(lapas.get("k") or 1.0)
    m = np.float32([[k, 0, float(lapas.get("dx") or 0.0) * s], [0, k, float(lapas.get("dy") or 0.0) * s]])
    laid = cv2.warpAffine(new_gray, m, (w, h), flags=cv2.INTER_LINEAR, borderValue=255)
    new_ink = laid < INK
    out = np.zeros((h, w, 4), dtype=np.uint8)
    if mode == "naujas":
        out[new_ink] = (*NAUJA_RGB, 255)
        return out
    old_ink = old_gray < INK
    kernel = np.ones((2 * FORGIVE_PX + 1, 2 * FORGIVE_PX + 1), np.uint8)
    old_near = cv2.dilate(old_ink.astype(np.uint8), kernel) > 0
    new_near = cv2.dilate(new_ink.astype(np.uint8), kernel) > 0
    out[old_ink & ~new_near] = (*ISBRAUKTA_RGB, 255)
    out[new_ink & ~old_near] = (*NAUJA_RGB, 255)
    return out


def _cached(key: tuple, build) -> bytes:
    with _PNG_LOCK:
        hit = _PNG_CACHE.get(key)
        if hit is not None:
            _PNG_CACHE.move_to_end(key)
            return hit
    png = build()
    with _PNG_LOCK:
        _PNG_CACHE[key] = png
        while len(_PNG_CACHE) > _PNG_CACHE_MAX:
            _PNG_CACHE.popitem(last=False)
    return png


def _forget(project_id: str, rid: str | None = None) -> None:
    with _PNG_LOCK:
        for key in [k for k in _PNG_CACHE if k[0] == project_id and (rid is None or k[1] == rid)]:
            del _PNG_CACHE[key]


def _image(png: bytes) -> Response:
    return Response(content=png, media_type="image/png", headers={"Cache-Control": "private, max-age=600"})


@router.get("/{project_id}/pdf-revisions/{rid}/pages/{n}/render")
def render_revision_page(request: Request, project_id: str, rid: str, n: int, dpi: int = Query(110)):
    project = _project_for(request, project_id)
    _record(project, rid)
    _rate(request, "pdf_revision_render")
    dpi = _dpi(dpi)
    pdf = _get_pdf(revision_key(project_id, rid), NO_REVISION)
    if not (1 <= n <= _page_count(pdf)):
        raise HTTPException(status_code=404, detail="Tokio lapo nėra")
    return _image(_cached((project_id, rid, "render", n, dpi), lambda: _png(_gray(pdf, n, dpi))))


@router.get("/{project_id}/pdf-revisions/{rid}/overlay/{page}")
def revision_overlay(request: Request, project_id: str, rid: str, page: int,
                     mode: str = Query("skirtumas"), dpi: int = Query(96)):
    project = _project_for(request, project_id)
    rec = _record(project, rid)
    if mode not in MODES:
        raise HTTPException(status_code=400, detail="Nežinomas palyginimo būdas")
    match = _served(rec)["pagal_sena"].get(str(page))
    if not match:
        raise HTTPException(status_code=404, detail=NO_SHEET)
    _rate(request, "pdf_revision_overlay")
    dpi = _dpi(dpi)
    lapas = (rec.get("lapai") or {}).get(str(match["naujas_lapas"])) or {}

    def build() -> bytes:
        from storage import pdf_key
        old = _get_pdf(pdf_key(project_id), NO_PDF)
        new = _get_pdf(revision_key(project_id, rid), NO_REVISION)
        return _png(compose_overlay(_gray(old, page, dpi), _gray(new, match["naujas_lapas"], dpi), lapas, dpi, mode))

    return _image(_cached((project_id, rid, mode, page, dpi), build))
