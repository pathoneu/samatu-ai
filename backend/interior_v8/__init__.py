"""
interior_v8 — residual modules kept for active endpoints.

Phase 5 refactor removed the V8/V8 pipeline endpoints and their supporting files.
Only the following remain:
- line_extractor: used by /pdf-lines endpoint
- universal_engine, lt_area_calculator, lt_sanity: reference implementations
  (no active consumers outside this package after Phase 5)
"""

from .line_extractor import (
    extract_lines_for_page,
    extract_lines_all_pages,
)

__all__ = [
    "extract_lines_for_page",
    "extract_lines_all_pages",
]
