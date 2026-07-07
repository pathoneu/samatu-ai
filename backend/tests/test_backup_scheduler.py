"""Nightly backup scheduler gating + timing (2026-06-21 durability track).

The async loop itself is just sleep→backup→repeat; what's worth pinning is that it
stays OFF in dev/tests and ON in prod, and that the next-run delay is sane.
"""
import asyncio


def _fresh(monkeypatch):
    for k in ("SAMATU_NIGHTLY_BACKUP", "R2_BUCKET",
              "SAMATU_BACKUP_HOUR_UTC", "SAMATU_BACKUP_MINUTE_UTC"):
        monkeypatch.delenv(k, raising=False)
    import backup_scheduler
    return backup_scheduler


def test_disabled_by_default(monkeypatch):
    bs = _fresh(monkeypatch)
    assert bs.is_enabled() is False  # dev/tests: no flag, no R2 → off


def test_enabled_when_r2_configured(monkeypatch):
    bs = _fresh(monkeypatch)
    monkeypatch.setenv("R2_BUCKET", "samatu-pdfs")
    assert bs.is_enabled() is True  # prod is automatic


def test_explicit_flag_overrides(monkeypatch):
    bs = _fresh(monkeypatch)
    monkeypatch.setenv("R2_BUCKET", "samatu-pdfs")
    monkeypatch.setenv("SAMATU_NIGHTLY_BACKUP", "0")
    assert bs.is_enabled() is False  # explicit off beats the R2 default
    monkeypatch.setenv("SAMATU_NIGHTLY_BACKUP", "on")
    assert bs.is_enabled() is True


def test_seconds_until_is_within_a_day(monkeypatch):
    bs = _fresh(monkeypatch)
    secs = bs._seconds_until(3, 15)
    assert 0 < secs <= 24 * 3600


def test_start_is_noop_when_disabled(monkeypatch):
    bs = _fresh(monkeypatch)

    async def go():
        started = bs.start()           # disabled → must not schedule anything
        assert started is False
        await bs.stop()                # idempotent when nothing running
    asyncio.run(go())
