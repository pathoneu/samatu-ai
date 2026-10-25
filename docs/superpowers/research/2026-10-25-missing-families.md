# Phase 2b — the families his sąmatos bill and we did not emit

**Date:** 2026-10-25 · **Worker:** Opus 5.5 (manager review: Fable 5.1) · **Branch:** `v4/missing-families` (not merged) · **Plan:** `docs/superpowers/plans/2026-10-24-deterministic-hybrid-plan.md` §1 R1–R3, R7, §9 · **Inputs:** `2026-10-25-conventions-fit.md` §0, §6, §7; `2026-10-24-phase0-baseline.md` §2.
**Zero API spend** (dead key, the client constructor raises). Codenames only; quantities only — his prices are never read or written.

## Resume point (kept current)

- [x] `git reset --hard togal-v2` → branch; merged togal-v2 @ 94528f65 (Phase 3b) as instructed (merge commit on the branch, no rebase).
- [x] Founder decision: `aperture_no_deduct_max_m2` default 3,0 m² — `0ffca09b`.
- [x] Commit 1 — concept table, wording only — `fde8a50a` (+ `6c2b320f`, the duct row Phase 3b renamed).
- [x] Families — `290061ba` (rules/rows.py + conventions.py + one hook in vision_call.py).
- [x] Symbol-kind diagnostic (vector counter vs his rows) — §5.
- [x] Touched tests, one plain rows pass, full backend suite, cold run objektas_i A/B — §6.
- Left for the manager: the batch (four passes, replay). Next blockers: §7.

## 0. Verdict

**G2 (rows ±10 % corpus mean ≥ 40 % in-sample) is not reached — the branch moves the plain corpus mean from 10,8 % to 12,1 % (€ share 15,0 → 15,2 %; harness table).** The number is not comparable with the brief's 26–28 %: Phase 3b (merged before this work, 0d59ff4f) blanks every per-room row whose room lacks a drawn perimeter or a written height, so on the frozen corpus 131 of his rows now meet a *blank row of ours*. The families built here add **4 comparable rows** (b +2, h +2 within ±10 % on h) and turn 2 „no family" rows into „our row blank, format named" (a). Two thirds of what is left is not a family problem at all:

