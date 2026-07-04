"""POST /api/lasso-rerun — G5 lasso re-extract.

Frontend sends a freehand polygon (≥3 vertices in 0..1 page coords).
Backend crops the bounding box, runs Vision over just that region asking
specifically for symbols (outlets, switches, drains, etc.) and any
zone polygons within the lasso. Returns updated symbol list and polygons.

Spec §4.5 lasso-rerun, §5.4 G5, §4.8 error envelope.
"""
import logging
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

import auth as _auth
import db as _db

router = APIRouter(prefix="/api", tags=["lasso_rerun"])
log = logging.getLogger(__name__)


def _require_project_ownership(user: dict, project_id: str) -> None:
    """F3 (2026-07-04 pentest): lasso-rerun was authed but ran Vision against ANY
    project_id, so a logged-in user could make another tenant's project pay for
    (and leak crops from) a Vision call. Gate on ownership; admins bypass. A
    missing/foreign project → 404 (do not leak existence)."""
    user_filter = None if user.get("is_admin") else user["id"]
    if _db.get_project(project_id, user_id=user_filter) is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")


class LassoRequest(BaseModel):
    project_id: str
    page_idx: int = Field(..., ge=0, le=200)
    lasso_polygon_pct: list[list[float]]

    @field_validator("lasso_polygon_pct")
    @classmethod
    def _polygon_valid(cls, v: list[list[float]]) -> list[list[float]]:
        if len(v) < 3:
            raise ValueError(f"lasso_polygon_pct needs ≥3 vertices, got {len(v)}")
        for vertex in v:
            if len(vertex) != 2:
                raise ValueError("each vertex must be [x, y]")
            x, y = vertex
            if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
                raise ValueError(f"vertex out of [0,1]: {vertex}")
        return v


def vision_lasso_extract(project_id: str, page_idx: int,
                         lasso_polygon_pct: list[list[float]]) -> dict[str, Any]:
    """Sprint 2 stub. Sprint 4 wires Vision crop+symbol-extract pipeline.

    Returns empty result so wiring is testable end-to-end. Mocked in tests.
    """
    return {"symbols": [], "polygons": []}


@router.post("/lasso-rerun")
def lasso_rerun(
    req: LassoRequest,
    user: dict = Depends(_auth.require_billable_user),
) -> dict:
    _require_project_ownership(user, req.project_id)
    try:
        result = vision_lasso_extract(
            project_id=req.project_id,
            page_idx=req.page_idx,
            lasso_polygon_pct=req.lasso_polygon_pct,
        )
    except Exception as exc:
        log.exception("lasso_rerun failed for project=%s page=%s",
                      req.project_id, req.page_idx)
        raise HTTPException(status_code=502, detail={
            "error_code": "lasso_extract_failed",
            "user_message": "Nepavyko apdoroti lasso srities. Bandyk vėl arba mažesnę sritį.",
            "retry_safe": True,
            "exception": str(exc),
        })
    return {
        "symbols": result.get("symbols", []),
        "polygons": result.get("polygons", []),
    }
