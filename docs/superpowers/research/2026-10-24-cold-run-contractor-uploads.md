# Cold run of the contractor's fresh uploads — Phase 0 (b)

**Date:** 2026-10-24 · **Worker:** Opus 5.5 · **Branch:** `phase0/cold-run` (from `togal-v2` @ d63cc06a)
**Plan:** `docs/superpowers/plans/2026-10-24-deterministic-hybrid-plan.md` §4 Phase 0 (b)
**Cost:** €0. No Anthropic call was made; the runner replaces the SDK client constructor with one that raises.

Inputs (read-only, outside the repo): production DB backup blobs and R2 PDFs for two accounts.
Codenames only:

| codename | upload | pages | table area | PDF |
|---|---|---|---|---|
| **objektas_i** (primary: the contractor who rejected the output) | upload A (Oct 9) and upload B (Oct 13) | 10 | 207,1 m² (two units, 104,99 + 102,11) | vector + text, sheet 1 a raster cover |
| objektas_j1 | — | 1 | 193 m² (two identical units) | vector + text |
| objektas_j2 | — | 7 | 96,5 m² | vector + text |
| objektas_j3 | — | 1 | 96,5 m² (same flat as j2) | raster scan, no text layer |
| objektas_j4 | — | 1 | 90 m² | vector, text converted to outlines (no text layer) |
| objektas_j5 | — | — | 100,2 m² | no PDF in storage, blob only |

Tools committed with this note: `scripts/cold_run/run_cold.py` (the lane, cold, per PDF) and
`scripts/cold_run/audit_blobs.py` (what production showed). Both take the PDF / blob directories on
the command line and refuse to write their output inside the repository.

---

## 0. Verdict

1. **On objektas_i the togal-v2 geometry lane reads nothing.** 0 of 17 rooms located, 0 outlines, 0
   perimeters, on both uploads. Production's own lane (it runs lane version 11; togal-v2 is version 13)
   recorded the same zero in all seven blobs — so every perimeter the contractor saw was a language
   model's guess.
2. **The zero comes from three concrete, fixable faults, not from the drawing being hard.** The room number
   badges are 6,6 pt tall and the badge limit is 6,5 pt; the wall solid is built from one fill colour and this
   architect draws the outer walls dark grey and the new partitions mid grey; the two units carry the same
   room numbers (1–8 and 1–9). With the first two faults patched for a diagnostic run only (nothing committed),
   the lane outlines 7 of the left unit's 8 rooms on the single-unit sheet, 4 of them within 0,3 % of the table.
3. **What he saw was unstable.** The two uploads are two sibling buildings with the same room table. The
   model gave one bedroom 15,40 m of perimeter in upload A and 28,24 m in upload B (the drawn outline
   is 15,40 m). Walls to paint: 554,4 m² vs 599,1 m² (+8 %). Bathroom height: 2,2 m vs 2,0 m. Neither
   value is written in the drawing.
