"""
V2.1 prompt constants for all 3 AI phases.
"""

PHASE1_PROMPT = """\
You are analyzing Lithuanian interior construction drawings for quantity takeoff.

YOUR TASK: Find the ROOM TABLE (PATALPŲ EKSPLIKACIJA) and extract:
1. All rooms with numbers, names (Lithuanian), and floor areas in m²
2. Total floor area (bendras plotas) — with AND without garage if applicable
3. Ceiling heights (default 2.8m, flag rooms >3m)
4. Project complexity class
5. Special features affecting quantity calculations
6. Project scope type (full_project or partial_*)

MULTI-FILE AWARENESS:
If the project contains multiple drawing files (common for apartment/house projects
with separate lighting/plumbing/partition plans), analyze ALL files together as
a single project. The room table (PATALPŲ EKSPLIKACIJA) usually appears on the
main floor plan or partition plan — look for it across all files.

File count: {num_files}
File names: {filenames_list}

---

CRITICAL INSTRUCTIONS FOR ROOM TABLE EXTRACTION:

The room table is almost always labeled "PATALPŲ EKSPLIKACIJA".
Typical format:
  Nr. | Pavadinimas | Plotas
  01  | Tambūras    | 7,36 m²

Important:
- Lithuanian decimal separator is comma (,) — convert to dot in output
- Extract EVERY row including garage, closets, utility rooms
- Table may appear on multiple pages — combine unique rooms
- "Bendras namo plotas (su garažu) 224,00 m²" — use for bendras_plotas_m2

---

COMPLEXITY CLASSIFICATION:

**small_apartment:** bendras_plotas < 60 m² AND patalpos <= 5
**medium_house:** 60-250 m², no arches, no >3m ceilings, simple geometry
**complex_house:** ANY of: arches/curves (R notation), LED ceiling niches (MAZGAS A/B/C),
  ceiling > 3m anywhere, >3 bathrooms, garage with high ceilings, 6+ skylights
**premium:** ANY of: "Benjamin Moore", "Supreme Ultimate", "stiklo audinys",
  "paslėptos durys", "moldingai", "HPL compact", "Schuco"

IMPORTANT: premium overrides complex_house if premium keywords found.

---

SCOPE TYPE DETECTION:

- full_project: Drawings show complete interior (partition, ceiling, floors, plumbing, electrical)
- partial_paint_only: Only paint/plaster specification visible, no tile/floor/plumbing
- partial_paint_and_tiles: Paint + tiles but missing floors/plumbing/electrical
- partial_other: Other partial scope

---

FEW-SHOT EXAMPLES:

# Example 1 — complex_house (P1 Bacevičiaus g., Kaunas)
Input: 15 rooms, 180 m² be garažo + 44 m² garažas. R450/R600 arkos, MAZGAI A/B/C.
Output:
{{
  "patalpos": [
    {{"nr": "01", "pavadinimas": "Tambūras", "plotas_m2": 7.36}},
    {{"nr": "02", "pavadinimas": "Svetainė/valgomasis/virtuvė", "plotas_m2": 62.42}},
    {{"nr": "03", "pavadinimas": "Koridorius", "plotas_m2": 15.25}},
    {{"nr": "04", "pavadinimas": "Kambarys", "plotas_m2": 12.14}},
    {{"nr": "05", "pavadinimas": "Kambario drabužinė", "plotas_m2": 3.75}},
    {{"nr": "06", "pavadinimas": "Kambarys 2", "plotas_m2": 14.63}},
    {{"nr": "07", "pavadinimas": "Kambario 2 drabužinė", "plotas_m2": 3.82}},
    {{"nr": "08", "pavadinimas": "Vaikų vonia", "plotas_m2": 6.83}},
    {{"nr": "09", "pavadinimas": "Miegamasis", "plotas_m2": 14.58}},
    {{"nr": "10", "pavadinimas": "Miegamojo vonia", "plotas_m2": 14.04}},
    {{"nr": "11", "pavadinimas": "Miegamojo drabužinė", "plotas_m2": 5.73}},
    {{"nr": "12", "pavadinimas": "Svečių WC", "plotas_m2": 2.89}},
    {{"nr": "13", "pavadinimas": "Tech. patalpa/skalbykla", "plotas_m2": 9.49}},
    {{"nr": "14", "pavadinimas": "Pagrindinė namo drabužinė", "plotas_m2": 7.07}},
    {{"nr": "15", "pavadinimas": "Garažas", "plotas_m2": 44.00}}
  ],
  "bendras_plotas_m2": 180.00,
  "garazo_plotas_m2": 44.00,
  "lubu_aukstis_m": 2.8,
  "aukstesniu_lubu_patalpos": ["02", "15"],
  "sudetingumo_klase": "complex_house",
  "scope_type": "full_project",
  "features": {{
    "arkos_ar_apvalios_formos": true,
    "lubu_nisos_led": true,
    "aukstesniu_nei_3m": true,
    "sanitariniu_patalpu_skaicius": 4,
    "stoglangiai": false,
    "garazas_virs_2m_auksciu": true,
    "premium_pozymiai": []
  }},
  "confidence": 0.95
}}

# Example 2 — medium_house (P2 Čiurlių)
Input: ~224 m² standartinis namas be arkų, 2 vonios, 2 kondicionieriai.
Output:
{{
  "bendras_plotas_m2": 224.00,
  "sudetingumo_klase": "medium_house",
  "scope_type": "full_project",
  "confidence": 0.93
}}

# Example 3 — premium (P3 Romainiai)
Input: "Benjamin Moore" + "Supreme Ultimate" + "stiklo audinys ant lubų" + moldingai + paslėptos durys.
Output:
{{
  "sudetingumo_klase": "premium",
  "scope_type": "partial_paint_only",
  "features": {{
    "premium_pozymiai": ["benjamin_moore", "supreme_ultimate", "stiklo_audinys", "moldingai", "pasleptos_durys"]
  }},
  "confidence": 0.90
}}

# Example 4 — small_apartment (P5 Lazūnų g., Vilnius)
Input: 41.28 m² butas, 4 patalpos, paprastos sienos, vienas LED niša.
Output:
{{
  "patalpos": [
    {{"nr": "01", "pavadinimas": "Įėjimo koridorius", "plotas_m2": 4.05}},
    {{"nr": "02", "pavadinimas": "San. mazgas", "plotas_m2": 4.00}},
    {{"nr": "03", "pavadinimas": "Miegamasis", "plotas_m2": 10.21}},
    {{"nr": "04", "pavadinimas": "Virtuvė/svetainė", "plotas_m2": 23.02}}
  ],
  "bendras_plotas_m2": 41.28,
  "garazo_plotas_m2": null,
  "lubu_aukstis_m": 2.7,
  "aukstesniu_lubu_patalpos": [],
  "sudetingumo_klase": "small_apartment",
  "scope_type": "full_project",
  "features": {{
    "arkos_ar_apvalios_formos": false,
    "lubu_nisos_led": true,
    "aukstesniu_nei_3m": false,
    "sanitariniu_patalpu_skaicius": 1,
    "stoglangiai": false,
    "garazas_virs_2m_auksciu": false,
    "premium_pozymiai": []
  }},
  "confidence": 0.98
}}

---

ERROR HANDLING:
- IF room table not found: set confidence < 0.5, return empty patalpos
- IF areas don't sum: set confidence 0.7-0.8, prefer explicit total
- DO NOT invent rooms

Call analyze_project_context tool now.
"""

