"""POST /api/projects/{project_id}/rooms/{room_nr}/recalc

Per-room math recompute. The Annotator's per-wall-edit feature calls
this whenever the user redraws a wall length: backend recomputes the
single room's totals via ``calc_room_quantities`` (no Vision, no DB
write) and returns the updated room dict plus the project-level
santrauka delta. Sub-50ms target.

Two modes, controlled by the body:
  1. ``walls`` — list of {wall_id, length_mm}; we accumulate into a new
     perimetras_m and recalc with that. Used by the wall-editing UI.
  2. ``primitives`` — full overrides for primitives (perimetras_m,
     lubu_aukstis_m, elementai, …). Used by the "Verify All Rooms"
     walkthrough.

Returns ``{room, santrauka_delta, prev_santrauka, new_santrauka}`` so
the frontend can render the delta inline.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query, Request

import db as _db
import auth as _auth
from extractor.vision_call import (
    _recompute_per_room_via_python, _recompute_santrauka,
)
from extractor.universal_rules import calc_room_quantities, calc_totals
from extractor.vision_call import _elementai_to_counts

REPO_ROOT = Path(__file__).resolve().parents[2]
import json
FIXTURES = {
    "berzas": REPO_ROOT / "docs/superpowers/fixtures/2026-05-26-berzu-g-24/app-output-to-the-dot.json",
}

router = APIRouter(prefix="/api/projects", tags=["room-recalc"])


def _load_project(request: Request, project_id: str, fixture: str | None) -> dict[str, Any]:
    # SECURITY (pass-3 sweep, 2026-07-04): the ``fixture`` branch RETURNS BEFORE
    # auth. This is only safe because recalc_room is a PURE in-memory compute — it
    # reads NO ``{URL_project_id}``-keyed per-user store (no data/annotations,
    # data/calibrations, PDF cache). If you EVER add such a store read to this
    # handler, you MUST call ``_auth.require_owned_project(request, project_id)``
    # FIRST (before this fixture branch), or ``?fixture=`` becomes an unauth
    # cross-tenant read (the P1/P2 class). Do not "optimise" the fixture branch to
    # touch a per-project file.
    if fixture:
        p = FIXTURES.get(fixture)
        if not p or not p.exists():
            raise HTTPException(status_code=404, detail=f"unknown fixture: {fixture}")
        return json.loads(p.read_text(encoding="utf-8"))
    user = _auth.require_user(request)
    user_filter = None if user.get("is_admin") else user["id"]
    proj = _db.get_project(project_id, user_id=user_filter)
    if not proj:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    return proj


def _santrauka_from_rooms(rooms: list[dict[str, Any]]) -> dict[str, Any]:
    """Light version of _recompute_santrauka tailored for the recalc path —
    operates on already-calc'd rooms, so we don't re-invoke the per-room
    engine."""
    mapped = []
    for r in rooms:
        mapped.append({
            "plotas_m2": r.get("plotas_m2", 0),
            "dazymo_plotas_m2": r.get("dazymo_plotas_m2", 0),
            "kampu_metrai": r.get("kampu_metrai") or r.get("kampai_m") or 0,
            "angokrasciu_gkp_m": r.get("angokrasciu_gkp_m", 0),
            "nisu_metrai": r.get("nisu_metrai", 0),
            "pvc_grindys_m2": r.get("pvc_grindys_m2", 0),
            "plyteles_grindys_m2": r.get("plyteles_grindys_m2", 0),
            "plyteles_sienos_m2": r.get("plyteles_sienos_m2", 0),
            "isliginamasis_m2": r.get("isliginamasis_m2", 0),
            "grindjuosciu_m": r.get("grindjuosciu_m") or r.get("grindjuostes_m") or 0,
            "hidroizoliacija_m2": r.get("hidroizoliacija_m2", 0),
            "lubu_tipas": r.get("lubu_tipas", "gkp"),
            "lubu_aukstis_m": r.get("lubu_aukstis_m", 2.82),
            "paskirtis": r.get("paskirtis", "gyvenamoji"),
            "gkp_lubu_standart_m2": r.get("gkp_lubu_standart_m2"),
            "gkp_lubu_virs_3m_m2": r.get("gkp_lubu_virs_3m_m2"),
        })
    totals = calc_totals(mapped)
    # Excl-garazas slice (matches _recompute_santrauka)
    house_paint_total = sum(
        float(r.get("dazymo_plotas_m2") or 0)
        for r in rooms if (r.get("paskirtis") or "").lower() != "garazas"
    )
    return {
        "dazymo_plotas_total_m2": totals.get("dazymo_plotas_total_m2", 0),
        "dazymo_excl_garazas_total_m2": round(house_paint_total, 2),
        "kampai_m_total": totals.get("kampai_m_total", 0),
        "angokrasciu_gkp_m_total": totals.get("angokrasciu_gkp_m_total", 0),
        "nisu_metrai_total": totals.get("nisu_metrai_total", 0),
        "gkp_lubu_m2_total": totals.get("gkp_lubu_m2_total", 0),
        "gkp_lubu_virs_3m_m2_total": totals.get("gkp_lubu_virs_3m_m2_total", 0),
        "pvc_grindys_m2_total": totals.get("pvc_grindys_m2_total", 0),
        "plyteles_grindys_m2_total": totals.get("plyteles_grindys_m2_total", 0),
        "plyteles_sienos_m2_total": totals.get("plyteles_sienos_m2_total", 0),
        "isliginamasis_m2_total": totals.get("isliginamasis_m2_total", 0),
        "grindjuosciu_m_total": totals.get("grindjuosciu_m_total", 0),
        "hidroizoliacijos_vnt": totals.get("hidroizoliacijos_vnt", 0),
    }


def _recalc_room(room: dict[str, Any], primitive_overrides: dict[str, Any]) -> dict[str, Any]:
    """Apply primitive overrides to a single room dict and return the
    recalculated room. Uses the same calc path as the production pipeline
    so behaviour is consistent."""
    # Strip prior computed fields so the calculator's output overrides cleanly.
    primitives = {
        "nr", "pavadinimas", "paskirtis", "puslapio_nr", "bbox_pct",
        "plotas_m2", "perimetras_m", "lubu_aukstis_m", "lubu_tipas",
        "elementai", "plyteles_sienos_aukstis_m", "sienu_apdailos_breakdown",
        "ceiling_geometry", "slope_angle_deg", "max_height_m", "room_type",
        "door_area_m2", "window_area_m2",
        "walls_paint_factor_override", "tile_floor_override",
        "extra_walls_m2", "extra_walls_virs_3m_m2", "high_ceiling_area_m2",
        "plyteles_grindys_m2_override", "gkp_extra_area_m2",
        "n_exterior_doors", "n_exterior_windows",
    }
    new_room = {k: v for k, v in room.items() if k in primitives}
    new_room.update(primitive_overrides)
    # Re-derive opening counts from elementai
    counts = _elementai_to_counts(new_room.get("elementai") or [])
    calc_input = {**new_room, **counts}
    computed = calc_room_quantities(calc_input)
    # Merge: primitives win, computed overrides everything else
    out = {**new_room, **{k: v for k, v in computed.items() if k not in primitives}}
    return out


@router.post("/{project_id}/rooms/{room_nr}/recalc")
async def recalc_room(
    request: Request,
    project_id: str,
    room_nr: str,
    body: dict[str, Any] = Body(...),
    fixture: str | None = Query(default=None),
) -> dict[str, Any]:
    parsed = _load_project(request, project_id, fixture)
    rooms = parsed.get("patalpos") or []
    idx = next((i for i, r in enumerate(rooms) if str(r.get("nr")) == str(room_nr)), -1)
    if idx < 0:
        raise HTTPException(status_code=404, detail=f"room {room_nr} not in project")
    original_room = rooms[idx]

    # Capture prior santrauka if present in the saved parsed (fixture has one;
    # DB-backed projects also store it). Otherwise compute it.
    prev_santrauka = parsed.get("santrauka") or _santrauka_from_rooms(rooms)

    # Build primitive overrides from the body.
    primitive_overrides: dict[str, Any] = {}
    walls = body.get("walls")
    if isinstance(walls, list) and walls:
        # Caller sent {wall_id, length_mm} list. Sum lengths → new perim.
        try:
            total_mm = sum(float(w["length_mm"]) for w in walls)
        except (KeyError, TypeError, ValueError) as e:
            raise HTTPException(status_code=400, detail=f"invalid walls payload: {e}")
        primitive_overrides["perimetras_m"] = round(total_mm / 1000.0, 3)

    primitives_extra = body.get("primitives") or {}
    if isinstance(primitives_extra, dict):
        primitive_overrides.update(primitives_extra)

    if not primitive_overrides:
        raise HTTPException(status_code=400, detail="body must include walls or primitives")

    # Recalc the target room
    new_room = _recalc_room(original_room, primitive_overrides)
    new_rooms = list(rooms)
    new_rooms[idx] = new_room

    new_santrauka = _santrauka_from_rooms(new_rooms)
    santrauka_delta = {
        k: round(float(new_santrauka.get(k, 0)) - float(prev_santrauka.get(k, 0)), 3)
        for k in new_santrauka if isinstance(new_santrauka.get(k), (int, float))
    }

    return {
        "project_id": project_id,
        "room_nr": room_nr,
        "room": new_room,
        "prev_santrauka": prev_santrauka,
        "new_santrauka": new_santrauka,
        "santrauka_delta": santrauka_delta,
        "primitive_overrides": primitive_overrides,
    }
