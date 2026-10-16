# backend/api/recompute_quantities.py
"""POST /api/recompute-quantities — single source of truth for paint
recompute (Sprint 0 Fix 2) plus gesture edits (Sprint 2 G2/G3/G4/G7).

Returns the full updated rooms[] + pozicijos[] so the frontend can
swap the canonical view in one re-render.

Spec: §4.5, §5.4
"""
from extractor import user_text as _user_text
import logging
import re
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Any
from extractor.universal_rules import paint_coverage_for_class

import auth as _auth

router = APIRouter(prefix="/api", tags=["recompute"])

log = logging.getLogger("samatu.recompute")


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
    # 2026-07-28 (P0): the user's PRICES live in `darbu_sarasas`, not in
    # `pozicijos` — the demo snapshot and every real project blob carry
    # pozicijos 0/73 priced vs darbu_sarasas 73/73 priced. Optional: when the
    # caller forwards it, the merge treats a position priced there as
    # user-edited, so tier-flip rescue + price carry-forward see the real money.
    darbu_sarasas: list[dict] = Field(default_factory=list)


# Sprint 0: assumption-class fields. Sprint 2 adds gesture fields below.
# 2026-05-06 (#7): lubu_auksciai (per-room dict, plural) added so the
# AssumptionsPanel per-room ceiling-height inputs trigger backend recompute.
_ASSUMPTION_FIELDS = {
    "paint_class", "lubu_aukstis", "sienos_storis",
    "plyteliu_aukstis", "kampu_skaicius",
    "lubu_auksciai", "glaistimo_lygis", "sienos_storis_m",
    "custom_windows", "custom_doors",
    # 2026-07-05: per-room finishing override (Objektas A garage: contractors finish
    # some garages/tambūrai — painted walls — that default to raw. Keyed by
    # patalpa.nr → 0.0 (raw) / 1.0 (painted). Flips walls_paint in the room's
    # rules and recomputes the paint fields, same live path as ceiling height.
    "walls_paint_override",
    # 2026-09-02: per-room ĮTEMPIAMOS LUBOS. Keyed by patalpa.nr → 1
    # (įtempiamos) / 0 (dažomos); absent means dažomos. A flagged room drops out
    # of the lubų glaistymas/gruntavimas/dažymas/šlifavimas lines (both height
    # tiers) — a stretch membrane is a separate trade and none of that work
    # happens under it. Karnizas / LED nišos / GKP lubos / grindjuostės are
    # untouched. Read by the canonical builder through `_overrides`
    # (extractor/vision_call._stretch_ceiling_nrs), so it needs no per-room
    # geometry recompute here.
    "stretch_ceiling_override",
    # 2026-07-29: concealed-vs-surface mixer. The builder splits a POTINKINIS
    # mixer into its rough-in + trim pair and says so as a disclosed assumption
    # (nothing we read tells us which it is). CLAUDE.md's rule — every
    # assumption must be overridable with a live recalc — means the answer has
    # to be reachable through this endpoint. Accepts a bool (whole project) or
    # {"praustuve"|"dusas"|"vonia"|"bide": bool}; both shapes land in
    # `_overrides` verbatim and are read by `_resolve_san_concealment`.
    "santechnika_potinkinis",
    # 2026-09-23: are the interior doors nobody tagged frameless (beapvadinės)? True / False — his answer
    # to the door-type question (or the Prielaidos switch); read by
    # universal_rules.settle_frameless_default ahead of anything the drawing says.
    "vidaus_durys_beapvadines",
    # 2026-09-25: which openings' reveals (angokraščiai) he bills — {langai, lauko_durys, praejimai,
    # vidaus_durys: bool}; read by universal_rules.settle_reveals_scope. Scope, not a reading: the drawing
    # shows the openings, the contractor decides which reveals are his.
    "angokrasciai_apimtis",
    # 2026-10-06: is an LED niche length estimated from the room type billed? True once he chose
    # „Priimti įvertinimą" in Nustatymai; read by niche_inference.estimate_accepted. Every room's billed
    # metres are rebuilt below (vision_call.refresh_led_metres), the same way the other two paths do.
    "led_nisu_ivertinimas",
}
_GESTURE_FIELDS = {
    "add_symbol",        # G2
    "remove_symbol",     # G3
    "color_zone",        # G4
    "override_pozicija", # G7
}
_VALID_FIELDS = _ASSUMPTION_FIELDS | _GESTURE_FIELDS

# Sentinel for "key absent" — an absent assumption falls back silently, a
# SUPPLIED but unparseable one is recorded in _degradations (audit fix 3).
_MISSING = object()

# The four addends behind `kampu_metrai` (restored 2026-09-02 for the
# contribution ledger). They travel with the parent total through every
# carry-forward below: a room whose corner metres were recomputed but whose
# terms were not would render an equation that contradicts its own result.
_KAMPAI_TERMS = ("kampai_inner_m", "kampai_opening_reveals_m",
                 "kampai_pusiniai_m", "kampai_perimetras_m")


def _num(v, default: float) -> float:
    """Tolerant float coercion — a malformed assumption/room field must degrade,
    never 500 the whole recompute (2026-07-27 audit, finding 3)."""
    try:
        if v is None or (isinstance(v, str) and not v.strip()):
            return float(default)
        return float(v)
    except (TypeError, ValueError):
        return float(default)


def _num_field(raw, default: float, degradations: list, field: str,
               room: str | None = None) -> float:
    """_num + a visible _degradations entry when a value WAS supplied but is
    unusable. Pass `_MISSING` when the key is absent (no degradation then)."""
    if raw is _MISSING:
        return float(default)
    try:
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            raise ValueError("empty")
        return float(raw)
    except (TypeError, ValueError):
        entry = {"field": field, "reason": "not_numeric",
                 "value": ("" if raw is None else str(raw))[:40],
                 "fallback": default}
        if room is not None:
            entry["room"] = room
        degradations.append(entry)
        return float(default)


def _non_negative(value: float, default: float, degradations: list, field: str,
                  room: str | None = None) -> float:
    """A quantity may not be negative. `_num_field` parses "-40" happily, and a
    negative dažomas plotas propagated straight into the paint split, the
    materials and the totals — a sąmata that SUBTRACTS work. Clamp and say so."""
    if value >= 0:
        return value
    entry = {"field": field, "reason": "negative_value",
             "value": str(value)[:40], "fallback": default}
    if room is not None:
        entry["room"] = room
    degradations.append(entry)
    return float(default)


def _calc_input(room: dict) -> dict:
    """Room dict prepared for ``calc_room_quantities`` — the SAME contract the
    extraction pipeline uses (``vision_call._recompute_per_room_via_python``)
    and the per-room recalc uses (``api.room_recalc._recalc_room``).

    `elementai` is the PRIMITIVE. `n_doors` / `n_windows` / `door_area_m2` /
    `window_area_m2` are DERIVED from it and are NOT stored on the room — the
    calculator's return value doesn't carry the counts and PRIMITIVE_KEYS never
    persisted them. So they have to be re-derived on every call.

    THE BUG this exists to prevent (2026-07-29, live project 87eb1197): this
    module called ``calc_room_quantities(room, …)`` with the raw room, so
    ``room.get("n_doors")`` was always absent and the calculator fell back to
    its ``1 door / 1 window`` default. A Prielaidos ceiling-height edit
    therefore rewrote the room's geometry as if every room had exactly one door
    and one window — the same phantom-opening defect the 2026-06-01 audit fixed
    inside the calculator, re-entering through a side door. Consequences on the
    first edit of a room with 2 doors + 1 window:
      · walls_paintable_m2 GREW by 1.125 m² (a door's worth of un-deducted wall)
      · kampu_metrai SHRANK by 5.0 m (a door's worth of reveal contour), so
        RAISING a ceiling LOWERED the corner metres
    and both losses were permanent: the counts are recomputed from scratch each
    time, so once a room had been touched every later edit repeated the same
    wrong default and the numbers never came back. Not a rounding drift — a
    whole missing opening.
    """
    from extractor.vision_call import _elementai_to_counts
    return {**room, **_elementai_to_counts(room.get("elementai") or [])}


