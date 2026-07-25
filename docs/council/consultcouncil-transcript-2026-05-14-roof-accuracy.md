# Consultcouncil Transcript — Roof Extraction Accuracy

**Date:** 2026-05-14
**Project:** Sąmatų AI / stogai V1
**Method:** 3-round debate (Claude Opus 4.7 + ChatGPT GPT-5.5 + Gemini 3.1-pro-preview)

## Final Verdict

Three-way R3 consensus: **drop ±2%-per-line as the public metric; adopt typed semantic routing in the merger + proof-carrying dimension ledger + WAPE-style value-weighted error.** Side with Gemini/Claude against ChatGPT on the OCR question — classical CV is V1.5 conditional, not V1 critical path. The 0039 -8.7% failure is a page-selection bug (Opus correctly read 4.61m from the wrong page), and that's a routing problem, not a perception problem. Ship semantic routing + ledger UI this week; build N=8-10 regression set in parallel, not as a gate.

## Three Positions After R3

- **Claude:** Semantic routing + Constraint Verification Graph + input-not-output HITL ship now; OCR is V1.5 conditional behind empirical data.
- **ChatGPT:** Same architecture, but treats targeted OCR + high-DPI re-read on high-impact ambiguous dims as worthwhile near-term addition.
- **Gemini:** Same architecture, but holds firm against classical CV in any form ("multi-month R&D trap").

## Load-bearing Disagreement

Whether targeted OCR earns its keep as a secondary evidence layer on raster PDFs. ChatGPT says yes (especially for "binding text to dimension entity"); Gemini says no (Opus orchestration suffices). Sided with Gemini for V1 because the named failure mode (0039) wasn't OCR-shaped — but ChatGPT's point holds for future failure modes we haven't yet seen at N=2.

## Strongest Argument Across the Debate

**Gemini R2 against Claude R1:** *"The Phase 0 deterministic strategy literally uses (a) and (b) to calculate (c). If Opus extracts the wrong width from the wrong page, the Python script will just deterministically compute the wrong total area based on that wrong width. They will match perfectly, and your system will silently fail to trigger HITL."* Single sentence that killed Claude's favorite R1 idea and forced the council toward Constraint Verification Graph as the actual HITL trigger.

## Council Scoreboard

- **Claude:** R1 → R3 — abandoned "larger width wins" and circular geometric cross-val; adopted semantic routing + Constraint Graph; conceded WAPE > ±2%.
- **ChatGPT:** Held proof-carrying-estimate frame from R1 to R3 (strongest single position kept). Softened on classical CV → "targeted OCR only, not full pipeline" by R3.
- **Gemini:** Held semantic routing + Opus-only line through all 3 rounds. Conceded N=10 wireframe (R1 mistakes) by R2.

## Agreed Action Sequence

1. **Today** — implement strict semantic routing in `build_roof_input` (page-class → allowed RoofInput fields; floor plans own axes, sections own slopes, roof plans own topology). Drops the wrong-page width on 0039 natively.
2. **This week** — dimension ledger UI: extracted value + page-class + cropped source snippet + conflict alternatives + cost impact. Constraint check: sub-dimensions sum to overall axis; flag failures into HITL.
3. **In parallel (not gated)** — N=8-10 regression set with per-page intermediate dimension labels. Capture user corrections as structured eval data.
4. **Internal metric**: WAPE + "no unflagged high-impact line error." **External promise**: "≤5 critical assumptions for you to confirm, then zero hidden error" — NOT "±2% per line autonomous."
5. **Defer to V1.5 (empirical-data dependent)**: targeted OCR re-read on flagged crops, ensemble voting, multi-shot.

---

## Round 1 — Independent Opening Positions

### Claude R1
LLM Council verdict mostly correct but understates and overstates. Understates: page-authority bug fix is highest-ROI (20 lines in `build_roof_input`). Overstates: "Build N=8-10 first" framed as precondition — can run in parallel. Council wrong: dismissed #3 (geometric cross-val) as "free signal" — it's the strongest technique. HITL on derived quantities is dangerous; confirm INPUTS not OUTPUTS. Hidden 9th: use strategy relationships as INPUT constraints. ±2% target = marketing not engineering; stop chasing past ±5%.

### ChatGPT R1
The Claude council mostly survives. Amendments: (1) "Ground truth first" right for accuracy claims, wrong if it delays product — build N=8-10 in parallel. (2) UITL correct only if "We inferred 7.20m from p46; confirm?" with crop, provenance, cost impact. (3) **Missing 9th strategy: dimension-annotation-first OCR/CV pipeline + constraint solver.** LLM vision JSON should be one evidence source, not THE source. (4) Real target: value-weighted total error (WAPE) + "no unflagged high-impact line error" — not ±2% per-line. Core product: proof-carrying estimate.

### Gemini R1
Claude council = "safe, defensive engineering." (1) N=8-10 is delay tactic disguised as rigor — **Ship and Capture**: ship now with UITL, organic N=100. (2) UITL needs to be VISUAL (wireframe overlay), not mathematical audit. (3) Missing 9th: dedicated digit OCR (Google Document AI / Textract) + Constraint Verification Graph (sub-dims sum = overall). (4) Real target: "Zero Hidden Structural Assumptions" via 100% trace-backability + cropped bounding-box images.

## Round 2 — Cross-Critique

### Claude R2 (critique of ChatGPT + Gemini)
Concede: Gemini's circular-validation catch killed my geometric cross-val ("Phase 0 uses (a)+(b) to compute (c); checking (a)+(b) against (c) is tautology"). Concede: ChatGPT's challenge to "larger width wins" — semantic authority by FIELD TYPE is right framing. Push back: both ChatGPT (OCR-first) and Gemini (wireframe UITL) go too far — 0039 was page-selection bug, not OCR misread, and wireframe won't catch 8cm errors. Adopt: ChatGPT's "dimension ledger with crops" as primary UI + WAPE metric.

### ChatGPT R2 (critique of Claude + Gemini)
Concede Claude's "fix bug + GT in parallel." Push back on Claude's "larger width wins" — encodes one failure as policy; need semantic authority by field type. Push back on Claude's perdanga × cos(slope) — formula domain-suspect. Push back on Gemini's "N=10 ≈ N=2 statistically" — N=8-10 is regression harness covering failure modes. Push back on Gemini's wireframe — won't catch 8cm axis-width errors. Push back on Gemini's "OCR is easy fix" — hard part is BINDING text to dimension entity. Endorse Gemini's Constraint Verification Graph.

### Gemini R2 (critique of Claude + ChatGPT)
Concede ChatGPT's WAPE metric. Concede Claude's "validate INPUTS not OUTPUTS." **CRITICAL pushback on Claude's geometric cross-val: CIRCULAR** — Phase 0 uses (a)+(b) to compute (c). **CRITICAL pushback on ChatGPT's classical CV: multi-month R&D trap** violating Opus 4.7 standard, deeply negative ROI at €5/project. Counter-proposal: **Strict Semantic Routing Hierarchy** — Floor Plans = exclusive write-access to global axes; Sections = slopes/heights; Roof Plans = topology. If extracted from wrong page-class, merger DROPS it.

## Round 3 — Final Positions (see Final Verdict + Three Positions sections above)
