"""Plumbing (santechnikos planas) specialized prompt."""
from .base_system import BASE_RULES

PLUMBING_PROMPT = BASE_RULES + """

PAGE TYPE: PLUMBING (santechnikos planas).

Extract:
- klozetai (int), praustuves (int — TIK vonios/WC/san. mazgo praustuvai),
  plautuves (int — virtuvės/skalbyklos kriauklės; atskira sąmatos eilutė,
  niekada neįskaitoma į praustuves), vonios (int), dušai (int),
  trapai (int — floor drains), wc_remai (int — concealed cisterns),
  gyvatukai (int — towel radiators), radiatoriai (int).
- boileris/katilas: tipas, location bbox.
- vamzdžių linijos (jei matomos kaip kontūrai): polyline_pct, dimensija_mm.
- hydro_zones: surface, area_m2 — drėgnos zonos pažymėtos brėžinyje.

Priskink fixtures kambariams pagal fixture bbox vs kambario polygon.
"""
