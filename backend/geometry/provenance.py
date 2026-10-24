"""Where a geometric number came from (plan 2026-10-24 §3.1 `provenance.py`).

Every scale the geometry package hands out is a `Scale`: the number AND the
source it was read from, the text that source wrote, how sure the reading is,
and — for a scale borrowed from another sheet — which sheet. A sheet with no
source is a `Scale` too: `m_per_pt is None`, `source == BLANK` and a reason
sentence (Lithuanian, user-visible: it says what to check, never pipeline
jargon). There is no default scale anywhere in this package.

Deterministic only: nothing under `backend/geometry/` may import a module
whose name starts with `vision` (guard test `test_geometry_no_vision_imports`).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

PT_M = 25.4 / 72 / 1000          # metres per PDF point at 1:1


class ScaleSource(str, Enum):
    """In the order `scale.scale_for_page` tries them."""
    USER_LINE = "user_line"               # a person drew a line over a dimension string („Mastelis" tool)
    DIMENSION_LINES = "dimension_lines"   # dimension strings sitting on their own hairline (plan_dimensions)
    DIMENSION_WALLS = "dimension_walls"   # dimension strings matched to the wall faces they measure
    STATED = "stated"                     # „M 1:50" written on the sheet
    SIBLING = "sibling"                   # another sheet of the set that overlays this one
    BLANK = "blank"                       # nothing to read a scale from — a reason, never a default


# How sure a reading is. high: measured on the sheet by ≥ 2 independent means or by a person;
# medium: one measured source; low: a nominal written scale nothing on the PDF confirms.
HIGH, MEDIUM, LOW = "high", "medium", "low"


@dataclass
class Scale:
    m_per_pt: float | None
    source: ScaleSource
    source_text: str | None = None        # what the sheet / the person wrote: „M 1:50", „4280", „6 strings agree"
    confidence: str | None = None         # HIGH / MEDIUM / LOW; None for a blank
    page_from: int | None = None          # the sheet the scale was read on, when it is not this one
    reason: str | None = None             # why a sheet is blank (or a note on a scale that disagrees)
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def denominator(self) -> int | None:
        """1:N as printed in the chip — the nearest whole number."""
        return int(round(self.m_per_pt / PT_M)) if self.m_per_pt else None

    @property
    def found(self) -> bool:
        return bool(self.m_per_pt)

    def to_dict(self) -> dict:
        out = asdict(self)
        out["source"] = self.source.value
        out["mastelis"] = self.denominator
        if self.m_per_pt:
            out["m_per_pt"] = round(self.m_per_pt, 6)
        return out


def blank(reason: str, **details: Any) -> Scale:
    return Scale(m_per_pt=None, source=ScaleSource.BLANK, reason=reason, details=dict(details))
