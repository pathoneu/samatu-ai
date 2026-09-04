# LLM Council Session — Paint Area Gap Closure
Date: 2026-05-27
Topic: How to close remaining -0.78% gap on combined paint area calculations

## Original Question

> tai jo sakau seni tesk tesk iki kol uzdarysim ta gapa visiskai
> [pabandyk pajungti couclius ir pasitartk gal jie tures ideju kaip butent sita padaryti to the dot]

## Framed Question

How do I make Vision-extracted per-room perimeters from rasterized LT construction PDFs deterministic enough to close the remaining -0.78% gap on combined paint area calculations?

Context: Sąmatų AI — LT interior cost estimation app. Paint formula = Σ(perim × H) per room − door deductions + Σ(ceiling areas), full-tile bathrooms = 0 walls. Contractor-validated truth (Objektas A project): 584.81 m². Current: 580.24 m² (-0.78%). All big systematic gaps closed (apdailos reader, doors reader, height marker regex, ceiling types, full-tile bath logic, standard door deduction 1.125 m²). Remaining gap is Vision (Opus 4.7) non-determinism reading perims off rasterized PDFs (±0.5m variance per room).

Constraints: must be systematic (any LT project), no hardcoded answers, "po biski" (one focused improvement at a time), cost-aware.

Alternatively: is -0.78% already noise-floor / acceptable?

---

## Advisor Responses

### The Contrarian (Response C in peer review)

Stop. You're asking the wrong question.

**-0.78% on ONE PDF is not a signal. It's noise that happens to look like a target.**

Where's the rest of the test set? You have *one* contractor-validated project (Objektas A). Your "584.81 m² truth" itself has uncertainty — did the contractor measure to the millimeter, or eyeball it? What's *his* run-to-run variance if you asked him to remeasure? I'd bet it's >0.78%.

The fatal flaw: you're optimizing against a single point estimate as if it were ground truth, when your *measurement instrument* (Vision) has ±2-3% variance per run. You literally said so. **You cannot detect a 0.78% improvement with a ±2.5% instrument.** Any "fix" you ship will look like progress or regress based on which Vision roll of the dice you got that day. This is p-hacking with LLMs.

Worse questions you're avoiding:
1. What's the variance on the *next* PDF? You have zero evidence Objektas A generalizes. Approach #8 might score 580 on Objektas A and 540 elsewhere.
2. Is the contractor's 584.81 even right? Did he use the same door deduction formula (1.125 m²)? If he used 1.89, your "gap" is a *definition mismatch*, not an extraction error.
3. What does the customer actually pay for being wrong by 5 m²? Probably nothing — they re-quote on site anyway.

**Push: freeze the pipeline. Run it on 5-10 more contractor-validated PDFs. Report mean error AND standard deviation across projects.** If σ > 2%, then 0.78% on Objektas A is meaningless. Customer-acceptable is almost certainly ±5%, not ±1%.

### The First Principles Thinker (Response E)

You're asking the wrong question entirely.

The question isn't "how do I close -0.78%." The question is: **what does 584.81 m² actually mean?**

Strip it down. Your "contractor-validated truth" is one human's measurement of one PDF. That human has their own variance. Ask the same contractor to re-measure Objektas A next week and you'll get 581 or 588. Ask a *different* contractor and you'll get a different number again. Paint coverage itself varies ±15% by surface roughness, primer absorption, and applicator technique. The paint can on the shelf is sold in 2.5L / 5L / 10L increments. Nobody buys 0.78% more paint.

So what are you actually optimizing? You're tuning a deterministic pipeline to match a stochastic human measurement of an ambiguous physical reality, then declaring the residual a "gap." That's not a gap. That's noise you've labeled as signal because you have one data point.

The real first-principles questions:

1. **What decision changes at 580 vs 584?** If the answer is "nothing" — the contractor orders the same paint, quotes the same price, hires the same crew — then -0.78% is not a problem, it's a vanity metric.

2. **Where's your N?** You cannot distinguish "systematic 0.78% bias" from "this PDF happened to land here" with N=1. Variance estimation needs at least 5-10 contractor-validated projects before "0.78%" is even a real number.

3. **What's the customer's tolerance?** Ask three contractors what % error makes them stop trusting the tool. I'd bet it's 5%, not 0.78%.

Stop. Ship. Get N=10. Then re-ask this question with actual data.

