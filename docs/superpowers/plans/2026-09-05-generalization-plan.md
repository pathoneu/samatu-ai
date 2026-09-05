# Generalizacija: nuo „teisinga ant savų" iki „teisinga ant bet kurio" (2026-09-05)

> **Santrauka (LT).** „Treniruoti modelį" mums reiškia ne svorius, o penkis
> artefaktus, kuriuos iki šiol derinome ant tų pačių 4 projektų: skaitytojų
> promptus/lokatorius, formulių numatytąsias reikšmes, 60 šeimų koncepto
> lentelę, rangovo šabloną ir patį vertinimą. Visi penki buvo „hill-climbed"
> ant a–d — todėl ant a–d 7,8 %, o ant dviejų naujų — 14 % ir 50 % (H, G); jo eurų ±10 % ribose: 31,8 % ir 2,5 % (in-sample 39,3 %). Šiandien du nauji
> projektai (G, H) tapo pirmuoju tikru testu: išmatuota aklai, prieš ką nors
> keičiant. Kelias į 90 % yra ne vienas triukas, o disciplina: (1) train/dev/test
> taisyklė, (2) daugiau jo dokumentų, (3) skaityti brėžinį taip, kaip jį
> parašė autorius (tekstinis sluoksnis, autoriaus paties kiekiai), (4) jo
> apimties/konvencijų nustatymai kaip klausimai, ne kodas, (5) padengimas per
> šabloną ir koncepto lentelę, kuri auga TIK iš jo sąmatų. „90 %" apibrėžiame
> kaip „90 % jo sąmatos eurų ±10 % po jo 5 minučių patikros" — ne 90 % eilučių
> iš karto, nes du žmonės (architektas ir rangovas) tą patį brėžinį skaičiuoja
> 9–16 % skirtingai.

## Founder decisions (2026-09-05, after reading the plan)

- **No € in this work** — the metric is quantities only: share of his rows within ±10 %. Prices are his business. The € columns below stay as history; targets are restated in rows.
- **No more projects for now, no paid runs for a few days** — everything is measured on the cached extracts (`--recompute`) and offline PDF reads.
- **Never teach the engine from the sąmata** — the AI computes from the drawing; the sąmata is only used afterwards to CHECK. No calibration factors from his numbers (Move 5 is dropped), no rule tuned until it matches him. A rule changes only when the DRAWING shows it is wrong; his name→our name pairing (for the check and the template) carries no quantities.
- **Scope is a free-form choice of what to calculate** (works × rooms, on/off, remembered), not yes/no questions like „ar lubos jūsų?".
- Truth = his **quote** (his takeoff from the drawing); the act's contract-quantity column is the same number; acted quantities are a second column.

Approved order of €0 work: (1) tile band + paint, (2) his wording → ours, names only, (3) room areas from the PDF text when there is no table, (4) what-to-calculate choices at upload.

### Item 1 — DONE 2026-09-05: a wall is tiled or painted, never both

`universal_rules.calc_room_quantities`: the apdailos and legacy branches now
take the tiled zone out of the glaistymas/dažymas base, exactly as the
išklotinių branch always did (`_tile_zone_in_paint_base`; the part of the
openings inside the band is not deducted twice). Provenance
`_tile_zone_deducted_m2` on every room; ledger line „Dažoma sienų dalis virš
plytelių juostos"; an assumed band adds the LT note. Tests: 7 new
(`test_tile_band_paint.py`), 4 rewritten with the reason.

| project | walls before → after | combined paint before → after | headline MAE |
|---|---:|---:|---:|
| **G** (OOS, his row is walls only) | +29,3 % → **+5,1 %** | +70,7 % → +46,4 % (ceilings are out of his scope — item 4) | 50,0 → 25,7 |
| **H** (OOS) | +34,3 % → +14,7 % | +24,2 % → +11,2 % | 14,2 → 7,7 |
| a | −7,3 % → −8,3 % | −7,2 % → −8,0 % | 3,1 → 3,5 |
| b | unchanged (bathrooms are full tile) | | 19,6 |
| c | −0,1 % → **−21,5 %** | −4,9 % → −20,2 % | 7,5 → 16,6 |
| d | +3,8 % → **−21,0 %** | +2,8 % → −15,3 % | 2,3 → 9,7 |
| in-sample mean | | | 7,82 → 11,83 |
| out-of-sample pooled | | | 24,4 → 12,8 |

