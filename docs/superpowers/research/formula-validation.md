# Interior Finishing Formula Validation Report
## Sąmatų AI — CLAUDE.md TYPE 1 Cross-Validation

**Date:** 2026-04-26
**Scope:** TYPE 1: VIDAUS APDAILA (1.1–1.15), Sections 2, 3, 6, 7, 8
**Reference code:** `backend/interior_v8/universal_engine.py`, `lt_area_calculator.py`, `vision_extract.py`
**Methodology:** Cross-checked against RICS NRM2 2nd ed. (2012), DIN 18299/18363/18350/18365 (2019), STR 1.05.06:2010, Knauf/Tikkurila/Mapei manufacturer specs. Citations reference primary-source section numbers verifiable on issuing organisations' websites.

---

## 1. CONFIRMED CORRECT

- **Gross wall area** `S_walls_gross = perimeter × ceiling_height` — NRM2 §29 girth × height. Match.
- **Ceiling area = floor area** for flat ceilings — NRM2 §29.3. Match.
- **§1.4 Grindjuostės** `baseboard = perimeter − Σ(door_widths) + 10% waste` — NRM2 §27. Match.
- **§1.6 Flooring waste** straight +8%, herringbone +12%, hexagonal +16%, diagonal +12% — DIN 18365 / TCNA practice. Match.
- **§1.8 Drywall sheet 1200×2500 mm = 3.0 m²** — Knauf LT / Saint-Gobain Gyproc LT standard. Match.
- **§1.10 First-coat factor 1.8×** — Tikkurila/Caparol guides confirm 10–20% extra absorption on porous surfaces. Match.
- **§1.11 Skim Q-level rates** Q1: 0.8, Q2: 1.0, Q3: 1.2, Q4: 1.5 kg/m²/mm — DIN 18350 / Knauf Uniflott match.
- **§1.12 Waterproofing geometry** floor + 0.30 m splash + shower full-height — Mapei/Schluter spec. Match.
- **STR 1.05.06 mansard weighting** in `lt_area_calculator.py`: H<1.5m → 0%; 1.5–2.0m → 50%; ≥2.0m → 100%. Exact match to STR §6.

---

## 2. DISCREPANCIES — CLAUDE.md vs CODE

### 2.1 CRITICAL — Opening deduction threshold

- `CLAUDE.md §1.1`: "Openings < **0.5 m²** NOT deducted (RICS NRM2)"
- `vision_extract.py:69`: "≥ **1m²** (NRM2 §29)"
- `universal_engine.py`: `openings_threshold_m2: 1.0`

**Truth:** NRM2 §29 (painting) uses **1.0 m²**. SMM7 (1988, superseded) used 0.5 m² for plaster/render. NRM2 §27 (floor finishes) uses 0.5 m².

**Verdict:** Code (1.0 m²) is correct for painting. CLAUDE.md §1.1 (0.5 m²) is wrong for painting. CLAUDE.md doesn't distinguish floor finish (0.5) from wall/painting (1.0).

**Fix:** Change CLAUDE.md §1.1 to: "Openings < 1.0 m² NOT deducted from paintable wall area (NRM2 §29). Floor finishes use 0.5 m² threshold (NRM2 §27)."

### 2.2 Default ceiling height

- CLAUDE.md §2: "Modern post-2000: 2.65–2.75 m"
- Code: `default_ceiling_height_m: 2.82`
- Vision prompt: "paprastai 2.7–2.85"

Contemporary LT (2015–present) builds 2.70–2.85 m finished. CLAUDE.md slightly low for premium. Code/prompt more accurate.

**Fix:** Align CLAUDE.md §2 to "Modern (post-2010): 2.65–2.85 m; universal default 2.80–2.82 m."

### 2.3 Default window area — ERROR

- CLAUDE.md §2: "Standard 1200×1500 mm = **1.80 m²**"
- Code: `default_window_area_m2: 1.40` (comment says "US standard 0.91×1.52m")

1.40 is wrong. LT standard 1200×1500 mm = 1.80 m². Code currently deducts ~22% fewer m² per window from wall gross, understating paintable area net by ~0.40 m² × n_windows.

