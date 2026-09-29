"""GET /api/projects/{project_id}/evidence — the pixels a number was read from.

WHY (2026-09-04, „AI shows its homework"). The room check sheet puts six facts
in front of the contractor — plotas, perimetras, aukštis, apdaila, angos,
grindys — and each one has to be checkable in the two seconds he is willing to
give it. A confidence dot is not checkable; the actual patch of drawing the
reader looked at is. So the fact carries a rectangle and this endpoint turns
that rectangle into a PNG.

Deliberately server-side. The 2026-05 attempt drew the eksplikacija row as a
canvas halo over the rendered page in the browser
(`EksplikacijaSourcePopover.jsx` still carries the post-mortem): the
bbox-to-canvas conversion drifted on real projects and flashed a yellow box in
arbitrary spots, which is worse than showing nothing. Here the crop is made
from the same PDF points the reader recorded, by the same process that recorded
them, so there is no coordinate boundary left to get wrong.

Two ways to ask:
    ?page=2&rect=0.11,0.42,0.38,0.44     — an explicit region, page-percent
    ?room=110                            — shorthand: that room's own region
                                           (polygon bounding box, else the
                                           printed room-number marker ± margin)

Everything is owner-scoped, rate-limited like the other heavy handlers, and
cached on disk keyed by (project, page, rect, dpi) under a byte cap — a render
is ~0,4 s of poppler and the check sheet asks for six of them per room.
"""
from __future__ import annotations

import hashlib
import io
import threading
import time
from collections import OrderedDict
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response

import auth as _auth
import db as _db
import storage as _storage
from extractor.room_facts import room_region_pct

log = logging.getLogger("samatu.evidence")

router = APIRouter(prefix="/api/projects", tags=["evidence"])

# 110 dpi renders an A3 landscape sheet at ~1820 px wide — enough that a
# table row is readable at 1:1 in the check sheet, cheap enough to make six
# of them while the contractor is still looking at the room.
DEFAULT_DPI = 110
MIN_DPI = 40
MAX_DPI = 160
# Poppler will happily rasterise an A0 sheet at 160 dpi into ~90 Mpx. Cap the
# LONG EDGE in pixels and derive a safe dpi from the page size instead.
MAX_PAGE_PX = 4000
# The returned crop, after cropping. Bigger than this is not more legible on a
# check-sheet card, it is just bytes.
MAX_CROP_PX = 1600
# A PLACE on the sheet (a table row, a pair of dimension strings, one room) is
# rendered on its own, at the resolution that makes it ~MAX_CROP_PX on its long
# edge — never below the requested dpi, never above this. Cut out of the
# 110–160 dpi whole-sheet raster the same place was 180–260 px wide, which is
# the „blurry" of the first real Patikra run (2026-09-17). PDFium renders only
# the region: 13 ms for a room on a real wall-painting sheet at 600 dpi.
REGION_MAX_DPI = 600
# A request for (nearly) the whole sheet keeps the pixel-capped page raster —
# it is what the enlarge dialog opens with, and it is shared between crops.
WHOLE_SHEET_SHARE = 0.6
# Part of every cache key: files written by an older renderer are never served
# again (the sweep removes them in time).
CACHE_VERSION = "v2"

# Padding around the requested rectangle, as a fraction of the page, so the
# crop carries enough context to be recognisable ("this is the eksplikacija
# table, and that is my row" rather than a floating number).
PAD_PCT = 0.012
# A table row is ~1 % of the page tall; without a floor the crop would be a
# 20 px sliver. These are the smallest crops that still read as a place.
MIN_CROP_W_PCT = 0.10
MIN_CROP_H_PCT = 0.045

CACHE_ROOT = _storage.data_path(
    "evidence_cache", Path(__file__).resolve().parents[1] / "data" / "evidence_cache")
# ~4000 crops at 60 KB. The cache is a pure optimisation: every entry can be
# re-rendered from the PDF, so eviction is never data loss.
CACHE_MAX_BYTES = 256 * 1024 * 1024
CACHE_SWEEP_TO = 0.8  # sweep down to this fraction of the cap
# The sweep walks the whole cache directory, and a contractor opening one
# project writes ~6 crops per room. Walking thousands of files on every one of
# those is the kind of cost that only shows up in production. Amortise it: the
# cache may overshoot by this many crops (a few MB against a 256 MB cap), which
# is not a number anyone can notice.
CACHE_SWEEP_EVERY = 50
_writes_since_sweep = 0


# ── request parsing ─────────────────────────────────────────────────────────

