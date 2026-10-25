"""extractor.wall_elevation — the TEXT of the sienų išklotinės sheets (v4 Phase 3c-2). Opt-in: WALL_ELEVATION_EXTRACT=1.

Until v4 3c-2 this module sent every elevation sheet to a model at 300 DPI and asked it for the tile / paint / niche
zones in millimetres — a model reading the drawing's pixels. That is gone. What is read now is the sheet's TEXT
(text layer; local OCR behind `SAMATU_OCR`): a sheet that names exactly one room of the project, and a line on it
that ties tiles to a height written in millimetres or metres („PLYTELĖS H=2400", „plytelės iki 1,20 m",
„plytelės iki lubų" → the room's height is not known here, so no number) becomes that room's tile zone from the
floor to that height, the line kept as `raw_text`. Wall widths are a measure of the drawing (the geometry), not of its
text: `wall_total_width_mm` stays None, so the tile override (`vision_call._apply_wall_elevation_tile_override`)
takes nothing from a zone without its width — the zones are evidence for the room sheet.

Output shape (PAGE_OUTPUT_SCHEMA per page, as before):
    {"wall_elevations": [{page, nr, room_name, wall_id, tile_zones: [{from_floor_mm, to_floor_mm, raw_text}],
                          paint_zones: [], niches: [], furniture_zones: [], wall_total_width_mm: None,
                          wall_total_height_mm: None, confidence: "medium"}],
     "_meta": {pages_processed, pages_failed, elapsed_s, saltinis: "tekstas", ...}}

No model call, no image. Never raises.
"""
from __future__ import annotations

import json
import re as _re
import time
import unicodedata
from typing import Any

__all__ = ["extract_wall_elevations"]


# =============================================================================
# JSON SCHEMA — locked output for ONE wall elevation page
# =============================================================================
PAGE_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["page", "wall_elevations"],
    "properties": {
        "page": {"type": "integer"},
        "wall_elevations": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["wall_id", "tile_zones", "paint_zones", "niches", "furniture_zones"],
                "properties": {
                    "nr": {"type": ["string", "null"],
                           "description": "Room number from eksplikacija (e.g. '107', '111'). REQUIRED when readable."},
                    "room_name": {"type": ["string", "null"],
                                  "description": "Room name as labelled in drawing title block. Match eksplikacija."},
                    "wall_id": {"type": "string",
                                "description": "Wall label (A/B/1/2/N/S/E/W). Use literal label from drawing."},
                    "wall_total_width_mm": {"type": ["integer", "null"]},
                    "wall_total_height_mm": {"type": ["integer", "null"]},
                    "tile_zones": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["from_floor_mm", "to_floor_mm"],
                            "properties": {
                                "from_floor_mm": {"type": "integer"},
                                "to_floor_mm": {"type": "integer"},
                                "wall_segment_label": {"type": ["string", "null"]},
                            },
                        },
                    },
                    "paint_zones": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["from_floor_mm", "to_floor_mm"],
                            "properties": {
                                "from_floor_mm": {"type": "integer"},
                                "to_floor_mm": {"type": "integer"},
                            },
                        },
                    },
                    "niches": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["width_mm", "height_mm"],
                            "properties": {
                                "width_mm": {"type": "integer"},
                                "height_mm": {"type": "integer"},
                                "depth_mm": {"type": ["integer", "null"]},
                                "purpose": {"type": ["string", "null"]},
                            },
                        },
                    },
                    "furniture_zones": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["from_floor_mm", "to_floor_mm", "width_mm"],
                            "properties": {
                                "from_floor_mm": {"type": "integer"},
                                "to_floor_mm": {"type": "integer"},
                                "width_mm": {"type": "integer"},
                                "label": {"type": ["string", "null"]},
                            },
                        },
                    },
                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                },
            },
        },
    },
}



# What the text reader looks for (folded: upper case, no diacritics)
SYSTEM_TEXT = ("Teksto skaitytuvas: išklotinės lapo eilutė, siejanti PLYTELES su aukščiu milimetrais (H=2400, iki 2400 mm) "
               "arba metrais (iki 1,20 m) — be modelio, be paveikslėlio.")
_TILE_H = _re.compile(r"PLYTEL\w*.{0,40}?(?:H\s*[=-]\s*|IKI\s+)(\d{3,4}|\d[.,]\d{1,2})\s*(MM|M)?\b")


def _fold(text) -> str:
    s = unicodedata.normalize("NFD", str(text or "").upper())
    return " ".join("".join(c for c in s if not unicodedata.combining(c)).split())


def _repair_json(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        if text.endswith("```"):
            text = text[:-3]
    text = _re.sub(r",(\s*[}\]])", r"\1", text)
    return text


def _mm(raw: str, unit: str | None) -> int | None:
    try:
        v = float(raw.replace(",", "."))
    except ValueError:
        return None
    mm = v * 1000 if (unit == "M" or (unit is None and v < 10)) else v
    return int(round(mm)) if 300 <= mm <= 4500 else None


def extract_wall_elevations(
    pdf_bytes: bytes,
    client=None,
    wall_elevation_pages: list[int] | None = None,
    room_list: list[dict] | None = None,
) -> dict:
    """The tile heights the elevation sheets' text writes, per room (see the module docstring). `client` is
    accepted for the old call shape and never used."""
    t0 = time.time()
    out: dict[str, Any] = {"wall_elevations": [], "_meta": {"pages_processed": 0, "pages_failed": 0,
                                                            "elapsed_s": 0.0, "saltinis": "tekstas",
                                                            "input_tokens_total": 0, "output_tokens_total": 0,
                                                            "cache_read_tokens_total": 0}}
    if not wall_elevation_pages:
        return out
    try:
        from .apdailos_reader import _rooms_named, _sheet_text
    except Exception:  # noqa: BLE001
        return out
    rooms = room_list or []
    by_nr = {str(r.get("nr") or "").strip(): r for r in rooms}
    for page in wall_elevation_pages:
        text = _sheet_text(pdf_bytes, int(page))
        if not text.strip():
            out["_meta"]["pages_failed"] += 1
            continue
        out["_meta"]["pages_processed"] += 1
        named = _rooms_named(_fold(text), rooms) if rooms else []
        zones = []
        for line in text.splitlines():
            m = _TILE_H.search(_fold(line))
            if not m:
                continue
            mm = _mm(m.group(1), m.group(2))
            if mm:
                zones.append({"from_floor_mm": 0, "to_floor_mm": mm, "wall_segment_label": None,
                              "raw_text": line.strip()[:160]})
        if not zones:
            continue
        nr = named[0] if len(named) == 1 else None
        out["wall_elevations"].append({
            "page": int(page), "nr": nr, "room_name": (by_nr.get(nr) or {}).get("pavadinimas") if nr else None,
            "wall_id": "tekstas", "tile_zones": zones, "paint_zones": [], "niches": [], "furniture_zones": [],
            "wall_total_width_mm": None, "wall_total_height_mm": None, "confidence": "medium"})
    out["_meta"]["elapsed_s"] = round(time.time() - t0, 2)
    return out