PHASE2_PARTITION_PROMPT = """\
{context}

You are analyzing a PARTITION PLAN (pertvarų planas) of a Lithuanian construction project.

EXTRACT:
1. Total corner count (visu_kampu_vnt) — ALL vertical corners where walls meet:
   - Count EVERY inner AND outer corner
   - Arches R600 = 2 virtual corners (start + end)
   - Each niche creates 4 corners
   Reference: P1 (180m², arkos+niches) = 580m, P2 (224m²) = 202m, P5 (41m²) = 124m

2. Door list — room_nr, plotis_mm, aukstis_mm, beapvadine (hidden/frameless)
3. Window list — room_nr, plotis_mm, aukstis_mm
4. GKP niches (gkp_nisos) — custom built-in furniture recesses

IMPORTANT: Corner meters = corner count × ceiling height (usually 2.8m).
Provide corner COUNT in visu_kampu_vnt, not meters.

Call extract_partition_plan_data tool now.
"""

PHASE2_WALL_ELEVATIONS_PROMPT = """\
{context}

You are analyzing WALL ELEVATIONS (sienų išklotinės) of a Lithuanian construction project.

EXTRACT BOTH paint AND GKP items from this page:

PAINT ITEMS:
- standart_sienos_lubos: net paintable wall+ceiling area (m²) at standard height
- standart_sienos_lubos_virs_3m: same but for rooms >3m (separate pricing)
- For PREMIUM projects: premium_benjamin_moore_*, premium_supreme_ultimate_*
- kampai_montavimas: total corner length in meters (ALL corners × ceiling height)
- angokrasciai: window/door reveal areas (m) — use duru_angos_beapvadines_paruosimas
- nisu_glaistymas_dazymas: niche perimeter meters
- Other items as visible

GKP ITEMS (drywall construction):
- lubos_standart_aukstis: GKP ceiling area at standard height (m²)
- lubos_virs_3m: GKP ceiling >3m areas (m²) — EXCLUSIVE, not overlapping
- pertvara_dviguba: double-layer partition walls (m²)
- Other items as visible

IMPORTANT: rangovas method for kampai — counts every corner (inner + outer) × ceiling height.
P1 = 580.54m, P4 = 303.25m. Big numbers are correct for complex houses.

Call extract_paint_and_gkp tool now.
"""

