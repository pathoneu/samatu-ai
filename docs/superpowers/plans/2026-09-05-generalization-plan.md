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

**Anchor backfill (same day, founder: „taip ir padaryk").** Old cached
extracts predate the anchor. `scripts/backfill_ceiling_anchor.py` adds it
from the fixture PDF's text-layer table (b: „Bendras namo plotas (su garažu)"
224 → billed 180 after the unpainted garage, as his sąmata bills), or — on a
raster PDF — from the Vision pre-pass total when it agrees with the rows within
1 % (a: 165,61; d: 41,28), under the same guard. The pipeline does the same on
a fresh run. The ceiling metric now reads the BILLED Lubų rows, so a is
+0,00 %. Ceilings: a/b/d/H 0,00 %; c −16,8 % (no table, sheets missing).

Read the walls column as the real open work: b (largest TP, known height
issues), c (phantom rooms), d (soffit faces not read), H (full-height windows
+ 2,82 m default height). Ceilings are closed wherever a table exists.

### Item 2 — DONE 2026-09-05: his words → ours, names only

The frozen concept table grew 60 → 81 from the G/H rows (his wording only; no
quantity enters the engine): tiles by format, potinkinė/virštinkinė dalis,
angokraščiai split in three (his one „apdirbimas GKP" row was scored against
our two operations summed → +121 %, now +11 %), magnetinis profilis = TRACK,
eleven admitted gaps named. The scorer learned „parents with parts" (his one
row for work we emit as several) without changing how objektas_a scores.
Result: unmapped rows G 12 → 0, H 11 → 0; H rows within ±10 % 22 % → 29 %;
G's two former „hits" were lucky pairings and now read honestly (+200 % /
+100 % — the phantom bathroom). In-sample unchanged. Full report:
`research/2026-09-04-row-scorecard-baseline.md`, mapping-change addendum.

