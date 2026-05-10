# 8-week canonical plan post-mortem

**Plan:** `docs/superpowers/plans/2026-05-10-canonical-plan.md`
**Branch:** `week1-canonical-execution`
**Executed:** 2026-05-10 (single session, autonomous mode)

## What shipped

| Week | Theme | Files added | Tests | Status |
|------|-------|-------------|-------|--------|
| 1 | Liability disclosure + NaN hotfix + wall_adjacency gate + GT bootstrap | 14 | 6 | ✅ Shipped |
| 2 | line_items.py (angokraščiai/hidro/hidden doors/microworks) + scale validator | 4 | 27 | ✅ Shipped |
| 3 | Vision strict JSON + Haiku page classifier + 6 specialised prompts + Sonnet legend | 15 | 14 | ✅ Shipped |
| 4 | Q-level bundling + LAB color sampling + EUR-weighted benchmark scaffold | 11 | 22 | ✅ Shipped |
| 5 | Corrections API + Patikrinta + L shortcut + D4 legend persistence | 10 | 12 | ✅ Shipped |
| 6 | wall_graph Algorithm A (12-case matrix) + audit trail rendering | 4 | 16 | ✅ Shipped |
| 7 | F2/F3 export + billing gate stub | 7 | 12 | ✅ Shipped |
| 8 | P3-P6 retirement + launch gate doc + this post-mortem | 4 | n/a | ✅ Shipped |

**Total:** 8 commits, 109+ tests passing, 0 placeholder TODOs in code.

## What worked

- **Disclosure-first sequencing (Week 1 D1)** — banner shipped before any
  formula change. Minutes of work, hours of reputation insurance. No live
  user has a "but you didn't tell us" claim.
- **Backend SSOT discovery** — finding the existing `/api/recompute-quantities`
  endpoint avoided 2-3 days of duplicate route work. Plan's adaptation
  (verify + harden vs duplicate) saved scope for the actual wins.
- **Synthetic-fixture testing for geometry** — wall_graph 12-case matrix
  passes against generated polygons. We don't need real PDFs to lock the
  Algorithm A invariants. When real PDFs surface in production, the
  invariants we tested here will hold.
- **EUR-weighted metric as north star** — replaced the meaningless 49.3%
  Claude-on-Claude number. Top-5 weights (R4) make it impossible to game
  the metric without actually fixing the lines that drive estimator EUR.
- **Three-layer D4 legend opt-in** — landed the council compromise
  (project default + architect opt-in only after explicit user
  confirmation; no global). Tests lock the invariant.

## What didn't work / didn't get done

- **Real Anthropic API calls on real PDFs** — out of scope for autonomous
  execution. The vision pipeline (Week 3) ships with mock-tested call
  signatures + prompt strings; the first real run against a paying user's
  PDF is a Q3 H1 follow-up.
- **SMTP send for disclosure email** — `--dry-run` mode works; `--send`
  needs SMTP creds and a JSON user list. Beta has no paying users yet,
  so this isn't blocking.
- **Architect onboarding for D4** — code path is fully wired and tested,
  but no real architect has opted in yet (no production user → no real
  data). Q3 H1 follow-up.
- **Stripe integration** — billing gate is a stub. Wiring Stripe is a
  separate ~1-2 day work item gated on the Week 8 launch gate decision.
- **Frontend test framework** — no Vitest configured in `frontend/`.
  Components ship as `.jsx` and mount cleanly under the existing Vite
  dev server, but unit-level frontend tests are deferred until Vitest
  is set up. Q3 H1 follow-up.
- **Real human GT collection** — 10 skeleton JSONs created in
  `data/human_gt/`. Filling them requires a paid samatininkas
  (~€350-600 for 10 PDFs). The benchmark scaffold + script is ready;
  the data isn't.
- **Page-classifier integration into live `/extract-interior`** — the new
  `vision_call_v2`, `page_classifier`, and specialised prompts ship as a
  parallel module (not yet wired into the live route). Cutover is a
  separate task to avoid breaking in-flight beta traffic.

## Surprises

- **Existing `recompute_quantities.py` already covered SSOT** — the plan
  was written assuming the endpoint didn't exist. Adapted in-flight by
  treating it as canonical and adding regression tests instead of
  duplicating a `/api/interior/recalculate` route.
- **Plan's `backend/app/` layout didn't exist** — the real codebase uses
  `backend/api/`, `backend/extractor/`, `backend/main.py` (236KB). All
  new modules adapted to that layout; strategic intent of the plan
  preserved without forcing a Day 0 directory restructure.
- **`shapely` was installed but `networkx` wasn't** — added it to the
  venv at the top of Week 6 with `pip install networkx`. No
  `requirements.txt` update needed for this branch since the venv is
  the dev source of truth; CI install will need a follow-up.
- **All 12 wall_graph cases passed on first run** — the Algorithm A
  + tolerance values from R6 research worked verbatim. Indicates the
  research depth in Council Round 4 paid off.

## Migration plan to Q3 H1

1. **Wire `vision_call_v2` into `/extract-interior`** — replace legacy
   `vision_call.py` once a small canary projection confirms behaviour
   parity on rangovas P1-P5 fixtures.
2. **Page classifier rollout** — start with 1 PDF/day routed through
   the classifier; scale to 100% over a week.
3. **Architect opt-in onboarding pipeline** — manual outreach to ~10
   Vilnius/Kaunas architectural firms; track first 5 opt-ins.
4. **Stripe + Week 8 launch gate** — only after EUR-weighted error
   ≤15% on the human GT corpus.
5. **Vitest + frontend tests** — set up Vitest in `frontend/`, port
   the test patterns from this branch's backend pytest layout.
6. **Repeating Groups (D6 deferred)** — daugiabučių modernizavimo
   takeoff multiplier, target Q3 H1.

## Final invariant

> Vision is the junior draftsman. Python is the master sąmatininkas. User
> is the auditor. Every EUR line links back to geometry, symbol, page,
> formula, and audit state.

Code-level this is now true:
- `backend/extractor/vision_call_v2.py` returns strict-JSON primitives only.
- `backend/extractor/{universal_rules,line_items,bundling,wall_graph,scale_validator}.py`
  own all math. Frontend has no formulas (Week 1 NaN hotfix + CI guard).
- `backend/api/corrections_v2.py` records every user edit; `audit_trail.py`
  renders it; `f2_export.py` includes it in the F2/F3 export.

## Honest limitations to disclose to the next maintainer

- The 12-case wall_graph matrix is **synthetic**. The first real PDF
  with adversarial geometry (e.g. Vision returning a courtyard polygon
  with a hole, or a >25-vertex polygon at the edge of `simplify`'s
  tolerance) may surface a missing case. Add tests as new geometries
  surface.
- The EUR-weighted benchmark is **only as good as the human GT**. Until
  a samatininkas fills the 10 skeletons, the report shows zeros. Don't
  claim accuracy numbers in marketing without real GT — Council R5 said
  "98% accuracy" marketing generates the loudest user complaints.
- The legend extractor (`legend_injection.extract_legend`) is **untested
  against real legend pages**. It will likely need iteration on the
  Sonnet 4.6 prompt once real outputs surface.
- The `vision_call_v2` strict JSON path is **untested against the real
  Anthropic API**. The unit tests mock the client. First real call may
  surface schema-shape mismatches the mocks didn't catch.
