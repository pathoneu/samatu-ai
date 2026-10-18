"""GET /api/projects/{project_id}/reminders — what an estimator commonly forgets, as notices.

Pathon v3 W5-E (E8, E9). The judgement lives in `extractor/reminders.py` (a pure function of the stored
project); this file is the owner check, the rate bucket, the drawing's text layer for the fire-rating words
(EI30, „ugniai atspari" — PDFium text search under PDFIUM_LOCK, cached per PDF digest) and the prose
scrubber. Read-only: saves nothing, €0, no model call. A project without a PDF still gets every reminder
that needs no drawing (the fire reminder is then the general one).
"""
from __future__ import annotations

import hashlib
import logging
import threading
from collections import OrderedDict

from fastapi import APIRouter, HTTPException, Request

from api.free_reread import _project_for
from extractor import user_text as _user_text
from extractor.reminders import FIRE_TERMS_RE, build_reminders

log = logging.getLogger("samatu.reminders")

router = APIRouter(prefix="/api/projects", tags=["reminders"])

# Literal searches (PDFium searches text, not patterns); every hit is checked against FIRE_TERMS_RE.
_FIRE_NUMBERS = (15, 20, 30, 45, 60, 90, 120, 180)
FIRE_SEARCHES = tuple(f"{p}{sep}{n}" for p in ("EI", "REI") for sep in ("", " ") for n in _FIRE_NUMBERS) + (
    "ugniai atspar", "ugniaatspar")
MAX_HITS = 20
MAX_PAGES = 60
_CACHE: "OrderedDict[str, list[dict]]" = OrderedDict()
_CACHE_MAX = 16
_CACHE_LOCK = threading.Lock()


def fire_hits(pdf_bytes: bytes) -> list[dict]:
    """[{page, box_pct, text}] — where the drawing's text layer names a fire-rated assembly; display-frame
    boxes as fractions of the page. Cached per PDF digest."""
    digest = hashlib.sha1(pdf_bytes).hexdigest()
    with _CACHE_LOCK:
        if digest in _CACHE:
            _CACHE.move_to_end(digest)
            return _CACHE[digest]
    hits = _scan(pdf_bytes)
    with _CACHE_LOCK:
        _CACHE[digest] = hits
        while len(_CACHE) > _CACHE_MAX:
            _CACHE.popitem(last=False)
    return hits


def _scan(pdf_bytes: bytes) -> list[dict]:
    import pypdfium2 as pdfium

    from extractor.pdf_vectors import _to_display
    from extractor.pdfium_guard import PDFIUM_LOCK

    out: list[dict] = []
    with PDFIUM_LOCK:
        doc = pdfium.PdfDocument(pdf_bytes)
        try:
            for p in range(1, min(len(doc), MAX_PAGES) + 1):
                page = doc[p - 1]
                try:
                    W, H = (float(v) for v in page.get_size())
                    k = (int(page.get_rotation() or 0) // 90) % 4
                    Wu, Hu = (H, W) if k in (1, 3) else (W, H)
                    tp = page.get_textpage()
                    try:
                        seen: list[tuple[int, int]] = []
                        for term in FIRE_SEARCHES:
                            searcher = tp.search(term, match_case=term[0].isupper(), match_whole_word=False)
                            try:
                                while len(out) < MAX_HITS:
                                    occ = searcher.get_next()
                                    if not occ:
                                        break
                                    idx, n = occ
                                    if any(a <= idx < a + m or idx <= a < idx + n for a, m in seen):
                                        continue          # „REI30" already found as „EI30", or the other way round
                                    around = tp.get_text_range(max(0, idx - 1), n + 2 if idx else n + 1)
                                    m = FIRE_TERMS_RE.search(around or "")
                                    if not m:
                                        continue
                                    seen.append((idx, n))
                                    boxes = [tp.get_charbox(i) for i in range(idx, idx + n)]
                                    left, bottom = min(b[0] for b in boxes), min(b[1] for b in boxes)
                                    right, top = max(b[2] for b in boxes), max(b[3] for b in boxes)
                                    pts = [_to_display(x, y, Wu, Hu, k) for x, y in ((left, bottom), (right, top))]
                                    x0, x1 = sorted((pts[0][0], pts[1][0]))
                                    y0, y1 = sorted((pts[0][1], pts[1][1]))
                                    pad = 0.01
                                    out.append({"page": p, "text": m.group(0).strip(),
                                                "box_pct": [round(max(0.0, x0 / W - pad), 5), round(max(0.0, y0 / H - pad), 5),
                                                            round(min(1.0, x1 / W + pad), 5), round(min(1.0, y1 / H + pad), 5)]})
                            finally:
                                searcher.close()
                    finally:
                        tp.close()
                finally:
                    page.close()
                if len(out) >= MAX_HITS:
                    break
        finally:
            doc.close()
    return out


def _pdf_or_none(project_id: str) -> bytes | None:
    from storage import get_storage, pdf_key
    try:
        return get_storage().get(pdf_key(project_id)) or None
    except Exception as exc:  # noqa: BLE001 — no drawing: the reminders that need none still come
        log.info("reminders: no pdf for %s (%r)", project_id, exc)
        return None


# Plain `def`: a sqlite read, pure work on the blob, and PDFium under its lock — the threadpool runs it.
@router.get("/{project_id}/reminders")
def api_project_reminders(request: Request, project_id: str):
    project = _project_for(request, project_id)            # ownership before anything about the request
    from main import _check_rate_limit, _client_key
    _check_rate_limit(_client_key(request), "reminders")
    hits = None
    pdf_bytes = _pdf_or_none(project_id)
    if pdf_bytes:
        try:
            hits = fire_hits(pdf_bytes)
        except Exception as exc:  # noqa: BLE001 — an unreadable text layer gives the general reminder
            log.warning("reminders: text layer unreadable for %s: %r", project_id, exc)
            hits = None
    try:
        payload = build_reminders(project, fire_hits=hits)
    except Exception as exc:  # noqa: BLE001 — a malformed legacy blob is not a 500 trace
        log.error("reminders failed project=%s: %r", project_id, exc)
        raise HTTPException(status_code=500, detail="Nepavyko sudaryti priminimų sąrašo") from exc
    payload["teksto_sluoksnis"] = hits is not None
    return _user_text.scrub_prose(payload)