def _walls_paint_choice(per_room_paint, nr: str) -> float | None:
    """His per-room „Dažomos / Nedažomos" (`walls_paint_override`: Prielaidos, the check sheet, the
    questions) — 1.0, 0.0, or None when he chose nothing for this room. A value that is no number raises
    ValueError; the callers degrade the room and say so."""
    if not isinstance(per_room_paint, dict) or nr not in per_room_paint:
        return None
    return 1.0 if float(per_room_paint[nr]) >= 0.5 else 0.0


def _with_paint_choice(calc_in: dict, rt: dict, wp: float) -> dict:
    """The calculator input with his paint choice applied (`rt` is the room's rules, set in place for
    „Dažomos" only).
    „Nedažomos" travels as the per-room factor override, the one input EVERY wall branch honours first:
    `walls_paint` alone was overruled by a finishes read, the bathroom paint-above-tile default and the
    elevation read (audit calc-engine-3, 2026-09-29) — and the room now says why it has no paint
    (`_walls_unpainted_reason = "override"`). The room's rule is left as it was: the unfinished-ceiling
    gate (universal_rules.calc_room_quantities) reads it as the room-type standard, so a raw garage keeps
    its bare ceiling when he confirms its walls are not painted, and a living room under a read concrete
    slab keeps its painted ceiling when he says its walls are not (2026-10-06).
    „Dažomos" sets the rule to painted: every branch without a stronger read paints the walls, and the
    room counts as finished — its ceiling with it."""
    if wp <= 0:
        return {**calc_in, "walls_paint_factor_override": 0.0}
    rt["walls_paint"] = wp
    return calc_in


# What a room keeps when the calculator's result is merged into it — ONE list for both paths:
# main.recompute_interior builds its `preserved` from it too. (`calculation_trace` is redone by
# derive_room_extras right after the merge on both paths; holding it back changes nothing.)
_KEPT_ON_RECALC = ("nr", "pavadinimas", "paskirtis", "puslapio_nr", "bbox_pct", "plotas_saltinis",
                   "lubu_aukstis_saltinis", "lubu_tipas", "calculation_trace", "confidence", "elementai",
                   "_zoom", "_zoom_changes")


def _apply_recalc(room: dict, recalc: dict, rules_override: dict | None) -> None:
    """The per-room tail /recompute-interior runs after the calculator (main.recompute_interior): every
    key the calculator returns replaces the room's, then the materials and the rest (`derive_room_extras`:
    putty, paint, primer, hidroizoliacija, karnizas, LED, trace). The hand-picked subset this path copied
    before left the plasterboard ceiling in the wrong height tier and the putty and primer stale after a
    height edit, so the two endpoints disagreed on the same edit (audit calc-engine-2, 2026-09-29)."""
    from extractor.vision_call import _elementai_to_counts, derive_room_extras
    # The calculator echoes the room's identity back NORMALISED (`paskirtis` „svetaine" → „gyvenamoji")
    # — the room keeps its own, exactly the fields main.recompute_interior's `preserved` holds back.
    kept = {k: room[k] for k in _KEPT_ON_RECALC if k in room}
    room.update(recalc)
    room.update(kept)
    derive_room_extras(room, _elementai_to_counts(room.get("elementai") or []), rules_override)


def _degrade(degradations: list, room: str | None, field: str, reason: str,
             **extra) -> None:
    """Append one machine-readable degradation entry. Silent drops/excepts in the
    recompute used to return HTTP 200 with quietly-wrong numbers (audit 2/3/4)."""
    entry = {"field": field, "reason": reason}
    if room is not None:
        entry["room"] = room
    entry.update(extra)
    degradations.append(entry)