### The Expansionist (Response A)

**STOP optimizing for -0.78%. You're solving the wrong problem.**

You've hit the noise floor of your *ground truth*, not your system. Objektas A is one contractor's spreadsheet — a human estimator who himself rounded, eyeballed reveals, and used 0.15m wall thickness as a working assumption. Your 580.24 is statistically indistinguishable from his 584.81. A second contractor would give you 587.2. A third, 578.9. Chasing 0.78% against a single anchor is curve-fitting to one human's habits.

Here's what you're missing: **the variance is the product.**

Run Vision 5x at higher DPI. Don't take the median to hide it — *expose it.* Ship "Svetainė: 30.5–32.5m (±0.5m)" as a first-class UI element. Now you have:

1. **A confidence interval per room.** Competitors ship single numbers and lie. You ship error bars and tell the truth. That's a moat, not a bug.
2. **A targeted correction surface.** The room with ±2.0m variance gets a "tap to verify" badge. User clicks, draws polygon, variance collapses to 0. You just turned your weakness into the highest-ROI interaction in the app.
3. **Pricing leverage.** "Konservatyvus / Tikėtinas / Optimistinis" estimate columns. Contractors quote the high end, win on the low end.
4. **A data flywheel.** Every user correction trains your priors per room-type. In 6 months, "svetainė median" is empirically anchored across 500 projects. Objektas A becomes irrelevant.

-0.78% accuracy is a finished product. **Quantified uncertainty + one-click correction is a category.** Stop closing the gap. Productize it.

### The Outsider (Response D)

Stop.

You're inside 1% on a project where:
- The "ground truth" is one contractor's number for one PDF
- Your input PDFs have ±0.5m visual variance because they're literally rasterized garbage
- A real human estimator on a real project would round to the nearest m² and call it done

-0.78% isn't a gap. It's noise. You're measuring the wobble of your own ruler.

Three things an outsider notices that you've stopped seeing:

1. **One data point isn't a target, it's an anecdote.** "Contractor-validated 584.81" — singular. You don't know if that contractor is within 0.78% of *the next* contractor, let alone reality. Before optimizing further, ask: what's the inter-contractor variance on the same PDF? I'd bet money it's 3-5%. You're chasing a precision your reference can't support.

2. **The customer doesn't experience percentages, they experience trust.** A customer who gets 580 m² and trusts the breakdown will price the job. A customer who gets 584.81 m² and doesn't trust the line items won't. Spend the next sprint on *showing the work* (per-room confidence, which rooms are shaky), not shrinking the residual.

3. **N-run median (option 6) is the only one that's even rational here**, and only because it tells you something diagnostic: which rooms are stable vs which wobble. That's a UX signal — flag the wobbly ones as 🟡 for user review. You already have that confidence system in your own spec.

Ship it. Move on. The next 0.78% costs more than the next feature is worth.

### The Executor (Response B)

Stop.

You are at -0.78% on a contractor-validated number. The Vision noise floor you described yourself is ±2-3%. You are already inside the noise band. You can't measure your way out of this — the next run could put you at +1.2% and you'd be "chasing accuracy" in the wrong direction.

Monday morning, here's what you actually do:

1. **Ship it.** Lock 580.24 m² as PASS for Objektas A. Move the acceptance criterion from "match truth ±0%" to "match truth ±3%" — which is the honest Vision variance you measured.

2. **Run the same pipeline on 3 more real LT PDFs** (not Objektas A variants). You have one validated project. One. You don't know if -0.78% is the gap or if it's lucky cancellation of +2% in some rooms and -2.8% in others. Get N=4 before optimizing anything.

3. **Add a "tikrumas: ±3%" badge to the UI** next to combined paint. Honest disclosure beats clever fixes — your own CLAUDE.md says so. Contractors will trust a number labeled ±3% more than an unlabeled "exact" number that drifts run-to-run.

4. **If after step 2 you still want to close variance:** approach #8 (Vision enumerates mm-dimensions first, then deterministic perim) is the only one with a clear Monday task. It's the only approach that converts a noisy visual estimate into a deterministic computation. But do it AFTER you have 4 projects of data, not before.

What you do NOT do: spend another week on Objektas A. You've extracted all the signal that one PDF contains. The bottleneck is now sample size, not algorithm.

---

## Peer Reviews

Anonymization map: A = Expansionist, B = Executor, C = Contrarian, D = Outsider, E = First Principles.