The exam improved and two in-sample projects got worse. Checked against the
DRAWINGS (not tuned to the sąmata): **c** — its fixture PDF says „Atskiras
brėžinys" for both bathrooms; their sheets are not in the bundle, the two
bathroom rooms are `default_fallback` guesses (4,5 and 23,25 m²) with a guessed
2,5 m band, and his tile row (55 m²) fits two ordinary fully tiled bathrooms,
not our 92. The old rule made a phantom bathroom's paint cancel a real
under-count. **d** — the lubų planas drops the bathroom ceiling to 2 390 mm;
the extract read that as the tile height while the room height stayed 2,82,
so the bathroom is in fact tiled to ITS ceiling; his paint line implies
≈ 23 m² we do not read anywhere (soffit faces at 2 390/2 510 mm, niche walls).
Both are now visible instead of cancelled. **The in-sample gate is therefore
restated: 11,83 % is the honest baseline; 7,82 % contained a compensating
error.** Registry notes carry both diagnoses.

### Item 1b — DONE 2026-09-05: ceilings from the table, walls on their own

Founder: „lubos dažomos visada taip, kaip iš eksplikacijos — negali būti
paklaidos; daryk atskirai lubas ir sienas." Applied in three places:

- **Engine.** The ceiling quantity was already anchored to the table's printed
  „Iš viso" (2026-09-02); now a table WITHOUT a printed total anchors to the
  sum of its rows (`vision_call`, same guard and tolerance), so a room Vision
  invents or drops cannot move the ceiling quantity. Walls and ceilings were
  already separate rows.