def _apply_assumption_edits(rooms: list[dict], assumptions: dict,
                            degradations: list | None = None) -> list[dict]:
    """Sprint 0: paint formula recompute from class.
    2026-05-06: per-room aukštis (lubu_auksciai dict) triggers full
    walls_paintable_m2 + ceiling_paintable_m2 recompute via calc_room_quantities.
    2026-07-27: every rejected override / swallowed exception appends to
    `degradations` so a silently-ignored input is visible in the response.
    """
    if degradations is None:
        degradations = []
    # 2026-09-02: resolved exactly the way the extraction pipeline resolves it
    # (`_paint_class` or `paint_class`, LT default 2 — not 1). The two paths
    # have to land on the same profile or they compute different paint litres
    # for an unchanged project; see the `dazai_l` block below.
    from extractor.vision_call import _PAINT_CLASS_DEFAULT
    if assumptions.get("_paint_class") is not None:
        _pc_raw = assumptions["_paint_class"]
    elif "paint_class" in assumptions:
        # SUPPLIED — even as None. Kept distinct from absent so an unusable
        # value still lands in `degradations` instead of vanishing (audit 3).
        _pc_raw = assumptions["paint_class"]
    else:
        _pc_raw = _MISSING
    paint_class = int(_num_field(
        _pc_raw, _PAINT_CLASS_DEFAULT, degradations, "paint_class"))
    # Coverage is now only the WEIGHTING between walls and ceiling inside the
    # canonical total — the absorption factor lives in the class profile
    # `_calc_dazai_liters` applies, so `first_coat_factor` is no longer read here.
    cov_walls, cov_ceil = paint_coverage_for_class(paint_class)
    per_room_h = assumptions.get("lubu_auksciai") or {}
    per_room_paint = assumptions.get("walls_paint_override") or {}
    # The Prielaidos that change the per-room GEOMETRY (wall thickness → the
    # doors' painted jambs; the deduction standard) reach the calc as rules —
    # the same translation /recompute-interior applies (2026-09-15: the wall
    # thickness edit used to move a reveal field no row reads, and nothing else).
    try:
        from extractor.universal_rules import translate_user_prefs_to_room_rules
        rules_all = translate_user_prefs_to_room_rules(assumptions) or None
    except Exception as exc:  # noqa: BLE001 — degrade, never 500
        rules_all = None
        _degrade(degradations, "*", "rules", "translate_failed", error=str(exc)[:120])
    thickness_edited = assumptions.get("sienos_storis_m") not in (None, "", _MISSING)
    _GEOMETRY_KEYS = ("walls_gross_m2", "walls_paintable_m2",
                      "ceiling_paintable_m2", "dazymo_plotas_m2",
                      "kampai_m", "kampu_metrai", *_KAMPAI_TERMS,
                      "lubu_karnizo_m", "glaistas_kg", "gruntas_l", "doors_deducted_m2")
    default_h = _num_field(
        assumptions.get("lubu_aukstis") or _MISSING, 2.82,
        degradations, "lubu_aukstis")  # noqa: F841 — kept for call-site parity

    out = []
    for r in rooms:
        room = {**r}
        # If user overrode this room's ceiling, swap it in BEFORE the calc.
        nr = str(r.get("nr") or "")
        if isinstance(per_room_h, dict) and nr in per_room_h:
            raw_h = per_room_h[nr]
            try:
                new_h = float(raw_h)
            except (TypeError, ValueError):
                # Was silently dropped with HTTP 200 before 2026-07-27 (audit 2).
                new_h = None
                _degrade(degradations, nr, "lubu_aukstis", "not_numeric",
                         value=str(raw_h)[:40])
            if new_h is not None and not (1.5 <= new_h <= 8.0):
                _degrade(degradations, nr, "lubu_aukstis", "out_of_range",
                         value=new_h, allowed="1.5–8.0 m")
                new_h = None
            if new_h is not None:
                room["lubu_aukstis_m"] = round(new_h, 2)
                room["lubu_aukstis_saltinis"] = "user_override"
                # Recompute geometry-derived fields with the new height.
                try:
                    from extractor.universal_rules import calc_room_quantities
                    recalc = calc_room_quantities(
                        _calc_input(room), ceiling_height_m=new_h, rules=rules_all)
                    # The same per-room tail as /recompute-interior — every
                    # computed field (the ceiling's height tier included), the
                    # materials, and the trace for the new H (Playwright
                    # regression 2026-05-10).
                    _apply_recalc(room, recalc, assumptions)
                except Exception as exc:  # noqa: BLE001 — degrade, never 500
                    _degrade(degradations, nr, "lubu_aukstis",
                             "recompute_failed", stage="calc_room_quantities",
                             error=str(exc)[:120])
        elif thickness_edited and rules_all:
            # No height override on this room, but the wall thickness changed:
            # its doors' net deduction moves with it, so the walls do too.
            try:
                from extractor.universal_rules import calc_room_quantities
                own_h = _num(room.get("lubu_aukstis_m"), 0) or 2.82
                recalc = calc_room_quantities(
                    _calc_input(room), ceiling_height_m=own_h, rules=rules_all)
                for k in _GEOMETRY_KEYS:
                    if k in recalc:
                        room[k] = recalc[k]
            except Exception as exc:  # noqa: BLE001 — degrade, never 500
                _degrade(degradations, nr, "sienos_storis_m",
                         "recompute_failed", stage="calc_room_quantities",
                         error=str(exc)[:120])
        # Per-room finishing override (2026-07-05): flip walls_paint (raw↔painted)
        # and recompute the paint geometry. Runs AFTER the height block so a room
        # with BOTH overrides gets the combined result (calc reads the already-set
        # lubu_aukstis_m). The same per-room tail as the height path (`_apply_recalc`).
        if isinstance(per_room_paint, dict) and nr in per_room_paint:
            try:
                wp = _walls_paint_choice(per_room_paint, nr)
                from extractor.universal_rules import (
                    calc_room_quantities, ROOM_TYPE_RULES, normalize_paskirtis,
                )
                pask = normalize_paskirtis(room.get("paskirtis") or "")
                rt = dict((rules_all or {}).get(pask) or ROOM_TYPE_RULES.get(pask)
                          or ROOM_TYPE_RULES["gyvenamoji"])
                room["_walls_paint_override"] = wp
                recalc = calc_room_quantities(_with_paint_choice(_calc_input(room), rt, wp),
                                              rules={pask: rt})
                _apply_recalc(room, recalc, assumptions)
            except Exception as exc:  # noqa: BLE001 — degrade, never 500
                _degrade(degradations, nr, "walls_paint_override",
                         "recompute_failed", stage="walls_paint_override",
                         error=str(exc)[:120])
        walls = _non_negative(_num_field(
            room.get("dazomas_plotas_m2") or room.get("walls_paintable_m2") or _MISSING,
            0.0, degradations, "dazomas_plotas_m2", room=nr),
            0.0, degradations, "dazomas_plotas_m2", room=nr)
        ceiling = _non_negative(_num_field(
            room.get("lubu_dazomas_plotas_m2") or room.get("ceiling_paintable_m2") or _MISSING,
            0.0, degradations, "lubu_dazomas_plotas_m2", room=nr),
            0.0, degradations, "lubu_dazomas_plotas_m2", room=nr)
        # 2026-09-02: the room's TOTAL paint litres come from the canonical
        # `_calc_dazai_liters` — the same function the extraction pipeline uses
        # (vision_call §4.2). This endpoint used to run its own formula off a
        # different constant set (paint_coverage + first_coat_factor vs the
        # class profiles), so an unchanged project came back with different
        # litres after any Prielaidos edit — measured on the Objektas A fixture,
        # 83.83 l of wall paint became 67.59 l on a NO-OP ceiling edit.
        #
        # That was invisible while the litres only ever fed `medziagos_kiekis`;
        # since materials became their own priceable section it would have been
        # a sąmata that moves when the user changes nothing.
        #
        # `dazai_luboms_l` stays — sanity_checks sums both fields and
        # RulesOverridePanel shows the per-surface split — but it is now a
        # DECOMPOSITION of the canonical total, weighted by each surface's
        # coverage, so `dazai_l + dazai_luboms_l` equals the one figure the
        # extraction pipeline writes.
        from extractor.vision_call import _calc_dazai_liters
        total_l = _calc_dazai_liters(walls + ceiling, paint_class=paint_class)
        # A zero coverage rate would be a ZeroDivisionError here — a 500 on a
        # live recompute. It cannot come from `paint_coverage_for_class` today,
        # but the split must not be the thing that discovers otherwise: with no
        # usable rate, divide the litres by AREA instead of by coverage, which
        # is the same answer whenever the two surfaces share a rate.
        w_raw = (walls / cov_walls) if (walls and cov_walls) else (walls or 0.0)
        c_raw = (ceiling / cov_ceil) if (ceiling and cov_ceil) else (ceiling or 0.0)
        denom = w_raw + c_raw
        walls_l = round(total_l * w_raw / denom, 2) if denom else 0.0
        room["dazai_l"] = walls_l
        room["dazai_luboms_l"] = round(total_l - walls_l, 2) if denom else 0.0

        # Recompute glaistas_kg from glaistimo_lygis (Q1-Q4) if assumption set.
        # Playwright regression 2026-05-10: the Q-toggle in Prielaidos was
        # saving glaistimo_lygis but never recomputing the putty kg, so the
        # UI buttons looked dead. CLAUDE.md §1.11 owns the canonical
        # consumption table; vision_call._calc_glaistas_kg implements it.
        # Either key name (the wizard's `glaistas_q_lygis` too), 2026-09-29.
        from extractor.vision_call import putty_q_level
        q_level = putty_q_level(assumptions, default=None)
        if q_level:
            try:
                from extractor.vision_call import _calc_glaistas_kg
                dazymo = _num(room.get("dazymo_plotas_m2"), 0)
                if dazymo > 0:
                    room["glaistas_kg"] = _calc_glaistas_kg(dazymo, str(q_level))
            except Exception as exc:  # noqa: BLE001
                # Recompute is best-effort — leave the prior value rather than
                # raise during a UI-driven assumption tweak, but SAY SO (audit 4).
                _degrade(degradations, nr, "glaistimo_lygis", "recompute_failed",
                         stage="glaistas_kg", error=str(exc)[:120])

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
            wall_thickness = _num_field(
                assumptions.get("sienos_storis_m") or _MISSING, 0.10,
                degradations, "sienos_storis_m")
            window_sides = int(_num_field(
                assumptions.get("window_sides") or _MISSING, 3,
                degradations, "window_sides"))
            openings = room.get("elementai") or []
            room["angokrasciai_lm"] = opening_reveal_lm(openings, window_sides=window_sides)
            room["angokrasciai_m2"] = opening_reveal_area_m2(
                openings, wall_thickness_m=wall_thickness, window_sides=window_sides,
            )
            _frameless = bool(room.get("_beapvadines_vidaus"))
            # his „su apvadais" (universal_rules.FRAMELESS_CHOSEN_KEY) covers the plan's hidden-door symbols too
            _chosen_framed = bool(room.get("_beapvadines_jusu")) and not _frameless
            room["pasleptu_duru_kompl"] = hidden_door_count(openings, frameless_default=_frameless, chosen_framed=_chosen_framed)
            room["pasleptu_duru_staktu_m"] = hidden_door_frame_lm(openings, frameless_default=_frameless, chosen_framed=_chosen_framed)
        except Exception as exc:  # noqa: BLE001
            # Don't block the recompute on a helper hiccup — but record it.
            _degrade(degradations, nr, "angokrasciai", "recompute_failed",
                     stage="line_items", error=str(exc)[:120])

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
    except Exception as exc:  # noqa: BLE001
        _degrade(degradations, None, "hidroizoliacija", "recompute_failed",
                 stage="hidroizoliacija_m2", error=str(exc)[:120])

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


# The tier vocabulary lives in `extractor/position_id` — the stable-id hash and
# this price index MUST strip the same suffixes or a re-tiered line gets a new
# id AND a new price key at once. One definition, imported, never re-typed.
from extractor.position_id import _TIER_SUFFIX_RE, tier_key as _tier_key  # noqa: E402


