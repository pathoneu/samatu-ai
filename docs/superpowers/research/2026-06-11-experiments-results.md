# Empirical Experiments — False-Green Rate & Text-vs-Geometry (2026-06-11)

**Why:** The council + headroom research both demanded empirical verification before the strategy is locked. Two contractor-validated projects used (per user: "most trustable, proper full projects"):
- **Beržų g. 24** — 58-line Rangovas A samata (existing fixture)
- **Bacevičiaus g. (Gytis ir Simona)** — 112-line Rangovas A pasiūlymas 2026-04-13, 65-page TP (fixture existed; fresh voted extraction run today)

Artifacts: `eval_runs/2026-06-11_experiments/` · harnesses: `scripts/exp1_false_green.py`, `scripts/exp2_text_vs_geometry.py`, `scripts/run_voted_extract.py`

---

## Experiment 2 — Text-derived vs geometry-derived quantities (Beržų) ✅ COMPLETE

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

## Experiment 1 — False-green rate · BERŽŲ ✅ MEASURED

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

## Experiment 1 — bacveviciaus ⏳ extracting (65-page TP × 3 voting rounds)

---

## Experiment 3 (implicit) — Generalization to a second contractor project ⏳

The bacveviciaus voted run doubles as the N=2 generalization test the council demanded ("months of build steered by one PDF"). Pre-registered expectations (so we can't rationalize after):
- Combined paint within ±10% would be a strong generalization signal (berzas voted was +2.3%).
- Kampai: truth 580.54; expect UNDER (pusiniai recovered by adjacency, but berzas voted was still −10.6%).
- Known-missing concepts (molio tinkas 160 m², laidų apsiuvimas garaže, mėnulio dekoras) will not be emitted — these measure the data model's coverage gap, not extraction error.
