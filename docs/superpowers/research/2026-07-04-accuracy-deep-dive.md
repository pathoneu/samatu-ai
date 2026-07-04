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
| **Systematic** (both models wrong identically): Beržų paint −22%/−35%, plytelės −20.0% *identical*, kampai −13%, GKP height-split (+140%/−100% pair whose **sum** is only +25% off) | 14% | ❌ — convention/formula fixes: net-vs-gross paint definitions vs contractor billing, GKP 3m-split logic bug. |
| **Model-dependent** | 19% | ✅ — the only slice the Opus→Fable flip touches. Fable won it on balance (esp. raster reading + tile tables). |
| OK on both | 9% | — |

**Benchmark recap (fresh vision, no fallbacks):** headline MAE avg 27.2% (Opus) → 18.2% (Fable); cost €4.93 → €16.18 per 4 projects; Čiurlių raster 52.4% → 17.0%. Lazūnai headline regression is one small-denominator LED metric; Fable better/equal on 4/5 metrics there.

## Part 2 — External evidence (deep research; confidence labeled)

**What VLMs are provably good and bad at on drawings** (MechVQA, 3,281 drawings — arXiv 2605.30794, medium-high confidence):
- Text & table extraction: **97.7%** — VLMs excel exactly where our eksplikacija reads already score +0.02%.
- Geometric calculation: **76.8%**; projection/multi-view: **64%** — geometry *derived from pixels* is the weak zone. Matches our angokraščiai volatility precisely.
- AECV-Bench (120 plans, ~10 frontier models; medium confidence — some numbers via secondary summary): document QA up to 0.95, but **door/window counting unsolved at 0.40–0.55 across ALL frontier models**. Claude-family door/window exact-match reported at 0.16 (older Opus 4.5). Confirms our long-standing window-detection pain is an industry-wide VLM ceiling, not our bug.
- VLMs produce essentially random coordinates/bounding boxes on floor plans (ACM study, medium-high confidence) — but zero-shot **counting matched trained YOLO**. Localization must come from CV; semantics can come from VLM.

**What the winners do:**
- **Togal.AI** (Tribe.ai case study, high confidence): custom raster **semantic-segmentation + object-detection CNNs**, built pre-VLM, not OCR/VLM-centric. I.e., the market leader's moat is exactly the "CV does geometry" half.
- **Countfire** (product docs, high confidence): exemplar propagation ("select once, count everywhere") + human correction as a first-class feature. No accuracy figures published.
- **Fine-tuning beats zero-shot at scale** (multiple papers, medium-high): Florence-2 0.23B fine-tuned beats frontier zero-shot by +52% F1 on drawing extraction; Qwen2.5-VL-3B hits 92.5% wall IoU after 2M-sample training. Not actionable for us today (no 2M-sample corpus), but our corrections loop is quietly building the seed dataset.

**Two techniques with measured gains we don't use:**
1. **Native PDF input** (official Claude docs, high confidence): Claude's document input feeds each page as image + embedded text layer *simultaneously*. Our pdf2image flow **throws the text layer away**. Beržų has a text layer (our viewer's search proved it). For text-layer PDFs this is hybrid text+vision for free. Caveat from a 75-plan study (medium confidence): vector/text side-channels are model-dependent — helped GPT-4o, slightly hurt Claude 3.7 on some tasks — so this is an A/B experiment, not a guaranteed win.
2. **Agentic cropping/zooming** (arXiv 2511.19820, medium-high): an external cropping loop lifted DocVQA 69.5→84.4 for a frozen VLM; gains largest when resolution is the bottleneck — A1 sheets at the 2576px cap ARE resolution-limited for small dimension strings. Fable 5 is explicitly trained to use crop tools on degraded images (official migration guide). Our zoom pass is a hand-rolled cousin; a model-driven crop loop is the evolved version.

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
| 7 | Determinism repeat-run on final config | ~€8 | Variance bar for every future claim |
| 8 | (Later) Fine-tuned segmentation/symbol models from our corrections corpus | months | The Togal-style moat, once data volume exists |

**Verification caveat:** the adversarial verification round of the external claims failed on session limits; confidence labels above reflect source quality (official docs/primary papers high, secondary summaries medium). Items 5–6 are framed as experiments partly for this reason — our own A/B is the real verification.
