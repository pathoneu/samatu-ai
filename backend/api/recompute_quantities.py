# backend/api/recompute_quantities.py
"""POST /api/recompute-quantities — single source of truth for paint
recompute (Sprint 0 Fix 2) plus gesture edits (Sprint 2 G2/G3/G4/G7).

Returns the full updated rooms[] + pozicijos[] so the frontend can
swap the canonical view in one re-render.

Spec: §4.5, §5.4
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Any
from extractor.universal_rules import UNIVERSAL_RULES, paint_coverage_for_class

router = APIRouter(prefix="/api", tags=["recompute"])


class Edit(BaseModel):
    field: str
    new_value: Any | None = None
    room_name: str | None = None
    target_pozicija_id: str | None = None
    target_room_id: str | None = None
    delta: int | None = None
    point_xy_pct: list[float] | None = None
    color_rgb: list[int] | None = None
    polygons_pct: list[list[list[float]]] | None = None


class RecomputeRequest(BaseModel):
    rooms: list[dict]
    pozicijos: list[dict] = Field(default_factory=list)
    edits: list[Edit]
    current_assumptions: dict


# Sprint 0: assumption-class fields. Sprint 2 adds gesture fields below.
# 2026-05-06 (#7): lubu_auksciai (per-room dict, plural) added so the
# AssumptionsPanel per-room ceiling-height inputs trigger backend recompute.
_ASSUMPTION_FIELDS = {
    "paint_class", "lubu_aukstis", "sienos_storis",
    "plyteliu_aukstis", "kampu_skaicius",
    "lubu_auksciai", "glaistimo_lygis", "sienos_storis_m",
    "custom_windows", "custom_doors",
}
_GESTURE_FIELDS = {
    "add_symbol",        # G2
    "remove_symbol",     # G3
    "color_zone",        # G4
    "override_pozicija", # G7
}
_VALID_FIELDS = _ASSUMPTION_FIELDS | _GESTURE_FIELDS


def _apply_assumption_edits(rooms: list[dict], assumptions: dict) -> list[dict]:
    """Sprint 0: paint formula recompute from class.
    2026-05-06: per-room aukštis (lubu_auksciai dict) triggers full
    walls_paintable_m2 + ceiling_paintable_m2 recompute via calc_room_quantities.
    """
    paint_class = int(assumptions.get("paint_class", 1))
    cov_walls, cov_ceil = paint_coverage_for_class(paint_class)
    absorption = float(UNIVERSAL_RULES["first_coat_factor"])
    per_room_h = assumptions.get("lubu_auksciai") or {}
    default_h = float(assumptions.get("lubu_aukstis") or 2.82)

    out = []
    for r in rooms:
        room = {**r}
        # If user overrode this room's ceiling, swap it in BEFORE the calc.
        nr = str(r.get("nr") or "")
        if isinstance(per_room_h, dict) and nr in per_room_h:
            try:
                new_h = float(per_room_h[nr])
                if 1.5 <= new_h <= 8.0:
                    room["lubu_aukstis_m"] = round(new_h, 2)
                    room["lubu_aukstis_saltinis"] = "user_override"
                    # Recompute geometry-derived fields with the new height.
                    try:
                        from extractor.universal_rules import calc_room_quantities
                        recalc = calc_room_quantities(room, ceiling_height_m=new_h)
                        # Carry forward the recomputed wall/ceiling/cornice fields.
                        for k in ("walls_gross_m2", "walls_paintable_m2",
                                  "ceiling_paintable_m2", "dazymo_plotas_m2",
                                  "kampai_m", "kampu_metrai", "lubu_karnizo_m",
                                  "glaistas_kg", "gruntas_l"):
                            if k in recalc:
                                room[k] = recalc[k]
                    except Exception:
                        pass
            except (ValueError, TypeError):
                pass
        walls = float(room.get("dazomas_plotas_m2", 0) or room.get("walls_paintable_m2", 0) or 0)
        ceiling = float(room.get("lubu_dazomas_plotas_m2", 0) or room.get("ceiling_paintable_m2", 0) or 0)
        room["dazai_l"] = round(walls * absorption / cov_walls, 2) if walls else 0.0
        room["dazai_luboms_l"] = round(ceiling * absorption / cov_ceil, 2) if ceiling else 0.0
        out.append(room)
    return out


def _apply_gesture_edits(rooms: list[dict], pozicijos: list[dict],
                         edits: list[Edit]) -> tuple[list[dict], list[dict]]:
    """Sprint 2: G2/G3/G4/G7 dispatch."""
    rooms_by_id = {r.get("id"): r for r in rooms if r.get("id")}
    poz_by_id = {p.get("id"): p for p in pozicijos if p.get("id")}

    for e in edits:
        if e.field == "add_symbol":
            if not e.target_pozicija_id:
                raise HTTPException(
                    status_code=400,
                    detail="add_symbol: target_pozicija_id is required",
                )
            poz = poz_by_id.get(e.target_pozicija_id)
            if poz is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"add_symbol: pozicija id '{e.target_pozicija_id}' not found",
                )
            poz["kiekis"] = (poz.get("kiekis") or 0) + (e.delta or 1)
            poz.setdefault("user_points", []).append({
                "delta": e.delta or 1,
                "xy_pct": e.point_xy_pct,
            })
        elif e.field == "remove_symbol":
            if not e.target_pozicija_id:
                raise HTTPException(
                    status_code=400,
                    detail="remove_symbol: target_pozicija_id is required",
                )
            poz = poz_by_id.get(e.target_pozicija_id)
            if poz is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"remove_symbol: pozicija id '{e.target_pozicija_id}' not found",
                )
            new_kiekis = (poz.get("kiekis") or 0) - (e.delta or 1)
            poz["kiekis"] = max(0, new_kiekis)
        elif e.field == "color_zone":
            if not e.target_room_id:
                raise HTTPException(
                    status_code=400,
                    detail="color_zone: target_room_id is required",
                )
            room = rooms_by_id.get(e.target_room_id)
            if room is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"color_zone: room id '{e.target_room_id}' not found",
                )
            room.setdefault("color_zones", []).append({
                "color_rgb": list(e.color_rgb or []),
                "polygons_pct": e.polygons_pct or [],
            })
        elif e.field == "override_pozicija":
            if not e.target_pozicija_id:
                raise HTTPException(
                    status_code=400,
                    detail="override_pozicija: target_pozicija_id is required",
                )
            poz = poz_by_id.get(e.target_pozicija_id)
            if poz is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"override_pozicija: pozicija id '{e.target_pozicija_id}' not found",
                )
            if "override_orig" not in poz:
                poz["override_orig"] = poz.get("kiekis")
            poz["kiekis"] = float(e.new_value) if e.new_value is not None else poz["kiekis"]
            poz["override_locked"] = True

    out_rooms = [rooms_by_id[r["id"]] if r.get("id") in rooms_by_id else r for r in rooms]
    return out_rooms, pozicijos


@router.post("/recompute-quantities")
def recompute(req: RecomputeRequest) -> dict:
    # 1. Validate
    for e in req.edits:
        if e.field not in _VALID_FIELDS:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown field '{e.field}'; valid: {sorted(_VALID_FIELDS)}"
            )

    # 2. Apply assumption edits to assumptions dict
    assumptions = {**req.current_assumptions}
    for e in req.edits:
        if e.field in _ASSUMPTION_FIELDS:
            assumptions[e.field] = e.new_value

    # 3. Recompute paint per room (Sprint 0 logic)
    rooms = _apply_assumption_edits(list(req.rooms), assumptions)

    # 4. Apply gesture edits (Sprint 2)
    rooms, pozicijos = _apply_gesture_edits(rooms, list(req.pozicijos), req.edits)

    return {"rooms": rooms, "pozicijos": pozicijos, "assumptions": assumptions}
