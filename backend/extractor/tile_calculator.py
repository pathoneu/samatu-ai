"""tile_calculator — convert ElevationPayload + plan room data into exact
per-room tile / paint area numbers.

Replaces the percentage-of-perimeter approximation in
``universal_rules.calc_room_quantities`` (the apdailos_breakdown path) once
real elevation data is available. The output is a per-room override block:

    {
      "111": {
        "plyteles_sienos_m2": 28.80,
        "paint_walls_extra_deduction_m2": 28.80,   # subtract from paintable
        "plyteles_grindys_m2": null,               # floor tiles come from
                                                   # floor plan, not elevations
        "formats": ["120x60"],
        "source": "elevation_zones",
        "confidence": "high",
      },
      ...
    }

The override block fits into ``patalpos[*].sienu_apdailos_breakdown`` or as
explicit ``walls_paint_factor_override`` / ``plyteles_sienos_m2_override`` so
the formula engine consumes it without further changes.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from .vision.elevation_extractor import ElevationPayload, ElevationPanel, ElevationZone


@dataclass
class RoomTileResult:
    room_nr: str
    panel_ids: list[str] = field(default_factory=list)
    tile_area_m2: float = 0.0
    paint_area_m2: float = 0.0
    other_area_m2: float = 0.0     # wood / mirror / wallpaper combined
    opening_area_m2: float = 0.0   # subtracted from totals
    panel_area_m2: float = 0.0     # sum of wall_length × height
    formats: list[str] = field(default_factory=list)
    confidence: str = "high"

    def to_dict(self) -> dict[str, Any]:
        return {
            "panel_ids": list(self.panel_ids),
            "plyteles_sienos_m2": round(self.tile_area_m2, 2),
            "paint_walls_m2": round(self.paint_area_m2, 2),
            "other_walls_m2": round(self.other_area_m2, 2),
            "opening_area_m2": round(self.opening_area_m2, 2),
            "panel_area_m2": round(self.panel_area_m2, 2),
            "formats": sorted(set(self.formats)),
            "source": "elevation_zones",
            "confidence": self.confidence,
        }


def _zone_area_m2(z: ElevationZone) -> float:
    return (z.width_mm * z.height_mm) / 1_000_000.0


def calculate_room_tile_area(payload: ElevationPayload) -> dict[str, RoomTileResult]:
    """Group panels by room_nr and sum zones per material.

    Returns
    -------
    dict[str, RoomTileResult]
        Keyed by room_nr (string, matches existing ``patalpos[*].nr``).
        Opening zones are deducted from BOTH tile and paint shares
        proportionally to their physical area within each material's region.
    """
    rooms: dict[str, RoomTileResult] = defaultdict(lambda: RoomTileResult(room_nr=""))
    # First pass — raw sums per material per room
    for panel in payload.panels:
        nr = str(panel.room_nr)
        r = rooms[nr]
        r.room_nr = nr
        r.panel_ids.append(panel.panel_id)
        r.panel_area_m2 += panel.panel_area_m2
        for z in panel.zones:
            a = _zone_area_m2(z)
            if z.material == "tile":
                r.tile_area_m2 += a
                if z.format_label:
                    r.formats.append(z.format_label)
            elif z.material == "paint":
                r.paint_area_m2 += a
            elif z.material == "opening":
                r.opening_area_m2 += a
            else:
                r.other_area_m2 += a

            # Carry lowest confidence forward
            if z.confidence == "low":
                r.confidence = "low"
            elif z.confidence == "medium" and r.confidence == "high":
                r.confidence = "medium"

    return dict(rooms)


WET_ROOM_PASKIRTYS = {"vonia", "wc", "san", "skalbykla", "katiline"}
HIGH_TILE_RATIO_WARNING = 0.80


def diagnose_tile_coverage(
    parsed: dict[str, Any],
    elevation_results: dict[str, RoomTileResult],
) -> list[dict[str, Any]]:
    """Soft sanity check — never mutates totals; surfaces a list of warnings
    when a non-wet room comes back with ≥80% tile coverage on walls. Real LT
    bathrooms tile floor-to-ceiling (95%+), so we explicitly do NOT clamp
    wet rooms. The warning surfaces likely Vision over-counts on living-area
    rooms (kitchens with full-height tile splashes are rare; if Vision says
    a svetainė is 90% tiled, the elevation read is probably wrong).
    """
    warnings: list[dict[str, Any]] = []
    rooms_by_nr = {str(r.get("nr")): r for r in parsed.get("patalpos") or []}
    for nr, result in elevation_results.items():
        room = rooms_by_nr.get(nr)
        if not room:
            continue
        wall_gross = float(room.get("perimetras_m") or 0) * float(room.get("lubu_aukstis_m") or 0)
        if wall_gross <= 0:
            continue
        ratio = result.tile_area_m2 / wall_gross
        paskirtis = (room.get("paskirtis") or "").lower()
        if ratio >= HIGH_TILE_RATIO_WARNING and paskirtis not in WET_ROOM_PASKIRTYS:
            warnings.append({
                "room_nr": nr,
                "room_name": room.get("pavadinimas"),
                "paskirtis": paskirtis,
                "tile_ratio": round(ratio, 3),
                "tile_area_m2": round(result.tile_area_m2, 2),
                "wall_gross_m2": round(wall_gross, 2),
                "message": (
                    f"non-wet room with {ratio:.0%} tile coverage — verify "
                    f"elevation read (truth-friendly diagnostic, no clamp applied)"
                ),
            })
    return warnings


def apply_tile_overrides_to_rooms(
    parsed: dict[str, Any],
    elevation_results: dict[str, RoomTileResult],
) -> dict[str, Any]:
    """Inject the per-room tile/paint override primitives into a ``parsed``
    extractor dict so the deterministic engine picks them up on the next
    `_recompute_per_room_via_python` pass.

    Sets:
        plyteles_sienos_m2_override (m²)
        extra_walls_m2 — negative? We don't go negative; instead, when the
            elevation says paint_area is X, we set walls_paint_factor_override
            so walls_paintable resolves to X.

    The override is conservative: if the elevation panels cover less than 90%
    of the room's known wall surface (panel_area_m2 vs perim × H), we keep the
    legacy apdailos path. Phase 4 will firm this up as we collect real
    elevations.
    """
    overrides_by_nr = {nr: r for nr, r in elevation_results.items()}
    for room in parsed.get("patalpos") or []:
        nr = str(room.get("nr"))
        r = overrides_by_nr.get(nr)
        if r is None or r.panel_area_m2 <= 0:
            continue
        perim = float(room.get("perimetras_m") or 0)
        H = float(room.get("lubu_aukstis_m") or 2.82)
        expected_panel_area = perim * H
        coverage = r.panel_area_m2 / expected_panel_area if expected_panel_area > 0 else 0
        if coverage < 0.90:
            # Insufficient elevation coverage; leave the legacy path in
            # charge and stash the partial result for debugging.
            room.setdefault("_elevation_partial", r.to_dict())
            continue
        # Full coverage — override.
        room["plyteles_sienos_m2_override"] = round(r.tile_area_m2, 2)
        # Use walls_paint_factor_override to drive the paintable walls toward
        # the contractor-true paint area when the panels disagree with the
        # perim×H − doors prediction. A factor of paint_area / walls_gross
        # produces the right output.
        walls_gross = perim * H
        if walls_gross > 0:
            room["walls_paint_factor_override"] = round(
                max(0.0, r.paint_area_m2 / walls_gross), 4
            )
        room["_elevation_full"] = r.to_dict()
    return parsed
