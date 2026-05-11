"""HTTP API for the CV layer. Three endpoints:

  POST /api/cv/match-template — click → count similar symbols on a page
  POST /api/cv/magic-wand     — click → suggest room polygon
  POST /api/cv/record-decision — append accept/reject as training data

Each endpoint is thin: parse → load page from the in-memory PDF cache →
call CV layer → return. Heavy multi-page jobs (run match across every
floor plan) belong in a future RQ-backed batch route; out of MVP scope.

PDFs come from `page_raster_cache._PDF_CACHE` (1h LRU). When the cache
has evicted, the endpoint returns 409 so the frontend can re-upload
from local browser state.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

import page_raster_cache as _pdf_cache
from extractor.cv_match import find_similar_symbols
from extractor.cv_render_cache import render_page
from extractor.cv_wand import suggest_room_polygon
from extractor.training_data import record_label

router = APIRouter(prefix="/api/cv", tags=["cv-tools"])


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
    klass: str
    decision: str  # "accept" | "reject"
    confidence: float | None = None
    dpi: int = 200


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
def match_template(body: MatchTemplateBody) -> dict:
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
def magic_wand(body: MagicWandBody) -> dict:
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
def record_decision(body: RecordDecisionBody) -> dict:
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
