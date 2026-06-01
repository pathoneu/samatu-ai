"""Multi-signal ceiling-height fusion.

Three independent signals are merged per project:
  1. Explicit annotation from `vision/height_extractor.py` (highest priority
     when present and confidence != low).
  2. Door height + lintel derivation:
     LT residential interior doors are nearly always 2100 mm tall; the
     finished ceiling sits ~600 mm above the door head. So a 2100 mm
     door implies ~2700 mm ceiling; a 2400 mm door implies ~3000 mm
     ceiling. This signal is computed from existing elementai (zero
     Vision cost) but only fires when the door height is non-default.
  3. Default fallback (2.70 m) when no other signal is available.

The fusion result lives on each project's ai_extract as
``_height_fusion = {signals, primary_m, source, confidence}``.
The chosen primary value is applied to every room whose
``_lubu_aukstis_source`` isn't already 'height_extractor' (which means
we have an explicit reading).

Note on dimensionally-impossible signals: the user-suggested
"height = area / (perimeter/2)" reduces to W/2 for a square room of
side W (W*W / (2W) = W/2). That's a floor dimension, not a ceiling
dimension. Skipped intentionally.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field, asdict
from typing import Any

# LT interior-door standard. Finishing lintel allowance (head-to-ceiling).
LT_INTERIOR_DOOR_MM_DEFAULT = 2100
LT_LINTEL_TO_CEILING_MM = 600
LT_HEIGHT_PLAUSIBLE_RANGE = (2.4, 4.0)
DEFAULT_FALLBACK_H = 2.70


@dataclass
class HeightSignal:
    source: str             # "explicit" | "door_lintel" | "default"
    value_m: float | None
    confidence: str         # "high" | "medium" | "low"
    evidence: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class HeightFusion:
    signals: list[HeightSignal] = field(default_factory=list)
    primary_m: float | None = None
    chosen_source: str = ""
    confidence: str = "low"

    def to_dict(self) -> dict[str, Any]:
        return {
            "signals": [s.to_dict() for s in self.signals],
            "primary_m": self.primary_m,
            "chosen_source": self.chosen_source,
            "confidence": self.confidence,
        }


def signal_from_door_heights(rooms: list[dict]) -> HeightSignal:
    """Derive ceiling height from the most common door height in elementai.

    Only fires for NON-STANDARD doors (e.g., 2400mm). Standard 2100mm
    doors recover only the default 2.7m, which is information-less —
    return None in that case so the fusion doesn't overwrite a
    Vision-extracted height with a tautology.
    """
    door_heights: list[float] = []
    for r in rooms:
        for el in (r.get("elementai") or []):
            tipas = (el.get("tipas") or "").lower()
            if tipas not in ("duris", "pasleptos_duris"):
                continue
            h_mm = float(el.get("aukstis_mm") or 0)
            if 1700 <= h_mm <= 2600:  # plausible door height range
                door_heights.append(h_mm)
    if not door_heights:
        return HeightSignal(source="door_lintel", value_m=None,
                            confidence="low",
                            evidence="no door heights in elementai")
    try:
        most_common = statistics.mode(door_heights)
    except statistics.StatisticsError:
        most_common = statistics.median(door_heights)
    # Only emit a usable value when the door is non-standard. Standard
    # 2100mm doors → 2.7m which is just the default; would overwrite
    # potentially-better Vision estimates.
    if abs(most_common - LT_INTERIOR_DOOR_MM_DEFAULT) < 100:
        return HeightSignal(
            source="door_lintel", value_m=None, confidence="low",
            evidence=f"door mode={most_common}mm (standard) — no signal beyond default",
        )
    derived_m = (most_common + LT_LINTEL_TO_CEILING_MM) / 1000.0
    n = len(door_heights)
    return HeightSignal(
        source="door_lintel", value_m=round(derived_m, 2), confidence="high",
        evidence=(f"non-standard door mode={most_common}mm across {n} doors → "
                  f"ceiling ≈ {derived_m:.2f}m"),
    )


def signal_from_explicit_reading(payload: dict | None) -> HeightSignal:
    """Wrap a `vision/height_extractor.py` payload as a fusion signal."""
    if not payload or not payload.get("primary_value_m"):
        return HeightSignal(source="explicit", value_m=None,
                            confidence="low",
                            evidence="no annotation found")
    val = float(payload["primary_value_m"])
    return HeightSignal(
        source="explicit",
        value_m=val,
        confidence=str(payload.get("confidence") or "medium"),
        evidence=str(payload.get("source_quote") or "")[:120],
    )


def fuse(signals: list[HeightSignal]) -> HeightFusion:
    """Strict-confidence fusion to avoid regressing well-extracted heights.

    Apply ONLY when:
      • explicit signal at HIGH confidence (medium isn't enough — too
        many false-positives from wall_elevation pages where the model
        picks fixture heights), OR
      • door_lintel signal at HIGH confidence (non-standard door)

    If neither fires, ``primary_m = None`` and the caller MUST keep the
    existing height. (No tautological default-override.)
    """
    out = HeightFusion(signals=list(signals))
    for s in signals:
        if (s.source == "explicit" and s.value_m is not None
                and s.confidence == "high"
                and LT_HEIGHT_PLAUSIBLE_RANGE[0] <= s.value_m <= LT_HEIGHT_PLAUSIBLE_RANGE[1]):
            out.primary_m = s.value_m
            out.chosen_source = "explicit"
            out.confidence = "high"
            return out
    for s in signals:
        if (s.source == "door_lintel" and s.value_m is not None
                and s.confidence == "high"
                and LT_HEIGHT_PLAUSIBLE_RANGE[0] <= s.value_m <= LT_HEIGHT_PLAUSIBLE_RANGE[1]):
            out.primary_m = s.value_m
            out.chosen_source = "door_lintel"
            out.confidence = "high"
            return out
    # No reliable signal — leave heights untouched
    out.primary_m = None
    out.chosen_source = "none"
    out.confidence = "low"
    return out


# Known Vision/eksplikacija default heights — rooms with these exact values
# are likely guessed-uniform defaults. Rooms with OTHER values (e.g. 3.4m
# for a high-ceiling Svetainė) carry per-room Vision-extracted information
# that we must NOT clobber with a project-level fused value.
VISION_DEFAULT_HEIGHTS_M = {2.50, 2.65, 2.70, 2.75, 2.80, 2.82}


def apply_fused_height_to_rooms(rooms: list[dict],
                                 fusion: HeightFusion) -> dict:
    """Apply the fused primary height to rooms that DON'T already carry a
    Vision-extracted per-room value.

    Skip when:
      • a previous height_extractor pass already updated this room, OR
      • the room's current height is OUT of the known default-guess set
        (≈ Vision already extracted a specific value to honour high-
        ceiling zones, sloped roofs, etc.)
    """
    summary = {"n_updated": 0, "from_to": [], "preserved": []}
    if fusion.primary_m is None:
        return summary
    for r in rooms:
        if r.get("_lubu_aukstis_source") == "height_extractor":
            continue
        old_h = round(float(r.get("lubu_aukstis_m") or 0), 2)
        if old_h and old_h not in VISION_DEFAULT_HEIGHTS_M:
            # Per-room Vision value detected; preserve it.
            summary["preserved"].append({"nr": r.get("nr"), "value_m": old_h})
            continue
        new_h = fusion.primary_m
        if abs(new_h - old_h) >= 0.05:
            r["lubu_aukstis_m"] = round(new_h, 2)
            r["_lubu_aukstis_source"] = f"fusion:{fusion.chosen_source}"
            summary["from_to"].append({"nr": r.get("nr"), "from": old_h, "to": new_h})
            summary["n_updated"] += 1
    return summary
