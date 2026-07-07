# W3 Billing (Stripe + Quota + LT PVM Invoice) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a complete, dormant billing subsystem — Stripe Checkout (one-off + subscriptions), webhooks, per-plan usage quota, company-code free-trial anti-abuse, and an LT PVM sąskaita-faktūra generator — all behind `BILLING_ENABLED` (default OFF), where OFF reproduces today's behavior byte-for-byte.

**Architecture:** A new `backend/billing/` package holds pure, unit-testable logic (tier config, entitlements, quota, trial gate, invoice); `backend/api/billing_v2.py` grows the HTTP surface (checkout, webhook, usage, portal); quota enforcement hooks into the existing `require_billable_user` → `_check_user_spend_cap` gate as an additive `_check_user_quota` that is a hard no-op when the flag is off. Plan state lives on the `users` row (Stripe is the source of truth, mirrored locally via webhooks). Usage is counted from a new `billing_usage` ledger, keyed to the Stripe billing period.

**Tech Stack:** FastAPI + SQLite (append-only `_migrate_schema` migrations), `stripe` Python SDK, reportlab (invoice PDF, mirrors existing `main.py` usage), React/JSX frontend.

**Approved tiers (from `docs/pricing.md`):** Free trial = 1 project (company-code-gated) · Pro €49 / 10 projects/mo (€8 overage) · Studio €149 / 35 projects/mo (€5 overage) · one-off Vienkartinis €12/project. EUR. Reverse-charge B2B VAT — sticker price = revenue, no +21% PVM added.

**Flag invariant (non-negotiable, verified in Phase 8):** `BILLING_ENABLED != "1"` ⇒ no quota check, no paywall, no Stripe calls on any hot path, pricing UI hidden. Extraction behaves exactly as it does today (only the pre-existing `SAMATU_USER_DAILY_SPEND_EUR` cap applies).

---

## File structure

**New — `backend/billing/` package (pure logic, no FastAPI imports):**
- `backend/billing/__init__.py` — package marker.
- `backend/billing/flag.py` — `billing_enabled() -> bool` (the single source of truth for the flag; import everywhere else).
- `backend/billing/plans.py` — tier definitions (id, name, price_eur, monthly_quota, overage_eur, features, stripe env key names) + `PLAN_BY_ID`, `PUBLIC_PLANS`, `QUOTA_POLICY` (default `"expire"`).
- `backend/billing/entitlements.py` — read plan state off a user row; `feature_allowed(user, feature)`; `projects_used(user)`, `projects_remaining(user)`, `quota_exceeded(user)` (policy-aware).
- `backend/billing/trial.py` — `normalize_company_code()`, `trial_available(company_code)`, `consume_trial(company_code, user_id)`.
- `backend/billing/stripe_client.py` — lazy Stripe SDK init from env; `is_configured()`; thin wrappers `create_customer`, `create_checkout_session`, `construct_event`.
- `backend/billing/invoice.py` — `render_pvm_invoice_pdf(invoice: dict) -> bytes` (reportlab).

**Modified:**
- `backend/db.py` — `_migrate_schema()` adds billing columns + `consumed_trials` + `billing_usage` tables; new helpers `set_user_plan(...)`, `get_user_billing(...)`, `record_billing_usage(...)`, `billing_usage_in_period(...)`.
- `backend/api/billing_v2.py` — replace the stub `PLANS` with `plans.PUBLIC_PLANS`; add `POST /checkout`, `POST /webhook`, `GET /usage`, `POST /portal`.
- `backend/auth.py` — `require_billable_user` also calls `_check_user_quota` (additive).
- `backend/main.py` — define `_check_user_quota`; increment `billing_usage` after a successful billable extraction; register nothing new (billing_v2_router already included).
- `backend/requirements.txt` — add `stripe`.

**Frontend (React/JSX under `frontend/src/`):**
- `frontend/src/components/PricingPage.jsx` — tiers, flag-gated visible.
- `frontend/src/components/UpgradeDialog.jsx` — shown on quota block.
- `frontend/src/components/BillingSettings.jsx` — company code, PVM code, current plan, manage/cancel.
- Wire checkout redirect + usage meter into the existing dashboard.

