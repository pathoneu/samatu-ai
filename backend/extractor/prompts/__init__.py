"""Specialized vision prompts (canonical plan Week 3 Task 3.3).

The legacy `prompt.py` SYSTEM_TEXT mixed instructions for floor plans,
elevations, electrical, etc. into one ~4700-token brief. This package
splits that into one prompt per page type so Opus can focus its attention
budget on the actual primitives that page surfaces.

Routing is performed by `backend.extractor.page_classifier.classify_page`.
"""
from .base_system import BASE_RULES
from .floor_plan import FLOOR_PLAN_PROMPT
from .ceiling_plan import CEILING_PLAN_PROMPT
from .wall_elevation import WALL_ELEVATION_PROMPT
from .electrical import ELECTRICAL_PROMPT
from .plumbing import PLUMBING_PROMPT
from .eksplikacija import EKSPLIKACIJA_PROMPT


PROMPTS_BY_PAGE_TYPE = {
    "floor_plan": FLOOR_PLAN_PROMPT,
    "ceiling_plan": CEILING_PLAN_PROMPT,
    "wall_elevation": WALL_ELEVATION_PROMPT,
    "electrical": ELECTRICAL_PROMPT,
    "plumbing": PLUMBING_PROMPT,
    "eksplikacija": EKSPLIKACIJA_PROMPT,
}

__all__ = [
    "BASE_RULES",
    "FLOOR_PLAN_PROMPT",
    "CEILING_PLAN_PROMPT",
    "WALL_ELEVATION_PROMPT",
    "ELECTRICAL_PROMPT",
    "PLUMBING_PROMPT",
    "EKSPLIKACIJA_PROMPT",
    "PROMPTS_BY_PAGE_TYPE",
]
