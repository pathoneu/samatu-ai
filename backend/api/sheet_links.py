"""GET /api/projects/{project_id}/pages/{page}/callouts — references on one sheet to other sheets.

Why (Togal-v2 W7, research §1 „Sheets"): a sheet set points at itself — „žr. lapą A-03", „žiūrėti
iškl.", an elevation tag „g2" on the finishes plan, „PJŪVIS A-A". The viewer underlines those spans
and a click jumps to the sheet they mean. The matching is pure (`api/sheet_refs.py`); this module
reads the text layer with pypdfium2 (the same reader as the plan-area lane, every text direction in
its own frame, boxes mapped into the display frame) and the sheet names the rail shows (the
classification's `puslapiai` with the user's `sheet_overrides` on top).

Read-only, owner-scoped (ownership is checked before anything else), saves nothing, calls no model.
Reading a PDF's text is rate-limited like the other PDF handlers; answering from the cache is not. The text of a PDF is read once per process and kept in a
small cache keyed by the PDF's hash, so scrolling through a set costs one parse. A scan has no text
layer and answers an empty list — never an error.
"""
from __future__ import annotations

import hashlib
import logging
import threading
from collections import OrderedDict

from fastapi import APIRouter, HTTPException, Request

from api.free_reread import NO_PDF, _project_for
from api.sheet_refs import build_sheet_index, find_callouts, line_text, span_box, title_block_codes

log = logging.getLogger("samatu.sheet_links")

router = APIRouter(prefix="/api/projects", tags=["sheet-links"])

_CACHE_MAX = 6
_cache: "OrderedDict[str, dict]" = OrderedDict()
_cache_lock = threading.Lock()


def read_text_pages(pdf_bytes: bytes) -> dict:
    """{page_count, pages: {page: {width, height, lines: [(text, boxes)]}}} — boxes in the display
    frame (/Rotate applied, points from the top-left), one entry per text line per direction."""
    from extractor.plan_area_annotations import _iter_pages_pdfium, _lines
    from extractor.pdfium_guard import PDFIUM_LOCK
    import pypdfium2 as pdfium

    with PDFIUM_LOCK:   # two threads inside PDFium segfault the process (pdfium_guard)
        doc = pdfium.PdfDocument(pdf_bytes)
        try:
            page_count = len(doc)
        finally:
            doc.close()
    pages: dict[int, dict] = {}
    for pn, W, H, chars, to_display in _iter_pages_pdfium(pdf_bytes, None):
        entry = pages.setdefault(pn, {"width": float(W), "height": float(H), "lines": []})
        for chs in _lines(chars):
            text, boxes = line_text(chs)
            if not text.strip():
                continue
            shown = [tuple(to_display(list(b))) if b is not None else None for b in boxes]
            entry["lines"].append((text, shown))
    return {"page_count": page_count, "pages": pages}


def _text_for(project_id: str, pdf_bytes: bytes, on_miss=None) -> dict:
    """The parsed text of a PDF, from the cache when this process has read it before. `on_miss`
    runs before a fresh parse — the rate limit guards the parse, not the cached answer: a sheet
    set scrolled end to end asks once per page, dozens of times a minute."""
    key = f"{project_id}:{hashlib.sha1(pdf_bytes).hexdigest()}"
    with _cache_lock:
        hit = _cache.get(key)
        if hit is not None:
            _cache.move_to_end(key)
            return hit
    if on_miss is not None:
        on_miss()
    parsed = read_text_pages(pdf_bytes)
    with _cache_lock:
        _cache[key] = parsed
        while len(_cache) > _CACHE_MAX:
            _cache.popitem(last=False)
    return parsed


def rail_sheets(project: dict, page_count: int) -> list[dict]:
    """[{page, name, tipas}] as the sheet rail shows them: the user's name and type first."""
    auto = {}
    for p in project.get("puslapiai") or []:
        if not isinstance(p, dict):
            continue
        try:
            auto[int(p.get("nr"))] = p
        except (TypeError, ValueError):
            continue
    overrides = project.get("sheet_overrides") if isinstance(project.get("sheet_overrides"), dict) else {}
    out = []
    for pn in range(1, page_count + 1):
        a = auto.get(pn) or {}
        o = overrides.get(str(pn)) or overrides.get(pn) or {}
        if not isinstance(o, dict):
            o = {}
        out.append({
            "page": pn,
            "name": str(o.get("name") or a.get("pavadinimas") or "").strip(),
            "tipas": str(o.get("type") or a.get("tipas") or "unknown"),
        })
    return out


def callouts_for_page(project: dict, parsed: dict, page: int) -> list[dict]:
    pages = parsed["pages"]
    codes = {pn: title_block_codes(p["lines"], p["width"], p["height"]) for pn, p in pages.items()}
    sheets = rail_sheets(project, parsed["page_count"])
    index = build_sheet_index(sheets, codes)
    names = {s["page"]: s["name"] for s in sheets}
    here = pages.get(page)
    if not here:
        return []
    W, H = here["width"], here["height"]
    out = []
    for c in find_callouts(page, here["lines"], index, parsed["page_count"]):
        box = span_box(here["lines"][c.line][1], c.start, c.end)
        if box is None or W <= 0 or H <= 0:
            continue
        x0, y0, x1, y1 = box
        out.append({
            "text": c.text,
            "bbox_pct": [round(max(0.0, x0 / W), 5), round(max(0.0, y0 / H), 5),
                         round(min(1.0, x1 / W), 5), round(min(1.0, y1 / H), 5)],
            "target_page": c.target_page,
            "target_name": names.get(c.target_page) or "",
            "other_pages": c.other_pages,
            "confidence": c.confidence,
            "kind": c.kind,
        })
    return out


# Plain `def`: PDFium parsing, blocking CPU — FastAPI runs it in the threadpool.
@router.get("/{project_id}/pages/{page}/callouts")
def api_page_callouts(request: Request, project_id: str, page: int):
    project = _project_for(request, project_id)
    if page < 1:
        raise HTTPException(status_code=400, detail="Lapo numeris prasideda nuo 1")
    from main import _check_rate_limit, _client_key

    from storage import get_storage, pdf_key
    try:
        pdf_bytes = get_storage().get(pdf_key(project_id))
    except Exception as exc:  # noqa: BLE001 — an R2 hiccup is a 502, not a 500
        log.warning("sheet-links pdf fetch failed for %s: %r", project_id, exc)
        raise HTTPException(status_code=502, detail="Nepavyko pasiekti brėžinio saugyklos")
    if not pdf_bytes:
        raise HTTPException(status_code=404, detail=NO_PDF)

    try:
        parsed = _text_for(project_id, pdf_bytes,
                           on_miss=lambda: _check_rate_limit(_client_key(request), "sheet_links"))
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 — a PDF PDFium cannot open has no links, not a 500
        log.warning("sheet-links text read failed for %s: %r", project_id, exc)
        raise HTTPException(status_code=422, detail="Nepavyko perskaityti brėžinio teksto")
    if page > parsed["page_count"]:
        raise HTTPException(status_code=400, detail="Tokio lapo brėžinyje nėra")
    return {"page": page, "page_count": parsed["page_count"], "callouts": callouts_for_page(project, parsed, page)}
