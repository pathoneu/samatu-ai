"""scripts/backup_db.py — a manual backup records its outcome the way the
nightly job does, and never prunes (2026-10-05).

The nightly job (backup_scheduler) keeps its last outcome in app_state, and the
admin backup panel reads it from there. The manual script stored a snapshot
but recorded nothing, so after a hand-made backup the panel still showed the
last NIGHT — red when that one was stale or had failed. Now the script writes
the same record (good → green, failed → its error, the last good snapshot
kept), and it still never deletes an old snapshot, even with
SAMATU_BACKUP_KEEP_DAYS set.

Temp database, local storage in a temp dir — never R2, never backend/data.
"""
from __future__ import annotations

import datetime
import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

import backup
import backup_scheduler as bs
import db
import storage

BACKEND = Path(__file__).resolve().parents[1]
SCRIPT = BACKEND / "scripts" / "backup_db.py"
UTC = datetime.timezone.utc
_R2_AND_BACKUP_ENV = ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY",
                      "R2_BUCKET", "R2_KEY_PREFIX", "SAMATU_BACKUP_KEEP_DAYS",
                      "SAMATU_NIGHTLY_BACKUP", "STORAGE_BACKEND", "LOCAL_STORAGE_DIR",
                      "SAMATU_DB_PATH", "ENV", "ENVIRONMENT", "RAILWAY_ENVIRONMENT",
                      "RENDER")


def _load_script():
    spec = importlib.util.spec_from_file_location("backup_db_script", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "live.db")
    db.init_schema()
    db._migrate_schema()
    db.create_user("u@x.lt", "h", name="U")                # something to snapshot
    for k in _R2_AND_BACKUP_ENV:
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
    """Wraps the backend: records puts/deletes/listings, then does them."""

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
    spy = _Spy(backend)
    storage._instance = spy            # the env fixture's teardown resets it
    return spy


def _ancient_snapshots(backend, n=10) -> set[str]:
    keys = set()
    for i in range(n):
        taken = datetime.datetime(2025, 1, 1, 3, 15, tzinfo=UTC) + datetime.timedelta(days=i)
        key = backup.backup_key(taken.strftime("%Y%m%dT%H%M%SZ"))
        backend.put(key, b"SQLite format 3\x00old")
        keys.add(key)
    return keys


def _stored(backend) -> set[str]:
    return {k for k, _ in backend.list_keys("backups/")}


def _panel_is_green(b: dict, now: datetime.datetime) -> bool:
    """The admin panel's verdict (frontend lib/adminStatus.js backupStatus):
    the backup is on, the last good snapshot is under stale_after_hours old,
    and the latest attempt did not fail."""
    if not b.get("enabled") or not b.get("last_ok_at"):
        return False
    age = now - datetime.datetime.fromisoformat(b["last_ok_at"])
    attempt = b.get("last_attempt") or {}
    return age <= datetime.timedelta(hours=b["stale_after_hours"]) and attempt.get("ok") is True


def _system_health_backup(monkeypatch) -> dict:
    import auth
    from fastapi.testclient import TestClient
    from main import app

    monkeypatch.setattr(auth, "AUTH_DISABLED", True)       # the dev user is admin
    monkeypatch.setattr(bs, "_last", bs._blank())          # read it as the web app would
    r = TestClient(app).get("/api/admin/v2/system-health")
    assert r.status_code == 200, r.text
    return r.json()["backup"]


# ── a good manual run ────────────────────────────────────────────────────────

def test_a_manual_run_records_its_outcome_and_turns_the_panel_green(env, monkeypatch, capsys):
    monkeypatch.setenv("SAMATU_NIGHTLY_BACKUP", "1")        # as in production
    long_ago = (datetime.datetime.now(UTC) - datetime.timedelta(days=3)).isoformat()
    yesterday = (datetime.datetime.now(UTC) - datetime.timedelta(hours=20)).isoformat()
    db.set_state("backup_last_outcome", json.dumps({
        "last_ok_at": long_ago, "last_key": "backups/samatu-20261002T031500Z.db",
        "last_size": 10, "last_error": "RuntimeError: R2 put failed",
        "last_error_at": yesterday,
        "last_attempt": {"at": yesterday, "ok": False, "key": None, "size": None,
                         "error": "RuntimeError: R2 put failed"},
        "last_prune": None}))
    assert not _panel_is_green(_system_health_backup(monkeypatch), datetime.datetime.now(UTC))

    spy = _spy(env)
    assert _load_script().main() == 0
    assert len(spy.puts) == 1 and spy.puts[0].startswith("backups/samatu-")
    out = capsys.readouterr().out
    assert f"DB backup uploaded → {spy.puts[0]}" in out

    stored = json.loads(db.get_state("backup_last_outcome"))
    assert stored["last_key"] == spy.puts[0]
    assert stored["last_size"] == len(env.get(spy.puts[0]))
    assert stored["last_attempt"]["ok"] is True and stored["last_attempt"]["key"] == spy.puts[0]
    assert stored["last_error"] is None and stored["last_error_at"] is None

    b = _system_health_backup(monkeypatch)
    assert b["last_key"] == spy.puts[0] and b["last_attempt"]["ok"] is True
    assert _panel_is_green(b, datetime.datetime.now(UTC))


