# Week 8 paid launch gate decision (D3)

## Plans (canonical, never change without owner sign-off)

| Plan   | Price        | PDFs/mo | Overage      | Seats | Audience |
|--------|--------------|---------|--------------|-------|----------|
| Free   | €0           | 1       | —            | 1     | First-time samatininkai trying the tool |
| Pro    | €49/mo       | 10      | €8/PDF       | 1     | Freelance estimators, small contractors |
| Studio | €129/mo      | 40      | €5/PDF       | 3     | Small construction companies, multi-user |

**Hard rule:** never raise the entry tier above €49/mo. The LT estimator's
reference price is "0 — Excel'yje". Above €49/mo we lose to inertia even
with a 10× faster product (R5 council finding).

## Gate checklist (all must pass before flipping `BILLING_ENABLED=1`)

- [ ] **EUR-weighted error ≤15%** on top-5 lines, measured against the human
      GT corpus (10 GT + 5 unseen PDFs per `docs/benchmark_protocol.md`).
      Run `python scripts/run_eur_benchmark.py --out reports/benchmark/week8_final.md`
      and verify mean error ≤0.15.

- [ ] **Audit export works end-to-end:** `GET /api/export/v2/f2/<project_id>.csv`
      returns a CSV with the audit-history column populated for at least one
      corrected line. Sample: open in Excel, verify "5.0→6.5 (...)" appears.

- [ ] **No NaN tests pass:** `./scripts/validate_no_frontend_math.sh` returns
      `OK` AND `pytest backend/tests/api/test_recompute_no_nan.py` is green.

- [ ] **Backend/frontend parity:** changing assumptions in the UI yields the
      same totals as a direct `POST /api/recompute-quantities` call with the
      same payload. Manual smoke check on at least one project.

- [ ] **Disclosure banner remains visible** for beta — do NOT remove until
      Q3 H1 once paying users have provided 2+ months of correction telemetry
      validating accuracy claims.

- [ ] **At least one architect opt-in legend exists** (proves D4 flow works
      end-to-end). Verify `data/legends/architect/<architect>.json` has at
      least one entry; if empty, the architect-opt-in promotion path was
      never exercised in the wild.

- [ ] **Owner explicit sign-off** on this document.

## Decision

If ALL boxes above are checked:

```bash
# Production environment
export BILLING_ENABLED=1
# Or: persist via your deployment env vars (Vercel → Railway).
```

If ANY box is unchecked: paid tier remains disabled. Open a Q3 H1 follow-up
issue for each blocker, ranked by EUR impact from the latest benchmark report.

## Owner sign-off

- [ ] Engineering: __________________
- [ ] Product / Owner: __________________
- [ ] Date: __________________

## Pricing rationale (R5 + R4)

- Bluebeam Revu Basics ~€240/yr (~€20/mo) is the psychological floor for
  "professional software". Pro at €49/mo positions ABOVE Bluebeam Basics
  (more features) but UNDER Kreo Plus ($70/mo) and well under Togal Growth
  ($299/mo) — defensible mid-market position.
- TAM: ~3,000-6,000 LT prospects (micro/small construction firms +
  freelance samatininkai).
- Top GTM: architect-firm partnerships, Suskaiciuok.lt sponsored embeds,
  Resta trade show. Skip LinkedIn ads at $200 CPL — wrong economics for LT.

## What this gate does NOT cover

- Stripe integration (separate work item; blocks `BILLING_ENABLED=1` flip).
- Architect onboarding pipeline for D4 legend opt-in (manual outreach).
- Multi-language UI (LT first; EN/RU later if demand surfaces).
- F3 official LT regulatory format vs. F2 reuse (verify with samatininkas
  whether the reuse strategy holds for their compliance flow).
