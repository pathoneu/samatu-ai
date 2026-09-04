# LLM Council transcript — 2026-09-04 — contractor trust: what to build in four weeks
Process: 5 advisors (Contrarian, First Principles, Expansionist, Outsider, Executor — all Opus 5) answered independently; 3 anonymized peer reviewers (neutral / contractor's seat / engineer's seat — reduced from 5 deliberately, as in the 2026-08-03 council, because the picks converged on one response); chairman synthesis by the director (Fable 5.1). No client names — codenames only.
## Framed question
# Framed question (LLM Council, 2026-09-04)

**Decision:** Pathon (Lithuanian construction cost-estimation app — a vision-LLM reads interior-project PDFs, deterministic LT formulas compute quantities, the contractor prices them). The founder wants the product "extremely helpful to a contractor — any AI miscount fixable in 2 minutes, extremely easy to use". A real contractor is engaged; after seeing the app on his own projects he said "every number was more or less off, many way off". What should the next 4 weeks build, in what order, to (a) make the contractor's own sąmata reproducible row by row (his vocabulary, his granularity) and (b) make every remaining miscount fixable in ≤ 2 minutes — and what should be explicitly rejected?

**Evidence (read these files in the repo /Users/ignasgaldikas/samatu-ai; they are the case):**
1. `docs/superpowers/research/2026-09-04-row-level-accuracy-gap.md` — KEY: on the contractor's OWN two projects, row by row against his sąmata (53 and 111 quantified rows): only ~27 % / ~14 % of his rows within ±10 %, ~25 % way off, 38 % / 58 % missing or emitted without a quantity — stable across 3 production runs and two models. Our eval (3–20 % headline MAE on ~22 aggregated metrics) measures the wrong thing. No artefacts of the contractor's NEW projects exist in our systems.
2. `docs/superpowers/research/2026-09-04-deep-research-claims.md` — 25 director-reviewed literature claims: VLM symbol-count ceiling ~0.4–0.55 exact-match (doors/windows ~0.16 for Claude); text-anchored counts near-reliable; voting cannot fix systematic misreads; zoom helps small text, not counting; a small fine-tuned detector beats zero-shot frontier on symbols with ~300–400 labelled drawings; a vector/SVG lane helps room counting for some models but is model-dependent.
3. `docs/superpowers/research/2026-09-04-two-minute-fix-ux.md` — measured friction: 4 of 8 real correction scenarios are IMPOSSIBLE today (room area, 4 rooms wrong, missing/phantom room, doors/windows per room) because the room editor is dead code behind an unreachable tab; a recompute ERASES every „Teisinga ✓“; numeric fields don't select on focus; the €-risk queue leads with un-fixable material rows. Proposal: verify ROOMS not rows (72 decisions → 11, ≈ 90 s); a „Patalpos" grid beside the drawing as the core screen (confirm-before-numbers AND the target of every fix); visible ripple + undo; per-room finishes and opening counts.
4. Context: `docs/superpowers/research/2026-08-03-council-verdict.md` (prior council: the corrections table at 0 rows is the central fact; the contractor test is a data-acquisition event); `docs/superpowers/research/2026-08-23-foreign-project-ablations.md` (no room table ⇒ ~15 % error and room identities drift); `docs/superpowers/research/2026-09-02-calc-transparency-options.md` §1 (data reality: no opening coordinates; ~10 families un-decomposable); `CLAUDE.md` (formulas; accuracy > code beauty; verify before claiming).

**Constraints:** solo founder + AI agents; €2.5 and ~23 min per paid extraction; production deploys from main only with the founder's OK; the contractor can supply his PDFs and his own sąmatos if asked; corrections table in production = 0 rows; the app must stay simple for a non-technical contractor.

