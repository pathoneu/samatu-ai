"""Database backup to durable object storage (2026-06-21 durability track).

The audit flagged "one disk failure on Render wipes every customer's projects" as
an unacceptable risk before charging money. This takes a CONSISTENT SQLite snapshot
(``VACUUM INTO``, safe under concurrent WAL readers) and uploads it to the same
object store the PDFs use — R2 in prod, local disk in dev. Point a nightly cron at
``scripts/backup_db.py``.
"""
from __future__ import annotations

import datetime
import pathlib
import sqlite3
import tempfile

import db
from storage import get_storage


def _utc_stamp() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def backup_db(stamp: str | None = None) -> dict:
    """Snapshot the live DB and upload it. Returns {key, size, backend}."""
    stamp = stamp or _utc_stamp()
    key = f"backups/samatu-{stamp}.db"
    with tempfile.TemporaryDirectory() as td:
        snap = pathlib.Path(td) / "snapshot.db"
        # Fresh connection in autocommit mode — VACUUM INTO can't run inside a
        # transaction, and a fresh handle avoids the app's pooled connection lock.
        conn = sqlite3.connect(str(db._DB_PATH))
        try:
            conn.execute("VACUUM INTO ?", (str(snap),))
        finally:
            conn.close()
        data = snap.read_bytes()
    get_storage().put(key, data, content_type="application/x-sqlite3")
    return {"key": key, "size": len(data), "backend": get_storage().name}