def _safe_project_id(project_id: str) -> str:
    """Reject anything that could escape the cache directory."""
    if not project_id or not all(c.isalnum() or c in ("-", "_") for c in project_id):
        raise HTTPException(status_code=400, detail="Netinkamas projekto ID")
    return project_id


def parse_rect(raw: str) -> list[float]:
    """"x0,y0,x1,y1" in page-percent → a validated, ordered rectangle.

    Degenerate input (a point, or a reversed edge) is normalised rather than
    rejected: a caller handing us the marker coordinate twice means "here",
    and the padding below turns that into a legible crop.
    """
    parts = [p.strip() for p in (raw or "").split(",")]
    if len(parts) != 4:
        raise HTTPException(status_code=400,
                            detail="rect turi būti x0,y0,x1,y1 (0–1)")
    try:
        vals = [float(p) for p in parts]
    except ValueError:
        raise HTTPException(status_code=400,
                            detail="rect reikšmės turi būti skaičiai 0–1")
    if any(v != v or v in (float("inf"), float("-inf")) for v in vals):
        raise HTTPException(status_code=400,
                            detail="rect reikšmės turi būti skaičiai 0–1")
    if any(not (-0.001 <= v <= 1.001) for v in vals):
        raise HTTPException(status_code=400,
                            detail="rect reikšmės turi būti nuo 0 iki 1")
    x0, y0, x1, y1 = (min(max(v, 0.0), 1.0) for v in vals)
    if x1 < x0:
        x0, x1 = x1, x0
    if y1 < y0:
        y0, y1 = y1, y0
    return [x0, y0, x1, y1]


def _padded(rect: list[float]) -> tuple[float, float, float, float]:
    """Grow the rectangle by PAD_PCT, then up to the legibility floor."""
    x0, y0, x1, y1 = rect
    x0, y0 = x0 - PAD_PCT, y0 - PAD_PCT
    x1, y1 = x1 + PAD_PCT, y1 + PAD_PCT
    if x1 - x0 < MIN_CROP_W_PCT:
        cx = (x0 + x1) / 2
        x0, x1 = cx - MIN_CROP_W_PCT / 2, cx + MIN_CROP_W_PCT / 2
    if y1 - y0 < MIN_CROP_H_PCT:
        cy = (y0 + y1) / 2
        y0, y1 = cy - MIN_CROP_H_PCT / 2, cy + MIN_CROP_H_PCT / 2
    # Slide (don't squash) a crop that ran off the sheet, so the requested
    # region stays inside it whenever the floor allows.
    if x0 < 0:
        x1, x0 = min(1.0, x1 - x0), 0.0
    if x1 > 1:
        x0, x1 = max(0.0, x0 - (x1 - 1)), 1.0
    if y0 < 0:
        y1, y0 = min(1.0, y1 - y0), 0.0
    if y1 > 1:
        y0, y1 = max(0.0, y0 - (y1 - 1)), 1.0
    return max(0.0, x0), max(0.0, y0), min(1.0, x1), min(1.0, y1)


# ── disk cache ──────────────────────────────────────────────────────────────

def cache_key(project_id: str, page: int, rect: list[float], dpi: int) -> str:
    raw = (f"{CACHE_VERSION}|{project_id}|{page}|"
           + ",".join(f"{v:.4f}" for v in rect)
           + f"|{dpi}")
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _cache_path(project_id: str, key: str) -> Path:
    return CACHE_ROOT / project_id / f"{key}.png"


def _cache_read(path: Path) -> bytes | None:
    try:
        return path.read_bytes()
    except OSError:
        return None


def _cache_write(path: Path, data: bytes) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".png.tmp")
        tmp.write_bytes(data)
        tmp.replace(path)
    except OSError as exc:  # a full/read-only disk must not fail the request
        log.warning("evidence cache write failed for %s: %r", path, exc)
        return
    global _writes_since_sweep
    _writes_since_sweep += 1
    if _writes_since_sweep >= CACHE_SWEEP_EVERY:
        _writes_since_sweep = 0
        _sweep_cache()


def _sweep_cache() -> None:
    """Evict oldest-first once the cache passes its byte cap."""
    try:
        entries = []
        total = 0
        for p in CACHE_ROOT.rglob("*.png"):
            try:
                st = p.stat()
            except OSError:
                continue
            entries.append((st.st_mtime, st.st_size, p))
            total += st.st_size
        if total <= CACHE_MAX_BYTES:
            return
        entries.sort()
        target = CACHE_MAX_BYTES * CACHE_SWEEP_TO
        for _mtime, size, p in entries:
            if total <= target:
                break
            try:
                p.unlink()
                total -= size
            except OSError:
                continue
        log.info("evidence cache swept to %d bytes", total)
    except OSError as exc:  # noqa: BLE001 — housekeeping is best effort
        log.warning("evidence cache sweep failed: %r", exc)