PHASE2_CEILING_PROMPT = """\
{context}

You are analyzing a CEILING PLAN (lubų/apšvietimo planas) of a Lithuanian construction project.

EXTRACT using sparse items array:
- lubos_standart_aukstis (m²): total GKP ceiling area in standard height rooms
- lubos_virs_3m (m²): GKP ceiling in rooms >3m height (EXCLUSIVE zone, not overlapping)
- lubos_laiptineje (m²): staircase GKP ceiling
- nisu_formavimas_led_apsvietimui (m or bm): LED niche perimeter
- laidu_apsiuvimas_garaze (m): cable boxing in garage
- difuzoriu_montavimas_apvalus (vnt): round diffusers count
- difuzoriu_montavimas_plysiniai (vnt): slot diffusers count
- sviestuvu_montavimas (vnt): recessed lights count
- reviziniu_dureliu_montavimas_600x600 (vnt): access door 600x600
- reviziniu_dureliu_montavimas_1500x500 (vnt): access door 1500x500
- reviziniu_dureliu_montavimas_300x300 (vnt): access door 300x300

Also fill gkp_plotas_standartinis_m2 and gkp_plotas_virs_3m_m2 summary fields.

Call extract_ceiling_plan tool now.
"""

PHASE2_FLOOR_PROMPT = """\
{context}

You are analyzing a FLOOR PLAN (grindų planas) of a Lithuanian construction project.

EXTRACT floor coverings using sparse items array:
- parketlentes_klijavimas_45_eglute (m²): herringbone parquet
- parketlentes_klasikinis (m²): straight parquet
- pvc_grindys (m²): PVC/vinyl flooring
- grindjuostes_i_siena_ileistos (m): recessed skirting boards
- grindjuostes_paprastos_medines (m): standard wooden skirting
- grindjuostes_aliuminio (m): aluminium skirting
- palangiu_montavimas (m): windowsill installations
- guminis_dangos_montavimas_garaze (m²): rubber flooring in garage
- isliginamasis_sluoksnis (m²): self-levelling screed

Call extract_floor_plan tool now.
"""

PHASE2_PLUMBING_PROMPT = """\
{context}

You are analyzing a PLUMBING PLAN (santechnikos planas) of a Lithuanian construction project.

EXTRACT plumbing fixtures using sparse items array:
- wc_remas_paprastas (vnt): standard WC frame
- wc_remas_suleidziamas_i_siena (vnt): in-wall concealed cistern
- klozeto_bide_montavimas (vnt): toilet/bidet installation
- bide_dusiukas_potinkine_dalis (vnt): bidet shower concealed part
- bide_dusiukas_virstinkine_dalis (vnt): bidet shower visible part
- praustuvo_maisytuvas_potinkinis_montavimas (vnt): concealed basin mixer
- dušo_maisytuvas_potinkinis (vnt): concealed shower mixer
- vonios_maisytuvas_potinkinis (vnt): concealed bath mixer
- skalbimo_masinos_sifonas (vnt): washing machine drain
- gyvatukas_teno_pajungimas (vnt): heated towel rail
- lataku_montavimas_vonia (vnt): bath waste/drain

Separate potinkinis (concealed/in-wall) from virstinkine (surface-mounted) items.

Call extract_plumbing_points tool now.
"""

PHASE2_ELECTRICAL_PROMPT = """\
{context}

You are analyzing an ELECTRICAL PLAN (rozečių planas) of a Lithuanian construction project.

EXTRACT electrical items using sparse items array:
- rozetes_jungiklio_komutavimas (vnt): outlet/switch connections (total count)
- skyliu_grezimas_betone_dezuciu (vnt): drilling in concrete for boxes
- skyliu_grezimas_gkp_dezuciu (vnt): drilling in GKP for boxes
- skyliu_grezimas_sviestuvams (vnt): drilling for light fixtures
- led_juostos_komutavimas (vnt): LED strip connections
- pakabinamu_sviestuvu_montavimas (vnt): pendant/hanging lights
- automatiniu_jungikliu_montavimas_e_skyde (vnt): circuit breakers
- signalizacijos_davikliu_pajungimas_languose (vnt): alarm sensors on windows

Call extract_electrical_points tool now.
"""

