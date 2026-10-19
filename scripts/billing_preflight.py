#!/usr/bin/env python
"""READ-ONLY billing pre-flight: may BILLING_ENABLED be set to "1" here? (2026-10-18)

docs/DEVELOPING.md › "Deploy / billing": never flip the flag without the
pre-flight. This script is that pre-flight, run in the environment that is
about to flip (Railway shell, or locally with that environment's variables):

  1. Stripe: the secret key, the webhook secret and the three price ids are
     present (NAMES are printed, values never — only whether the key is a test
     or a live key).
  2. Webhook signature: a payload signed here with STRIPE_WEBHOOK_SECRET
     verifies through billing.stripe_client.construct_event, and a tampered one
     is refused. Offline — it proves the secret is wired into the code path,
     not that Stripe delivers to the URL (that is a manual check below).
  3. Usage metering: the database the backend would open has the
     usage_events and billing_usage tables, and usage_events has rows from the
     last 7 days (a silent failure there would let a user read projects
     uncharged). Opened read-only.
  4. Spend guards: SAMATU_USER_DAILY_SPEND_EUR > 0 and
     SAMATU_USER_HOURLY_EXTRACTS > 0 (audit backend-security-1).
  5. Invoice supplier block: PATHON_COMPANY_NAME / _CODE / _ADDRESS / _IBAN /
     _EMAIL are set; PATHON_COMPANY_PVM set or not decides the VAT branch
     (printed, so whoever flips the flag sees which rule invoices will follow).

It changes nothing, calls no network service, and has no option to.
Exit code 0 = every hard check passed; 1 = at least one failed (the list says
which); manual checks are printed either way.

Usage (from the repository root):
    venv/bin/python scripts/billing_preflight.py
    venv/bin/python scripts/billing_preflight.py --json
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BACKEND = REPO / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

PRICE_ENVS = ("STRIPE_PRICE_PRO", "STRIPE_PRICE_STUDIO", "STRIPE_PRICE_ONEOFF")
SUPPLIER_ENVS = ("PATHON_COMPANY_NAME", "PATHON_COMPANY_CODE", "PATHON_COMPANY_ADDRESS",
                 "PATHON_COMPANY_IBAN", "PATHON_COMPANY_EMAIL")

MANUAL_CHECKS = [
    "Stripe Dashboard → Webhooks: the endpoint https://api.pathon.eu/api/billing/v2/webhook "
    "is subscribed to checkout.session.completed, checkout.session.async_payment_succeeded, "
    "checkout.session.async_payment_failed, customer.subscription.updated, "
    "customer.subscription.deleted, invoice.paid, invoice.payment_failed — and a test "
    "event shows 200 in its delivery log.",
    "Stripe Checkout payment methods: if delayed methods (SEPA, bank transfer) are on, a "
    "test purchase with one grants nothing until async_payment_succeeded arrives.",
    "An accountant has confirmed the invoice VAT rule (audit backend-security-8; "
    "backend/billing/invoice.py module docstring states the rule the code applies).",
    "The prices in backend/billing/plans.py are the ones the founder approved, and the "
    "Stripe price ids point at the same amounts.",
    "Run once with test keys end to end: buy the one-off, see one credit and one invoice; "
    "subscribe Pro, see plan=pro; cancel, see plan=free.",
]


def _present(name: str) -> bool:
    return bool((os.environ.get(name) or "").strip())


def _key_mode(key: str) -> str:
    if key.startswith(("sk_live_", "rk_live_")):
        return "live"
    if key.startswith(("sk_test_", "rk_test_")):
        return "test"
    return "unknown"


def check_stripe_env() -> dict:
    missing = [n for n in ("STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET", *PRICE_ENVS) if not _present(n)]
    mode = _key_mode(os.environ.get("STRIPE_SECRET_KEY", "")) if _present("STRIPE_SECRET_KEY") else "absent"
    return {"name": "stripe_env", "ok": not missing, "missing": missing, "key_mode": mode}


def _sign(payload: bytes, secret: str, ts: int) -> str:
    mac = hmac.new(secret.encode(), f"{ts}.".encode() + payload, hashlib.sha256).hexdigest()
    return f"t={ts},v1={mac}"


def check_webhook_signature() -> dict:
    if not (_present("STRIPE_SECRET_KEY") and _present("STRIPE_WEBHOOK_SECRET")):
        return {"name": "webhook_signature", "ok": False, "detail": "secret key or webhook secret missing"}
    from billing import stripe_client
    secret = os.environ["STRIPE_WEBHOOK_SECRET"]
    payload = json.dumps({"id": "evt_preflight", "object": "event",
                          "type": "preflight.check", "data": {"object": {}}}).encode()
    ts = int(time.time())
    try:
        event = stripe_client.construct_event(payload, _sign(payload, secret, ts))
        good = (event.get("id") if isinstance(event, dict) else getattr(event, "id", None)) == "evt_preflight"
    except Exception as exc:  # noqa: BLE001 — reported, never raised
        return {"name": "webhook_signature", "ok": False, "detail": f"signed payload refused: {type(exc).__name__}"}
    try:
        stripe_client.construct_event(payload + b" ", _sign(payload, secret, ts))
        tampered_refused = False
    except ValueError:
        tampered_refused = True
    except Exception:  # noqa: BLE001
        tampered_refused = False
    return {"name": "webhook_signature", "ok": bool(good and tampered_refused),
            "detail": "signed payload verified, tampered payload refused" if good and tampered_refused
            else "verification did not behave as expected"}


def _db_path() -> Path:
    return Path(os.environ.get("SAMATU_DB_PATH", BACKEND / "data" / "samatu.db"))


def check_usage_metering() -> dict:
    path = _db_path()
    if not path.exists():
        return {"name": "usage_metering", "ok": False, "detail": f"database not found ({path.name})"}
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        need = {"usage_events", "billing_usage", "webhook_events", "invoices"}
        missing = sorted(need - tables)
        recent = None
        if "usage_events" in tables:
            since = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 7 * 86400))
            recent = con.execute("SELECT COUNT(*) FROM usage_events WHERE created_at >= ?",
                                 (since,)).fetchone()[0]
        con.close()
    except sqlite3.Error as exc:
        return {"name": "usage_metering", "ok": False, "detail": f"database unreadable: {exc}"}
    ok = not missing and (recent or 0) > 0
    return {"name": "usage_metering", "ok": ok, "missing_tables": missing,
            "usage_events_last_7_days": recent,
            "detail": "" if ok else "no usage_events rows in 7 days — confirm metering before charging"}


def check_spend_guards() -> dict:
    def num(name):
        try:
            return float(os.environ.get(name) or 0)
        except ValueError:
            return 0.0
    daily = num("SAMATU_USER_DAILY_SPEND_EUR")
    # main.py defaults the hourly cap to 20 when unset; only an explicit 0 turns it off.
    hourly = num("SAMATU_USER_HOURLY_EXTRACTS") if _present("SAMATU_USER_HOURLY_EXTRACTS") else 20.0
    return {"name": "spend_guards", "ok": daily > 0 and hourly > 0,
            "daily_spend_eur": daily, "hourly_extracts": hourly}


def check_invoice_supplier() -> dict:
    missing = [n for n in SUPPLIER_ENVS if not _present(n)]
    vat_branch = ("Pathon registered for PVM: 21 % for buyers without a PVM kodas, "
                  "reverse charge for buyers with one") if _present("PATHON_COMPANY_PVM") else \
                 ("Pathon not registered for PVM: no PVM line, except buyers with a PVM kodas "
                  "get the reverse-charge note")
    return {"name": "invoice_supplier", "ok": not missing, "missing": missing, "vat_branch": vat_branch}


def run() -> dict:
    checks = [check_stripe_env(), check_webhook_signature(), check_usage_metering(),
              check_spend_guards(), check_invoice_supplier()]
    return {"billing_enabled_now": os.environ.get("BILLING_ENABLED", "0") == "1",
            "ok": all(c["ok"] for c in checks), "checks": checks, "manual": MANUAL_CHECKS}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)
    try:
        from dotenv import load_dotenv
        load_dotenv(BACKEND / ".env", override=False)
    except ImportError:
        pass
    report = run()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"BILLING_ENABLED is now: {'1 (ON)' if report['billing_enabled_now'] else 'off'}")
        for c in report["checks"]:
            extra = {k: v for k, v in c.items() if k not in ("name", "ok")}
            print(f"  [{'OK ' if c['ok'] else 'FAIL'}] {c['name']}: {json.dumps(extra, ensure_ascii=False)}")
        print("Manual checks (nobody can script these):")
        for m in report["manual"]:
            print(f"  - {m}")
        print("RESULT:", "every scripted check passed" if report["ok"] else "NOT READY — fix the FAIL lines first")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
