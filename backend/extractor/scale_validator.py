"""Sprint 0 Fix 3: verify the scale claimed in title block matches
the actual rendered page dimensions.

Catches user uploads of wrong-scale copies (e.g., 1:100 PDF re-exported
and labeled "M 1:50") which would otherwise produce 4× systematic errors
in every quantity.

See docs/superpowers/specs/2026-05-03-takeoff-workspace-design.md §7 Fix 3.
"""
import math
import re

# 1 inch = 25.4 mm
_MM_PER_INCH = 25.4
# Tolerance: warn if measured diagonal differs from expected by >5%
_TOLERANCE_PCT = 0.05


class ScaleMismatch(Exception):
    """Raised when scale validation fails hard (currently warnings-only)."""
    pass


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
