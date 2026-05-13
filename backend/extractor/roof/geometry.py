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


from dataclasses import dataclass


@dataclass
class KeturslaitisQuantities:
    """Computed quantities for a hip (keturšlaitis) roof."""
    perdanga_m2: float
    stogas_m2: float
    latakai_m: float
    kraigai_m: float
    ridge_plan_m: float
    hip_plan_per_corner_m: float
    hip_surface_per_corner_m: float
    waste_factor: float


def keturslaitis_quantities(
    *,
    footprint_outer_w: float,
    footprint_outer_l: float,
    eaves_overhang_m: float,
    slope_long_deg: float,
    slope_short_deg: float,
    wall_thickness_m: float = 0.0,
    waste_factor: float = 0.05,
) -> KeturslaitisQuantities:
    """Compute keturšlaitis (4-pitch hip) roof quantities.

    Args:
        footprint_outer_w, footprint_outer_l: outer-wall footprint (m).
        eaves_overhang_m: eaves projection from outer wall face (m).
        slope_long_deg: pitch on the two long slopes (deg).
        slope_short_deg: pitch on the two short (hip) slopes (deg).
        wall_thickness_m: unused here (kept for API symmetry).
        waste_factor: skardos cuts/overlap allowance (default 5%).

    Returns:
        KeturslaitisQuantities dataclass.
    """
    # Roof footprint (with eaves) dims
    roof_w = footprint_outer_w + 2 * eaves_overhang_m
    roof_l = footprint_outer_l + 2 * eaves_overhang_m

    # Perdanga = outer-wall footprint
    perdanga_m2 = footprint_outer_w * footprint_outer_l

    # Ridge height above eaves (must be same from both slopes, so use long-slope side)
    ridge_height = (roof_w / 2) * math.tan(math.radians(slope_long_deg))

    # Hip plan run (horizontal distance from corner to ridge endpoint, along long axis)
    # Hip rises ridge_height over hip_plan_run at slope_short_deg
    hip_plan_run = ridge_height / math.tan(math.radians(slope_short_deg))
    ridge_plan_m = roof_l - 2 * hip_plan_run

    # Long faces: 2 trapezoids at slope_long_deg
    long_face_plan_area = ((roof_l + ridge_plan_m) / 2) * (roof_w / 2)
    long_face_surface = long_face_plan_area / math.cos(math.radians(slope_long_deg))

    # Short faces: 2 triangles at slope_short_deg
    short_face_plan_area = 0.5 * roof_w * hip_plan_run
    short_face_surface = short_face_plan_area / math.cos(math.radians(slope_short_deg))

    # Total stogas surface (with waste)
    stogas_no_waste = 2 * long_face_surface + 2 * short_face_surface
    stogas_m2 = stogas_no_waste * (1 + waste_factor)

    # Latakai = full eaves perimeter
    latakai_m = 2 * (roof_w + roof_l)

    # Hip plan length per corner (in plan, from corner of roof to ridge endpoint)
    hip_plan_per_corner = math.sqrt((roof_w / 2) ** 2 + hip_plan_run ** 2)
    # Hip surface length (with rise = ridge_height over hip_plan_per_corner)
    hip_surface_per_corner = math.sqrt(hip_plan_per_corner ** 2 + ridge_height ** 2)

    # Kraigai = top ridge + 4 hip surface lengths
    kraigai_m = ridge_plan_m + 4 * hip_surface_per_corner

    return KeturslaitisQuantities(
        perdanga_m2=perdanga_m2,
        stogas_m2=stogas_m2,
        latakai_m=latakai_m,
        kraigai_m=kraigai_m,
        ridge_plan_m=ridge_plan_m,
        hip_plan_per_corner_m=hip_plan_per_corner,
        hip_surface_per_corner_m=hip_surface_per_corner,
        waste_factor=waste_factor,
    )
