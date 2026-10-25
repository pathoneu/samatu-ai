"""POST /api/projects/{project_id}/legend/rows  — a legend box (or the sheet's legend zones) → its rows
POST /api/projects/{project_id}/legend/count — legend rows → how many of each symbol the drawing carries

Pathon v3, track B (docs/superpowers/specs/2026-10-18-pathon-v3-design.md §4; waves 2–4 plan, track W2-A, A4).
„Pažymėti legendą": the person accepts the suggested legend (W1-E's `legenda` zone) or draws a box; the rows
come back with their glyph and text (extractor/legend_rows.py); for the rows the person keeps, the count
answers per sheet with every instance's box, a proposal the person reviews before anything exists (W2-B).

Who counts what: a coloured glyph is counted from the drawing's own paths (vector_symbols
`count_glyph_instances_many`, saltinis „vektoriai"); a black one — or a coloured one the paths do not carry —
by its shape on the rendered sheets (cv_match `batch_find_symbol`, „rastras", each instance with its score);
a glyph that is a character of the text layer by that character standing alone (`tekstas`). One rule for
all three: the sheets that carry the row's own legend text are counted, a sheet that repeats an earlier
sheet's plan is counted once, nothing inside a legend, a table or the title block; instances on sheets
without the legend are listed (`kiti`), not counted — unless the legend stands on a sheet of its own.

Both routes are read-only and €0 (no model call): NOTHING is saved here — the legend is stored by
api/legends.py when the UI commits it. Owner-scoped (the owner check before anything about the request),
rate-limited like the other PDF handlers, explicit Lithuanian errors. A sheet without a text layer answers
`status: "be_teksto"`, never a guess.
"""
from __future__ import annotations

import logging
import time

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from api.free_reread import NO_PDF, _project_for

log = logging.getLogger("samatu.legend_count")

router = APIRouter(prefix="/api/projects", tags=["legend-count"])

NO_PAGE = "Tokio lapo brėžinyje nėra"
MAX_ROWS = 40
# The count core lives in extractor/legend_counts.py since v4 Phase 3c-2 (the reading runs it too); the names
# stay importable from here.
from extractor.legend_counts import (  # noqa: E402,F401
    GLYPH_PAD_PT, RING_HOW_LT, ROUTE_BUDGET_S, SALTINIAI, VECTOR_BUDGET_S, _in_word, _mediabox_box,
    _one_symbol_one_row, _pages_for, _pages_word, _raster_count, _ring_count, _sheet_rules, _text_count, _text_hits,
    count_rows, sentence_lt,
)


class RowsBody(BaseModel):
    page: int = 1
    bbox_pct: list[float] | None = None


class CountBody(BaseModel):
    rows: list[dict] = []
    row_ids: list[str] = []
    pages: list[int] | None = None
    min_score: float = 0.70
    margin: float | None = None        # the shape search keeps candidates within this of the best twin (default 0,02)
    other_sheets: bool = False


# ── helpers ─────────────────────────────────────────────────────────────────


def _pdf(project_id: str) -> bytes:
    from storage import get_storage, pdf_key
    try:
        pdf_bytes = get_storage().get(pdf_key(project_id))
    except Exception as exc:  # noqa: BLE001 — an R2 hiccup is a 502, not a 500
        log.warning("legend pdf fetch failed for %s: %r", project_id, exc)
        raise HTTPException(status_code=502, detail="Nepavyko pasiekti brėžinio saugyklos")
    if not pdf_bytes:
        raise HTTPException(status_code=404, detail=NO_PDF)
    return pdf_bytes


def _box(v, what: str) -> list[float]:
    try:
        b = [float(x) for x in v]
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail=f"{what} turi būti keturi skaičiai nuo 0 iki 1")
    if len(b) != 4 or not all(0.0 <= x <= 1.0 for x in b) or not (b[2] > b[0] and b[3] > b[1]):
        raise HTTPException(status_code=400, detail=f"{what} turi būti [x0, y0, x1, y1] nuo 0 iki 1, x1 > x0, y1 > y0")
    return b


def _union(a, b):
    return [min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])]


