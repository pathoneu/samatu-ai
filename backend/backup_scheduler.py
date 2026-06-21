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
            log.info("nightly backup ok: %s (%s bytes, %s)",
                     res["key"], res["size"], res["backend"])
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 — one bad night must not kill the schedule
            log.exception("nightly backup failed; retrying tomorrow")


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