# The canonical builder folds 'LED nišų glaistymas' + 'LED nišų dažymas' into one
# 'LED nišų glaistymas/dažymas' line (vision_call._consolidate_led_niche_pozicijos).
# A project priced BEFORE that consolidation carries the two separate lines, so map
# both onto the consolidated key or the rebuild loses their prices (2026-07-27 audit).
_LED_PAIR_RE = re.compile(r"^led\s+niš[ųu]\s+(glaistymas|dažymas)$", re.IGNORECASE)
_LED_CONSOLIDATED = "led nišų glaistymas/dažymas"


# 2026-07-29 sanitary pair split: a CONCEALED mixer is two jobs (in-wall body
# before tiling, visible trim after), and the canonical builder now emits the
# LT-conventional pair instead of one bundled line. A project priced BEFORE the
# split carries the old single label, which pass 1 can no longer match — without
# this map pass 3 would carry it as an orphan and the user would see the SAME
# work twice: once as the legacy bundled line, once as the new pair. Maps the
# legacy label onto the ROUGH-IN half (the half that inherits the original
# work's price — it is the larger job and the one that happens first).
#
# NOTE the map is only consulted when the successor is actually in the rebuilt
# list. With `santechnika_potinkinis` overridden to false the builder re-emits
# the legacy label verbatim, pass 1 matches it exactly, and none of this fires.
_SAN_LEGACY_SPLIT = {
    "praustuvės maišytuvo montavimas":
        "potinkinio praustuvės maišytuvo potinkinės dalies montavimas",
    "dušo maišytuvo sistemos montavimas":
        "potinkinio dušo maišytuvo potinkinės dalies montavimas",
}

# 2026-07-29 line-coverage pass: same mechanism, plain RENAMES (one work item,
# one successor — no split). A relabeled line must be listed here or the
# rebuild shows the user the SAME work twice: once under the label they priced,
# once under the new one. Keys and values are lowercase `_tier_key` form.
_LEGACY_LABEL_RENAMES = {
    "dėžučių iš gkp formavimas wc mechanizmams paslėpti":
        "pertvaros sutvirtinimas wc mechanizmams montuoti (gkp dėžutė)",
}

# Every legacy label the canonical builder no longer emits → its successor.
_LEGACY_LABEL_MAP = {**_SAN_LEGACY_SPLIT, **_LEGACY_LABEL_RENAMES}

# 2026-09-02 sienų/lubų split: the combined "Sienų, lubų glaistymas/dažymas …"
# line became two, one per surface. Mapped at the EXACT label (tier suffix and
# all) rather than through `_norm_label`, because the tier-stripped key matches
# BOTH new tier lines — ambiguous, so pass 2 would refuse and pass 3 would carry
# the priced old row alongside the four new ones, showing the same work twice.
#
# The money goes to the WALLS half, on the same principle as the sanitary split:
# it is the larger area and the one the combined €/m² was mostly buying. The
# ceiling half comes back unpriced, which is visible and correct — the
# contractor now prices the two trades separately, which is why he asked for
# the split.
_PAINT_SPLIT_EXACT_RENAMES = {
    "sienų, lubų glaistymas/dažymas": "sienų glaistymas/dažymas",
    "sienų, lubų glaistymas/dažymas (iki 3m aukščio)":
        "sienų glaistymas/dažymas (iki 3m aukščio)",
    "sienų, lubų glaistymas/dažymas (virš 3m aukščio)":
        "sienų glaistymas/dažymas (virš 3m aukščio)",
    "sienų, lubų šlifavimas q4 (80–120 grit, 100% paviršius)":
        "sienų šlifavimas q4 (80–120 grit, 100% paviršius)",
}


# `_tier_key` (imported above) — label with ONLY the height/Q-level tier
# suffixes stripped. Two labels sharing a tier key describe the same work at
# different ceiling tiers ('… (iki 3m aukščio)' vs '… (virš 3m aukščio)' vs
# '… (standartinis aukštis)'). Used by the orphan pass to tell a legitimately
# RE-TIERED line (the work is still in the list, under the sibling label) from a
# line the rebuild simply cannot produce (corner beads, whole electrical
# sections). Deliberately does NOT fold the LED pair — 'LED nišų dažymas' is a
# distinct work item from the consolidated line, so it must still be carried.


# The paint split at the TIER-STRIPPED level. `_PAINT_SPLIT_EXACT_RENAMES` above
# only fires on the full label, which is what pass 1 needs; pass 2 works on
# `_norm_label` keys, and without the rename there a legacy priced
# "Sienų, lubų glaistymas/dažymas (virš 3m aukščio)" whose ceiling was lowered
# below 3 m normalized to a key NO rebuilt row carries — measured: the priced row
# came back as an orphan and BOTH new rows came back unpriced. With it, pass 2's
# one-to-one guard reunites it with the walls line, and still refuses (two
# candidates) when both tier lines exist — that case is pass 1's, by exact label.
_PAINT_SPLIT_TIER_RENAMES = {
    "sienų, lubų glaistymas/dažymas": "sienų glaistymas/dažymas",
    "sienų, lubų šlifavimas": "sienų šlifavimas",
}


def _norm_label(s: str | None) -> str:
    """Height/Q-level-independent label key: strip the tier suffixes whose text
    flips when a ceiling crosses 3 m or the glaistymo lygis changes, so a priced
    line can be matched to its post-rebuild sibling. Also collapses the LED
    glaistymas/dažymas pair onto its consolidated label, and renames the
    pre-split combined paint labels onto their walls successor."""
    base = _tier_key(s)
    if _LED_PAIR_RE.match(base):
        return _LED_CONSOLIDATED
    base = _PAINT_SPLIT_TIER_RENAMES.get(base, base)
    return _LEGACY_LABEL_MAP.get(base, base)


def _has_user_edit(p: dict) -> bool:
    return (p.get("kaina") not in (None, 0)
            or p.get("manual_override") is True
            or p.get("quantity_source") == "manual_override"
            or bool(p.get("override_locked")))


def _has_user_edit_beyond_kainynas(p: dict) -> bool:
    """`_has_user_edit`, except that a price the KAINYNAS filled in is not the
    user's hand.

    THE OVER-BILLING (2026-09-02): pass 3 keeps a superseded tier line whenever
    the row carries a user edit, and `_has_user_edit` reads ANY non-zero kaina as
    one. That was harmless while rows arrived unpriced — the fold worked. Since
    the automatic fill prices every row at extraction, EVERY row looked edited:
    lowering a ceiling left the old "(virš 3m aukščio)" line carried as a priced
    orphan next to its own re-tiered successor, and the client was billed 240 m²
    of the 200 m² he has. An AI-matched price must not veto a fold; a hand-typed
    one still does, and so does a corrected quantity or a gesture lock."""
    if p.get("kaina_source") == "kainynas":
        return (p.get("manual_override") is True
                or p.get("quantity_source") == "manual_override"
                or bool(p.get("override_locked")))
    return _has_user_edit(p)


_TRAILING_PAREN_RE = re.compile(r"\s*\([^()]*\)\s*$")


def _price_key_for_id(pid) -> str:
    """Namespace an `id` so it can never collide with a label key."""
    return f"\x1fid\x1f{str(pid).strip()}"


def _price_index(darbu_sarasas: list[dict]) -> dict[str, dict]:
    """id/label-key → priced/edited darbu_sarasas row.

    Indexed FOUR ways. The stable `id` (2026-09-02) is the only one that is not
    a guess about wording — it survives a rename, a re-section and a Q-level
    relabel — so `_hydrate_prices_from_darbu_sarasas` tries it first and falls
    back to the three label keys for every project saved before ids existed:
    exact lowercased label, the height-independent `_norm_label`, and the label
    with a trailing parenthetical removed (`_emit_v8_compat_fields` appends
    `(pastaba)` to the darbu_sarasas label, e.g. tile size, so its text is
    LONGER than the pozicija's)."""
    idx: dict[str, dict] = {}
    for row in darbu_sarasas or []:
        if not isinstance(row, dict) or not _has_user_edit(row):
            continue
        lab = (row.get("aprasymas") or row.get("pavadinimas") or "").strip()
        pid = str(row.get("id") or "").strip()
        if not lab and not pid:
            continue
        keys = [_price_key_for_id(pid)] if pid else []
        if lab:
            keys += [lab.lower(), _norm_label(lab),
                     _TRAILING_PAREN_RE.sub("", lab).strip().lower()]
        for key in keys:
            if key:
                idx.setdefault(key, row)
    return idx


