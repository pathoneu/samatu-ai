# Pathon Launch — Master Plan (2026-07-03)

> **For agentic workers:** This is the ROADMAP. Each workstream gets its own detailed implementation plan (superpowers:writing-plans) when it starts — do not implement from this document alone. Execution model: subagent-driven with controller browser/benchmark verification between phases.

**Goal:** Take the product from working prototype to a revenue-ready, professionally branded **Pathon** (renamed from Sąmatų AI) — accuracy upgraded and benchmarked, audited, secured, priced (billing built but dormant), redesigned, bilingual, with an admin cockpit and a marketing engine. Founder has contractors waiting; bias every choice toward the revenue-critical path.

**Founder decisions of record (2026-07-03):** rename to Pathon (international ambitions) · Fable 5 upgrade is benchmark-gated, mixed per-reader config allowed · corpus = 6 projects (2-3 complete) · billing BUILT but activated only on founder command (`BILLING_ENABLED` flag) · BIG design change ("looks a bit like a game" now) · magic-byte upload validation, no AV · LT primary + EN · brand-new marketing plan · **periodic numbers reports to founder for double-verification**.

---

## Sequencing & dependency logic

```
W0 Viewer finish (in flight)
W1 Fable 5 benchmark + engine upgrade        ──┐ (cost/project feeds W3 pricing)
W2 Codebase audit + security sweep            │ (clean base for everything after)
W3 Pricing model + Stripe (flag-dormant)    ◄─┘
W4 Admin dashboard v2                        ◄── W3 (revenue metrics, cost monitor)
W5 Pathon rebrand + full redesign            ──┐ (final screens before string extraction)
W6 i18n LT+EN                                ◄─┘
W7 Marketing engine + landing                ◄── W5 (assets in new brand), W3 (pricing page)
```

Why this order: accuracy is the product (W1 first — contractors judge numbers, not chrome); audit/security (W2) before building billing on top; pricing math (W3) needs W1's real cost-per-project; admin (W4) displays W3's Stripe + W1's telemetry; redesign (W5) before i18n (W6) so strings are extracted once from final screens; marketing (W7) last so it sells the rebranded, priced product.

---

## W0 — Finish the commercial viewer (IN FLIGHT)

Plan: `2026-07-02-commercial-viewer-buildout.md`. P1 declutter ✅verified · P2 rail/keyboard/statusbar ✅verified · P3 measurement (building) · P4 search/print/attribution → final full browser pass.
**Report to founder:** before/after screenshots, test counts, feature checklist vs the market-benchmark table.

## W1 — Analysis engine: Fable 5, benchmark-gated (Task 1)

1. **Benchmark harness first:** ingest the 6-project corpus (`~/Desktop/projektai` = batch-5 + new Nr. 6; contractor sąmatos = ground truth; classify which are complete vs partial). Extend the existing eval harness to run the FULL production pipeline per model.
2. **Baseline run** on `claude-opus-4-8` (current, 32 refs across 8 files) → per-project MAE on key quantities (dažymas, grindys, GK, tinkas, grindjuostės…), per-reader accuracy, tokens + € cost per project.
3. **Candidate run** on `claude-fable-5` (exact ID; temp 0 where not already; strict tool-schema JSON per reader — verify current state per reader first).
4. **Decision gate (with founder, numbers on the table):** flip globally, or mixed per-reader config; only where Fable ≥ Opus. Keep `MODEL_OVERRIDE` env fallback.
5. **Validation layer v2:** sums-of-parts checks, plausibility bands (§6 CLAUDE.md), low-confidence re-prompt loop; queue worker + retry/error handling on the new model map.
6. Centralize model IDs in one config module (kill the 32 scattered literals).
**Report:** benchmark table (both models × 6 projects × key quantities, MAE + cost), the per-reader decision, and post-upgrade re-run proving no regression.

## W2 — Codebase audit + security hardening (Tasks 2+3, one sweep)

