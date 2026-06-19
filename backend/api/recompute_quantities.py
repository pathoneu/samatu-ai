# backend/api/recompute_quantities.py
"""POST /api/recompute-quantities — single source of truth for paint
recompute (Sprint 0 Fix 2) plus gesture edits (Sprint 2 G2/G3/G4/G7).

Returns the full updated rooms[] + pozicijos[] so the frontend can
swap the canonical view in one re-render.

Spec: §4.5, §5.4
"""
import re
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
    # Reader/extraction context (_door_types, detected_symbols_summary,
    # _plyteliu_specs, bendras_plotas_m2, v9_meta). Needed so an assumption edit
    # (e.g. ceiling height) can rebuild the CANONICAL pozicijos from the
    # recomputed rooms without losing the door/fixture/symbol lines.
    context: dict = Field(default_factory=dict)


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
                        # Regenerate the human-readable trace so it matches
                        # the new H (Playwright regression 2026-05-10).
                        existing = room.get("elementai") or []
                        n_doors = sum(int(e.get("kiekis") or 1) for e in existing
                                      if (e.get("tipas") or "").lower().startswith("dur"))
                        n_windows = sum(int(e.get("kiekis") or 1) for e in existing
                                        if (e.get("tipas") or "").lower().startswith("lang"))
                        perim = float(room.get("perimetras_m") or 0)
                        room["calculation_trace"] = (
                            f"perim({perim:.2f}) × H({new_h:.2f}) = "
                            f"{perim * new_h:.2f} m² "
                            f"− {n_windows} lang./{n_doors} dur. atimimai → "
                            f"dažymas {room.get('dazymo_plotas_m2', 0):.2f} m². "
                            f"Skaičiavo Python (deterministinis)."
                        )
                    except Exception:
                        pass
            except (ValueError, TypeError):
                pass
        walls = float(room.get("dazomas_plotas_m2", 0) or room.get("walls_paintable_m2", 0) or 0)
        ceiling = float(room.get("lubu_dazomas_plotas_m2", 0) or room.get("ceiling_paintable_m2", 0) or 0)
        room["dazai_l"] = round(walls * absorption / cov_walls, 2) if walls else 0.0
        room["dazai_luboms_l"] = round(ceiling * absorption / cov_ceil, 2) if ceiling else 0.0

        # Recompute glaistas_kg from glaistimo_lygis (Q1-Q4) if assumption set.
        # Playwright regression 2026-05-10: the Q-toggle in Prielaidos was
        # saving glaistimo_lygis but never recomputing the putty kg, so the
        # UI buttons looked dead. CLAUDE.md §1.11 owns the canonical
        # consumption table; vision_call._calc_glaistas_kg implements it.
        q_level = assumptions.get("glaistimo_lygis")
        if q_level:
            try:
                from extractor.vision_call import _calc_glaistas_kg
                dazymo = float(room.get("dazymo_plotas_m2") or 0)
                if dazymo > 0:
                    room["glaistas_kg"] = _calc_glaistas_kg(dazymo, str(q_level))
            except Exception:
                # Recompute is best-effort — leave the prior value rather than
                # raise during a UI-driven assumption tweak.
                pass

        # Wire Week 2 line_items helpers (angokraščiai_m², hidden door frames,
        # real hidroizoliacija m²) into the response so the recompute path
        # surfaces the missing line items the canonical plan added back. These
        # helpers are deterministic + tested; before this hook they only ever
        # ran inside isolated unit tests.
        try:
            from extractor.line_items import (
                opening_reveal_lm, opening_reveal_area_m2,
                hidden_door_count, hidden_door_frame_lm,
            )
            wall_thickness = float(assumptions.get("sienos_storis_m") or 0.10)
            window_sides = int(assumptions.get("window_sides") or 3)
            openings = room.get("elementai") or []
            room["angokrasciai_lm"] = opening_reveal_lm(openings, window_sides=window_sides)
            room["angokrasciai_m2"] = opening_reveal_area_m2(
                openings, wall_thickness_m=wall_thickness, window_sides=window_sides,
            )
            room["pasleptu_duru_kompl"] = hidden_door_count(openings)
            room["pasleptu_duru_staktu_m"] = hidden_door_frame_lm(openings)
        except Exception:
            # Don't block the recompute on a helper hiccup.
            pass

        out.append(room)

    # Also surface the project-wide hidroizoliacija m² (was a wet-room count
    # before the Week 2 fix; now actual square metres per STR 2.04.01).
    try:
        from extractor.line_items import hidroizoliacija_m2
        hidro_total, hidro_warns = hidroizoliacija_m2(out)
        for r in out:
            r["_project_hidroizoliacija_m2"] = hidro_total
            if hidro_warns:
                r["_project_hidroizoliacija_warnings"] = hidro_warns
    except Exception:
        pass

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