**Config/docs:**
- `.env.example` — document `BILLING_ENABLED`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_PRO`, `STRIPE_PRICE_STUDIO`, `STRIPE_PRICE_ONEOFF`, `PATHON_COMPANY_*` (invoice supplier block).

---

## Phase 0 — Foundation & flag (zero behavior change)

### Task 1: Billing flag + stripe dependency

**Files:**
- Create: `backend/billing/__init__.py` (empty), `backend/billing/flag.py`
- Modify: `backend/requirements.txt`
- Test: `backend/tests/test_billing_flag.py`

- [ ] **Step 1: Failing test**

```python
# backend/tests/test_billing_flag.py
import os
from billing.flag import billing_enabled

def test_flag_defaults_off(monkeypatch):
    monkeypatch.delenv("BILLING_ENABLED", raising=False)
    assert billing_enabled() is False

def test_flag_on_only_for_exactly_1(monkeypatch):
    monkeypatch.setenv("BILLING_ENABLED", "1")
    assert billing_enabled() is True
    for v in ("0", "true", "yes", "", "2"):
        monkeypatch.setenv("BILLING_ENABLED", v)
        assert billing_enabled() is False
```

- [ ] **Step 2: Run — expect ImportError/FAIL**

Run: `cd backend && ../venv/bin/python -m pytest tests/test_billing_flag.py -q`

- [ ] **Step 3: Implement**

```python
# backend/billing/flag.py
"""Single source of truth for the billing kill-switch.

BILLING_ENABLED must be exactly "1" to enable. Any other value (unset, "0",
"true", "") = OFF. OFF is the launch default and reproduces pre-billing
behavior everywhere this is checked.
"""
from __future__ import annotations
import os


def billing_enabled() -> bool:
    return os.environ.get("BILLING_ENABLED", "0") == "1"
```

Append `stripe>=11,<13` to `backend/requirements.txt`, then `../venv/bin/pip install 'stripe>=11,<13'`.

- [ ] **Step 4: Run — expect PASS**
- [ ] **Step 5: Commit** — `git commit -m "feat(billing): BILLING_ENABLED flag helper + stripe dep"`

### Task 2: DB migration — billing columns + trial/usage tables

**Files:**
- Modify: `backend/db.py` (`_migrate_schema` around line 587 where the `users` `ucols` block lives; and `_ensure_schema`/CREATE section)
- Test: `backend/tests/test_billing_migration.py`

Mirror the existing append-only pattern (`PRAGMA table_info` → `ALTER TABLE ... ADD COLUMN`). Columns on `users`: `plan TEXT NOT NULL DEFAULT 'free'`, `plan_status TEXT NOT NULL DEFAULT 'active'`, `stripe_customer_id TEXT`, `stripe_subscription_id TEXT`, `current_period_end TEXT`, `company_code TEXT`, `pvm_code TEXT`. (SQLite forbids adding a NOT NULL column without a constant default — the two defaults above are constants, fine.)

- [ ] **Step 1: Failing test**

```python
# backend/tests/test_billing_migration.py
import sqlite3, importlib, os

def _cols(db, table):
    con = sqlite3.connect(db)
    try:
        return {r[1] for r in con.execute(f"PRAGMA table_info({table})")}
    finally:
        con.close()

