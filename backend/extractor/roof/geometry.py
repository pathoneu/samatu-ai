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


def hip_valley_factor(angle_deg: float) -> float:
    """Length ratio: 3D hip/valley length / plan-projected length.

    Hips and valleys travel diagonally on a sloped roof. Their 3D length
    on the roof surface is longer than the plan-projected diagonal because
    they rise as they travel inward.

    Formula: √(sec²α + 1), where α = slope angle of the adjacent slopes
    (assuming 90° plan-angle between intersecting slopes).

    Args:
        angle_deg: slope angle of the planes meeting at this hip/valley.

    Returns:
        Multiplier > 1.0. At 30° slope = 1.528, at 45° = 1.732.

    Raises:
        ValueError: if angle_deg outside [0, 90).
    """
    if not (0 <= angle_deg < 90):
        raise ValueError(f"angle_deg must be in [0, 90), got {angle_deg}")
    sec_a = 1.0 / math.cos(math.radians(angle_deg))
    return math.sqrt(sec_a ** 2 + 1)
