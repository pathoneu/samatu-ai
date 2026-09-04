# LLM Council Transcript — Vision/Extraction Strategy Pressure-Test

**Date:** 2026-06-11 · **Method:** Karpathy-style LLM Council (5 advisors → anonymized peer review → chairman synthesis)
**Companion report:** `2026-06-11-council-vision-strategy-report.html` · **Related research:** `2026-06-11-vision-takeoff-sota.md`

---

## The framed question

Sąmatų AI (LT construction cost-estimation app, 2-person startup, hosted Anthropic APIs, modest budget) drafted a technical strategy for analyzing flattened RASTER construction PDFs and asked the council to pressure-test it before committing months of build.

**Constraints:** input format uncontrollable (messy raster re-exports); customers non-technical (pay = result); deterministic math layer verified accurate; N-pass voting just shipped and live-verified on the Objektas A fixture (paint −25%→+2.3%, kampai −36%→−10.6%, +13% wall-clock).

**Fresh research context (2026):** zero-shot VLMs cap at 42–51% on architectural drawings; fine-tuned YOLOv8 hits 82.5% mAP on scanned symbols; pure-VLM counting fails; agentic zoom helps but is fragile on noise; hosted-API determinism impossible (impose downstream); every funded competitor ships human-in-the-loop; accuracy leaders narrow scope; our own benchmark recently found to overstate production ~7.5× (AI-seeded ground truth).

**The drafted strategy:**
1. *Architecture:* deterministic scale calibration (detect+OCR) → fine-tuned YOLO symbol detector (bootstrapped from legend crops via Grounding DINO auto-labeling) → localizer-gated agentic VLM zoom → deterministic Python formulas → N-sample median + constrained flat JSON + agreement-spread confidence (🟢🟡🔴) → human-correction UI on flagged items.
2. *Sequencing:* reliability substrate first, then scale layer, then symbol detector.
3. *Expansion:* scaffold universal, detectors/formulas per-type, one type at a time, accept "80% AI + 20% human review" permanently.

**Questions:** (a) weakest point? (b) sequencing right? (c) scaffolding-over-model correct? (d) expansion thesis sound? (e) biggest missing lever? (f) steelman >90% autonomous.

---

## Advisor responses

### The Contrarian
Your evaluation loop is circular, and that's the fatal flaw. The detector will be trained on auto-labels from Grounding DINO — a model family that already fails on this task — and scored against ground truth your own docs admit is AI-seeded. Your benchmark already overstates production by ~7.5x, and the voting win everyone's excited about was measured on one fixture. N=1. You cannot tell whether any of this strategy works, and the plan contains no step that fixes that. Human-verified ground truth isn't housekeeping; it's the prerequisite for every other line item.

Second: the sequencing buries the actual product. The correction UI is listed last, almost as garnish — but every competitor you cite ships human-in-the-loop as the product, your own bake-off concluded "ship 50% AI + fast correction tool," and that UI is also your only realistic label factory. Every contractor click is a verified training example. Build it first and the YOLO bootstrap problem solves itself; build it last and you're fine-tuning on garbage for months.

Third: count the workstreams. Scale calibration, YOLO pipeline, auto-labeling, gated agentic zoom, IR contract, confidence system, correction UI — plus per-type detectors and formulas for *eleven* construction types. Funded teams narrow because per-type accuracy work doesn't amortize; the "universal scaffold" is the cheap 20%. Two people just lost three weeks rediscovering deleted readers. This plan is a platform roadmap wearing a startup costume.

And "deterministic scale" via OCR on iLovePDF re-rasterized scans isn't deterministic — it's a single point of silent catastrophic failure poisoning every downstream number.

Missing lever (e): corrections-as-labels flywheel. Steelman (f): >90% autonomous requires a large human-verified corpus per drafting style. You don't have one. Customers correcting your output is the only way you ever get one.

