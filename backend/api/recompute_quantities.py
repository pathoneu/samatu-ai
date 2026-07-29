# backend/api/recompute_quantities.py
"""POST /api/recompute-quantities — single source of truth for paint
recompute (Sprint 0 Fix 2) plus gesture edits (Sprint 2 G2/G3/G4/G7).

Returns the full updated rooms[] + pozicijos[] so the frontend can
swap the canonical view in one re-render.

Spec: §4.5, §5.4
"""
import logging
import re
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Any
from extractor.universal_rules import UNIVERSAL_RULES, paint_coverage_for_class

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
    # 2026-07-05: per-room finishing override (Beržų garage: contractors finish
    # some garages/tambūrai — painted walls — that default to raw. Keyed by
    # patalpa.nr → 0.0 (raw) / 1.0 (painted). Flips walls_paint in the room's
    # rules and recomputes the paint fields, same live path as ceiling height.
    "walls_paint_override",
    # 2026-07-29: concealed-vs-surface mixer. The builder splits a POTINKINIS
    # mixer into its rough-in + trim pair and says so as a disclosed assumption
    # (nothing we read tells us which it is). CLAUDE.md's rule — every
    # assumption must be overridable with a live recalc — means the answer has
    # to be reachable through this endpoint. Accepts a bool (whole project) or
    # {"praustuve"|"dusas"|"vonia"|"bide": bool}; both shapes land in
    # `_overrides` verbatim and are read by `_resolve_san_concealment`.
    "santechnika_potinkinis",
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
    paint_class = int(_num_field(
        assumptions.get("paint_class", _MISSING), 1,
        degradations, "paint_class"))
    cov_walls, cov_ceil = paint_coverage_for_class(paint_class)
    absorption = float(UNIVERSAL_RULES["first_coat_factor"])
    per_room_h = assumptions.get("lubu_auksciai") or {}
    per_room_paint = assumptions.get("walls_paint_override") or {}
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
                    perim = _num(room.get("perimetras_m"), 0)
                    room["calculation_trace"] = (
                        f"perim({perim:.2f}) × H({new_h:.2f}) = "
                        f"{perim * new_h:.2f} m² "
                        f"− {n_windows} lang./{n_doors} dur. atimimai → "
                        f"dažymas {_num(room.get('dazymo_plotas_m2'), 0):.2f} m². "
                        f"Skaičiavo Python (deterministinis)."
                    )
                except Exception as exc:  # noqa: BLE001 — degrade, never 500
                    _degrade(degradations, nr, "lubu_aukstis",
                             "recompute_failed", stage="calc_room_quantities",
                             error=str(exc)[:120])
        # Per-room finishing override (2026-07-05): flip walls_paint (raw↔painted)
        # and recompute the paint geometry. Runs AFTER the height block so a room
        # with BOTH overrides gets the combined result (calc reads the already-set
        # lubu_aukstis_m). Same carry-forward set as the height path.
        if isinstance(per_room_paint, dict) and nr in per_room_paint:
            try:
                wp = 1.0 if float(per_room_paint[nr]) >= 0.5 else 0.0
                from extractor.universal_rules import (
                    calc_room_quantities, ROOM_TYPE_RULES, normalize_paskirtis,
                )
                pask = normalize_paskirtis(room.get("paskirtis") or "")
                rt = dict(ROOM_TYPE_RULES.get(pask) or ROOM_TYPE_RULES["gyvenamoji"])
                rt["walls_paint"] = wp
                room["_walls_paint_override"] = wp
                recalc = calc_room_quantities(room, rules={pask: rt})
                for k in ("walls_gross_m2", "walls_paintable_m2",
                          "ceiling_paintable_m2", "dazymo_plotas_m2",
                          "kampai_m", "kampu_metrai", "lubu_karnizo_m",
                          "glaistas_kg", "gruntas_l",
                          "gkp_lubu_standart_m2", "gkp_lubu_virs_3m_m2"):
                    if k in recalc:
                        room[k] = recalc[k]
            except (ValueError, TypeError) as exc:
                _degrade(degradations, nr, "walls_paint_override",
                         "recompute_failed", stage="walls_paint_override",
                         error=str(exc)[:120])
        walls = _num_field(
            room.get("dazomas_plotas_m2") or room.get("walls_paintable_m2") or _MISSING,
            0.0, degradations, "dazomas_plotas_m2", room=nr)
        ceiling = _num_field(
            room.get("lubu_dazomas_plotas_m2") or room.get("ceiling_paintable_m2") or _MISSING,
            0.0, degradations, "lubu_dazomas_plotas_m2", room=nr)
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
            room["pasleptu_duru_kompl"] = hidden_door_count(openings)
            room["pasleptu_duru_staktu_m"] = hidden_door_frame_lm(openings)
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


_TIER_SUFFIX_RE = re.compile(
    r"\s*\((?:iki|virš)\s*3\s*m[^)]*\)"          # (iki 3m aukščio) / (virš 3 m aukščio)
    r"|\s*\(standartinis aukštis\)"               # GKP tier label
    r"|\s*—\s*papildomas darbas dėl aukščio"      # height-premium tail
    r"|\s*q4\s*\([^)]*\)",                         # Q4 sanding suffix
    re.IGNORECASE,
)


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


