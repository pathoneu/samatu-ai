"""Nightly in-process DB backup scheduler (2026-06-21 durability track).

`backup.backup_db()` is dead code unless something calls it. On Render the SQLite
file lives on THIS web service's disk, so a *separate* cron service can't read it —
the backup must run inside this process. This schedules a daily call on the running
event loop.

Gated OFF by default so dev + the test suite don't spew snapshots. It turns on when
either:
  - SAMATU_NIGHTLY_BACKUP is truthy (explicit), or
  - R2 is configured (R2_BUCKET set) — i.e. prod — so it's automatic once deployed.

render.yaml runs a single uvicorn worker → exactly one scheduler. Scaling to N
workers would produce N same-timestamp snapshots a day (harmless, just redundant).
"""
from __future__ import annotations

import asyncio
import datetime
import logging
import os

import backup

log = logging.getLogger("samatu.backup")

_task: "asyncio.Task | None" = None

# 2026-07-27 audit (finding 7): a failing nightly backup logged an exception into
# stdout and nothing else — nobody would notice until a restore was needed. The
# last outcome is now held in-process and surfaced by /api/admin/v2/system-health.
# In-process only (resets on restart) — that is enough to answer "did last night's
# backup run?" without adding a table.
_last: dict = {"last_ok_at": None, "last_error": None, "last_error_at": None,
               "last_key": None}


def last_outcome() -> dict:
    """Snapshot of the most recent backup attempt (see _last)."""
    return {**_last, "enabled": is_enabled()}


def _record_ok(res: dict) -> None:
    _last["last_ok_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    _last["last_key"] = res.get("key")
    _last["last_error"] = None
    _last["last_error_at"] = None


def _record_error(exc: BaseException) -> None:
    _last["last_error"] = f"{type(exc).__name__}: {exc}"[:300]
    _last["last_error_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()


def is_enabled() -> bool:
    flag = os.environ.get("SAMATU_NIGHTLY_BACKUP")
    if flag is not None:
        return flag.strip().lower() in ("1", "true", "yes", "on")
    return bool(os.environ.get("R2_BUCKET"))  # default-on in prod


def _seconds_until(hour: int, minute: int) -> float:
    """Seconds from now until the next HH:MM UTC (always in (0, 86400])."""
    now = datetime.datetime.now(datetime.timezone.utc)
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += datetime.timedelta(days=1)
    return (target - now).total_seconds()


async def _run_forever() -> None:
    hour = int(os.environ.get("SAMATU_BACKUP_HOUR_UTC", "3"))
    minute = int(os.environ.get("SAMATU_BACKUP_MINUTE_UTC", "15"))
    while True:
        try:
            await asyncio.sleep(_seconds_until(hour, minute))
            # backup_db() blocks (sqlite VACUUM + network put) — keep the loop free.
            res = await asyncio.to_thread(backup.backup_db)
            _record_ok(res)
            log.info("nightly backup ok: %s (%s bytes, %s)",
                     res["key"], res["size"], res["backend"])
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 — one bad night must not kill the schedule
            _record_error(exc)
            log.error("nightly backup FAILED; retrying tomorrow: %s", exc, exc_info=True)


def start() -> bool:
    """Launch the daily task if enabled and not already running. Returns started?"""
    global _task
    if not is_enabled() or _task is not None:
        return False
    _task = asyncio.create_task(_run_forever())
    log.info("nightly DB backup scheduled (daily %s:%s UTC)",
             os.environ.get("SAMATU_BACKUP_HOUR_UTC", "3"),
             os.environ.get("SAMATU_BACKUP_MINUTE_UTC", "15"))
    return True


async def stop() -> None:
    global _task
    if _task is None:
        return
    _task.cancel()
    try:
        await _task
    except asyncio.CancelledError:
        pass
    _task = None
