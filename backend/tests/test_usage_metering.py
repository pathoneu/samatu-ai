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


# ── Reservations (2026-06-19 bug-hunt: cap only saw extract-interior actuals) ──

def test_record_reservation_counts_toward_cap(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    db.record_reservation("u1", 0.30, "reserve:/extract")
    total, n = db.user_usage_since("u1", hours=24)
    assert n == 1
    assert abs(total - 0.30) < 1e-6


def test_reservation_noop_on_anonymous_or_zero(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    assert db.record_reservation(None, 0.30) == 0.0
    assert db.record_reservation("u1", 0.0) == 0.0
    _, n = db.user_usage_since("u1")
    assert n == 0


def test_hourly_extract_cap_ignores_light_reservations(tmp_path, monkeypatch):
    """The hourly-EXTRACT cap counts only extraction events ('%extract%'), so a
    flurry of light-endpoint reservations (chat/vision_fill/lasso/symbols) does
    NOT falsely trip an 'extracts/hour' limit — while the EUR sum still includes
    them. (2026-06-19: the reservation fix initially tripped the cap on light calls.)"""
    _isolate(tmp_path, monkeypatch)
    for _ in range(30):
        db.record_reservation("u1", 0.03, "reserve:/chat-project")
    spend, n_extracts = db.user_usage_since("u1", hours=1, kind_like="%extract%")
    assert n_extracts == 0          # light reservations don't count as extracts
    assert spend > 0                # but they DO count toward EUR spend
    # extraction events (a reserve:/extract pre-charge + an extract-interior actual) count
    db.record_reservation("u1", 0.30, "reserve:/extract")
    db.record_usage("u1", _resp(1_000, 500), "extract-interior")
    _, n_extracts = db.user_usage_since("u1", hours=1, kind_like="%extract%")
    assert n_extracts == 2


def test_reserve_billable_skips_extract_interior_meters_others(tmp_path, monkeypatch):
    """The reservation must fire for every billable path EXCEPT extract-interior
    (which self-reports actuals) — otherwise the cap stays dead for the other
    ~13 endpoints, or double-counts extract-interior."""
    _isolate(tmp_path, monkeypatch)
    import main
    main._reserve_billable("u1", "/extract-interior")
    main._reserve_billable("u1", "/extract-interior-stream")
    _, n0 = db.user_usage_since("u1")
    assert n0 == 0  # self-metered → no reservation
    main._reserve_billable("u1", "/chat-project")        # 0.03
    main._reserve_billable("u1", "/extract")             # 0.30
    main._reserve_billable("u1", "/v9/symbols/detect")   # 0.10
    total, n = db.user_usage_since("u1")
    assert n == 3
    assert abs(total - 0.43) < 1e-6