| his scored rows that are not comparable (plain, six projects) | before (post-3b, 94528f65 + aperture) | after this branch |
|---|---|---|
| `blank_row` — we emit the row, without a number (mostly Phase 3b's gate: no read height / perimeter) | 126 | 136 |
| `missing_family` — no row of ours does this work | 93 | 88 |
| `finer_split` — he splits what we sum | 14 | 11 |
| `unit_mismatch` | 0 | 4 |
| `wording_unmapped` — we emit it, the table did not read his label | **10** | **0** |
| total not comparable / comparable | 243 / 51 | 239 / 55 |

So the next lever is not more families: it is the heights / perimeters the person answers (the harness re-base the manager ordered), which turns most of the 136 blank rows back into numbers. Of the 88 `missing_family` rows, **32 are one project's ventilation material specification (objektas_b)** and ~35 are one-off lump lines (garage stairs, „Mėnulio" wall décor, door-handle change, materials lumps, rentals, AC routes, cabling) that no drawing quantifies.

## 1. Class counts per project

Rows: his scored rows (subtotals and rows without a quantity excluded). Classes as defined in the brief; mapping in `scratchpad/…/classify.py` (rules: `unmapped` → missing_family unless the concept-table commit maps it → wording_unmapped; „app row has no quantity" → blank_row; „unit" → unit_mismatch; „granularity" → finer_split; admitted gap / no app row → missing_family; tile niche-reveal rows → missing_family; his frameless-frame row (`pasleptu_duru_staktos`) → finer_split).

### 1.1 On the head the brief was written against (togal-v2 1a2cf04a, replay mode — the fit's 138 + 5 hidro rows = 143)

| project | not comparable | blank_row | missing_family | finer_split | unit_mismatch | wording_unmapped |
|---|---|---|---|---|---|---|
| objektas_a | 20 | 13 | 6 | 0 | 1 (hidro vnt) | 0 |
| objektas_b | 77 | 6 | 56 | 11 | 1 | 3 |
| objektas_c | 12 | 1 | 10 | 0 | 1 | 0 |
| objektas_d | 18 | 1 | 9 | 4 | 2 | 2 |
| objektas_g | 7 | 0 | 5 | 1 | 0 | 1 (hidro m², app side) |
| objektas_h | 9 | 3 | 5 | 1 | 0 | 0 |
| **total** | **143** | **24** | **91** | **17** | **5** | **6** |

(The hidro row on a b c d is both: our two-row labels were read by no concept *and* his vnt can never meet m² / m — counted as unit_mismatch here.) Of the 91 missing_family rows, 36 are objektas_b's ventilation (32 material-spec lines — SPIRO / SONODUCT / COMBIFLEX ducts by diameter, elbows, sleeves, tees, dampers, tape — + 3 EGROVENT diffuser spec lines + „Skylių gręžimo darbai" in the ventilation section).

### 1.2 Post-3b, plain mode (the instrument now) — before → after this branch

| project | comparable | blank_row | missing_family | finer_split | unit_mismatch | wording_unmapped | rows ±10 % |
|---|---|---|---|---|---|---|---|
| objektas_a | 5 → 5 | 40 → 42 | 6 → 4 | 1 → 1 | 0 → 1 | 1 → 0 | 3,8 → 3,8 % |
| objektas_b | 9 → **11** | 32 → 37 | 57 → 55 | 9 → 7 | 0 → 1 | 4 → 0 | 2,7 → 2,7 % |
| objektas_c | 6 → 6 | 19 → 19 | 10 → 10 | 0 → 0 | 0 → 1 | 1 → 0 | 5,6 → 5,6 % |
| objektas_d | 12 → 12 | 23 → 26 | 10 → 9 | 2 → 2 | 0 → 1 | 3 → 0 | 10,0 → 10,0 % |
| objektas_g | 11 → **12** | 2 → 2 | 5 → 5 | 1 → 1 | 0 → 0 | 1 → 0 | 30,0 → 30,0 % |
| objektas_h | 8 → **9** | 10 → 10 | 5 → 5 | 1 → 0 | 0 → 0 | 0 → 0 | 12,5 → **20,8 %** |
| **corpus** | **51 → 55** | 126 → 136 | 93 → 88 | 14 → 11 | 0 → 4 | 10 → 0 | **10,8 → 12,1 %** |

Every move, row by row:
- **commit 1 (wording only)** — hits unchanged. b „WC ir bide rėmo montavimas" ×2 and „Klozeto/ bide montavimas" → our WC-frame / WC rows (blank since 3b); d „Priglaistomų gipsinių šviestuvų, montavimas" → our lights row (blank), „Nišos įrengimas duše" → our niches-in-partitions row (blank, m vs vnt); our two-row waterproofing read → his vnt rows a b c d stay incomparable (unit), g „Hidroizoliacija" 39,50 m² meets our floor 17,67 m² (way off — the founder's two-row rule bills the floor only); `6c2b320f`: d „Rekuperacijos ortakių įrengimas" meets our blank duct row.
- **families** — h „Priglaistomų gipsinių difūzorių montavimas" 7: way off (ours 9) → **within ±10 % (7)**; h „Priglaistomų plyšinių difūzorių montavimas" 2: missing → **within ±10 % (2)**; b round 7 / slot 13 (montavimas and apdirbimas): one missing + one way off (20) → two way off (ours 2 slot, 18 round — the drawing's legend calls 2 of them slot „kondicionieriaus" diffusers and 18 round; he bills 13 slot from his EGROVENT specification; the drawing does not say what he says); a's two „Didžiaformačių plytelių klijavimas" rows (4,48 m², 8,70 m² niche reveals): no family → our row blank (format 120×120 cm named on sheet 9, area not).

**Leave-one-out.** No parameter was fitted in this branch — each family's default is „ON where the drawing gives the fact", which is not chosen on his rows — so leave-one-out equals in-sample. The one fitted-on-his-rows choice the brief warned about (a scope / share) does not exist here.

## 2. The concept table — what changed and why it is not a looser hit

`scripts/reconcile_samata_lines.py` (the frozen table): five of his wordings and three of our labels, nothing else. A row that newly maps can only land where our row says: in this corpus every newly mapped row of his meets a blank row or an incomparable unit, except g's waterproofing m² (way off). Same unit rule, same ±10 %; `test_row_scorecard.py` asserts each mapping and that a mapped wording against a blank row of ours is `missing`. The count of concepts goes 89 → 91 (two new families: `papildomas_glaistymas`, `demontavimas`); `mozaika` gets an app row.

Not done on purpose: his tile niche-reveal rows („(nišos angokraščiai)", a 8,70 m², b 34,49 m + 10,49 m²) are **not** mapped to our new „Angokraščių klijavimas plytelėmis" row — his are the reveals of shower niches, ours the reveals of windows / doors in tiled walls; scoring one against the other would make any hit an accident. b's „Aliuminio apdailinio kampo montavimas ant plytelių" is still swallowed by the ventilation-material pattern (`aliumini…`) — both are admitted gaps, so the bucket does not change; flagged for the table's next edit.

## 3. The families (rules/rows.phase2b_families) and their parameters

One marked hook in `extractor/vision_call._build_pozicijos_from_rooms` (`# v4 phase2b families`, after `_apply_row_provenance`, before the granularity merge) — a one-line call into `rules/rows.py`. Every row carries `_kilme`; blank rows carry `_tuscia_priezastis` = `_assumption` (row_provenance's shape). Parameters in `rules/conventions.LT_RANGOVAS` (overridable per project via `_overrides.profilis`):

| parameter | default | ON when | the number | without the fact |
|---|---|---|---|---|
| `difuzoriai_rows` | `by_kind` | the vector counter's legend has slot („plyšinis") and other diffusers, and the all-diffuser rows carry its count | per kind, from the counter's legend rows (drawing) | rows stay as they were (one kind) |
| `plyteliu_angokrasciai` | `auto` | a room with wall tiles has an opening of the reveals scope whose top the tiles reach | Σ (W + 2H), CLAUDE.md §1.2 (derived); the painted reveals row loses the same metres | blank naming the room when such an opening's size is unread; no row when no tiled wall has such an opening |
| `didziaformates_rows` | `auto` | the tile specification text (`_plyteliu_specs`) or the designer's legend (`_autoriaus_kiekiai`) names a ≥ 600 × 1200 mm (`LARGE_TILE_MIN_MM`) or mosaic tile | the designer's m² for that format when written in m² (drawing) — a piece count is never turned into m² | blank with the format and sheet (and the legend's piece count, if any) |
| `papildomas_glaistymas` | `auto` | his Prielaidos putty level is Q4 | = the painted wall rows' m² (derived), blank with them | blank: „…pasirinkite glaistymo lygį Q4 arba įrašykite plotą" |
| `demontavimas_rows` | `auto` | (row always present) | none — no reader | blank; names the demolition sheet when a sheet title says so, else says the set has none |

Corpus effect, row by row (plain): diffuser rows split on b (18 + 2) and h (7 + 2); tile-clad reveals a 5,90 m (111, window 1,50 × 2,20), b 10,50 m (08 and 10), c blank (room 06: two windows of unread size); large-format a blank (120×120 cm, sheet 9, „14 vnt" in the legend), b blank (1200×1200, sheet 10), g blank (60×120 cm, sheet 7), h blank (120 × 60 cm, sheet 7); mosaic: none named in a text-layer fact (b's „mozaika 3,5 m²" is in the model's prose summary, not in the text lane — not used); extra skim coat blank on all six (nobody chose Q4); demolition blank on all six (no demolition sheet in a…h or objektas_i — the title detection is tested synthetically).

**Not built (honest):**
- **GKP extras** (ceiling boxes, thickening, niches in partitions) stay the existing blank rows: `height_markers` gives altitudes inside rooms, not the length of the boundary between two ceiling levels, and the legend rows carry no length for these. Reading that boundary off the ceiling plan's vector paths is a geometry task (next blocker 3).
- **Ventilation ducts on b:** the 32 material-spec lines are a supplier's bill of materials (diameters, fittings); the drawing set has no ventilation plan sheet with duct runs. Duct rows stay blank with a reason (Phase 3b's rows).
- **Extra skim coat from the apdailos table's text („glaistoma 2 kartus")**: the corpus parse keeps no page text the rules can read; only his Q4 choice turns it on. A text-lane flag on the apdailos page would be the honest source (next blocker 4).

## 4. Founder decision: aperture threshold 3,0 m² (`0ffca09b`)

`aperture_no_deduct_max_m2` default 3,0 (source „rangovo taisyklė, 2026-10-25"); 1,0 stays a choice. The engine reads the profile default when the project chose nothing (`universal_rules`, LT standard only; NRM2 / VOB keep 0,5). 17 tests that check the *mechanics* of deducting a door / window under the 1,0 rule pin it with a new conftest fixture (`lt_aperture_1m2`); `test_rules_profile` states the new default.

Plain rows pass, before → after that single commit: **identical on all six projects** (a 3,8 · b 2,7 · c 5,6 · d 10,0 · g 30,0 · h 12,5 %). The fit's predicted +1 row on b and d does not show here because on this head the wall paint rows of a b c d are blank (Phase 3b: no read height / perimeter), and g / h carry the designer's wall figure. The fit's prediction is a statement about the pre-3b engine; it should be re-checked on the manager's replay pass and again once the harness supplies the answered heights.

## 5. Fixture / diffuser / light counts — what the vector counter can and cannot count

`count_legend_symbols` (extractor/vector_symbols.py) asked, per project, for legend labels of lights, sockets, switches, LED, floor drains, inspection hatches (diagnostic only, nothing wired):

| kind | a (his) | b (his) | c | d (his) | g | h (his) | verdict |
|---|---|---|---|---|---|---|---|
| diffusers (wired) | — (no glyph in legend) | 20 (20 = 7 + 13) | — | 6 (6) | 8 | 9 (7 + 2) | works; b's round / slot split disagrees with him (§1.2) |
| lights („šviestuv…") | 129 (38) | 17 (69) | — | — (9 + 2) | — | — (20) | **not countable**: the label matches several legend rows and prose; the counter counts wall lights, surface lights and halogen spots together on a and misses most on b; H's lights differ only in strokes that fragment (the module's own LIMITS note) |
| sockets | 355 (—) | — | — | — (33) | 110 | 137 | counts text matches of „rozetė" in annotations, not glyphs — unusable |
| switches | 169 | 6 | — | — | 29 | 363 | same |
| floor drains („trapas") | 21 (—) | — | — | — | — | — | a's legend row „Linijinis trapas" × 21 is implausible for two bathrooms |

So the only symbol kind the drawings define distinctly enough today is the diffuser; lights / sockets / switches need a per-legend-row template with a black-symbol path (the walls share the colour) — a counter project of its own, not a regex. Not fixed here.

## 6. Checks

- Touched tests: `test_missing_families_2026_10_25.py` (19, one per family behaviour + `_kilme` on every new row), `test_row_scorecard.py` (68 incl. the new mappings), `test_rules_profile.py`, `test_rules_split.py`, `test_samata_template.py`, `test_kill_model_rows_2026_10_25.py` (corpus guard: no row with a model / default number — green with the families).
- Full backend suite (`SAMATU_AUTH_DISABLED=1`) on the branch head: **5342 passed, 50 skipped, 0 failed** (8 min 42 s). The first full run found two: `test_calculator_audit` (module-scoped rooms computed before the function fixture pinned the 1,0 m² rule → a module-scoped `lt_aperture_1m2_module`) and `test_contribution_ledger` on objektas_r1 (the painted reveals row lost its tiled metres but kept the old room chain → the chain is rebuilt; a chain other than one Σ step is dropped, never bent).
- One plain rows pass (`eval_harness.py --rows --recompute`): §1.2 (the harness's own table agrees with the per-row dump).
- Cold run objektas_i A and B (scripts/cold_run, the contractor's uploads; no sąmata): `illegal: []` on both. New rows: „Papildomas sienų glaistymas (Q4 — visas paviršius)" blank („…pasirinkite glaistymo lygį Q4…"), „Demontavimo darbai (pertvaros, apdaila)" blank („Demontavimo plano komplekte nėra…"); no tile format, no tiled-wall opening and no diffuser legend in the text / vector facts, so no other family row (the plan's „oro padavimo difuzorius — 5 vnt." is a note in the room table, not a legend glyph). „Angokraščių glaistymas-dažymas" / „…apdirbimas GKP (struktūra)" 105,58 m unchanged (derived).
- `scripts/reading_scorecard.py` on the branch head: unchanged — vidaus durų poros 21/24, lauko durys 32/32, langai 29/30, praėjimai 2/4.
- Denylist grep over every staged diff: empty.

## 7. What blocks G2 next (in order of rows)

1. **Answered heights / perimeters in the harness** (ordered by the manager): 136 of his rows meet a blank row of ours. Until then the corpus mean measures the 3b gate, not the conventions or the families.
2. **objektas_b's ventilation material specification** (32 rows) — a supplier's BOM, not a takeoff family; either out of scope by founder decision (then the row should be excluded from the denominator like `no_truth_qty`, a scorecard rule change he decides) or a ventilation-plan reader that does not exist.
3. **GKP extras from the ceiling plan's geometry** (ceiling-level boundary lengths: a 11,16 m, d 9,94 m; niches in partitions a 9,11 m, h 13,68 m; thickening a 6,24 m²) — vector work in the geometry lane.
4. **Lights / sockets / switches counting** (a 38 + 38, b 69 + 69, h 20, d 9; c 75 sockets, d 33) — per-legend-row black-symbol templates; §5.
5. ~35 one-off lump rows (garage, décor, handles, rentals, materials) — nothing in a drawing quantifies them; a contractor template („Jūsų eilutės") is where they live.
