# Council transcript — Executable 4-week plan (2026-05-11 R2)

**Raw question:** Re-run /llm-council with full context (CV pivot doc, current bugs, code reality), produce a ready-to-execute plan with files, tests, acceptance criteria, research items, and risk register.

**Anonymization map for peer review (revealed):**
- Response A = Outsider
- Response B = First Principles Thinker
- Response C = Executor
- Response D = Contrarian
- Response E = Expansionist

**Verification by Chairman (post-debate):**
- ✅ D's grep claim: 26 `_total"` occurrences in `vision_call.py`. Pattern at L424-434 (read side) mirrors L1850-1860 (write side) — exact 11-field symmetry. Single-site L1100 fix would regress the other sites.
- ✅ C's `Dashboard.jsx:24` claim: `React.useEffect(() => { pullProjectsFromBackend()... }, [queryClient])` — mount-only effect, never re-runs.
- ✅ D's `universal_rules.py:553` claim: `grindjuostes = grindjuostes_base * 1.10  # +10% waste (NRM2 §27)`. CLAUDE.md §1.4 calls for +10% baseboard AND +5% cornice — cornice line is missing entirely from `calc_room_quantities`, not just wrong waste %.
- ❌ Peer Reviewer 3 hallucinated paths (`backend/api/vision_call.py` does not exist; correct path is `backend/extractor/vision_call.py`). Their critique of D is invalid.

---

## Round 1 — Advisor responses

### The Contrarian (Response D)

Three fatal flaws in the implied plan:

**1. "Vision/Python boundary at vision_call.py:1100" is mis-scoped.** I grepped: `angokrasciu_gkp_m_total` appears on lines 425, 1831, 1851 — and the *real* pattern is "Vision returns a `_total` aggregate, Python re-derives per-room." See `vision_call.py:425` (`s.get("angokrasciu_gkp_m_total", 0)`) and the symmetric write at 1851. If you frame this as "fix line 1100" you'll fix one occurrence and regress two. **Audit must be a grep for `_total"` across all 2732 LOC** before touching anything. There are likely 10+ similar aggregates.

**2. "Write test_universal_math.py W1" is the wrong yardstick if you skip the gap.** `universal_rules.py:553` adds +10% waste inline to grindjuostės — but CLAUDE.md §1.4 says +10% on baseboard, +5% on cornice. Are these two computed in one place or split? You don't know yet. Before writing the test file, grep for every `* 1.05`, `* 1.10`, `* 1.08` constant — your unit tests will lock in whatever's currently wrong if you assert against current outputs instead of CLAUDE.md numbers.

**3. "5 Rangovas PDFs = customer-call substitute" — dangerous framing.** Batch-testing reveals bug distribution, not willingness to pay or which bugs block trust. Spending W1 hunting bugs across 5 PDFs without re-pinging the contractor who promised to test is procrastination dressed as rigor. W1 acceptance criterion must include: "contractor X re-engaged with prod link."

**Risk if ignored:** W4 ends with a green test suite, a clean `_total` audit, 5 perfect Rangovas reproductions — and zero users.

### The First Principles Thinker (Response B)

Three separate problems hiding in one ask: (1) **Math correctness** — does `calc_room_quantities` faithfully implement CLAUDE.md §1? Answerable today, pure unit tests. (2) **Vision input correctness** — does the model extract the right rooms/dimensions/openings from a drawing? Needs hand-GT, probabilistic. (3) **Bugs blocking confidence** (lubų >3m, stale project cards) — felt-pain items from your own first prod test. These three have different feedback loops. Bundling them is the trap.

The real W1 question — and the one the user must answer before any plan is written: *if no contractor calls back for 4 weeks, what evidence in W1 would convince you the app is closer to shippable?* If the answer is "math is provably right" → write `test_universal_math.py` against §1, full stop. If "Vision reads p1 of Rangovas-1 correctly" → hand-extract GT from ONE PDF and diff. Don't batch 5. If "I trust the demo I'd give a contractor tomorrow" → fix the two bugs, ignore accuracy.

My vote: (b) unit tests first, because math bugs invalidate every Vision measurement above them. But the user must own this choice — not the council.

### The Expansionist (Response E)

Upside lives inside the four artifacts you're already building.

