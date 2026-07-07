# Sąmatų AI — Commercial-Grade Level-Up Plan

**Date:** 2026-06-19
**Inputs:** 7-dimension commercial-readiness audit (file-cited) + LLM council debate (Claude + Gemini, 3 rounds; ChatGPT offline) + deep research (payments / Sistela / infra / fonts — 13 adversarially-verified claims).
**Constraint this cycle:** no expensive Vision/extraction re-runs. Every item below is infra / frontend / backend / a cheap mapping table.

---

## 0. The thesis — what we are actually optimizing for

The binding constraint is **not** "scaling" or "more features." It is three things, in order:

1. A handful of bugs that make the product **look broken or risk an uncapped Anthropic bill** (font, dead cost-metering, unguarded endpoints).
2. The product is a **browser tool, not a cloud product** — the source PDF lives only in the uploader's browser; "your projects are safe" is currently false.
3. **Zero proven retention** and a **ground-truth corpus stuck at n=2 contractors** — the moat is a *data* problem, not a code problem.

**Survival-first principle (the sequencing rule):** fix what makes you look broken or go bankrupt → make it a durable cloud product → make the deliverable a *signable business document* → validate willingness-to-pay with a concierge pilot that harvests corpus → only then build self-serve billing.

We design **around** the ~50% pure-vision accuracy ceiling (an industry constant in 2026), we do not spend money chasing it. The product's honest pitch is **"AI does the tedious 80%, you correct fast — and it's the only tool that reads your eksplikacija and gives you an F2 aktas."**

---

## 1. Resolved strategic decisions (council + research)

| Fork | Decision | Confidence |
|---|---|---|
| **1 — Depth vs breadth** | **Go DEEP on LT interior finishing.** Do NOT build facade / concrete / MEP now. Breadth multiplies the accuracy problem across types with no raster SOTA and dilutes the one defensible thing. | Council unanimous |
| **2 — Sell on accuracy vs honest triage** | **Honest triage.** Re-engineer confidence to be **class-calibrated** — force known-bad classes (doors, silikonavimas, garažas grindys, angokraščiai) to 🟡/🔴 *by class*, regardless of voting agreement. Cheapest, highest-trust move in the whole plan → Week 1. | Council unanimous |
| **3 — Re-platform timing** | **Don't re-platform heavily.** Object storage now (needed anyway). For the DB: **Neon managed Postgres** if the SQLite SQL ports cleanly (≈1 weekend, native PITR, kills the write-lock); **else SQLite + Litestream** to the same bucket. Either is fine — both end at "durable backups before money." | Council contested; Postgres slightly favored |

**Research-resolved external picks:**

- **Payments → Stripe (not a Merchant-of-Record), self-invoiced.** Your buyer is LT construction *businesses* (B2B), which makes VAT genuinely simple: EU cross-border B2B with a valid VAT ID = **reverse charge, you collect no VAT** (verified, 3-0); LT companies register for VAT only above **€45,000 turnover** (verified, 3-0). A Merchant-of-Record (Paddle / Lemon Squeezy) erases a VAT burden you barely have at this stage and costs ~5%+ in fees — overkill for LT-B2B. Use Stripe Billing + your own LT **PVM sąskaita-faktūra** generator (must include supplier + buyer names, both VAT numbers, supply date, description, VAT rate). Montonio/Paysera can be added later for local bank-payment UX; they don't solve VAT/subscriptions.
- **Sistela → Excel now; native DBF interop is a real *later* moat.** Sistela is **not** a closed ecosystem: its estimate format is documented legacy **DBF (FoxPro) files** (`FDARxxxx.DBF`, 5–6 files per complex) and rival tools (SES2004) already import/export it (verified, 3-0). But round-trip fidelity is fiddly — needs complex/object/estimate + contractor codes and per-version LT-character encoding (verified, 3-0). **Ship great Excel now** (the universal LT interchange); scope native Sistela DBF export as a deliberate future feature; **stop advertising "Sistela integration" until it exists.**
- **Object storage → Cloudflare R2** — S3-compatible, presigned URLs via standard `boto3` (verified, 3-0), zero egress (its headline feature) so serving PDFs back is free.
- **Font → DejaVu Sans or Noto Sans (SIL OFL 1.1).** Both have full `ąčęėįšųūž` coverage and licenses that permit embedding/redistribution inside a closed-source product. Vendor the TTF into the repo.

