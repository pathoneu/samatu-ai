# Council transcript — Accuracy 4-week plan (2026-05-11)

**Question (raw):** pasiziurekit kodus, pasiziurekit kaip kas skaiciuojama, stress-testinkit vienas kita iki tol, kol grisite su tiksliu planu kaip improvinti accuracy projektu analizeje.

**Updated context (mid-debate):**
- CONSTRAINT 1 — rangovas ≠ 100% ground truth (each LT contractor calculates differently). Yardstick must be universal math (RICS NRM2 + DIN + LT STR + CLAUDE.md §1), not rangovas. Parsed rangovas (242 lines, ~168k EUR, 5 projects) is *reference corpus* only.
- CONSTRAINT 2 — Parallel council already decided Option F (no-CV MVP). Focus: prod bugs (lubų >3m, stale cards) + customer discovery (3–5 builders) + inline-number hypothesis. Per `2026-05-11-council-cv-strategy-decision.md`.

**Repository signals fed to all advisors:**
- Vision pipeline `vision_call.py` 2732 LOC, prompt v3, mature
- `universal_rules.calc_room_quantities` + `_build_pozicijos_from_rooms` exist
- 2026-04-28 priorities partly shipped: grindjuostės cap @ 0.65, angokrasciai_m, pasleptu_duru_staktu_m
- `backend/extractor/benchmark/eur_weighted.py` + `lt_unit_prices.json` scaffolded; prices rangovas-derived
- VISION violation `vision_call.py:1100` — returns aggregated `angokrasciu_gkp_m_total` (should be raw geometry only per Vision-perception/Python-arithmetic principle)
- CV V2 infra on disk, NOT mounted, frozen by Option F

**Anonymization map for peer review (revealed after review):**
- Response A = Outsider
- Response B = Executor
- Response C = Contrarian
- Response D = Expansionist
- Response E = First Principles Thinker

---

## Round 1 — Advisor responses

### The Contrarian (Response C)

**The fatal flaw: you don't have a customer yet, and you're writing a 4-week accuracy plan.**

Stop. The 2026-05-07 production test was *one* real PDF. You have zero paying users. You have not validated that "AI suggests 26 outlets" is even the unit of value LT builders will pay for. And you're about to spend 4 weeks tuning math against a yardstick (universal RICS/DIN) that no Lithuanian contractor cites in their pasiulymai. rangovas doesn't use NRM2. None of them do. You're building accuracy against a standard your buyers have never heard of.

**What you're avoiding:** the customer discovery calls. Option F said "3-5 LT builders in parallel" — that's the actual experiment. Everything else is yak-shaving. If 3 builders tell you they only care about KŽ extraction speed and don't trust any AI quantity, your universal-math benchmark is worthless on day 28.

**What breaks in week 2:** you'll discover the "lubų >3m" bug is a symptom of 8 more page-classification edge cases, the inline-number hypothesis test requires UX you haven't built, and the `vision_call.py:1100` refactor cascades into 200 LOC of prompt rewrites. Week 4 you ship nothing.

**On the EUR-weighted benchmark:** kill it. If rangovas isn't GT, then a benchmark weighted by rangovas's prices measures agreement-with-rangovas dressed up in money. Same AI-seeded ground truth problem from the bake-off, rebranded. Already flagged in CLAUDE.md and about to repeat the mistake.

**Real priority order:** Week 1: prod bugs + 3 customer calls *before writing code*. Week 2: build the smallest thing the calls demand. Weeks 3-4: TBD based on what week 1 taught you. Anything else is procrastination disguised as engineering.

### The First Principles Thinker (Response E)

Stop. You're conflating three different problems and calling the bundle "accuracy."

**Problem A:** Does the math (CLAUDE.md §1 formulas) produce the right number *given correct inputs*? This is a unit test. It's either right or it's a bug. It has nothing to do with PDFs, Vision, or rangovas. You can fix it in an afternoon with pytest.

