"""Sprint 0 Fix 3 + Week 2 Task 2.4: verify drawing scale.

Two complementary checks:
  1. `validate_scale` (original): compare claimed scale × room diagonal against
     measured pixel diagonal. Requires Vision to populate `diagonal_px`, which
     it doesn't yet — so this remained dormant until Vision pass adds it.
  2. `validate_scale_by_doors` (Week 2): cross-check claimed `px_per_m` against
     the median pixel width of detected doors, assuming standard interior
     door = 0.9 m. Catches the 4× scale-mismatch failure mode (1:100 re-exported
     and labeled "M 1:50") even when `diagonal_px` is missing.

See docs/superpowers/specs/2026-05-03-takeoff-workspace-design.md §7 Fix 3
and docs/superpowers/plans/2026-05-10-canonical-plan.md Task 2.4.
"""
from dataclasses import dataclass
from statistics import median
import math
import re

# 1 inch = 25.4 mm
_MM_PER_INCH = 25.4
# Tolerance: warn if measured diagonal differs from expected by >5%
_TOLERANCE_PCT = 0.05


class ScaleMismatch(Exception):
    """Raised when scale validation fails hard (currently warnings-only)."""
    pass


@dataclass(frozen=True)
class ScaleValidationResult:
    """Outcome of a scale check.

    severity:
      green  — within ±15% of expected (valid).
      yellow — 0.5×–2× off (suspicious, likely mis-classification).
      red    — >2× or <0.5× off (almost certainly the wrong scale).
    """
    valid: bool
    severity: str
    factor: float | None
    message: str


_SCALE_RE = re.compile(r"(?:M|Mastelis)?\s*1\s*:\s*(\d+)", re.IGNORECASE)


def parse_scale_string(s: str | None) -> float | None:
    """Extract numeric scale factor from a title-block string.

    Handles 'M 1:50', 'Mastelis 1:100', '1:200', 'M 1 : 75'.
    Returns None when no scale annotation found.
    """
    if not s:
        return None
    m = _SCALE_RE.search(s)
    return float(m.group(1)) if m else None


def expected_diagonal_px(width_m: float, height_m: float,
                         scale_factor: float, rendered_dpi: int) -> float:
    """How many pixels the room diagonal should occupy in the rendered page."""
    diag_m = math.hypot(width_m, height_m)
    diag_mm = diag_m * 1000.0
    page_mm = diag_mm / scale_factor
    return page_mm * rendered_dpi / _MM_PER_INCH


def validate_scale(scale_factor: float, rendered_dpi: int,
                   rooms: list[dict]) -> list[str]:
    """Return human-readable warnings for any room whose measured diagonal
    differs from expected by more than 5%.

    Each room dict needs: width_m, height_m, diagonal_px (from Vision).
    Rooms missing any of these fields are silently skipped — Vision does not
    currently populate diagonal_px, so this function is a no-op until the
    Vision prompt is extended to return pixel bounding-box dimensions.
    """
    warnings: list[str] = []
    for room in rooms:
        w = float(room.get("width_m") or 0)
        h = float(room.get("height_m") or 0)
        actual = float(room.get("diagonal_px") or 0)
        if w <= 0 or h <= 0 or actual <= 0:
            continue
        expected = expected_diagonal_px(w, h, scale_factor, rendered_dpi)
        deviation = abs(actual - expected) / expected
        if deviation > _TOLERANCE_PCT:
            ratio = actual / expected
            warnings.append(
                f"Mastelis (scale) nesutampa patalpoje '{room.get('name', '?')}': "
                f"matavimas rodo ~{ratio:.2f}× nuo deklaruoto {int(scale_factor)} "
                f"(nukrypimas {deviation*100:.1f}%). Patikrink M 1:{int(scale_factor)}."
            )
    return warnings


def validate_scale_by_doors(
    door_pixel_widths: list[float],
    claimed_px_per_m: float,
    expected_door_width_m: float = 0.9,
) -> ScaleValidationResult:
    """Door-as-ruler scale check (Week 2 Task 2.4).

    Standard LT interior door is 0.9 m. Given a list of detected door pixel
    widths and the claimed pixels-per-metre, compute the implied door width
    and compare to the expected. Use the median to dodge a single mis-detected
    door spike.

    No-op (yellow) when no doors found — Vision lacks a ruler this run.
    """
    if not door_pixel_widths or claimed_px_per_m <= 0:
        return ScaleValidationResult(
            valid=False, severity="yellow", factor=None,
            message="No door ruler available — scale cannot be cross-checked.",
        )
    median_px = median(door_pixel_widths)
    implied_width_m = median_px / claimed_px_per_m
    factor = implied_width_m / expected_door_width_m
    if 0.85 <= factor <= 1.15:
        return ScaleValidationResult(
            valid=True, severity="green", factor=factor,
            message=f"Scale matches door ruler (factor {factor:.2f}).",
        )
    severity = "red" if (factor < 0.5 or factor > 2.0) else "yellow"
    return ScaleValidationResult(
        valid=False, severity=severity, factor=factor,
        message=(
            f"Scale mismatch: implied door width {implied_width_m:.2f} m "
            f"vs expected {expected_door_width_m:.2f} m (factor {factor:.2f}). "
            f"Patikrink ar PDF deklaruotas mastelis sutampa su tikrove."
        ),
    )