### The First Principles Thinker
You're optimizing the wrong variable. The product isn't "accurate extraction" — it's *a number a contractor will stake a bid on*. Strip it down: errors are fine if they're caught cheaply; errors are fatal if they wear a green dot. So the load-bearing component of your entire strategy is the one you treat as plumbing: **confidence calibration**. Agreement-spread measures self-consistency, not correctness — N samples from one model family happily converge on the same geometric hallucination. Your existential metric is the *false-green rate*: of items flagged 🟢, how many are wrong? It appears nowhere in the plan. Measure it first; everything else is decoration until it's near zero.

(a/e) The biggest missing lever follows directly: the correction UI isn't a fallback, it's your **data engine**. Every human fix is a labeled datapoint — the only ground truth you'll ever afford, the calibration signal, and the YOLO training set. Your own benchmark is AI-seeded and overstates production ~7.5×; bootstrapping the detector from Grounding DINO auto-labels is AI grading AI, the same circularity again. Humans must enter the loop as labelers, not just reviewers.

(b) Sequencing: substrate-first is right, but ship the correction UI *before* the detector — it manufactures the detector's training data.

(c) Scaffold-over-model is correct *because* of the flywheel; fine-tunes are downstream of owning labels.

(d) Competitors narrow because ground truth is per-domain, not because scaffolds aren't universal. Your thesis holds only at the speed you acquire validated fixtures per type — currently one (Objektas A).

(f) Steelman: >90% autonomous doesn't require zero errors — it requires near-perfect recall on "I might be wrong." That's achievable; omniscient extraction isn't. Build the company that knows when it's guessing.

### The Expansionist
**The asset they don't see: every human correction is a labeled training example, and they're the only player positioned to harvest it.** The drafted strategy treats "80% AI + 20% human review" as a permanent tax. Wrong frame. The correction UI sitting on top of a typed IR is an annotation factory where *customers pay you* to generate ground truth on exactly the distribution that breaks everyone else — messy Lithuanian raster re-exports. Togal falls to ~60% on messy scans; AECV-Bench caps zero-shot at 51%. Whoever owns the largest corpus of corrected messy-scan extractions owns the fine-tune nobody can replicate. Log every N-pass vote spread, every flagged item, every human fix, with provenance, from day one. That's the single biggest missing lever — it costs almost nothing now and is unrecoverable later.

**The expansion thesis is stronger than drafted.** Competitors narrowing scope are validating it: each is hand-building one detector with no scaffold. With the scaffold amortized, Sąmatų AI can enter a new construction type *before* building its detector — ship the correction UI as a fast manual takeoff tool for stogai/fasadai (contractors would pay for that alone), Wizard-of-Oz the extraction, collect the corpus, then automate. Every vertical launches at human accuracy on day one and gets cheaper monthly. That inverts the sequencing risk entirely.

**Steelman on >90%:** voting alone already moved paint from −25% to +2.3%. Errors here are *multiplicative across independent stages* — deterministic scale kills one class, fine-tuned YOLO kills counting (82.5% mAP exists today), gated zoom kills small reads (55→95.7%). Stack three independent halvings on a 40% error rate and you're at ~90% without any frontier-model improvement. It's within reach — but only if the flywheel is logging.

**Verdict:** sequencing is right; add the data-capture layer to the substrate, and treat review not as overhead but as the moat-generation engine.

### The Outsider
The thing nobody seems to be asking: **what does the customer actually pay for, and how fast do they get it?** This entire document is about extraction accuracy percentages. Not one number about turnaround time, price per project, or how long the "fast human-correction UI" session takes a non-technical contractor. Beam AI's "24–72h, ±1%" is the only customer-shaped metric here, and it belongs to a competitor.

What looks contradictory to fresh eyes:

1. **You cite research showing fine-tuned detectors beat VLMs, then plan to train YOLO on labels generated by... other AI models** (Grounding DINO auto-labeling). Your own notes admit "ground truth is AI-seeded" is a known problem. You're rebuilding the same circular-measurement trap one layer down.

2. **"Accept 80% AI + 20% human review as permanent" appears in point 3, but the correction UI is the LAST item in the architecture list and, per your own backlog, doesn't exist yet.** If human review is permanent product reality, it's the product. Why is the permanent part sequenced after the experimental parts (YOLO, agentic zoom)?

