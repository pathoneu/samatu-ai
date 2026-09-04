# Headroom Above the ~50% Zero-Shot Ceiling — Research Round 2 (2026-06-11)

**Method:** 7 parallel web-research agents (fine-tuned VLMs, synthetic data, classical CV, text-first, preprocessing, ensembles/test-time-compute, adjacent industries) → synthesis → adversarial fact-check. Companion to `2026-06-11-vision-takeoff-sota.md` (round 1) and the council pressure-test (`2026-06-11-council-vision-strategy-*`).

## The headline

**The ~50% ceiling is real but substantially a *zero-shot, full-sheet, low-resolution* artifact.** It breaks at sub-task granularity with fine-tuning, resolution discipline, and a text-first lane. Nothing dethrones the drafted architecture; one thing reorders it (text lane first), several modify it. **One prerequisite gates everything: human-verified ground truth — fine-tuning on AI-seeded labels distills the ceiling instead of breaking it.**

## Ranked headroom table (gain × feasibility for 2 people)

| # | Path | Evidence-backed gain | Cost | Confidence |
|---|------|---------------------|------|-----------|
| 1 | **Resolution-budget enforcement** — render 250–300 DPI, tile/crop so every sent image stays under the provider downscale threshold (~1568–2576px for Claude); SAHI-style overlapped slicing for symbols | +5–11 pp (CropVLM +6–10.7 [arxiv 2511.19820]; SAHI +5–7 AP [arxiv 2202.06934]; DeepSeek-OCR compression rule [arxiv 2510.18234]) | Days; ~0 data | **High** mechanism (silent downscale documented in Claude docs), gain is transfer-assumption — measure on our PDFs |
| 2 | **Text-first measurement lane** — eksplikacija/schedules/dimension chains; RANSAC consensus over redundant dimension strings for scale + OCR-outlier detection | Text-derivable quantities → 85–95% (AECV-Bench OCR split 0.70–0.95 vs symbol counting 0.09–0.39 [arxiv 2601.04819]; RANSAC scale >95% [doi 10.3390/buildings16051043]) | 2–4 wks; no training data | High on components, **end-to-end unverified — Objektas A makes it a 1-day experiment** |
| 3 | **Fine-tuned YOLO detector + synthetic composites** — paste legend crops onto real plan backgrounds w/ collision rules, Augraphy degradation, slice fine-tuning (+12.7–14.5 AP) | Symbol counting → 70–90% F1 per drawing style (P&ID industry: 95–98% P/R at 75K annotations [JCDE 9/4/1298]; synthetic pretrain + 60 real sheets recipe [arxiv 2411.13929]) | ~10³ annotations + 60–100 human-checked sheets; rented 4090; quarter-scale project | High in-style, **medium cross-style** (zero published evidence on style transfer — where our bake-off died) |
| 4 | **Fine-tuned crop readers** (Florence-2/Donut) behind the detector | +50–75% relative F1 on the sub-task (Florence-2: 61.5% vs GPT-4o 35.5% with 400 drawings, one 4090 [arxiv 2411.03707]; Donut detect-then-read 93.5% F1 [arxiv 2506.17374]) | 300–500 crops *per sub-task* (annotation labor is the constraint) | High, in-distribution only; 10–25% residual hallucination |
| 5 | **Cross-family disagreement triage** (DAFE pattern) — NOT voting for answers; escalate on disagreement only | Error-flagging: consensus entropy +42.1% error-detection F1 [arxiv 2504.11101]; DAFE 72.9→86.6 macro-F1 at 1.3–1.5× cost [arxiv 2503.08542] | Days; no data | Medium-high; families may share blind spots on tiny glyphs — measure disagreement-vs-error correlation on fixtures first |
| 6 | **Wall/geometry segmentation nets** | 76→89% mIoU only after regional fine-tune; pixel-IoU→quantity-error link unverified anywhere | 100+ pixel-labeled plans | Medium — **defer** until 1–4 plateau |

## Architecture changes (vs the draft)

- **REORDER:** insert the **text-first lane ahead of the entire vision pipeline** — quantities readable from tables/schedules/dimension chains never enter the detector/VLM path; vision becomes the fallback for symbol-only and dimension-less sheets. (Matches the perimeter-floor finding: no-eksplikacija plans were already the failure mode.)
- **MODIFY voting:** keep self-consistency inside the best model for answers (cross-family majority voting *loses* to the best single model [arxiv 2603.06197, 2502.00674]); add ONE cheap cross-family check that escalates only on disagreement. **Never average divergent numerics** — escalate to zoom-retry or human.
- **MODIFY scale:** single-source scale → **RANSAC consensus over all dimension strings** on the sheet; redundancy turns OCR errors into detectable outliers instead of silent 30% length errors.
- **UPGRADE YOLO data:** drop the Grounding DINO teacher (weak on schematic linework — consistent with our Pipeline 5/6 deaths; teacher caps the student) → synthetic composites + Augraphy + slice fine-tuning + human-checked sheets.
- **⚠️ PERCEPTION ≠ REASONING:** do NOT spend thinking budget on perception calls — longer chains reduce visual attention and amplify hallucination [arxiv 2505.21523, 2512.11109]. Spend reasoning on quantity derivation/cross-check math (+7–11 pt documented). **Our Pass-1/zoom use `effort: high` — A/B this on Objektas A; possible accuracy AND cost win.**
- **CONFIRMED:** localizer-gated zoom (CropVLM is direct validation); correction UI (mature P&ID industry ships 100% human review even at claimed 99.9% — pre-annotate-then-verify *is* the product).

## Honest dead ends (don't revisit)

Diffusion super-resolution on text-bearing drawings (below bicubic, hallucinates digits); one end-to-end plan→quantities fine-tune (needs ~2M samples; FloorplanVLM still only 73% door/window F1); naive cross-family majority voting; more test-time thinking for perception; Grounding DINO-class teachers on linework; CAD-layers-as-labels (we get flattened rasters — Path-A spike already proved); quoting point-cloud numbers as raster ceilings; deskew/binarization as a headline lever.

## Skeptic's gates (before betting the roadmap)

- Text-lane "85–95%" is synthesized, not measured — let the Objektas A run set the number.
- YOLO "70–90%" anchors used 75K annotations on standardized symbols; we propose ~10³ on messier LT drawings; cross-office transfer has zero published evidence.
- All "+pp" projections sit on a baseline our own audit says was inflated ~7.5× — re-baseline on production-realistic inputs first.
- The 10-week schedule is optimistic for 2 people; the detector is a quarter-scale project. Annotation labor is the binding constraint.
- **Hard gate for ALL fine-tuning: human-verified ground truth** (`build_ground_truth.py` + ~1h flow). Objektas A contractor fixture = held-out test seed.

## Recommended sequence (research's view; council adds correction-UI-first — see council transcript)

1. Resolution-budget stage + tiled delivery → re-run fixtures (expect +5–10 pp; days).
2. **The 1-day Objektas A experiment: text-derived vs geometry-derived quantities head-to-head** — decides how much of the pipeline the text lane owns. (Nobody has published this; highest-value item.)
3. Human ground truth — gates all fine-tuning. Text-first lane + RANSAC scale.
4. YOLO detector (synthetic composite recipe) + DAFE disagreement triage into the existing confidence flags.
5. Defer: segmentation nets, crop readers (until detector + ground truth exist).
