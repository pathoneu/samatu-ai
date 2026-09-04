# Contractor trust — the four-week plan (2026-09-04)

> Source of truth for the decision: `docs/superpowers/research/2026-09-04-council-transcript-contractor-trust.md` (verdict) built on `2026-09-04-row-level-accuracy-gap.md`, `2026-09-04-deep-research-claims.md`, `2026-09-04-two-minute-fix-ux.md`. Founder rules: nothing is pushed without an explicit OK per batch; no client identifiers anywhere; accuracy > code beauty; verify before claiming.

**The problem, measured.** Against the contractor's own sąmatas (six of them on disk, 329 rows, no prices) we reproduce ~27 % / ~14 % of his rows within ±10 % and miss 38–58 % outright — stable across runs and models. The eval's 3–20 % headline MAE measures ~22 aggregated metrics; he judges every billed row in his own vocabulary. The complaint is about the LIST (coverage + vocabulary), then about volatile reads (openings), then about a correction loop that today makes 4 of 8 real fixes impossible and erased his checkmarks.

**Metric that proves it (Week 1, €0):** *share of his rows reproduced within ±10 %*, count-weighted, through a FROZEN concept mapper, `sernu` held out, scored on all cached extracts. Target by week 4 on the held-out sąmata: ≥ 60 % of his rows present under his labels, ≥ 40 % within ±10 %, 0 unverified numbers dropped into his cells.

## Week 1 — instrument + stop the loop eating itself (€0)
- [ ] **Scorecard** in `eval_harness.py`: contractor rows × ai rows via `scripts/reconcile_samata_lines.py` CONCEPTS (freeze the table; changes to it are reported, never counted as accuracy gains); per project: present / ±10 % / ±25 % / way-off / missing; holdout `sernu`. Extend `scripts/parse_all_samatas.py` to keep any price columns when a priced sąmata arrives.
- [x] **S bugs (81aa83a, local):** ✓ survives recompute only when its number did (value-guarded — never launder into `build_ground_truth`); `rnk-` rows kept, not „pasenusi"; numeric select-on-focus.
- [ ] „Suveskite patys" rows editable in place (inline kiekis editor; they are the rows he must fill).
- [ ] Changed rows after a recompute carry a visible „pasikeitė — patikrinkite" badge (the Contrarian's requirement; the ripple lists them, the badge sticks).
- [ ] **Founder asks the contractor (this week):** the PDFs he judged; his sąmatos for them; ONE priced sąmata (any project); how long his own sąmata takes on a typical project (baseline).
- [ ] Storage hygiene: dev/tests must not write to the production R2 bucket (`storage.get_storage` picks R2 whenever env vars exist — gate on `ENV=production` or an explicit `STORAGE_BACKEND=r2`).

## Week 2 — his sąmata as the skeleton (family template)
- [ ] Build the family template from five sąmatas (his five sections, his labels per family), measure coverage on the held-out sixth BEFORE UI work — this decides how much of A to build.
- [ ] Project output in his layout: his sections + his labels; our quantity only where a ledgered/verifiable family maps; **blank typable cell** everywhere else (never a guessed number in his row); export in that layout.
- [ ] Contractor session (end of week 2) on his own project: scorecard + template; ≥ 20 correction rows written; record which rows he reaches for first.

## Founder direction 2026-09-04 (after the council): evidence-first checking, no "AI dots"
"We may never reach 100 % accuracy, so perfect the CHECKING so it still saves time — not with AI dots, with normal explanations showing how, where, what." The checking surface is therefore the product's core loop, designed as **the AI showing its homework**:
- **Room check sheet** (one per room, in drawing order): the drawing auto-framed on the room; 6 facts with an EVIDENCE CROP each — area (eksplikacija row crop), perimeter (dimension strings highlighted on the plan when a text layer exists; outline otherwise), height (section/marker crop, or an explicit „neradau — skaičiuoju 2,80, įrašykite" blank), finishes (finish-table row crop), openings (plan crop with numbered marks + schedule sizes), floor (floor-plan legend crop); the per-room contributions strip („iš šio kambario sąmatoje …"); one-click „Viskas teisinga — kitas" (Enter).
- **Second layer per room — the billed quantities themselves** (founder, same day: "tu rodai tik plotą, bet reikia ir dažomą plotą, angokraščius, kampus ir visa kita — kažkaip tuos dalykus tikrint"): under the facts, every quantity this room contributes (sienų dažymas, lubų dažymas, kampai, angokraščiai, grindjuostės, plytelės, grindys) as a line with the formula in real numbers („perimetras 19,72 × aukštis 2,80 = 55,22 − D1 1,89 − L1 1,80 = 51,53 m²"; „6 kampai K1–K6 × 2,80 = 16,80 m") and the elements MARKED on the plan (walls green, corners K1–K6 from the polygon vertices, deducted openings red), each with ✓ / Pataisyti. Fix semantics: fixing a FACT recomputes every quantity and the whole sąmata; fixing a QUANTITY overrides only that room's contribution (manual override, remembered, never re-written by a recompute). Data: `contributions[].terms` from the ledger (kampai/grindjuostės have terms; paint terms to be added), polygon vertices for corners (5/11 rooms today; all once the room grid lets him adjust outlines), openings have no coordinates (show count + schedule sizes + the room crop; the D1/L1 rings in the mockup are illustrative).
- **Then „Bendri faktai"** (eksplikacijos Iš viso, symbol counts with the plan crop and a „suskaičiuok pats" fallback, wall thickness) and **„Jūsų eilutės"** (template rows the drawing cannot answer, blank, remembered for the next project).
- **Confidence dots go out of the primary UI**; a missing/assumed fact is a blank field with the reason in plain Lithuanian. Uncertainty may still order the walk internally.
- Evidence sources we already persist: room marker (11/11) + polygon (5/11) + page; `eksplikacija_row_bbox` (since 08-23); height-marker page + x/y (P0 T3); finish/door schedule pages. Missing: opening coordinates (show the plan crop), dimension-string positions on scans (show the outline). Crops: server-side `GET /api/projects/{id}/evidence/{room_nr}/{fact}` via pdf2image region crop (cached) — or client-side framing in the EmbedPDF viewer.
- Time model to validate with the contractor: manual ≈ 2–3 min/room vs ≈ 15 s (AI right) / 45 s (AI wrong) — the pitch is "checking is faster than counting" even at 60 % accuracy.

## Week 3 — the correction product (2-minute loop) → becomes the room check sheet above
- [ ] Resurrect the room grid beside the drawing (`RoomsGrid.jsx`/`RoomCard.jsx` out of the unreachable `kiekiai` tab): area, perimeter, height, add/remove room — the four impossible scenarios become ≤ 10 s each.
- [ ] Room-first Patikra with **per-input-family verification**: confirming a room verifies only room-derived rows (paint, ceilings, floors, skirting, corners); opening-derived rows (angokraščiai, door prep) get their own confirm step — they must never inherit a ✓ from rooms.
- [ ] Visible ripple with undo; bulk height edit; keyboard flow.

## Week 4 — his new PDFs
- [ ] One paid run per new PDF, scored with the scorecard; contractor session #2; per-room finishes (tiled vs painted) and opening counts editable if time remains.

## Rejected for this period (with the reason)
Fine-tuned symbol detector (needs 300–400 labelled drawings; we have 4 projects, 0 corrections) · vector/SVG lane, zoom loops, more voting, model swaps (row hit-rate 14 % → 14 %) · measure-first as the default („bought a ruler") · €-weighted metric before a priced sąmata exists · growing the concept map to move the metric.
