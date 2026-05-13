"""Pure-function roof geometry math. No PDF, no Vision, no I/O.

All public functions are pure and deterministic. See
docs/superpowers/research/2026-05-13-stogai-v1-research-stogo-math.md
for formulas + LT statybų reglamentų references.
"""
import math


def slope_factor(angle_deg: float) -> float:
    """Area ratio: sloped surface area / plan-view area.

    Formula: 1 / cos(angle). For a roof at angle α from horizontal,
    1 m² of plan footprint corresponds to slope_factor m² of actual
    sloped surface to cover.

    Args:
        angle_deg: roof slope angle in degrees, 0 ≤ angle < 90.

    Returns:
        Multiplier ≥ 1.0. Flat roof = 1.0, 45° = 1.414, etc.

    Raises:
        ValueError: if angle_deg outside [0, 90).
    """
    if not (0 <= angle_deg < 90):
        raise ValueError(f"angle_deg must be in [0, 90), got {angle_deg}")
    return 1.0 / math.cos(math.radians(angle_deg))
