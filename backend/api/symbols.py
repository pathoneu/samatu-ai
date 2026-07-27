"""POST /api/projects/{project_id}/detect-symbols

Calls the symbol_detector Vision pass on a project's electrical / plumbing
page (or any specific page when ``?page=N`` is supplied) and returns the
result as JSON. Cached on disk via the Vision cache, so subsequent calls
are free.

Fixture mode (``?fixture=berzas``) operates on the contractor PDF directly
without DB lookup. The endpoint requires auth in non-fixture mode.
"""

from __future__ import annotations

import os
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
    # SECURITY (2026-07-27 audit, finding 10): the fixture branch is NOT
    # ownership-gated — any logged-in user could run Vision detection against the
    # committed contractor fixture under ANY project_id. Same convention as
    # api/room_graph.py: allowed in dev/demo, ignored in production, where the
    # request falls through to the normal owner-scoped DB path below.
    if fixture and os.environ.get("ENV") != "production":
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
    # Auth + spend cap BEFORE any Vision work. The fixture branch of
    # _resolve_pdf_bytes skipped require_user entirely, so detect-symbols?fixture=
    # was an unauthenticated, uncapped Vision call anyone could loop. (2026-06-19)
    _auth.require_billable_user(request)
    pdf_bytes = _resolve_pdf_bytes(request, project_id, fixture)
    pages = pdf_to_b64_images(pdf_bytes, max_pages=page)
    if len(pages) < page:
        raise HTTPException(status_code=400, detail=f"PDF has only {len(pages)} pages")
    image_b64 = pages[page - 1]["image_b64"]
    out = detect_symbols(image_b64=image_b64)
    response = out.to_dict()
    # Only claim fixture provenance when the fixture branch actually ran (in
    # production it is ignored and real project bytes are used).
    used_fixture = bool(fixture) and os.environ.get("ENV") != "production"
    response["project_id"] = f"fixture:{fixture}" if used_fixture else project_id
    response["page"] = page
    return response
