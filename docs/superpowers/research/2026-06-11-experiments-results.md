# Empirical Experiments — False-Green Rate & Text-vs-Geometry (2026-06-11)

**Why:** The council + headroom research both demanded empirical verification before the strategy is locked. Two contractor-validated projects used (per user: "most trustable, proper full projects"):
- **Objektas A** — 58-line Rangovas A samata (existing fixture)
- **Objektas B** — 112-line Rangovas A pasiūlymas 2026-04-13, 65-page TP (fixture existed; fresh voted extraction run today)

Artifacts: `eval_runs/2026-06-11_experiments/` · harnesses: `scripts/exp1_false_green.py`, `scripts/exp2_text_vs_geometry.py`, `scripts/run_voted_extract.py`

---

## Experiment 2 — Text-derived vs geometry-derived quantities (Objektas A) ✅ COMPLETE

**Design:** Two live probes on the floor page asking ONLY for transcription of per-room dimension strings (no visual estimation): (A) full-page ≤2000px (current pipeline delivery), (B) 300 DPI × 4 overlapping tiles (resolution-budget lever pilot). Text-derived perimeters (2×(a+b)) swapped into the same deterministic calc; both lanes scored against contractor walls truth (460.71 m²).

### Results

| Lane | Coverage | walls_paint | error |
|------|----------|------------|-------|
| **Geometry (Vision visual estimation — current pipeline)** | 11/11 rooms | 447.73 | **−2.8%** ✅ |
| Text dims, full-page probe | 7/11 rooms | 401.78 | −12.8% ❌ |
| Text dims, tiled probe | 5/11 rooms | 393.99 | −14.5% ❌ |
| **Text TABLE lane (eksplikacija → ceiling/floor)** | 11/11 | 165.64 vs 165.6 | **+0.02%** ✅✅ |

### Findings (n=1 plan, but mechanism-level)