Fallout found on the way (engine, next): Rotband is 30 % of the PAINTED wall
(a constant calibrated on objektas_a's sąmata in June — the kind of number the
founder's rule now forbids). Tried and reverted the same day: basing it on all
finished walls incl. tiled zones (a −8 %, b +15 %, d +5 %, H −34 %, c +124 %)
— gypsum levelling belongs under paint, not under wet-room tile, and H's gap
is the SHARE (a brick house with few GKP partitions levels ~46 % of its
walls, not 30 %): readable from the pertvarų planas (which walls are new
GKP), so it goes to item 3, and as a choice to item 4; the tile-skirting rule counts a fraction of the tiled rooms (G −69 %;
the architect's sheet says 24,97 m); hole drilling over-generates (G +84 %);
hidroizoliacija is emitted in vnt, his row is m².

### Item 3a/3b — DONE 2026-09-06: room areas from the plan text when there is no table; a room no label supports is flagged

**What the drawing offers.** Objektas G prints no patalpų eksplikacija, but the
lubų planas carries every room's area as TEXT („37.86 m²" standing inside the
room) — exact, deterministic, free to read. Vision had read 7 of the 8 correctly,
mis-read two (3,11 for 3,52; 7,01 for 7,25) and invented a ninth room (a third
bathroom, 5,64 m², with its own tiles, paint and one of every fixture).

**The lane** (`backend/extractor/plan_area_annotations.py`, text layer only, no
model call). Engine: **pypdfium2** (already a dependency, Apache/BSD) — pdfplumber
needed 58–75 s for three pages of the 22 MB drawing because pdfminer parses the
object streams the renders live in; PDFium reads the same pages in 0.1 s, the
whole sheet set in 0.6 s. Character boxes are converted into the display frame
the crops use (/Rotate applied); every text DIRECTION on a sheet is analysed in
its own frame (a plan's vertical dimension strings neither outvote nor pollute
its horizontal labels; a's grindų planas is a landscape drawing turned 90° on
a portrait page with no /Rotate — its legend reads at π/2 and is read there).
A „N.NN m²" that stands alone, or beside a ROOM NAME, is a room label; beside a
material / total / count word (danga, laminat, vnt, sienų dažai, bendras
plotas…) it is not. Digits are re-joined from characters (CAD exports split
„7.25"). Sheets are taken richest-first and a sheet whose values repeat ≥ 60 %
of the accepted ones is the same rooms drawn again.

**Reconcile — WHERE the label stands first, its VALUE second.** The floor plan
the rooms were outlined on and the lubų planas share one frame on G (every
label falls inside a room outline of the pertvarų planas). When ≥ 60 % of the
labels fall inside some outline: a label inside exactly one room IS that room's
area (confirmed within ±3 %, otherwise adopted — the Vision figure is kept for
the sheet); a label inside SEVERAL outlines means the outlines overlap — the
closer room takes it and the other is the same room drawn twice
(`_area_unconfirmed_reason = duplicate_of:NN`), kept, never deleted; a label
inside NO outline is a room the model never returned. Without a shared frame,
value only: ±3 % confirm, one unclaimed label within ±20 % adopt, else
`_area_unconfirmed` (`no_label`). Σ labels becomes `_ceiling_anchor` („plano
užrašų suma") so an invented room cannot move the ceilings. Warnings
(`lane_warnings`, shared by pipeline and backfill): duplicate → high, no label
→ high, unclaimed label with a shared frame → medium („greičiausiai trūksta
patalpos; pridėkite ją, jei ji jūsų"). Runs in Step 2.44 only when
`eksplikacija_merged_rooms == 0`; `scripts/backfill_plan_areas.py`
(`--refresh-lane`, `--refresh-author`) applies it to cached extracts.
Check sheet: `plotas_saltinis = plano_uzrasas` crops the label itself; the
duplicate room says „persidengia su patalpa 06 … greičiausiai ta pati patalpa
antrą kartą"; provenance chip „užrašyta plane"; RoomCard confidence high.

**What G actually is (read, not guessed).** Ten room labels on the lubų planas
(pdfplumber had found eight): 8 fall inside one Vision outline each, „7.25"
inside TWO (06 „Vonios kambarys" 7,01 and 07 „Vonios kambarys" 5,64 — the
bathroom returned twice; 06 takes it, 07 is flagged a duplicate), and two
labels — 6,90 and 3,60 m², bottom of the plan — inside no outline: two rooms
the model never returned (a hallway and a small room by the look of the plan).
Σ 104,53 m² = the ceiling anchor. Walls +5,1 % → +3,6 % (unchanged by the
final geometry pass: the duplicate still counts until he switches it off —
item 4 gives him the switch); OOS pooled 5,85 %; in-sample 9,75 % unchanged
(a/b/d/H have tables — the lane never runs; c has no labels at all).

**By-product — the scorecard's paint family, names only.** The frozen table had
ONE „glaistymas/dažymas" concept and paired his rows greedily with our single
best row: G's walls-only row was scored against our walls + ceilings (+43 %,
while the walls row alone is +3,6 %), and a's „iki 3 m" / „virš 3 m" rows were
crossed with the wrong height band. Now four leaves (Sienų / Lubų × iki / virš —
the rows we emit) + five parents in his aggregations (walls only — G; ceilings
only; combined per height band — a; everything in one row — b, H), pooled by the
scorer's existing `parts` rule. Within-10 % counts of a–d unchanged; a's and b's
paint rows now compare like with like (a −10,9 % / +20,6 %, b +23,1 % — real
gaps, previously hidden); G rows ±10 % 0 → 5 % (1 of 20). Table 81 → 89.

**Still inside item 3:** 3c — the author's own figures (legend totals such as
„laminuota grindų danga 76,65 m²") shown beside ours on the general facts
panel, never as the value; the Rotband share from the pertvarų planas (masonry
vs GKP) instead of the 30 % constant.

### Item 3c — DONE 2026-09-06: the designer's own figures beside ours

**What the drawing offers.** Designers total their own drawing in legends:
G „Glaistoma dažoma (baltai) 202 m²" + „(akcentinė spalva) 18 m²", „laminuota
grindų danga 76,65 m²", „Grindjuostės … 53,69 m", „Sienų plytelės 60×120 –
38 vnt."; H „Sienų dažai 320 m²"; a „Parketlentės 135 m²", „Grindjuostės h=60
mm 56 m". A second reading of the same drawing — worth showing, never worth
copying (his 239 m² of walls vs the designer's 220 m² is the 9–16 % two
humans disagree by).

**The reader** (`read_author_figures`, same module, pure text layer): a number
+ unit (m², m, vnt, kompl) whose own line — or the label-like text lines just
above it — names a material family (paint, floor covering, skirting, tiles,
wallpaper, cornice, LED, GKP). Lines are rebuilt from characters; rotated
dimension fragments („0.610", „5 0 0") interleaved with the legend are skipped
when looking for the label and scrubbed from it; heights („h 1,20 m", „H 0.3m")
are refused; the ROOM-AREA labels the room lane owns are excluded; a note
paragraph („*PASTABA: …") never adopts the number below it (objektas_b labels
its rooms under such notes — the first version misread ten of them as paint);
a second statement on one rebuilt line starts after the first quantity, while
„Plytelių klojimo 13vnt. 3.95 m²" stays one statement. Read in the same single
PDFium pass as the room labels (`scan_text_layer`, `_meta.text_layer_scan_s`).
Stored as `_autoriaus_kiekiai` on every extraction (tables or not). Yield on
the fixtures: G 12 (paint 202 + 18, skirting 53,69 + tile skirting 24,97,
laminate 76,65, tile zones and counts), a 5 (the turned legend: parketlentės
135, grindjuostės 56, three tile counts), d 1, H 1, b/c 0.

**On the sheet.** General facts panel, „Projektuotojo užrašyti kiekiai": each
figure with its crop, and OUR number for the same family beside it (walls iki +
virš summed, all tile rooms summed; `lib/roomSheet.authorFigureRows`), paired
ones first; when we emit nothing comparable the sentence says so and offers
the typed row. The ceiling row of the panel now also names its source when the
anchor is the plan labels' sum. No value is taken from any figure.

### Item 4 — first slice DONE 2026-09-06: „ką skaičiuoti" as the contractor wants it

**Founder's ask.** „Reikia padaryti kažkokių daug pasirinkimų ką skaičiuoti ko
ne, kad būtų freeform kaip ką nori rangovas" — choices, not odd yes/no
questions; scope questions at upload; the choice remembered after three uses.

**The object** (`_apimtis` on the project; `rules_override.apimtis` on every
compute — `frontend/src/lib/scope.js`, `backend/extractor/scope.py`):
`patalpos_ne` (rooms he does not do), `darbai_ne` (work families he does not
do), `lubos` (dažomos / ne mūsų / įtempiamos, project default), `sienos_angos`
(atimti / neatimti). Absent = as the drawing says; a room's own Prielaidos flag
wins over the project default. Stateless: derived on every compute, nothing is
written into the rooms for keeps — switch back and the drawing's numbers return.

**Enforced server-side** (so the sheet, the exports and the template agree):
an excluded room stays in `patalpos` marked `_neskaiciuoti`, its computed
quantities zeroed, and the builder, the totals, the paint consolidation and the
ceiling anchor skip it (the anchor subtracts its area as a named step
„− neįtrauktos patalpos"; the ledger lists it „Neįtraukta jūsų pasirinkimu");
a family that is off drops its rows and their materials after the build
(server twin of `workFamilies.js`, unknown sections always stay); „lubos ne
mūsų" empties every painted ceiling without an explicit room flag
(`_ceiling_paint_source = pasirinkimas`); „įtempiamos" marks every room stretch
unless its own flag says no; „sienos be angų" turns the openings deduction off
through the room rules (`deduct_openings`). Wired into `/recompute-interior`,
`/api/recompute-quantities` (a Prielaidos edit cannot undo the scope) and the
extraction end (upload-time choices). Every frontend sender folds the scope
into its overrides (`rulesWithScope`): room sheet, assumptions panel, rules
panel, interior page, upload.

**On the screen.** Room sheet: „Ši patalpa: Skaičiuoju / Neskaičiuoju" above
the facts — the one control the duplicate-room warning asks for. General facts
page: „Ką skaičiuoti" — lubos, sienų plotas, darbų sritys, each option saying
what it does to the sąmata; changes recompute at once. Upload: lubos and sienų
plotas next to the families; after three projects with the same choice the
screen pre-selects it and says „Kaip jūsų 3 paskutiniuose projektuose"
(`lib/scopeMemory.js`, browser storage).

**Second slice (same day).** Per-room × family: one room can drop apdaila,
grindys or plytelės (`patalpu_sritys_ne`) — the room-driven families; its
fields for that family are zeroed by `FAMILY_ROOM_FIELDS`, the predicate
fields say „Neįtraukta jūsų pasirinkimu" in the ledger, and the tile piece
counts (nuolydis, lentynėlės, skylės, silikonas, hidroizoliacija) skip a room
whose tiles are off. Plumbing and electrics are symbol counts per project, so
they stay project-level (the note says so). **Rotband is a choice, not a
constant**: nėra / dalis % / visos dažomos sienos (`rotband`, `rotband_dalis`),
default a stated 30 % assumption whose row note tells him to set his share —
the adjacency count of GKP partitions was measured too coarse to stand in for
wall types (a +15 %, b −69 %, H −43 % against his rows), so no reading-based
share is claimed. **A missed room becomes one click**: the labels no room
claimed are listed on the general page with their crop and „Pridėti kaip
patalpą" — the new room carries the label as its area (`plano_uzrasas`), sits
where the label stands, and leaves purpose and perimeter to him
(`lib/planLabels.js`).

**Measured:** in-sample and out-of-sample numbers unchanged (no scope on the
fixtures); `tests/test_scope.py` (20) covers the helpers, both endpoints, the
wall-finish branch, a room switched back on, per-room families and Rotband;
the ledger invariant holds on scoped rows. A scope change drops the rows the
builder left out instead of carrying them as orphans (`mergeDarbuSarasasEdits`
`scopeChange`), keeping his own rows and typed quantities. **Still not done:**
windows to the floor (a reading question, not a scope); Rotband from a real
wall-type read (needs the pertvarų planas legend read by geometry — a paid
Vision pass, parked with the €0 rule).

### Third €0 round — DONE 2026-09-06 (founder: „dar kažką galima nemokamai padaryt?")

- **Corner bead is a choice.** The calculator counted every room's four
  concave corners as bead (`inner_corners_m = 4 × H`, ~100 m on G) and the
  Setup Wizard's „tik išorės kampai" checkbox was never read by it. Now
  `apimtis.kampai` (su vidiniais — today's default — / tik angų ir pertvarų)
  and the wizard checkbox both reach `calc_room_quantities`
  (`count_inner_corners`). Default unchanged on purpose: G reads +122 % against
  his row and H +6 % with inner corners in, so the convention is his, not a
  standard we can pick for him — the founder decides the default.
- **Waterproofing checked in m² without a second row.** His out-of-sample
  sąmata bills hidroizoliacija in m² (G 39,5); the LT pro convention the
  builder follows is ONE line per job (per wet zone, vnt), and a second m² row
  would be a row he could price twice (`test_pozicijos_p6_hidroizoliacija_
  collapsed_to_one_line` pins it). The line already carries its m²
  (`_detail_m2` = floors + splash zone); the row scorecard now pairs a his-row
  in m² with that detail when the units differ.
- **The plan's stated storey height is read, not assumed.** `H - 2820` on a
  floor plan (objektas_d, p1–p2) now gives rooms that carried only our default
  the stated value with `lubu_aukstis_saltinis = plano_uzrasas` and the
  statement's crop on the sheet („Aukštis — užrašytas plane: „H - 2820""). A
  reader or the user always wins; two different statements → nothing applied.
  Soffit/fixture heights („Kaktos pab. h - 2390", „spintoje h - 2,20 m") are
  refused by their words, and so is a height inside a sentence („ap. h - 2260 mm,
  kai …" — words around the stamp). G/H/b print no storey height; d's two
  default-height rooms flip from „prielaida" to „perskaityta" at the same 2,82 m
  (the other two already had per-room reads) — numbers unchanged.
- Checked and NOT changed for free: hole count (a per-fixture convention),
  tile skirting on G (which floors are tiled is a Vision read; the designer's
  own 24,97 m now shows beside our 8,42 m), fixture counts on G (+50 % = the
  duplicated bathroom; the room switch fixes it in one click).

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


## Kampai default — measured 2026-09-10

Founder: „skaičiuok su būdu, kuris tiktų visiems projektams, ir pažiūrėk, kuris labiau
matchina pagal sąmatas". Both methods run on the six frozen extracts (deterministic tail
only, €0) against the contractor's own „Dažymo kampų montavimas" / „Glaistymo kampų
statymas" row:

| objektas | his m | su vidiniais | tik išoriniai |
|---|---:|---:|---:|
| a | 493,35 | 437,70 (−11 %) | 333,70 (−32 %) |
| b | 580,54 | 445,66 (−23 %) | 344,14 (−41 %) |
| c | 201,86 | 266,89 (+32 %) | 199,21 (−1 %) |
| d | 123,59 | 131,87 (+7 %) | 86,75 (−30 %) |
| g | 134,72 | 299,78 (+122 %) | 198,26 (+47 %) |
| h | 412,94 | 437,78 (+6 %) | 324,98 (−21 %) |

„Su vidiniais": median |err| 17 %, 2/6 within ±10 %, 4/6 within ±25 %. „Tik išoriniai":
31 %, 1/6, 2/6. **Default stays „su vidiniais"**; the per-project choice covers objektas_c.
Side finding: the Setup Wizard sent `count_inner_corners: false` with every upload, so a
new project was silently computed „tik išoriniai" while the UI pre-selected the other —
flipped to `true`. objektas_g (+122 %) is its own problem (duplicate room 07 alone is 26 m).

## €0 closure — 2026-09-10 („padaryk absoliučiai viską, kas nemokamai")

Done: per-room ledgers on every per-room line (karnizas, angokraščiai, paslėptų durų
angos, LED nišos, GKP lubos ir siūlės, Rotband, WC dėžutės, plytelių darbai, drėgnų
patalpų santechnika) — a living room's check sheet now lists 19 quantities, a bathroom's
29; `bendras_plotas_m2` follows the rooms he counts; kampai default measured (above);
scorecard m² pairing; wizard default fixed.

Looked at with existing reads, NO engine change (the numbers explain themselves):
- **Hidroizoliacija G** — his 39,5 m², ours 57,69. Without the duplicate room 07 ours is
  40,14 (+1,6 %). The formula (floor + 0,30 m splash band + shower zone × H) is fine;
  the phantom bathroom is the whole gap.
- **Grindjuostės G** — designer 53,69 m, ours 64,79 = 58,9 net + 10 % waste. The 5 m net
  difference is most likely the kitchen run of the svetainė-virtuvė (no plinth behind
  cabinets), which no lane reads.
- **Plytelių grindjuostės G** — designer 24,97 m, ours 8,42 (skalbykla only; wet rooms
  are treated as tiled to the floor). The two plan labels without a room (3,60 + 6,90 m²,
  perimeters ≈ 7,6 + 10,5 m) plus the technical room would add up to his figure — the
  gap is the missed rooms, which he adds with the button (his decision: „užrašas").
- **Dažomos sienos G** — designer 220 m², ours 248 (235 without room 07).
- **Window rows for H** („Langų rėmų sandarinimas perimetru" 74,95 m, „Grindų
  betonavimas prie langų rėmų" 11,72 m) — computable from window sizes in principle,
  but the read windows give 41,4 m / 0 m: the window reader is not reliable enough to
  emit them. Needs reader work (paid runs), not formula work.
- **„Trapo montavimas"** — he bills trapas AND latakas as two rows on G, so our latakas
  line cannot double as the trapas; stays an admitted gap.
- The 55 empty „Jūsų eilutės" are rows from OTHER objects (garage etc.), checklist rows
  that need his input, or the admitted gaps above — no safe names-only mapping was left.

## First paid runs after the €0 work — 2026-09-10 (localhost, objektas_g × 2)

Two fresh extractions of the same 16-page PDF (a client disconnect made the first request
survive as an orphan-drain job, so the second launch ran alongside it): €3,17 + €2,35,
25 and 28 min, both saved server-side (`stream_disconnect_recovery`).

| | run 1 | run 2 | demo (old engine, backfilled) |
|---|---:|---:|---:|
| rooms | 9 | 8 | 9 |
| plan-label lane | value_only, 7 confirmed | value_only, 6 confirmed | shared_frame |
| Sienų glaistymas/dažymas | 276,11 | 268,48 | 248,12 |
| Dažymo kampų montavimas | 302,88 | 218,31 | 299,78 |
| Angokraščių glaistymas-dažymas | 88,40 | 30,60 | 94,85 |
| Lubų glaistymas/dažymas (anchor) | 104,53 | 104,53 | 104,53 |
| Vonios sienų plytelių | 39,20 | 35,37 | 51,96 |
| Hidroizoliacija / WC rėmai | 2 / 2 | 2 / 2 | 3 / 3 |

What the live path showed (and what was fixed the same day):
- **Zoom overwrote a plan label** — Step 2.5 turned room 02's adopted 14,26 m² back into
  11,68 m² „wall_dim_calc"; the lane summary and its warnings then described rooms that no
  longer existed, and `bendras_plotas_m2` kept Vision's pre-zoom total (101,04 vs Σ 97,90).
  Fixed: `_apply_zoom_refinements` never overwrites a `plano_uzrasas`/`eksplikacija` area
  (keeps the zoom figure as `_plotas_zoom_m2`); after zoom the lane takes a confirm-only
  second look at unconfirmed rooms (`reclaim_after_refinement`), warnings are regenerated
  and the project area is re-summed.
- **The phantom third bathroom did not come back** — both runs read 2 wet rooms (his
  sąmata: 2), so hidroizoliacija and WC rėmai match without any switch.
- **Run-to-run variance is the opening reader**: kampai 303 vs 218 m and angokraščiai
  88 vs 31 m from the same drawing — the doors/windows per room differ between reads.
  Areas (label-confirmed) and ceilings are stable. This is the paid-side lever now.
- The lane fell to `value_only` on both fresh runs (the backfilled demo had
  `shared_frame`): Vision's room boxes did not frame ≥60 % of the labels. Run 2 read two
  rooms named „Miegamasis 3" (10,55 and 8,22) — the 10,55 label sat unclaimed until the
  post-zoom reclaim.

## Openings — step 1 (measure) and step 2 (deterministic lanes), 2026-09-10

**Where the reader actually fails.** objektas_a is the only object with per-room opening
truth: the read matches it in 11/11 rooms (doors AND windows). On objektas_g the two fresh
runs disagree because run 2 came back with ZERO doors in every room — not a per-room
misread: the dedicated doors reader found 11 doors, but `merge_doors_into_rooms` first
erased every pass-1 door and then could not place a single one of its own (`between`
numbers did not match the run's room numbers), so all eleven were dropped silently while
`doors_rooms_updated` still said 8. Convention worth knowing: doors are counted ONCE, on
the corridor side (objektas_a: koridorius D6, bedrooms D0 — that is the truth, not a
miss), so „every room has a door" is NOT a valid prior.

**Fixed (€0):** the merge resolves `between` by number, by number without leading zeros,
by unique name, or by a number inside the string; doors it cannot place are counted in
`_meta.doors_unattributed` and said in a warning; when fewer than half can be placed the
pass-1 doors are left alone. Tests in tests/test_doors_reader.py.

**Deterministic lanes probed on the G drawing (vector PDF, 8 911 paths, text layer):**
- Window/door TAGS are positioned text on the floor plan (L-01 ×2, L-02, L-03, D1, D2,
  G01 ×2) and pages 2 and 4 share one frame, so page-4 area labels locate rooms on page 2.
  Totals are therefore deterministic (4 windows, 2+2 exterior doors); per-room assignment
  by nearest label is ambiguous for big rooms (L-03 sits as close to the bedroom's label
  as to the living room's) — it needs room outlines, which Vision's boxes do not give
  reliably (the plan-area lane fell to `value_only` on both fresh runs for the same reason).
- Door swings: 3 bezier arcs of door radius on the whole plan, and no quarter-arc chains
  among the 8 176 two-point segments — swings are not extractable cheaply from this PDF.

**Next lever (paid, small):** a schedule/tag-driven check of the doors reader — when the
plan carries tags, the reader's exterior-door count must equal the tag count; and a
targeted re-read when the merged door total is far below `total_count`.