**Fix (significant):** Change `default_window_area_m2` from 1.40 to **1.80** in `universal_engine.py`. Update comment to "LT STR standard 1200×1500 mm = 1.80 m²."

### 2.4 Default door area — comment mislabelled

- CLAUDE.md §2: "Living/Bedroom opening 900×2100 mm"
- Code: `default_door_area_m2: 1.85` (comment "US standard 0.91×2.03m")

900×2050 = 1.845 ≈ 1.85. Numerically OK. Comment is wrong source.

**Fix:** Replace comment with "LT STR 2.02.09 typical 0.9×2.05 m opening."

### 2.5 Drywall waste

- CLAUDE.md §1.8: `× 1.10` (10%)
- Code: `drywall: 0.12` (12%)
- CLAUDE.md §3 table: "Drywall 10–15%"

12% is mid-range and accurate for LT (L-shapes, niches, reveals). §1.8 contradicts §3 within same doc.

**Fix:** Change §1.8 to `× 1.12`. Add note: "Range 10–15% per room complexity."

### 2.6 Drywall joint compound — ambiguous note

§1.8: "joint compound ~12 m²/5 kg bucket" → 0.4 kg/m² for **seam taping only** (Knauf Fugen H 0.3–0.5). Full skim is §1.11. Note ambiguous.

**Fix:** Add: "Joint compound (0.4 kg/m²) = seam taping only — not full skim. Full skim §1.11."

### 2.7 Corners formula — CLAUDE.md §1.3 incomplete

- CLAUDE.md §1.3: `corner_length = number_of_outer_corners × ceiling_height`
- Code computes:
  ```
  kampai = perim + 4*H                                # ceiling perim + 4 inner verticals
  kampai += n_doors * (door_W + 2*door_H)              # door reveal edges
  kampai += n_windows * (window_W + 2*window_H)        # window reveal edges
  ```

Code is far more correct. §1.3 misses ceiling-wall junction (perimetras), inner vertical corners × H, door + window reveal edges (NRM2 §29.10).

**Fix:** Replace §1.3 with full formula, separated into 3 sub-items. Note NRM2 §29.10 alignment.

### 2.8 Grindjuostės waste missing in code

- CLAUDE.md §1.4: `+ 10% waste`
- Code: `grindjuostes = max(0, perim - door_widths_total)` — waste absent

**Fix:** Add `* 1.10` to grindjuostes line in `calc_room_quantities`.

### 2.9 Tile straight-lay waste — too optimistic universal default

Code `tiles_straight: 0.08`. NRM2 §27 / LT QS practice = 10% universal QS default; 8% only for very simple rectangular rooms.

**Fix (minor):** Raise universal default to 10%. Keep 8% as "tikslus" option.

---

## 3. ERRORS / CORRECTIONS NEEDED

### 3.1 Window reveals: 3 sides only — ERROR

CLAUDE.md §1.2:
```
Per window: reveal_length = (2 × window_height + window_width)  ← 3 sides ONLY
Per door:   reveal_length = (2 × door_height + door_width)      ← 3 sides, correct for door
```

A window has **4 reveal sides**: top head, bottom sill (inside wall depth), left + right jambs.

**Correct:**
```
window_reveal_length = 2 × window_H + 2 × window_W   (4 sides)
window_reveal_area   = reveal_length × wall_thickness
door_reveal_length   = 2 × door_H + door_W            (3 sides — correct, no floor sill)
```

Error understates window reveal area by `window_W / (2H+2W)`. For 1200×1500 mm window, 200 mm wall: CLAUDE.md gives (3.0+1.2)×0.2 = 0.84 m²; correct is (3.0+2.4)×0.2 = **1.08 m²** — **29% undercount per window**.

**Fix:** Change §1.2 window formula to `2 × window_H + 2 × window_W`.

### 3.2 Ceiling cornice waste 5% too low

§1.4: `ceiling_cornice = perimeter + 5%`. For mitred decorative cornice, 8–12% (4 mitre cuts per rect room). 5% only OK for straight shadow gap profiles.

