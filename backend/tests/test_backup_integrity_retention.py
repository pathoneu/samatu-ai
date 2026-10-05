"""Nightly backups: checked before upload, outcome persisted, retention opt-in
(2026-10-05, audit data-ops-infra-9 / product-strategy-9).

  * integrity — `PRAGMA integrity_check` runs on the snapshot before it leaves
    the machine; a snapshot that fails is never uploaded, and the failure is
    recorded with its key and size;
  * outcome — time, ok/failed, key, size of the last attempt (and the last good
    one) live in app_state, so a restart no longer blanks them, and the admin
    system-health payload reports them;
  * retention — OFF unless SAMATU_BACKUP_KEEP_DAYS is set (env unset → not one
    delete call); when on, the newest 7 snapshots are kept whatever their age,
    and only keys with the exact backup name are ever considered. It runs only
    after a night whose own snapshot was stored.

Temp database, local storage in a temp dir — never R2, never backend/data.
"""
from __future__ import annotations

import asyncio
import datetime
import json
import logging
import sqlite3

import pytest

import backup
import backup_scheduler as bs
import db
import storage

UTC = datetime.timezone.utc
NOW = datetime.datetime(2026, 10, 5, 3, 15, tzinfo=UTC)


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "live.db")
    db.init_schema()
    db._migrate_schema()
    db.create_user("u@x.lt", "h", name="U")             # something to snapshot
    for k in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET",
              "SAMATU_BACKUP_KEEP_DAYS", "SAMATU_NIGHTLY_BACKUP"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("LOCAL_STORAGE_DIR", str(tmp_path / "store"))
    storage.reset_storage_for_test()
    backend = storage.get_storage()
    assert isinstance(backend, storage.LocalDiskStorage)
    monkeypatch.setattr(bs, "_last", bs._blank())
    yield backend
    storage.reset_storage_for_test()


class _Spy:
    """Wraps a backend: records puts/deletes/listings, then does them."""

    def __init__(self, backend):
        self.backend, self.puts, self.deletes, self.listings = backend, [], [], []

    def put(self, key, data, content_type="application/pdf"):
        self.puts.append(key)
        return self.backend.put(key, data, content_type)

    def delete(self, key):
        self.deletes.append(key)
        return self.backend.delete(key)

    def list_keys(self, prefix=""):
        self.listings.append(prefix)
        return self.backend.list_keys(prefix)

    def __getattr__(self, name):
        return getattr(self.backend, name)


def _spy(backend) -> _Spy:
    """Make the spy THE storage backend. Set directly, not via monkeypatch:
    the `env` fixture's teardown resets the backend to None, and a monkeypatch
    undo running after it would bring this test's temp-dir backend back."""
    spy = _Spy(backend)
    storage._instance = spy
    return spy


def _stamp(dt: datetime.datetime) -> str:
    return dt.strftime("%Y%m%dT%H%M%SZ")


def _seed_snapshots(backend, ages_days) -> list[str]:
    """One snapshot per age (days before NOW), returned newest first."""
    keys = []
    for age in sorted(ages_days):
        key = backup.backup_key(_stamp(NOW - datetime.timedelta(days=age)))
        backend.put(key, b"SQLite format 3\x00" + key.encode())
        keys.append(key)
    return keys


def _stored(backend, prefix="backups/") -> set[str]:
    return {k for k, _ in backend.list_keys(prefix)}


# ── integrity check before upload ────────────────────────────────────────────

def _corrupting_snapshot(real):
    def snap(dest):
        real(dest)
        raw = bytearray(dest.read_bytes())
        page = int.from_bytes(raw[16:18], "big") or 65536
        assert len(raw) >= 3 * page, "the test DB must span a few pages"
        raw[page:page + 64] = b"\xff" * 64           # wreck page 2's b-tree header
        dest.write_bytes(bytes(raw))
    return snap


def _grow_db():
    with db._conn() as c:
        c.execute("CREATE TABLE IF NOT EXISTS filler (v TEXT)")
        c.executemany("INSERT INTO filler (v) VALUES (?)", [("x" * 400,)] * 200)


def test_a_snapshot_failing_integrity_check_is_never_uploaded(env, monkeypatch):
    _grow_db()
    spy = _spy(env)
    monkeypatch.setattr(backup, "_snapshot", _corrupting_snapshot(backup._snapshot))
    with pytest.raises(backup.BackupError) as info:
        backup.backup_db(stamp="20261005T031500Z")
    assert "integrity_check" in str(info.value) and "NOT uploaded" in str(info.value)
    assert info.value.key == "backups/samatu-20261005T031500Z.db"
    assert info.value.size and info.value.size > 0
    assert spy.puts == []
    assert _stored(env) == set()