_TIER_SUFFIX_RE = re.compile(
    r"\s*\((?:iki|virš)\s*3\s*m[^)]*\)"          # (iki 3m aukščio) / (virš 3 m aukščio)
    r"|\s*\(standartinis aukštis\)"               # GKP tier label
    r"|\s*—\s*papildomas darbas dėl aukščio"      # height-premium tail
    r"|\s*q4\s*\([^)]*\)",                         # Q4 sanding suffix
    re.IGNORECASE,
)


def _norm_label(s: str | None) -> str:
    """Height/Q-level-independent label key: strip the tier suffixes whose text
    flips when a ceiling crosses 3 m or the glaistymo lygis changes, so a priced
    line can be matched to its post-rebuild sibling."""
    return _TIER_SUFFIX_RE.sub("", (s or "").strip().lower()).strip()


def _has_user_edit(p: dict) -> bool:
    return (p.get("kaina") not in (None, 0)
            or p.get("manual_override") is True
            or p.get("quantity_source") == "manual_override"
            or bool(p.get("override_locked")))


def _carry_edit(prev: dict, p: dict) -> None:
    # 1. Manual count override / gesture lock FIRST — these set the final kiekis,
    #    which the price→suma calc below depends on.
    if prev.get("manual_override") is True or prev.get("quantity_source") == "manual_override":
        p["kiekis"] = prev.get("kiekis")
        p["manual_override"] = True
        p["quantity_source"] = prev.get("quantity_source") or "manual_override"
        if prev.get("ai_kiekis_original") is not None:
            p["ai_kiekis_original"] = prev["ai_kiekis_original"]
    if prev.get("override_locked"):
        p["kiekis"] = prev.get("kiekis")
        p["override_locked"] = True
        if prev.get("override_orig") is not None:
            p["override_orig"] = prev["override_orig"]
    # 2. Entered price — carry it and recompute suma from the FINAL kiekis
    #    (rebuilt-or-overridden), not the stale prior suma.
    if prev.get("kaina") not in (None, 0):
        p["kaina"] = prev["kaina"]
        kiekis = p.get("kiekis")
        p["suma"] = (round(float(kiekis) * float(prev["kaina"]), 2)
                     if isinstance(kiekis, (int, float)) else prev.get("suma"))