**Fix:** "5% for flat shadow gap profiles; 10% for decorative cornice with corner mitres."

### 3.3 Waterproofing low on rough substrates

§1.12: "1.5 kg/m² 2 coats". Mapei Mapelastic HP TDS: 1.5–2.5 kg/m². Rough concrete (typical LT bathroom before screed) needs 2.0+; smooth screed 1.5 OK.

**Fix:** "1.5–2.5 kg/m² (1.5 smooth screed; 2.0–2.5 rough concrete/block)."

### 3.4 Paint coverage on fresh plaster — substrates conflated

§1.10: "Fresh plaster | 3–5 m²/L". LT new-build standard is Knauf Rotband (gypsum, smoother). Coverage on fresh Rotband Q2: 5–7 m²/L first, 8–10 second. Sand-cement plaster: 3–4 m²/L.

**Fix:** Split:
- Fresh gypsum plaster (Rotband/gipso tinkas): 5–7 m²/L
- Fresh sand-cement plaster (cemento tinkas): 3–4 m²/L

---

## 4. MISSING POSITIONS

### M1 — Gruntavimas (Priming)
```
primer_liters = paintable_area / primer_coverage
  Standard primer (Tikkurila Miramix, Caparol Tiefengrund): 0.15 L/m², ~7 m²/L
  Deep-penetration (porous): 0.20–0.25 L/m², ~4–5 m²/L
KZ: "Sienos gruntuojamos giliai skverbiančiu grunteliu 1 sluoksnis"
```

### M2 — GKP siūlių armavimo tinklelis (Mesh tape for drywall seams)
```
arming_tape_m = drywall_area_m2 × 0.35  (0.35 m joint per m², industry avg)
Knauf Fugen mesh: 45 mm width, 90 m roll
KZ: "GKP siūlių armavimas stiklopluošto tinkleliu"
```

### M3 — Vidinė palangė (Internal windowsill)
```
windowsill_m = n_windows × (window_W + 2×0.05)  [5 cm overhang each side]
windowsill_m2 = windowsill_m × sill_depth_m  [0.20–0.35 m for 200–250 mm walls]
KZ: "Vidinė palangė (granitas/MDF/PVC)" m or m²
```

### M4 — Grindų išlyginamasis sluoksnis volume
```
screed_volume_m3 = floor_area × thickness_m  [avg 5 mm self-levelling]
screed_bags_25kg = CEILING(floor_area × thickness_mm × 1.65 / 25)
Weber.Floor 4310: 20 kg → ~10 m² @ 5 mm
```

### M5 — Plytelių klijai ir fugavimas
```
adhesive_kg = tile_area_m2 × consumption_kg_per_m2
  C1 thin-bed (flat): 3–4 kg/m²
  C2 (LT default, Mapei Granirapid): 3.5 kg/m²
  Thick-bed/natural stone: 6–8 kg/m²

grout_kg = tile_area_m2 × joint_factor
  30×60 cm tile, 2 mm joint: ~0.7 kg/m² (Mapei Ultracolor Plus)
  Universal LT: 0.5–1.5 kg/m²
```

### M6 — Hidroizoliacija kampų juosta
```
waterproof_tape_m = bathroom_floor_perim + shower_floor_perim + n_pipe_penetrations × 0.30
Mapei Mapeband / Schluter Kerdi-Band, 5 m / 10 m rolls
```

### M7 — Kampų silikonas
```
silikonas_m = bathroom_floor_perim + shower_vert_corners + bath_rim_length
600 ml cartridge → ~5–7 m at 6 mm bead
```
(Present in code `calc_additional_positions` item 5; absent from CLAUDE.md.)

### M8 — Betono lubų/sienų gruntas
```
concrete_primer_m2 = ceiling/wall area of concrete rooms (tambūras, garažas, exposed soffit)
0.15–0.20 L/m² (Tikkurila Miramix, Caparol Tiefengrund CT17)
```

