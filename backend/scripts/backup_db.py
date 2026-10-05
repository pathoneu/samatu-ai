#!/usr/bin/env python
"""Manual DB backup to durable object storage (R2/local): one snapshot, now.

The nightly backup runs inside the web process (backup_scheduler.py); this is
its by-hand twin, e.g. before a migration:

    cd backend && ../venv/bin/python scripts/backup_db.py

The snapshot is the nightly one (backup.backup_db: VACUUM INTO, integrity
check, upload). Since 2026-10-05 the outcome is recorded the same way too, in
app_state (`backup_last_outcome`) through backup_scheduler — the record the
admin backup panel reads. A good manual run turns the panel green, a failed
one shows its error there, and a failed one keeps the last good snapshot as
what a restore would use. Old snapshots are never pruned here: retention runs
only after a nightly backup, and only when SAMATU_BACKUP_KEEP_DAYS is set.

Exit code 0 = stored, 1 = failed (the reason is printed and recorded).
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import backup  # noqa: E402
import backup_scheduler  # noqa: E402


def main() -> int:
    try:
        result = backup.backup_db()
    except Exception as exc:  # noqa: BLE001 — recorded and reported, like a failed night
        backup_scheduler._record_error(exc)
        print(f"DB backup FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    backup_scheduler._record_ok(result)
    print(f"DB backup uploaded → {result['key']} "
          f"({result['size']} bytes, backend={result['backend']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