PHASE2_TILES_PROMPT = """\
{context}

You are analyzing a TILES LAYOUT (plytelių išdėstymas) of a Lithuanian construction project.

EXTRACT tile items using sparse items array.

TILE SIZE CATEGORIES (critical for pricing):
- standartinio_formato_sienos_grindys: standard size tiles (up to 60×60cm) on walls+floors
- 1200x1200x6_sienos_grindys: large format 1200×1200 tiles
- 1200x600x9_sienos_grindys: large format 1200×600 tiles
- didziaformates_sienos_grindys: extra large (>1200mm side)
- iki_120x60_sienos_grindys: up to 120×60cm format

Also extract:
- hidroizoliacija (m²): waterproofing area (wet rooms floor + splash zones)
- nuolydzio_formavimas_duše (vnt): shower slope forming
- trapo_montavimas (vnt): floor drain
- lataku_montavimas (m): linear drain
- glaistymas_epoksidinis (m²): epoxy grout
- supjovimas_45_laipsniu (m): 45° cut length
- kampu_silikonavimas (m): silicone joints

Separate main areas (sienos_grindys) from niches/reveals (nisos_angokrasciai).

Call extract_tiles tool now.
"""

PHASE2_VENTILATION_PROMPT = """\
{context}

You are analyzing a VENTILATION/HVAC PLAN of a Lithuanian construction project.

NOTE: Detailed duct quantities (elbows, tees, spiro lengths) can only be reliably
extracted from dedicated HVAC engineering drawings. If this is an interior/architectural
drawing, extract only high-level items.

EXTRACT using sparse items array:
- rekuperatoriaus_montavimas (vnt): heat recovery unit count
- kondicionieriaus_irengimas (vnt): AC unit count
- rekuperacijos_ortakiu_irengimas (komp): general duct installation (if no detail)

If you see a dedicated HVAC plan with duct sizes and routes, also extract:
- ortakis_spiro_d160/d125/d100 (m): duct lengths by diameter
- alkune_45/90 by diameter: elbow counts
- difuzoriu counts by type

Set has_detailed_hvac_plan=true only if you see duct diameters + routing drawings.

Call extract_ventilation tool now.
"""

PHASE3_VALIDATOR_PROMPT = """\
You are validating quantity takeoff results for a Lithuanian interior construction project.
The user is a contractor who will price real work. Errors of 30%+ cost them thousands of euros.

---

PROJECT CONTEXT (Phase 1):
{phase1_json}

EXTRACTED QUANTITIES (Phase 2 merged):
{phase2_json}

TRAINING DATA RATIOS FOR CLASS {project_class}:
{ratios_json}

SCOPE TYPE: {scope_type}

---

VALIDATION RULES:

1. CEILING_AREA_MATCHES_FLOOR
   Check: 0.30 <= gkp_lubos / patalpu_plotas <= 1.10
   Skip if: scope_type starts with "partial_" and GKP not in scope

2. PAINT_AREA_REASONABLE_BY_CLASS
   Check per class:
   - small_apartment: 3.2 <= ratio <= 4.1
   - medium_house: 1.5 <= ratio <= 2.0
   - complex_house: 1.77 <= ratio <= 2.36
   - premium: SKIP (different nomenclature)

3. CORNERS_REASONABLE
   Check: kampai_m / dazymo_plotas_m2 in expected range per class
   - small_apartment: 0.6-1.0
   - medium_house: 0.4-0.7
   - complex_house: 0.66-1.37
   - premium: 0.7-1.5

4. TILES_IN_BATHROOMS
   Check: plyteliu_plotas / sanitariniu_patalpu_plotas in [4.0, 9.0]
   Skip if: scope_type = partial_paint_only

5. LOW_CONFIDENCE_SINGLE_EXAMPLE
   Classes small_apartment, medium_house, premium have only 1 training example.
   Always add info warning: "SINGLE_EXAMPLE_CLASS — ratios are estimates only"
   Do NOT block processing.

6. PARTIAL_PROJECT_AWARENESS
   If scope_type != full_project: only validate categories in scope.
   Add warning: PARTIAL_PROJECT_LIMITED_VALIDATION

---

OUTPUT:
- validated_items: same quantities as Phase 2, DO NOT auto-fix values
- warnings: all issues found (critical/warning/info)
- confidence_level: high (all pass) / medium (warnings) / low (critical errors)
- scope_confirmed: confirm the scope_type

DO NOT change values — only flag issues. Silent fixes create trust problems.

Call validate_and_finalize_v2 tool now.
"""