1. **The research's "text-first lane owns measurements" hypothesis FAILS on this plan style for dimension chains** — not because OCR fails (both probes transcribed the same raw strings honestly: 4330, 3980, 2780…) but because **the drawing has segmented exterior/structural chains, not per-room a×b annotations**. The model attributes partial segments as room dims (e.g. room 108 "4280×2070" — 2070 is a door; room 101 "1400×3980" — 1400 is a wall segment). Both probes even *agree* on the wrong attributions. Deriving room perimeters from text requires spatial chain-summing — i.e. the full raster-to-vector problem again, not a prompt.
2. **The text lane splits decisively by text TYPE:** tables/schedules (eksplikacija) → near-perfect (+0.02%) and already exploited by the pipeline; dimension chains → structurally unusable cheaply. *Amend the strategy: "text-first" = table/schedule-first (keep maximizing), NOT dims-first.*
3. **Geometry lane vindicated as the perimeter source** on this plan style: Vision visual estimation + voting = −2.8% walls. The 2026 research's 85–95% text-lane projection does not transfer to LT plans with segmented chains.
4. **Tiling pilot (headroom lever #1):** tiled delivery found MORE strings (55 vs 48 — confirms resolution loss at 2000px; the page is 4963px at 300 DPI, so the pipeline sends a 2.5× downsample) but had WORSE room attribution (5/11 vs 7/11) — **tiles break global layout context**. Supports the research's gated-zoom (localizer chooses crops; full page keeps context) over naive blanket tiling. Resolution matters for *reading*; context matters for *attribution*; the architecture needs both.

---

## Experiment 1 — False-green rate · OBJEKTAS A ✅ MEASURED

**Design:** Fresh voted extraction (N=3, restored pipeline, 392s), scored at the **production output level** (pozicijos/santrauka the user sees) against 24 contractor-truth-anchored quantities. GREEN unless a voting low-confidence flag touches the quantity's input rooms or a structural fallback fired. WRONG = |err|>10%.

### THE HEADLINE: **FALSE-GREEN RATE = 50%** (8 of 16 green quantities wrong @10% tol; 56% @5%)

- Voting flags caught only **5 of 13** wrong quantities (38% error recall; flag precision 5/8).
- **The false greens are SYSTEMATIC, not noise** — garažas floor tiles not modeled (0 vs 10.1), frameless doors under-tagged (15.3 vs 39.2, −61%), silikonavimas formula (−39%), lentynėlės count (4 vs 5), 45° pjovimas (+15.5%), angokraščiai (−14.8%), skylių recall (−10.7%), tambūras tile area (+28.9%). All 3 voting runs agree on the *same wrong answer* → disagreement-based flags are blind to exactly this class. **This empirically confirms the council's sharpest claim: agreement-spread measures self-consistency, not correctness.**
- What IS reliably green: counts anchored on wet-room logic (klozetai/WC rėmai/hidro/nuolydis all exact), floor/ceiling from eksplikacija (−2.3%), and several per-room tile quantities (±1%).
- **Voted-vs-voted drift is real:** this voted run vs the restoration-day voted run — combined paint 546.4 vs 598.4 (truth 584.8), kampai 405.1 vs 441.2 (truth 493.4), walls-layer −15.1% vs −5.1%. N=3 voting reduced variance but two voted runs still differ by ~10pp on geometry-derived quantities. The eksplikacija itself read differently (floor 161.79 vs 165.64).

**Implications (empirical, not opinion):**
1. The 🟢 as currently computed is **not sellable** — half wrong. Confidence must come from *calibration against ground truth per quantity-class*, not from run-agreement alone. Quantity-classes with measured systematic bias (doors, silikonavimas, garažas rules) must be 🟡/🔴 by *class*, regardless of voting agreement.
2. Voting flags ARE useful for what they see (5/8 precision) — they catch geometric instability — but they are one signal of several, not the confidence system.
3. The systematic-error list IS the work queue: each false-green row is a rule/recall fix with a contractor-anchored target.

## Experiment 1 — False-green rate · OBJEKTAS B ✅ MEASURED

Fresh voted run: 803s, 15 rooms × 3 rounds, npw=59, 7 voting flags, ~$9. Scored vs 21 mappable truth quantities from the 112-line pasiūlymas.

### **FALSE-GREEN RATE = 60%** (9/15 after harness-mapping corrections*; raw 67%). Flag precision 6/6 (100%), error recall ~40%.
*\*Corrections: contractor has TWO išlyginamasis lines (143.19 + 39.43 = 182.62 total floor) → app 180.0 is −1.4% ✓ not +25.7% ✗; floor-total mapping must include garažas.*

### Pre-registered expectations vs reality
- "Combined paint ±10% = generalization signal" → **FAILED: +62.8%** (802.8 vs 493.0).
- "Kampai expect UNDER" → wrong direction: **+16.5%** (676 vs 580.5; adjacency npw=59 worked).
- "Missing concepts won't be emitted" → confirmed, **but worse: their absence CORRUPTS paint** (see below).

### THE DECISIVE DECOMPOSITION — geometry is fine; FINISH-ASSIGNMENT is the error mass
- **Interior wall geometry: app ~506 m² vs contractor's painted+clay total ~509.8 → −0.7%.** Perimeter×height extraction generalized essentially perfectly.
- The +62.8% paint error is **semantics, not geometry**: (a) **160 m² molio tinkas counted as paint — the apdailos schema has NO clay-plaster/decor category**, so it maps to dazymas; (b) garažas walls (76 m²) + garage/extra ceilings painted by the app but not finished by the contractor (scope rules); (c) parquet assigned to rooms the contractor tiles (+29% parketas).
- **The apdailos pass self-reported its failure and we ignored it:** 8/15 rooms carry `_apdailos_pastabos` = "low confidence; spėjimas pagal paskirtį", and at least one room was classified from *vizualizacijos* (renders), not the finish plan. **This self-reported low-confidence signal is not wired into the confidence system — a free, immediate fix.**
- **Height attribution failed on this drafting style** (was fine on objektas_a): app marked small wet rooms 3.5 m and the 62 m² svetainė 2.82 m → GKP split inverted (iki3m +127%, virš3m −86%). Voting flags DID fire on these rooms (the system knew it was unsure).
- **Systematic classes repeat across BOTH projects:** beapvadinės durys **−61% / −64%** (strikingly consistent → calibratable), silikonavimas −39% / −68%, skylių −11% / −21%, fixture counts ±40%. Two contractor anchors now exist per class.

---

## Cross-experiment synthesis — what the data says the strategy should be

1. **Geometry extraction is NOT the bottleneck** (walls −2.8%/−0.7% across two projects). The research's symbol-detector/zoom levers target a layer that is already adequate at the totals level. **Re-rank: finish-semantics first.**
2. **The #1 accuracy lever (measured): the finish-semantics lane** — extend the apdailos vocabulary (molio tinkas, mikrocementas, dekoras, "netinkuojama"), find the REAL finish-plan pages (not renders), per-project scope rules (is garažas painted? which ceilings are finished?). This is "measure by reading the project's own spec" — the text-first thesis is right at the SEMANTIC level, wrong at the dimension-chain level.
3. **The #2 lever: confidence rebuild** — false-green 50–67% is unsellable. Calibrate per quantity-class (doors/silikonavimas/skylių classes → 🟡 by default with measured bias ranges), propagate self-reported low-confidence (apdailos pastabos), keep voting flags (100% precision when they fire, ~40% recall).
4. **Heights: style-dependent** — right on objektas_a, inverted on objektas_b; voting flags them; zoom-apply fix (pending follow-up) + section-marker cross-check is the path.
5. **Both projects' false-green rows are the concrete fix queue** with contractor-anchored targets. Don't eval-fit to N=2 — fix mechanisms (vocabulary, scope rules), calibrate classes, and grow the anchor set.

| | Objektas A | Objektas B |
|---|---|---|
| False-green rate @10% | 50% | 60% |
| Flag precision / error recall | 63% / 38% | 100% / 40% |
| Walls geometry vs truth | −2.8% | −0.7% |
| Combined paint | −6.6% | +62.8% (finish semantics) |
| Voted-run cost / time | ~$4 / 392s | ~$9 / 803s |

---

## SAME-DAY FIX ROUND (the "go" build) — measured before → after

Shipped (commits `feat(finish)`, `feat(confidence)`, `feat(apdailos)` 2026-06-11): molio tinkas/kita_danga vocabulary + paint split; apdailos self-reported-confidence propagation; per-pozicija confidence post-pass (class calibration from the 2 anchors + finish provenance + voting flags, worst wins); apdailos page-finder excludes renders; **multi-page išklotinės reading** (Objektas B TP carries finishes across pages 12–22 — single-page reads structurally cannot work).

| Metric | Before | After |
|---|---|---|
| Objektas A false-green @10% | 50% | **25%** (error recall 38%→**85%**) |
| Objektas B false-green @10% | 60% | **0%** (error recall 40%→**100%**) |
| Objektas B apdailos low-confidence rooms | 14/15 (single page, renders) | **7/15** (11 išklotinės sheets, one call, ~$0.8) |
| Molio tinkas pozicija | not representable | emitted, 32.5 m², geltona |
| Objektas B combined paint | +62.8% | +56.9% (paint+molio vs contractor paint+molio: **+23.4%**) |

**Honest residuals:** (1) Objektas A's 2 remaining false greens are *confidently-wrong* apdailos shares (garažas walls +20%, vonia tile −19%) — the blind-audit class; self-flagging cannot catch them. (2) The molio gap (32.5 emitted vs 160 contracted) is a **TP-vs-contract divergence** — the drawing specifies paint where the client later chose clay; no drawing reader can see that. It stays geltona, and the correction UI is where it gets fixed — which is exactly why the council made the correction UI the product. (3) Greens are now scarce (8/24, 4/21) — the path back to green is fixing calibrated classes, not relabeling.

### Second fix round (heights + garage scope) — measured

Shipped after the multi-page apdailos work (commits `feat(heights)`, `fix(finish)` garage):

- **Height-plausibility gate** (`apply_height_plausibility_gate`): Vision had put the 3.5 m tall ceiling on a 6.8 m² wet room + 2.9 m² WC while the 62 m² svetainė got the 2.82 default → inverted iki/virš-3m split. Gate moves the tall height to the large living room, clamps the wet rooms. **Objektas B GKP virš-3m: 9.72 → 62.42 (truth 68.28; −86% → −8.6%).** Objektas A (tall room already the large svetainė): gate does not fire → zero regression.
- **Low-confidence apdailos no longer overrides structural no-paint:** the reader GUESSED "garažas — dažytos sienos (spėjimas)" and that override painted 76 m² of garage walls the contractor never finishes. Now a low-confidence breakdown can't override garažas/tambūras = no-paint (a confident read still can). **Objektas B combined paint (vs contractor paint+molio 653 m²): +62.8% → +1.6%.**
- **Zoom-apply reframed (not a height fix):** the Pass-2 zoom is a floor-plan crop; ceiling heights live in sections (pjūviai), so floor-plan zoom structurally cannot recover them — "0 applied" for heights is expected, not a bug. The height fix is the plausibility gate above. The zoom-apply remains a *cost*-not-accuracy issue (it runs but rarely applies on single-pass; voting skips it when consensus carries heights). Deprioritized.

**Cumulative finish-accuracy on the two anchors after both rounds:** false-green 50%/60% → 25%/0%; objektas_b combined paint +62.8% → +1.6%; GKP virš-3m −86% → −8.6%; objektas_a unchanged (zero regression). Geometry was never the problem — finish semantics + height attribution + scope rules were.

### Recall round (the "bit more backend recalls") — disciplined against N=2 fitting

The systematic under-count classes were triaged for *mechanism* fixes (generalizable) vs *coefficient fitting* (overfit to 2 anchors):

- ✅ **silikonavimas — SHIPPED (mechanism):** it only sealed `paskirtis ∈ {vonia,wc,san}`, missing skalbyklos and other apdailos-tiled rooms. Extended to all tiled rooms (`plyteles_share≥0.6`), unchanged ×1.4 coefficient → objektas_a −39%→−10%, objektas_b −68%→−55%. Residual is fixture-density-driven (needs more anchors) and stays flagged geltona.
- ❌ **silikonavimas corner-seam term — REJECTED (fitting):** adding `internal_corners × tile_h` over-shot objektas_a (+31%) while still under-shooting objektas_b (−35%); per-room sealing genuinely differs ~2× (fixture density). Can't derive stable coefficients from N=2.
- ❌ **skylių gręžimas — LEFT AS-IS (fitting):** −11%/−21%. Adding the omitted fixture types (gyvatukai, trapai) doesn't close both gaps with stable per-fixture counts (`2g+3t=6` vs `4g+3t=23` → inconsistent). Mild + likely symbol-recall, not formula. Stays flagged.
- ❌ **beapvadinės durys −61%/−64% — VISION RECALL, not deterministic:** the contractor treats ~all interior doors as frameless; Vision tags only the explicitly-marked ones. Forcing "all interior frameless" over-shoots projects with framed doors. Needs the doors-reader to classify better (Vision), not a formula.

**Discipline note:** of 4 candidate recall classes, 1 was a clean mechanism gap (shipped) and 3 were N=2 fitting traps or Vision-recall (correctly declined). The honest move with 2 anchors is to fix mechanisms and flag the rest, not tune coefficients to hit two numbers.