3. **Validation rests on "the contractor-validated fixture" — singular.** Months of build are being steered by one PDF. A normal person asks: how do you know any of these percentages generalize before you have ten?

4. **Everyone successful narrows scope; you widen. The justification is "the scaffold is universal" — but scaffolding is exactly the part competitors could copy.** The defensible part is per-type accuracy on messy Lithuanian PDFs, which is the part you're spreading thin.

(e) Biggest missing lever: **the correction UI as a labeling machine.** Every human fix is a free ground-truth label. Build it first and your YOLO training data, benchmarks, and confidence calibration all fall out of paying customers' clicks. That's the one move that compounds.

(f) >90% autonomous on messy raster? Nothing cited supports it. Stop steelmanning; sell the 80%.

### The Executor
**(a) Weakest point: the YOLO detector is your hidden yak-shave.** "Bootstrapped from legend crops via Grounding DINO auto-labeling" — you already tried Grounding DINO (Pipeline 5: died at 1 call, 402 errors) and template matching (Pipeline 3: 1772 counted where truth=5). Auto-labeling from sources that already failed, plus GPU training, label QA, and per-drafting-style drift, is 4-6 weeks of infra for two people. And your own bake-off conclusion says: ship ~50% AI + fast correction UI, don't chase the detector.

**(b) Sequencing is backwards at the end.** Reliability substrate first — correct, and mostly shipped (voting is live, spread→confidence is days of work). But the symbol detector should be *last or never until* two cheaper things exist: (1) the count-correction UI — it doesn't exist, your frontend already has the viewer, polygon editor, and provenance popovers, so this is ~1-2 weeks and it's what customers actually pay for; (2) human ground truth — `build_ground_truth.py` is still vapor, all your accuracy numbers measure agreement-with-Claude. You can't train or even evaluate a detector against AI-seeded labels. The ~1h interactive labeling flow dual-purposes as YOLO training data later. Do it first.

**(c/d)** Scaffolding-over-model: yes, your math layer proves it. Universal-scaffold expansion: no — research says leaders narrow; nail interior fully before facade.

**(e) Biggest missing lever:** correction-data flywheel. Every user fix in the correction UI is a free labeled example. Log them from day one.

**(f) >90% autonomous on messy raster:** requires per-style fine-tuned detectors + human-verified eval — not true this year. Accept 80/20.

**Monday morning:** spread→confidence wiring (1 day), then count-correction UI, then human ground-truth session. Detector decision deferred until those ship.

---

## Peer review (anonymization mapping: A=Executor, B=First Principles, C=Outsider, D=Contrarian, E=Expansionist)

### Reviewer 1
1. **Strongest: B.** It's the only response that identifies a genuinely new failure mode rather than re-litigating the backlog: agreement-spread measures self-consistency, not correctness — N samples from one model family converge on the same hallucination, so the 🟢 false-green rate is the existential metric and it appears nowhere in the plan. Everything else (flywheel, circularity, UI-first) is shared across A/C/D. A is the best execution plan; B is the best diagnosis.
2. **Biggest blind spot: E.** Its >90% argument stacks "three independent halvings," but the stages aren't independent — a silent scale-OCR miss (D's point) poisons detection, zoom, and formulas simultaneously. It also endorses widening scope against every cited empirical result, and "sequencing is right" contradicts the UI-buried-last problem the other four caught.
3. **All five missed two things.** First: the beloved corrections flywheel is currently *impossible* — the app has no auth and no database; projects live in localStorage. Logging "every fix with provenance from day one" requires persistence, accounts, and GDPR-grade consent for training on client-confidential drawings. That's weeks of unglamorous work nobody scoped. Second: correction data is selection-biased — users only fix errors they notice, so confident-but-wrong greens (B's own metric) never enter the dataset. The flywheel can't calibrate the exact failure mode that matters most.

