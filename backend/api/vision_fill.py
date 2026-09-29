"""POST /api/vision-fill — G1 click-to-fill backend.

Frontend sends a click in 0..1 page-fraction coords. We crop a square
~40% page-width around the click and ask Claude Vision to trace the
room polygon containing that point.

Returns the polygon_pct (vertices in 0..1 coords) plus the AI's room-name
guess and a confidence band.

Spec §4.5 vision-fill, §5.4 G1, §4.8 error envelope.
"""
import logging
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

import auth as _auth
import db as _db

router = APIRouter(prefix="/api", tags=["vision_fill"])
log = logging.getLogger(__name__)


def _require_project_ownership(user: dict, project_id: str) -> None:
    """F3 (2026-07-04 pentest): vision-fill was authed but ran Vision against ANY
    project_id, so a logged-in user could make another tenant's project pay for
    (and leak crops from) a Vision call. Gate on ownership; admins bypass. A
    missing/foreign project → 404 (do not leak existence)."""
    user_filter = None if user.get("is_admin") else user["id"]
    if _db.get_project(project_id, user_id=user_filter) is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")


class VisionFillRequest(BaseModel):
    project_id: str
    page_idx: int = Field(..., ge=0, le=200)
    click_xy_pct: list[float]
    viewport_state: dict | None = None

    @field_validator("click_xy_pct")
    @classmethod
    def _click_in_unit(cls, v: list[float]) -> list[float]:
        if len(v) != 2:
            raise ValueError("click_xy_pct must be [x, y]")
        x, y = v
        if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
            raise ValueError(f"click_xy_pct out of [0,1]: got [{x}, {y}]")
        return v


def call_vision_for_polygon(
    project_id: str, page_idx: int, click_xy_pct: list[float]
) -> dict[str, Any]:
    """Wrap the Vision call. Real implementation uses Pass-2 zoom prompt
    on a crop centered at click_xy_pct.

    For Sprint 2, this is a thin shim — Sprint 4 swaps to the full Pass-2
    pipeline once we have at least one real-PDF golden test. Until then
    returns a placeholder polygon_pct with confidence='low'.
    """
    # Sprint 2: minimal viable call. Uses crop-around-click prompt.
    # See backend/extractor/vision_call.py:zoom_pass for the existing helper.
    from extractor.vision_call import vision_polygon_at_click
    return vision_polygon_at_click(project_id=project_id, page_idx=page_idx,
                                   click_xy_pct=click_xy_pct)


@router.post("/vision-fill")
def vision_fill(
    req: VisionFillRequest,
    # Stub, no Anthropic call (audit 2026-09-29). Wiring a real Vision call
    # here means switching back to _auth.require_billable_user.
    user: dict = Depends(_auth.require_user),
) -> dict:
    _require_project_ownership(user, req.project_id)
    try:
        result = call_vision_for_polygon(
            req.project_id, req.page_idx, req.click_xy_pct,
        )
    except Exception as exc:
        log.exception("vision_fill failed for project=%s page=%s",
                      req.project_id, req.page_idx)
        raise HTTPException(status_code=502, detail={
            "error_code": "vision_call_failed",
            "user_message": "Nepavyko apskaičiuoti zonos AI dėka. Bandyk dar kartą arba lasso (G5).",
            "retry_safe": True,
            "exception": str(exc),
        })
    return {
        "polygon_pct": result.get("polygon_pct"),
        "room_name_guess": result.get("room_name_guess"),
        "confidence": result.get("confidence", "medium"),
    }