1. **The 5-PDF W1 batch test is a bug-class detector, not a pass/fail.** Bucket failures by class (scale misread / opening-deduction / per-room ceiling / wall-thickness default). One root-cause class probably owns 40%+ of EUR variance. Fix the class, not the symptom.
2. **`test_universal_math.py` is the compounding asset.** Each new PDF gets its drawing-printed dimensions frozen as fixtures. By W4 the file becomes your only honest accuracy number — replaces the EUR-Rangovas benchmark you killed. Future Vision-prompt tweaks become a 30-second pytest. 2× speedup.
3. **The `vision_call.py:1100` boundary fix is a prompt-tuning unlock.** Once that layer is clean, you can A/B prompts deterministically against the fixture set from #2.
4. **Wow-before-contractor (ship by W2):** confidence-annotated quantities with the source dimension shown inline. "Lubų aukštis: 3.20 m 🟢 (read from pjūvis p.4)". CLAUDE.md §7 already specifies this. Bigger "wow" than +10% accuracy he can't verify.

**Risks:** W1 batch reveals 5 different bug classes → fix highest-EUR fallback. Drawing-printed dimensions disagree across sheets → surface as finding. Fixture-freezing locks current Vision quirks → `@pytest.mark.golden`.

### The Outsider (Response A)

You are planning four weeks of engineering for an app with zero paying users. There is no "accuracy problem" yet — there is a "nobody has tried it" problem. "vision_call.py:1100", "Vision/Python boundary," "universal math," "EUR-weighted benchmark" — none of these words exist for the contractor. The ceiling-over-3m bug is not a 4-week item. It is a tonight item. Ship it before sleep. Same with stale cards — embarrassment bugs, not roadmap bugs.

The 4-week plan is procrastination dressed as rigor. Hour-by-hour W1, contingent branches W2-W4, `[RESEARCH]` tags, risk register — this is the comfort of pretending engineering is the bottleneck. It isn't. The bottleneck is one human running one real PDF and telling you what hurt.

Real plan, one page: Today/tomorrow fix the two known bugs, deploy. This week drive to that contractor, sit beside him, watch him quote one job. Record it. The next 3 weeks write themselves from what you saw. The 5 Rangovas PDFs are not a customer substitute. They are Rangovas.

Friday deliverable: 90-second screen recording of his own PDF being quoted, sent to his WhatsApp. Burn the 4-week plan. Book the visit.

### The Executor (Response C) — full plan

**W1 Monday hour-by-hour:**
- **09:00–09:30** Open `backend/extractor/vision_call.py:2218-2270`. Marker fallback only fires when section/ceiling_plan pages exist + page 1. Grep first: `grep -n "page_classifier\|tipas.*section" backend/extractor/`. Verify p1 of failing PDF passes through `scan_page_height_markers`.
- **09:30–10:30** Open `backend/extractor/height_markers.py`. Run `pytest backend/tests/test_height_markers.py -v`. If pass, reproduce on real PDF.
- **10:30–12:00** Create `backend/tests/test_universal_math.py` FIRST (TDD). One test per CLAUDE.md §1 formula: `test_dažomas_plotas_NRM2_no_deduct_under_0_5m2`, `test_angokrasciai_2H_plus_W`, `test_grindjuostes_perimeter_minus_doors_plus_10pct`, `test_paint_liters_2coats_1_8x`, `test_glaistas_Q4_1_5kg`, `test_GK_sheets_ceil_div_3_x_1_1`, `test_hidroizoliacija_full_floor_plus_splash_zone`. Aim 12 tests, all RED on launch.
- **13:00–14:00** Make tests GREEN. Fix `universal_rules.py` (NOT vision_call.py).
- **14:00–15:00** Lubų >3m fix. Add to Vision prompt: `"Jei pjūvyje arba lubų plane matosi žymeklis +3.000 ar didesnis (pvz. +3.200, +3.450), VISADA grąžink lubu_aukstis_m = tas skaičius. NIEKADA neatsakink 2.80 jei matosi žymeklis virš 3m. Jei nematai žymeklio — grąžink null, ne default."` Then strengthen `vision_call.py:2247` override threshold from `< cand_m - 0.3` to `< cand_m - 0.15`.
- **15:00–16:00** Fix stale cards. `frontend/src/pages/Dashboard.jsx:24` — change useEffect to also re-pull on window focus + `useQuery` `refetchOnWindowFocus: true`.
- **16:00–17:00** Fix boundary violation `vision_call.py:1100`. Move the loop INTO `universal_rules._build_pozicijos_from_rooms`. Run test suite.