### Reviewer 2
1. **Strongest: B.** It alone identifies the load-bearing flaw — agreement-spread measures self-consistency, not correctness, so N samples from one model family converge on the same hallucination. "False-green rate" is the only genuinely new, decision-changing metric proposed; everything in A/C/D follows from it. A is the most operationally grounded (Pipeline 5's 402 failure, `build_ground_truth.py` vapor, the Monday plan) and is the best runner-up.
2. **Biggest blind spot: E.** Its ~90% math multiplies "independent halvings" — but the stages aren't independent. A silent scale-OCR miscalibration (D's point) corrupts detection, zoom, and formulas simultaneously; errors correlate, they don't stack. E also blesses the widening expansion and the existing sequencing that the other four correctly reject, and assumes contractors will pay for a Wizard-of-Oz manual tool with no evidence.
3. **All five missed: the flywheel poisons itself.** Automation bias means users rubber-stamp 🟢 items — so corrections are anchored labels, not clean ground truth, and green items generate *zero* review data, making B's false-green rate unmeasurable by the flywheel alone. You need deliberate blind audits of green-flagged outputs. Also unaddressed: contractual/GDPR rights to train on customers' project PDFs and corrections — secure consent before logging.

### Reviewer 3
1. **Strongest: B.** It names the one metric that determines whether the product is sellable — the false-green rate — and correctly diagnoses that agreement-spread measures self-consistency, not correctness. Every other major point appears in 3+ responses; B's calibration framing is the only unique, decision-changing insight. A is runner-up — most grounded in project history and the best Monday-morning plan.
2. **Biggest blind spot: E.** Its >90% math assumes errors are independent and multiplicative — they aren't: one scale miscalibration corrupts every downstream stage at once. It takes 82.5% mAP and 55→95.7% at face value right after this team learned its own benchmark overstated production 7.5×. And "Wizard-of-Oz each vertical" means two people doing manual takeoffs — a consulting trap, not a moat.
3. **All five missed:** the flywheel's cold-start and label-quality problem. Corrections-as-labels requires paying users at volume — there is roughly one — and contractors only fix errors they *notice*, so the label stream is selection-biased precisely against false-greens, the failure mode B calls existential. Also: nobody priced N-pass voting as the default production mode on a modest budget.

### Reviewer 4
1. **Strongest: A.** It's the only response that grounds every claim in the repo's actual state — Pipeline 5's 402 deaths, Pipeline 3's 1772-vs-5, `build_ground_truth.py` being vapor, the viewer/polygon-editor already existing — and converts that into a costed Monday-morning sequence. That's execution-risk review; the others are strategy essays. Its one gap: it should absorb B's false-green-rate metric, the sharpest single idea in the set.
2. **Biggest blind spot: E.** Its >90% math multiplies other teams' benchmark numbers as if stages were independent — but a scale-calibration error propagates into every downstream quantity; errors compound, they don't halve. And "Wizard-of-Oz stogai/fasadai" means manual takeoff staffed by the same two founders who just lost three weeks to deleted readers.
3. **All five missed: the flywheel has a cold-start and a data-quality problem.** Corrections-as-labels presumes (a) volume — there has been one real production test; (b) accurate correctors — contractors only fix errors they *notice*, so silent false-greens never enter the corpus, recreating the AI-seeded bias one layer down; (c) contractual/GDPR rights to train on customers' confidential drawings. No customers, no labels — and nobody priced acquiring either.

### Reviewer 5
1. **Strongest: A.** Nearly every claim is traceable to project artifacts: Pipeline 5's 402 deaths and Pipeline 3's 1772-vs-5 overcount (bake-off docs), the "ship 50% AI + correction tool" conclusion, `build_ground_truth.py` being vapor, and the existing viewer/polygon/provenance components that make the correction UI a 1-2 week job. It converts evidence into a dated, ordered plan. D is close behind — the circularity argument and the OCR-scale single-point-of-failure are the deepest individual points.
2. **Biggest blind spot: E.** Its >90% case rests on multiplying "independent halvings" — but the stages aren't independent (same drawing, same model family; a bad scale read corrupts detector and zoom alike), and key figures are unsourced. It also endorses widening scope against the cited research.
3. **All five missed:** the correction flywheel is contaminated by anchoring bias. Reviewers shown an AI number mostly confirm plausible-wrong values — exactly the false-greens B worries about never get corrected, so "every fix is free ground truth" overstates label quality. Periodic blind labeling (no AI prefill) is required to keep the flywheel honest. Nobody priced N-pass voting's per-project API cost either.