---

## 2. The two non-negotiables that outrank the feature list

- **Hard cost cap BEFORE any new beta user.** You cannot separate retention-testing from quota-gating when a run costs $0.20–$1.20. A reservation-based hard cap ships in Week 1; if a user hits the wall, they email for more credits — that friction is *high-signal demand validation*, not a bug.
- **The pilot's deliverable is the corpus, not the revenue.** Every correction from every pilot user must land in `build_ground_truth.py`'s corpus. The 12 code moves make the product *demoable*; corpus growth is the only thing that makes it *defensible* and that Togal cannot replicate without entering the LT market.

---

## 3. The sequenced roadmap (4–6 weeks)

Effort key: **S** ≤ half-day · **M** 1–3 days · **L** ~1 week. Each week is shippable on its own.

### WEEK 1 — Stop the bleeding (all S/M, zero Vision runs)
*Goal: nothing embarrassing in prod, no uncapped-bill risk, the trust signal works.*

1. **[S] Un-break Lithuanian PDFs.** Vendor `DejaVuSans.ttf` + `DejaVuSans-Bold.ttf` into `backend/assets/fonts/`; repoint the font registration at `backend/main.py:154-163` to the repo-relative path. Add a test that renders a PDF containing `ąčęėįšųūž` and asserts the glyphs embed (no `.notdef`). *Accept: prod PDF shows LT characters.*
2. **[M] Resurrect cost metering + turn on the hard cap.** Fix `db.save_extraction()` in `backend/db.py` (the `NameError` on `in_tok/out_tok/cache_tok` — use the real `input/output/cache` token values it already computes); call it after **every** Vision run; set `SAMATU_USER_DAILY_SPEND_EUR`. *Accept: `user_recent_spend_eur()` returns non-zero; cap fires in a test.*
3. **[S] Close the cost/DoS holes.** Swap `_billable_user` in for `require_user` on `backend/api/vision_fill.py`, `lasso_rerun.py`, `symbols.py`; call the existing `_validate_pdf_upload` at the top of `/extract`, `/detect-type`, `/extract-facade/-roof/-earthworks/-concrete` (one line each). *Accept: a 0-byte and a 300MB upload are rejected pre-parse on every endpoint.*
4. **[S] Class-calibrated confidence.** Extend `backend/extractor/confidence.py` `CLASS_RULES` so the measured-bad classes from `2026-06-11-experiments-results.md` (doors, silikonavimas, garažas grindys, angokraščiai) are forced 🟡/🔴 by class regardless of voting. *Accept: those lines never render 🟢 on the contractor fixture.*
5. **[S] Fix the hero trust signal.** In `ConfidenceBadge.jsx` + `ProvenanceChip.jsx`, swap the dark-theme `-300` shades for the existing `--conf-*` / `--source-*` tokens (match `WorkRow`'s readable `-700`). *Accept: badges pass WCAG AA on `#f6f5f2`.*
6. **[S] Kill the amateur tells.** Replace native `alert()` / `window.confirm()` with the mounted shadcn `toast` / `AlertDialog` at the 18 sites (`ProjectMainView.jsx:952,964`, `ProjectDetail.jsx:79`, `AssumptionsPanel.jsx:151`, `PdfViewer.jsx:969,1061,1096,1848`, `WorkspacePanel.jsx:100`, `Settings.jsx:250,338`, `Annotator.jsx`, `AnnotationCanvas.jsx:352`, …).
7. **[S] First-run safety net.** Guard zero-room results (`NewProject.jsx:~301`: catch `patalpos.length === 0` → "AI nerado patalpų — patikrinkite, ar tai interjero/aukšto planas"); add client-side file-type/size validation in `UploadZone.jsx`; default the post-extraction tab to **Kiekiai** (`InteriorProject.jsx:503`); wire the unused `DEMO_PROJECTS` to a "Peržiūrėti pavyzdinį projektą" button.
8. **[S, free] Stop-doing.** Delete the dead Konva `PdfViewer.jsx` (2324 lines, 0 imports) + `npm rm fabric konva react-konva`; remove the "Multi-user (3 seats)" and "Sistela (when available)" copy until they exist.

### WEEK 2 — Browser tool → cloud product
*Goal: the source drawing is durable and the DB can't be lost.*

9. **[L] Persist PDF bytes to object storage.** Stand up a Cloudflare R2 bucket; `POST /api/projects/{id}/pdf` streams bytes in (keyed by `pdf_sha256`), a presigned-GET streams them back; `frontend/src/lib/pdfStore.js` IndexedDB becomes a *cache*, not the only copy. *Accept: clear browser data → reopen project → drawing still loads; share link renders the drawing.*
10. **[M] Durability baseline.** Choose **one**: (a) migrate the 4-table schema to **Neon** Postgres with Alembic introduced (native PITR; watch the SQLite→PG gotchas: `AUTOINCREMENT`→`SERIAL/IDENTITY`, dynamic typing, no native bool, `?`→`%s` placeholders, date handling); or (b) keep SQLite + **Litestream** replicating to the R2 bucket. Add `/health` + `/healthz`. *Accept: a simulated disk loss restores from backup; load balancer has a probe.*
11. **[M] Operational hygiene.** Forgot-password + email-verification flow (the backend already has rate-limiting + a generic-error validator); replace the `/api/log-error` print-stub with a Sentry-style sink; install PostHog (free) — you cannot tune first-run/activation without knowing where users stall.

### WEEK 3 — Professional finish + the correction loop people can trust
*Goal: it looks and feels like paid software; users can actually fix what AI got wrong.*

12. **[M] Branding / business-document system.** Logo upload in Settings (stored per-account in R2) + company legal block (įmonės kodas, PVM kodas, adresas, tel., el. paštas, IBAN) + per-project client/objektas block; render all into the Excel banner and the PDF cover/footer, replacing the `ĮMONĖS LOGOTIPAS` stub (`main.py:4318-4328`). Add a real cover page (pasiūlymo nr., data, galioja iki) + signature line. *Accept: an exported PDF reads as a signable LT pasiūlymas, not a table dump.*
13. **[M] Lightweight scale-verification** (not a Bluebeam drafting UI — the council's resolved middle). Surface the existing `scale_validator.py` result; let the user confirm/override the drawing scale with a two-point check against one known dimension. *Accept: a wrong auto-scale is catchable in one click; geometry m² the user can trust.*
14. **[S] Price-input nudge + 0,00 € guard.** Warn before exporting an all-€0 sąmata; nudge to apply a kainynas first.
15. **[M, staged] Design-system down-payment.** Don't boil the ocean (the full ~237-inline-style migration is deferred). Just tokenize the two highest-traffic surfaces — the Kiekiai table + PDF viewer toolbar — and add an ESLint/grep CI guard that fails on *new* hardcoded hex / inline `fontSize`. *Accept: the surfaces buyers live in 95% of the time look coherent; no new drift lands.*

### WEEK 4 — The commercial wedge + concierge pilot launch
*Goal: expose the moat; get money + corrections from real estimators without building billing.*

16. **[M] Ship F2/F3.** Re-enable the buttons (`ExportDropdown.jsx:164,212`, wired to the built+tested `f2_export.py` / `exports_v2.py`) and add a real F2/F3 **PDF** renderer (collect laikotarpis, sutarties nr., šalys, parašai). This is the LT regulatory moat a frontier document-agent can't replicate. *Accept: a contractor can produce a fileable F2 aktas.*
17. **[Non-code] Launch the concierge paid pilot.** Personally onboard **5 LT estimators**. Charge a discounted annual via a manual **PVM sąskaita-faktūra** + Stripe payment link / bank transfer — **no billing integration**. The deliverable is two-fold: (a) does a 3rd–5th estimator come back and pay? (b) every correction they make flows into the corpus. Run `build_ground_truth.py` on a cron; surface corpus size as the north-star metric.

### WEEK 5–6 — Conditional: build the gate, or deepen the pilot
*Decide based on Week-4 signal, not the calendar.*

- **If the pilot proves retention (≥3 of 5 return + would-be-sad-if-gone):** build self-serve billing — Stripe Checkout that flips `plan` on the user row + a webhook; gate F2/F3 + logo + higher quota behind Pro; LT VAT-invoice generator. Add `plan`, `plan_status`, `stripe_customer_id`, `current_period_end` to the users table.
- **If retention is weak:** do NOT build billing. Use the weeks to fix what the pilot exposed and acquire 5 more pilot users. Billing in front of an unvalidated product is a wall, not a feature.

---

## 4. Explicitly deferred (anti-scope — say no on purpose)

- **Facade / concrete / MEP / earthworks modules.** Breadth dilutes the moat (Fork 1). Revisit only if a paying interior customer explicitly blocks on it.
- **Full design-system migration** (all ~237 inline styles). Stage it; do the two key surfaces + CI guard now, the rest post-revenue.
- **Heavy measurement/snapping (Bluebeam-style) drafting UI.** Lightweight scale-verification is enough for interior-from-eksplikacija; full polyline drafting waits for a customer who demands it.
- **Teams / multi-user / seats.** No org model today; don't sell "3 seats." Single-user is fine for the first paying contractors.
- **Postgres-everything re-platform / multi-worker.** Not until concurrent load actually bites.
- **Native Sistela DBF round-trip.** Real moat, real cost (FoxPro LT encoding) — a deliberate later project, not now. Excel covers interchange meanwhile.

---

## 5. Decisions for you to confirm

1. **Payments:** Recommended — **Stripe + self-issued PVM sąskaita-faktūra**, starting with a manual concierge pilot (no integration until retention proven). Alternative — Paddle/Lemon Squeezy (Merchant-of-Record) only if you want zero VAT/accounting work and accept ~5%+ fees. → *Confirm: Stripe, or MoR?*
2. **Database durability:** Recommended — **Neon Postgres** (one-weekend migration, native PITR) if the `db.py` SQL ports cleanly; **SQLite + Litestream** as the faster-to-ship fallback. → *Confirm: migrate to Neon, or stay on SQLite+Litestream?*
3. **Monetization timing:** Recommended — **concierge pilot first** (Week 4), build self-serve billing only after retention proves out. → *Confirm: pilot-first, or build Stripe self-serve immediately?*

---

## Appendix — research citations (2025–2026, adversarially verified)

- Paddle is Merchant-of-Record, remits EU VAT, applies B2B reverse-charge — `paddle.com/help/sell/tax/...` (3-0).
- EU cross-border B2B reverse-charge with valid VAT ID = no VAT collected — `quaderno.io/guides/lithuania-vat-guide` (3-0).
- LT VAT registration threshold €45,000 turnover (+€14,000 intra-EU purchases); OSS for B2C digital; required invoice fields — `1office.co/blog/vat-registration-in-lithuania-2025` (3-0 / 2-0).
- Sistela format = documented `FDARxxxx.DBF` (FoxPro), readable by SES2004; LT-ecosystem is interoperable at the file layer; round-trip needs codes + per-version encoding — `ses.lt/.../SES2004.pdf` (3-0 ×3).
- R2 presigned URLs via `boto3.generate_presigned_url()` — `developers.cloudflare.com/r2/examples/aws/boto3` (3-0).

*(Deep-research run hit a session rate-limit before auto-synthesis; the above are the claims that passed adversarial verification. Several infra claims — R2 zero-egress, Neon/Supabase/Render-Postgres specifics, font licenses — are well-established but were left unverified by the limit; treat as high-confidence-but-confirm-at-implementation.)*
