# LLM Council Transcript — Roof Extraction Accuracy

**Date:** 2026-05-14
**Project:** Sąmatų AI / stogai V1
**Branch:** `week1-canonical-execution`

## Original Question

User: "junk llmcouncil ir consultcouncil komandas ir ieskokit bandykit darykit kaip analizuot kuo tiksliau, nes cia ne kaip vidaus apdaila, yra nedaug kiekiu stogui, del to jie visi turi buti tikslus"

## Framed Question

**Sąmatų AI — push roof extraction accuracy from ±10% to ±2% per line item.**

Current state on branch `week1-canonical-execution`:
- A LAIDA (keturslaitis, clean architectural PDF): 4/4 line items pass, max delta -2.8% (kraigai)
- 0039 (dvislaitis, structural-only SK dalis, raster CID-garbled PDF): 5/5 pass, max -8.7% on "sienos" (gable area)

Problem: roof has only 4-8 line items per project (vs interior with 50+ where errors average out). Each error proportionally matters. User mandate: ≤2% per line item.

Root cause of -8.7% on 0039: vision read axis_width=7.12m from p46 (only page showing full building width — SK stogo page only shows partial half-rafter detail), vs expected 7.2m axis. 8cm width gap propagates squared into gable area.

Strategies under consideration: (1) multi-page orchestration, (2) prompt iteration with LT few-shot, (3) geometric cross-validation, (4) Opus+Sonnet ensemble vote, (5) user-in-the-loop, (6) higher-DPI rendering, (7) multi-shot per page, (8) back-propagate strategy outputs.

Constraints: ≤€5/project, raster PDFs, N=2 ground truth, same Opus 4.7 standard as interior pipeline.

---

## Advisor → Letter Mapping (revealed)

- **Response A** = The Outsider
- **Response B** = The Contrarian
- **Response C** = The First Principles Thinker
- **Response D** = The Expansionist
- **Response E** = The Executor

---

## The Contrarian (Response B)

Your N=2 ground truth is the fatal flaw and nobody at this table is naming it. You cannot validate "±2% per line item" against two projects. Hitting ±2% on N=2 is a coin flip — you have no idea if your next PDF is the one where vision reads 7.12 vs 7.20 again, or where it hallucinates an eave that wasn't drawn. The -8.7% you "explained" on 0039 is a post-hoc story. You'd tell a different story for the next miss. **Build N=10 before you tune anything.** Otherwise every strategy below is theater.

