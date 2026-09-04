# The row-level accuracy gap — what the contractor actually sees (2026-09-04)

**Trigger.** The founder sat with the contractor: on his projects "every number was more or less off; many way off". No artefacts of that session exist in our systems (prod DB backup 2026-09-04 03:15 has 12 projects, last non-founder one 2026-08-03; all September R2 `projects/` objects are 409-byte test seeds; local dev DB unchanged since 07-25). So the only measurable thing is the project we DO have his numbers for — his own house (objektas_a) — compared the way HE compares: his sąmata's 53 quantified rows against our full list, row by row, not our 5–22 headline metrics.

## Result (fuzzy label match ≥0.55, same unit; three independent production runs + the frozen corpus extract)

| Run | AI rows | within ±10 % | ±10–25 % | > 25 % ("way off") | no AI row / no quantity |
|---|---:|---:|---:|---:|---:|
| prod 2026-08-31 (what the founder most likely showed him) | 85 | 14 (26 %) | 4 | 15 (28 %) | 20 (38 %) |
| prod 2026-08-11 | 82 | 15 (28 %) | 5 | 13 (25 %) | 20 (38 %) |
| prod 2026-07-29 | 82 | 15 (28 %) | 3 | 15 (28 %) | 20 (38 %) |
| frozen corpus extract (the eval's input) | 83 | 10 (19 %) | 4 | 14 (26 %) | 25 (47 %) |

Stable across runs → this is **structure, not read variance**. On the same project the eval reports 3–5 % headline MAE, because the eval scores ~22 aggregated metrics (paint, ceiling, LED, tiles, kampai, angokraščiai…) while the contractor bills ~55 rows in HIS vocabulary and granularity.

**Caveat:** the matcher is naive (difflib on normalised labels) — some "missing" rows exist under different wording (e.g. his "GKP montavimas ant lubų, dvigubas karkasas 2,8 m / 3,4 m" vs our "GKP lubų montavimas (standartinis / virš 3 m)"), and some "way off" pairs are mismatches (his LED-niche row matched our angokraščiai row). A section-aware matcher would move a handful of rows between buckets; it would not change the picture: **roughly a quarter good, a quarter far off, and a third to a half of what he bills we either do not emit or emit as „suveskite patys“.**

## What is in each bucket (2026-08-31 run)

- **Good (≤10 %)** — the deterministic, text-anchored quantities: Rotband (−4 %), paint iki 3 m (−7 %), šiukšlės (−10 %), and every fixture COUNT that comes from the room list (WC rėmai 2, klozetai 2, gyvatukai 2, skalbimo mašina 1, dušo maišytuvai 2…).
- **Way off (>25 %)** — angokraščiai +56 % (the 09-02 run had +1 % on the same PDF: the door/opening reader is the single most volatile input), paint virš 3 m (+62 % — tier split), kampai −27 %, silikonavimas −54 %, grindjuosčių supjovimas +72 %, praustuvų maišytuvai 2 vs 5, tile families matched to the wrong bucket (90×90 grindų vs "kitų sienų"), "Medžiagos montavimui 1 vnt" vs our 4 664 screws.
- **Missing / no quantity** — GKP lubos by height (102,78 + 62,82), GKP nišos 42,3 m, nišos pertvarose 9,11, priglaistomi difūzoriai 15 + 21, hidroizoliacija 2 vnt, latakai 2, TRACK apšvietimas 20,06 m ×2, dekoro plytelės 28,8 m², plytelės 120×120 55,62 m², dėžutė ortakiams 1 — rows we emit as checklist („suveskite patys") or under names his sąmata does not use.


## Second datapoint — objektas_b (the contractor's other project, 111 quantified rows)

| Run | AI rows | within ±10 % | ±10–25 % | > 25 % | no AI row / no quantity |
|---|---:|---:|---:|---:|---:|
| frozen corpus extract (eval input; headline MAE 19.6 %) | 80 | 6 (5 %) | 5 | 26 (23 %) | 74 (67 %) |
| fresh 2026-09-02 Opus 5 run | 133 | 15 (14 %) | 5 | 28 (25 %) | 63 (57 %) |
| fresh 2026-09-02 Fable 5.1 run | 131 | 16 (14 %) | 4 | 26 (23 %) | 65 (59 %) |

Same shape, worse: on the bigger, table-less project we reproduce **one row in seven** of what he bills, and miss well over half outright. The model swap moves nothing (14 % vs 14 %). Whatever the founder showed at the contractor's house, this is what a contractor sees when he holds his own sąmata next to ours — and it is consistent with "every number was more or less off, many way off".

## What this means

1. **Our accuracy instrument measures the wrong thing.** A contractor-facing scorecard = *share of HIS billed rows we reproduce within ±10 %, by € weight*. Today that is ~27 % of rows on the one project we know best. This must become the eval's headline number (his parsed sąmata already exists: `ground_truth/objektas_a/contractor_samata_parsed.json`; objektas_b has a truth file too).
2. **Coverage is the biggest lever, not read precision.** 38–47 % of his rows have no counterpart. Half of those are rows the engine cannot compute from a drawing (hydro-insulation as a count, gutters, track lighting) — they need his TEMPLATE, not a better reader: a per-contractor list of what he always bills, learned from one priced sąmata, with our quantities dropped in where we have them and „suveskite" where we don't.
3. **Vocabulary/granularity mismatch makes correct numbers look wrong.** He bills GKP ceilings per height, "apdirbimas" and "montavimas" as pairs, tiles per format. Our rows must be expressible in his labels (the kainynas + his priced sąmata give the mapping).
4. **Read volatility is real but secondary**: the opening reader swings ±50 % between runs on the same PDF; voting does not cover it. Fix by determinism (text-lane dimensions where present) and by the 2-minute correction loop where not.
5. The 2026-08-03 council was right that corrections are the flywheel — the corrections table is still at 0 rows in production.

## Next measurements (cheap, no paid runs)

- Build the row-level scorecard into `eval_harness.py` (section-aware matcher; € weight from his prices) for objektas_a and objektas_b.
- Re-score every stored run of objektas_a with it to get the variance band per ROW family.
- Ask the contractor for the sąmatos of the projects he judged; run those PDFs ourselves (paid) and score them the same way.
