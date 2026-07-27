"""2026-07-27 audit finding 7 — durability must be observable.

Three silent failure modes, all of which looked healthy from outside:
  (a) one missing R2_* var → get_storage() fell back to ephemeral local disk
      without a word, so "uploaded" PDFs died with the container;
  (b) a nightly backup that had been failing for a week left only a stack trace
      in stdout — nothing to query;
  (c) /api/admin/v2/system-health, the operator cockpit, reported neither.
"""
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import storage  # noqa: E402


def _no_r2(monkeypatch):
    for k in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY",
              "R2_BUCKET", "LOCAL_STORAGE_DIR", "SAMATU_DATA_DIR"):
        monkeypatch.delenv(k, raising=False)


# ── (a) storage selection is logged ─────────────────────────────────────────

def test_local_fallback_warns_and_names_missing_vars(tmp_path, monkeypatch, caplog):
    _no_r2(monkeypatch)
    monkeypatch.delenv("ENV", raising=False)
    monkeypatch.setenv("LOCAL_STORAGE_DIR", str(tmp_path / "pdfs"))
    storage.reset_storage_for_test()
    with caplog.at_level(logging.INFO, logger="samatu.storage"):
        assert storage.get_storage().name == "LocalDiskStorage"
    rec = [r for r in caplog.records if r.name == "samatu.storage"]
    assert rec and rec[-1].levelno == logging.WARNING, [r.getMessage() for r in rec]
    msg = rec[-1].getMessage()
    assert "R2_BUCKET" in msg and "LOCAL DISK" in msg
    storage.reset_storage_for_test()


def test_local_fallback_in_production_is_an_error(tmp_path, monkeypatch, caplog):
    _no_r2(monkeypatch)
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("LOCAL_STORAGE_DIR", str(tmp_path / "pdfs"))
    storage.reset_storage_for_test()
    with caplog.at_level(logging.INFO, logger="samatu.storage"):
        storage.get_storage()
    rec = [r for r in caplog.records if r.name == "samatu.storage"]
    assert rec and rec[-1].levelno == logging.ERROR, [r.getMessage() for r in rec]
    assert "NOT durable" in rec[-1].getMessage()
    storage.reset_storage_for_test()
    monkeypatch.delenv("ENV", raising=False)


def test_r2_selection_is_logged_at_info(monkeypatch, caplog):
    for k, v in (("R2_ACCOUNT_ID", "acct"), ("R2_ACCESS_KEY_ID", "ak"),
                 ("R2_SECRET_ACCESS_KEY", "sk"), ("R2_BUCKET", "samatu-pdfs")):
        monkeypatch.setenv(k, v)
    storage.reset_storage_for_test()
    with caplog.at_level(logging.INFO, logger="samatu.storage"):
        assert storage.get_storage().name == "R2Storage"
    rec = [r for r in caplog.records if r.name == "samatu.storage"]
    assert rec and rec[-1].levelno == logging.INFO
    assert "samatu-pdfs" in rec[-1].getMessage()
    storage.reset_storage_for_test()


def test_selected_backend_name_matches_selection(monkeypatch):
    _no_r2(monkeypatch)
    assert storage.selected_backend_name() == "local"
    for k, v in (("R2_ACCOUNT_ID", "a"), ("R2_ACCESS_KEY_ID", "b"),
                 ("R2_SECRET_ACCESS_KEY", "c"), ("R2_BUCKET", "d")):
        monkeypatch.setenv(k, v)
    assert storage.selected_backend_name() == "r2"
    monkeypatch.delenv("R2_BUCKET")           # one missing var → local, silently before
    assert storage.selected_backend_name() == "local"


# ── (b) the scheduler remembers its last outcome ────────────────────────────

def test_backup_failure_is_recorded_and_logged(monkeypatch, caplog):
    import backup_scheduler as bs
    import backup

    monkeypatch.setattr(bs, "_last", {"last_ok_at": None, "last_error": None,
                                      "last_error_at": None, "last_key": None})
    monkeypatch.setattr(bs, "_seconds_until", lambda h, m: 0.0)

    def _boom():
        raise RuntimeError("R2 put failed")
    monkeypatch.setattr(backup, "backup_db", _boom)

    async def go():
        task = asyncio.create_task(bs._run_forever())
        for _ in range(50):                       # let one cycle run, then stop
            await asyncio.sleep(0)
            if bs._last["last_error"]:
                break
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    with caplog.at_level(logging.ERROR, logger="samatu.backup"):
        asyncio.run(go())

    assert "RuntimeError: R2 put failed" in (bs._last["last_error"] or "")
    assert bs._last["last_error_at"]
    assert any(r.levelno == logging.ERROR for r in caplog.records
               if r.name == "samatu.backup")


def test_backup_success_is_recorded(monkeypatch):
    import backup_scheduler as bs
    monkeypatch.setattr(bs, "_last", {"last_ok_at": None, "last_error": None,
                                      "last_error_at": None, "last_key": None})
    bs._record_error(RuntimeError("older failure"))
    bs._record_ok({"key": "backups/samatu-20260727T031500Z.db", "size": 1, "backend": "R2"})
    out = bs.last_outcome()
    assert out["last_ok_at"] and out["last_key"].endswith(".db")
    assert out["last_error"] is None              # a good night clears the alarm
    assert "enabled" in out


# ── (c) the cockpit reports both ────────────────────────────────────────────

def test_system_health_reports_storage_and_backup(tmp_path, monkeypatch):
    import auth
    import db
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "health.db")
    db.init_schema()
    db._migrate_schema()
    monkeypatch.setattr(auth, "AUTH_DISABLED", True)   # dev user is admin
    _no_r2(monkeypatch)

    from fastapi.testclient import TestClient
    from main import app
    r = TestClient(app).get("/api/admin/v2/system-health")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["storage_backend"] in ("r2", "local")
    assert body["storage_backend"] == "local"          # no R2 vars in this env
    backup = body["backup"]
    assert set(backup) >= {"enabled", "last_ok_at", "last_error"}
    assert backup["enabled"] is False                  # no R2 / no flag in tests