def _hydrate_prices_from_darbu_sarasas(prior: list[dict],
                                       darbu_sarasas: list[dict]) -> int:
    """Copy the user's kaina onto prior `pozicijos` that don't carry one.

    THE P0 (2026-07-28): `_has_user_edit` keyed on `pozicijos[].kaina`, but in
    every real project blob prices live ONLY in `darbu_sarasas` — so the merge
    saw zero user edits and the rescue passes never fired. Mutates `prior` in
    place and returns how many positions gained a price."""
    if not darbu_sarasas:
        return 0
    idx = _price_index(darbu_sarasas)
    if not idx:
        return 0
    n = 0
    for p in prior:
        if not isinstance(p, dict) or _has_user_edit(p):
            continue
        lab = (p.get("aprasymas") or "").strip()
        pid = str(p.get("id") or "").strip()
        if not lab and not pid:
            continue
        # The id first: it is the one key that does not depend on the two lists
        # agreeing about wording.
        row = idx.get(_price_key_for_id(pid)) if pid else None
        if row is None and lab:
            row = (idx.get(lab.lower()) or idx.get(_norm_label(lab))
                   or idx.get(_TRAILING_PAREN_RE.sub("", lab).strip().lower()))
        if row is None:
            continue
        kaina = row.get("kaina")
        if kaina not in (None, 0):
            p["kaina"] = kaina
            for key in (*_PRICE_PROVENANCE_KEYS, *_ROW_CHOICE_KEYS):
                if row.get(key) is not None:
                    p[key] = row[key]
            kiekis = p.get("kiekis")
            if isinstance(kiekis, (int, float)):
                p["suma"] = round(float(kiekis) * float(kaina), 2)
            n += 1
        if row.get("manual_override") is True:
            p["manual_override"] = True
            p.setdefault("quantity_source", "manual_override")
            if row.get("kiekis") is not None:
                p["kiekis"] = row["kiekis"]
            if row.get("ai_kiekis_original") is not None:
                p["ai_kiekis_original"] = row["ai_kiekis_original"]
    return n


# Where a price CAME FROM. Travels with `kaina` everywhere the money travels —
# the carry, the compat emit and the darbu_sarasas hydration — because the UI's
# "hand-typed prices are left alone" guarantee is enforced on `kaina_source`
# alone, and a rebuild that drops it silently unprotects the price.
_PRICE_PROVENANCE_KEYS = ("kaina_source", "kaina_match_score",
                          # the darbo + medžiagų split (togal-v2 W9): it describes
                          # THIS price, so it travels exactly where the price does
                          "kaina_darbo", "kaina_medziagu", "medziagos_kainoje")
# His choices on a row that are not money: the cost code he typed and the
# rinkinys he bound it to. Carried with the row whatever happens to its price.
# Mirror of mergeDarbuSarasas.js `ROW_CHOICE_KEYS`.
_ROW_CHOICE_KEYS = ("kodas", "rinkinys_id")


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
        # …WITH its provenance. `kaina_source` was in neither carry set, so a
        # hand-typed price came back from the first recompute unlabelled and the
        # next "Taikyti kainyną" overwrote it — the exact opposite of what the
        # button's own footnote promises. It also tells pass 3 whether a price
        # is the user's hand or the kainynas's guess.
        for key in _PRICE_PROVENANCE_KEYS:
            if prev.get(key) is not None:
                p[key] = prev[key]
    for key in _ROW_CHOICE_KEYS:
        if prev.get(key) is not None:
            p[key] = prev[key]
    # 3. Verification („Teisinga ✓" / review status). It certified a NUMBER, so
    #    it survives only when that number survived the rebuild (or the row is a
    #    manual override, whose number the user owns). A row whose quantity
    #    moved goes back to the queue — the ripple shows it — instead of
    #    carrying a checkmark for a value nobody looked at. Before 2026-09-04
    #    nothing carried these keys at all: one Prielaidos click erased every
    #    checkmark on the project (measured: 72 → 7 accepts → 71).
    _carry_verification(prev, p)


_VERIFICATION_KEYS = ("user_verified_at", "_review_status", "_review_status_at")


def _same_quantity(a, b) -> bool:
    try:
        return abs(float(a) - float(b)) <= 0.01
    except (TypeError, ValueError):
        return a == b


def _carry_verification(prev: dict, p: dict) -> None:
    if not any(prev.get(k) is not None for k in _VERIFICATION_KEYS):
        return
    owned = p.get("manual_override") is True or p.get("override_locked") is True
    if owned or _same_quantity(prev.get("kiekis"), p.get("kiekis")):
        for k in _VERIFICATION_KEYS:
            if prev.get(k) is not None:
                p[k] = prev[k]


# Literal copy of `extractor.vision_call.SK_MEDZIAGOS`, copied rather than
# imported to keep this module free of the heavy extractor import at load time
# (the same choice eval_harness.py made). Kept in step by
# test_medziagos_section.
_MEDZIAGOS_SKYRIUS = "Medžiagos"


def _materials_last(rows: list[dict]) -> list[dict]:
    """Stable-partition the shopping list to the foot of the sąmata.

    `SKYRIUS_ORDER[Medžiagos] = 11` is decorative: the builder appends the
    section AFTER its sort, and pass 3 below appends carried orphans after
    everything. So a priced orphan of a section that no longer exists sat BELOW
    the shopping list, which is supposed to be the last thing the contractor
    reads. Stable, so nothing else moves."""
    work, mats = [], []
    for r in rows:
        (mats if (r.get("skyrius") or "") == _MEDZIAGOS_SKYRIUS else work).append(r)
    return work + mats if mats else rows


def _reassign_duplicate_ids(rows: list[dict]) -> int:
    """Re-establish `id` uniqueness on the MERGE OUTPUT. Returns how many moved.

    `assign_position_ids` runs inside the builder, so it only ever sees the
    rebuilt list. Pass 3 then appends carried orphans keeping the ids they were
    saved with, and an orphan can legitimately carry a live row's id — a priced
    legacy label whose id folds onto its successor through `LEGACY_LABEL_KEYS`,
    for instance. Two rows with one id are indistinguishable to the price index,
    to the next merge's pass 0 and to a React key, so the duplicate is renamed
    here rather than shipped.

    THE RULE (mirror this exactly in `frontend/src/lib/mergeDarbuSarasas.js`):

      · rows are claimed in TWO passes — first every row that is NOT flagged
        `_orphaned_after_rebuild`, in list order, then every carried orphan, in
        list order. So the rebuilt canonical row always keeps the clean id and
        the orphan is the one that takes a suffix;
      · a row with no id is skipped (legacy blobs stay untouched);
      · claiming `base`: take it if free, else the first free `f"{base}-{n}"`
        counting up from n = 2. The counting-up (rather than "position among
        duplicates") is what keeps it collision-free when an orphan already
        carries a `-2` id from an earlier build.

    Same `-N` shape as `extractor/position_id.assign_position_ids`, so an id
    minted here and one minted there are indistinguishable downstream.
    """
    used: set[str] = set()
    moved = 0

    def _claim(base: str) -> str:
        if base not in used:
            used.add(base)
            return base
        n = 2
        while f"{base}-{n}" in used:
            n += 1
        used.add(f"{base}-{n}")
        return f"{base}-{n}"

    for orphans in (False, True):
        for row in rows:
            if not isinstance(row, dict):
                continue
            if bool(row.get("_orphaned_after_rebuild")) is not orphans:
                continue
            base = str(row.get("id") or "").strip()
            if not base:
                continue
            claimed = _claim(base)
            if claimed != base:
                row["id"] = claimed
                moved += 1
    return moved


