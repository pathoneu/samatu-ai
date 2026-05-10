"""Floor-plan (aukšto planas) specialized prompt."""
from .base_system import BASE_RULES

FLOOR_PLAN_PROMPT = BASE_RULES + """

PAGE TYPE: FLOOR PLAN (aukšto planas).

Extract:
- Patalpos: nr, pavadinimas, paskirtis (gyvenamoji|miegamoji|vonia|wc|...),
  plotas_m2 (PREFER eksplikacijos ploto vertę polygon-derived'ui),
  perimetras_m, lubu_aukstis_m, polygon_pct (vidinė kontūra), bbox_pct,
  finish_tags, confidence, evidence_text.
- Angos (openings): id, type ∈ {door, window, hidden_door, opening},
  room_ids (kuriuos kambarius jungia), width_m, height_m,
  hidden_frame (true tik jei labeled "paslėpta" / "nematoma stakta"
  / "D pasl." / explicit legend), swing, bbox_pct, confidence, evidence_text.

DOORS — KAIP ATSKIRTI HIDDEN:
- Jei brėžinys turi durų schedule lentelę — naudok jos `tipas` koloną.
- Jei plane prie durų yra žymos "paslėpta", "nematoma stakta", "D pasl.",
  "hidden frame" → type="hidden_door".
- Jei tik standartinė durų lankomis simbolis — type="door".

NEDARYK:
- Neskaičiuok dažomo ploto / glaisto / hidroizoliacijos.
- Nepriskirk default 0.9 m durų pločio jei matosi tikras matmuo.
- Nemaišyk kambario bendro pločio su sienos storumu.
"""
