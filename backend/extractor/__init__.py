"""extractor — vienas Vision call'as, vienas struktūruotas takeoff JSON.

Architektūra (po Phase 1 baseline validation 2026-04-26):
    PDF bytes → pdf_to_b64_images → call_vision (Opus 4.7, effort=high,
    cached system prompt, streaming) → parse JSON (with repair fallback)
    → recompute santrauka via calc_totals → apply_lt_sanity (warnings only)
    → apply user overrides → return.
"""

from .vision_call import extract_interior  # noqa: F401
from .stream import extract_interior_stream  # noqa: F401
from .eksplikacija_reader import read_eksplikacija  # noqa: F401
from .plyteliu_specifikacija import extract_plyteliu_specifikacija  # noqa: F401
from .cross_page_validator import validate_consistency  # noqa: F401
from .wall_elevation import extract_wall_elevations  # noqa: F401
