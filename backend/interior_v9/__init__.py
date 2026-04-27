"""
V9 symbol detector — used by /v9/symbols/detect and /v9/symbols/count-by-template.

Pipeline files (pipeline_v9, som_renderer, vision_classifier) were removed in Phase 5
refactor. Only symbol_detector and vector_polygons remain.
"""
from .symbol_detector import (
    detect_symbols,
    detect_symbols_bundled,
    detect_all_symbols_for_pdf,
    count_symbols_by_template,
    list_symbol_types_for_page_type,
    SYMBOL_TYPES,
)
from .vector_polygons import build_room_polygons

__all__ = [
    "build_room_polygons",
    "detect_symbols",
    "detect_symbols_bundled",
    "detect_all_symbols_for_pdf",
    "count_symbols_by_template",
    "list_symbol_types_for_page_type",
    "SYMBOL_TYPES",
]