---

## Chairman's Verdict

### Where the Council Agrees
1. **All five advisors independently named the same missing lever: the correction UI as a data engine** (corrections-as-labels flywheel). Five different thinking styles converging unprompted is the strongest signal a council can produce.
2. **The correction UI must move from last to first.** It is simultaneously (a) the product customers pay for, (b) the only affordable label factory, and (c) our own bake-off's standing conclusion. Sequencing the permanent part after the experimental parts was the strategy's structural error.
3. **The YOLO bootstrap as drafted is circular** — Grounding DINO auto-labels evaluated against AI-seeded ground truth is AI grading AI, the same trap as the 7.5× benchmark inflation, one layer down. Human-verified ground truth is a prerequisite, not housekeeping.
4. **Scaffolding-over-model is correct** — but *because* of the flywheel: fine-tunes are downstream of owning labels.
5. **>90% autonomous this year: no.** Sell the 80%. Reframe the ambition as near-perfect recall on "I might be wrong" (calibration), not omniscient extraction.

### Where the Council Clashes
- **Expansion.** The Expansionist's inverted model (enter each vertical as a manual-first correction tool, Wizard-of-Oz the extraction, collect the corpus, then automate) vs. the Contrarian/Outsider/Executor's "narrow and nail interior first." Peer review demolished E's >90% independence math but acknowledged manual-first vertical entry as the one defensible version of widening. Resolution: hold the all-types ambition, but each new vertical enters as a correction-UI product, automation strictly behind the corpus — and not before interior is genuinely strong.
- **Whether the detector ever gets built.** Executor: "last or never until correction UI + human ground truth exist." Others assume eventually. Resolution: decision deferred until a human-verified corpus exists — both camps accept this.

### Blind Spots the Council Caught (peer-review round — none of the five advisors saw these)
1. **The flywheel is currently impossible:** no auth, no DB — projects live in localStorage. Persistence + accounts + GDPR-grade consent for training on client-confidential drawings is unscoped prerequisite work.
2. **The flywheel poisons itself:** anchoring/automation bias — users rubber-stamp 🟢 items, so false-greens never enter the corpus. Requires periodic **blind audits** (re-extraction review with no AI prefill) of green-flagged items.
3. **Cold start:** ~one real customer; no volume → no labels. Customer acquisition is on the critical path of the *technical* strategy.
4. **Nobody priced N-pass voting** (now default-on) per project at scale.
5. **The false-green rate** (First Principles) — the load-bearing metric of the entire trust model — appears nowhere in the plan and is partially unmeasurable via the flywheel alone (see #2).

### The Recommendation
Amend the strategy:
1. **Keep:** deterministic math, voting/median substrate, deterministic scale step (with cross-checks, not as a single point of failure), confidence flags, one-construction-type-at-a-time.
2. **Resequence:** (i) finish the substrate *including a false-green measurement protocol*; (ii) **build the correction UI now** — as the product and the label factory, with persistence/auth/consent scoped into it; (iii) run the human ground-truth labeling flow (`build_ground_truth.py`) — dual-purposes as honest eval + future training data; (iv) deterministic scale layer; (v) **defer the detector decision** until a human-verified corpus exists.
3. **Add:** false-green rate as the tracked existential metric; blind-audit protocol for greens; provenance/correction logging schema designed into the UI from day one (cheap now, unrecoverable later); per-project voting cost tracking.
4. **Expansion:** each new vertical enters as a correction-first product; automate behind the corpus.

### The One Thing to Do First
**Measure the false-green rate today:** take the voted Objektas A extraction (and the other ground-truth projects), list every item the system would flag 🟢, and count how many are actually wrong vs contractor truth. One day, zero new infrastructure — and it tests the single assumption the entire product trust model stands on.

*(Standing house rule applies: council output is hypothesis until empirically verified on real PDFs — and the recommended first step is exactly that verification.)*