4. **objektas_j3 / objektas_j4 are blind spots of the text-first lane.** No text layer means no table, no badges,
   no dimension strings and no scale. j4's walls are proper vector fills (146 wall pieces), so OCR plus a scale is
   enough there; j3 needs OCR plus raster segmentation (the plan's SAM 2 track).

---

## 1. objektas_i — primary case

### 1.1 Do the two uploads differ?

Yes. They are **two different PDFs of one design for two neighbouring buildings**, not a re-upload:

- Same room table on the same sheet (17 rooms, 207,10 m², identical values).
- The title block's address differs by the house number. On upload B the cover sheet's text and sheet
  labels were edited.
- Sheet order changed: upload A has the partitions plan (pertvarų planas) on sheet 4 and the plumbing plan on
  sheet 6. Upload B swaps them. The path counts confirm it (A: 6 764 / 28 645, B: 28 624 / 6 750).
- Every plan sheet differs in the render by 12–27 % of the pixels. An overlay of the partitions sheets
  shows the walls **mirrored left to right**: the sibling building is the mirror image.
- Production read them as different projects. It took 989 s and $1,63 of Vision for A, 1 245 s and $1,78 for B
  (Opus 5, three voting rounds each).

Content shared by both: sheet 1 is a raster cover; sheets 2–3 hold the drawing list. Sheets 4 and 6 are **two-unit**
sheets: partitions and plumbing, both units drawn, both room tables printed. Sheets 5 and 7–10 show the
**left unit only**: furniture, ceiling and three electrical sheets. No section, no wall developments
(išklotinės), no door or window schedule and no finish schedule. The room tables are the only m² labels;
the plan writes no area inside a room.

### 1.2 What production showed him (both uploads)

**Scope he chose** (`_apimtis`, identical on both): floors, tiles, plumbing and electrical **excluded**, and openings
**not deducted** (`sienos_angos: neatimti`; the default is `atimti`). So the missing tile, floor, waterproofing
and skirting rows are **his own scope**, not an engine fault. What remained is walls, ceilings, plasterboard,
ventilation and site rows: 41 rows, 35 with a quantity, 6 checklist rows.

**Rooms.** Production showed 17 rooms numbered `K1–K8` / `D1–D9`. Those numbers were **invented by the model**:
the drawing numbers them 1–8 and 1–9. The text-layer room table merged nothing (`eksplikacija_merged_rooms`
0 in A, 3 in B; `eksplikacija_guard: insufficient`). Areas are right, because the model copied them from the table.

**Perimeters — all from the model** (`_walls_perimetras_saltinis: vision`, one `zoom`). Not one comes from the drawing:

| room (table nr) | table m² | prod A perimeter | prod B perimeter | prod A walls m² | prod B walls m² |
|---|---|---|---|---|---|
| left 1 corridor | 16,14 | 24,00 | 22,00 | 67,68 | 62,04 |
| left 2 bedroom | 14,56 | 15,40 | **28,24** | 43,43 | **79,64** |
| left 3 bathroom | 3,68 | 7,80 | 7,90 | 0 (full tile) | 0 |
| left 4 bedroom | 11,95 | 14,00 | 14,20 | 39,48 | 40,04 |
| left 5 bedroom | 10,68 | 13,30 | 13,60 | 37,51 | 38,35 |
| left 6 living / kitchen | 36,32 | 24,60 | 25,20 | 69,37 | 71,06 |
| left 7 bathroom | 7,04 | 10,80 | 10,70 | 0 | 0 |
| left 8 technical | 4,62 | 8,70 | 8,70 | 14,09 | 24,53 |

Production's `_perimeter_validation` passed 17/17 in A and 16/17 in B; only the 28,24 m one was flagged.
Isoperimetric bounds are too loose to catch most of these errors.

**Heights.** There is no section and no height mark. 2,82 m default everywhere. Bathrooms got 2,2 m (A) and 2,0 m (B),
both invented. With the tile height of 2,4 m from his overrides, every bathroom became „full tile" and its walls left
every row. In B the invented 2,0 m also fired eight STR „below 2,20 m" warnings about a value nobody read.

**Rows that look wrong to an estimator** (A / B):

| row | A | B | why it is suspect |
|---|---|---|---|
| Sienų glaistymas/dažymas, m² | 554,4 | 599,1 | rests on model perimeters; differs 8 % between two copies of one design |
| Sienų lyginimas Rotband, m² | 166,3 | 179,7 | a fixed 30 % share of the walls (`_rotband_source: prielaida`) |
| Dažymo kampų montavimas, m | **622,1** | **633,6** | 2,5 × the sum of all room perimeters. The row adds the wall–ceiling line (200 m), inner corners (147 m), reveal corners (137 m) and half corners (138 m) — scope `kampai: su_vidiniais` |
| Durų angų paruošimas beapvadinėms durims, m | 75,3 | 80,3 | every interior door taken as frameless because of one plan symbol (`_door_types.plan_tagged` 1 / 3) |
| LED nišų glaistymas/dažymas, m | 17,6 | 22,0 | the legend states 24,00 m of LED strip plus 2,40 m flush (production's own warning); the two copies disagree; a second „LED nišos — suveskite ilgį" row stays blank |
| Lubų glaistymas/dažymas, GKP lubos, m² | 207,1 | 207,1 | = table total, correct |

The other rows are fixed-rule rows (ventilation from symbols, site rows) and are not judged here.

Hidden fault, not visible in the rows: in A the ceiling anchor is **621,3 m² = 3 × 207,1**. The plan-area lane summed
the room-table labels of sheet 4, which hold both units plus the subtotals. It did not move the ceiling row this
time; it would once a row reads the anchor.

**Warnings he saw**: 49 (A) and 37 (B). They include „no section, 2,82 m default" and „no door/window schedule".
Also „perimeters approximated from area and proportions, ±10 %" (A) or „estimated from the plan's dimension
chains" (B): two different stories for the same method. Consistency check `room_count`: „17 rooms but table
lists 7". The `lt_rules` duplicate hint „tech room right and tech room left may be the same room" is wrong:
they are two units.

### 1.3 What the togal-v2 geometry lane reads cold

Runner: `run_cold.py`. It reproduces the paid reading's deterministic steps 2.44 → 2.44d: text scan, room table
from the text layer, dimension pairs, raster wall outlines, geometry lane. Then the door schedule, ruled tables,
vector symbols and wall types. Both uploads give the same picture.

| read | upload A | upload B |
|---|---|---|
| sheets | 1 raster cover, 1 text, 8 vector + text | same |
| text-only sheet kind (preflight) | interior_plan | interior_plan |
| scale per plan sheet (from dimension strings over their hairlines) | 4: 1:75 · 5: 1:75 · 7: 1:71 · 6, 8, 9, 10: none (strings not line-backed) | same values; sheet 4/6 swapped |
| room table (text layer) | **7 of 17 rows**, numbers mangled (`1, 101, 201, 202, 301, 401, 501`); the right unit's table and the left unit's room 8 are lost; no header detected | same |
| m² labels inside rooms | none (all 85 labels are table cells) | none |
| designer figures (`_autoriaus_kiekiai`) | 1: „Priglaistoma LED juosta 2,4 m" | same |
| rooms located | **0** | **0** |
| vector outlines | **0** | **0** |
| perimeters read from strings | 0 | 0 |
| drawn doors / windows | 0 / 0 | 0 / 0 |
| floor coverings read | 0 (no floor sheet) | 0 |
| door schedule | none in the drawing | none |
| ruled tables | 6 tables, no schedule recognised | same |
| vector symbols (diffusers) | 5, from the legend (sheet 7; 8 and 10 repeat the plan) | 5 |
| time, whole cold run | 22,7 s (lane itself 0,6 s; table read 4,3 s; project scans 11,6 s) | 26,4 s |

The seeded variant gives the lane production's 17 rooms (number, name, area only) and production's page
classification. It also locates 0. The invented numbers `K1…D9` match no badge on the drawing.

**Why zero — three causes, each confirmed by a diagnostic run (patches live in the scratchpad, not the repo):**

1. **Badge size limit.** `room_locator.BADGE_MAX_H_PT = 6.5`. On every sheet this drawing's badges measure
   6,6 pt in PDFium's frame, so all of them are rejected. With the limit at 7,0 pt, all 8 badges of a unit
   are found on sheets 4, 5 and 7.
2. **One wall colour.** `vector_rooms._wall_solid` takes the single dominant fill colour. Here new partitions are
   mid grey (0,58), and the outer and bearing walls dark grey (0,39, about 25 % of the wall-shaped area). The
   outer shell is dropped, so no room closes: „sienos neuždaro patalpos". With wall pieces of every colour
   holding ≥ 20 % of the dominant one's wall-shaped area, the rooms close. Upload A's dark grey holds 24,5 %;
   a 25 % cut-off still loses it there. The rule has to be principled, not a tuned share.
3. **Duplicate room numbers across units.** Sheets 4 and 6 draw both units with badges 1–8 and 1–9.
   `locate_rooms` keys rooms by number and keeps one seat per number. The left unit's „4" landed in the right
   unit's room 4 (5,01 m² outline for an 11,95 m² room). The text table reader fails on the same structure:
   two stacked tables with repeated numbers.

**What the lane reads with faults 1 and 2 patched** (left unit, single-unit sheet 5; both uploads identical):

| room | table m² | prod A / B perimeter | lane outline m² | Δ area | lane outline length m | lane perimeter status |
|---|---|---|---|---|---|---|
| 1 corridor | 16,14 | 24,00 / 22,00 | 13,85 shared with 6 | open space 1+6: 45,0 vs 52,46 (−14 %) | 24,30 | estimate (open space) |
| 2 bedroom | 14,56 | 15,40 / 28,24 | 14,56 | 0,0 % | 15,40 | estimate (2 of 4 walls without a string) |
| 3 bathroom | 3,68 | 7,80 / 7,90 | 3,69 | +0,3 % | 7,72 | estimate (no strings) |
| 4 bedroom | 11,95 | 14,00 / 14,20 | 11,96 | +0,1 % | 14,82 | estimate |
| 5 bedroom | 10,68 | 13,30 / 13,60 | 11,96 | **+12 %** | 14,82 | outline ≠ table (mirror twin of 4; table and drawing disagree, or the wrong face) |
| 6 living / kitchen | 36,32 | 24,60 / 25,20 | 31,16 shared with 1 | see 1 | 15,81 | estimate (open space) |
| 7 bathroom | 7,04 | 10,80 / 10,70 | not located on sheet 5 (badge touches a „20" string) | — | (sheet 4: 7,05 m², 11,72 m) | — |
| 8 technical | 4,62 | 8,70 / 8,70 | 4,62 | 0,0 % | 9,50 | estimate |

Bedroom 2 settles the upload-B question: the drawn outline is 14,56 m² and 15,40 m long. The 28,24 m he saw
was a model error that doubled that room's wall rows.

What stays weak even with those patches:

- **No perimeter is READ.** Sheet 5 is the furniture plan: its dimension strings are furniture modules. The lane
  even attached eight „530" wardrobe modules to bedroom 4's walls (marked as estimate, but the assignment is
  wrong). The real wall strings are on the two-unit partitions sheet, which fault 3 blocks.
- **Drawn openings: 0 doors, 0 windows** classified, although the outlines show 1–6 wall gaps per room.
  The door swings are dashed arcs. `drawn_openings` did not recognise them on this drawing.
- On the two-unit sheet the right unit's rooms were outlined where their badge won the duplicate race.
  Rooms 4 (5,01 m²) and 7 (10,31 m²) got perimeters summed from strings: 8,90 m and 13,00 m. This shows
  what sheet 4 can give once units are separated.

---

## 2. Secondary cases (objektas_j1–j5)

All five have the contractor's scope at its default (or tiles in scope), so tile, floor and waterproofing rows exist.
Production's lane (v11) placed **0 outlines in every one**.

**objektas_j1** (one sheet, two identical units, 18 rooms numbered 101–109 / 201–209, 193 m²).
- Cold: no m² label in the text layer, and the text table reader found nothing (production's model read the table).
  36 dimension strings, **0 line-backed → no scale**. Seeded with production's rooms, all 18 badges are located,
  then the lane stops: no scale, no outlines.
- Production: perimeters from the model (two units with identical areas got different perimeters: room 102
  9,40 m vs room 202 12,04 m), height 2,82 m default everywhere. 4 waterproofing „vnt" rows. 71,72 m² of
  kitchen floor tiles = both open living/kitchen rooms tiled wall to wall, an assumption.
  Corners 685,7 m = 3,1 × perimeters.
- Cold run 7,2 s.

**objektas_j2** (7 sheets, 9 rooms, 96,5 m²).
- Cold: text table read **8 of 9** rows (room 2 lost). Scales on sheet 5 (1:50) and sheet 6 (1:45) only.
  The room badges are written **11 pt tall**, so none counts, and 0 rooms are located.
- With the badge limit raised (diagnostic): 9/9 located, **8/9 outlined**. Areas run +1 … +3 % above the table
  (sheet 1 measures 1:45 against its stated 1:40; the entry room is −13 %). The living room is open (no
  outline). Bathroom 6's perimeter is summed from strings: 7,68 m, equal to production's. 9 doors drawn.
- Production: heights read from ceiling-plan marks (2,7 / 2,8 / 3,2 m — the one project where heights were
  real). The designer's floor plan states **tiles 14,5 m²** (and floor 82,4 m² per production's own page note).
  Production billed **48,26 m² of floor tiles** (whole living room tiled) plus 48,28 m² of laminate.
  Designer LED strips 3,2 + 2 + 4,2 + 5,6 = 15,0 m; production 19,3 m of LED niches and 18,0 m connected.
  Production read the designer's „Karnizas … 3 m" note as a figure; it is a sentence about a curtain motor.
  Corners 368,5 m = 3,4 × perimeters.
- Cold run 9,7 s.

**objektas_j3** (a raster of j2's sheet 1, 213 dpi, with hand-written blue measurements and notes on it).
- Cold: nothing. No text layer: no table, no badges, no strings, no scale; the lane returns in 0,0 s.
- Production: the contractor **typed every perimeter and height himself** (`user_override` on all 9 rooms).
  Production's validator flagged two of his values (bathroom 6: 12,5 m for 3,69 m²; bathroom 8: 8,06 m,
  below the minimum for 5,57 m²).
- He ran the same flat twice (j2 vector, j3 scan): wall paint 221,2 m² vs 217,6 m².

**objektas_j4** (one vector sheet, every letter and digit converted to outline paths, so no text layer).
- Cold: nothing readable as text. The **walls are vector fills** (146 wall pieces, 38 solid parts) and would trace.
  But there is no badge to seed a room, no string for a scale, and no room table on the sheet.
- Production: rooms named „Patalpa 101…109", areas computed by the model „from wall dimensions"
  (90,24 m² vs 96,5 m² for what looks like the same flat). Scale „not found, read as centimetres".
  Ceiling rows only 45,97 m² of 90,24 m². Heights typed by him.
- Cold run 1,2 s.

**objektas_j5** (no PDF; blob only, rooms „2-1…2-9", 100,2 m²).
- Perimeters typed by him (`user_override`). Two ceiling heights read from the ceiling plan.
- Corners 367,7 m = 3,2 × perimeters. Waterproofing as 3 „vnt". Reveals only 17,0 m for a flat with windows.

---

## 3. Cross-project failure list (ordered by rows broken)

„Rows" = production rows with a quantity whose value depends on the failing input, summed over the seven blobs.
The wall/perimeter-driven families are walls, Rotband, corners, reveals, skirting, cornice, wall tiles, silicone
and wall materials; production had **166** such rows across the seven projects. The 53 rows on j3/j5 rest on
perimeters he typed. Table-area-driven rows (ceilings, floors, protection, screed, floor tiles) are 132.

| # | failure | where | rows broken | fix track |
|---|---|---|---|---|
| 1 | **Rooms never placed → no outline, no read perimeter, so perimeters come from the model** (prod lane v11: 0 outlines in 7/7; togal-v2: 0 in objektas_i and j2) | i (A, B), j1, j2, j4 | **113** wall/perimeter rows (12 + 12 + 30 + 35 + 24) | causes 2–5 below |
| 2 | **Badge height limit 6,5 pt** rejects real badges (6,6 pt objektas_i, 11 pt j2) | i, j2 | 59 (i A + i B + j2) | relative size rule (badge vs dimension text on the same sheet), or zone-scoped badges |
| 3 | **Wall solid from one fill colour** — outer walls in a second colour drop out, no room closes | i | 24 | union of every wall-shaped fill colour above a principled floor; check closure per room |
| 4 | **Repeated room numbers across units on one sheet / table** (two units, 1–8 + 1–9) — locator keys by number, table reader merges two tables, model invents `K/D` prefixes | i | 24 (and all 17 room identities) | a unit/table key next to the number; split sheets by table → plan region |
| 5 | **No scale where strings are not line-backed** (j1: 36 strings, 0 backed; i sheets 6, 8–10) | j1 (+ i partly) | 30 | calibration-line gesture (§3.1 `scale.py`); stated-scale fallback when strings agree |
| 6 | **No text layer** (raster j3; text-as-paths j4) — no table, badge, string or scale | j3, j4 | 52 (28 + 24; j3's rest on his typed perimeters) | OCR (PaddleOCR) on the render; SAM 2 for j3's walls; j4's walls are vector already |
| 7 | **Heights invented when no section exists** (2,82 default; bathrooms 2,2 vs 2,0 across two runs) | i, j1, j4 | every wall row again (×H) — same 113 rows, second error factor | blank-with-reason + one project question; never a per-room invented value |
| 8 | **Corner row 2,5–3,4 × sum of perimeters** on every project (wall–ceiling line + inner + reveal + half corners) | all 7 | 7 rows (+7 PVC corner material rows) | conventions profile: which corner families he bills, fitted to his sąmatos |
| 9 | **Designer figures ignored or contradicted** (j2 tiles 14,5 m² vs 48,3 m² billed; LED 15,0 m vs 19,3 m; objektas_i LED legend 24 m vs 17,6 / 22,0 m) | i, j2 | ~8 | figures as checks against rows, shown in Patikra; text reader for legend totals on electrical sheets |
| 10 | **Room-table reader misses rows** (i: 7 of 17, mangled numbers; j2: 8 of 9; j1: 0) | i, j1, j2 | table-area rows stay right only because the model re-read the table | multi-table pages, header-less tables, repeated numbers |
| 11 | **Waterproofing billed in „vnt"** (count of wet rooms) instead of m² + tape m | j1–j5 | 5 | founder rule 4 (two rows), plan §1 |
| 12 | **All interior doors assumed frameless from one plan symbol** | i (A, B), j2, j3 | 4 | ask, do not assume, when only 1–3 symbols are tagged |
| 13 | **Drawn openings not classified** (dashed swing arcs; 0 doors on objektas_i even when outlined) | i | reveal + door rows (4) | `drawn_openings` on dashed arcs |
| 14 | **Furniture strings assigned to walls** on a furniture sheet („530" × 8) | i (diagnostic run) | 0 today (estimates), a risk once read | prefer the partitions sheet for strings; reject repeated module strings |
| 15 | **Ceiling anchor = 3 × total** (table labels of two units + subtotals summed) | i A | 0 today, latent | skip table cells and subtotal rows in the plan-area lane |

---

## 4. What the contractor saw vs what the geometry lane reads

| item | production showed (objektas_i A / B) | togal-v2 lane cold, as shipped | lane with faults 1–2 patched (diagnostic) |
|---|---|---|---|
| room list | 17 rooms, numbers invented (`K1…D9`) | 7 of 17, numbers mangled | table still mangled; seeded with the right numbers per unit |
| room position | model's box | none | badge, 8/8 per unit |
| outline | none (prod lane 0/17) | none | 7 of 8 rooms (left unit), 4 within 0,3 %, 1 at +12 %, open space 1+6 at −14 % |
| perimeter | model guess, e.g. bedroom 15,40 / **28,24** m | blank | outline length as estimate (bedroom 15,40 m) — none READ from strings yet |
| height | 2,82 default; bathrooms 2,2 / 2,0 invented | blank | blank (no section in the drawing) |
| doors / windows | model counts (19 / 20 doors) | none | wall gaps per room found, 0 classified |
| walls to paint | 554,4 / 599,1 m² | — | — (needs heights and his conventions) |
| scale | used implicitly | 1:75 on sheets 4, 5; 1:71 on 7 | same |
| designer figures | 1 found (2,4 m LED), not used as a check | same 1 | same |
| time / cost | 989 s, $1,63 / 1 245 s, $1,78 | 23–26 s, €0 | about 25 s, €0 |

| item | objektas_j2 production | j2 lane as shipped | j2 lane, badge limit raised |
|---|---|---|---|
| outlines | 0 | 0 (badges 11 pt) | 8/9, +1 … +3 % vs table |
| perimeters | model, every room | blank | 1 read from strings (7,68 m = prod), 7 estimates |
| heights | read from the ceiling plan (2,7 / 2,8 / 3,2) | — | — |
| floor tiles | 48,26 m² (designer states 14,5 m²) | — | — |

---

## 5. objektas_j3 and objektas_j4 — what the lane cannot do today

**objektas_j3 (raster, 2 481 × 1 754 px on a 838 × 593 pt page, no text layer, no vector paths):**
- No room table, no area label and no badge: every reader in the lane reads PDF text (`pdfplumber`, PDFium chars).
- No scale: dimension strings come from the text layer and their hairlines from vector paths, and here there are
  neither. The stated „M 1:40" in the title block is pixels too.
- No walls: `pdf_vectors.filled_shapes` sees no paths. `wall_outline` (the raster lane) needs a scale and label
  seeds and gets neither.
- No symbols, schedules or floor coverings (all text- or path-driven).
- What the image carries for OCR + segmentation: the room table (9 rows, sum 96,53), the badges 1–9, dimension
  strings in mm, the title-block scale, door swings, and **the contractor's own blue hand measurements**.
  These are evidence a check could show, and they must never be read as the designer's.
- Needed: plan §3.2 `text/ocr.py` (table, badges, strings, scale text). §3.1 `geometry/sam_source.py` or the
  floor-plan segmenter for the walls. The calibration-line gesture as the scale fallback.

**objektas_j4 (vector, 5 548 paths, 0 characters — the letters are outline paths):**
- No room table on the sheet at all, so no areas to compare against: areas must come from geometry.
- No badge text (the numbers 101–109 are glyph outlines), so no seed position.
- No dimension string (written in **centimetres** as paths), so no scale.
- **Walls are fine**: 146 wall-shaped fills in one colour, 38 solid parts. Once a seed and a scale exist, the
  existing vector trace applies; SAM is not needed here.
- Needed: OCR on the vector render (its glyphs are clean, so OCR should be near-exact), unit detection (cm vs mm),
  then the existing lane. Or one click per room plus one calibration line.

---

## 6. Corrections to the brief and caveats

- **Production does run a geometry lane.** Every blob carries `_meta.geometrija.versija = 11`, and togal-v2 is
  version 13. What production lacks is not the lane but any success of it on these drawings: 0 outlines in 7/7.
- Rooms in my diagnostic runs were seeded with the table's true per-unit numbers by hand. No reader produces
  that today (failure 4).
- The two diagnostic patches (`BADGE_MAX_H_PT = 7.0`; wall colours ≥ 20 % share) are measurements, not
  proposals. A colour share is threshold-sensitive: upload A's outer walls sit at 24,5 %.
- „Rows broken" counts are row families depending on an input, not row-by-row error against a contractor
  sąmata. Neither account's own sąmata is available.
- No paid call was needed or made. Production's page classification (`puslapiai`) was reused in the seeded
  variant only; it was already paid for.

## 7. Reproduce

```
venv/bin/python scripts/cold_run/run_cold.py --pdfs <dir> --blobs <dir> --out <dir outside repo> \
    --project objektas_i_a=<id> --project objektas_i_b=<id> …
venv/bin/python scripts/cold_run/audit_blobs.py --blobs <dir> --out <dir outside repo> --project …
```