**W1 Tue–Fri:** Tue run benchmark on all 5 Rangovas PDFs, diff vs drawing-printed dimensions, categorize errors by formula. Wed fix top-3 categories in `universal_rules.py` only. Thu visual diff tool. Fri tag `w1-baseline`.

**W2-W4 contingent branches:**
- **Branch A — Vision wrong > formulas:** if >40% errors are bad Vision input. W2 typed Pydantic schema at boundary; W3 split `vision_call.py`; W4 prompt iteration with golden-set regression.
- **Branch B — Formulas wrong > Vision:** if >40% errors are formula bugs. W2 expand tests to 40; W3 implement missing CLAUDE.md §1 items (hidroizoliacija, Q4 sanding, LED juostos); W4 cross-page validator improvements.
- **Branch C — Both ~equal:** ship count-correction UI per CLAUDE.md "Open/next". W2 inline-edit any quantity row with provenance pinning; W3 persist corrections to `data/corrections/`; W4 dogfood Rangovas PDF #4+#5.

**Trigger rule:** W1 Friday EOD count errors per category, pick branch by majority.

**[RESEARCH] items:**
1. Page classifier reliability on p1 — read `backend/extractor/page_classifier.py`. Run on 5 PDFs page 1, log tipas. If p1 mis-tagged → height-marker scan misses it.
2. Vision boundary surface area — `grep -n "parsed\[" backend/extractor/vision_call.py | wc -l`. Each aggregate Vision-side field is a candidate boundary violation.
3. Rangovas PDFs ground truth — hand-build `training-data/gt/projektas_N.yaml` from drawing-printed dimensions. ~2h work, replaces AI-seeded GT flagged in CLAUDE.md.
4. `universal_rules.calc_room_quantities` coverage — map each function to CLAUDE.md §1 formula. Missing entries = W2 backlog.

**Risk register:** vision_call.py regression HIGH (touch only prompt + L2247 threshold W1, no refactor until W3 with tag-revert plan); boundary fix breaks `_build_pozicijos_from_rooms` MED (snapshot test first); `refetchOnWindowFocus` price-edit thrash LOW (scope to Dashboard route); height-marker threshold 0.15 false override on Soviet 2.50m MED (asymmetric guard: only override when `cand_m > 2.95`); TDD pins wrong values LOW (cross-check each test against §1 line numbers in commit).

**Substitutes for customer calls:** Drawing-printed dimensions oracle (all 5 Rangovas PDFs have human-drawn `+2.800`, `+3.200`, `Plotas: 18.5 m²`). Cross-formula sanity per CLAUDE.md §6 (paintable/floor 2.5–4×, ceiling ≈ floor, baseboard ≈ perim − 0.8/door). Self-dogfood end-to-end Friday.

---

## Round 2 — Peer reviews (5 reviewers, R2 with skill access)

### Reviewer 1

D's specific line numbers are slightly off (425, 1851 — not 425/1831/1851) but the **pattern claim is correct and bigger than they said**: 26 `_total"` aggregates exist, not the single line:1100 the prompt named. Scope was genuinely mis-framed.

1. **Strongest: D.** Only response that empirically falsified the prompt's framing. "Fix line 1100" assumes one hotspot; grep shows 26. D also catches the test-trap (asserting against wrong-current-output locks in bugs) and names the AC the prompt buries: "contractor re-engaged."
2. **Biggest blind spot: C.** Most detailed plan, weakest grounding. Hour-by-hour cites `vision_call.py:2218-2270`, `:2247`, `Dashboard.jsx:24`, `:553` — and D just proved line numbers in this codebase drift. C also commits to "fix in universal_rules.py NOT vision_call.py" before auditing the 26-site boundary. The TDD-RED-first sequence is backwards per D's flaw #2: write tests against §1 *spec*, not current outputs, or you freeze bugs green.
3. **All five missed:** the project is on `week1-canonical-execution` with uncommitted CV work (`backend/api/cv_tools.py`, `data/corrections/`, `data/legends/`) — none acknowledged the *actual current branch state*. Plan can't start until that contradiction is resolved.

### Reviewer 2