# ── rendering ───────────────────────────────────────────────────────────────

def _page_count_and_size(pdf_bytes: bytes) -> tuple[int | None, float, float]:
    """(pages, width_pt, height_pt) — best effort, never raises.

    Used to answer "no such page" without rasterising, and to pick a dpi that
    cannot blow up on an A0 sheet. `None` pages means poppler could not tell
    us cheaply; the render below then decides.
    """
    try:
        from pdf2image import pdfinfo_from_bytes
        info = pdfinfo_from_bytes(pdf_bytes)
        pages = int(info.get("Pages") or 0) or None
        size = str(info.get("Page size") or "")
        w = h = 0.0
        if "x" in size:
            left, right = size.split("x", 1)
            w = float(left.strip().split()[0])
            h = float(right.strip().split()[0])
        return pages, w, h
    except Exception as exc:  # noqa: BLE001 — poppler variance, not our bug
        log.debug("pdfinfo unavailable: %r", exc)
        return None, 0.0, 0.0


def safe_dpi(requested: int, page_w_pt: float, page_h_pt: float) -> int:
    dpi = max(MIN_DPI, min(MAX_DPI, int(requested)))
    longest_pt = max(page_w_pt or 0.0, page_h_pt or 0.0)
    if longest_pt > 0:
        allowed = int(MAX_PAGE_PX * 72.0 / longest_pt)
        dpi = max(MIN_DPI, min(dpi, allowed))
    return dpi


# A room's check sheet asks for six crops on one or two sheets, and the zoom
# viewer for a fresh rect on every gesture — each used to refetch the PDF and
# rasterise the whole page again (2026-09-15 review). Small in-process LRUs:
# the rendered page per (project, page, dpi) and the page count/size per
# project; the crop is cut from the cached raster.
# Entries live for a couple of minutes: long enough for one room's burst of
# crops, short enough that a project whose PDF changes under the same id (a
# re-read after a new upload) is never served the old sheet for long. A page
# raster is bounded by MAX_PAGE_PX (≈ 40 MB RGB at the cap), so three of them
# is the most the container is asked to hold.
_PAGE_CACHE: "OrderedDict[tuple, tuple[float, object]]" = OrderedDict()
_PAGE_CACHE_MAX = 3
_SIZE_CACHE: "OrderedDict[str, tuple[float, tuple]]" = OrderedDict()
_SIZE_CACHE_MAX = 8
_CACHE_TTL_S = 120.0
_cache_lock = threading.Lock()


def _cached(cache: "OrderedDict", key, maxsize: int, make, ttl_s: float = _CACHE_TTL_S):
    now = time.monotonic()
    with _cache_lock:
        hit = cache.get(key)
        if hit is not None and now - hit[0] < ttl_s:
            cache.move_to_end(key)
            return hit[1]
    value = make()
    with _cache_lock:
        cache[key] = (time.monotonic(), value)
        cache.move_to_end(key)
        while len(cache) > maxsize:
            cache.popitem(last=False)
    return value


def forget_project(project_id: str) -> None:
    """Drop a deleted project's PDF, page sizes and page rasters from memory
    (project delete, audit 2026-09-29)."""
    with _cache_lock:
        _PDF_CACHE.pop(project_id, None)
        _SIZE_CACHE.pop(project_id, None)
        for key in [k for k in _PAGE_CACHE if isinstance(k, tuple) and k[:1] == (project_id,)]:
            _PAGE_CACHE.pop(key, None)


def _reset_render_caches_for_test() -> None:
    with _cache_lock:
        _PAGE_CACHE.clear()
        _SIZE_CACHE.clear()
        _PDF_CACHE.clear()


def _render_page(pdf_bytes: bytes, page: int, dpi: int):
    from pdf2image import convert_from_bytes
    try:
        imgs = convert_from_bytes(pdf_bytes, dpi=dpi, fmt="png",
                                  first_page=page, last_page=page)
    except Exception as exc:  # noqa: BLE001 — a broken PDF is not a 500
        log.warning("evidence render failed (page=%s dpi=%s): %r", page, dpi, exc)
        raise HTTPException(status_code=502,
                            detail="Nepavyko atvaizduoti brėžinio puslapio")
    if not imgs:
        raise HTTPException(status_code=404,
                            detail=f"Brėžinyje nėra {page} puslapio")
    return imgs[0]


