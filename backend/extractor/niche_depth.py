"""Curtain / LED niche depth (Pathon v3 W5-E, E3; CLAUDE.md §1.5 ``niche_paintable_area = niche_length ×
niche_depth × 3`` — top and two sides).

INPUT: ``nisos_gylis_m`` — typed on the room (its own niche), else the project assumption
``_overrides["nisos_gylis_m"]``. Nothing reads it off the ceiling-plan detail yet; with no depth the niche rows stay
in metres exactly as before (a missing depth is a blank, never a default).

TERM, behind flag ``SAMATU_NICHE_DEPTH`` (default off — nothing changes with it off): when every room with niche
metres has a depth, the two finishing rows („LED nišų glaistymas", „LED nišų dažymas") are billed in m² =
Σ metres × depth × 3 instead of metres. The framing row stays in metres. Pure helpers.
"""
from __future__ import annotations

import math
import os

FLAG_ENV = "SAMATU_NICHE_DEPTH"
KEY = "nisos_gylis_m"
DEPTH_RANGE = (0.03, 0.60)        # m — a niche shallower or deeper than this is a typing slip


def enabled() -> bool:
    return os.environ.get(FLAG_ENV) == "1"


def _depth(v) -> float | None:
    try:
        x = float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) and DEPTH_RANGE[0] <= x <= DEPTH_RANGE[1] else None


def room_depth(room: dict, overrides: dict | None) -> float | None:
    """The niche depth for a room: its own typed one, else the project's, else None."""
    d = _depth(room.get(KEY)) if isinstance(room, dict) else None
    if d is None and isinstance(overrides, dict):
        d = _depth(overrides.get(KEY))
    return d


def niche_area(rooms: list[dict], overrides: dict | None, metres_of) -> tuple[float, list[str]] | None:
    """(Σ metres × depth × 3, per-room parts) when every room with niche metres has a depth; else None."""
    total = 0.0
    parts: list[str] = []
    from .universal_rules import lt_num
    for r in rooms:
        m = float(metres_of(r) or 0)
        if m <= 0:
            continue
        d = room_depth(r, overrides)
        if d is None:
            return None
        total += m * d * 3
        parts.append(f"{str(r.get('pavadinimas') or r.get('nr') or '').strip()} {lt_num(m)} m × {lt_num(d)} m × 3")
    return (round(total, 2), parts) if total > 0 else None
