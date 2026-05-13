"""Electrical (rozečių/apšvietimo planas) specialized prompt."""
from .base_system import BASE_RULES

ELECTRICAL_PROMPT = BASE_RULES + """

PAGE TYPE: ELECTRICAL (rozečių / apšvietimo planas).

Naudok PROJECT LEGEND (žemiau, jei pateikta). NESPĖK simbolio reikšmės iš
spalvos ar formos, jei jos nėra legendoje.

Extract detected_symbols_summary:
{
  "rozetes": int, "jungikliai": int, "sviestuvai": int,
  "pakabinami_sviestuvai": int, "led_juostos_m": number,
  "difuzoriai": int, "kondicionieriai": int,
  "ortakiai_d100_m": number, "ortakiai_d125_m": number, "ortakiai_d160_m": number
}

PLUS sąrašas unknown_symbols, kurių legendoje neaptikai:
[
  {"description": "small blue triangle", "count": 4, "bbox_examples": [...]},
  ...
]
Tai leidžia vartotojui frontend'e priskirti reikšmę ir re-trigger'inti recompute.
"""