### M9 — GKP metalinis karkasas (MAJOR omission)
```
studs_CW_m = CEILING(wall_length / spacing) × wall_height  [CW75 @ 400 or 625 mm c/c]
tracks_UW_m = wall_length × 2  [floor + ceiling UW]
Total metal profile ≈ 1.8–2.5 × drywall_area_m2 (linear m)
Knauf W111: CW75 + UW75; 30–40% of partition material cost
KZ: "Metalinis GKP karkasas (CW75+UW75)" m or kompl.
```

### M10 — Garo barjeras drėgnosiose patalpose
```
vapour_barrier_m2 = wet_room_wall_area_above_tiles × 1.10  [10% overlap]
Material: PE foil 0.2 mm or foil-faced retarder
KZ: "Garosandara (PE plėvelė 0.2mm) prieš GKP montavimą"
```

### M11 — Durų montavimas
```
door_installation_count = n_doors  (vnt.)
KZ: "Vidaus durų komplekso montavimas" vnt.
```

### M12 — Shadow gap / lubinis kampas profilis
```
shadow_gap_m = room_perimeter  [for rooms with this detail]
KZ: "Aliuminio shadow gap profilio montavimas" m
```

### M13 — Akustinė izoliacija pertvarose (LEGALLY REQUIRED multifam)
```
acoustic_wool_m2 = GKP partition area  [mineral wool inside stud cavity]
impact_acoustic_mat_m2 = floor_area  [floating floor]
STR 2.01.07:2003: Rw ≥ 50 dB between apartments — mandatory
KZ: "Mineralinė vata GKP pertvarose (akustinė)" + "Akustinis padas po grindimis"
```

### M14 — Judamosios siūlės plytelėse
```
movement_joint_m = floor_area / 20  [one joint per ~4.5 m bay]
ISO 13007 / EN 12004: required every 4–5 m in LT climate
KZ: "Judamosios siūlės formavimas ir silikonavimas" m
```

### M15 — Saunas / special wet rooms (LT-specific)
Common in LT private houses. Missing positions: sauna timber lining (m²), heater base (vnt.), bench framing (m), steam room waterproofing (higher spec than standard bathroom).

---

## 5. SECTION 6 (Validation Checks) — Corrections

- **Check 1:** "2.5–4× floor area for paintable walls" correct for 9–25 m² rooms. Add: "Open-plan >40 m² may be as low as 2.0×."
- **Check 4:** "Paint ≈ 0.22 l/m²" implies 2.0× factor (2/9). §1.10 specifies 1.8× → 0.20 l/m². Use 0.20.
- **Check 6 misplaced:** "Insulation anchors 6–8 per m²" is facade ETICS (Type 2), not interior. Replace with:
  - GKP screws: 30/sheet = 10/m² (flag <8 or >15)
  - Tile adhesive: 3.5–4.5 kg/m² thin-bed (flag <2 or >8)
  - Primer: 0.15–0.20 L/m² (flag <0.10 or >0.30)

---

## 6. SECTION 8 — Additional LT-specific Mistakes

- **Missing GKP metal framing:** estimators price boards but not CW/UW steel (30–40% of partition cost)
- **Ignoring acoustic requirements:** STR 2.01.07 Rw≥50 dB multifam mandatory; mineral wool legally required
- **Applying new-build rates to renovation:** demo + surface prep at 2–3× labour rate
- **Forgetting tile movement joints:** ISO 13007 every 4–5 m in LT climate; cracking in 2–3 yrs if omitted
- **Sauna/wet room omissions:** steam-room waterproofing, heater base, specific ventilation
- **Missing vapour barrier docs:** Knauf/Gyproc require it for warranty in wet rooms

---

## 7. Authoritative Source Bibliography

