"""Database backup to durable object storage (2026-06-21 durability track).

The audit flagged "one disk failure on Render wipes every customer's projects" as
an unacceptable risk before charging money. This takes a CONSISTENT SQLite snapshot
(``VACUUM INTO``, safe under concurrent WAL readers) and uploads it to the same
object store the PDFs use — R2 in prod, local disk in dev. Point a nightly cron at
``scripts/backup_db.py``.

2026-10-05 (audit data-ops-infra-9):
  · the snapshot is checked with ``PRAGMA integrity_check`` before it leaves the
    machine; one that fails is never uploaded (BackupError says why);
  · old snapshots can be pruned (`prune_backups`), but ONLY when
    SAMATU_BACKUP_KEEP_DAYS says how many days to keep. Unset or empty — the
    default, because the retention is the founder's decision — nothing is ever
    deleted. The newest KEEP_NEWEST snapshots are kept whatever their age, and
    only keys with the exact name `backup_db` writes are ever considered.
    `scripts/report_backup_retention.py` shows what a given N would delete.
"""
from __future__ import annotations

import datetime
import logging
import os
import pathlib
import re
import sqlite3
import tempfile

import db
from storage import get_storage

log = logging.getLogger("samatu.backup")

BACKUP_PREFIX = "backups/"
_STAMP_FORMAT = "%Y%m%dT%H%M%SZ"
# The one name backup_db() writes: backups/samatu-20261005T031500Z.db. Retention
# considers nothing else — not a ".tmp" leftover, not a file in a sub-folder,
# not a hand-made copy under another name.
_BACKUP_KEY = re.compile(r"backups/samatu-([0-9]{8}T[0-9]{6}Z)\.db")
# However old they are, this many newest snapshots are never pruned.
KEEP_NEWEST = 7


class BackupError(Exception):
    """A night that produced no trustworthy stored snapshot. Carries the key
    and the snapshot's size when they are known, for the recorded outcome."""

    def __init__(self, message: str, *, key: str | None = None,
                 size: int | None = None):
        super().__init__(message)
        self.key = key
        self.size = size


def _utc_stamp() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime(_STAMP_FORMAT)


def backup_key(stamp: str) -> str:
    return f"{BACKUP_PREFIX}samatu-{stamp}.db"


def _snapshot(dest: pathlib.Path) -> None:
    # Fresh connection in autocommit mode — VACUUM INTO can't run inside a
    # transaction, and a fresh handle avoids the app's pooled connection lock.
    conn = sqlite3.connect(str(db._DB_PATH))
    try:
        conn.execute("VACUUM INTO ?", (str(dest),))
    finally:
        conn.close()


def _integrity_problem(path: pathlib.Path) -> str | None:
    """None when `PRAGMA integrity_check` answers "ok"; otherwise what it
    reported, or why the file could not be read as a database at all. Opened
    read-only: the check must not change the bytes it vouches for."""
    uri = pathlib.Path(path).resolve().as_uri() + "?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True)
        try:
            rows = conn.execute("PRAGMA integrity_check").fetchall()
        finally:
            conn.close()
    except sqlite3.DatabaseError as exc:
        return f"{type(exc).__name__}: {exc}"
    if rows == [("ok",)]:
        return None
    return " | ".join(str(r[0]) for r in rows) or "no answer"


def backup_db(stamp: str | None = None) -> dict:
    """Snapshot the live DB, check it, upload it. Returns {key, size, backend}.

    Raises BackupError — and uploads nothing — when the snapshot fails its
    integrity check; any other failure (the snapshot itself, the upload)
    propagates as it is."""
    stamp = stamp or _utc_stamp()
    key = backup_key(stamp)
    with tempfile.TemporaryDirectory() as td:
        snap = pathlib.Path(td) / "snapshot.db"
        _snapshot(snap)
        problem = _integrity_problem(snap)
        if problem is not None:
            size = snap.stat().st_size if snap.exists() else None
            raise BackupError(
                "snapshot failed PRAGMA integrity_check and was NOT uploaded: "
                + problem[:300], key=key, size=size)
        data = snap.read_bytes()
    backend = get_storage()
    backend.put(key, data, content_type="application/x-sqlite3")
    return {"key": key, "size": len(data), "backend": backend.name}


# ── retention ────────────────────────────────────────────────────────────────