def _merge_user_edits(rebuilt: list[dict], prior: list[dict],
                      notes: list | None = None) -> list[dict]:
    """After a canonical pozicijos rebuild (ceiling/assumption edit), carry the
    user's manual edits forward from the prior pozicijos so the rebuild doesn't
    silently revert them.

    Four-pass match:
      0. STABLE ID (2026-09-02) — both sides carry `id` only when both were built
         by the current builder (`extractor/position_id`), so this pass is a
         no-op on every project saved before ids existed and the label passes
         below stay the fallback forever. The id already folds the renames the
         label maps below spell out (the sienų/lubų split, the sanitary split,
         the Q-level suffix), so it agrees with them rather than racing them.
      1. EXACT aprasymas — handles the common case and the simultaneously-present
         iki/virš tier pair in mixed-height projects (no collision).
      2. HEIGHT-INDEPENDENT fallback for any prior edited line left unmatched
         (its label flipped across the 3 m / Q-level boundary, e.g. a priced
         '… (virš 3m aukščio)' line that became '… (iki 3m aukščio)'; or the
         LED pair that got consolidated). Applied only when the target is
         unambiguous — exactly ONE unmatched rebuilt line carries the normalized
         key — so it can never mis-assign a price between the two co-existing
         tier lines. N prior → 1 rebuilt: the first prior wins the line, the
         rest fall through to pass 3.
      3. ORPHAN CARRY (2026-07-27 audit fix 1, widened 2026-07-28): EVERY prior
         line that matched nothing is APPENDED to the rebuilt list, flagged
         `_orphaned_after_rebuild` — not just the ones carrying a visible user
         edit. The 2026-07-27 version gated this on `_has_user_edit`, which
         reads `pozicijos[].kaina`; real blobs keep prices in `darbu_sarasas`,
         so the net never fired in production and a ceiling-height round-trip
         deleted 12-15 rows (whole 'Elektros instaliacijos' / 'Ventiliacijos'
         sections, both 'Glaistymo kampai' lines) with HTTP 200 and an empty
         `_degradations`. The ONLY prior line still dropped is an un-edited one
         whose work is demonstrably still in the list under a sibling TIER label
         (`_tier_key` hit) — that is the rebuild legitimately re-tiering a line
         (… (virš 3m) → … (iki 3m)), not a deletion. A line carrying real user
         money/edits is carried even then, because guessing that its price is
         obsolete is not ours to make silently.

    Preserved: kaina/suma (prices), manual count overrides, gesture locks.
    Formula/geometry quantities are otherwise recomputed (the point of the rebuild).

    `notes` (optional, out-param): appended with one dict per carried orphan /
    suppressed line so the endpoint can DISCLOSE what wasn't recomputed.

    Finally `_reassign_duplicate_ids` re-establishes `id` uniqueness over the
    OUTPUT: pass 3 appends orphans carrying the ids they were saved with, and
    `assign_position_ids` only ever saw the rebuilt list.
    """
    if notes is None:
        notes = []
    if not prior:
        return _materials_last(rebuilt)
    prior_by_label: dict[str, dict] = {}
    for p in prior:
        lab = (p.get("aprasymas") or "").strip().lower()
        if lab:
            prior_by_label.setdefault(lab, p)
    # Aliases in a SECOND pass. Registering them in the loop above let a legacy
    # row that happens to come FIRST in the list shadow a row already carrying
    # the post-split label: the walls line then inherited the legacy 9 €/m² and
    # the user's real 12 €/m² row was carried back as an orphan. A row's own
    # label always wins; a rename only fills a key nobody claimed.
    for p in prior:
        lab = (p.get("aprasymas") or "").strip().lower()
        renamed = _PAINT_SPLIT_EXACT_RENAMES.get(lab)
        if renamed:
            prior_by_label.setdefault(renamed, p)

    matched_prior: set[int] = set()
    matched_rebuilt: set[int] = set()

    # Pass 0 — stable id. Only fires when BOTH rows carry one; an old blob has
    # none and drops straight through to the label passes.
    prior_by_id: dict[str, dict] = {}
    for p in prior:
        pid = str(p.get("id") or "").strip()
        if pid:
            prior_by_id.setdefault(pid, p)
    if prior_by_id:
        for p in rebuilt:
            pid = str(p.get("id") or "").strip()
            prev = prior_by_id.get(pid) if pid else None
            if prev is None or id(prev) in matched_prior:
                continue
            _carry_edit(prev, p)
            matched_prior.add(id(prev))
            matched_rebuilt.add(id(p))
            if ((prev.get("aprasymas") or "").strip().lower()
                    != (p.get("aprasymas") or "").strip().lower()):
                # Same row, new wording — say where the money went, exactly as
                # the label passes do, so the browser-side merge folds it too.
                notes.append({"aprasymas": prev.get("aprasymas"),
                              "reason": "relabeled",
                              "into": p.get("aprasymas"),
                              "kaina": p.get("kaina")})

    for p in rebuilt:
        if id(p) in matched_rebuilt:
            continue
        lab = (p.get("aprasymas") or "").strip().lower()
        prev = prior_by_label.get(lab)
        if prev is not None and id(prev) in matched_prior:
            prev = None
        if prev is not None:
            _carry_edit(prev, p)
            matched_prior.add(id(prev))
            matched_rebuilt.add(id(p))
            # Matched under a RENAME (the paint split), not under its own
            # label: the row the user priced is gone from their sąmata, so
            # declare where its money went. InteriorProject forwards exactly
            # these notes to the browser-side merge as `serverRelabeled`, which
            # is what stops it re-carrying the row we just folded.
            if (prev.get("aprasymas") or "").strip().lower() != lab:
                notes.append({"aprasymas": prev.get("aprasymas"),
                              "reason": "relabeled",
                              "into": p.get("aprasymas"),
                              "kaina": p.get("kaina")})

    # Pass 2 — reunite prior lines with their renamed post-rebuild sibling.
    # STILL gated on `_has_user_edit`, and that gate is load-bearing in a way
    # worth spelling out (measured live, 2026-07-28): consuming a prior line in
    # favour of its renamed successor only preserves the money if we can SEE the
    # money to carry it. Un-gated, the LED pair collapses onto the consolidated
    # line and 320 € evaporates whenever the caller didn't forward
    # `darbu_sarasas` — the frontend's own merge can't recover it either,
    # because its JS `_normLabel` doesn't fold the LED pair. So: price visible
    # (natively or hydrated from darbu_sarasas) → clean rename with the price
    # carried; price invisible → fall through to pass 3 and keep the original
    # line. Never trade a row for a rename we can't pay for.
    leftover_prior_by_norm: dict[str, list[dict]] = {}
    for p in prior:
        if id(p) in matched_prior or not _has_user_edit(p):
            continue
        leftover_prior_by_norm.setdefault(_norm_label(p.get("aprasymas")), []).append(p)
    # When several priors collapse onto one line, the one carrying real money
    # wins it.
    for _priors in leftover_prior_by_norm.values():
        _priors.sort(key=lambda p: not _has_user_edit(p))
    if leftover_prior_by_norm:
        leftover_rebuilt_by_norm: dict[str, list[dict]] = {}
        for p in rebuilt:
            if id(p) in matched_rebuilt:
                continue
            leftover_rebuilt_by_norm.setdefault(_norm_label(p.get("aprasymas")), []).append(p)
        for norm, priors in leftover_prior_by_norm.items():
            cands = leftover_rebuilt_by_norm.get(norm, [])
            if len(cands) == 1:  # unambiguous target → safe to carry the first
                _carry_edit(priors[0], cands[0])
                matched_prior.add(id(priors[0]))
                matched_rebuilt.add(id(cands[0]))
                # A rename is not a deletion — but the label the user priced is
                # gone from their sąmata, so say where its money went.
                if ((priors[0].get("aprasymas") or "").strip()
                        != (cands[0].get("aprasymas") or "").strip()):
                    notes.append({"aprasymas": priors[0].get("aprasymas"),
                                  "reason": "relabeled",
                                  "into": cands[0].get("aprasymas"),
                                  "kaina": cands[0].get("kaina")})

    # Pass 3 — carry (don't delete) every still-unmatched prior line. Flagged so
    # the UI/QA can tell a carried line from a rebuilt one. Computed BEFORE the
    # appends below so a carried orphan can never suppress a later one.
    rebuilt_tier_keys = {_tier_key(p.get("aprasymas")) for p in rebuilt}
    rebuilt_tier_keys.discard("")
    rebuilt_labels = {(p.get("aprasymas") or "").strip().lower() for p in rebuilt}
    for p in prior:
        if id(p) in matched_prior:
            continue
        # `edited` decides whether a row survives being superseded; `has_money`
        # is what the user is TOLD about. They differ on exactly one row: a line
        # the kainynas priced, which carries money but is not a reason to keep a
        # duplicate of work that legitimately moved tier.
        edited = _has_user_edit_beyond_kainynas(p)
        has_money = _has_user_edit(p)
        # Legacy sanitary line the split replaced. Emitted as `relabeled` (not
        # `superseded_by_tier`) on purpose: InteriorProject.jsx forwards exactly
        # the `relabeled` notes to the frontend merge as `serverRelabeled`, and
        # that is what stops the browser-side pass 3 from re-carrying the same
        # row the backend just folded away.
        _into = _LEGACY_LABEL_MAP.get((p.get("aprasymas") or "").strip().lower())
        if not edited and _into and _into in rebuilt_labels:
            notes.append({"aprasymas": p.get("aprasymas"),
                          "reason": "relabeled", "into": _into,
                          "kaina": None})
            continue
        if not edited and _tier_key(p.get("aprasymas")) in rebuilt_tier_keys:
            # Un-edited line whose work is still listed under a sibling tier
            # label — the rebuild re-tiered it, nothing was lost.
            notes.append({"aprasymas": p.get("aprasymas"),
                          "reason": "superseded_by_tier"})
            continue
        if str(p.get("id") or "").startswith("rnk-"):
            # Hand-added („rankinė") row: the builder can never reproduce it,
            # so carrying it is the contract, not a degradation. Flagging it
            # „pasenusi eilutė" told the user his 30-second-old row was obsolete
            # (2026-09-04 UX audit).
            kept = {**p}
            kept.pop("_orphaned_after_rebuild", None)
            rebuilt.append(kept)
            notes.append({"aprasymas": p.get("aprasymas"), "reason": "manual_row_kept"})
            continue
        if p.get("_only_while") and not edited:
            # A row the builder emits only under a condition („Pastolių nuoma"
            # while a room is above 3 m) and did not emit now: the condition
            # is gone and so is the row. Carrying it flagged „pasenusi" showed
            # scaffolding in a 2,82 m flat (2026-09-08). Mirrors the browser
            # merge (lib/mergeDarbuSarasas.js).
            notes.append({"aprasymas": p.get("aprasymas"), "reason": "dropped_by_condition",
                          "only_while": p.get("_only_while")})
            continue
        rebuilt.append({**p, "_orphaned_after_rebuild": True})
        notes.append({"aprasymas": p.get("aprasymas"), "reason": "orphan_carried",
                      "kiekis": p.get("kiekis"), "kaina": p.get("kaina"),
                      "user_edit": has_money})
    out = _materials_last(rebuilt)
    _reassign_duplicate_ids(out)
    return out