def _with_crops(project_id: str, rows: list[dict], legend_box) -> list[dict]:
    from api.evidence import evidence_url
    out = []
    for r in rows:
        r = dict(r)
        r["legend_bbox_pct"] = list(legend_box) if legend_box else None
        r["glyph_crop_url"] = evidence_url(project_id, r["page"], r["glyph_bbox_pct"])
        r["crop_url"] = evidence_url(project_id, r["page"], _union(r["glyph_bbox_pct"], r["text_bbox_pct"]))
        out.append(r)
    return out


# ── POST …/legend/rows ──────────────────────────────────────────────────────


# Plain `def`: PDFium and pdfplumber parsing, blocking CPU — FastAPI runs it in the threadpool.
@router.post("/{project_id}/legend/rows")
def api_legend_rows(request: Request, project_id: str, body: RowsBody):
    project = _project_for(request, project_id)            # ownership before anything about the request
    from main import _check_rate_limit, _client_key
    _check_rate_limit(_client_key(request), "legend_rows")
    page = int(body.page)
    if page < 1:
        raise HTTPException(status_code=400, detail="Lapo numeris prasideda nuo 1")
    bbox = _box(body.bbox_pct, "Legendos rėmelis") if body.bbox_pct is not None else None
    pdf_bytes = _pdf(project_id)

    from extractor.legend_rows import split_legend_rows, suggest_legend_rows
    from extractor.sheet_zones import display_frame
    if display_frame(pdf_bytes, page) is None:
        raise HTTPException(status_code=400, detail=NO_PAGE)
    if bbox is not None:
        res = split_legend_rows(pdf_bytes, page, bbox)
        legends = [{**res, "zone": None}]
        source, status, detail = "remelis", res["status"], res["detail"]
    else:
        meta = project.get("_meta") if isinstance(project.get("_meta"), dict) else {}
        stored = (meta.get("zonos") or {}).get(str(page)) if isinstance(meta.get("zonos"), dict) else None
        sug = suggest_legend_rows(pdf_bytes, page, stored if isinstance(stored, list) else None)
        legends = sug["legends"]
        source, status, detail = "zona", sug["status"], sug["detail"]
    for leg in legends:
        leg["rows"] = _with_crops(project_id, leg.get("rows") or [], leg.get("bbox_pct"))
    return {"page": page, "status": status, "detail": detail, "source": source, "legends": legends,
            "rows": [r for leg in legends for r in leg["rows"]]}


# ── GET …/legend/sheets ─────────────────────────────────────────────────────

SHEETS_BUDGET_S = 20.0


# Plain `def` for the same reason as the rows route. B1-B (2026-10-19): G on a sheet without a legend used to
# say only „apveskite ją rėmeliu" — on objektas_g the legend stands on sheet 5 of 16 and he boxed whatever was
# on screen. This answers WHERE the legends are, so the tool can say „Legenda yra 5 lape — eiti".
@router.get("/{project_id}/legend/sheets")
def api_legend_sheets(request: Request, project_id: str):
    """The sheets that carry a legend the tool can propose: {pages: [{page, rows}], partial, pages_not_read}.
    Sheet zones are read (and cached) per sheet within SHEETS_BUDGET_S; a sheet not reached in time is listed in
    `pages_not_read`, never guessed. Read-only, €0, owner first."""
    project = _project_for(request, project_id)            # ownership before anything about the request
    from main import _check_rate_limit, _client_key
    _check_rate_limit(_client_key(request), "legend_sheets")
    pdf_bytes = _pdf(project_id)

    from extractor.cv_match import _mediabox_geometry
    from extractor.legend_rows import suggest_legend_rows
    from extractor.sheet_zones import read_zones
    try:
        n = len(_mediabox_geometry(pdf_bytes))
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=422, detail="Brėžinio atidaryti nepavyko")
    meta = project.get("_meta") if isinstance(project.get("_meta"), dict) else {}
    stored_all = meta.get("zonos") if isinstance(meta.get("zonos"), dict) else {}
    started = time.monotonic()
    pages: list[dict] = []
    not_read: list[int] = []
    for p in range(1, n + 1):
        if time.monotonic() - started > SHEETS_BUDGET_S:
            not_read.append(p)
            continue
        stored = stored_all.get(str(p))
        zones = stored if isinstance(stored, list) else (read_zones(pdf_bytes, p).get("zones") or [])
        if not any(z.get("kind") == "legenda" for z in zones if isinstance(z, dict)):
            continue
        sug = suggest_legend_rows(pdf_bytes, p, zones)
        rows = sum(len(leg.get("rows") or []) for leg in sug.get("legends") or [])
        if rows:
            pages.append({"page": p, "rows": rows})
    return {"pages": pages, "partial": bool(not_read), "pages_not_read": not_read,
            "elapsed_s": round(time.monotonic() - started, 2)}


