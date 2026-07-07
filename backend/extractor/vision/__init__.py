"""extractor.vision — multi-pass deterministic Vision pipeline.

Phase 2 architecture:
  dimension_extractor → list[Dimension]
  room_graph_extractor(image, dimensions) → RoomGraph
  plan_assembler(dimensions, room_graph) → Plan          (no LLM)
  geometry_solver(plan) → Plan                            (no LLM)

The output Plan is converted to the existing ``parsed`` schema (patalpos[])
so the downstream formula engine (`_recompute_per_room_via_python` +
`_recompute_santrauka`) stays unchanged.
"""

from ._cache import VisionCache, cache_key  # noqa: F401