def _tier_key(s: str | None) -> str:
    """Label with ONLY the height/Q-level tier suffixes stripped.

    Two labels sharing a tier key describe the same work at different ceiling
    tiers ('… (iki 3m aukščio)' vs '… (virš 3m aukščio)' vs '… (standartinis
    aukštis)'). Used by the orphan pass to tell a legitimately RE-TIERED line
    (the work is still in the list, under the sibling label) from a line the
    rebuild simply cannot produce (corner beads, whole electrical sections).
    Deliberately does NOT fold the LED pair — 'LED nišų dažymas' is a distinct
    work item from the consolidated line, so it must still be carried."""
    return _TIER_SUFFIX_RE.sub("", (s or "").strip().lower()).strip()


def _norm_label(s: str | None) -> str:
    """Height/Q-level-independent label key: strip the tier suffixes whose text
    flips when a ceiling crosses 3 m or the glaistymo lygis changes, so a priced
    line can be matched to its post-rebuild sibling. Also collapses the LED
    glaistymas/dažymas pair onto its consolidated label."""
    base = _tier_key(s)
    if _LED_PAIR_RE.match(base):
        return _LED_CONSOLIDATED
    return _SAN_LEGACY_SPLIT.get(base, base)


def _has_user_edit(p: dict) -> bool:
    return (p.get("kaina") not in (None, 0)
            or p.get("manual_override") is True
            or p.get("quantity_source") == "manual_override"
            or bool(p.get("override_locked")))


_TRAILING_PAREN_RE = re.compile(r"\s*\([^()]*\)\s*$")


def _price_index(darbu_sarasas: list[dict]) -> dict[str, dict]:
    """label-key → priced/edited darbu_sarasas row.

    Indexed three ways because the same line appears under slightly different
    text in the two lists: exact lowercased label, the height-independent
    `_norm_label`, and the label with a trailing parenthetical removed
    (`_emit_v8_compat_fields` appends `(pastaba)` to the darbu_sarasas label,
    e.g. tile size, so its text is LONGER than the pozicija's)."""
    idx: dict[str, dict] = {}
    for row in darbu_sarasas or []:
        if not isinstance(row, dict) or not _has_user_edit(row):
            continue
        lab = (row.get("aprasymas") or row.get("pavadinimas") or "").strip()
        if not lab:
            continue
        for key in (lab.lower(), _norm_label(lab),
                    _TRAILING_PAREN_RE.sub("", lab).strip().lower()):
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
        if not lab:
            continue
        row = (idx.get(lab.lower()) or idx.get(_norm_label(lab))
               or idx.get(_TRAILING_PAREN_RE.sub("", lab).strip().lower()))
        if row is None:
            continue
        kaina = row.get("kaina")
        if kaina not in (None, 0):
            p["kaina"] = kaina
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


def _merge_user_edits(rebuilt: list[dict], prior: list[dict],
                      notes: list | None = None) -> list[dict]:
    """After a canonical pozicijos rebuild (ceiling/assumption edit), carry the
    user's manual edits forward from the prior pozicijos so the rebuild doesn't
    silently revert them.

    Two-pass match:
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
    """
    if notes is None:
        notes = []
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
        edited = _has_user_edit(p)
        # Legacy sanitary line the split replaced. Emitted as `relabeled` (not
        # `superseded_by_tier`) on purpose: InteriorProject.jsx forwards exactly
        # the `relabeled` notes to the frontend merge as `serverRelabeled`, and
        # that is what stops the browser-side pass 3 from re-carrying the same
        # row the backend just folded away.
        _into = _SAN_LEGACY_SPLIT.get((p.get("aprasymas") or "").strip().lower())
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
        rebuilt.append({**p, "_orphaned_after_rebuild": True})
        notes.append({"aprasymas": p.get("aprasymas"), "reason": "orphan_carried",
                      "kiekis": p.get("kiekis"), "kaina": p.get("kaina"),
                      "user_edit": edited})
    return rebuilt


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
    rooms = _apply_assumption_edits(list(req.rooms), assumptions, degradations)

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
                   "_orphaned_after_rebuild")
    if len(darbu_sarasas) == len(pozicijos):
        for row, poz in zip(darbu_sarasas, pozicijos):
            for key in _CARRY_KEYS:
                if poz.get(key) is not None:
                    row[key] = poz[key]
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
            for key in _CARRY_KEYS:
                if poz.get(key) is not None:
                    row[key] = poz[key]
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
                f"Kiekių lentelė nesutapo su pozicijomis ({len(darbu_sarasas)} / "
                f"{len(pozicijos)}). Kainos perkeltos pagal pavadinimą "
                f"({recovered} eil.); patikrinkite "
                + (f"{_lost} eilučių kainas." if _lost else "sumas.")
            ),
        })

    # DISCLOSE what wasn't recomputed. Carried lines keep their ORIGINAL numbers
    # under the new assumptions — the user must know which ones so they can
    # re-check or delete them. Silence here is what made the row loss invisible.
    carried = [n for n in merge_notes if n.get("reason") == "orphan_carried"]
    lt_warnings: list[dict] = []
    if carried:
        msg = (f"{len(carried)} pozicijų nebuvo perskaičiuotos pagal naujas "
               f"prielaidas — paliktos originalios: "
               + ", ".join(str(n.get("aprasymas") or "—") for n in carried[:8])
               + ("…" if len(carried) > 8 else ""))
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

    return {
        "rooms": rooms,
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