**Problem B:** Does Vision extract the right *inputs* (room perimeter, ceiling height, opening count, wall thickness) from a PDF? This is the only thing that needs a benchmark — and the benchmark is **dimensions stamped on the drawing**, not rangovas's bid. The drawing literally has the ground truth printed on it. Build a 20-room human-labeled fixture of "perimeter=14.2m, h=2.65m, 2 windows" and measure Vision against *that*. rangovas is irrelevant.

**Problem C:** Will a Lithuanian builder pay 50€/mo for this? Unknown, unrelated to A or B, and the dominant risk.

Now the actual question: at pre-revenue, MVP-in-6-weeks, zero paying users — **accuracy is not your north star.** Willingness-to-pay is. You don't know if buyers care about ±5% vs ±15%. You don't know if they want full automation or "AI-suggested row I edit." A 4-week accuracy sprint before 5 customer calls is building a faster horse before checking if anyone wants a horse.

**Reframe the 4 weeks:**
- Week 1: prod bugs (real users hit them) + 5 builder calls. Nothing else.
- Week 2: ship inline-number hypothesis to those 5 builders. Watch them use it.
- Week 3: fix Problem A (formula unit tests) + the L1100 boundary violation — both are cheap correctness work, not "accuracy."
- Week 4: *if* calls revealed accuracy is the blocker, build the dimensions-from-drawing fixture for Problem B. Otherwise build what the calls revealed.

Kill the EUR-weighted benchmark. It measures agreement with one contractor's pricing — that's not accuracy, that's mimicry.

### The Expansionist (Response D)

Everyone is treating "universal math benchmark" as a QA tool. It isn't. It's the product.

Once you encode RICS NRM2 + DIN 18363 + STR + CLAUDE.md §1 as an executable rule engine, you stop being a takeoff app and become **the canonical "what does LT building code actually require you to quote?" engine.** Every LT estimator currently guesses whether Q4 sanding is a separate line, whether <0.5m² openings deduct, whether hidroizoliacija belongs in the bathroom row. You will *know*, with a citation. That's a compliance product. Sell it to: insurance adjusters validating renovation claims, APVA auditing modernizavimas subsidies, banks underwriting construction loans, courts in statybos ginčai. None of those buyers care about your CV pipeline.

The parsed rangovas corpus is a goldmine you're underusing. Five proposals is enough to ship a **"LT Contractor Variance Index"** — show a builder "your grindjuostės markup is 23% above the LT median, your angokraščiai pricing is 15% below." Builders will pay to see where they're leaving money on the table. Get 20 more proposals (offer free extraction in exchange) and you have a defensible pricing dataset no competitor can replicate without 6 months of LT-specific work.

Inline-number hypothesis positive means something bigger than UX: it means **the PDF is already a structured database** and you're the parser. That unlocks auto-generated F2/F3 forms, defektinis aktas drafts, and direct Sistela export — i.e. the entire LT documentation stack, not just the quote.

The moat isn't accuracy. It's **codified LT regulatory truth + bidding-variance data**. Both compound. Both are invisible to anyone copying your UI. Build the rule engine as a public, citable artifact — that's your TechCrunch moment.

### The Outsider (Response A)

A LT contractor lands on your page. They don't care about EUR-weighted error metrics. They don't know what RICS NRM2 is. They have never heard the phrase "universal math benchmark." They would not recognize "angokrasciai" as a feature — that's just a thing in a drawing.

What they care about: **"I spent 4 hours on a quote last night and lost the job because I was too slow."**

Half the words in your brief are gibberish to a buyer. "Lubų >3m not auto-detected" — translation for a builder: *"the app got the ceiling height wrong and I had to fix it manually."* Why is that in engineer-speak in your own planning doc? Because you've stopped thinking like a buyer.