def parse_keep_days(raw: str | None) -> int | None:
    """A SAMATU_BACKUP_KEEP_DAYS value as whole days ≥ 1, or None = no pruning.
    Empty means "not chosen"; anything that is not a positive whole number is
    never guessed at either — it also means no pruning."""
    text = (raw or "").strip()
    if not text:
        return None
    try:
        days = int(text)
    except ValueError:
        return None
    return days if days >= 1 else None


def backup_keep_days(*, warn: bool = True) -> int | None:
    """The configured retention in days, or None when pruning is OFF."""
    raw = os.environ.get("SAMATU_BACKUP_KEEP_DAYS")
    days = parse_keep_days(raw)
    if days is None and (raw or "").strip() and warn:
        log.warning("SAMATU_BACKUP_KEEP_DAYS=%r is not a whole number of days >= 1 "
                    "— no backup is pruned", raw)
    return days


def snapshot_time(key: str) -> datetime.datetime | None:
    """When the snapshot under `key` was taken, read from its name — or None
    when the key is not exactly a name backup_db() writes."""
    m = _BACKUP_KEY.fullmatch(key) if isinstance(key, str) else None
    if m is None:
        return None
    try:
        taken = datetime.datetime.strptime(m.group(1), _STAMP_FORMAT)
    except ValueError:
        return None   # e.g. month 13 — not a name backup_db() ever wrote
    if taken.strftime(_STAMP_FORMAT) != m.group(1):
        return None
    return taken.replace(tzinfo=datetime.timezone.utc)


def retention_plan(keys, keep_days: int, now: datetime.datetime | None = None) -> dict:
    """What a prune keeping `keep_days` days would do to `keys`. Pure — no
    storage access; the prune and the read-only report both use it.

    Only exact backup names take part; every other key is listed under
    "ignored" and is never deleted. Of the snapshots, the newest KEEP_NEWEST
    are kept whatever their age; the rest are deleted when taken more than
    `keep_days` days before `now`. Returns {"delete", "keep", "ignored",
    "cutoff"} — delete and keep newest first."""
    if isinstance(keep_days, bool) or not isinstance(keep_days, int) or keep_days < 1:
        raise ValueError("keep_days must be a whole number of days >= 1")
    now = now or datetime.datetime.now(datetime.timezone.utc)
    cutoff = now - datetime.timedelta(days=keep_days)
    snapshots, ignored = [], []
    for key in keys:
        taken = snapshot_time(key)
        if taken is None:
            ignored.append(key)
        else:
            snapshots.append((taken, key))
    snapshots.sort(reverse=True)
    keep, delete = [], []
    for rank, (taken, key) in enumerate(snapshots):
        if rank < KEEP_NEWEST or taken >= cutoff:
            keep.append(key)
        else:
            delete.append(key)
    return {"delete": delete, "keep": keep, "ignored": sorted(ignored),
            "cutoff": cutoff.isoformat()}


def prune_backups(keep_days: int | None = None, *, backend=None,
                  now: datetime.datetime | None = None) -> dict:
    """Delete the snapshots retention_plan() marks — nothing else, ever.

    `keep_days` None reads SAMATU_BACKUP_KEEP_DAYS; still None → OFF: returns
    at once, without listing or deleting anything. Meant to run only after a
    night whose own snapshot was stored (backup_scheduler). Returns
    {"enabled", "keep_days", "deleted": [keys], "kept": n, "ignored": n}."""
    if keep_days is None:
        keep_days = backup_keep_days()
    if keep_days is None:
        return {"enabled": False, "keep_days": None, "deleted": [], "kept": 0,
                "ignored": 0}
    backend = backend or get_storage()
    plan = retention_plan([key for key, _size in backend.list_keys(BACKUP_PREFIX)],
                          keep_days, now=now)
    deleted = []
    for key in plan["delete"]:
        if snapshot_time(key) is None:   # the plan never holds one; the delete line stays obvious
            continue
        backend.delete(key)
        deleted.append(key)
        log.info("backup prune: deleted %s (older than %d days)", key, keep_days)
    log.info("backup prune: %d deleted, %d kept (keep %d days, newest %d always)",
             len(deleted), len(plan["keep"]), keep_days, KEEP_NEWEST)
    return {"enabled": True, "keep_days": keep_days, "deleted": deleted,
            "kept": len(plan["keep"]), "ignored": len(plan["ignored"])}