Now: user-in-the-loop (#5) is not a cop-out — but the way you're framing it *is*. A cop-out is hiding behind "the user will catch it." Useful HITL is: the system commits to a number, **shows the three dimensions it's most uncertain about** (with the page + crop it read them from), and asks for one click of confirmation. That's not abdication, that's calibrated confidence. Roofers will respect it. They will *not* respect a UI that punts every dim back to them — at that point you're Bluebeam with extra steps.

What kills you is #4 ensemble and #7 multi-shot voting. Two wrong LLMs agreeing isn't signal — vision models share failure modes (same OCR misread on CID-garbled text). You'll get false confidence.

Highest leverage, in order: (a) N=10 ground truth — non-negotiable; (b) #3 geometric cross-validation, because it's the only one with an *independent* signal (floor area constrains roof width, full stop); (c) #1 multi-page orchestration as a specific fix for the SK-only failure mode you actually observed. Skip #4, #6, #7.

## The First Principles Thinker (Response C)

You're asking the wrong question entirely.

"How do I get vision to ±2%?" assumes the bottleneck is the model. It isn't. The bottleneck is that **a single number on a single page determines the answer**, and there's no redundancy in the source document. When axis_width=7.12 vs 7.20 is the difference, you are not facing a perception problem — you are facing an **information-theoretic** problem. The PDF contains the answer once, sometimes badly, sometimes ambiguously. No amount of Opus calls extracts certainty that isn't in the artifact.

So strip it down. What are we actually trying to solve?

A roofer needs a quote they trust. ±2% is a proxy — the real goal is "the roofer doesn't get burned and doesn't have to redo the math." That goal does not require the AI to be ±2% autonomously. It requires the **final number** to be ±2%.

That reframes everything. User-in-the-loop isn't a cop-out — it's the **only honest answer** when N=2 ground truths, 4-8 line items, and source ambiguity exists. A roofer staring at "axis_width: 7.12m — confirm?" with the page cropped next to it spends 30 seconds and kills the error. That is cheaper, faster, and more accurate than any ensemble you can build for €5.

The cop-out is pretending autonomy is achievable here. It's vanity engineering.

Real priority order: (1) Cross-validation from geometry (#3) — free internal consistency check. (2) Surface dimensions for confirmation (#5). (3) Everything else is rounding error on the wrong problem.

Stop chasing ±2% autonomous. Ship ±2% **collaborative**, and be honest that's what it is.

## The Expansionist (Response D)

The accuracy obsession is hiding the real upside. ±2% on 4-8 line items is a vanity metric. Here's what's being undervalued.

**User-in-the-loop is not a cop-out — it's the moat.** Every correction is labeled training data on raster LT PDFs, a dataset that literally does not exist anywhere else. Frame each fix as "teach Sąmatų" and you've built a flywheel where N=2 becomes N=200 in six months. Togal.ai spent millions getting USA-labeled drawings. You get LT-labeled drawings for free, with the customer thanking you for the privilege.

**The bigger play hiding behind roof:** if you crack the multi-page orchestration pattern (pull width from floor plan, pitch from section, perimeter from elevation), you've built a *cross-drawing reasoning engine*. That generalizes to facades, earthworks, concrete — every Section 1 module in CLAUDE.md. Roof is the cheapest 4-8-line testbed for the architecture that unlocks the other 10 construction types.

**Ensemble + multi-shot is undervalued at €5/project.** A roofer's quote is €15-40k. Spending €15 instead of €5 to hit ±2% is invisible to the customer and lets you charge €99 instead of €29/project with a "verified accuracy" badge. Stop treating the cost cap as fixed.

**Highest leverage:** ship multi-page orchestration (option 1) + user-in-the-loop labeled corrections (option 5), priced as "Pro tier with confidence guarantee." The ±2% target is the trojan horse — the dataset and the orchestrator are the actual company.

## The Outsider (Response A)

Wait — I'm confused by the framing. You're asking how to get a *measurement* of a roof to ±2% from a PDF, but the PDF itself was drawn by a human who rounded numbers. The "expected 7.2m" — where does that come from? Is that the actual roof, or is that another number on another page that someone decided was the truth? If your ground truth is "what a different page says," you're measuring agreement between two documents, not accuracy.

Second thing that jumps out: you have **two projects**. Two. And you want to engineer your way from ±10% to ±2% based on n=2. A regular person would ask — how do you even know ±2% is achievable? Maybe the drawings themselves disagree with each other by more than 2%.

On the "cop-out" question — no. A roofer who's about to order €15,000 of materials wants to see the number that drives the bill and confirm it. That's not a cop-out, that's how every professional tool works (tax software, CAD, surveying). Hiding the dimension and hoping the AI nailed it is the cop-out.

What seems obvious that you might be missing: the gable-wall error came from reading width off the wrong page. That's not a vision problem, that's a *which-page-is-authoritative* problem. Humans solve this by knowing "ground floor exterior dimensions are the real building footprint." Encode that rule. You don't need ensembles or higher DPI — you need a hierarchy of which page wins for which measurement.

Start there. Cheaper, more honest, and it'll survive project #3 better than any model vote.

## The Executor (Response E)

Stop. Before anyone debates strategies, look at what you actually have: N=2. You cannot tell strategy #1 from strategy #4 from cosmic rays at N=2. Every "±2% target" conversation at this sample size is theater.

Monday morning, in order:

1. **Ground truth, not strategies.** Spend the day collecting 8-10 more roof projects with hand-measured truth. Mix of keturslaitis/dvislaitis, clean/CID-garbled, full/structural-only. Without this you're tuning to two PDFs and will overfit instantly. This is the bottleneck — everything else is downstream.

2. **Then fix the known bug, not the abstract goal.** The -8.7% on 0039 has a named cause: width pulled from a partial-rafter page. That's strategy #1 — multi-page orchestration with a "prefer floor_plan for axis dimensions" rule. One afternoon of work in `vision_extractor.py` + merger. Re-run both projects, confirm 0039 sienos drops under 2%.

3. **#5 is not a cop-out — it's the shipping plan.** Surface every extracted dimension in a "patikrinkite" panel before strategy runs. Roofer fixes the 7.12→7.20 in 3 seconds. You hit ±0% on the items they checked, log overrides as training signal for prompts later. Ship this in week 1.

Skip #4 (ensemble) and #7 (multi-shot voting) until ground truth exists — you'll burn budget voting on the wrong answer. Skip #6 (DPI) unless you actually see a vision read failure that looks DPI-bound; 0039 wasn't.

Concrete Monday task: write `build_roof_ground_truth.py` (the interior version doesn't exist either — same hole). Then fix the floor-plan-width pull. Then the override UI. In that order.

---

## Peer Review Summary

All 5 reviewers picked **Response E (Executor)** as strongest — only one with a sequenced, executable Monday plan grounded in the actual codebase.

All 5 reviewers picked **Response D (Expansionist)** as biggest blind spot — selling a "verified accuracy" premium badge before the underlying accuracy is measured (N=2 still). Flywheel assumes infrastructure that doesn't exist; Claude Vision via API isn't fine-tunable.

**Reviewer-converged blind spot (all five missed in advisor responses):**
- Drawings themselves may not be ±2% internally consistent. Architectural plans round to 100mm; axis dimensions disagree across sheets.
- A LAIDA and 0039 sąmatos are *different roofers' opinions*, not absolute truth — same AI-seeded-ground-truth trap CLAUDE.md flags for `detector_bench/`.
- Waste factors (CLAUDE.md §3: 5-10% for roofing) swamp extraction error. ±2% extraction is below the noise floor of the downstream material order.
- The right target may be "±2% on the **total** quote with every assumption surfaced," not "±2% per line autonomous."

---

## Chairman Synthesis

### Where the Council Agrees

**N=2 is the bottleneck.** Five out of five advisors plus all five reviewers converged: you cannot validate ±2% per line against two projects. A LAIDA at 2.8% and 0039 at 8.7% is a 3× spread, not a trendline.

**The -8.7% on 0039 is a page-authority bug, not a model bug.** Vision pulled width from a partial-rafter page when a floor plan page exists. Ensemble (#4), multi-shot (#7), and higher DPI (#6) are all answers to a different question.

**User-in-the-loop (#5) is NOT a cop-out** — provided it's framed correctly. The system commits to a number, surfaces the 3 most-uncertain dims with page crops, asks for confirmation. Every comparable professional tool works this way.

**Geometric cross-validation (#3) is free signal worth taking.** Floor area × slope_factor constrains roof width independently. Only proposed strategy that adds non-correlated information.

**Skip #4 (ensemble), #6 (DPI), #7 (multi-shot)** until ground truth exists.

### Where the Council Clashes

**Is ±2% the right target at all?** Executor and Contrarian implicitly accept the target. First Principles says ±2% autonomous is information-theoretically impossible from a single-source PDF. Expansionist says ±2% is a vanity metric. Reviewers sharpened: waste factors are 5-10%, so ±2% extraction is below the noise floor of the material order.

**Is the flywheel real?** Expansionist's "every correction becomes training data, N=2 → N=200" got rejected by four of five reviewers. Reasons: Claude Vision via API isn't fine-tunable, no storage/structure exists, roofers under time pressure rubber-stamp wrong numbers and poison signal.

**Inter-page / inter-rater disagreement.** Outsider and three reviewers raised: "expected 7.2m" might just be another page's opinion. A LAIDA and 0039 sąmatos are different roofers' guesses, not absolute truth.

### Blind Spots the Council Caught

1. **Inter-page consistency is unmeasured.** Drawings round to 100mm and disagree across sheets. Before claiming any accuracy target, measure how much a single axis dimension varies across pages of one project.

2. **Waste factors swamp extraction error.** Roofs ship with +8-10% waste baked in. Going from ±10% to ±2% on extraction is below the resolution of the material order.

3. **The flywheel needs infrastructure that doesn't exist.** Storing corrections, structuring them, feeding them back via retrieval/few-shot is its own project.

4. **Ground truth is contractor opinion, not truth.** Two sąmatos from two estimators is measuring agreement, not correctness — exact `detector_bench/` AI-seeded trap.

5. **Roofers rubber-stamp under time pressure.** HITL only produces clean signal if the UI forces real engagement (page crop, anomaly highlight, two-click confirm on flagged dims).

### The Recommendation

**Adopt the Executor's plan, with three corrections from peer review.**

1. **Build N=8-10 ground truth — AND measure inter-page variance on each project.** For each key dimension (axis_width, ridge_length, slope), record what every page that shows that dimension says. This tells you the floor of achievable accuracy. If pages disagree by 4%, stop chasing ±2%.

2. **Fix the page-authority bug (#1 with "prefer floor_plan for axis dims" rule).** One afternoon in `vision_extractor.py`. Named cause of -8.7%. Re-run 0039, confirm sienos drops under 2%.

3. **Ship #5 + #3 together, with friction.** Patikrinkite panel surfaces every dim *with the page crop it came from* and the geometric cross-validation result. Flag mismatches as 🟡 not 🟢. Two-click confirm on flagged dims — no "accept all" button.

**Drop the ±2% per-line-item target. Adopt "±2% on the total quote, with every assumption surfaced and confirmable."** Information-theoretically achievable, matches CLAUDE.md's existing operational rule that every calculation must show its assumptions.

**Reject the Expansionist's pricing/moat framing entirely until N>10 and the flywheel infrastructure exists.** Charging €99 with "verified accuracy" badging at 8.7% error on N=2 is exactly the "honest disclosure beats clever fixes" violation CLAUDE.md prohibits.

### The One Thing to Do First

**Write `backend/extractor/roof/build_roof_ground_truth.py` and run it on 8-10 projects this week, recording per-dimension *per-page* values, not just one number per project.** Without this, every accuracy conversation is fiction. With it, you'll know within a week whether ±2% is even achievable from the artifact.