**Candidate directions to weigh against each other:**
(A) a per-contractor sąmata TEMPLATE learned from one priced sąmata (his rows, our quantities where we have them, „suveskite" where not) + a €-weighted row-level scorecard as THE accuracy metric;
(B) accuracy-first engine work (text-layer dimension/room-table lane, opening-reader determinism, a trained symbol detector);
(C) correction-first product (resurrect the room grid, room-first Patikra, measure-to-fix on the plan, verification that survives recompute);
(D) a "measure-first" product where the contractor clicks room outlines/openings on the plan and the AI only pre-fills.

Be concrete about the first shippable slice, the metric that proves it, and what NOT to do.

## Advisor responses

### The Contrarian

**The plan's #1 item is the one that poisons the asset.** "Carry `_review_status`/`user_verified_at` through both merge layers" (UX doc §5) is a *flat* carry — the same shape as `_CARRY_KEYS` at `backend/api/recompute_quantities.py:1115`. But `scripts/build_ground_truth.py:82` reads `user_verified_at` as quantity truth and mints an (ai_value, human_value) pair from it. A recompute that moved `sienos virš 3 m` 155,39 → 271,80 m² would carry a green check onto a number no human ever saw, and harvest it as human-confirmed. That is the truth-laundering the 2026-08-03 council named, shipped as a P0. The correct fix is invalidate-on-value-change with a visible „pasikeitė — patikrinkite" badge, not carry.

**Room-first Patikra manufactures false green.** Angokraščiai read +56 % on 08-31 and +1 % on 09-02 *on the same PDF*. That error lives in the opening reader, not in any room field. Confirm 11 rooms, and rows inherit ✓ over a volatility the contractor never looked at. Today the row is at least honestly unverified.

**The 90-second math covers the easy third.** 38–47 % (objektas_a) and 57–67 % (objektas_b) of his billed rows have no quantity, and they are *not* room-derived: hidroizoliacija 2 vnt, latakai 2, TRACK 20,06 m ×2, dekoro plytelės 28,8 m². On objektas_b that is ~63 rows to hand-type. Eleven room cards do not touch them.

**Reject B outright:** a detector needs ~300–400 labelled drawings (arXiv 2411.03707); we have 4 projects and 0 correction rows — and even fine-tuned, recall was 51 %.

**Two things nobody costed:** the 27 %/14 % figures come from his *own house*, the corpus's best project (3.10 % MAE) — the projects he actually judged left no artefacts anywhere. And nobody has measured his current time-to-sąmata. Both are free to obtain. Get his PDFs and that baseline **before** week 1, or four weeks get built against a proxy.

### The First Principles

The framing hides two assumptions I can falsify from disk in 90 seconds.

**"No artefacts of his projects exist."** `/Users/ignasgaldikas/samatu-ai/ground_truth/` holds **six** parsed sąmatos from the same contractor (`registry.yaml` labels all six "Rangovas A") — objektas_a/b/c/d/romainiai/sernu, 329 rows — and five carry a cached `ai_extract.json`. I scored all five row-by-row just now, no paid run: within ±10 % = 23 % / 6 % / 14 % / 32 % / 7 %; unmatched = 25 % / 55 % / 36 % / 34 % / 53 %. The scorecard the roadmap treats as a deliverable is a morning's script over data you already own, and it triples the sample. Build it first; let it order everything else.

**"€-weighted."** No price survives parsing — every one of the six `contractor_samata_parsed.json` files carries only `page/nr/section/name/unit/quantity`. Zero priced rows, six of six. A €-ranked metric is unbuildable this month. Rank by row count and ask him for one priced sąmata.

Now the reframe. "Every miscount fixable in 2 minutes" is the wrong denominator: on objektas_a that's 22 way-off + 13 unmatched ≈ 35 fixes ≈ 70 minutes. Nobody does that. The question is *how few decisions trust costs* — which is why room-first (72 → 11) is correct, and per-fix speed is a side effect.

Deeper: he isn't buying numbers, he's buying a document he can send. His skeleton is stable — the same five section headings across all six files — while row wording overlaps only 25–66 %. So (A) is right as a **family** template in his sections and his labels; it's fiction as a literal row list.

Reject (B): Claude scores 0.16 exact-match on doors/windows (arXiv 2601.04819) and a detector needs 300–400 labels against a corrections table at zero. Reject (D): that's asking him to do the takeoff.

### The Expansionist

**A wins, and it's bigger than a scoring fix — the priced sąmata is the product.**

`ground_truth/objektas_a/contractor_samata_parsed.json` already holds 58 of his rows with his sections, his units (`b/m`), his granularity (GKP lubos split 2,8 m / 3,4 m) **and his prices**. That one file is simultaneously: the eval, the row template, and the kainynas seed. `backend/api/price_lists.py` + `frontend/src/lib/applyPriceList.js` already exist to receive it. Nobody has noticed that "ask him for one priced sąmata" costs €0 and 0 minutes — versus €2.5 / 23 min per extraction — and moves the number that actually broke the meeting.

The upside is asymmetric. Engine work (B) buys read precision on the bucket that's already good — the deterministic text-anchored rows (Rotband −4 %, paint iki 3 m −7 %, every fixture count). It cannot touch the 38–58 % that has *no row at all*, and the literature caps it: Claude at 0.16 exact-match on doors/windows. A template flips those 20–74 rows from absent to present-in-his-name, with „suveskite" where the drawing can't answer — and every number he types there is a labelled row we never had, in his vocabulary, priced.

Second-order: the template is per-contractor, so his *next* project starts at his 58 rows, not at ours. Marginal cost of project #2 collapses. Ten contractors' templates = the first real Lithuanian row-and-price corpus — a data asset that survives even if extraction plateaus at 50 %.

**First slice:** sąmata upload → his row list → our quantities mapped in by section-aware match → export in his layout. **Metric:** €-weighted share of HIS rows present and within ±10 % (today ~27 %; target 60 % present, 40 % accurate). Then C's room grid so the residual is fixable.

**Reject outright:** the fine-tuned symbol detector, the vector/SVG lane, zoom loops, more voting, and D entirely — measure-first discards the 27 % that already works and makes us a slow Bluebeam.

### The Outsider

Naive question first: why does this app read the drawing before it reads his sąmata? He already owns the document he wants back — a priced list in his words. Ask him for two of them, parse them, and most of the "38–58 % missing" bucket disappears without touching the reader. That's direction A, and it's the only one aimed at what he actually complained about. He never said "your vision model is weak." A row he bills that we don't emit reads to him as a wrong number too.

Second: a contractor doesn't audit 72 rows and compute a hit rate. He scans, finds one number he knows is wrong, and stops believing the rest of the page. Trust here is binary, not a percentage. 27 % → 45 % buys nothing. Going from "these aren't my rows" to "these are my rows, three need my number" buys everything.

Third — three things in the UX doc would make me close the tab, and none are accuracy. The app calls my own 30-second-old row "pasenusi eilutė". One settings click deletes seven checkmarks I just made. A list headed "SUVESKITE PATYS (12)" has no box to type in. That is the software being rude about my work. Fix those first; they're all S-sized.

Reject D outright. If I trace room outlines myself, I'll use the ruler I already own — you've sold me a slower manual tool with a €2.5, 23-minute waiting room. Reject B for now: doors and windows aren't where his euros are.

And nobody has run his new PDFs. Get them and his sąmatos this week before committing four weeks to what one house said.

First slice: his sąmata pasted in → his rows come back, our quantities dropped in, empty typable cells where we have none. Metric: share of his invoiced € reproduced within ±10 %, and whether he exports it and bills from it.

### The Executor

**Week 1 — instrument, and stop the loop eating itself.**
Mon (S): add `_review_status` + `user_verified_at` to `_CARRY_KEYS` (`backend/api/recompute_quantities.py:1115`) and to `carry()` (`frontend/src/lib/mergeDarbuSarasas.js:260`). Metric: verifications surviving one recompute, 1/7 → 7/7. Same day (S): select-on-focus on numeric inputs; exempt `rnk-…` ids from the „pasenusi eilutė" badge.
Tue–Thu (M): the row scorecard. Don't write it from scratch — `scripts/reconcile_samata_lines.py` already carries 61 concept mappings and an `--all` flag, and **six** of his parsed sąmatas are already on disk (`ground_truth/{objektas_a..d,romainiai,sernu}/contractor_samata_parsed.json`). Extend `scripts/parse_all_samatas.py` to keep the kaina/suma columns — it currently drops every price, so € weighting is impossible today — then make concept-matched row hit-rate the headline in `eval_harness.py`. Baseline: 27 % / 14 %. Zero API spend. Every other decision is theatre until that number exists.

**Week 2 — (A), the template. M.** Union those six sąmatas into his row list: his labels, his granularity, our quantity where a concept maps, an input box where it doesn't. It is the only lever that touches the 38–58 % missing bucket; no reader improvement reaches those rows. Metric: share of his rows we emit *with* a quantity.

**Week 3 — (C), build-list items 1–10.** Re-home `RoomsGrid.jsx`/`RoomCard.jsx` out of the unreachable `tab === 'kiekiai'` branch (`InteriorProject.jsx:1093`) beside the drawing (M); ripple + undo (M); room-first Patikra (M). Metric: the four impossible scenarios → ≤ 10 s; 11 rooms in 90 s.

**Week 4:** per-room finishes and opening counts (M), then ONE paid run on his *new* PDFs, scored the new way.

**Reject:** detector fine-tuning (needs 300–400 labelled drawings that don't exist), zoom loops, voting, an SVG lane, model swaps (14 % vs 14 %), and (D) measure-first as the default — a contractor who must trace every room bought a ruler, not an estimator.

## Peer reviews (anonymization: A=Executor, B=Contrarian, C=Outsider, D=First Principles, E=Expansionist)

### Reviewer 1 (neutral)

**1. Strongest: D.** The only response that falsified the brief from disk rather than arguing from it, and both checks hold. `ground_truth/` has six parsed sąmatas — 58/121/44/58/16/32 = 329 rows — and every row carries only `page/nr/section/name/unit/quantity/raw_qty`. **Zero prices, six of six.** D's sequencing (score the five cached extracts first, €0) and its reframe — 35 fixes ≈ 70 min, so minimise *decisions*, not per-fix seconds — follow from evidence.

**2. Biggest blind spot: E.** Its whole case rests on "`objektas_a`… **and his prices**." That field does not exist. So E's first slice, its €-weighted metric and its "kainynas seed" all rest on a file it never opened. Secondary: A's Monday P0 is already shipped — `_carry_verification`/`_same_quantity` and `carryVerification`, both value-guarded, dated today. B reasoned to that exact design; A would ship the flat carry B warns against. B's `build_ground_truth.py:82` laundering path is real but now narrower.

**3. All five missed** the €0 falsification of the template hypothesis they're ranking. D measured 25–66 % row-wording overlap across his own sąmatas — so hold one of the six out, build the template from five, measure coverage. That settles A vs C before code. Nobody puts anything in front of the contractor before week 4.

### Reviewer 2 (contractor's seat)

Verified two disputed claims on disk before ranking: all six `ground_truth/*/contractor_samata_parsed.json` (329 rows) carry only `name/nr/page/quantity/raw_qty/section/unit` — **no prices**; and `scripts/build_ground_truth.py:82` does read `user_verified_at` as truth.

**1. Strongest: D.** It falsifies the brief's own premise ("no artefacts exist") with five cached row-by-row scores at €0, tripling the sample before anyone spends 23 minutes. It also fixes the goal: 35 fixes × 2 min = 70 min, so cut the *number* of decisions, not per-fix time. Its "his sections are stable, his wording isn't → template as family skeleton, not literal rows" is the only claim that survives contact with the files. C is the contractor's actual voice („pasenusi eilutė" on my own 30-second-old row) — keep that language.

**2. Biggest blind spot: E.** It builds its headline metric on prices that aren't in the file it cites. €-weighting is unbuildable this month, so E's plan has no scoreboard. B's truth-laundering catch is real and A ships that exact P0.

**3. All five missed:** dropping our quantities into *his* labelled rows makes wrong numbers more billable, not less. At 14–27 % hit rate, an unverified cell must ship blank, not filled.

### Reviewer 3 (engineer's seat)

**1. Strongest: D.** The only response that falsified the brief from disk before planning — and it checks out: keys are `page/nr/section/name/unit/quantity`, **0 priced rows, 6/6**. So D correctly kills the €-weighted metric as unbuildable this month, triples the sample using 5 cached `ai_extract.json` at zero paid spend, and reframes (A) from "his row list" (fiction — 25–66 % wording overlap) to "his section skeleton" (stable across six files). **A is second**: best day-by-day executability with real file:line, but its Week-1 Monday is already at HEAD — commit 81aa83a shipped value-guarded carry, select-on-focus and the badge exemption.

**2. Biggest blind spot: E.** Its load-bearing fact — "**and his prices**" — is false, so both its headline metric and its kainynas-seed story collapse. It also never sizes the 20–74 hand-typed „suveskite" rows (B did: ~63 on objektas_b). B's laundering warning is directionally right — `build_ground_truth.py:82` does mint truth from `user_verified_at` — but the fix it demands already exists as `_carry_verification`'s `_same_quantity` guard.

**3. All five missed:** the new metric is scored through `reconcile_samata_lines.py`'s hand-maintained 61 concept mappings. Hill-climbing it means adding aliases, not improving the product. Nobody proposes a frozen mapper, a holdout (`sernu` has no cached extract), or one non-Rangovas-A sąmata — `registry.yaml` itself warns all six are a single contractor.

## Chairman's verdict

## Where the Council Agrees

1. **Reject (B) engine-first work for the next four weeks** — all five, independently. The literature ceiling (Claude 0.16 exact-match on doors/windows; a detector needs 300–400 labelled drawings against 4 projects and 0 corrections; a model swap moved the row hit-rate 14 % → 14 %) means a reader upgrade cannot reach the bucket the contractor complained about.
2. **Reject (D) measure-first as the default** — all five: a contractor who must trace every room "bought a ruler, not an estimator", and it discards the 27 % that already works.
3. **The complaint is about the LIST, not the reads.** 38–58 % of his billed rows have no counterpart at all, and no reader improvement touches those. The only lever that does is his own sąmata as the skeleton (direction A) — refined by First Principles: his five SECTION headings are stable across all six sąmatas while row wording overlaps only 25–66 %, so the template is a *family skeleton in his sections and his labels*, not a literal row list.
4. **Cut the number of decisions, not the seconds per fix.** 35 fixes × 2 min ≈ 70 min — nobody does that. Room-first verification (72 decisions → 11) is the right shape; per-fix speed is a side effect.
5. **Fix the rude S-sized bugs first**: a recompute erased every „Teisinga ✓", the app called his 30-second-old row „pasenusi", the „Suveskite patys" list had no box to type in, numbers appended instead of replacing. (Three of four shipped locally today as 81aa83a — value-guarded, see clashes.)
6. **Get his NEW PDFs, his sąmatos for them, and his current time-to-sąmata baseline before committing four weeks to a proxy** (Contrarian, Outsider, Executor). The 27 %/14 % figures come from the corpus's own projects; the projects he actually judged left no artefacts anywhere.

## Where the Council Clashes

- **Template (A) first vs correction product (C) first.** Expansionist and Outsider: A first — it is the only thing aimed at what he said. Contrarian: room-first verification *manufactures false green* (angokraščiai read +56 % on 08-31 and +1 % on 09-02 on the same PDF — that error lives in the opening reader, not in any room field; confirming 11 rooms would let rows inherit a ✓ over a volatility he never looked at) and the 90-second maths covers only the easy third (objektas_b has ~63 rows to hand-type). Executor: scorecard → A → C. **Resolution:** verification must be per input-family — rooms confirm room-derived rows only (paint, ceilings, floors, skirting, corners); opening-derived rows (angokraščiai, door prep) get their own confirm step; and the €0 holdout experiment (below) decides how much A buys before either is fully built.
- **€-weighted metric.** Expansionist built its plan on "his prices" — three reviewers verified: none of the six parsed sąmatas carries a price. **Resolution:** count-weighted scorecard now; ask him for ONE priced sąmata this week.
- **Carry verification flat vs invalidate on change.** Executor's Monday item was a flat carry; the Contrarian showed it would launder unseen numbers into `build_ground_truth.py` (which mints truth from `user_verified_at`). **Resolved in code:** the carry is conditional on the rebuilt quantity being unchanged (±0,01) or user-owned.

## Blind Spots the Council Caught

1. **No prices exist in any parsed sąmata** (6/6) — the €-metric and the "kainynas seed" story collapse until one priced sąmata arrives.
2. **The template hypothesis can be falsified for €0**: hold one of the six sąmatas out, build the family template from five, measure how many held-out rows it covers. That settles A-vs-C before a line of product code.
3. **Unverified cells must ship BLANK in his rows.** At a 14–27 % hit rate, dropping our numbers into his labelled rows makes wrong numbers *more* billable. Only ledgered/verified quantities fill his cells; the rest are typable blanks.
4. **The new metric runs through a hand-maintained 61-concept map** (`scripts/reconcile_samata_lines.py`); hill-climbing it means adding aliases, not improving the product. Freeze the mapper, hold out `sernu`, and get one sąmata from a second contractor — `registry.yaml` warns all six are one person.
5. **Nobody put anything in front of the contractor before week 4.** Schedule a session at the end of week 2 on his own project with the scorecard and the template.

## The Recommendation

**Sequence: measure → template → room grid → contractor session. Explicitly not: readers, detectors, model swaps, measure-first.**

- **Week 1 (€0).** (i) The row-level scorecard becomes THE accuracy number in `eval_harness.py`: contractor rows reproduced within ±10 %, count-weighted, through a FROZEN concept mapper, with `sernu` held out; scored on all cached extracts (five projects, 329 rows). (ii) Ship the S bugs (done: value-guarded ✓ carry, `rnk-` rows kept, select-on-focus) plus: „Suveskite patys" becomes editable, a changed row gets a visible „pasikeitė — patikrinkite" badge. (iii) Founder asks the contractor for: the PDFs he judged, his sąmatos for them, ONE priced sąmata, and how long his own sąmata takes.
- **Week 2 — the family template.** From five sąmatas: his five sections, his labels, our quantities ONLY where a ledgered family maps, typable blanks elsewhere; export in his layout; measured against the held-out sąmata before it touches the UI. Contractor session at the end of the week on his own project.
- **Week 3 — the correction product.** Resurrect the room grid beside the drawing (the four impossible scenarios: area, four rooms, missing/phantom room, openings per room), room-first Patikra with per-input-family verification, visible ripple + undo.
- **Week 4 — his new PDFs.** One paid run each, scored with the new metric; target ≥ 20 correction rows written in the session; per-room finishes and opening counts if time remains.
- **Rejected for this period:** fine-tuned symbol detector, vector/SVG lane, zoom loops, more voting, model swaps, measure-first as default, €-weighting before prices exist, growing the concept map to move the metric.

## The One Thing to Do First

Build the row-level scorecard over the six sąmatas you already own — frozen mapper, `sernu` held out — and print today's number. Everything else in the four weeks is ordered by what it says.