1. **Strongest: D.** Only response that did the work — grep'd actual files. Two claims that should change the plan: `_total` aggregates at L425, L1831, L1851 (not just L1100). C's surgical L1100 fix regresses two other sites. Constants in `universal_rules.py:553` may already disagree with CLAUDE.md §1.4 (+10% baseboard, +5% cornice). TDD against a wrong implementation locks bugs in. **Audit constants before writing assertions** is the highest-leverage insight in the council.
2. **Biggest blind spot: C.** Writes hour-by-hour without verifying the boundary violation is localized to L1100 (D shows it isn't), and without checking whether math constants are correct before specifying 12 RED tests. A perfectly executed plan against the wrong target.
3. **All missed:** **The lubų >3m bug may not be a prompt/threshold problem at all** — it may be a page-classifier or pjūvis-extraction problem. None of A-E ran the failing PDF through the pipeline to see *where* the 2.5m default wins. Fix the diagnosis before the fix.

### Reviewer 3

*Chairman note: This reviewer hallucinated file paths (`backend/api/vision_call.py` does not exist; the actual path is `backend/extractor/vision_call.py`, named correctly in the brief). Their critique of D is invalidated — Chairman verified D's grep claims are correct.*

1. **Strongest (claimed): A.** Zero users with a contractor pending is a distribution problem.
2. **Biggest blind spot (claimed): D.** [Invalid — paths are correct.]
3. **All FIVE missed:** None checked whether the cited paths exist. *Chairman: this critique applies to reviewer, not advisors.*

### Reviewer 4

1. **Strongest: D.** D is the only response that audited the actual code before answering. The `_total` grep (L425, 1831, 1851) means C's "fix L1100 only, don't touch vision_call.py" is dangerously wrong — partial fix regresses siblings. D's catch that `universal_rules.py:553` already hard-codes +10% on all baseboards (CLAUDE.md §1.4 says cornice is +5%) means E and C's "lock current values in tests" would freeze a bug as ground truth. D also reframes W1 success criterion correctly: re-engaged contractor > N bugs closed.
2. **Biggest blind spot: A.** A is right that no-users-is-the-problem, but ignores that the user explicitly locked the premise: "no live user, contractor pending, MVP 1-2mo." A burns the question instead of answering it. Shipping bugs tonight on a `_total` boundary violation when D shows 3 sibling sites exist would brick the demo PDF mid-contractor-visit. Wrong order.
3. **All missed:** None checked whether the 5 Rangovas PDFs are representative of the *pending* contractor's drawing style. If pending contractor draws differently (different CAD, no +3.000 markers), W1 work optimizes for a dead benchmark.

### Reviewer 5

1. **Strongest: D.** Only response treating the codebase as evidence. The `_total` aggregate pattern at L425/1831/1851 invalidates C's entire "move boundary to universal_rules" plan — if pattern repeats 3 times, single-site fixes regress siblings. D also catches `universal_rules.py:553` disagrees with CLAUDE.md §1.4, which means E's "lock current values" would calcify a known bug.
2. **Biggest blind spot: A.** A's "burn the plan, drive to contractor" instinct is correct on customer signal, but ignores contractor is *pending* (locked context), not available Friday. A offers no fallback when the WhatsApp recording doesn't happen, and dismisses the math test as bureaucracy — yet D just proved the math is silently wrong. Shipping bugs tonight onto wrong formulas is worse than no ship.
3. **All five missed:** The AI-seeded ground truth problem (CLAUDE.md "Open/next"). Universal math + drawing-printed dims is still Claude-vs-Claude unless a human signs off. No response proposes the 1h `build_ground_truth.py` flow the README already points at — the highest-leverage W1 item per the project's own docs.

---

## Round 3 — Chairman synthesis

See `council-report-2026-05-11-execution.html` for visual report and final plan.

**Verdict:** Combine D's audit-first discipline + C's hour-by-hour structure + B's three-problem decomposition + E's compounding-asset framing. Reject A (premise is locked; "drive to contractor" not available this week). Absorb peer-review additions: branch state cleanup BEFORE any code change; lubų >3m needs DIAGNOSIS pass, not assumed-prompt fix; constants audit BEFORE TDD; surface dimension provenance in UI (E's wow-by-W2 idea — actually shippable).

**One thing first:** W1 Day 1 morning = a 2-3 hour AUDIT pass (read-only). Output: single report file `reports/2026-05-11-w1-audit.md` containing (a) `_total"` site inventory across vision_call.py; (b) every waste constant in universal_rules.py with CLAUDE.md §1 cross-reference; (c) failing-PDF instrumentation through pipeline showing exactly where 2.5m ceiling default wins. This 3-hour audit prevents 30+ hours of misdirected work.
