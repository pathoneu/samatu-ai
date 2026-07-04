# Billing — operator runbook

Pathon's billing subsystem (Stripe Checkout + subscriptions, per-plan usage
quota, company-code free-trial anti-abuse, LT PVM sąskaita-faktūra generator).
The whole thing is **dormant by default**. This doc is what you do to turn it on.

> Backend package: `backend/billing/` (pure logic) + `backend/api/billing_v2.py`
> (HTTP surface, prefix `/api/billing/v2`). Env template: `backend/.env.example`.

---

## 1. What "dormant" means

The single kill-switch is **`BILLING_ENABLED`**. It is ON only when set to
exactly `"1"` — unset, `"0"`, `"true"`, `""`, anything else = **OFF**
(`billing.flag.billing_enabled`).

**With the flag OFF (today's production):**

- No quota check, no paywall. `_check_user_quota` and `_check_trial_gate` are
  hard no-ops; `entitlements.quota_exceeded(...)` is always `False`.
- No Stripe calls on any hot path. `/checkout` refuses with `{enabled: false}`
  (403); extractions never touch Stripe.
- `entitlements.feature_allowed(user, ...)` returns `True` for **everything** —
  every feature (incl. F2/F3 export) is unlocked, exactly as before billing existed.
- `GET /api/billing/v2/usage` and `/status` report `{"enabled": false}` — the
  frontend renders no meter and no pricing UI.
- Nothing is written to the `billing_usage` quota ledger.

This is proven end-to-end in `backend/tests/test_billing_flag_flip.py` (the OFF
proof reproduces pre-billing behavior byte-for-byte; the ON proof exercises the
full paywall).

> **Wiring caveat (known, 2026-07-04):** the quota/trial paywall fires through
> the `auth.require_billable_user` dependency, which today is wired onto the
> `api/*` Vision routers (`vision_fill`, `lasso_rerun`, `cv_tools`, `symbols`).
> The primary `POST /extract-interior` endpoint authenticates via
> `main._billable_user`, which runs the € spend cap + reservation but **not** the
> quota/trial gate — so an at-quota user is not blocked on that specific route yet.
> If you want the interior-extraction endpoint itself paywalled, wire
> `_check_user_quota` + `_check_trial_gate` into `main._billable_user` (or make the
> route `Depends(auth.require_billable_user)`) before go-live and add a
> regression test. The ledger increment on `/extract-interior` already works.

---

## 2. Approved tiers

Single source of truth: `backend/billing/plans.py`. Prices in EUR. B2B reverse-charge
VAT — the sticker price is the revenue, no +21% PVM added on top for VAT-registered buyers.

| Plan | Price | Quota | Overage | Stripe mode | Env for Price ID |
|------|-------|-------|---------|-------------|------------------|
| Free (trial) | €0 | 1 project | — | (not purchasable) | — |
| Pro | €49/mo | 10 projects/mo | €8 | `subscription` | `STRIPE_PRICE_PRO` |
| Studio | €149/mo | 35 projects/mo | €5 | `subscription` | `STRIPE_PRICE_STUDIO` |
| Vienkartinis (one-off) | €12 | 1 project (credit) | — | `payment` | `STRIPE_PRICE_ONEOFF` |

The one-off is a **non-expiring credit**, not a plan state — a user is never set
to `plan="oneoff"`. A purchased credit is drawn only after the monthly quota is
exhausted (`db.credits_balance` / `record_extract_and_maybe_consume_credit`).

---

## 3. Going-live checklist

Do these in order. Nothing here affects users until the final `BILLING_ENABLED=1`
flip, so it is safe to prepare everything ahead of time.

1. **Create a Stripe account** and switch it to **test mode** for validation.
2. **Create three Prices** in the Stripe dashboard (Products → add Price):
   - Pro — **€49 / month**, recurring → note its `price_...` id.
   - Studio — **€149 / month**, recurring → note its `price_...` id.
   - Vienkartinis — **€12**, one-time → note its `price_...` id.
3. **Set the Stripe env vars** (host secret manager — Render/Fly, never `.env` in
   git; `.env` is gitignored):
   - `STRIPE_SECRET_KEY` = `sk_test_...`
   - `STRIPE_PRICE_PRO` / `STRIPE_PRICE_STUDIO` / `STRIPE_PRICE_ONEOFF` = the three ids above.
   - `PATHON_APP_URL` = the frontend base URL (Checkout success/cancel redirects).
4. **Set the invoice supplier block** — `PATHON_COMPANY_*` (see §5). Get these
   right before any real payment, since each payment emits a PVM invoice with this data.
5. **Register the webhook** so Stripe can mirror state onto our users:
   - Local dev: `stripe listen --forward-to localhost:8000/api/billing/v2/webhook`
     — it prints the `whsec_...` signing secret.
   - Production: dashboard → Developers → Webhooks → add endpoint
     `https://<host>/api/billing/v2/webhook`, subscribe to
     `checkout.session.completed`, `customer.subscription.updated`,
     `customer.subscription.deleted`, `invoice.paid`, `invoice.payment_failed`;
     copy its signing secret.
   - Set `STRIPE_WEBHOOK_SECRET` = that `whsec_...` value.
6. **Smoke-test in test mode** (flag still off is fine for the webhook — see the
   note below): run a test Checkout with a `4242 4242 4242 4242` card, confirm the
   webhook upgrades the user row and (for the one-off) emits an invoice.
7. **Flip the switch:** `BILLING_ENABLED=1`, restart. The paywall is now live.

> The webhook **state-mirror runs regardless of `BILLING_ENABLED`** — the flag
> gates *enforcement* (quota/checkout), not the local mirror of Stripe truth. So
> you can validate the webhook wiring before flipping the flag, and flipping it on
> later finds correct plan state already in place.

---

## 4. Test-vs-live key swap

Everything is env-driven, so swapping test → live is a config change, no code change:

- `STRIPE_SECRET_KEY`: `sk_test_...` → `sk_live_...`.
- `STRIPE_PRICE_PRO` / `_STUDIO` / `_ONEOFF`: **recreate the three Prices in live
  mode** (test-mode Price ids do not work with a live key) and set the new `price_...` ids.
- `STRIPE_WEBHOOK_SECRET`: create a **live-mode** webhook endpoint → its own
  `whsec_...` (test and live signing secrets differ).

The price-id → plan mapping is rebuilt from env at call time
(`_price_to_plan_map`), so no restart-order subtlety — just set the live values
and restart. A webhook carrying an unmapped price is logged and skipped, never a crash.

---

## 5. Invoice supplier block (`PATHON_COMPANY_*`)

Printed on every PVM sąskaita-faktūra (`billing/invoice.py`). Set in the host env:

| Env var | Meaning |
|---------|---------|
| `PATHON_COMPANY_NAME` | Legal name, e.g. `MB Pathon` |
| `PATHON_COMPANY_CODE` | Įmonės kodas (numeric) |
| `PATHON_COMPANY_PVM` | PVM kodas (e.g. `LT100012345678`) — **blank = not VAT-registered** |
| `PATHON_COMPANY_ADDRESS` | Registered address |
| `PATHON_COMPANY_IBAN` | Payout IBAN (printed as "Apmokėti į sąskaitą") |
| `PATHON_COMPANY_EMAIL` | Contact email on the invoice |

Any blank field is simply omitted. The VAT branch is driven by two flags:

- **Buyer is VAT-registered** (user row has a `pvm_code`) → **reverse charge**:
  no VAT added, note "Atvirkštinis PVM (PVMĮ 96 str.)", total = sum.
- **Buyer not registered, Pathon not registered** (`PATHON_COMPANY_PVM` blank) →
  **not a VAT payer**: no VAT line, note "Pardavėjas nėra PVM mokėtojas".
- **Buyer not registered, Pathon registered** → **standard 21% PVM** added.

Set `PATHON_COMPANY_PVM` the day Pathon registers for PVM — that single flip moves
non-registered buyers from the not-a-VAT-payer branch to standard 21%.

---

## 6. Quota-policy switch

`BILLING_QUOTA_POLICY` (read by `billing/plans.QUOTA_POLICY`):

- **`expire`** (default, the only implemented policy) — use-it-or-lose-it. Unused
  monthly quota does not carry over.
- **`rollover_1` / `rollover_3`** — placeholders. `db.rolled_over_credits` returns
  `0`, so these behave like `expire` today. **Not implemented** — do not set them
  expecting carry-over until the rollover logic lands.

Leave it as `expire`.

---

## 7. Free-trial anti-abuse (company-code gate)

The Free tier is a **one-time, one-project trial gated by LT įmonės kodas**
(`billing/trial.py` + the `consumed_trials` table):

- A free user must set a **company_code** before the trial can be consumed. Hitting
  a billable endpoint without one → **403 `company_code_required`**.
- The trial is **consumed on a successful extraction** (not on the gate check), and
  the company code is stored **normalized** (whitespace stripped, digits only, 5–11
  length). `"30 25 36 741"` and `"302536741"` are the same company.
- **One trial per company, permanent.** `consumed_trials` is keyed by the normalized
  code and is **not** FK-referenced to the user — deleting/recreating an account
  with the same įmonės kodas does **not** reset the trial. This survives account
  deletion by design (`docs/pricing.md §3a`).
- A free user who has spent their single slot is blocked with **402** (either
  `quota_exceeded` or `trial_used`, since the gate order is spend-cap → quota →
  trial). They must buy a plan or a one-off credit to continue.

---

## 8. Endpoint reference (`/api/billing/v2`)

| Method + path | Auth | Notes |
|---------------|------|-------|
| `GET /status` | none | Public flag + public plans. `{enabled:false}` when off. |
| `GET /usage` | `require_user` | Meter data. `{enabled:false}` when off. |
| `POST /checkout` | `require_user` | Starts a Checkout Session. 403 `{enabled:false}` when off. |
| `POST /webhook` | **none** (Stripe-signature-verified) | Bad/missing signature → 400. Idempotent on `event.id`. See `docs/SECURITY.md §10`. |
| `GET /invoices` | `require_user` | Caller's invoices only. |
| `GET /invoices/{id}` | `require_user` | Owner-scoped; non-owner → **404**, not 403. |