The "inline-number hypothesis" — I have no idea what that is. It sounds like a research paper. If it can't be explained to a contractor in one sentence ("you click a number on the PDF and it goes into your quote"), it's not a feature yet, it's a hunch.

Hard truth: **your benchmark is wrong.** You're optimizing for "matches universal math." A buyer's benchmark is "did this save me 3 hours and did the total at the bottom look right enough that I'd send it to a client." Those are different problems. The second one tolerates 10% error if the workflow is fast. The first one tolerates a 4-hour workflow if math is pristine.

What would convince me to pay? **A 90-second video of a real PDF going from upload to a finished quote PDF I could email a client.** Not accuracy charts. Not rangovas-vs-universal-math. A demo.

Week 1 should be: talk to 5 builders, ask them to time their last quote, and watch their face when you show the demo. Everything else is premature.

### The Executor (Response B)

**Monday, hour by hour.**

**09:00–09:30.** Open `backend/api/vision_call.py`, jump to L1100. Delete the aggregated `angokrasciu_gkp_m_total` field from the returned dict. Ship it. That's your pre-lunch one-liner — Vision/Python boundary cleaned in 20 minutes.

**09:30–12:00.** Lubų >3m bug. Grep `vision_call.py` for `ceiling_height` / `lubu_aukstis`. Find the room-extraction prompt block. The bug is almost certainly: prompt asks for ceiling height but doesn't instruct Vision to scan section drawings or "+2800"-style annotations on lubų planas. Add one sentence to the prompt: *"If any room shows ceiling height >2.75m on section/lubų planas, return that exact value, not the default."* Add a Python post-check: if `room.ceiling_height is None and room.area > 15`, log warning. Deliverable by lunch: re-run projektas_1 PDF, verify p1 ceiling reads correctly.

**13:00–15:00.** Project-load cards stale bug. This is frontend — `localStorage` not re-hydrating on mount. Open `frontend/src/`, find the projects list component, fix the useEffect. 2 hours max.

**15:00–18:00.** Customer discovery prep. Write 5 emails to LT builders. Send them. This is the only thing on Monday that creates revenue optionality.

**Universal-math benchmark = `backend/tests/test_universal_math.py`.** Not a framework. Hand-code 5 rooms from projektas_1 with known dimensions, assert `calc_room_quantities` matches CLAUDE.md §1.1 formula within 2%. First test: a 4×5m room, h=2.7m, 1 door, 1 window → assert `S_walls_net == 48.6 - 1.8 - 1.6`. That's it. Ten lines.

**If 1 week only:** Bugs Monday. Inline-number prototype Tue–Wed (just render Vision output as KŽ rows, no canvas). Customer calls Thu–Fri. Skip the benchmark — write it week 2 when you have real builder feedback telling you which formulas actually matter.

---

## Round 2 — Peer reviews (5 reviewers, anonymized)

### Reviewer 1

1. **Strongest: E.** Only response that cleanly separates the three conflated problems (math correctness, input extraction, willingness-to-pay) and gives each its own test. The "drawing itself has ground truth stamped on it" reframes the question correctly. B is close second for execution density.
2. **Biggest blind spot: D.** Beautiful pitch, wrong stage. Pre-revenue solo dev with one prod test does not ship a "canonical LT compliance engine" to insurance adjusters and courts in 4 weeks. Strategy fiction at MVP stage.
3. **All missed:** 2026-05-07 prod test was N=1. Before any 4-week plan, run the *existing* pipeline on 5-10 more real PDFs from prospective builders' archives — surfaces real bug distribution and doubles as discovery. Nobody questioned whether 1-2 month MVP launch is itself the wrong constraint.

### Reviewer 2

