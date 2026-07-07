# Vision-for-Raster-Takeoff — State of the Art (2025-2026)

**Date:** 2026-06-11. **Method:** 6 parallel web-research agents (2025-2026 sources) → synthesis → adversarial fact-check. Replaces the stale internal bake-off assumptions. Decimals flagged below are single-source / post-cutoff — treat as indicative, directions as solid.

## The one sentence
General multimodal models got dramatically better at **charts, docs, and UI-pointing (now human-parity)** — but on **construction floor plans they still score 33–51%**. The ~50% pure-vision ceiling is **confirmed by two 2026 benchmarks as real and persistent**, not a prompt artifact. The adoptable wins are in the **scaffolding around the model**, not the model.

## Verified (multi-source, safe to act on)
- **No breakthrough on drawing/geometric understanding.** AECV-Bench (Jan 2026): Gemini 3 Pro 51%, GPT-5.2 49%, Claude Opus 4.5 42%; door/window counting 0.40–0.55 exact-match, "remains unsolved." ArchPlanVQA: 33–38%. Named failure mode in the literature now: **"geometric hallucination."** Floor plans are the geometric-reasoning regime, NOT the chart/doc regime where 2025 gains happened. ([arxiv 2601.04819](https://arxiv.org/abs/2601.04819), [ASCE JCCEE5](https://ascelibrary.org/doi/10.1061/JCCEE5.CPENG-7571), [arxiv 2602.06507](https://arxiv.org/html/2602.06507v1))
- **Pure-VLM counting FAILS** (FSC-147: GPT-4o/GPT-5 MAE ~22; predicted "1" for 2,560 Lego). VLMs only count well on **text-labeled** symbols (OCR). ([arxiv 2512.03233](https://arxiv.org/html/2512.03233v1))
- **The symbol fix = fine-tuned closed-vocab detector.** SkeySpot/YOLOv8 = 82.5% mAP@50 on 45 scanned electrical plans. Our old Pipeline-3 100× over-count was a *template-matching artifact, not a hard limit.* Bootstrap: feed our existing `legend_extractor.py` crops as visual prompts to **T-Rex2 / Grounding DINO** to auto-label a YOLO training set (no hand-labeling). Transfer to raster engineering symbols is **unbenchmarked — ours to measure.** ([arxiv 2508.10449](https://arxiv.org/pdf/2508.10449), [arxiv 2403.14610](https://arxiv.org/html/2403.14610v1))
- **Hosted-API bitwise determinism is impossible** (even T=0; provider controls batching). Impose determinism **downstream**: constrained flat-schema JSON (errors 32%→0.4%) + **N-sample median** for continuous numbers (self-consistency +27.6 GSM8K; CISC halves N) + **inter-sample agreement spread as the confidence signal** (model self-reported confidence is junk, ECE up to 0.43). *This validates our shipped N-pass voting and the 🟢🟡🔴 spec.* Self-hosting an open model with batch-invariant kernels (Qwen3: 80→1 unique outputs/1000) is the only path to true determinism. ([thinkingmachines.ai](https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/), [arxiv 2502.06233](https://arxiv.org/pdf/2502.06233))
- **Scale = detect + OCR + compute, NEVER VLM eyeballing.** Good auto-scale tools hit 1.8–3% error (vendor "98%" is marketing). ([roboticsandautomationnews](https://roboticsandautomationnews.com/2026/02/19/6-ai-construction-estimating-software-tested-on-complex-project-accuracy/98967/))
- **Agentic zoom/crop ("think-with-images") is the best lever for small reads** (V\* 55%→95.7% with o3/o4-mini; fine-tuned Florence-2 +52% F1 / −43% hallucination on dimension extraction) — **BUT fragile on noisy/re-rasterized input** (our exact case). Mitigation: **gate the crop with a deterministic localizer (Grounding DINO); never blind-crop.** ([openai think-with-images](https://openai.com/index/thinking-with-images/), [arxiv 2411.03707](https://arxiv.org/abs/2411.03707), [arxiv 2509.23789](https://arxiv.org/abs/2509.23789))
- **Human-in-the-loop is universal in 2026** — even "100% automated" Beam AI = AI + in-house human reviewer (24–72h, ±1%). Field reality on Togal: 85–95% on clean PDFs, **~60% on messy/low-res scans** (= our Ghostscript/iLovePDF re-exports). **"80% AI + 20% human review" is vindicated, not moved.** ([ibeam.ai](https://www.ibeam.ai/), [bidicontracting](https://www.bidicontracting.com/blog/togal-ai-review-2026))

## Blocked / hype for us
- **Vector-CAD spotters (CADSpotting AP50 70.6, SymPoint, DPSS) — BLOCKED**: need vector primitives flattened raster lacks.
- **Raster2CAD/Scan2CAD** give linework, not semantic walls/rooms/quantities. Not a takeoff shortcut.
- **CubiCasa "95–97%" — irrelevant** (LiDAR phone scanning, not image parsing).
- **MEP / sections / elevations: NO published raster SOTA.** Expanding beyond interior = off the research map; each new type needs its own fixtures + detector + fallback.
- **Strategic tension:** accuracy winners are *narrowing* scope (Fresco = doors only, Rudus = concrete only); our roadmap *widens* it. Breadth and accuracy pull opposite ways.

## Endorsed architecture (hybrid, not a bigger prompt)
> deterministic **scale calibration** (detect+OCR) → fine-tuned **YOLO symbol/opening detector** (bootstrapped from legend crops) → **localizer-gated agentic VLM zoom** for hard small reads → **deterministic Python geometry/formulas** (our existing strength) → **N-sample median + constrained flat JSON** → **agreement-spread confidence** → **fast human-correction UI on the 🔴 flags**.

= our current pipeline + 3 literature-validated additions: (1) a real scale step, (2) a trained detector replacing template-matching AND VLM counting, (3) gated zoom for small features. **The model is the least important upgrade.**

## Bottom line
>90% autonomous raster takeoff across all construction types is **NOT credible in 2026**. With the right scaffolding we can credibly push the AI share toward ~80% **on clean LT plans**; the human-review slice and the messy-PDF / novel-type long tail are irreducible. Don't wait for a better model — build the scaffolding.

## Skeptic's caveats (carried forward)
- The "51% vs our 49.3%" are **different benchmarks** — the "+1 point/generation" is rhetorical; the *direction* (no breakthrough) is solid.
- Model decimals (42/49/51%), competitor errors (1.8/3/4%), detector numbers (82% mAP, 0.925 IoU) are **single-source / self-reported / post-cutoff** — indicative, not load-bearing. The "~82% mAP target" and "~80% AI share on LT raster" are **extrapolations, not measured on our data.**
- Best-supported, safe-to-build-on: no-breakthrough, VLM-counting-fails→detector, downstream-determinism (voting/median/constrained-JSON), detect+OCR scale, universal human-in-loop.