def render_crop(pdf_bytes: bytes, page: int, rect: list[float], dpi: int,
                cache_key: str | None = None) -> bytes:
    """PNG bytes for `rect` (page-percent, padded) on `page` (1-based).
    `cache_key` (the project id) lets the page raster and size be reused
    across crops; without it every call renders afresh."""
    if cache_key:
        pages, w_pt, h_pt = _cached(_SIZE_CACHE, cache_key, _SIZE_CACHE_MAX,
                                    lambda: _page_count_and_size(pdf_bytes))
    else:
        pages, w_pt, h_pt = _page_count_and_size(pdf_bytes)
    if pages is not None and not (1 <= page <= pages):
        raise HTTPException(status_code=404,
                            detail=f"Brėžinyje nėra {page} puslapio")
    dpi = safe_dpi(dpi, w_pt, h_pt)
    x0, y0, x1, y1 = _padded(rect)
    crop = None
    if (x1 - x0) < WHOLE_SHEET_SHARE or (y1 - y0) < WHOLE_SHEET_SHARE:
        try:
            crop = _render_region(pdf_bytes, page, (x0, y0, x1, y1), dpi)
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001 — the page raster below still answers
            log.warning("evidence region render failed (page=%s): %r", page, exc)
            crop = None
    if crop is None:
        if cache_key:
            img = _cached(_PAGE_CACHE, (cache_key, page, dpi), _PAGE_CACHE_MAX,
                          lambda: _render_page(pdf_bytes, page, dpi))
        else:
            img = _render_page(pdf_bytes, page, dpi)
        W, H = img.size
        box = (int(W * x0), int(H * y0),
               max(int(W * x1), int(W * x0) + 1),
               max(int(H * y1), int(H * y0) + 1))
        crop = img.crop(box)
    cw, ch = crop.size
    scale = min(1.0, MAX_CROP_PX / max(cw, ch, 1))
    if scale < 1.0:
        crop = crop.resize((max(1, int(cw * scale)), max(1, int(ch * scale))))
    buf = io.BytesIO()
    crop.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _render_region(pdf_bytes: bytes, page: int, box: tuple[float, float, float, float],
                   min_dpi: int):
    """The padded rectangle `box` (fractions of the page AS DISPLAYED) rendered
    on its own through PDFium. Returns a PIL image, or None when PDFium is not
    installed or the page has no size — the caller falls back to the raster."""
    try:
        import pypdfium2 as pdfium
    except ImportError:
        return None
    from extractor.pdfium_guard import PDFIUM_LOCK

    x0, y0, x1, y1 = box
    with PDFIUM_LOCK:
        doc = pdfium.PdfDocument(pdf_bytes)
        try:
            if not (1 <= page <= len(doc)):
                raise HTTPException(status_code=404,
                                    detail=f"Brėžinyje nėra {page} puslapio")
            pg = doc[page - 1]
            try:
                # get_size() is the page as DISPLAYED (/Rotate applied), and so
                # is the frame `crop` cuts in — left, bottom, right, top.
                W, H = (float(v) for v in pg.get_size())
                if W <= 0 or H <= 0:
                    return None
                long_in = max((x1 - x0) * W, (y1 - y0) * H) / 72.0
                dpi = MAX_CROP_PX / max(long_in, 1e-6)
                dpi = max(float(min_dpi), min(float(REGION_MAX_DPI), dpi))
                cut = (x0 * W, (1.0 - y1) * H, (1.0 - x1) * W, y0 * H)
                return pg.render(scale=dpi / 72.0, crop=cut).to_pil().convert("RGB")
            finally:
                pg.close()
        finally:
            doc.close()


# ── the endpoint ────────────────────────────────────────────────────────────