def test_a_manual_run_never_prunes_even_with_retention_set(env, monkeypatch):
    monkeypatch.setenv("SAMATU_BACKUP_KEEP_DAYS", "1")
    old = _ancient_snapshots(env)
    spy = _spy(env)
    prunes = []
    monkeypatch.setattr(backup, "prune_backups", lambda *a, **k: prunes.append(1) or {})
    assert _load_script().main() == 0
    assert prunes == [] and spy.deletes == [] and spy.listings == []
    assert _stored(env) == old | set(spy.puts)
    assert bs.last_outcome()["last_prune"] is None


# ── a failed manual run ──────────────────────────────────────────────────────

def _corrupting_snapshot(real):
    def snap(dest):
        real(dest)
        raw = bytearray(dest.read_bytes())
        page = int.from_bytes(raw[16:18], "big") or 65536
        raw[page:page + 64] = b"\xff" * 64           # wreck page 2's b-tree header
        dest.write_bytes(bytes(raw))
    return snap


def test_a_failed_manual_run_is_recorded_and_keeps_the_last_good_one(env, monkeypatch, capsys):
    with db._conn() as c:                                   # a few pages to wreck
        c.execute("CREATE TABLE IF NOT EXISTS filler (v TEXT)")
        c.executemany("INSERT INTO filler (v) VALUES (?)", [("x" * 400,)] * 200)
    script = _load_script()
    assert script.main() == 0
    good = bs.last_outcome()

    spy = _spy(env)
    monkeypatch.setattr(backup, "_snapshot", _corrupting_snapshot(backup._snapshot))
    monkeypatch.setattr(bs, "_last", bs._blank())          # a fresh process
    assert script.main() == 1
    assert spy.puts == []                                   # nothing uploaded
    err = capsys.readouterr().err
    assert "DB backup FAILED" in err and "integrity_check" in err

    out = bs.last_outcome()
    assert out["last_attempt"]["ok"] is False and "integrity_check" in out["last_attempt"]["error"]
    assert out["last_error"] == out["last_attempt"]["error"]
    assert (out["last_ok_at"], out["last_key"], out["last_size"]) == (
        good["last_ok_at"], good["last_key"], good["last_size"])
    assert json.loads(db.get_state("backup_last_outcome"))["last_attempt"]["ok"] is False


# ── the script as it is really run ───────────────────────────────────────────

def test_running_the_script_as_a_program(tmp_path, monkeypatch):
    """A real `python scripts/backup_db.py` in its own process, on a temp
    database and temp-dir storage (no R2: STORAGE_BACKEND=local and no R2_*)."""
    live = tmp_path / "prog.db"
    monkeypatch.setattr(db, "_DB_PATH", live)               # build it with the real schema
    db.init_schema()
    db._migrate_schema()
    db.create_user("kopija@x.lt", "h", name="Kopija")
    store = tmp_path / "prog_store"
    old = store / "backups" / "samatu-20250101T031500Z.db"
    old.parent.mkdir(parents=True)
    old.write_bytes(b"SQLite format 3\x00old")
    child_env = {k: v for k, v in os.environ.items() if k not in _R2_AND_BACKUP_ENV}
    child_env.update(SAMATU_DB_PATH=str(live), STORAGE_BACKEND="local",
                     LOCAL_STORAGE_DIR=str(store), SAMATU_BACKUP_KEEP_DAYS="1")
    done = subprocess.run([sys.executable, str(SCRIPT)], cwd=str(BACKEND), env=child_env,
                          capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stderr
    assert "DB backup uploaded → backups/samatu-" in done.stdout

    snaps = sorted(p.name for p in (store / "backups").iterdir())
    assert len(snaps) == 2 and old.name in snaps            # the old one is still there
    new = next(store / "backups" / n for n in snaps if n != old.name)
    copy = sqlite3.connect(new)
    assert copy.execute("SELECT email FROM users").fetchall() == [("kopija@x.lt",)]
    copy.close()

    conn = sqlite3.connect(live)
    (value,) = conn.execute(
        "SELECT value FROM app_state WHERE key = 'backup_last_outcome'").fetchone()
    conn.close()
    outcome = json.loads(value)
    assert outcome["last_attempt"]["ok"] is True
    assert outcome["last_key"] == f"backups/{new.name}"
    assert outcome["last_size"] == new.stat().st_size