def test_a_file_that_is_no_database_is_never_uploaded(env, monkeypatch):
    spy = _spy(env)
    monkeypatch.setattr(backup, "_snapshot", lambda dest: dest.write_bytes(b"not sqlite" * 500))
    with pytest.raises(backup.BackupError):
        backup.backup_db(stamp="20261005T031500Z")
    assert spy.puts == [] and _stored(env) == set()


def test_the_check_runs_on_the_snapshot_before_the_upload(env, monkeypatch):
    seen = []
    real = backup._integrity_problem

    def check(path):
        seen.append((path.read_bytes(), _stored(env)))
        return real(path)
    monkeypatch.setattr(backup, "_integrity_problem", check)
    res = backup.backup_db(stamp="20261005T031500Z")
    assert len(seen) == 1
    checked_bytes, stored_at_check_time = seen[0]
    assert stored_at_check_time == set()                  # checked, THEN uploaded
    assert env.get(res["key"]) == checked_bytes           # the bytes that passed
    assert res["size"] == len(checked_bytes)
    assert checked_bytes.startswith(b"SQLite format 3")


def test_the_scheduler_records_an_integrity_failure_and_keeps_the_last_good_one(env, monkeypatch):
    _grow_db()
    bs._record_ok({"key": "backups/samatu-20261004T031500Z.db", "size": 4096,
                   "backend": "LocalDiskStorage"})
    good = bs.last_outcome()
    monkeypatch.setattr(backup, "_snapshot", _corrupting_snapshot(backup._snapshot))
    spy = _spy(env)
    prunes = []
    monkeypatch.setattr(backup, "prune_backups", lambda *a, **k: prunes.append(1) or {})
    _run_one_night(monkeypatch)
    assert spy.puts == []
    out = bs.last_outcome()
    att = out["last_attempt"]
    assert att["ok"] is False and att["key"].startswith("backups/samatu-")
    assert att["size"] > 0 and "integrity_check" in att["error"]
    assert out["last_error"] == att["error"]
    # The good snapshot from the night before is still what a restore would use.
    assert (out["last_ok_at"], out["last_key"], out["last_size"]) == (
        good["last_ok_at"], "backups/samatu-20261004T031500Z.db", 4096)
    assert prunes == []                                   # no stored snapshot → no prune
    stored = json.loads(db.get_state("backup_last_outcome"))
    assert stored["last_attempt"]["ok"] is False


# ── the outcome survives a restart ───────────────────────────────────────────

def test_the_outcome_is_read_back_after_a_restart(env, monkeypatch):
    bs._record_ok({"key": "backups/samatu-20261005T031500Z.db", "size": 12345,
                   "backend": "LocalDiskStorage"})
    monkeypatch.setattr(bs, "_last", bs._blank())         # a new process
    out = bs.last_outcome()
    assert out["last_key"] == "backups/samatu-20261005T031500Z.db"
    assert out["last_size"] == 12345 and out["last_ok_at"]
    assert out["last_attempt"]["ok"] is True
    assert out["last_attempt"]["key"] == out["last_key"]
    assert out["stale_after_hours"] == 26 and out["keep_newest"] == 7
    assert out["keep_days"] is None                        # retention off by default

    # A failure after the restart keeps the persisted good snapshot.
    bs._record_error(RuntimeError("R2 put failed"))
    monkeypatch.setattr(bs, "_last", bs._blank())
    out = bs.last_outcome()
    assert out["last_attempt"]["ok"] is False
    assert out["last_error"] == "RuntimeError: R2 put failed"
    assert out["last_key"] == "backups/samatu-20261005T031500Z.db"
    assert out["last_size"] == 12345


def test_an_unwritable_database_does_not_lose_the_outcome(env, monkeypatch):
    def boom(*_a, **_k):
        raise sqlite3.OperationalError("database is locked")
    monkeypatch.setattr(db, "set_state", boom)
    bs._record_ok({"key": "backups/samatu-20261005T031500Z.db", "size": 1,
                   "backend": "LocalDiskStorage"})
    assert bs.last_outcome()["last_key"] == "backups/samatu-20261005T031500Z.db"


