# LLM Council — "More Backend Accuracy, or Move to Frontend?" (2026-06-14)

**Method:** 5 advisors → anonymized peer review (3) → chairman synthesis. Companion to the 2026-06-11 council + experiments.

## Question
After a session of backend accuracy work, systematic debugging established: deterministic math is verified sound (byte-identical before/after; geometry −0.7%/−2.8% vs contractor truth where Vision reads cleanly); the benchmark MAE rose 6.66%→9.48% from **honest regeneration** of 2 extracts (not a code regression); remaining gaps (ciurliu −21%, lazunu −11%) are **Vision recall** on hard plans, not math bugs; 3 recall classes were declined as N=2 fitting traps; per-pozicija confidence (🟢🟡🔴 + Lithuanian reasons) is built but **invisible in the React UI**. Is there more high-value backend/accuracy work, or move to the frontend?

## Chairman's Verdict

### Where the council agrees (high confidence)
1. **The deterministic math is not where value remains.** All five accept the verification: remaining error is in Vision reading, not arithmetic. More recall *tuning* on N=2 is correctly declined.
2. **The confidence/bias-ledger work is the real asset** — a per-quantity, contractor-measured, plain-Lithuanian map of where the tool is weak. No black-box competitor (Togal/Kreo/Bluebeam) can match a tool that recites its own report card. It's a triage product ("check these 4 of 40, here's why"), not a QA feature.
3. **"Backend vs frontend" is a false binary** (First Principles): the gaps are Vision recall, which neither pure-backend-math nor pure-frontend fixes — the correction loop is the lever.

### Where the council clashed → resolved by peer review
- **Ship the colors now (Executor/Expansionist/Outsider) vs validate first (Contrarian/First-Principles).** The peer-review round broke this **decisively toward validate-first**: all 3 reviewers picked the Contrarian as strongest and the Executor's "ship the dot Monday" as the biggest blind spot.
- **Why:** surfacing 🟢 as "trust this" on top of a confidence signal that is itself **unvalidated** would *launder confidently-wrong numbers as trustworthy*. 0% false-green on N≈6 has a Wilson upper bound ~40% — statistically meaningless. The labels are decoration until checked against **human-confirmed** (not AI-seeded) ground truth.

### Blind spots the council caught (peer-review round)
1. **The confidence labels have never been validated against human truth** — and can't be on ~6 AI-seeded fixtures. "The colors and the validation are the same prerequisite."
2. **Silent failure has no completeness check.** (Chairman note: *verified* — lazunu's 4 rooms MATCH its eksplikacija, so it's complete; the omission hypothesis didn't hold on our anchors, but the gate is still sound defense-in-depth for projects where it would.)
3. **localStorage-only storage is a live P0 trust-killer** — one cleared cache loses a contractor's bid. Only the Outsider flagged it, and under-weighted it.
4. **Nobody verified the one customer actually uses it, on what.** A 20-minute call could moot all five roadmaps; with ~1 customer, that's the cheapest highest-value "research" there is.

### The recommendation
**Do NOT just surface the confidence colors yet — that was the trap.** The honest sequence:
1. **Validate the confidence signal against human-confirmed ground truth** (the standing `build_ground_truth.py` gap). Without this, the false-green rate (and therefore the colors) is unmeasured. This is the prerequisite to an *honest* frontend.
2. **Cheap deterministic completeness/consistency gate** (room-count vs eksplikacija when present; area-sum plausibility) — defense-in-depth, and it produces a real completeness confidence signal. Buildable now; won't move our two anchors but catches genuine omissions.
3. **Then** surface confidence + correction UI — at which point the colors are honest and the correction loop turns Vision-recall gaps into 30-second human fixes (and labeled training data).
4. **In parallel (user-driven):** a call with the one real customer; 3-5 independently human-built takeoffs.

### The one thing to do first
**Get human-confirmed ground truth on a handful of projects** (talk to the customer / build it). It's the keystone: it validates the confidence signal, re-baselines the benchmark honestly, and unblocks an *honest* frontend. Everything else is premature until the measurement is trustworthy.

*House rule: council output is hypothesis until verified. The room-omission premise was already partially refuted by checking lazunu's eksplikacija — apply the same skepticism to the rest.*
