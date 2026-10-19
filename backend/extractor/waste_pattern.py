"""Waste factor by the laying pattern the drawing WRITES (Pathon v3 W5-E, E7).

Behind flag ``SAMATU_WASTE_BY_PATTERN`` (default off — nothing changes with it off). With it on, the
tile and floor-covering material rows take their waste from ``UNIVERSAL_RULES["waste_factors"]`` keyed by
the pattern read off the drawing's own text (the floor-plan covering label, the tile specification excerpt)
instead of the fixed 1,08 / 1,10; paint litres carry the §3 paint waste. Material row NAMES never change (price-list
assemblies match on them, api/assemblies_default.py) — the pattern and factor go into the row's `_assumption`.

Factors come only from CLAUDE.md §1.6 / §1.7 / §3 via ``UNIVERSAL_RULES``. A pattern is claimed only when
the text names exactly one; two different patterns in one group, or none, fall back to straight laying.
Pure: no I/O.
"""
from __future__ import annotations

import os
import re
import unicodedata
from typing import Iterable

FLAG_ENV = "SAMATU_WASTE_BY_PATTERN"

STRAIGHT = "straight"
HERRINGBONE = "herringbone"
DIAGONAL = "diagonal"
HEXAGONAL = "hexagonal"
PATTERN_LT = {STRAIGHT: "tiesus", HERRINGBONE: "eglutė", DIAGONAL: "įstrižai", HEXAGONAL: "šešiakampės"}

# The words a LT drawing uses for each pattern (accents folded, lower case).
_PATTERN_WORDS = (
    (HERRINGBONE, re.compile(r"eglut|egliuk|herringbone|chevron|silke")),
    (HEXAGONAL, re.compile(r"sesiakamp|heksagon|hexagon|\bhex\b|koriu")),
    (DIAGONAL, re.compile(r"istrizai|istrizain|istrizas|diagonal|45\s*°?\s*kampu")),
)


def enabled() -> bool:
    """The flag, read on every call so a test or the eval can toggle it per process."""
    return os.environ.get(FLAG_ENV) == "1"


def _fold(text: str) -> str:
    s = unicodedata.normalize("NFKD", str(text or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def pattern_of_text(text: str | None) -> str | None:
    """The one pattern a text names, else None (no pattern word, or two different ones)."""
    folded = _fold(text or "")
    if not folded.strip():
        return None
    hits = {name for name, rx in _PATTERN_WORDS if rx.search(folded)}
    return next(iter(hits)) if len(hits) == 1 else None


def pattern_of_texts(texts: Iterable[str | None]) -> str:
    """One pattern for a group of texts: the single pattern they agree on, else straight."""
    found = {p for p in (pattern_of_text(t) for t in texts) if p}
    return next(iter(found)) if len(found) == 1 else STRAIGHT


def room_floor_text(room: dict) -> str:
    """The floor plan's own covering label for a room (`_grindu_danga.tekstas`), or ''."""
    ev = room.get("_grindu_danga") if isinstance(room, dict) else None
    return str(ev.get("tekstas") or "") if isinstance(ev, dict) else ""


def tile_spec_texts(parsed: dict, where: set[str] | None) -> list[str]:
    """Tile-specification excerpts for one location (`where` in the reader's vonia / wc / virtuve / kita;
    None = every excerpt not of a wet room or the kitchen)."""
    out = []
    for s in parsed.get("_plyteliu_specs") or []:
        if not isinstance(s, dict):
            continue
        w = str(s.get("where") or "kita")
        if (w in where) if where is not None else (w not in ("vonia", "wc", "virtuve")):
            out.append(str(s.get("raw_excerpt") or ""))
    return out


def factor(kind: str, pattern: str, rules: dict | None = None) -> float:
    """1 + waste for a material kind (``tiles`` / ``floor`` / ``paint``) and pattern, from
    ``UNIVERSAL_RULES["waste_factors"]``. Floors: herringbone takes the parquet key, other patterns the
    laminate key; a pattern with no key of its own falls back to the straight one."""
    if rules is None:
        from .universal_rules import UNIVERSAL_RULES
        rules = UNIVERSAL_RULES
    wf = rules.get("waste_factors") or {}
    if kind == "paint":
        return 1.0 + float(wf.get("paint", 0.0))
    if kind == "tiles":
        key, straight = f"tiles_{pattern}", "tiles_straight"
    else:
        key = "parquet_herringbone" if pattern == HERRINGBONE else f"laminate_{pattern}"
        straight = "laminate_straight"
    return 1.0 + float(wf.get(key, wf.get(straight, 0.0)))


def pct_label(f: float) -> str:
    """„12" for 1,12 — the waste % written into a material name."""
    return str(int(round((f - 1.0) * 100)))
