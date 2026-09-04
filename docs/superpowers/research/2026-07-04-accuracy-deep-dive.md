# Accuracy Deep-Dive: Is Our Analysis Foundation Capable? (2026-07-04)

**Founder question:** before flipping models — are there fundamentally more accurate ways to analyze projects? Are we using something incapable of proper project reading?

**Answer in one line:** our *architecture* is the right one (validated by both our own forensics and external evidence), but we're leaving accuracy on the table in three places that no model swap touches — eval mapping, systematic definition mismatches, and missing readers — and there are two proven techniques we haven't adopted (native PDF text+image input, agentic cropping).

---

## Part 1 — Internal forensics (our own benchmark data, 64 scored quantities)

| Error class | Share | Fixable by better model? |
|---|---|---|
| Not scored / "missing" | 58% | ❌ — splits further below |
| → of which: **produced but unmapped by eval** (plytelės, Rotband/išlyginamasis, GKP virš 3m, bendras plotas on 3 projects) | ~half | Fix = eval truth-key mapping. Zero API cost. Our real coverage is better than the benchmark showed. |
| → of which: **genuinely unbuilt readers** (rozetės+jungtukai, priglaistomi šviestuvai, difūzoriai, šiukšlių išvežimas) | ~half | Fix = new extractors. Formulas already in CLAUDE.md §1.13 etc. |
| **Systematic** (both models wrong identically): Objektas A paint −22%/−35%, plytelės −20.0% *identical*, kampai −13%, GKP height-split (+140%/−100% pair whose **sum** is only +25% off) | 14% | ❌ — convention/formula fixes: net-vs-gross paint definitions vs contractor billing, GKP 3m-split logic bug. |
| **Model-dependent** | 19% | ✅ — the only slice the Opus→Fable flip touches. Fable won it on balance (esp. raster reading + tile tables). |
| OK on both | 9% | — |

**Benchmark recap (fresh vision, no fallbacks):** headline MAE avg 27.2% (Opus) → 18.2% (Fable); cost €4.93 → €16.18 per 4 projects; Objektas C raster 52.4% → 17.0%. Objektas D headline regression is one small-denominator LED metric; Fable better/equal on 4/5 metrics there.

## Part 2 — External evidence (deep research; confidence labeled)