@router.post("/recompute-quantities")
def recompute(
    req: RecomputeRequest,
    user: dict = Depends(_auth.require_user),  # F4 (2026-07-04): no anon compute
) -> dict:
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

    # 3. Recompute paint per room (Sprint 0 logic). `degradations` collects every
    # rejected override / swallowed failure so the 200 response is honest about
    # what was silently ignored (2026-07-27 audit findings 2/3/4).
    degradations: list = []
    _paruosimas: dict = {}
    rooms = _apply_assumption_edits(list(req.rooms), assumptions, degradations)
    # 2026-09-23: the same project-level pass the extraction runs — doors two rooms list paired, the
    # frameless-door assumption settled (his Prielaidos choice first), cornice evidence
    try:
        from extractor.universal_rules import prepare_rooms_for_calc
        _ctx = req.context if isinstance(req.context, dict) else {}
        _paruosimas = prepare_rooms_for_calc(rooms, overrides={**(_ctx.get("_overrides") or {}), **assumptions},
                                             door_types=_ctx.get("_door_types"), legend=_ctx.get("_symbol_legend"),
                                             schedule=_ctx.get("_duru_ziniarastis"))
    except Exception as exc:  # noqa: BLE001 — degrade, never 500
        _degrade(degradations, None, "paruosimas", "prepare_failed", error=str(exc)[:120])
    # 2026-09-23: the per-opening fields FOLLOW that pass — his answer to „beapvadinės ar su apvadais?"
    # (vidaus_durys_beapvadines) must move the frameless-door row and the reveals, and the height/paint
    # blocks above never touch those fields. Every room's are recomputed from its marked elements.
    try:
        from extractor.universal_rules import calc_room_quantities, translate_user_prefs_to_room_rules
        _rules = translate_user_prefs_to_room_rules(assumptions) or None
        for room in rooms:
            # a legacy payload lists its doors under `openings` (line_items helpers above), not `elementai`;
            # windows count too since the reveals scope (2026-09-25) can switch them off
            if not any(isinstance(e, dict) and ("dur" in str(e.get("tipas") or "") or "lang" in str(e.get("tipas") or "")
                                                 or str(e.get("tipas") or "") in ("door", "hidden_door", "window"))
                       for e in room.get("elementai") or []):
                continue
            own_h = _num(room.get("lubu_aukstis_m"), 0) or 2.82
            recalc = calc_room_quantities(_calc_input(room), ceiling_height_m=own_h, rules=_rules)
            for k in ("pasleptu_duru_staktu_m", "pasleptu_duru_kompl", "_pasleptu_duru_pagal", "angokrasciu_gkp_m"):
                if k in recalc:
                    room[k] = recalc[k]
    except Exception as exc:  # noqa: BLE001 — degrade, never 500
        _degrade(degradations, None, "durys", "recompute_failed", error=str(exc)[:120])

    # 4. Apply gesture edits (Sprint 2)
    rooms, pozicijos = _apply_gesture_edits(rooms, list(req.pozicijos), req.edits)

    # 5. If an ASSUMPTION edit changed room geometry (e.g. ceiling height), the
    # aggregated pozicijos (paint iki/virš split, kampai, GKP virš-3m, karnizas…)
    # must be rebuilt from the recomputed rooms — otherwise the displayed/exported
    # numbers stay stale (the Prielaidos recompute bug, 2026-06-17). Rebuild via
    # the canonical builder, carrying the reader context so door/fixture/symbol
    # lines survive. Gesture-only edits keep the in-place pozicijos above.
    assumption_edited = any(e.field in _ASSUMPTION_FIELDS for e in req.edits)
    merge_notes: list = []
    if assumption_edited and req.context:
        try:
            from extractor.vision_call import _build_pozicijos_from_rooms
            overrides = {**(req.context.get("_overrides") or {}), **assumptions}
            # The Prielaidos field is `glaistimo_lygis`, the wizard's is
            # `glaistas_q_lygis`: the builder reads either (vision_call.putty_q_level),
            # the same way /recompute-interior does, so no bridging here (2026-09-29).
            parsed = {
                **req.context,
                "patalpos": rooms,
                "_overrides": overrides,
                "_paruosimas": _paruosimas,           # the pass's verdicts for the rows (2026-09-23)
            }
            # His answer to „LED nišos be perskaityto ilgio" moves every room's billed metres (2026-10-06):
            # the same per-room function the extraction and /recompute-interior run, and BEFORE the scope
            # marks below, so a room he does not do stays zeroed.
            from extractor.vision_call import refresh_led_metres
            for _r in rooms:
                if isinstance(_r, dict) and isinstance(_r.get("elementai"), list):
                    refresh_led_metres(_r, overrides)
            # Apimtis (2026-09-06): the contractor's „ką skaičiuoti" rides in
            # `_overrides.apimtis`; enforced exactly as in /recompute-interior
            # (extractor/scope.py) so a Prielaidos edit cannot undo it.
            from extractor import scope as _scope
            _apimtis = _scope.normalize_apimtis(overrides.get("apimtis"))
            _scope.mark_rooms(rooms, _apimtis)       # also CLEARS a stale mark when no scope
            if _apimtis:
                _scope.apply_ceiling_choice(rooms, _apimtis)
                parsed["_apimtis"] = _apimtis
            rebuilt = _build_pozicijos_from_rooms(parsed)
            if _apimtis:
                rebuilt["pozicijos"] = _scope.filter_rows_by_families(rebuilt.get("pozicijos"), _apimtis)
            if rebuilt.get("pozicijos"):
                # Carry the user's manual edits (prices, corrected counts,
                # locks) forward so the rebuild doesn't silently revert them.
                prior = [dict(p) for p in req.pozicijos]
                # The prices live in darbu_sarasas — lift them onto the prior
                # positions first, otherwise the merge sees zero user edits.
                _hydrate_prices_from_darbu_sarasas(prior, req.darbu_sarasas)
                pozicijos = _merge_user_edits(
                    rebuilt["pozicijos"], prior, merge_notes)
        except Exception as exc:  # noqa: BLE001 — never break the recompute
            log.warning("canonical pozicijos rebuild failed: %s", exc, exc_info=True)
            # OBJECT, not a bare string (2026-07-28 audit): the only consumer
            # (InteriorProject.jsx) filters _degradations on `d.reason`, so a
            # plain string was invisible — the user was told nothing and kept
            # quoting stale quantities.
            degradations.append({
                "field": "pozicijos",
                "reason": "partial_recompute",
                "message": "Dalis kambarių nebuvo iki galo perskaičiuoti — "
                           "kiekiai gali būti seni.",
            })

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
        log.warning("v8-compat emit failed: %s", exc, exc_info=True)
        degradations.append({
            "field": "darbu_sarasas",
            "reason": "stale_quantities",
            "message": "Nepavyko atnaujinti kiekių lentelės — gali būti rodomi "
                       "seni kiekiai.",
        })

    # `_emit_v8_compat_fields` builds a fresh row per pozicija with a fixed key
    # set — it drops kaina/suma and the orphan flag. The lists are 1:1 and in the
    # same order by construction, so carry the money + the provenance markers
    # across; without this the response's darbu_sarasas (what the Kiekiai table
    # and the exports read) is silently price-free. (2026-07-28 P0.)
    _CARRY_KEYS = ("kaina", "suma", "manual_override", "quantity_source",
                   "ai_kiekis_original", "override_locked",
                   "_orphaned_after_rebuild",
                   # verification state (2026-09-04) — see _carry_verification
                   "user_verified_at", "_review_status", "_review_status_at",
                   # WHERE the price came from. Without it the compat row — the
                   # one the Kiekiai table and the exports read, and the one the
                   # frontend writes back onto the project — came back with the
                   # money but not the 'manual' flag that protects it, so the
                   # next "Taikyti kainyną" overwrote a hand-typed price.
                   *_PRICE_PROVENANCE_KEYS, *_ROW_CHOICE_KEYS)
    # Verification rides only with a quantity that survived (`_carry_verification`);
    # everything else is carried outright. The by-label fallback below used to
    # copy the checkmark unconditionally (2026-09-15 review).
    _MONEY_KEYS = tuple(k for k in _CARRY_KEYS if k not in _VERIFICATION_KEYS)
    if len(darbu_sarasas) == len(pozicijos):
        for row, poz in zip(darbu_sarasas, pozicijos):
            for key in _MONEY_KEYS:
                if poz.get(key) is not None:
                    row[key] = poz[key]
            _carry_verification(poz, row)
    else:
        # The 1:1 invariant broke (a compat-emit change, a dropped/merged row).
        # There was NO else here: the response's darbu_sarasas silently came
        # back price-free, and the frontend writes it straight onto the project
        # — the user watched their entered kainos vanish with no explanation.
        # (2026-07-28 audit, B3.)
        #
        # Fall back to an EXACT aprasymas match — no fuzzy matching, a
        # mislabelled price is worse than a missing one — so the money survives
        # wherever the labels still line up, and say what happened either way.
        by_label: dict[str, dict] = {}
        for poz in pozicijos:
            label = str(poz.get("aprasymas") or "").strip()
            if not label:
                continue
            # A duplicated label is ambiguous → carry nothing for it.
            by_label[label] = None if label in by_label else poz
        recovered = 0
        for row in darbu_sarasas:
            poz = by_label.get(str(row.get("aprasymas") or "").strip())
            if not poz:
                continue
            for key in _MONEY_KEYS:
                if poz.get(key) is not None:
                    row[key] = poz[key]
            _carry_verification(poz, row)
            recovered += 1
        log.warning("compat emit length mismatch: %d rows vs %d pozicijos "
                    "(%d recovered by label)",
                    len(darbu_sarasas), len(pozicijos), recovered)
        _lost = max(len(darbu_sarasas) - recovered, 0)
        degradations.append({
            "field": "darbu_sarasas",
            "reason": "compat_emit_mismatch",
            "rows": len(darbu_sarasas),
            "pozicijos": len(pozicijos),
            "recovered": recovered,
            "message": (
                f"Kiekių lentelė nesutapo su perskaičiuotomis eilutėmis "
                f"({len(darbu_sarasas)} / {len(pozicijos)}). Kainos perkeltos pagal "
                f"pavadinimą ({recovered} eil.); "
                + (f"patikrinkite kainas sąmatoje (be kainos liko eilučių: {_lost})."
                   if _lost else "patikrinkite sumas sąmatoje.")
            ),
        })

    # DISCLOSE what wasn't recomputed. Carried lines keep their ORIGINAL numbers
    # under the new assumptions — the user must know which ones so they can
    # re-check or delete them. Silence here is what made the row loss invisible.
    carried = [n for n in merge_notes if n.get("reason") == "orphan_carried"]
    lt_warnings: list[dict] = []
    if carried:
        msg = (f"Šios eilutės nebuvo perskaičiuotos pagal naujus nustatymus ir "
               f"paliktos su senais kiekiais ({len(carried)}): "
               + ", ".join(str(n.get("aprasymas") or "—") for n in carried[:8])
               + ("…" if len(carried) > 8 else "")
               + ". Patikrinkite jas sąmatoje arba pašalinkite.")
        degradations.append({
            "field": "pozicijos",
            "reason": "orphans_carried",
            "count": len(carried),
            "positions": [n.get("aprasymas") for n in carried],
            "message": msg,
        })
        lt_warnings.append({
            "level": "WARNING", "room": "", "field": "recompute",
            "value": len(carried), "expected": None, "message": msg,
        })

    # Carried orphans keep the prose they were saved with — scrub the output
    # like the read path does (extractor/user_text.py).
    pozicijos = _user_text.scrub_prose(pozicijos)
    darbu_sarasas = _user_text.scrub_prose(darbu_sarasas)
    return {
        "rooms": rooms,
        # 2026-09-25: the project-level pass's verdicts (frameless doors, reveals scope) travel back so the
        # Prielaidos panel's notes follow his switch instead of the extraction-time sentence
        "_paruosimas": _paruosimas,
        "pozicijos": pozicijos,
        "darbu_sarasas": darbu_sarasas,
        "assumptions": assumptions,
        "_degradations": degradations,
        # Same shape /recompute-interior emits, so SanityWarningsBanner can
        # render it once the frontend forwards it.
        "lt_sanity": {
            "warnings": lt_warnings,
            "summary": {
                "warnings_count": len(lt_warnings),
                "errors": 0,
                "warnings": len(lt_warnings),
                "info": 0,
                "pozicijos_carried": len(carried),
            },
        },
        "_merge_notes": merge_notes,
    }
