# The row scorecard — baseline, 2026-09-04

Week 1 of `plans/2026-09-04-contractor-trust-4-weeks.md` asked for the number the
contractor actually reads: **the share of HIS billed rows we reproduce within
±10 %**. It exists now — `backend/extractor/row_scorecard.py`, printed by
`eval_harness.py --rows` and folded into the default `--totals-only --recompute`
table. This is what it says today, before any of the work it is meant to steer.

Reproduce:

```
venv/bin/python eval_harness.py --rows --recompute            # the table below
venv/bin/python eval_harness.py --rows --recompute --detailed # every row, and why
venv/bin/python eval_harness.py --totals-only --recompute     # MAE + the compact block
```

Zero API spend — every number here is scored off the cached
`ground_truth/<slug>/ai_extract.json` through the same deterministic recompute
the headline MAE uses.

## The number

**26.5 %** of the contractor's billed rows, count-weighted, mean over the four
corpus projects, live engine. The headline MAE for the same run is **7.82 %**.
Both are true; they measure different things, and only the first is his complaint.

| project | his rows | scored | **±10 %** | ±10–25 % | way off | missing | unmapped | he left blank | family Σ ±10 % | our rows he doesn't bill |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| objektas_a | 53 | 53 | **20 (37.7 %)** | 8 | 6 | 19 | 0 | 0 | 19/27 | 59 |
| objektas_b | 113 | 111 | **11 (9.9 %)** | 8 | 16 | 57 (13 granularity) | 19 | 2 | 9/29 | 69 |
| objektas_c | 37 | 36 | **8 (22.2 %)** | 2 | 15 | 3 | 8 | 1 | 8/25 | 57 |
| objektas_d | 50 | 50 | **18 (36.0 %)** | 3 | 12 | 9 (3 granularity) | 8 | 0 | 17/33 | 70 |
| **corpus mean** | | | **26.5 %** | | | | | | | |
| romainiai | 15 | 15 | 2 (13.3 %) | 0 | 6 | 2 (1 granularity) | 5 | 0 | 1/7 | 115 |
| sernu | 32 | — | — | — | — | — | — | — | — | — |

*romainiai* is outside the mean for the reason `ground_truth/registry.yaml`
already gives (`scope_mismatch`: his pasiūlymas prices the 4.1–5.1 punktas subset
while the project PDF is the whole 45-page interior) — the same exclusion the
headline MAE applies, kept identical so one project cannot be in one number and
out of the other. *sernu* is the **HOLDOUT**: its sąmata is parsed (32 rows) but
no extract exists, and none will be made until the four-week target is claimed
against it. Its unmapped families are deliberately **not** listed below —
reading them would let the template work be fitted to the holdout.

### Same instrument on the FROZEN extracts

The frozen `ai_extract.json` numbers are what the engine produced on the day each
extract was written; `--recompute` re-runs today's deterministic tail over the
same Vision reads. Both, side by side, are the honest measure of what the engine
has gained since:

| project | frozen ±10 % | live ±10 % |
|---|---:|---:|
| objektas_a | 15 (28.3 %) | 20 (37.7 %) |
| objektas_b | 6 (5.4 %) | 11 (9.9 %) |
| objektas_c | 5 (13.9 %) | 8 (22.2 %) |
| objektas_d | 15 (30.0 %) | 18 (36.0 %) |
| corpus mean | **19.4 %** | **26.5 %** |

## How a row is judged

Full contract in the module docstring; the parts that decide the number:

1. **The concept table is frozen.** Matching runs through the 60 hand-maintained
   contractor-family → app-family mappings in `scripts/reconcile_samata_lines.py`,
   never a fuzzy label match. A row no concept covers is `unmapped`: reported,
   counted against us, never scoreable as a hit. **Adding a concept raises the
   score without a single quantity improving**, so the table's size is pinned by
   `backend/tests/test_row_scorecard.py::test_the_frozen_concept_table_loads_and_is_frozen`
   — grow it and the test fails until someone re-baselines this document on
   purpose. A mapping change is a mapping change, not an accuracy gain.
2. **Unit-compatible or it does not count.** His `m2` is never compared against
   our `vnt`; `b/m` and `bv/m` are read as linear metres; a two-unit cell
   (`m2; b/m`) matches either. An unrecognised unit degrades to `missing`.