**What VLMs are provably good and bad at on drawings** (MechVQA, 3,281 mechanical drawings — arXiv 2605.30794; **verified 2026-07-04 with correction**):
- Best closed model (Gemini-3-Pro-Preview, 77.28% overall): text & table extraction **97.73%**, geometric calculation **73.58%**, projection/multi-view **58.00%** — the gradient is even steeper than first extracted (the 76.8/64.0 pair belonged to the authors' fine-tuned 4B model). VLMs excel exactly where our eksplikacija reads already score +0.02%; geometry *derived from pixels* is the weak zone. Matches our angokraščiai volatility precisely.
- AECV-Bench (arXiv 2601.04819, 120 plans; **abstract verified verbatim**; per-model numbers via EmergentMind): document QA up to 0.95, but **door/window counting "remains unsolved (often 0.40–0.55 accuracy)" across frontier models**. Claude-family door/window exact-match reported at 0.16 (older Opus 4.5). Confirms our long-standing window-detection pain is an industry-wide VLM ceiling, not our bug.
- VLMs produce essentially random coordinates/bounding boxes on floor plans (ACM study, unverified — consistent with all verified sources) — but zero-shot **counting matched trained YOLO**. Localization must come from CV; semantics can come from VLM.

**What the winners do:**
- **Togal.AI** (Tribe.ai case study, high confidence): custom raster **semantic-segmentation + object-detection CNNs**, built pre-VLM, not OCR/VLM-centric. I.e., the market leader's moat is exactly the "CV does geometry" half.
- **Countfire** (product docs, high confidence): exemplar propagation ("select once, count everywhere") + human correction as a first-class feature. No accuracy figures published.
- **Fine-tuning beats zero-shot at scale** (multiple papers, medium-high): Florence-2 0.23B fine-tuned beats frontier zero-shot by +52% F1 on drawing extraction; Qwen2.5-VL-3B hits 92.5% wall IoU after 2M-sample training. Not actionable for us today (no 2M-sample corpus), but our corrections loop is quietly building the seed dataset.

**Two techniques with measured gains we don't use (both verified 2026-07-04):**
1. **Native PDF input** (official Claude docs — **CONFIRMED verbatim**: "The text from each page is extracted and provided alongside each page's image"): our pdf2image flow **throws the text layer away**. Objektas A has a text layer (our viewer's search proved it). For text-layer PDFs this is hybrid text+vision for free. Caveat from the 75-plan SVG study (verified with scope correction): side-channels are model-dependent — GPT-4o +0.21 EM on moderate plans, while Claude 3.7 was best with PNG-only on *low-complexity* plans (0.95 vs 0.90; moderate: 0.61 vs 0.60 — same direction, thinner margin). A/B experiment, not a guaranteed win. (Note: the study tested SVG vector code, not PDF text layers — adjacent evidence, not identical.)
2. **Agentic cropping/zooming** (arXiv 2511.19820 — **numbers verified**, one label corrected: the Qwen 56.42→67.14 average is over 7 benchmarks, not 4): 256M RL cropper + frozen VLM lifted DocVQA 69.52→84.41; gains largest when resolution is the bottleneck (SmolVLM +9.7 pts at 512px vs +2.5 at 2048px) — A1 sheets at the 2576px cap ARE resolution-limited for small dimension strings. Fable 5 is explicitly trained to use crop tools on degraded images (official migration guide). Our zoom pass is a hand-rolled cousin; a model-driven crop loop is the evolved version.

**New insight from the verification round's gap search:** the "Hidden Clones" VLM-ensemble study (arXiv 2603.17111) finds **same-model self-consistency produces correlated errors; cross-family/cross-model ensembles provide independent signal**, and voting helps most on constrained outputs (counts, numbers) — our exact use case. Our voting is currently 3× the *same* model. Our own benchmark independently corroborates this: Opus and Fable disagree on 12 metrics with roughly uncorrelated error directions (angokraščiai: one overshoots where the other is exact, varying by project). → **New experiment: mixed-model voting** (e.g., 2× Fable + 1× Opus reads in the voting pool) may beat either model's self-consistency at intermediate cost.

## Part 3 — Verdict & roadmap

**The foundation is capable — and validated.** Our shape (VLM for semantics/tables + CV flood-fill for geometry + deterministic formulas + human correction) is what the evidence says works. Pure-VLM approaches cap out on exactly the subtasks we already route around. The gap is execution breadth, not architecture.

Ranked by accuracy-per-effort:

| # | Action | Cost | Expected effect |
|---|---|---|---|
| 1 | Fix eval truth-key mappings for all 4 projects, re-score existing runs | 0 € (no API) | TRUE accuracy picture; unblocks honest iteration |
| 2 | Fix GKP height-split bug + reconcile paint/tile conventions with contractor billing semantics | code only | Kills the largest systematic errors (−22/−35% paint, +140/−100 GKP) on every project forever |
| 3 | Flip vision roles to Fable 5 (keep KŽ text + chat on Opus) | ×2.6 runtime cost | The benchmarked 19% slice: raster projects 52→17% |
| 4 | Build missing readers: elektros taškai (rozetės/jungtukai), šviestuvai, difūzoriai — **exemplar/symbol-based or low-confidence-flagged, NOT naive VLM counting** (0.40–0.55 ceiling) | days | Coverage of quantities contractors bill every time |
| 5 | A/B: native PDF input (text+image) on text-layer PDFs | ~€10 experiment | Possible large gain on dims/tables; model-dependent — measure |
| 6 | A/B: Fable agentic crop loop on dimension-dense regions | ~€10 experiment | Attacks small-text misreads at the resolution ceiling |
| 7 | A/B: **mixed-model voting** (Fable+Opus reads in one voting pool) | ~€10 experiment | Decorrelates voting errors (Hidden Clones finding + our own 12 disagreement metrics) |
| 8 | Determinism repeat-run on final config | ~€8 | Variance bar for every future claim |
| 9 | (Later) Fine-tuned segmentation/symbol models from our corrections corpus | months | The Togal-style moat, once data volume exists |

**Verification status (updated 2026-07-04):** the pipeline's automated verification round failed on session limits; a dedicated verification pass against primary sources was then run for all six load-bearing claims. Verdicts: counting-ceiling CONFIRMED (arXiv 2601.04819 abstract verbatim), native-PDF dual-channel CONFIRMED (official docs verbatim), Togal-architecture CONFIRMED (case-study quotes; "not VLM" supported by omission), CropVLM numbers CONFIRMED with one benchmark-count label fixed, SVG-study PARTIALLY (Claude numbers rescoped to low-complexity), MechVQA PARTIALLY (subtask numbers reattributed — gradient holds, steeper). Corrections applied above. Coverage gaps that remain: Kreo/STACK/Bluebeam disclose nothing technical; no drawing-specific ensemble study exists (nearest: Hidden Clones, cross-domain).