def _merge_user_edits(rebuilt: list[dict], prior: list[dict]) -> list[dict]:
    """After a canonical pozicijos rebuild (ceiling/assumption edit), carry the
    user's manual edits forward from the prior pozicijos so the rebuild doesn't
    silently revert them.

    Two-pass match:
      1. EXACT aprasymas — handles the common case and the simultaneously-present
         iki/virš tier pair in mixed-height projects (no collision).
      2. HEIGHT-INDEPENDENT fallback for any prior edited line left unmatched
         (its label flipped across the 3 m / Q-level boundary, e.g. a priced
         '… (virš 3m aukščio)' line that became '… (iki 3m aukščio)'). Applied
         ONLY when unambiguous — exactly one unmatched edited prior line and one
         unmatched rebuilt line share the normalized key — so it can never
         mis-assign a price between the two co-existing tier lines.

    Preserved: kaina/suma (prices), manual count overrides, gesture locks.
    Formula/geometry quantities are otherwise recomputed (the point of the rebuild).
    """
    if not prior:
        return rebuilt
    prior_by_label: dict[str, dict] = {}
    for p in prior:
        lab = (p.get("aprasymas") or "").strip().lower()
        if lab:
            prior_by_label.setdefault(lab, p)

    matched_prior: set[int] = set()
    matched_rebuilt: set[int] = set()
    for p in rebuilt:
        prev = prior_by_label.get((p.get("aprasymas") or "").strip().lower())
        if prev is not None:
            _carry_edit(prev, p)
            matched_prior.add(id(prev))
            matched_rebuilt.add(id(p))

    # Pass 2 — rescue user edits on prior lines whose label changed on rebuild.
    leftover_prior_by_norm: dict[str, list[dict]] = {}
    for p in prior:
        if id(p) in matched_prior or not _has_user_edit(p):
            continue
        leftover_prior_by_norm.setdefault(_norm_label(p.get("aprasymas")), []).append(p)
    if leftover_prior_by_norm:
        leftover_rebuilt_by_norm: dict[str, list[dict]] = {}
        for p in rebuilt:
            if id(p) in matched_rebuilt:
                continue
            leftover_rebuilt_by_norm.setdefault(_norm_label(p.get("aprasymas")), []).append(p)
        for norm, priors in leftover_prior_by_norm.items():
            cands = leftover_rebuilt_by_norm.get(norm, [])
            if len(priors) == 1 and len(cands) == 1:  # unambiguous → safe to carry
                _carry_edit(priors[0], cands[0])
    return rebuilt


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

    # 5. If an ASSUMPTION edit changed room geometry (e.g. ceiling height), the
    # aggregated pozicijos (paint iki/virš split, kampai, GKP virš-3m, karnizas…)
    # must be rebuilt from the recomputed rooms — otherwise the displayed/exported
    # numbers stay stale (the Prielaidos recompute bug, 2026-06-17). Rebuild via
    # the canonical builder, carrying the reader context so door/fixture/symbol
    # lines survive. Gesture-only edits keep the in-place pozicijos above.
    assumption_edited = any(e.field in _ASSUMPTION_FIELDS for e in req.edits)
    if assumption_edited and req.context:
        try:
            from extractor.vision_call import _build_pozicijos_from_rooms
            overrides = {**(req.context.get("_overrides") or {}), **assumptions}
            # The Prielaidos field is `glaistimo_lygis`, but the canonical builder
            # reads the Q-level under `glaistas_q_lygis` (vision_call.py). Bridge
            # the two names so a Q4 toggle actually emits the Q4 sanding-labor line.
            if assumptions.get("glaistimo_lygis"):
                overrides["glaistas_q_lygis"] = assumptions["glaistimo_lygis"]
            parsed = {
                **req.context,
                "patalpos": rooms,
                "_overrides": overrides,
            }
            rebuilt = _build_pozicijos_from_rooms(parsed)
            if rebuilt.get("pozicijos"):
                # Carry the user's manual edits (prices, corrected counts,
                # locks) forward so the rebuild doesn't silently revert them.
                pozicijos = _merge_user_edits(rebuilt["pozicijos"], list(req.pozicijos))
        except Exception as exc:  # noqa: BLE001 — never break the recompute
            print(f"[recompute-quantities] canonical pozicijos rebuild failed: {exc}")

    # Also emit the V8-compat darbu_sarasas from the final pozicijos. The Kiekiai
    # table, the top-bar totals AND the Excel/PDF export all read darbu_sarasas —
    # NOT pozicijos — so without this a Prielaidos recompute updated pozicijos but
    # the visible/exported quantities stayed stale (2026-06-19 workspace hunt).
    # The frontend re-applies the user's entered prices by matching aprasymas.
    darbu_sarasas: list[dict] = []
    try:
        from extractor.vision_call import _emit_v8_compat_fields
        darbu_sarasas = _emit_v8_compat_fields(
            {"pozicijos": pozicijos, "santrauka": {}}
        ).get("darbu_sarasas", [])
    except Exception as exc:  # noqa: BLE001 — never break the recompute on compat emit
        print(f"[recompute-quantities] v8-compat emit failed: {exc}")

    return {
        "rooms": rooms,
        "pozicijos": pozicijos,
        "darbu_sarasas": darbu_sarasas,
        "assumptions": assumptions,
    }
