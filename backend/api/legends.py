"""Per-project + architect-opt-in legend persistence (Week 5 Task 5.4 — D4).

Three layers (canonical plan §D4 verdict):

1. **Project legend** — automatic; stored at `data/legends/<project_id>.json`.
2. **Architect legend** — opt-in only after the user verifies the same
   mapping in ≥2 projects from the same architect.
3. **Global legend** — DELIBERATELY DOES NOT EXIST. No silent cross-project
   learning that could poison future projects.

The `/api/legends/architect/{architect}/promote` endpoint requires
`opt_in=true` AND ≥2 verified projects, mirroring the council's compromise
between Gemini's "per-project ephemeral only" and ChatGPT's three-layer
opt-in flow.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/legends", tags=["legends"])

LEGENDS_DIR = Path(__file__).resolve().parents[2] / "data" / "legends"
ARCHITECT_DIR = LEGENDS_DIR / "architect"


class LegendSymbol(BaseModel):
    glyph: str | None = None
    colored_line: str | None = None
    colored_hatch: str | None = None
    meaning: str
    confidence: float = 0.5


class ProjectLegend(BaseModel):
    project_id: str
    architect: str | None = None
    symbols: list[LegendSymbol] = []


class ArchitectPromotion(BaseModel):
    opt_in: bool
    verified_in_projects: list[str]


def _safe_id(name: str) -> str:
    if not name or "/" in name or ".." in name:
        raise HTTPException(status_code=400, detail=f"Invalid identifier: {name!r}")
    return name


def save_project_legend(project_id: str, legend: dict) -> None:
    LEGENDS_DIR.mkdir(parents=True, exist_ok=True)
    (LEGENDS_DIR / f"{_safe_id(project_id)}.json").write_text(
        json.dumps(legend, indent=2, ensure_ascii=False), encoding="utf-8",
    )


def load_project_legend(project_id: str) -> dict:
    p = LEGENDS_DIR / f"{_safe_id(project_id)}.json"
    if not p.exists():
        return {"project_id": project_id, "symbols": []}
    return json.loads(p.read_text(encoding="utf-8"))


def promote_to_architect(architect: str, verified_in_projects: list[str]) -> dict:
    """Aggregate ≥2 verified project legends into an architect-level dictionary."""
    if len(verified_in_projects) < 2:
        raise HTTPException(
            status_code=400,
            detail="Architect promotion requires at least 2 verified projects.",
        )
    aggregated: dict[tuple, dict] = {}
    for pid in verified_in_projects:
        leg = load_project_legend(pid)
        for sym in leg.get("symbols", []):
            key = (
                sym.get("glyph") or "",
                sym.get("colored_line") or "",
                sym.get("colored_hatch") or "",
            )
            if key not in aggregated:
                aggregated[key] = sym
    out = {"architect": architect, "symbols": list(aggregated.values())}
    ARCHITECT_DIR.mkdir(parents=True, exist_ok=True)
    (ARCHITECT_DIR / f"{_safe_id(architect)}.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8",
    )
    return out


def load_architect_legend(architect: str) -> dict:
    p = ARCHITECT_DIR / f"{_safe_id(architect)}.json"
    if not p.exists():
        return {"architect": architect, "symbols": []}
    return json.loads(p.read_text(encoding="utf-8"))


@router.post("/{project_id}")
def post_project_legend(project_id: str, legend: ProjectLegend) -> dict:
    if legend.project_id != project_id:
        raise HTTPException(
            status_code=400,
            detail=f"Body project_id ({legend.project_id}) does not match URL ({project_id})",
        )
    save_project_legend(project_id, legend.model_dump())
    return {"saved": True}


@router.get("/{project_id}")
def get_project_legend(project_id: str) -> dict:
    return load_project_legend(project_id)


@router.post("/architect/{architect}/promote")
def post_architect_promotion(architect: str, body: ArchitectPromotion) -> dict:
    if not body.opt_in:
        raise HTTPException(
            status_code=400,
            detail="opt_in=true required for architect persistence.",
        )
    return promote_to_architect(architect, body.verified_in_projects)


@router.get("/architect/{architect}")
def get_architect_legend(architect: str) -> dict:
    return load_architect_legend(architect)
