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

2026-10-05 (audit data-ops-infra-9):
  · the last outcome — time, ok/failed, key, size, error — is persisted in
    app_state (`backup_last_outcome`). It used to live only in this process, so
    every deploy blanked it and the cockpit could not tell "last good backup
    30 hours ago" from "not run since the restart";
  · after a night whose snapshot was stored — and only then — old snapshots
    are pruned when SAMATU_BACKUP_KEEP_DAYS is set (backup.prune_backups). It is
    unset by default, and then nothing is ever deleted.
"""
from __future__ import annotations

import asyncio
import datetime
import json
import logging
import os

import backup
import db

log = logging.getLogger("samatu.backup")

_task: "asyncio.Task | None" = None

# The admin health panel turns red when the last good snapshot is older than
# this: a nightly job that missed one night by a little is still green.
STALE_AFTER_HOURS = 26

_STATE_KEY = "backup_last_outcome"


def _blank() -> dict:
    return {"last_ok_at": None, "last_key": None, "last_size": None,
            "last_error": None, "last_error_at": None,
            "last_attempt": None, "last_prune": None}


# 2026-07-27 audit (finding 7): a failing nightly backup logged an exception into
# stdout and nothing else — nobody would notice until a restore was needed. The
# last outcome is surfaced by /api/admin/v2/system-health; this is the copy held
# by the running process, app_state holds the one that survives a restart.
_last: dict = _blank()


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _persisted() -> dict:
    """The outcome app_state holds, or {} when there is none or it is unreadable."""
    try:
        raw = db.get_state(_STATE_KEY)
        data = json.loads(raw) if raw else {}
    except Exception:  # noqa: BLE001 — unreadable → the in-process copy answers
        return {}
    return data if isinstance(data, dict) else {}


def _attempt_at(outcome: dict) -> str:
    attempt = outcome.get("last_attempt")
    return (attempt.get("at") or "") if isinstance(attempt, dict) else ""


def _current() -> dict:
    """The newest known outcome: app_state's, or this process's when that is
    newer (a write to app_state that failed)."""
    stored, here = _persisted(), dict(_last)
    best = stored if _attempt_at(stored) > _attempt_at(here) else here
    blank = _blank()
    return {**blank, **{k: v for k, v in best.items() if k in blank}}


def _save(state: dict) -> None:
    """Hold `state` in this process and persist it. Never raises: a database
    that cannot be written must not cost the schedule. The dict is swapped in
    whole (it is written from a worker thread): a reader sees the old outcome
    or the new one, never a half-cleared one."""
    global _last
    _last = state
    try:
        db.set_state(_STATE_KEY, json.dumps(state, ensure_ascii=False))
    except Exception as exc:  # noqa: BLE001
        log.warning("backup outcome not persisted: %r", exc)


def last_outcome() -> dict:
    """The most recent backup attempt and the last good one, plus whether the
    schedule is on, the retention setting and the staleness threshold."""
    return {**_current(), "enabled": is_enabled(),
            "keep_days": backup.backup_keep_days(warn=False),
            "keep_newest": backup.KEEP_NEWEST,
            "stale_after_hours": STALE_AFTER_HOURS}


def _record_ok(res: dict) -> None:
    now = _now_iso()
    state = _current()
    state.update(last_ok_at=now, last_key=res.get("key"), last_size=res.get("size"),
                 last_error=None, last_error_at=None,
                 last_attempt={"at": now, "ok": True, "key": res.get("key"),
                               "size": res.get("size"), "error": None})
    _save(state)


def _record_error(exc: BaseException) -> None:
    now = _now_iso()
    message = f"{type(exc).__name__}: {exc}"[:300]
    state = _current()
    # The last good snapshot (last_ok_at / last_key / last_size) is kept: it is
    # what a restore would use, and what the cockpit measures staleness from.
    state.update(last_error=message, last_error_at=now,
                 last_attempt={"at": now, "ok": False,
                               "key": getattr(exc, "key", None),
                               "size": getattr(exc, "size", None),
                               "error": message})
    _save(state)


def _record_prune(result: dict) -> None:
    if not result.get("enabled"):
        return   # retention is off: nothing ran, nothing to report
    state = _current()
    state["last_prune"] = {"at": _now_iso(), "keep_days": result.get("keep_days"),
                           "deleted": len(result.get("deleted") or []),
                           "kept": result.get("kept"), "error": None}
    _save(state)


def _record_prune_error(exc: BaseException) -> None:
    state = _current()
    state["last_prune"] = {"at": _now_iso(),
                           "keep_days": backup.backup_keep_days(warn=False),
                           "deleted": 0, "kept": None,
                           "error": f"{type(exc).__name__}: {exc}"[:300]}
    _save(state)


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


async def _prune_after_success() -> None:
    """Thin out old snapshots — called only after a night whose own snapshot
    was stored. A prune failure is reported on its own; the backup stays ok."""
    try:
        result = await asyncio.to_thread(backup.prune_backups)
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # noqa: BLE001
        await asyncio.to_thread(_record_prune_error, exc)
        log.error("backup prune FAILED (tonight's snapshot itself is stored): %s",
                  exc, exc_info=True)
        return
    await asyncio.to_thread(_record_prune, result)


async def _run_forever() -> None:
    hour = int(os.environ.get("SAMATU_BACKUP_HOUR_UTC", "3"))
    minute = int(os.environ.get("SAMATU_BACKUP_MINUTE_UTC", "15"))
    while True:
        try:
            await asyncio.sleep(_seconds_until(hour, minute))
            # backup_db() blocks (sqlite VACUUM + integrity check + network put)
            # — keep the loop free. So does the outcome's write to app_state.
            res = await asyncio.to_thread(backup.backup_db)
            await asyncio.to_thread(_record_ok, res)
            log.info("nightly backup ok: %s (%s bytes, %s)",
                     res["key"], res["size"], res["backend"])
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 — one bad night must not kill the schedule
            await asyncio.to_thread(_record_error, exc)
            log.error("nightly backup FAILED; retrying tomorrow: %s", exc, exc_info=True)
            continue
        await _prune_after_success()


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
