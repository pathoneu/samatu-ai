"""extractor.vision — what is left of the Vision readers after v4 Phase 3b (2026-10-25).

The room-geometry passes (dimensions, room graph, adjacency, boxes, niches, elevation zones, symbols, built-ins)
are gone: geometry comes from the drawing's vector paths and text layer (extractor/geometry_lane.py). What stays
are the Pass-1 voting helpers and the readers Phase 3c reduces to text (heights, schedules).
"""

from ._cache import VisionCache, cache_key  # noqa: F401
