"""POST /api/recompute-quantities — apply user edits to assumptions/quantities,
return recomputed full KŽ.

Replaces the frontend hardcoded paint formula at interiorCalc.js:187-188
which diverged from backend's paint class model.

See docs/superpowers/specs/2026-05-03-takeoff-workspace-design.md §7 Fix 2.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from extractor.universal_rules import UNIVERSAL_RULES, paint_coverage_for_class

router = APIRouter(prefix="/api", tags=["recompute"])


class Edit(BaseModel):
    field: str
    new_value: float | int | str
    room_name: str | None = None  # if None, applies to all rooms


class RecomputeRequest(BaseModel):
    rooms: list[dict]
    edits: list[Edit]
    current_assumptions: dict


# Sprint 0 scope: only `paint_class` is wired through to recompute output.
# Other fields are accepted (forward-compat for Tasks 6, 7, and future sprints
# that wire ceiling height, wall thickness, etc. into the formula stack), but
# editing them today does not change returned quantities. Tracked as follow-up.
_VALID_FIELDS = {
    "paint_class",        # Sprint 0 — wired
    "lubu_aukstis",       # Sprint 0 Fix 4 (Task 6) — accepted, will wire then
    "sienos_storis",      # Future — accepted, no-op today
    "plyteliu_aukstis",   # Future — accepted, no-op today
    "kampu_skaicius",     # Future — accepted, no-op today
}


@router.post("/recompute-quantities")
def recompute(req: RecomputeRequest) -> dict:
    # 1. Validate edit fields
    for e in req.edits:
        if e.field not in _VALID_FIELDS:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown field '{e.field}'; valid: {sorted(_VALID_FIELDS)}"
            )

    # 2. Apply edits to assumptions
    assumptions = {**req.current_assumptions}
    for e in req.edits:
        assumptions[e.field] = e.new_value

    # 3. Recompute paint per room using paint class model (NOT hardcoded *2/9)
    paint_class = int(assumptions.get("paint_class", 1))
    coverage_walls, coverage_ceiling = paint_coverage_for_class(paint_class)

    out_rooms = []
    for r in req.rooms:
        room = {**r}
        walls = float(r.get("dazomas_plotas_m2", 0) or 0)
        ceiling = float(r.get("lubu_dazomas_plotas_m2", 0) or 0)
        # 2 coats with first_coat_factor absorption (NOT 2.0×)
        absorption = float(UNIVERSAL_RULES["first_coat_factor"])
        room["dazai_l"] = round(walls * absorption / coverage_walls, 2) if walls else 0.0
        room["dazai_luboms_l"] = round(ceiling * absorption / coverage_ceiling, 2) if ceiling else 0.0
        out_rooms.append(room)

    return {
        "rooms": out_rooms,
        "pozicijos": [],
        "assumptions": assumptions,
    }