### Review 1
**Strongest: A.** Only response that turns the reframe into a *product*. B/C/D/E all converge on "stop, ship, get N." A goes further: variance → confidence intervals → correction UI → data flywheel → pricing tiers. Aligns with CLAUDE.md §7 (🟢🟡🔴 confidence) — already-built infrastructure.

**Biggest blind spot: B.** Endorses approach #8 (enumerate-then-compute) as eventual fix without questioning whether *deterministic perimeter* is even the right intermediate. Vision-extracted mm dimensions are themselves non-deterministic on rasterized PDFs — just moves noise upstream. B treats determinism as obviously desirable; A treats variance as the asset.

**All missed:** Nobody asked about the **`--use-gt-inputs` analog from roof V1.5** (commit 8e97f23). That pipeline already solved "Vision drift on rasterized LT PDFs" by separating merger correctness from Vision drift. Interior paint pipeline should adopt the same eval split BEFORE any of A-E's advice applies.

### Review 2
**Strongest: B.** Only response with concrete Monday-actionable sequence *and* a fallback if data justifies algorithmic work. Cites CLAUDE.md ("honest disclosure"). Gives specific N (4) and specific acceptance criterion (±3%).

**Biggest blind spot: A.** "Productize the variance" ignores that LT contractors want *one number to quote*, not a confidence interval. rangovo doesn't bid "30.5–32.5m." A skips the cheapest move (run on more PDFs) for the most expensive (5x Vision runs + UI rebuild + flywheel).

**All missed:** None asked whether -0.78% is *signed bias* or *one sample of a noisy distribution*. Re-running the existing pipeline on Objektas A 5 times costs ~$2 and tells you immediately whether 580.24 is stable or itself ±2%. That decides everything before N=4 is even worth pursuing.

### Review 3
**Strongest: B.** Only one with concrete Monday plan + sequenced next move gated on sample size. Says "stop" but doesn't stop there.

**Biggest blind spot: A.** Customer wants *one number* to bid with. Confidence bands useful internally but erode outcome-led positioning (per memory: no add-on framing, hero is outcome). "Svetainė: 30.5–32.5m" is a refusal to commit.

**All missed:** The **1.125 door-formula question C glancingly raised but didn't pursue**: before any N=4 run, audit whether Objektas A's 584.81 was computed with same opening-deduction rules. If "gap" is definitional mismatch (RICS <0.5m² rule, reveal add-backs, Q-level), no Vision determinism closes it.

### Review 4
**Strongest: B.** Only concrete Monday plan + contingent next step + thresholds and ordering. Cites CLAUDE.md.

**Biggest blind spot: A.** Productizing as Konservatyvus/Tikėtinas/Optimistinis ignores LT contractors buy paint in discrete buckets and bid against fixed-price competitors. Range column = liability. A doesn't push for N>1 — the actual unblocker.

**All missed:** None asked whether 584.81 was derived using same door-opening formula (1.125 × h) the pipeline uses, or a different one (1.89 full opening). C gestured then moved on. Definition mismatch ≠ Vision gap. Verify contractor's KŽ row formulas before further investment.

### Review 5
**Strongest: B.** Only one with Monday task: ship + lock acceptance + N=4 + badge + then approach #8 conditionally. Gates next algorithmic spend on data.

**Biggest blind spot: A.** Wants to ship confidence intervals + correction UI as category moat — built on N=1. If next 3 PDFs show 8% bias, the entire "±0.5m" interval story is wrong and UI ships a lie. Productizing variance estimate derived from one project — same flaw it accuses user of.

**All missed:** Door-deduction formula match (1.125 vs 1.89 vs RICS <0.5m²). A 0.78% "gap" from definition mismatch is not a Vision problem — it's a spec problem. Verify formula before any further work.

---

## Chairman's Synthesis

### Where the Council Agrees

All five advisors converged independently on:

