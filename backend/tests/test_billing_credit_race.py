"""One-off credit consumption must be atomic — balance can never go negative
(audit 2026-07-06).

The bug: record_extract_and_maybe_consume_credit() did a check-then-act —
`if credits_balance(uid) > 0: record_billing_usage('credit_consumed')` — across
two SEPARATE db connections. Two concurrent extractions both read balance==1 and
both wrote credit_consumed, driving the balance to −1 (a free extraction). The
fix routes consumption through _consume_oneoff_credit_if_available(), a single
conditional INSERT ... SELECT WHERE (balance) > 0 that SQLite serializes.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import db  # noqa: E402


def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "credit.db")
    db.init_schema()
    db._migrate_schema()


# ── deterministic: the conditional guard never goes negative ─────────────────

def test_consume_never_goes_negative(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    user = db.create_user("c1@x.lt", "!x", name="C1")
    uid = user["id"]

    db.grant_oneoff_credit(uid)                       # balance 1
    assert db.credits_balance(uid) == 1

    assert db._consume_oneoff_credit_if_available(uid) is True
    assert db.credits_balance(uid) == 0               # consumed

    # No credit left → the conditional inserts nothing, balance stays 0 (not −1).
    assert db._consume_oneoff_credit_if_available(uid) is False
    assert db.credits_balance(uid) == 0


def test_two_credits_two_consumes(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    user = db.create_user("c2@x.lt", "!x", name="C2")
    uid = user["id"]
    db.grant_oneoff_credit(uid)
    db.grant_oneoff_credit(uid)                       # balance 2
    assert db._consume_oneoff_credit_if_available(uid) is True
    assert db._consume_oneoff_credit_if_available(uid) is True
    assert db._consume_oneoff_credit_if_available(uid) is False   # only 2 existed
    assert db.credits_balance(uid) == 0


# ── concurrent: N threads racing 1 credit consume it exactly once ────────────

def test_concurrent_consumers_consume_one_credit_exactly_once(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    user = db.create_user("c3@x.lt", "!x", name="C3")
    uid = user["id"]
    db.grant_oneoff_credit(uid)                       # exactly 1 credit

    def worker(_i):
        return db._consume_oneoff_credit_if_available(uid)

    with ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(worker, range(8)))

    # Exactly one of the 8 racers won the single credit; balance never negative.
    assert sum(1 for r in results if r) == 1, results
    assert db.credits_balance(uid) == 0