def test_billing_columns_and_tables(tmp_path, monkeypatch):
    dbp = str(tmp_path / "t.db")
    monkeypatch.setenv("SAMATU_DB_PATH", dbp)
    import db as dbmod
    importlib.reload(dbmod)
    dbmod.init_db()
    ucols = _cols(dbp, "users")
    for c in ("plan", "plan_status", "stripe_customer_id",
              "stripe_subscription_id", "current_period_end",
              "company_code", "pvm_code"):
        assert c in ucols, c
    assert "consumed_trials" in {
        r[0] for r in sqlite3.connect(dbp).execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
    assert "billing_usage" in {
        r[0] for r in sqlite3.connect(dbp).execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
```

- [ ] **Step 2: Run — expect FAIL**
- [ ] **Step 3: Implement** — in `_migrate_schema`, after the existing `ucols` block, append:

```python
        if "plan" not in ucols:
            c.execute("ALTER TABLE users ADD COLUMN plan TEXT NOT NULL DEFAULT 'free'")
        if "plan_status" not in ucols:
            c.execute("ALTER TABLE users ADD COLUMN plan_status TEXT NOT NULL DEFAULT 'active'")
        for col in ("stripe_customer_id", "stripe_subscription_id",
                    "current_period_end", "company_code", "pvm_code"):
            if col not in ucols:
                c.execute(f"ALTER TABLE users ADD COLUMN {col} TEXT")
        # consumed_trials: keyed by company code, SURVIVES user deletion
        c.execute("""
            CREATE TABLE IF NOT EXISTS consumed_trials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_code TEXT NOT NULL UNIQUE,
                user_id TEXT,
                consumed_at TEXT NOT NULL
            )""")
        # billing_usage: per-billable-extraction ledger, keyed to billing period
        c.execute("""
            CREATE TABLE IF NOT EXISTS billing_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                project_id TEXT,
                created_at TEXT NOT NULL
            )""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_billing_usage_user_time ON billing_usage(user_id, created_at)")
```

Note: if `init_db`/`_migrate_schema` are structured differently than assumed, place the `ALTER`/`CREATE` in the same transaction/cursor the existing user-column migration uses. Do NOT reorder existing migrations (append-only).

- [ ] **Step 4: Run — expect PASS** (also run the full suite to confirm no existing DB test broke)
- [ ] **Step 5: Commit** — `git commit -m "feat(billing): users billing columns + consumed_trials + billing_usage tables"`

### Task 3: Tier config (single source of truth)

**Files:**
- Create: `backend/billing/plans.py`
- Test: `backend/tests/test_billing_plans.py`

- [ ] **Step 1: Failing test**

```python
# backend/tests/test_billing_plans.py
from billing.plans import PLAN_BY_ID, PUBLIC_PLANS, QUOTA_POLICY

def test_approved_tiers_exact():
    pro = PLAN_BY_ID["pro"]
    studio = PLAN_BY_ID["studio"]
    assert pro["price_eur"] == 49 and pro["monthly_quota"] == 10 and pro["overage_eur"] == 8
    assert studio["price_eur"] == 149 and studio["monthly_quota"] == 35 and studio["overage_eur"] == 5
    assert PLAN_BY_ID["free"]["monthly_quota"] == 1
    assert PLAN_BY_ID["oneoff"]["price_eur"] == 12

def test_default_quota_policy_is_expire():
    assert QUOTA_POLICY == "expire"

def test_f2f3_gated_to_paid():
    assert "f2f3_export" in PLAN_BY_ID["pro"]["features"]
    assert "f2f3_export" not in PLAN_BY_ID["free"]["features"]
```

- [ ] **Step 2: Run — expect FAIL**
- [ ] **Step 3: Implement**

```python
# backend/billing/plans.py
"""Approved Pathon tiers (docs/pricing.md, 2026-07-04 founder gate).

Single source of truth for prices, quotas, features. Stripe Price IDs come
from env (per-tier) so test/live keys swap without code changes.
"""
from __future__ import annotations
import os

# QUOTA_POLICY is a config, not a decision yet locked (founder deferred the
# unused-quota question). "expire" = use-it-or-lose-it (default). Changing to
# "rollover_1"/"rollover_3" is a one-line flip — entitlements.py reads it.
QUOTA_POLICY = os.environ.get("BILLING_QUOTA_POLICY", "expire")

PLANS = [
    {"id": "free", "name": "Nemokamas bandymas", "price_eur": 0,
     "monthly_quota": 1, "overage_eur": None, "seats": 1,
     "features": ["interior"], "stripe_price_env": None, "purchasable": False},
    {"id": "pro", "name": "Pro", "price_eur": 49,
     "monthly_quota": 10, "overage_eur": 8, "seats": 1,
     "features": ["interior", "f2f3_export", "audit_trail", "priority_queue"],
     "stripe_price_env": "STRIPE_PRICE_PRO", "purchasable": True, "mode": "subscription"},
    {"id": "studio", "name": "Studio", "price_eur": 149,
     "monthly_quota": 35, "overage_eur": 5, "seats": 3,
     "features": ["interior", "f2f3_export", "audit_trail", "priority_queue",
                  "multi_seat", "unit_price_overrides"],
     "stripe_price_env": "STRIPE_PRICE_STUDIO", "purchasable": True, "mode": "subscription"},
    {"id": "oneoff", "name": "Vienkartinis", "price_eur": 12,
     "monthly_quota": 0, "overage_eur": None, "seats": 1,
     "features": ["interior", "f2f3_export"],
     "stripe_price_env": "STRIPE_PRICE_ONEOFF", "purchasable": True, "mode": "payment"},
]

PLAN_BY_ID = {p["id"]: p for p in PLANS}
# Shown in the pricing UI (subscriptions + one-off; free advertised separately).
PUBLIC_PLANS = [p for p in PLANS if p["id"] != "free"]
```

- [ ] **Step 4: Run — PASS**
- [ ] **Step 5: Commit** — `git commit -m "feat(billing): approved tier config (Pro 49/10, Studio 149/35, one-off 12)"`

---

## Phase 1 — Entitlements & quota logic (pure, flag-gated, unit-tested)

### Task 4: Entitlement reads + quota computation

**Files:**
- Create: `backend/billing/entitlements.py`
- Modify: `backend/db.py` (add `billing_usage_in_period`, `get_user_billing`)
- Test: `backend/tests/test_entitlements.py`

Quota period: for subscribers with a `current_period_end`, the period is `[current_period_end − 1 month, current_period_end)`; otherwise calendar month. `projects_used` counts `billing_usage` rows of kind `extract` in that window. `projects_remaining = monthly_quota − used` (+ rolled-over amount when `QUOTA_POLICY` ≠ `"expire"`; rollover carries at most one prior period's unused for `rollover_1`). `quota_exceeded(user)` returns False whenever `billing_enabled()` is False OR the plan is `oneoff` (one-off users are gated at purchase, not by monthly quota).

- [ ] **Step 1: Failing test**

```python
# backend/tests/test_entitlements.py
import importlib
from datetime import datetime, timezone

def _mkuser(**kw):
    base = {"id": "u1", "plan": "pro", "plan_status": "active",
            "current_period_end": None}
    base.update(kw); return base

def test_free_plan_one_project(monkeypatch, tmp_path):
    monkeypatch.setenv("SAMATU_DB_PATH", str(tmp_path/"t.db"))
    monkeypatch.setenv("BILLING_ENABLED", "1")
    import db; importlib.reload(db)
    import billing.entitlements as ent; importlib.reload(ent)
    u = _mkuser(id="f1", plan="free")
    assert ent.projects_remaining(u) == 1
    db.record_billing_usage("f1", kind="extract")
    assert ent.projects_remaining(u) == 0
    assert ent.quota_exceeded(u) is True

def test_flag_off_never_exceeds(monkeypatch, tmp_path):
    monkeypatch.setenv("SAMATU_DB_PATH", str(tmp_path/"t.db"))
    monkeypatch.delenv("BILLING_ENABLED", raising=False)
    import db; importlib.reload(db)
    import billing.entitlements as ent; importlib.reload(ent)
    u = _mkuser(plan="free")
    for _ in range(5):
        db.record_billing_usage("u1", kind="extract")
    assert ent.quota_exceeded(u) is False   # flag OFF ⇒ no enforcement

def test_feature_gate(monkeypatch):
    import billing.entitlements as ent
    assert ent.feature_allowed(_mkuser(plan="pro"), "f2f3_export") is True
    assert ent.feature_allowed(_mkuser(plan="free"), "f2f3_export") is False
```

- [ ] **Step 2: Run — FAIL**
- [ ] **Step 3: Implement** `db.record_billing_usage`, `db.billing_usage_in_period`, then:

```python
# backend/billing/entitlements.py
from __future__ import annotations
from .flag import billing_enabled
from .plans import PLAN_BY_ID, QUOTA_POLICY
import db


def _plan(user: dict) -> dict:
    return PLAN_BY_ID.get((user or {}).get("plan") or "free", PLAN_BY_ID["free"])


def feature_allowed(user: dict, feature: str) -> bool:
    # Flag OFF ⇒ everything unlocked (today's behavior).
    if not billing_enabled():
        return True
    return feature in _plan(user).get("features", [])


def projects_used(user: dict) -> int:
    return db.billing_usage_in_period(
        user["id"], current_period_end=user.get("current_period_end"), kind="extract")


def projects_remaining(user: dict) -> int:
    p = _plan(user)
    base = p["monthly_quota"]
    if QUOTA_POLICY.startswith("rollover"):
        base += db.rolled_over_credits(user["id"])  # implemented only if policy used
    return max(0, base - projects_used(user))


def quota_exceeded(user: dict) -> bool:
    if not billing_enabled():
        return False
    if _plan(user)["id"] == "oneoff":
        return False  # one-off gated at purchase, not monthly
    return projects_remaining(user) <= 0
```

`db.billing_usage_in_period(user_id, current_period_end, kind)`: compute the window start (period_end − 30 days, or first-of-month if None), `SELECT COUNT(*) FROM billing_usage WHERE user_id=? AND kind=? AND created_at >= ?`. `rolled_over_credits` may `return 0` for now (only exercised when a rollover policy is set — YAGNI until the founder picks one).

- [ ] **Step 4: Run — PASS**
- [ ] **Step 5: Commit** — `git commit -m "feat(billing): entitlements + policy-driven quota (no-op when flag off)"`

### Task 5: `_check_user_quota` gate helper (additive to billable gate)

**Files:**
- Modify: `backend/main.py` (near `_check_user_spend_cap`, ~line 80), `backend/auth.py` (`require_billable_user`, ~line 184)
- Test: `backend/tests/test_quota_gate.py`

- [ ] **Step 1: Failing test** — a user at quota, flag ON, calling the gate raises HTTP 402; flag OFF never raises; one-off never raises.

```python
# backend/tests/test_quota_gate.py
import importlib, pytest
from fastapi import HTTPException

def test_quota_gate_402_when_exceeded(monkeypatch, tmp_path):
    monkeypatch.setenv("SAMATU_DB_PATH", str(tmp_path/"t.db"))
    monkeypatch.setenv("BILLING_ENABLED", "1")
    import db; importlib.reload(db); db.init_db()
    uid = db.create_user(email="a@b.lt", password_hash="x", name="A")  # real accessor; returns id
    db.record_billing_usage(uid, kind="extract")  # free quota = 1, now used
    import main; importlib.reload(main)
    with pytest.raises(HTTPException) as e:
        main._check_user_quota("u1")
    assert e.value.status_code == 402

def test_quota_gate_noop_when_flag_off(monkeypatch, tmp_path):
    monkeypatch.setenv("SAMATU_DB_PATH", str(tmp_path/"t.db"))
    monkeypatch.delenv("BILLING_ENABLED", raising=False)
    import db; importlib.reload(db); db.init_db()
    import main; importlib.reload(main)
    main._check_user_quota("u1")  # must NOT raise
```

- [ ] **Step 2: Run — FAIL**
- [ ] **Step 3: Implement** in `main.py`:

```python
def _check_user_quota(user_id: str | None) -> None:
    """Raise 402 when a logged-in user is over their plan quota. Hard no-op
    when BILLING_ENABLED != '1' (pre-billing behavior)."""
    from billing.flag import billing_enabled
    if not billing_enabled() or not user_id:
        return
    from billing.entitlements import quota_exceeded
    user = db.get_user_by_id(user_id)   # existing accessor
    if user and quota_exceeded(user):
        raise HTTPException(
            status_code=402,
            detail={"error": "quota_exceeded", "plan": user.get("plan"),
                    "message": "Išnaudotas mėnesio projektų limitas. Atnaujinkite planą."})
```

In `auth.py` `require_billable_user`, after `_check_user_spend_cap(user["id"])` add `from main import _check_user_quota` and `_check_user_quota(user["id"])`. (Import is already lazy in that function.)

- [ ] **Step 4: Run — PASS** + full suite
- [ ] **Step 5: Commit** — `git commit -m "feat(billing): quota gate on billable endpoints (402, no-op when off)"`

### Task 6: Increment `billing_usage` on successful billable extraction

**Files:**
- Modify: `backend/main.py` (in the `/extract-interior` success path, right after `db.record_usage(...)`)
- Test: `backend/tests/test_billing_usage_increment.py`

Increment exactly once per successful billable project analysis (kind `extract`), only when `billing_enabled()`. Do NOT count failed/refused extractions. This is the counter `entitlements.projects_used` reads.

- [ ] **Step 1–4:** test that a successful `/extract-interior` (mocked Vision) writes one `billing_usage` row when the flag is on and zero when off; implement the guarded `db.record_billing_usage(user_id, kind="extract", project_id=...)` call.
- [ ] **Step 5: Commit** — `git commit -m "feat(billing): count successful billable extraction into quota ledger"`

---

## Phase 2 — Stripe Checkout

### Task 7: Stripe client wrapper

**Files:**
- Create: `backend/billing/stripe_client.py`
- Test: `backend/tests/test_stripe_client.py` (all mocked — NO network)

`is_configured()` = `STRIPE_SECRET_KEY` present. Lazy-init `stripe.api_key`. Wrappers: `create_customer(email, name, metadata)`, `create_checkout_session(...)`, `construct_event(payload, sig_header)` (uses `STRIPE_WEBHOOK_SECRET`). Every wrapper raises a clear error if `not is_configured()`.

- [ ] Test with `unittest.mock.patch("stripe.checkout.Session.create")` etc.; assert our wrappers pass the right args and surface `stripe.error.SignatureVerificationError` as a 400-mapped exception. Implement. Commit `feat(billing): stripe SDK wrapper (lazy, mockable)`.

### Task 8: `POST /api/billing/checkout`

**Files:**
- Modify: `backend/api/billing_v2.py`
- Test: `backend/tests/test_checkout_endpoint.py`

Body `{ "plan": "pro" | "studio" | "oneoff" }`. Requires `require_user`. Returns 404-style `{enabled:false}` refusal when `not billing_enabled()`. Creates/reuses `stripe_customer_id` on the user, creates a Checkout Session (`mode` from the plan: `subscription` or `payment`) with the plan's Stripe price (from its `stripe_price_env`), `success_url`/`cancel_url` to frontend routes, `client_reference_id=user_id`, `customer=stripe_customer_id`. Returns `{ "url": session.url }`.

- [ ] **Step 1: Failing test** (mock stripe_client): flag off → 403/`{enabled:false}`; flag on + unknown plan → 400; flag on + `pro` → returns a URL and persists `stripe_customer_id`.
- [ ] Implement; assert `client_reference_id` and `mode` are correct per plan.
- [ ] **Commit** — `feat(billing): checkout session (subscription + one-off)`

---

## Phase 3 — Webhooks (Stripe = source of truth)

### Task 9: `POST /api/billing/webhook` — verify + idempotent dispatch

**Files:**
- Modify: `backend/api/billing_v2.py`; `backend/db.py` (add `webhook_events` dedup table + `seen_webhook(event_id)`)
- Test: `backend/tests/test_webhook.py`

Read the raw body (`await request.body()`), verify signature via `stripe_client.construct_event`. Bad signature → 400. Dedup on `event.id` (store processed ids; a re-delivered event is a 200 no-op). Dispatch by `event.type`.

- [ ] Test: tampered signature → 400; valid `checkout.session.completed` → user upgraded; re-delivery of same event id → no double effect. Commit `feat(billing): signed, idempotent Stripe webhook`.

### Task 10: Webhook event → user plan state

**Files:**
- Modify: `backend/api/billing_v2.py`; `backend/db.py` (`set_user_plan(user_id, plan, plan_status, stripe_subscription_id, current_period_end)`)
- Test: `backend/tests/test_webhook_handlers.py`

Handle:
- `checkout.session.completed` — subscription: set `plan` from the session's price→plan map, `plan_status="active"`, store `stripe_subscription_id`, `current_period_end`; one-off (`mode=payment`): grant one `billing_usage` "oneoff-credit" (or set a one-shot entitlement) + trigger invoice (Phase 6). Resolve the user via `client_reference_id`.
- `customer.subscription.updated` — refresh `plan_status` (`active`/`past_due`/`canceled`), `current_period_end`, and `plan` if the price changed.
- `customer.subscription.deleted` — set `plan="free"`, `plan_status="canceled"`, clear `stripe_subscription_id`.
- `invoice.payment_failed` — `plan_status="past_due"` (keep access per grace policy = keep until `subscription.deleted`).

Map Stripe price IDs → plan id via the `stripe_price_env` values (build a reverse map at call time). Unknown price → log + skip (never crash the webhook).

- [ ] Test each event mutates the user row correctly (mock event payloads). Commit `feat(billing): webhook handlers map Stripe state onto users row`.

---

## Phase 4 — Usage surface & upgrade-block

### Task 11: `GET /api/billing/usage`

**Files:** Modify `backend/api/billing_v2.py`; Test `backend/tests/test_usage_endpoint.py`

Requires `require_user`. Returns `{ enabled, plan, plan_status, used, quota, remaining, current_period_end }` (from entitlements). When flag off, returns `{enabled:false}` and the frontend shows no meter. Drives the usage meter + the "switch to one-off / upgrade" nudge.

- [ ] Test values for a free user with 0/1 used. Commit `feat(billing): usage endpoint for meter + nudge`.

---

## Phase 5 — Free-trial company-code gate

### Task 12: Company code capture + validation

**Files:** Modify `backend/api/billing_v2.py` (or the profile/settings route), `backend/db.py`; Create `backend/billing/trial.py`; Test `backend/tests/test_trial_gate.py`

`normalize_company_code(raw)` — strip spaces, uppercase, keep digits (LT įmonės kodas is numeric, typically 9 digits); reject empty/malformed with a clear error. `trial_available(code)` — False if the normalized code exists in `consumed_trials`. `consume_trial(code, user_id)` — insert into `consumed_trials` (UNIQUE enforces one-per-company; on IntegrityError → already consumed → return False).

- [ ] **Step 1: Failing test**

```python
# backend/tests/test_trial_gate.py
import importlib
def test_one_trial_per_company_survives_account_delete(monkeypatch, tmp_path):
    monkeypatch.setenv("SAMATU_DB_PATH", str(tmp_path/"t.db"))
    import db; importlib.reload(db); db.init_db()
    import billing.trial as trial; importlib.reload(trial)
    assert trial.trial_available("302536741") is True
    assert trial.consume_trial("302536741", user_id="u1") is True
    assert trial.trial_available("30 25 36 741") is False   # normalized dup
    # simulate account deletion — consumed_trials row remains (no FK cascade).
    # (No db.delete_user helper exists — delete the row directly for the test.)
    with db._conn() as c:  # use the module's connection helper
        c.execute("DELETE FROM users WHERE id = ?", ("u1",))
    assert trial.trial_available("302536741") is False
    assert trial.consume_trial("302536741", user_id="u2") is False
```

- [ ] Implement `trial.py` + wire the trial consumption into the free-project path (a `free`-plan user's first billable extraction requires a `company_code` on the row and consumes the trial; subsequent = quota_exceeded). Commit `feat(billing): company-code-gated free trial, persists past account deletion`.

---

## Phase 6 — LT PVM sąskaita-faktūra generator

### Task 13: Invoice PDF renderer

**Files:** Create `backend/billing/invoice.py`; Test `backend/tests/test_invoice_pdf.py`

Reuse reportlab (already a dep; mirror `main.py` PDF usage). `render_pvm_invoice_pdf(invoice: dict) -> bytes` renders a valid LT sąskaita-faktūra: **supplier block** (Pathon: pavadinimas, įmonės kodas, PVM kodas if registered, adresas, IBAN — from `PATHON_COMPANY_*` env), **buyer block** (name, company_code, pvm_code from the user row), serija+numeris, išrašymo data, line item (description, qty, unit price, sum), total, and the **reverse-charge note** ("Atvirkštinis PVM (PVMĮ 96 str.)") when the buyer has a valid `pvm_code`, else "Pardavėjas nėra PVM mokėtojas" when Pathon is under threshold. No VAT amount line when reverse-charged.

- [ ] **Step 1: Failing test** — assert the returned bytes start with `%PDF`, and that rendering with a buyer `pvm_code` includes the reverse-charge note (render to text via a stub or assert the code path chosen), and required fields are present (unit-test the field-assembly function separately from the PDF bytes for assertability).
- [ ] Implement (split a pure `build_invoice_fields(user, plan, payment)` from the reportlab rendering so the field logic is unit-testable without parsing PDF bytes). Commit `feat(billing): LT PVM sąskaita-faktūra generator (reverse-charge aware)`.

### Task 14: Emit invoice on payment + retrieval

**Files:** Modify `backend/api/billing_v2.py` (webhook one-off + `invoice.paid`), `backend/db.py` (`invoices` table: id, user_id, number, pdf path/bytes ref, created_at); Test `backend/tests/test_invoice_emit.py`

On `checkout.session.completed` (one-off) and subscription `invoice.paid`, build fields, render PDF, persist (R2 or `data/invoices/{id}.pdf` — mirror existing PDF storage), store a row. `GET /api/billing/invoices` (owner-scoped, mirror the ownership pattern from `docs/SECURITY.md` §3) lists them; `GET /api/billing/invoices/{id}` streams the owner's PDF (404 for non-owners — reuse `auth.require_owned_project`-style gate).

- [ ] Test emit-on-webhook + owner-only retrieval (A-vs-B → 404). Commit `feat(billing): persist + serve PVM invoices, owner-scoped`.

---

## Phase 7 — Frontend (flag-gated)

### Task 15: `GET /status`-driven flag in the app

**Files:** Modify `frontend/src/` billing/config loader; Test: component test if harness exists, else manual.

Fetch `/api/billing/v2/status`; when `enabled=false`, render **no** billing UI anywhere (today's app). All billing components below mount only when enabled.

- [ ] Implement a `useBilling()` hook returning `{enabled, plans, usage}`. Commit `feat(billing-ui): billing gated on /status enabled flag`.

### Task 16: Pricing page + checkout redirect

**Files:** Create `frontend/src/components/PricingPage.jsx`; wire a route + nav entry (visible only when enabled).

Render `PUBLIC_PLANS` (Pro, Studio, one-off) in LT with EUR prices and the reverse-charge note ("Kainos be PVM — taikomas atvirkštinis apmokestinimas"). Each purchasable plan's CTA → `POST /api/billing/checkout` → `window.location = url`. Success/cancel routes show a toast (reuse the shadcn toast per the June "kill amateur alert()" note).

- [ ] Implement; verify in the browser with `BILLING_ENABLED=1` locally (test keys) that Checkout opens. Commit `feat(billing-ui): pricing page + Stripe Checkout redirect`.

### Task 17: Usage meter + upgrade dialog

**Files:** Create `frontend/src/components/UpgradeDialog.jsx`; modify dashboard to show `used/quota` and intercept a `402 quota_exceeded` from `/extract-interior` → open the dialog (upgrade OR one-off), plus the light-user nudge ("Panaudojote 3/10 — apsvarstykite vienkartinį planą").

- [ ] Implement; browser-verify the 402 path opens the dialog. Commit `feat(billing-ui): usage meter, upgrade-block dialog, one-off nudge`.

### Task 18: Billing settings (company code, plan, manage)

**Files:** Create `frontend/src/components/BillingSettings.jsx`.

Fields: company_code (įmonės kodas) + pvm_code (optional) with save → PUT profile; current plan + period end; "Manage subscription" → Stripe Billing Portal (`POST /api/billing/portal` returns a portal URL); invoice list (download PDFs). Company code is required before the free trial can be consumed (surfaced inline).

- [ ] Implement + browser-verify. Commit `feat(billing-ui): billing settings, company code, portal, invoices`.

---

## Phase 8 — Flag-flip verification (the invariant)

### Task 19: OFF = today, ON = paywall — integration proof

**Files:** Create `backend/tests/test_billing_flag_flip.py`

- [ ] **OFF proof:** with `BILLING_ENABLED` unset, a `free`-plan user runs N>1 mocked `/extract-interior` calls → all succeed (no 402), no `billing_usage` enforcement, `/api/billing/v2/status` → `enabled:false`, `feature_allowed(...)` all True.
- [ ] **ON proof:** with `BILLING_ENABLED=1`, a `free` user's 2nd extraction → 402 `quota_exceeded`; a `pro` user (mock webhook-applied) gets 10 then 402 on the 11th; F2/F3 feature gated for free, allowed for pro.
- [ ] Run the FULL backend suite fresh; confirm no regression (dodge the known spend-cap DB-pollution flake per prior runs).
- [ ] **Commit** — `test(billing): prove flag OFF = pre-billing behavior, ON = full paywall`

### Task 20: Docs + env template

**Files:** Modify `.env.example`, `docs/SECURITY.md` (webhook endpoint is unauthenticated-by-design but signature-verified — add to §10), create `docs/billing.md` (operator runbook: env vars, going live checklist, price-id setup, quota-policy switch, invoice supplier block).

- [ ] Document every env var; note the webhook path in the security posture; note Stripe test-vs-live key swap. Commit `docs(billing): env template + operator runbook + security note`.

---

## Founder-side inputs (needed only for live verification, not to build)
- **Stripe account (test mode)** → `STRIPE_SECRET_KEY`, per-tier `STRIPE_PRICE_*` (create 3 Prices: Pro €49/mo, Studio €149/mo, one-off €12), `STRIPE_WEBHOOK_SECRET` (from `stripe listen` / dashboard). Founder sets these in `.env`/Render themselves — Claude never handles key values.
- **Pathon company legal block** for the invoice supplier: pavadinimas, įmonės kodas, (PVM kodas if registered), adresas, IBAN → `PATHON_COMPANY_*` env.

## Notes / prior-art to follow
- Migrations: append-only `_migrate_schema` (`backend/db.py:565`).
- Ownership gate for invoice retrieval: `auth.require_owned_project` pattern (`docs/SECURITY.md` §3).
- Quota hooks the existing billable gate (`auth.py:184` → `main.py:_check_user_spend_cap`).
- Reservation/self-metered paths (`main.py:298`) — do not double-count; `billing_usage` is separate from `usage_events` (cost ledger) and counts *projects*, not €.
