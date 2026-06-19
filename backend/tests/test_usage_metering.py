"""Per-user Vision-cost metering (2026-06-19 commercial level-up, plan move #2).

Before this fix the per-user spend cap could NEVER fire: db.save_extraction()
had zero callers (and needed a project_id FK that doesn't exist at extract time),
so the cost ledger was always empty and user_recent_spend_eur() always returned 0.
The new user-keyed usage_events ledger + record_usage()/user_usage_since() make
the cap real. These tests lock that in.
"""
import db


def _resp(in_t, out_t, cache_t=0):
    return {"_meta": {"input_tokens": in_t, "output_tokens": out_t,
                      "cache_read_tokens": cache_t}}


def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "metering.db")
    db.init_schema()


def test_record_usage_populates_ledger(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    cost = db.record_usage("u1", _resp(100_000, 5_000), "extract-interior")
    assert cost > 0
    total, n = db.user_usage_since("u1", hours=24)
    assert n == 1
    assert abs(total - round(cost, 4)) < 0.01


def test_zero_token_response_records_nothing(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    assert db.record_usage("u1", {"_meta": {}}, "x") == 0.0
    assert db.record_usage("u1", _resp(0, 0, 0), "x") == 0.0
    total, n = db.user_usage_since("u1")
    assert n == 0 and total == 0.0


def test_anonymous_user_is_noop(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    assert db.record_usage(None, _resp(1_000, 1_000), "x") == 0.0


def test_usage_is_isolated_per_user(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    db.record_usage("u1", _resp(100_000, 5_000))
    db.record_usage("u2", _resp(100_000, 5_000))
    db.record_usage("u1", _resp(100_000, 5_000))
    _, n1 = db.user_usage_since("u1")
    _, n2 = db.user_usage_since("u2")
    assert n1 == 2
    assert n2 == 1


def test_hourly_count_is_a_reliable_backstop(tmp_path, monkeypatch):
    # The hourly COUNT cap (events, not tokens) is the hard backstop against a
    # runaway loop and is unaffected by any token-accuracy undercount.
    _isolate(tmp_path, monkeypatch)
    for _ in range(25):
        db.record_usage("u1", _resp(1_000, 500))
    _, n = db.user_usage_since("u1", hours=1)
    assert n == 25