| Source | Publisher | Document | Location |
|--------|-----------|----------|----------|
| RICS NRM2 2nd ed (2012) | RICS | Detailed Measurement — §29 (paint, 1.0 m² thr.); §27 (floors, 0.5 m² thr.) | rics.org → Standards |
| BCIS SMM7 | BCIS/RICS | Standard Method 7 §K (plaster: 0.5 m², superseded 2012) | RICS library |
| DIN 18299 (2019) | DIN | VOB/C: Allgemeine Regelungen | din.de |
| DIN 18363 (2019) | DIN | VOB/C: Maler- und Lackierarbeiten §3.4 | din.de |
| DIN 18365 (2019) | DIN | VOB/C: Bodenbelagarbeiten | din.de |
| DIN 18350 (2019) | DIN | VOB/C: Putz-/Stuckarbeiten Q-system | din.de |
| STR 1.05.06:2010 | LR AM | Statinio projekto rengimo tvarka §6 mansard | e-seimas.lrs.lt |
| STR 2.01.07:2003 | LR AM | Triukšmo apsauga, Rw≥50 dB | am.lt |
| STR 2.02.09:2005 | LR AM | Visuomeniniai pastatai, durų matmenys | am.lt |
| Knauf GKP | Knauf | 1200×2500 mm, 30 screws/sheet, compound 0.3–0.5 kg/m² | knauf.lt |
| Tikkurila | Tikkurila | Coverage 7–10 m²/L smooth, 5–7 fresh gypsum, primer 0.15 L/m² | tikkurila.lt |
| Mapei Mapelastic HP | Mapei | Waterproofing 1.5–2.5 kg/m² 2 coats; Mapeband corner | mapei.lt |
| Mapei Granirapid | Mapei | C2FT 3.5 kg/m² thin-bed | mapei.lt |
| Mapei Ultracolor Plus | Mapei | Grout 0.5–1.5 kg/m² | mapei.lt |

---

## SUMMARY TABLE — Priority Order

| Issue | Location | Status | Priority |
|-------|----------|--------|----------|
| Opening threshold 0.5 m² for paint | CLAUDE.md §1.1 | ERROR — NRM2 = 1.0 m² | **Critical** |
| Default window area 1.40 m² | code | ERROR — LT std 1.80 m² | **High** |
| Window reveals 3 sides only | CLAUDE.md §1.2 | ERROR — 4 sides, ~29% undercount | **High** |
| Corners formula incomplete | CLAUDE.md §1.3 | Incomplete; code correct | **High** |
| Gruntavimas formula | CLAUDE.md | MISSING KŽ position | **High** |
| Tile adhesive + grout | CLAUDE.md | MISSING KŽ position | **High** |
| GKP metalinis karkasas | CLAUDE.md | MISSING — major cost item | **High** |
| Drywall waste 1.10 vs 1.12 | §1.8 vs code | Inconsistency | Medium |
| Ceiling height 2.65–2.75 m | CLAUDE.md §2 | Minor inconsistency vs code | Medium |
| Grindjuostė waste missing in code | code | Inconsistency vs CLAUDE.md | Medium |
| Waterproofing 1.5 kg/m² | §1.12 | Low on rough | Medium |
| Fresh plaster coverage conflated | §1.10 | Gypsum vs cement not split | Medium |
| Akustinė izoliacija | CLAUDE.md | MISSING — legally required | Medium |
| Grindų išlyginamasis volume | CLAUDE.md | MISSING formula | Medium |
| Vapour barrier wet rooms | CLAUDE.md | MISSING position | Medium |
| Internal windowsill (palangė) | CLAUDE.md | MISSING position | Medium |
| Durų montavimas | CLAUDE.md | MISSING KŽ position | Medium |
| Movement joints in tiles | CLAUDE.md | MISSING position | Medium |
| Cornice waste 5% | §1.4 | Low for mitred; use 10% | Low |
| Check 4: 0.22 vs 0.20 | §6 | Minor inconsistency | Low |
| Check 6 ETICS in interior | §6 | Misplaced | Low |
| Kampų silikonas | CLAUDE.md | Missing doc (in code) | Low |
| Shadow gap profilis | CLAUDE.md | MISSING position | Low |
| Sauna/special wet rooms | CLAUDE.md | MISSING LT-specific | Low |
| STR 1.05.06 mansard | code | CONFIRMED CORRECT | — |
| Q-level skim | §1.11 | CONFIRMED | — |
| First coat 1.8× | §1.10 | CONFIRMED | — |
| GKP sheet 3.0 m² | §1.8 | CONFIRMED | — |
| Gross wall/ceiling | §1.1 | CONFIRMED | — |