def test_system_health_reports_the_persisted_outcome(env, monkeypatch):
    import auth
    from fastapi.testclient import TestClient
    from main import app

    monkeypatch.setattr(auth, "AUTH_DISABLED", True)       # dev user is admin
    bs._record_ok({"key": "backups/samatu-20261005T031500Z.db", "size": 777,
                   "backend": "LocalDiskStorage"})
    monkeypatch.setattr(bs, "_last", bs._blank())          # as after a deploy
    r = TestClient(app).get("/api/admin/v2/system-health")
    assert r.status_code == 200, r.text
    b = r.json()["backup"]
    assert b["last_key"] == "backups/samatu-20261005T031500Z.db"
    assert b["last_size"] == 777 and b["last_ok_at"]
    assert b["last_attempt"]["ok"] is True
    assert b["keep_days"] is None and b["keep_newest"] == 7
    assert b["stale_after_hours"] == 26
    assert b["last_prune"] is None


# ── retention ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("value", [None, "", "  "])
def test_retention_is_off_by_default_zero_deletes(env, monkeypatch, value):
    if value is not None:
        monkeypatch.setenv("SAMATU_BACKUP_KEEP_DAYS", value)
    keys = _seed_snapshots(env, range(0, 400, 20))        # 20 snapshots, most ancient
    spy = _spy(env)
    result = backup.prune_backups(now=NOW)
    assert result["enabled"] is False and result["deleted"] == []
    assert spy.deletes == [] and spy.listings == []       # not even listed
    assert _stored(env) == set(keys)


@pytest.mark.parametrize("value", ["abc", "0", "-3", "1.5", "7d"])
def test_an_unreadable_retention_prunes_nothing(env, monkeypatch, caplog, value):
    monkeypatch.setenv("SAMATU_BACKUP_KEEP_DAYS", value)
    keys = _seed_snapshots(env, range(0, 400, 20))
    spy = _spy(env)
    with caplog.at_level(logging.WARNING, logger="samatu.backup"):
        result = backup.prune_backups(now=NOW)
    assert result["enabled"] is False and spy.deletes == []
    assert _stored(env) == set(keys)
    assert any("SAMATU_BACKUP_KEEP_DAYS" in r.getMessage() for r in caplog.records)


def test_the_newest_seven_stay_even_when_all_are_old(env, monkeypatch):
    monkeypatch.setenv("SAMATU_BACKUP_KEEP_DAYS", "30")
    keys = _seed_snapshots(env, [100 + i for i in range(10)])   # all older than 30 d
    spy = _spy(env)
    result = backup.prune_backups(now=NOW)
    assert result["enabled"] is True and result["keep_days"] == 30
    assert sorted(result["deleted"]) == sorted(keys[7:])   # keys: newest first
    assert sorted(spy.deletes) == sorted(keys[7:])
    assert _stored(env) == set(keys[:7])
    assert result["kept"] == 7


def test_only_snapshots_older_than_n_days_beyond_the_newest_seven_go(env, monkeypatch):
    keys = _seed_snapshots(env, range(20))              # one a day, 0..19 days old
    spy = _spy(env)
    result = backup.prune_backups(10, now=NOW)
    gone = {backup.backup_key(_stamp(NOW - datetime.timedelta(days=a))) for a in range(11, 20)}
    assert set(spy.deletes) == gone                     # 11..19 days old
    assert _stored(env) == set(keys) - gone             # 0..10 days (10 = exactly N, kept)
    assert result["kept"] == 11


class _MemoryStore:
    """Case-sensitive key → bytes, like R2. (The local disk backend maps keys to
    files, and on a case-insensitive disk `X.DB` and `X.db.tmp` collide.)"""

    def __init__(self):
        self.objects: dict[str, bytes] = {}

    def put(self, key, data, content_type="application/pdf"):
        self.objects[key] = data

    def get(self, key):
        return self.objects.get(key)

    def delete(self, key):
        self.objects.pop(key, None)

    def list_keys(self, prefix=""):
        for key in sorted(self.objects):
            if key.startswith(prefix):
                yield key, len(self.objects[key])


def test_keys_outside_the_exact_backup_name_are_never_touched():
    ancient = "20200101T000000Z"
    decoys = [
        f"backups/samatu-{ancient}.db.tmp",            # a half-written local upload
        f"backups/samatu-{ancient}.db.bak",
        f"backups/old/samatu-{ancient}.db",            # a sub-folder
        "backups/samatu-20200101T000000.db",           # no Z
        "backups/samatu-2020-01-01.db",
        "backups/samatu-20201301T000000Z.db",          # month 13
        "backups/samatu-20200230T000000Z.db",          # 30 February
        f"backups/Samatu-{ancient}.db",
        f"backups/samatu-{ancient}.DB",
        f" backups/samatu-{ancient}.db",
        "backups/samatu-٢٠٢٠٠١٠١T000000Z.db",          # digits, but not ASCII ones
        "backups/manual-before-migration.db",
        f"projects/samatu-{ancient}.db",
        "projects/proj-1.pdf",
        "invoices/inv-1.pdf",
    ]
    store = _MemoryStore()
    for key in decoys:
        store.put(key, b"keep me " + key.encode())
    snapshots = _seed_snapshots(store, [500 + i for i in range(9)])   # 9 ancient ones
    spy = _Spy(store)
    result = backup.prune_backups(1, backend=spy, now=NOW)
    two_oldest = set(snapshots[-2:])                     # snapshots: newest first
    assert set(spy.deletes) == two_oldest == set(result["deleted"])
    for key in decoys:
        assert store.get(key) == b"keep me " + key.encode(), key
    assert set(store.objects) == set(decoys) | set(snapshots[:7])
    assert result["ignored"] == len([k for k in decoys if k.startswith("backups/")])


