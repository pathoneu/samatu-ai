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

Pathon v3 (2026-10-18, W2-A A4):
  * a project legend carries `rows` — the legend rows the person accepted in
    „Pažymėti legendą" (extractor/legend_rows.py shape: glyph box, kind, text),
    written only when the UI commits them; the counting routes
    (api/legend_count.py) save nothing;
  * the architect legend is the CALLER'S OWN: stored per owner under
    `data/legends/architect/<user id>/<architect>.json` (audit 2026-09-29,
    backend-security-14: it was one global file per architect name, so any
    signed-in user read — and overwrote — what another user had promoted).
    A user reads and promotes only from projects they own; another user's
    aggregate of the same architect name is invisible to them;
  * project-scoped twins of the architect routes
    (`GET/POST /api/projects/{project_id}/legend/architect…`) are what the
    cross-project reuse (W2-B, B4) calls: the owner check on the project comes
    first, and the routes are in the ownership-policy walk.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict

import auth as _auth
import db as _db

router = APIRouter(prefix="/api/legends", tags=["legends"])
project_router = APIRouter(prefix="/api/projects", tags=["legends"])

LEGENDS_DIR = Path(__file__).resolve().parents[2] / "data" / "legends"
ARCHITECT_DIR = LEGENDS_DIR / "architect"


class LegendSymbol(BaseModel):
    glyph: str | None = None
    colored_line: str | None = None
    colored_hatch: str | None = None
    meaning: str
    confidence: float = 0.5


class LegendRow(BaseModel):
    """One accepted legend row (extractor/legend_rows.py), plus the person's own name for it."""
    model_config = ConfigDict(extra="ignore")
    row_id: str
    page: int
    glyph_bbox_pct: list[float]
    glyph_box_pt: list[float] | None = None
    glyph_kind: str | None = None
    colour: str | None = None
    glyph_text: str | None = None
    text: str = ""
    text_bbox_pct: list[float] | None = None
    legend_bbox_pct: list[float] | None = None
    countable: bool = True
    name: str | None = None            # „Kitas pavadinimas" — the person's name for the count type


class ProjectLegend(BaseModel):
    project_id: str
    architect: str | None = None
    symbols: list[LegendSymbol] = []
    rows: list[LegendRow] = []


class ArchitectPromotion(BaseModel):
    opt_in: bool
    verified_in_projects: list[str]


class ProjectArchitectPromotion(BaseModel):
    architect: str
    opt_in: bool
    verified_in_projects: list[str]


def _safe_id(name: str) -> str:
    if not name or "/" in name or ".." in name or "\\" in name:
        raise HTTPException(status_code=400, detail=f"Invalid identifier: {name!r}")
    return name


def _require_project_access(request: Request, project_id: str) -> dict:
    """Auth + ownership gate (F1, 2026-07-04 pentest).

    The legend routes wrote/read per-project files under data/legends/** keyed
    only by project_id, with no auth and no ownership check — an anonymous caller
    could poison or read any project's symbol legend, and the architect-promote
    route let a caller aggregate legends from ANY project id it named. Require a
    logged-in user (401), then scope db.get_project to the caller (admins see
    all). Missing/foreign project → 404 (do not leak existence). Returns the
    caller's user dict.
    """
    user = _auth.require_user(request)  # 401 if not logged in
    user_filter = None if user.get("is_admin") else user["id"]
    if _db.get_project(project_id, user_id=user_filter) is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    return user


def _owner_key(user: dict) -> str:
    """The caller's folder under ARCHITECT_DIR — their user id, made path-safe."""
    key = re.sub(r"[^A-Za-z0-9_-]", "_", str(user.get("id") or ""))
    if not key:
        raise HTTPException(status_code=401, detail="Reikia prisijungti")
    return key


def save_project_legend(project_id: str, legend: dict) -> None:
    LEGENDS_DIR.mkdir(parents=True, exist_ok=True)
    (LEGENDS_DIR / f"{_safe_id(project_id)}.json").write_text(
        json.dumps(legend, indent=2, ensure_ascii=False), encoding="utf-8",
    )


def load_project_legend(project_id: str) -> dict:
    p = LEGENDS_DIR / f"{_safe_id(project_id)}.json"
    if not p.exists():
        return {"project_id": project_id, "symbols": [], "rows": []}
    data = json.loads(p.read_text(encoding="utf-8"))
    data.setdefault("rows", [])
    return data


