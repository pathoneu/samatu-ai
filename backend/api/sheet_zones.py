"""GET /api/projects/{project_id}/pages/{page}/zones — where on one sheet the plan, the legend, the tables,
the title block and the notes are (extractor/sheet_zones.py).

Pathon v3, track A (docs/superpowers/specs/2026-10-18-pathon-v3-design.md §4; wave-1 plan, track W1-E): the
zones are the ground the next waves stand on — the legend marking proposes the legenda zone, the table
reader looks inside lentele zones, a click in the antspaudas is never a room, a count inside a legend or a
table makes no marker. Nothing in the UI calls this route yet (wave 2 does).

Read-only, owner-scoped (the owner check comes before anything else), rate-limited like the other PDF
handlers, saves nothing, €0 — no model call. Cached per PDF digest and page inside the module, the way the
page geometry is. A sheet with no text layer and no vector walls answers `status: "no_text"`, `detail:
"nėra teksto sluoksnio"` and no zones — never an error.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request

from api.free_reread import NO_PDF, _project_for
from extractor.sheet_zones import read_zones

log = logging.getLogger("samatu.sheet_zones")

router = APIRouter(prefix="/api/projects", tags=["sheet-zones"])

NO_PAGE = "Tokio lapo brėžinyje nėra"


# Plain `def`: PDFium and pdfplumber parsing, blocking CPU — FastAPI runs it in the threadpool.
@router.get("/{project_id}/pages/{page}/zones")
def api_sheet_zones(request: Request, project_id: str, page: int):
    _project_for(request, project_id)                      # ownership before anything about the request
    if page < 1:
        raise HTTPException(status_code=400, detail="Lapo numeris prasideda nuo 1")
    from main import _check_rate_limit, _client_key
    _check_rate_limit(_client_key(request), "sheet_zones")

    from storage import get_storage, pdf_key
    try:
        pdf_bytes = get_storage().get(pdf_key(project_id))
    except Exception as exc:  # noqa: BLE001 — an R2 hiccup is a 502, not a 500
        log.warning("sheet-zones pdf fetch failed for %s: %r", project_id, exc)
        raise HTTPException(status_code=502, detail="Nepavyko pasiekti brėžinio saugyklos")
    if not pdf_bytes:
        raise HTTPException(status_code=404, detail=NO_PDF)

    res = read_zones(pdf_bytes, page)
    if res["status"] == "no_page":
        raise HTTPException(status_code=400, detail=NO_PAGE)
    return res