def test_retention_plan_is_pure_and_refuses_a_bad_number():
    keys = [backup.backup_key(_stamp(NOW - datetime.timedelta(days=d))) for d in (40, 0, 20)]
    plan = backup.retention_plan(keys + ["backups/other.db"], 30, now=NOW)
    assert plan["keep"] == [keys[1], keys[2], keys[0]]   # newest first, 7 always kept
    assert plan["delete"] == [] and plan["ignored"] == ["backups/other.db"]
    assert plan["cutoff"] == (NOW - datetime.timedelta(days=30)).isoformat()
    for bad in (0, -1, None, True, "30", 1.5):
        with pytest.raises(ValueError):
            backup.retention_plan(keys, bad, now=NOW)


# ── the scheduler: prune only after a stored snapshot ────────────────────────

def _run_one_night(monkeypatch):
    """Run _run_forever for exactly one night, then cancel it while it waits
    for the next one."""
    waits = []

    def seconds_until(_h, _m):
        waits.append(1)
        return 0.0 if len(waits) == 1 else 3600.0
    monkeypatch.setattr(bs, "_seconds_until", seconds_until)

    async def go():
        task = asyncio.create_task(bs._run_forever())
        for _ in range(1000):
            await asyncio.sleep(0.01)
            if len(waits) >= 2:           # the night is over: it waits for the next
                break
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        assert len(waits) >= 2, "the night never finished"
    asyncio.run(go())


def test_a_good_night_with_retention_unset_deletes_nothing(env, monkeypatch):
    old = _seed_snapshots(env, [100 + i for i in range(10)])
    spy = _spy(env)
    _run_one_night(monkeypatch)
    assert len(spy.puts) == 1                           # tonight's snapshot is stored
    assert spy.deletes == []
    assert _stored(env) == set(old) | set(spy.puts)
    out = bs.last_outcome()
    assert out["last_attempt"]["ok"] is True and out["last_prune"] is None


def test_a_good_night_with_retention_set_prunes_and_records_it(env, monkeypatch):
    monkeypatch.setenv("SAMATU_BACKUP_KEEP_DAYS", "30")
    old = _seed_snapshots(env, [100 + i for i in range(10)])
    spy = _spy(env)
    _run_one_night(monkeypatch)
    # Tonight's snapshot is the newest; with it, the 6 newest old ones stay.
    assert sorted(spy.deletes) == sorted(old[6:])
    prune = bs.last_outcome()["last_prune"]
    assert prune["deleted"] == 4 and prune["kept"] == 7 and prune["keep_days"] == 30
    assert prune["error"] is None


def test_a_failed_night_never_prunes(env, monkeypatch):
    monkeypatch.setenv("SAMATU_BACKUP_KEEP_DAYS", "1")
    old = _seed_snapshots(env, [100 + i for i in range(10)])
    spy = _spy(env)

    def boom(*_a, **_k):
        raise RuntimeError("disk full")
    monkeypatch.setattr(backup, "backup_db", boom)
    _run_one_night(monkeypatch)
    assert spy.deletes == [] and spy.listings == []
    assert _stored(env) == set(old)
    assert bs.last_outcome()["last_attempt"]["ok"] is False


def test_a_failed_prune_leaves_the_backup_ok(env, monkeypatch, caplog):
    monkeypatch.setenv("SAMATU_BACKUP_KEEP_DAYS", "30")

    def boom(*_a, **_k):
        raise storage.StorageError("listing failed")
    monkeypatch.setattr(backup, "prune_backups", boom)
    with caplog.at_level(logging.ERROR, logger="samatu.backup"):
        _run_one_night(monkeypatch)
    out = bs.last_outcome()
    assert out["last_attempt"]["ok"] is True and out["last_error"] is None
    assert "listing failed" in out["last_prune"]["error"]
    assert any("prune FAILED" in r.getMessage() for r in caplog.records)