def _row_key(row: dict) -> tuple:
    text = re.sub(r"\s+", " ", str(row.get("name") or row.get("text") or "")).strip().lower()
    return (row.get("glyph_kind") or "", row.get("colour") or "", row.get("glyph_text") or "", text)


def promote_to_architect(architect: str, verified_in_projects: list[str], owner: str) -> dict:
    """Aggregate ≥2 verified project legends into the OWNER'S architect-level dictionary."""
    if len(verified_in_projects) < 2:
        raise HTTPException(
            status_code=400,
            detail="Architect promotion requires at least 2 verified projects.",
        )
    aggregated: dict[tuple, dict] = {}
    rows: dict[tuple, dict] = {}
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
        for row in leg.get("rows", []):
            if isinstance(row, dict) and _row_key(row) not in rows:
                rows[_row_key(row)] = {**row, "from_project": pid}
    out = {"architect": architect, "symbols": list(aggregated.values()), "rows": list(rows.values())}
    folder = ARCHITECT_DIR / _safe_id(owner)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{_safe_id(architect)}.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8",
    )
    return out


def load_architect_legend(architect: str, owner: str) -> dict:
    p = ARCHITECT_DIR / _safe_id(owner) / f"{_safe_id(architect)}.json"
    if not p.exists():
        return {"architect": architect, "symbols": [], "rows": []}
    data = json.loads(p.read_text(encoding="utf-8"))
    data.setdefault("rows", [])
    return data


def _promote(request: Request, architect: str, opt_in: bool, verified: list[str]) -> dict:
    # Architect promotion aggregates legends from several projects — the caller
    # MUST own every project it names, or it could pull symbol mappings out of
    # another tenant's projects (F1, 2026-07-04 pentest). Gate each one.
    user = _auth.require_user(request)
    for pid in verified:
        _require_project_access(request, pid)
    if not opt_in:
        raise HTTPException(
            status_code=400,
            detail="opt_in=true required for architect persistence.",
        )
    return promote_to_architect(architect, verified, _owner_key(user))


@router.post("/{project_id}")
def post_project_legend(project_id: str, legend: ProjectLegend, request: Request) -> dict:
    _require_project_access(request, project_id)
    if legend.project_id != project_id:
        raise HTTPException(
            status_code=400,
            detail=f"Body project_id ({legend.project_id}) does not match URL ({project_id})",
        )
    save_project_legend(project_id, legend.model_dump())
    return {"saved": True}


@router.get("/{project_id}")
def get_project_legend(project_id: str, request: Request) -> dict:
    _require_project_access(request, project_id)
    return load_project_legend(project_id)


@router.post("/architect/{architect}/promote")
def post_architect_promotion(architect: str, body: ArchitectPromotion, request: Request) -> dict:
    return _promote(request, architect, body.opt_in, body.verified_in_projects)


@router.get("/architect/{architect}")
def get_architect_legend(architect: str, request: Request) -> dict:
    # The caller's own aggregate only (backend-security-14): another user's
    # promotion under the same architect name is not theirs to read.
    user = _auth.require_user(request)
    return load_architect_legend(architect, _owner_key(user))


# ── project-scoped (the cross-project reuse calls these; in the ownership walk) ──


@project_router.get("/{project_id}/legend/architect")
def get_project_architect_legend(project_id: str, request: Request, architect: str | None = None) -> dict:
    """The caller's architect legend for this project's architect (`architect`, else the one the project's
    saved legend names) — what „Rasta ankstesnio projekto legenda — pritaikyti?" offers."""
    user = _require_project_access(request, project_id)       # ownership before anything about the request
    name = architect or load_project_legend(project_id).get("architect")
    if not name:
        return {"architect": None, "symbols": [], "rows": []}
    return load_architect_legend(str(name), _owner_key(user))


@project_router.post("/{project_id}/legend/architect/promote")
def post_project_architect_promotion(project_id: str, body: ProjectArchitectPromotion, request: Request) -> dict:
    _require_project_access(request, project_id)              # ownership before anything about the request
    verified = list(body.verified_in_projects)
    if project_id not in verified:
        verified.insert(0, project_id)
    return _promote(request, body.architect, body.opt_in, verified)