3. **His granularity wins.** We sum OUR side — he can add our sienų + lubų rows
   together to check his one „glaistymas/dažymas" row — but never HIS. When he
   bills a family on more rows than we emit (GKP ceilings by carcass height,
   tiles by format, revizinės durelės by size), the rows are paired greedily on
   the smallest relative error and the leftovers are `missing` with
   `reason="granularity …"`. 16 rows in this corpus are missing for that reason
   alone.
4. **Count-weighted.** Every row weighs one — see the pricing finding below.

### Why this reads higher than the research doc, and why it is still the harsh choice

`research/2026-09-04-row-level-accuracy-gap.md` measured objektas_a at 19 %
(frozen) / 26–28 % (three production runs) with a difflib matcher over normalised
labels, and called that matcher naive itself. The concept table matches families
difflib could not — his „GKP monatavimas ant lubų, įrengiant dvigubą karkasą"
against our „GKP lubų montavimas (standartinis aukštis)" — so the frozen number
moves 19 % → 28.3 %, and today's engine adds the rest of the way to 37.7 %.
That is a better matcher, not a better engine, and both effects are separated in
the frozen-vs-live table above.

The choice that mattered went the other way. Summing BOTH sides per family — the
obvious implementation — reads **49.1 %** on objektas_a against 37.7 % here,
because his two GKP-ceiling rows and three tile rows each become hits the moment
our single aggregate lands near their total. It was rejected: he cannot find
„GKP lubos 3,4 m — 62,82 m²" in a list that only has one ceiling line, and a
metric that says he can would make week 2's whole job — emitting rows under his
labels — invisible. The Σ-vs-Σ family agreement is still reported (the
`family Σ ±10 %` column, and per family in `--rows --detailed`) as the softer
second number; the gap between the two columns *is* the granularity debt.

## The coverage gap — 39 families no concept covers

This list is the input for the family-template work (week 2). These are rows he
bills that our vocabulary has no name for at all; they are not read failures and
no better reader fixes them.

> **Outcome (2026-09-04, `2026-09-04-template-holdout.md`):** the template built
> from his own sąmatas offers **73,2 %** of his billed rows, leave-one-out, at
> zero cost to the ±10 % share — which stays at exactly the 26,5 % below. The
> families still missed are the ones seen in a single project; that residual
> shrinks with HIS sąmata count, not with our reader.

| his family | seen in |
|---|---|
| Priglaistomų led ptofilių apdirbimas | objektas_d, romainiai |
| Priglaistomų led profilių montavimas | objektas_d |
| Priglaistomų gipsinių šviestuvų, montavimas | objektas_d |
| Plyšinis priglaistomas difuzorius EGROVENT 1m, 20mm, 2x125 tvirtinimas | objektas_b |
| Apvalus potinkinis priglaistomas difuzorius EGROVENT Ø100mm | objektas_b |
| Apvalus potinkinis priglaistomas difuzorius EGROVENT Ø125mm | objektas_b |
| Rekuperatoriaus montavimas* | objektas_d |
| Trasų kondicionieriams įrengimas | objektas_c |
| Kondicionieriaus įrengimas | objektas_d |
| Kondicionieriaus sifono įrengimas | objektas_c |
| Automatinių jungiklių montavimas E. skyde | objektas_d |
| Esamų kabelių koregavimas, naujų kabeliavimas | objektas_d |
| Jungikliai | objektas_b |
| Smulkūs el. darbai | objektas_c |
| Signalizacijos daviklių pajungimas languose | objektas_c |
| Laidų apsiuvimas garaže | objektas_b |
| WC ir bide rėmo montavimas | objektas_b |
| WC ir bide rėmo montavimas suleidžiant į sieną | objektas_b |
| Klozeto/ bide montavimas | objektas_b |
| Vandens mazgo demontavimas, potinkinės dėžės sumontavimas, vamzdžių privedimas | objektas_b |
| Durų angos platinimas į miegamojo rūbinę | objektas_b |
| Durų angos į rūbinę glaistymas dažymas | objektas_c |
| Durų rankenos keitimas | objektas_b |
| Durų varčios dažymas | romainiai |
| Palangių montavimas | objektas_c |
| Moldingų dažymas | romainiai |
| Lubų iš gipso kartono montavimas laiptinėje | romainiai |
| Stiklo audinio klijavimas ant vėsinamų lubų | romainiai |
| Nišos įrengimas duše | objektas_d |
| Pertvarėlės lentynoms įrengimas dušo kabinoje | objektas_b |
| Plytelių pripjovimas prie trapo garaže | objektas_b |
| Garažo plytelės | objektas_b |
| Laiptų garaže įrengimas | objektas_b |
| Sienos paruošimas Mėnulio dekorui | objektas_b |
| Mėnulio ir tv sienos dekoravimas | objektas_b |
| Skylių gręžimo darbai | objektas_b |
| Montavimo darbai | objektas_b |
| Smulkūs papildomi darbai | objektas_c |
| Drėgmės surinkėjo nuoma | objektas_c |

