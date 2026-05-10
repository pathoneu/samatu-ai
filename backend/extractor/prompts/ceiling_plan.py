"""Ceiling-plan (lubų planas) specialized prompt."""
from .base_system import BASE_RULES

CEILING_PLAN_PROMPT = BASE_RULES + """

PAGE TYPE: CEILING PLAN (lubų planas).

Extract:
- ceiling_zones per kambarį: finish ∈ {gkp, paint, stretch, unknown},
  area_m2, height_m, level_change_m (pvz. +2.800), polygon_pct, confidence.
- linear_elements: type ∈ {led_profile, shadow_gap, curtain_box, unknown},
  length_m, polyline_pct, legend_key (kuri legendos eilutė atitinka),
  confidence.
- symbols (lubinis apšvietimas): naudok PROJECT LEGEND. Jei legendoje
  spalvos/simbolio nerasi → return type="unknown_symbol" with bbox + RGB.

LEVEL CHANGES:
- Jei kambario lubų aukštis > 3.0 m, pažymėk level_change_m kad downstream
  Python paimtų jį į `lubos_virs_3m_m2` line item (R4: scaffolding adder).
"""
