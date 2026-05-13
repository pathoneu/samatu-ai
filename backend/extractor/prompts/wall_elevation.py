"""Wall-elevation (sienų išklotinė) specialized prompt."""
from .base_system import BASE_RULES

WALL_ELEVATION_PROMPT = BASE_RULES + """

PAGE TYPE: WALL ELEVATION (sienų išklotinė).

Extract per sieną:
- room_id_hint (jei labeled), wall_label (A/B/C/D arba nr).
- tile_zones: surface=wall, width_m, height_m, area_m2, bottom_height_m,
  top_height_m, material_label, miter_45_lm, edge_profile_lm, silicone_lm,
  bbox_pct.
- hydro_zones: surface, area_m2 (jei sienos pora aiškiai pažymėta hidro).
- openings: width_m, height_m, sill_m (palangė).
- niches (nišos): bottom_height_m, top_height_m, width_m, depth_m.

KRITIŠKAS PRIORITETAS:
- IŠKLOTINĖ override'ina aukšto plano default plytelių zoną — jei matosi
  konkretus aukštis/plotis išklotinėje, naudok JĮ, ne `perim × default_height`.
- 45° suleidimą atpažink iš žymos "45°", "kampas 45", "mitre" etc. ir grąžink
  miter_45_lm. Jei nepažymėta — palik 0 (Python NEgenkles defaultu).
- Silikoną grąžink tik jei aiškiai pažymėtas ar matomas siūlių brėžinyje.
"""
