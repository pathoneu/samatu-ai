"""rules.rounding — rule R4: every row quantity is rounded ONCE, at the row boundary.

`docs/superpowers/plans/2026-10-24-deterministic-hybrid-plan.md` §1 R4:
m² and m (and m³, l, kg, t) to 0,01 with `Decimal` ROUND_HALF_UP, counts to whole
numbers, material packs up with `ceil`. No rounding inside intermediate math —
rounding early is how estimates drift.

`Decimal(str(x))` reads a float by its shortest repr, so 2.675 (stored as
2.67499…) rounds to 2,68 the way a person reads it, where Python's `round()`
gives 2,67. That is the only kind of difference R4 introduces against the old
`round(x, 2)`: one cent of a unit, on a value that ends in a 5.
"""
from __future__ import annotations

import math
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

__all__ = ["CONTINUOUS_UNITS", "COUNT_UNITS", "round_2", "round_count", "round_pack", "unit_class", "round_qty"]

# Units measured on a continuous scale (rounded to 0,01) vs counted (whole numbers).
CONTINUOUS_UNITS = frozenset({"m2", "m²", "m", "b/m", "m3", "m³", "l", "kg", "t", "val", "d.d.", "d.d"})
COUNT_UNITS = frozenset({"vnt", "vnt.", "kompl", "kompl.", "komp", "komp.", "kmpl", "lapai", "lap.", "maiš.", "pak."})

_CENT = Decimal("0.01")


def _dec(value) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return d if d.is_finite() else None


def round_2(value) -> float | None:
    """0,01 with ROUND_HALF_UP; None stays None (a blank stays blank)."""
    d = _dec(value)
    if d is None:
        return None
    return float(d.quantize(_CENT, rounding=ROUND_HALF_UP))


def round_count(value) -> int | None:
    """A count: the nearest whole number, halves up."""
    d = _dec(value)
    if d is None:
        return None
    return int(d.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def round_pack(value, pack_size: float = 1.0) -> int | None:
    """Material packs: always up to the next whole pack."""
    d = _dec(value)
    if d is None:
        return None
    if pack_size <= 0:
        raise ValueError("pack_size must be positive")
    # a float like 3.0000000001 is three packs, not four
    n = float(round_2(float(d) / pack_size) or 0.0)
    return int(math.ceil(n)) if n > 0 else 0


def unit_class(unit) -> str:
    """'count', 'continuous', or 'unknown' (left as it is)."""
    u = " ".join(str(unit or "").split()).lower()
    if u in COUNT_UNITS:
        return "count"
    if u in CONTINUOUS_UNITS:
        return "continuous"
    return "unknown"


def round_qty(value, unit):
    """The row-boundary rounding for one quantity in its unit.

    Continuous units → 0,01 HALF_UP; counts → whole number HALF_UP; an
    unknown unit → 0,01 HALF_UP as well (never more precision than a cent);
    None → None."""
    if value is None or isinstance(value, bool):
        return value
    if unit_class(unit) == "count":
        return round_count(value)
    return round_2(value)