Reading it as groups: **MEP** (ventilation diffusers by model, recuperator, air
conditioning runs, switchboard, cabling, alarm) — an engineering-plan lane the
interior module does not have; **finish carpentry** (moldings, sills, door leaf
painting, door-handle swap, widening an opening) — small named jobs that come
from a walk-through, not from the drawing; **garage and stairwell** — rooms our
room model skips; **bespoke items** („Mėnulio dekoras", a shower shelf partition,
a niche); and **catch-alls** he bills as one line („Montavimo darbai", „Smulkūs
papildomi darbai", dehumidifier hire). Almost none of these can be *read* off a
drawing. They need his template — a per-contractor list of what he always bills,
with a blank typable cell where we have no number.

Also worth its own line: **57–115 rows per project that we emit and he never
bills** (the last column). Coverage is not only what we miss.

## Findings that change the plan's premises

**1. All six sąmatas already carry prices.** The plan says a €-weighted metric
waits for "ONE priced sąmata (any project)" from the contractor. He does not need
to send one: every sąmata PDF on disk has four price columns — `Darbų kaina € be
PVM` (vnt. / viso) and `Medžiagų kaina € be PVM` (vnt. / viso). They were dropped
because `scripts/parse_all_samatas.py` only ever read columns 0-3. It now keeps
them (`prices` per row, `has_prices` per file), proved additive on all six real
PDFs — same rows, same fields, zero diffs.

The tracked JSONs were **deliberately not regenerated**:
`ground_truth/<slug>/contractor_samata_parsed.json` is tracked in a public repo
and his unit prices are commercially confidential. Where the priced parse lives —
a gitignored path, or prices stripped on write — is a founder decision, and it
unlocks the €-weighted scorecard the plan wanted to defer. Rows with prices per
file: objektas_a 34, objektas_b 25, objektas_c 28, objektas_d 28, romainiai 16,
sernu 28.

**2. The frozen extracts understate today's engine by ~7 pp** (19.4 % → 26.5 %).
Any row-level number quoted from a cached extract without `--recompute` is a
number from the past — the same trap `--totals-only` documents for the MAE.

**3. objektas_a is not representative.** 37.7 % against objektas_b's 9.9 %. It is
the project with a full `gt_dimensions` block and months of tuning behind it, and
the corpus mean is dragged up by it and objektas_d. The week-4 target (≥ 40 %
within ±10 %) must be claimed on `sernu`, not on the mean.

## What the buckets say to do next

- **57 missing + 19 unmapped on objektas_b** is over two thirds of that sąmata.
  Coverage, not precision, is the lever — same conclusion as the gap research,
  now with a number that will move when it is fixed.
- **16 granularity rows** are a pure output-shape fix: the family total is
  already right (`family Σ ±10 %` counts them), we simply emit one row where he
  bills three. GKP ceilings by height, revizinės durelės by size, tiles by
  format, floor coverings by material, grindjuostės by type.
- **`missing: app row has no quantity (checklist — „suveskite patys")`** is the
  other big block: rows we do emit, under his family, with no number. Those are
  exactly the rows the plan wants editable in place.

## Addendum — € weighting (2026-09-04, director)

All six sąmatas carry four price columns; the priced parse is generated locally into the gitignored `ground_truth/<slug>/contractor_samata_priced.json` and the harness prefers it when present. **Live engine**, share of the contractor's row totals (€) reproduced within ±10 %, next to the row-count share:

| project | rows ±10 % | € ±10 % |
|---|---:|---:|
| objektas_a | 37.7 % | 32.4 % |
| objektas_b | 9.9 % | 21.0 % |
| objektas_c | 22.2 % | 49.1 % |
| objektas_d | 36.0 % | 54.7 % |
| **corpus mean** | **26.5 %** | **39.3 %** |

Frozen extracts: 19.4 % of rows / 13.4 % of €. Reading: on the live engine the expensive families (paint, GKP, tiles) land closer than the cheap, numerous ones, so by money we reproduce ~40 % of his sąmata today; the missing/way-off tail is many small rows plus a few large misses per project. The € column is the founder's number from here on; the row count stays as the coverage signal.
