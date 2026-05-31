"""POST /api/projects/{project_id}/detect-symbols

Calls the symbol_detector Vision pass on a project's electrical / plumbing
page (or any specific page when ``?page=N`` is supplied) and returns the
result as JSON. Cached on disk via the Vision cache, so subsequent calls
are free.

Fixture mode (``?fixture=berzas``) operates on the contractor PDF directly
without DB lookup. The endpoint requires auth in non-fixture mode.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

import db as _db
import auth as _auth
from extractor.vision_call import pdf_to_b64_images
from extractor.vision.symbol_detector import detect_symbols

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = {
    "berzas": REPO_ROOT / "docs/superpowers/fixtures/2026-05-26-berzu-g-24/project.pdf",
}

router = APIRouter(prefix="/api/projects", tags=["symbols"])


def _resolve_pdf_bytes(
    request: Request,
    project_id: str,
    fixture: str | None,
) -> bytes:
    if fixture:
        p = FIXTURES.get(fixture)
        if not p or not p.exists():
            raise HTTPException(status_code=404, detail=f"unknown fixture: {fixture}")
        return p.read_bytes()
    user = _auth.require_user(request)
    user_filter = None if user.get("is_admin") else user["id"]
    project = _db.get_project(project_id, user_id=user_filter)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    # Existing project rows carry the PDF bytes via separate storage; if your
    # db layer differs, swap to whatever fetches the raw upload.
    pdf_bytes = _db.get_project_pdf_bytes(project_id, user_id=user_filter) \
        if hasattr(_db, "get_project_pdf_bytes") else None
    if not pdf_bytes:
        raise HTTPException(status_code=409, detail="Project PDF bytes not available")
    return pdf_bytes


@router.post("/{project_id}/detect-symbols")
async def detect_symbols_endpoint(
    request: Request,
    project_id: str,
    page: int = Query(default=5, ge=1, description="1-indexed page number to scan"),
    fixture: str | None = Query(default=None),
) -> dict[str, Any]:
    pdf_bytes = _resolve_pdf_bytes(request, project_id, fixture)
    pages = pdf_to_b64_images(pdf_bytes, max_pages=page)
    if len(pages) < page:
        raise HTTPException(status_code=400, detail=f"PDF has only {len(pages)} pages")
    image_b64 = pages[page - 1]["image_b64"]
    out = detect_symbols(image_b64=image_b64)
    response = out.to_dict()
    response["project_id"] = project_id if not fixture else f"fixture:{fixture}"
    response["page"] = page
    return response
