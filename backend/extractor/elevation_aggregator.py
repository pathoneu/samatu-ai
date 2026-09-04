"""Per-room aggregation of elevation panels.

The elevation_extractor returns panels labeled by Vision-derived hints
(``room_nr="bath"``, ``"kitchen"``, ``"bedroom"`` or letter families like
``"e"``, ``"f"``). For projects that name elevations by letter clusters
(common in LT residential drawings), the project-specific mapping from
elevation-letter family → contractor room number lives ALONGSIDE the
project's truth file rather than baked into Vision.

This module exposes a small disambiguator that:
  1. Reads a project-specific letter→room_nr map.
  2. Walks the aggregated ElevationPayload panels.
  3. Sums tile / paint / wood_panel / opening areas per real room nr.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from .vision.elevation_extractor import ElevationPayload, ElevationPanel


# Objektas A-specific mapping. Each elevation page in the PDF carries a wall-
# label letter family (a/b/c/d/e/f/g/h) corresponding to one or two real
# rooms in the eksplikacija. The page-by-letter source of truth is the
# puslapiai title row in app-output-to-the-dot.json.
OBJEKTAS_A_PAGE_LETTER_TO_ROOM = {
    11: {"a": "102"},                  # svetainė/virtuvė
    12: {"b": "104", "c": "106"},      # darbo, skalbykla
    13: {"d": "107"},                  # vaikų san.mazgas
    14: {"e": "108", "f": "109"},      # berniukų kambariai
    15: {"g": "110"},                  # miegamasis
    16: {"h": "111"},                  # tėvų vonia
}


@dataclass
class RoomElevationSummary:
    room_nr: str
    tile_m2: float = 0.0
    paint_m2: float = 0.0
    wood_panel_m2: float = 0.0
    mirror_m2: float = 0.0
    opening_m2: float = 0.0
    panel_count: int = 0
    formats: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "room_nr": self.room_nr,
            "tile_m2": round(self.tile_m2, 3),
            "paint_m2": round(self.paint_m2, 3),
            "wood_panel_m2": round(self.wood_panel_m2, 3),
            "mirror_m2": round(self.mirror_m2, 3),
            "opening_m2": round(self.opening_m2, 3),
            "panel_count": self.panel_count,
            "formats": sorted(set(self.formats)),
        }


def disambiguate_panel_room(
    panel_id: str,
    page_nr: int,
    page_letter_map: dict[int, dict[str, str]],
) -> str | None:
    """Resolve a panel's room_nr by parsing the letter family out of its
    panel_id and consulting the page-letter map.

    Examples
    --------
    >>> disambiguate_panel_room("bath-d1-d2", 13, OBJEKTAS_A_PAGE_LETTER_TO_ROOM)
    '107'
    >>> disambiguate_panel_room("bath-h1", 16, OBJEKTAS_A_PAGE_LETTER_TO_ROOM)
    '111'
    >>> disambiguate_panel_room("kitchen-a1-a6-upper", 11, OBJEKTAS_A_PAGE_LETTER_TO_ROOM)
    '102'
    >>> disambiguate_panel_room("no-letter-here", 13, OBJEKTAS_A_PAGE_LETTER_TO_ROOM) is None
    True
    """
    parts = panel_id.split("-")
    for part in parts:
        if part and part[0].isalpha():
            letter = part[0].lower()
            mapping = page_letter_map.get(page_nr, {})
            if letter in mapping:
                return mapping[letter]
    return None


def aggregate_panels_by_room(
    panels_by_page: dict[int, list[ElevationPanel]],
    page_letter_map: dict[int, dict[str, str]],
) -> dict[str, RoomElevationSummary]:
    """Aggregate panels into per-room summaries using a page-letter map."""
    out: dict[str, RoomElevationSummary] = defaultdict(lambda: RoomElevationSummary(room_nr=""))
    for page_nr, panels in panels_by_page.items():
        for panel in panels:
            nr = disambiguate_panel_room(panel.panel_id, page_nr, page_letter_map)
            if not nr:
                continue
            summary = out[nr]
            summary.room_nr = nr
            summary.panel_count += 1
            for zone in panel.zones:
                a_m2 = (zone.width_mm * zone.height_mm) / 1_000_000.0
                if zone.material == "tile":
                    summary.tile_m2 += a_m2
                    if zone.format_label:
                        summary.formats.append(zone.format_label)
                elif zone.material == "paint":
                    summary.paint_m2 += a_m2
                elif zone.material == "wood_panel":
                    summary.wood_panel_m2 += a_m2
                elif zone.material == "mirror":
                    summary.mirror_m2 += a_m2
                elif zone.material == "opening":
                    summary.opening_m2 += a_m2
    return dict(out)


def aggregate_payload_by_room(
    payload: ElevationPayload,
    page_nr: int,
    page_letter_map: dict[int, dict[str, str]],
) -> dict[str, RoomElevationSummary]:
    """Single-page convenience wrapper around ``aggregate_panels_by_room``."""
    return aggregate_panels_by_room({page_nr: payload.panels}, page_letter_map)