# Deliberately `def`, not `async def` — same reasoning as /api/projects/{id}/pdf
# and /generate-excel: the body is object storage + poppler + Pillow, i.e. 100 %
# blocking. As a coroutine it would rasterise ON the event loop and every other
# request would queue behind ~0,4 s of poppler. Plain `def` hands it to the
# threadpool.
@router.get("/{project_id}/evidence")
def api_project_evidence(
    request: Request,
    project_id: str,
    page: int | None = Query(None, ge=1, le=2000),
    rect: str | None = Query(None),
    room: str | None = Query(None),
    dpi: int = Query(DEFAULT_DPI),
):
    _safe_project_id(project_id)
    user = _auth.require_user(request)
    user_filter = None if user.get("is_admin") else user["id"]

    from main import _check_rate_limit, _client_key
    _check_rate_limit(_client_key(request), "evidence")

    if room is not None:
        proj = _db.get_project(project_id, user_id=user_filter)
        if not proj:
            raise HTTPException(status_code=404,
                                detail="Projektas nerastas")
        target = str(room).strip()
        match = next((r for r in (proj.get("patalpos") or [])
                      if str(r.get("nr") or "").strip() == target), None)
        if match is None:
            raise HTTPException(status_code=404,
                                detail=f"Patalpa {target} nerasta")
        region = room_region_pct(match)
        if region is None:
            # 404, not an empty image: the room genuinely has no geometry, and
            # the check sheet must be able to tell "we cannot point at this"
            # apart from "here it is".
            raise HTTPException(
                status_code=404,
                detail="Šios patalpos vietos brėžinyje nežinome")
        rect_v = region
        page_v = int(match.get("puslapio_nr") or page or 1)
    else:
        if not _db.project_exists(project_id, user_id=user_filter):
            raise HTTPException(status_code=404,
                                detail="Projektas nerastas")
        if page is None or rect is None:
            raise HTTPException(
                status_code=400,
                detail="Nurodykite page ir rect (arba room)")
        rect_v = parse_rect(rect)
        page_v = int(page)

    dpi_v = max(MIN_DPI, min(MAX_DPI, int(dpi)))
    key = cache_key(project_id, page_v, rect_v, dpi_v)
    etag = f'"{key}"'
    if etag in [t.strip() for t in
                (request.headers.get("if-none-match") or "").split(",") if t.strip()]:
        return Response(status_code=304, headers=_headers(etag))

    path = _cache_path(project_id, key)
    data = _cache_read(path)
    if data is None:
        pdf_bytes = _load_pdf(project_id)
        data = render_crop(pdf_bytes, page_v, rect_v, dpi_v, cache_key=project_id)
        _cache_write(path, data)
    return Response(content=data, media_type="image/png", headers=_headers(etag))


_PDF_CACHE: "OrderedDict[str, bytes]" = OrderedDict()
_PDF_CACHE_MAX = 2


def _load_pdf(project_id: str) -> bytes:
    """The project's PDF bytes — fetched once per project while its crops are
    being asked for (two projects kept), not once per crop."""
    return _cached(_PDF_CACHE, project_id, _PDF_CACHE_MAX, lambda: _load_pdf_uncached(project_id))


def _load_pdf_uncached(project_id: str) -> bytes:
    from storage import get_storage, pdf_key
    try:
        data = get_storage().get(pdf_key(project_id))
    except Exception as exc:  # noqa: BLE001 — an R2 hiccup is a 502, not a 500
        log.warning("evidence pdf fetch failed for %s: %r", project_id, exc)
        raise HTTPException(status_code=502,
                            detail="Nepavyko pasiekti brėžinio saugyklos")
    if not data:
        # Explicit, and distinct from "no such project": projects extracted
        # before durable PDF storage (2026-06-21) have rooms and quantities but
        # no bytes to crop, and the check sheet has to say so rather than show
        # a broken image.
        raise HTTPException(status_code=404, detail="Brėžinys nerastas")
    return data


def _headers(etag: str) -> dict:
    # private: these are the user's own drawings, never a shared/CDN cache.
    # A crop is immutable for the life of an upload (same project, page, rect,
    # dpi ⇒ same pixels), so it may be held for a day.
    return {"Cache-Control": "private, max-age=86400", "ETag": etag}


def evidence_url(project_id: str, page: int | None, rect: list[float] | None,
                 dpi: int = DEFAULT_DPI) -> str | None:
    """The URL the check sheet puts in `crop_url`. None when unpointable."""
    if page is None or not rect or len(rect) != 4:
        return None
    r = ",".join(f"{float(v):.4f}" for v in rect)
    return (f"/api/projects/{project_id}/evidence"
            f"?page={int(page)}&rect={r}&dpi={int(dpi)}")


# Keep the module importable in a pure-unit context where the data dir is
# read-only; the first write recreates it anyway.
try:
    CACHE_ROOT.mkdir(parents=True, exist_ok=True)
except OSError:  # pragma: no cover — surfaced by the write path instead
    log.warning("evidence cache dir unavailable: %s", CACHE_ROOT)