- **Truth.** Where a table exists, `ceiling_paint_total_m2` = the table's total
  and `walls_paint_total_m2` = his combined line − that total (b, d, H
  rewritten; the old „− billed GKP" derivation is superseded and noted). c and G
  have no table and say so.
- **Eval.** The combined line is printed but never pooled
  (`INFORMATIONAL_METRICS`): a walls error and a ceilings error can no longer
  cancel. The headline MAE is walls, ceilings, LED and floor total, each on
  its own.

| project | walls | ceilings | headline MAE |
|---|---:|---:|---:|
| a | −8,3 % | +0,02 % | 2,3 % |
| b | +29,5 % (vs 493,03 − 180) | 0,00 % | 15,9 % |
| c (no table, bathroom sheets missing) | −21,5 % | −16,8 % | 15,4 % |
| d | −21,0 % | 0,00 % | 7,8 % |
| **G** (OOS, walls-only scope) | **+5,1 %** | — | 5,1 % |
| **H** (OOS) | +17,1 % (designer's own figure would put us at −1,3 %) | 0,00 % | 6,4 % |
| in-sample mean | | | 9,76 % |
| out-of-sample | | | 6,13 % |

Read the walls column as the real open work: b (largest TP, known height
issues), c (phantom rooms), d (soffit faces not read), H (full-height windows
+ 2,82 m default height). Ceilings are closed wherever a table exists.

## 0. What was handed over, and what we did with it (€0 + two paid blind runs)

Two new projects, both from the reference contractor, drawn by two architects
the corpus has never seen. Codenamed at once; real names live only in the
private denylist (`backend/.confidential-terms`) and the private memory file.

| | Objektas G | Objektas H |
|---|---|---|
| Drawing | 16-page interior of a flat in a new-build (vector PDF, text layer) | 8-page house interior by a designer studio (vector PDF, text layer) |
| Room table (eksplikacija) | **none** — dimensions on the pertvarų planas; per-room areas as text on the lubų planas; apdailos legend states 202 + 18 m² of painted walls | **yes** — 11 rooms, 143,27 m²; pdfplumber reads it exactly (11/11, Σ 143,27) |
| Sheets | baldų, pertvarų, sienų apdailos, lubų, elektros, santechnikos, grindų planai; durų/grindjuosčių lapas; vonios išklotinės; vizualizacijos | išdėstymo, rozečių, apšvietimo, vandens įvadų, lubų, sienų dažymo (designer: 320 m²), grindų dangų (98,37 m²), pertvarų planai |
| Truth | **Atliktų darbų aktas** (20 rows): bathroom prep + tiles + WALL paint (239,4 m²), kampai 134,72 m; no ceilings, no floors, no wooden skirting in his scope | **Pasiūlymas xlsx** (24 quantified rows): GKP lubos 137,71; glaistymas/dažymas 412,88; kampai 412,94; Rotband 168,83; angokraščiai 63,23; tiles priced without quantities |
| Template (a–d) offers his rows | **40 %** (8/20) — 12 tile-work families a–d never had | **71 %** (17/24) |
| Frozen concept table maps his rows | 40 % | 67 % |
| Blind pipeline (first run, no tuning) | headline MAE **49,98 %** (6 metrics); his rows: **2,5 % of € within ±10 %**; 9 rooms read, one of them a phantom | headline MAE **13,7 %** (9 metrics); his rows: **31,8 % of € within ±10 %**, 67 % within ±25 %; 11 rooms read exactly |

Registered in `ground_truth/registry.yaml` with `out_of_sample: true`; the
harness now prints an **OUT-OF-SAMPLE MAE** line and never blends it into the
in-sample 7,82 % (the number a rule change is gated on).

**Two humans, one drawing.** On G the architect's legend says 220 m² of painted
walls, the contractor billed 239,4 (+8,8 %). On H the designer's plan says
320 m² of wall paint, the contractor's quote implies 275 (−14 %). Wall tiles
on G: 75 tiles × 0,72 = 54 m² drawn, 46,06 m² billed (gross vs net). And his
own act shows 179,54 m² of the 239,4 actually painted at the first act. There
is no single „teisingas skaičius" — there is HIS number, with a ±10 % band,
and everything else is a reference to show beside it.

## 1. Blind results — the generalisation gap, measured

### 1.1 Objektas H (house, clean room table) — blind

| his row (€ of his quote) | his | ours | verdict | class |
|---|---:|---:|---|---|
| Sienų, lubų glaistymas/dažymas (€ 8 877, 35 % of the quote) | 412,88 | 512,69 | +24 % | **F + R + C**: both bathrooms carry tiles to 2,5 m (22,5 + 21,0 m²) AND a full painted wall (25,4 + 23,7 m²) — a double count worth ≈ 49 m²; windows deducted at standard 1,2×1,5 sizes while the house has floor-to-ceiling glazing (his „Grindų betonavimas prie langų rėmų 11,72 m" says so); height 2,82 m is a default labelled `section_average` on a PDF with no section |
| GKP monatavimas ant lubų (€ 4 544) | 137,71 | 136,37 | −1 % | ✓ |
| Sienų lyginimas Rotband (€ 2 195) | 168,83 | 110,83 | −34 % | **C/F**: which walls get Rotband is a convention we guess |
| Dažymo kampų montavimas (€ 1 652) | 412,94 | 437,78 | +6 % | ✓ |
| Angokraščių apdirbimas GKP (€ 1 265) | 63,23 | 70,0 (140 as scored) | +11 % real, +121 % as scored | **scorecard/mapping**: we emit the same 70 m twice as two operations (struktūra + glaistymas-dažymas); the frozen table sums both against his one row |
| Nišų formavimas iš GKP (€ 963) | 33,19 | 30,37 | −8 % | ✓ (LED niche lengths read off the lubų planas) |
| GKP pertvarų įrengimas (€ 735) | 19,35 | — | missing | **M**: engine has no partition-m² family; the pertvarų planas carries the wall lengths as text |
| Angų beapvadinėms durims (€ 716) | 40,94 | 18,2 | −56 % | **mapping + R**: our row exists („Durų angų paruošimas beapvadinėms durims") but the table does not pair it; and we prepare ~4 doors where he bills ~8 |
| Magnetinis profilis, karkasas + apdirbimas (€ 984) | 31,26 + 31,26 | blank | unmapped | **M**: the track is drawn with its length on the lubų planas; our row is a „suveskite" placeholder |
| Šviestuvų/difūzorių apdirbimas (€ 378) | 27 | 30 (10 as scored) | +11 % real | **mapping**: our „Šviestuvų apdirbimas 30" is not in the table |
| Priglaistomi šviestuvai (€ 240) | 20 | 30–35 | +50 % | **R**: symbol count on a dense apšvietimo planas |
| Potinkinės sistemos, 2 rows (€ 420) | 2 + 2 | 2 + 3 | unmapped | **mapping**: our rows carry his numbers under other wording |
| Langų rėmų sandarinimas (€ 300), grindų betonavimas prie langų (€ 82) | 74,95 m, 11,72 m | — | unmapped | **M + R**: window perimeter / full-height widths — readable once windows are |
| Smulkūs darbai, bortelis, nišos pertvarose (€ 590) | 1, 11,8, 13,68 | — | — | **U**: „Jūsų eilutės" |

By € of his quote: 31,8 % within ±10 %, 35,3 % within ±25 % (the one paint
row), 16,8 % way off, 7,4 % missing, 8,6 % unmapped. **Half of the money that
is wrong is not a reading problem**: two vocabulary pairings (angokraščiai,
šviestuvų apdirbimas, potinkinės — ≈ € 2 100) are right numbers under other
words; one engine bug (tiled bathroom walls also painted, ≈ 49 m²) and one
unknowable-from-plan fact (floor-to-ceiling windows) account for most of the
paint gap; two families (GKP partitions, magnetic track) are drawn with their
lengths as text and simply never computed. What the reader actually misread:
the light-fixture count (+50 %) and the door count behind the frameless-door
row. The room table, LED niches, ceilings and corners were right first time.

### 1.2 Objektas G (flat, no room table, bathroom + walls scope) — blind

Rooms: 9 read by Vision (Σ 99,0 m²). Six areas match the lubų planas
annotations exactly (37,86 · 14,26 · 10,05 · 3,76 · 10,55 · 6,78) — Vision
found the text; the two bathrooms drifted (3,11 vs 3,52; 7,01 vs 7,25) and a
**third bathroom appeared** (5,64 m², 11,1 m perimeter) that the flat does not
have. It carries 18,5 m² of tiles, 30 m² of paint and one of every fixture —
every „+50 %" in his santechnika section (WC frames 3 vs 2, drains 3 vs 2,
slopes 3 vs 2) is that one room.

| his row (€ of his act) | his | ours | verdict | class |
|---|---:|---:|---|---|
| Sienų glaistymas/dažymas (€ 5 027, 43 % of the act) | 239,4 | 408,56 | +71 % | **C + F + R**: 99 m² of ceilings we paint are not his scope here (C); walls 309,5 vs 239,4 — the three „bathrooms" are tiled to 2,4 m AND fully painted, 78,5 m² of wall paint where ≈ 12 m² sits above the band (F); take that out and walls land at ≈ 243 m², **1,5 % from his number** — the phantom room (R) is inside those 78,5 |
| Glaistymo kampų statymas (€ 539) | 134,72 | 299,78 | +122 % | unmapped by wording; **F/C** to investigate on dev: corners in tiled rooms and (probably) around openings — H's corners were +6 %, so it is the room mix, not the constant |
| Plytelės – sienos 60×120 (€ 2 073) | 46,06 | 61,46 | +33 % | unmapped by wording; **R** (phantom bathroom 18,5 m²) + **C** (kitchen 4,4 + laundry 5,1 m² splashbacks he does not bill) → without them 42,8 m², −7 % |
| Plytelės – grindys 60×120 + 60×60 (€ 968) | 21,5 | 19,52 | −9 % | unmapped **by wording only** — the number is within ±10 % |
| Siūlių glaistas + silikonas (€ 135) | 67,56 | 81,0 | +20 % | unmapped by wording (our four „fugavimas" rows) |
| Plytelių pjovimas 45° (€ 362) | 12,08 | 14,4 | +19 % | unmapped by wording |
| Skylių pjovimas plytelėse (€ 224) | 32 | 59 | +84 % | unmapped by wording; **F**: the per-fixture hole rule over-generates |
| Plytelės – grindjuostės (€ 296) | 26,87 | 8,42 | −69 % | unmapped by wording; **F**: the architect's own sheet states 24,97 m — our rule counts a fraction of the tiled rooms |
| Hidroizoliacija (€ 237) | 39,5 m² | unit mismatch | missing | **F**: emitted in another unit; CLAUDE.md §1.12 already gives the m² formula |
| Dušo latakai, nuolydžiai, WC rėmai (3 rows, ≈ € 740) | 2 · 2 · 2 | 3 · 3 · 3 | +50 % | **R**: the phantom bathroom |
| GKP sienutės ×2, bidė (€ 500) | 1 · 1 · 1 | 1 · — · 1 | ✓ / missing / ✓ | one of two GKP boxes paired |
| Trapas 2, betonavimas 2, šildymo remontas 1 (€ 560) | — | — | unmapped | **M / U**: „Trapas" is written on the santechnikos planas (countable); the other two are U |

By € of his act: **2,5 % within ±10 %**, 49 % way off (the paint row alone is
43 % of the act), 44,6 % unmapped, 3,7 % missing. Read the unmapped column
again: **five of those twelve rows are already right or nearly right under
our wording** (floor tiles −9 %, 45° cuts +19 %, joints +20 %, wall tiles −7 %
once the phantom room and the splashbacks are out). His tile labels go by
FORMAT (60×120, 60×60), ours by ROOM (vonios / kitų) — and the frozen table
only knows the wording of a–d.

### 1.3 What the two blind runs say together

| finding | H | G | class | was it visible in-sample? |
|---|---|---|---|---|
| **A wall tiled to 2,4–2,5 m of 2,82 m keeps its full painted area** — `universal_rules` zeroes paint only when the band reaches the ceiling (`_walls_full_tile`, the 2026-07-28 fix) | ≈ 49 of the +100 m² | ≈ 66 m² — the whole wall gap | **F** | The same overlap sits in objektas_c and objektas_d bathrooms today; the combined walls+ceilings metric never isolated it |
| Ceiling height 2,82 m is a hard default that wears the label `section_average` | 11/11 rooms | 9/9 rooms | F (label) | yes |
| Scope: ceilings, splashbacks, rooms he does not bill | bathrooms tiled, katilinė | 99 m² ceilings; kitchen + laundry tiles | **C** | invisible — his a–d quotes were whole-house |
| His wording ≠ ours (tiles by format, potinkinės, apdirbimas, kampų statymas, latakai) | ≈ € 2 100 | ≈ € 3 500 | vocabulary | the frozen table was written against a–d |
| Families drawn as TEXT but never computed: GKP partitions, magnetic track, trapai, hidroizoliacija m², tile skirting | € 984 + 735 | € 560 + 237 + 296 | **M** | — |
| No room table → Vision invents a room | — | phantom bathroom: +30 m² paint, +18,5 m² tiles, +1 of every fixture | **R** | the 2026-08 ablation predicted ≈ 15 % for „no table"; on a small bathroom scope it is 50 % |
| Window sizes default to 1,2 × 1,5 without a schedule | floor-to-ceiling glazing (his „betonavimas prie langų 11,72 m") | 5 windows | **R** | in-sample PDFs had schedules |
| Symbol counts | šviestuvai +50 % | skylės +84 % | **R** | known ceiling (deep-research claims) |

Headline: in-sample **7,82 % unchanged**; out-of-sample **14,19 % (H) and
49,98 % (G)**, the harness's pooled `Out-of-sample` line 24,42 % (7 headline observations); his € within
±10 %: **31,8 % and 2,5 %** against 39,3 % in-sample. The two runs cost $8,10
and $12,91 by the runner's list-price estimate (12 and 25 minutes).

**The order of the money.** On both projects the largest single error is one
formula (tile band + paint), the second is scope he knows and we cannot see,
the third is his words for numbers we already have. Reading — the thing the
word „training" points at — is fourth: one invented room, default window sizes,
two symbol counts. That ordering is the plan.


Error taxonomy of every row that is not within ±10 %:

| class | meaning | fixable by |
|---|---|---|
| **R** read | room area / perimeter / height / opening count misread | reader redundancy (text lane + Vision + author's own figures), check sheet |
| **M** missing | his family never emitted by the engine | concept table + rules, grown from his sąmatas |
| **C** convention / scope | we compute the drawing, he bills his scope (walls only, net tiles, per-format tiles, 3 m split, „su dažų kaina") | per-contractor settings, upload questions |
| **U** unknowable | not on the drawing (rentals, repairs, walk-through items) | „Jūsų eilutės" — typed by him, remembered |
| **F** formula / default | right inputs, wrong constant or rule | measured rule change on train, verified on dev |


## 2. Why in-sample ≠ out-of-sample (the diagnosis)

The pipeline has no weights we could train. Its knowledge lives in five
artefacts, and every one of them was tuned while looking at objektas_a–d:

1. **Reader prompts, locators, page-type rules** — written against 4 flattened
   raster PDFs from 2–3 architects (the 2026-08-23 ablations already showed
   what a missing table or a scan does: 15 % / 12 % → fixed, but only for the
   ways a–d could be broken).
2. **`universal_rules.py` defaults** — door sizes, reveal formulas, tile heights,
   the iki/virš 3 m split, garage handling: HIS conventions on HIS four houses.
3. **The frozen concept table** (60 families) — hand-written against a–d; G's
   tile-work vocabulary is simply absent (12 families).
4. **The family template** — built from a–d; offers 73 % leave-one-out, 40 %
   on a bathroom-heavy flat.
5. **The eval itself** — 7,82 % is the mean over the projects the rules were
   fitted to. It cannot fall when a fix over-fits; it can only rise when a fix
   breaks a–d. The row scorecard (26,5 %) has the same blind spot.

None of this is a model problem: Opus 5 is the champion and Fable 5.1 lost
twice (`2026-09-02-fable51-benchmark.md`). It is a **methodology problem** —
train and test were the same four files — plus a **coverage problem** (his
vocabulary is larger than our corpus) plus a **scope problem** (a drawing
never says what a contractor will bill).

## 3. What „90 %" should mean

**Definition (founder, 2026-09-05: quantities, no €):** on projects the engine was never tuned on, the share
of the contractor's sąmata **rows** whose quantities we reproduce within ±10 %
(`eval_harness.py --rows`, `out_of_sample` block only), measured
**after his ≤5-minute check** — his three upload answers and room
confirmations count; quantities he had to type do not.

Why this and not „90 % of rows on first read":
- the two-humans baseline above puts any first-read number in a 9–16 % band;
- 25–60 % of his rows are U-class on every project so far (rentals, repairs,
  walk-through items) — no reader will ever read them;
- his € concentrate in ~10 families (paint, GKP ceilings, tiles, Rotband,
  kampai, angokraščiai) — those ARE readable, and they are where 90 % is won.

**Staged targets** (out-of-sample € share within ±10 %, after check):

| projects scored blind | target | what has to be true |
|---|---|---|
| 2 (today) | **H 31,8 % · G 2,5 %** | baseline — nothing changed yet |
| 4 | ≥ 50 % | Move 2a/2c shipped and measured on G/H; scope questions live |
| 8 | ≥ 70 % | concept table + template grown from 8 sąmatas; calibration gate has ≥3 projects per family |
| 15 | ≥ 90 % on R+F+C classes; U typed | second contractor in the set |

## 4. The plan — six moves, ordered by evidence per euro

### Move 0 — Protocol (this week, €0): train / dev / test is law
- **train** = objektas_a–d: the only projects a rule, prompt, concept or default
  may be tuned on. **dev** = the newest blind-scored project (today: G) —
  diagnose there, fix on train, re-measure on dev; when its fixes land it
  joins train. **test** = every other out-of-sample project (today: H;
  sernu stays held out for the row scorecard) — scored, never studied.
- Every new project: **blind run first** (≈ €0,5–3,7 each — a–d cost $0,47–3,65),
  score, taxonomy, then and only then fix. `out_of_sample: true` in the
  registry (done today); the harness prints the OOS number separately (done).
- A change ships only if: in-sample 7,82 % / 26,5 % unchanged or better, OOS
  not worse, and the row it targeted moved on dev.

### Move 1 — Data: his documents are the training set (€0 to us, the biggest lever)
- Ask the contractor for **every past project that has drawing + sąmata (or
  aktas)** — 10–15 more. Each one grows the template residual, the concept
  table and the calibration learner's evidence (its promotion gate needs ≥3
  projects agreeing in direction — with 4 it has never fired).
- Ask for **one project from a second contractor** — every caveat in
  `registry.yaml` says „single contractor"; per-contractor settings (Move 3)
  cannot be told apart from universal rules until a second one exists.
- Prefer his **quotes** as truth (his takeoff from the drawing — what the app
  replaces); keep **acts** as a second column (G: 179,54 of 239,4 painted at
  act 1) — actuals differ from quotes by 25 % on that row, so „truth" must
  name which one it is.
- Make „upload your sąmata" a first-class action in the app (a parser endpoint
  for xlsx/PDF → `line_items`; today `scripts/parse_all_samatas.py` runs by
  hand and does not read an act's group-column layout).

### Move 2 — Read the drawing the way its author wrote it (reader redundancy)
- **2a. Author's own figures as a second lane.** New-architect PDFs carry the
  designer's takeoff as text: G — „Glaistoma dažoma 202 m² + 18 m²", skirting
  53,69 m + 24,97 m, laminate 76,65 m², tile counts per room; H — „Sienų dažai
  320 m²", „Grindys 98,37 m²". Read them with pdfplumber (€0), never as the
  answer, always as the reconciliation partner shown beside ours on the check
  sheet („Architektas nurodo 220 m² · mes 235 m²").
- **2b. Dimension-string lane for table-less plans.** G's pertvarų/grindų
  planai carry 18–22 machine-readable dimension strings and per-room areas
  on the lubų planas (14,26 · 3,52 · 37,86 · 10,05 · 3,76 · 7,25 · 10,55 ·
  6,78). The 2026-08 ablation put „no table" at 15 % MAE with guessed areas;
  a text lane turns it into a table.
- **2c. Page types of other authors.** Verify the classifier and locators on
  both PDFs (išdėstymo / rozečių / apšvietimo / vandens / grindų dangų /
  pertvarų planai; išklotinės + vizualizacijos). Corpus-title assumptions are
  the cheapest R-class bug to find.
- **2d. Disagreement is a flag, not an average.** Two lanes > 10 % apart → the
  room is shown on the check sheet with both numbers and its evidence crop.
- Not on this list, on purpose: more voting (its ceiling is documented), a
  trained detector (300–400 labelled drawings), zoom loops, model swaps.

### Move 3 — Conventions as settings, asked once, learned forever („jūsų standartai")
The largest OOS deltas are C-class and cost nothing to read — they must be
asked, then remembered per contractor:
- **Scope:** which rooms are yours (G: bathrooms + walls only); are ceilings
  yours (G: no); floors; skirting (wooden vs tile).
- **Measuring rules:** openings deducted or not; walls iki/virš 3 m split;
  tiles net (his 46,06) vs gross (drawn 54); „su dažų kaina" (materials
  folded into the work rate); GKP ceilings = painted ceilings identity.
- **Where:** three upload questions exist today (object type, ceiling height,
  work families). Add „Kurios patalpos jūsų?", „Lubos: dažomos / ne jūsų /
  įtempiamos", „Sienų plotas su angomis ar be?" — each with the consequence
  written next to it (design „Rimo kelionė"). A choice repeated ≥3× becomes
  that contractor's default (the calibration learner's guardrail, reused).

### Move 4 — Coverage grows only from his sąmatas (template + concept table)
- G names 12 tile-work families a–d never had: tiles per format (60×120 /
  60×60), 45° cuts (m), hole drilling (vnt), tile skirting (m), silicone joints
  (m² = tile area), waterproofing (m²), bathtub cladding, shower slope, drains.
  The computable ones get engine rows (tiles per format from the grindų and
  išklotinių sheets; silicone = tile area; waterproofing = wet-room floor +
  splash zone — CLAUDE.md §1.12 already states the formula); the rest are U.
- Rule: a concept enters the frozen table **only from a contractor row**, never
  from our output — the council's hill-climbing warning stands. Re-run the
  template hold-out after every 2 new sąmatas.

### Move 5 — Calibration: DROPPED (founder rule 2026-09-05)
Factors derived from his quantities would be teaching the engine the answers.
The engine computes from the drawing; the sąmata checks.

### Move 6 — Cadence and budget
Per project: blind run → score → taxonomy → fix on train → gates → promote.
Weekly number: OOS € share within ±10 % (after check) + OOS family MAE.
Budget: ~€3 per blind run + ~€3 per fix validation ≈ €30–60 / month at
5–10 projects.

## 5. What NOT to do (and the evidence)
- Train or fine-tune a vision model: 300–400 labelled drawings needed
  (arXiv 2411.03707); we have 6–8 projects.
- Swap models: Fable 5.1 lost twice; Sonnet 5 unusable (memory).
- Add voting or zoom loops: measured ceilings (`2026-09-04-deep-research-claims.md`).
- Tune anything while looking at a test project; add concept aliases from app
  output; average OOS into the in-sample mean.
- Chase 100 %: the architect and the contractor already disagree by 9–16 %.

## 6. Questions for the founder (each one changes the plan)
1. Ar sutinki su „90 %" apibrėžimu: jo sąmatos **eurų** dalis ±10 % ribose,
   matuojama tik ant naujų projektų, **po jo 5 min patikros**?
2. Ar gali gauti iš rangovo **10–15 senų projektų** (brėžinys + sąmata arba
   aktas) ir **vieną kito rangovo** projektą? Tai didžiausias svertas.
3. Mokamų paleidimų biudžetas: ~€30–60/mėn. (≈ €3 už aklą paleidimą, €3 už
   pataisos patikrą) — gerai?
4. Tiesa = jo **pasiūlymas** (kiekiai iš brėžinio) ar **aktas** (faktas)? Siūlau
   pasiūlymą; aktą laikyti antru stulpeliu.
5. Ar rangovas sutiktų atsakyti į 3–5 apimties klausimus per projektą (lubos
   jūsų? kurios patalpos? sienos su angomis?), ar app'as turi spėti pagal jo
   istoriją?
6. Ar G tipo apimtis (tik vonios + sienos) jam būdinga butuose? Tai lemia, ar
   „per patalpą" apimtis reikalinga jau dabar.
7. Ar architekto/dizainerio brėžinyje nurodyti kiekiai (320 m², 220 m²) jam
   yra naudinga nuoroda šalia mūsų skaičiaus?

## 7. Next four weeks (if the answers are „taip")
**Week 1 — protocol + the two rule fixes the blind runs paid for (≈ €0 + 2 validation runs)**
- Tile-band paint deduction (F): paintable wall = perimeter × (H − band) in
  rooms with a partial band. Gate: in-sample 7,82 % must not worsen (c and d
  will move — check their truth), then G walls 309 → ≈ 243 and H paint
  512 → ≈ 463 on the cached extracts (€0), then one fresh run each later.
- Height honesty: `section_average` → „assumed 2,82 m" on the check sheet and in
  the ledger; the upload question already exists, its default must be visible.
- Send the contractor: (a) the data ask (Move 1), (b) five scope questions on
  G and H (ceilings yours? katilinė painted? splashbacks yours? windows to the
  floor? Rotband on which walls?) — his answers are the truth for every C row.
- Metric: OOS block live (done); registry carries both blind results (done).

**Week 2 — his words, and rooms from text (€0)**
- Grow the frozen concept table from G/H rows only (tiles by format, potinkinės,
  apdirbimas, kampų statymas, latakai, trapai); re-run the template hold-out;
  re-derive the template from a–d + G + H. Expected: G unmapped 44,6 % → < 10 %
  of €, and ≈ € 3 000 of G/H rows scored as they stand.
- Lubų-planas area lane: when no table, room areas from text annotations
  (G: 8 numbers, all on one sheet) before Vision invents any; a phantom-room
  guard — a room whose area appears on no sheet is low-confidence and flagged
  on the check sheet.
- Author's-figure lane: legend totals (220 m² paint, 320 m², 53,69 m skirting,
  76,65 m² laminate) shown beside ours on the check sheet — never as the value.

**Week 3 — families that are drawn but never computed, and scope as questions**
- GKP partitions (pertvarų planas lengths × H), magnetic track length (lubų
  planas), trapai (santechnikos planas labels), hidroizoliacija in m² (§1.12),
  tile skirting from the grindų planas, window perimeter once windows are read.
- Upload questions: „Kurios patalpos jūsų?", „Lubos: dažomos / ne jūsų /
  įtempiamos", „Langai iki grindų?", „Sienų plotas su angomis ar be?" — each
  with its consequence; answers become the contractor's defaults after 3×.

**Week 4 — measure again, on new ground**
- The next project he sends: blind run FIRST (it is the first true test after
  today), scored, taxonomy; contractor session on G/H with the check sheet —
  timed — gives the first „after his 5-minute check" number.
- Decide calibration candidates only where ≥3 projects agree; write the
  8-project targets from the measured curve, not from hope.