1. **Strongest: E.** Only one that cleanly separates three problems and proposes the right test for each. Nails the benchmark fix — measure Vision against dimensions printed on the drawing itself. B operationally tight but takes the 4-week framing at face value. C right to push back but offers no W3-4.
2. **Biggest blind spot: D.** Builds a regulatory-compliance castle on zero buyer signal. "Sellable to APVA/banks/courts" is fan-fiction until one builder pays for the current product. First production test showed buyers can't even articulate "ceiling >3m" — nowhere near caring about NRM2 codification.
3. **All missed:** Ground truth itself is the bottleneck. Without `build_ground_truth.py`, every accuracy claim measures something other than truth. Customer calls won't fix that; one afternoon of human-confirmed GT on 3 PDFs would.

### Reviewer 3

1. **Strongest: E.** Cleanly decomposes three problems. "Drawing has GT printed on it" is the only one that escapes the AI-seeded-GT trap CLAUDE.md flags as the project's #1 open issue. Week sequencing concrete and W4 contingent on W1 learnings.
2. **Biggest blind spot: D.** Reframes universal-math as regulatory-compliance moat (APVA/banks/courts) without a single data point that any of those buyers exist, will pay, or care. Exactly the "procrastination disguised as engineering" C warned about.
3. **All missed:** The 2026-05-07 production-test memory — a real builder used the app and hit two specific bugs. That's a live customer signal sitting in front of them. None of A-E mention it. W1 should start there — not 5 cold calls (A/C/E), not L1100 (B), not compliance pivot (D) — because one real user's friction beats five hypothetical ones.

### Reviewer 4

1. **Strongest: E.** Cleanly separates math correctness (pytest), vision extraction (benchmark against printed dimensions), WTP (dominant pre-revenue risk). Kills EUR benchmark for right reason (AI-seeded GT per CLAUDE.md), sequences W1-W4 honestly. B tactically excellent but answers "how" before "whether." A's "watch the face" insight is gold but it's a tweet, not a plan.
2. **Biggest blind spot: D.** "Compliance product to APVA/banks/courts" pre-revenue, solo, 4 weeks, zero customers, zero regulatory relationships, zero legal review of liability. Variance Index requires corpus of builders that don't exist yet. Series A pitch deck, not a 4-week plan.
3. **All missed:** L1100 boundary violation is a *symptom*, not a task. Real question is whether Python should own all aggregation post-Vision. Fixing L1100 in isolation guarantees the next aggregated field reappears within two sprints. Also: none asked what "MVP launch" means without auth or DB — localStorage isn't shippable to paying builders.

### Reviewer 5

1. **Strongest: E.** Cleanest decomposition. Killer insight: drawings print their own ground truth via dimension strings. Sequences correctly — bugs+calls W1, defer L1100 to W3 when calls have shaped priorities. B tactically tighter but accepts the premise; E reframes it.
2. **Biggest blind spot: D.** "Universal math = regulatory compliance product for APVA/banks/courts" is a fantasy moat built on zero evidence. No insurance adjuster has asked for this. Solo-dev pre-revenue MVP wins by repositioning as a B2G compliance play in 1-2 months is fantasy.
3. **All missed:** Prod-bug feedback loop. The 2026-05-07 user is the most valuable signal in the entire project — nobody proposed re-engaging them specifically. Also: "1-2 month MVP launch" deadline is self-imposed; none questioned whether shipping at all in 4 weeks beats 2 more weeks of discovery. Nobody priced L1100 as *carrying cost* (every future vision change pays interest) vs one-time fix.

---

## Round 3 — Chairman synthesis

See `council-report-2026-05-11-accuracy.html` for the visual report.

**Verdict:** Adopt E + B (problem decomposition + Monday execution discipline). Reject D (fantasy moat). Absorb peer-review additions: the 2026-05-07 prod user is the single highest-signal contact in the entire project — re-engage them before cold calls; treat L1100 not as a one-line fix but as a class-of-bugs to audit.

**The one thing to do first:** Email/call the 2026-05-07 production-test user *today*. Ask them to time their next quote with the current app. Watch them use it. Their actual friction sets the W1-W4 priority, not any of these advisor plans.
