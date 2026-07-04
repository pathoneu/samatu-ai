"""W3 Phase 1 Task 4 — entitlements + policy-driven quota computation.

Uses the real db idioms (no init_db()/SAMATU_DB_PATH): isolate by
monkeypatching db._DB_PATH to a tmp file, then init_schema()+_migrate_schema()
(both idempotent). billing_enabled() reads BILLING_ENABLED at call time, so the
flag env is set per-test — the modules do not cache it.
"""
import importlib

import db
import billing.entitlements as ent


def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "ent.db")
    db.init_schema()
    db._migrate_schema()


def _mkuser(**kw):
    base = {"id": "u1", "plan": "pro", "plan_status": "active",
            "current_period_end": None}
    base.update(kw)
    return base


def test_free_plan_one_project(monkeypatch, tmp_path):
    _isolate(tmp_path, monkeypatch)
    monkeypatch.setenv("BILLING_ENABLED", "1")
    u = _mkuser(id="f1", plan="free")
    assert ent.projects_remaining(u) == 1
    db.record_billing_usage("f1", kind="extract")
    assert ent.projects_remaining(u) == 0
    assert ent.quota_exceeded(u) is True


def test_pro_plan_ten_projects(monkeypatch, tmp_path):
    _isolate(tmp_path, monkeypatch)
    monkeypatch.setenv("BILLING_ENABLED", "1")
    u = _mkuser(id="p1", plan="pro")
    assert ent.projects_remaining(u) == 10
    for _ in range(10):
        db.record_billing_usage("p1", kind="extract")
    assert ent.projects_used(u) == 10
    assert ent.projects_remaining(u) == 0
    assert ent.quota_exceeded(u) is True


def test_flag_off_never_exceeds(monkeypatch, tmp_path):
    """The invariant that matters most: flag OFF ⇒ quota is never enforced,
    even after far more usages than any plan allows (today's behavior)."""
    _isolate(tmp_path, monkeypatch)
    monkeypatch.delenv("BILLING_ENABLED", raising=False)
    u = _mkuser(id="u1", plan="free")
    for _ in range(5):
        db.record_billing_usage("u1", kind="extract")
    assert ent.quota_exceeded(u) is False   # flag OFF ⇒ no enforcement


def test_oneoff_never_quota_blocks(monkeypatch, tmp_path):
    """one-off users are gated at purchase, not by a monthly quota."""
    _isolate(tmp_path, monkeypatch)
    monkeypatch.setenv("BILLING_ENABLED", "1")
    u = _mkuser(id="o1", plan="oneoff")
    for _ in range(5):
        db.record_billing_usage("o1", kind="extract")
    assert ent.quota_exceeded(u) is False


def test_feature_gate(monkeypatch):
    monkeypatch.setenv("BILLING_ENABLED", "1")
    assert ent.feature_allowed(_mkuser(plan="pro"), "f2f3_export") is True
    assert ent.feature_allowed(_mkuser(plan="free"), "f2f3_export") is False


def test_feature_gate_flag_off_all_allowed(monkeypatch):
    """Flag OFF ⇒ every feature unlocked (today's behavior)."""
    monkeypatch.delenv("BILLING_ENABLED", raising=False)
    assert ent.feature_allowed(_mkuser(plan="free"), "f2f3_export") is True
    assert ent.feature_allowed(_mkuser(plan="free"), "audit_trail") is True


def test_subscriber_period_window(monkeypatch, tmp_path):
    """A subscriber with current_period_end counts usage within the
    [period_end − ~30d, period_end) window; usage older than that window
    (from a prior period) does not count against the current quota."""
    _isolate(tmp_path, monkeypatch)
    monkeypatch.setenv("BILLING_ENABLED", "1")
    # period ends 5 days from now
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    period_end = (now + timedelta(days=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    u = _mkuser(id="s1", plan="pro", current_period_end=period_end)
    # one usage inside the window (now) and one well before the window start
    db.record_billing_usage("s1", kind="extract")
    old = (now - timedelta(days=60)).strftime("%Y-%m-%dT%H:%M:%SZ")
    with db._conn() as c:
        c.execute(
            "INSERT INTO billing_usage (user_id, kind, project_id, created_at) "
            "VALUES ('s1', 'extract', NULL, ?)", (old,))
    assert ent.projects_used(u) == 1  # only the in-window one counts


def test_kind_filter(monkeypatch, tmp_path):
    """Only rows of the requested kind count toward projects_used."""
    _isolate(tmp_path, monkeypatch)
    monkeypatch.setenv("BILLING_ENABLED", "1")
    u = _mkuser(id="k1", plan="pro")
    db.record_billing_usage("k1", kind="extract")
    db.record_billing_usage("k1", kind="oneoff-credit")
    assert ent.projects_used(u) == 1