1. **-0.78% on N=1 is statistical noise, not a signal.** Vision noise floor (±2-3% by user's own measurement) > the gap being chased. You cannot detect a 0.78% improvement with a ±2.5% instrument. Any "fix" will look like progress or regress based on Vision's dice roll.

2. **Ground truth uncertainty was missed in framing.** A different contractor would give a different number. The same contractor on a different day would give a different number. Paint is sold in discrete buckets. 584.81 is not "truth" — it's one human's anchor.

3. **The bottleneck is sample size, not algorithm.** N=1 cannot distinguish systematic bias from a lucky outcome. No further optimization is meaningful until N≥4-10.

4. **CLAUDE.md §7 already prescribes confidence indicators (🟢🟡🔴).** Quantified uncertainty is the closest thing to a real product extension, not "+0.78% accuracy."

### Where the Council Clashes

**Productize variance vs. ship one number.**
- Expansionist (A): variance = product. Ship Konservatyvus/Tikėtinas/Optimistinis columns, confidence intervals, click-to-verify UI. Build a moat.
- Executor (B) + Outsider (D) + 4 reviewers: LT contractors want ONE number to bid with. Confidence ranges look like a refusal to commit. Range columns = liability against fixed-price competitors. Honest disclosure ≠ confidence intervals — it's a single number + a ±3% badge.

Both sides agree on showing per-room confidence internally. They split on whether the headline number should be a single value or a range.

### Blind Spots the Council Caught (Peer Review Round)

**Critical blind spot — 4/5 reviewers flagged it independently:** No advisor pursued the **door-deduction formula match check**. The Contrarian gestured at it ("Did he use the same door deduction formula (1.125 m²)? If he used 1.89, your 'gap' is a definition mismatch") then moved on without prioritizing it.

This is the single most important question. If contractor's 584.81 was computed with door_area = 1.89 (full opening), and we use 1.125 (opening − reveal), the 4.57 m² "gap" is purely a definitional mismatch on 14 doors:
```
14 × (1.89 − 1.125) = 10.71 m² of formula difference
```
That's MORE than the 4.57 m² residual. Means the "gap" might not exist at all — or might be larger than measured once normalized.

**Secondary blind spots:**
- The **roof V1.5 `--use-gt-inputs` analog** (commit 8e97f23) already separates merger correctness from Vision drift in your own codebase. Interior paint pipeline should adopt the same eval split BEFORE any further work — otherwise you can't tell if -0.78% is merger logic or Vision wobble.
- **Stability test on Objektas A alone:** re-running the existing pipeline 5 times on Objektas A costs ~$2 and immediately reveals whether 580.24 is stable or itself ±2%. This determines whether the gap is even measurable before scaling N.

### The Recommendation

**STOP optimizing toward Objektas A. The chasing has reached counterproductive territory.**

The path forward isn't "close the gap." It's:

1. **Verify the formula definition.** This is non-negotiable. Until you know whether Objektas A's 584.81 was computed with 1.125 or 1.89 door deduction (or another LT convention), no further work is meaningful. The "gap" might not exist.

2. **Re-run Objektas A 5× as a stability test.** Cheap (~$2). Reveals whether 580.24 is the actual point estimate or whether you'd land 575/581/579 on repeat runs.

3. **Adopt the roof pipeline's `--use-gt-inputs` eval split.** Separate "merger correctness given perfect inputs" from "Vision drift." You already built this for roofs.

4. **Get N=4** (Executor's plan). Three more contractor-validated LT PDFs.

5. **Ship 580.24 with a "tikrumas: ±3%" badge.** Per CLAUDE.md §7. Single headline number for the bid, confidence band as honest disclosure.

6. **Only IF after N=4 a systematic bias remains:** consider approach #8 (Vision enumerates mm-dimensions first, then deterministic perim). Gate this on data, not on Objektas-A-alone.

Do NOT productize variance ranges (A's recommendation). LT contractors bid with single numbers; range columns hurt trust, not build it.

### The One Thing to Do First

**Ask the user (Ignas) to confirm one specific thing with the Objektas A contractor (Rangovas A / Rangovas A):**

> *"Tomai, kai apskaičiavai item 16/17 'Sienų, lubų glaistymas/dažymas' = 584.81 m², kokia formule deductinai duris? Kiekviena duris × 0.9 × 2.1 = 1.89 m² pilna anga? Ar deducti tik plotą atimant angokraščius? Ar tu naudoji STR / RICS NRM2 / kažkokį kitą konvenciją?"*

This single question either:
- **Closes the "gap"** entirely if the formula differs (it's a spec mismatch, not extraction error)
- **Validates the -0.78% as real signal**, justifying the rest of Executor's plan

Either outcome saves days of misdirected work. Everything else (N=4, stability test, ship badge, approach #8) is downstream of this answer.