# ── POST …/legend/count ─────────────────────────────────────────────────────


def _row_in(r: dict) -> dict:
    """A row (or a template the person boxed) as the counters take it — validated."""
    if not isinstance(r, dict):
        raise HTTPException(status_code=400, detail="Legendos eilutė turi būti objektas")
    try:
        page = int(r.get("page"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Legendos eilutei trūksta lapo numerio")
    if page < 1:
        raise HTTPException(status_code=400, detail="Lapo numeris prasideda nuo 1")
    kind = r.get("glyph_kind")
    if kind is not None and kind not in ("spalvotas", "juodas", "tekstas"):
        raise HTTPException(status_code=400, detail="Nežinoma ženklo rūšis")
    out = {"row_id": str(r.get("row_id") or ""), "page": page, "glyph_kind": kind,
           "glyph_bbox_pct": _box(r.get("glyph_bbox_pct"), "Ženklo rėmelis"),
           "text": str(r.get("text") or "")[:200], "glyph_text": r.get("glyph_text"),
           "countable": r.get("countable") is not False,
           "legend_bbox_pct": _box(r["legend_bbox_pct"], "Legendos rėmelis") if r.get("legend_bbox_pct") else None}
    if kind == "tekstas" and not (isinstance(out["glyph_text"], str) and out["glyph_text"].strip()):
        raise HTTPException(status_code=400, detail="Teksto ženklui trūksta paties ženklo")
    return out


@router.post("/{project_id}/legend/count")
def api_legend_count(request: Request, project_id: str, body: CountBody):
    _project_for(request, project_id)                      # ownership before anything about the request
    from main import _check_rate_limit, _client_key
    _check_rate_limit(_client_key(request), "legend_count")
    started = time.monotonic()
    rows_in = list(body.rows or [])
    if body.row_ids:
        from api.legends import load_project_legend
        saved = {str(r.get("row_id")): r for r in (load_project_legend(project_id).get("rows") or []) if isinstance(r, dict)}
        for rid in body.row_ids:
            if str(rid) not in saved:
                raise HTTPException(status_code=404, detail="Tokios legendos eilutės šiame projekte nėra")
            rows_in.append(saved[str(rid)])
    if not rows_in:
        raise HTTPException(status_code=400, detail="Nurodykite bent vieną legendos eilutę")
    if len(rows_in) > MAX_ROWS:
        raise HTTPException(status_code=400, detail=f"Vienu kartu galima skaičiuoti iki {MAX_ROWS} eilučių")
    if not (0.3 <= float(body.min_score) <= 1.0):
        raise HTTPException(status_code=400, detail="Panašumo riba turi būti nuo 0,3 iki 1")
    if body.margin is not None and not (0.0 <= float(body.margin) <= 0.3):
        raise HTTPException(status_code=400, detail="Panašumo paklaida turi būti nuo 0 iki 0,3")
    rows = [_row_in(r) for r in rows_in]
    for k, r in enumerate(rows):
        r["row_id"] = r["row_id"] or f"sablonas-{k + 1}"
    pdf_bytes = _pdf(project_id)

    from extractor.cv_match import _mediabox_geometry
    try:
        geo = _mediabox_geometry(pdf_bytes)
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=422, detail="Brėžinio atidaryti nepavyko")
    n = len(geo)
    if any(r["page"] > n for r in rows):
        raise HTTPException(status_code=400, detail=NO_PAGE)
    wanted = sorted({int(p) for p in (body.pages or range(1, n + 1)) if 1 <= int(p) <= n})
    if not wanted:
        raise HTTPException(status_code=400, detail="Nurodyti lapai brėžinyje neegzistuoja")

    out_rows = count_rows(pdf_bytes, rows, wanted, geo, min_score=float(body.min_score), margin=body.margin,
                          other_sheets=bool(body.other_sheets), started=started)
    return {"rows": out_rows, "pages": wanted, "partial": any(r["partial"] for r in out_rows),
            "elapsed_s": round(time.monotonic() - started, 2)}