Reality: JS/JSX + FastAPI/SQLite — **no TS/Prisma migration** (accuracy>refactor rule; founder informed). Scope: ESLint zero-error; logical-bug hunt (unit conversions mm↔m↔cm, missing await, race conditions, off-by-one, array indices); unit tests for every calculation lib (`interiorCalc`, `measureGeometry`, waste factors, universal_rules) + critical API utils; perf pass (N+1s, indexes, bundle split, upload compression); UI interaction sweep in live app. Security: session-auth matrix on every endpoint (401/403 paths), XSS payloads on inputs, CORS allowlist verification (app.pathon.eu/pathon.eu/api.pathon.eu + localhost dev), SQLi probes, secrets scan of client bundle, security headers middleware (CSP, X-Frame-Options, Referrer-Policy, HSTS), sliding-window rate limits on auth+analysis, Pydantic strictness on every route, upload magic-byte/MIME/size validation (PDF/PNG/JPEG only), `npm audit` + `pip-audit` clean, `security.md`. Builds on the 2026-06-19 invariants (don't redo — extend).
**Report:** counts (errors fixed, bugs found+fixed w/ severity, tests added, endpoints × auth matrix), before/after bundle size, audit results.

## W3 — Pricing + Stripe, built dormant (Task 5)

1. Real token/cost analysis from logs + W1 measurements → € cost per project (both models).
2. Financial model: single-project €X (≥40% margin), Basic monthly (Y projects + overage), Pro (high cap/unlimited, priority) — EUR, 21% PVM, Stripe Tax; `pricing.md` with break-even math.
3. Stripe Checkout (one-time + subscriptions) + webhooks → user limits; usage metering + upgrade-block prompt at limit.
4. **Everything behind `BILLING_ENABLED` (env + admin toggle, default OFF):** flag off = today's behavior exactly; flag on = full paywall. Pricing page ships visible-when-flagged.
**Report:** the pricing table with margin math per tier, cost sensitivity (Opus vs Fable mix), and a demo of the flag flip in staging.

## W4 — Admin dashboard v2 (Task 8)

Extend existing `AdminDashboard.jsx` (stats/costs/corrections) to: User Management (list/search/disable, per-user projects), Project Oversight (browse analyses, raw+processed, download plans), Analytics (projects, API cost trend, signups, Stripe revenue, conversion), Cost Monitor (per-project token spend, threshold alerts), System Health (queue/failed analyses, error log tail). Paginated, CSV export, double-secured (admin role + separate rate limit), `admin-guide.md`.
**Report:** dashboard screenshots with real numbers + the cost-alert demo.

## W5 — Pathon rebrand + professional redesign (Task 4)

1. **Logo:** Pathon wordmark + icon (precision/construction), SVG variants (full/icon/mono), favicon, app assets.
2. **Design system:** typography (Inter/Montserrat headings, system body, tabular mono numbers), spacing/shadow/radius scales, color tokens — professional, NOT game-like; founder authorized BIG change (this amends the old keep-light-palette note).
3. Restyle every screen (login, dashboard, project list, upload, results/workspace, admin) + rename all user-facing "Sąmatų AI" → "Pathon".
4. Interactive polish: skeleton loaders, transitions, toasts, empty states; mobile-first responsive; onboarding tooltip flow; WCAG AA (contrast, keyboard, ARIA).
**Gate:** founder reviews logo + design direction on mockups BEFORE mass restyle. **Report:** before/after screenshots per screen, Lighthouse + a11y scores.

## W6 — Localization LT+EN (Task 6)

react-i18next, fallback EN; extract ALL strings → `lt.json` (professional construction terminology — LT is source of truth) + `en.json`; language selector in nav (cookie-persisted); `Intl` lt-LT dates/numbers/currency; overflow sweep in both languages on every screen.
**Report:** string count, coverage check, screenshots of tight layouts in both languages.

## W7 — Marketing engine (Task 7) — NEW plan, better than May's

Weekly calendar Aug–Nov 2026 (LT interior-finishing pros); 15 captions LT+EN; 3 video scripts (30-60s, screen-rec instructions + VO text); 5 image-gen prompts; profile banners + post templates + link-in-bio; landing on pathon.eu in new brand with SEO meta/OG/GA4; `marketing-plan.md` with full strategy + all assets.
**Needs from founder:** social accounts (IG/TikTok/FB/LinkedIn) — exist? GA4 property. Posting is founder-side; everything else generated.
**Report:** the full asset pack + calendar for founder review before anything is public.

---

## Reporting protocol (founder-mandated)

After every workstream: a **numbers-first report** (tables, not adjectives) + screenshots where visual. Decision gates that stop and wait for the founder: W1 model flip (benchmark table), W3 pricing tiers (margin math), W5 logo/design direction (mockups), W7 asset pack (before publishing anything). Everything else proceeds autonomously.

## Founder-side inputs needed (not blocking start)

Stripe account/live keys (W3 can build on test keys) · GA4 property (W7) · social account inventory (W7) · logo taste feedback at the W5 gate.
