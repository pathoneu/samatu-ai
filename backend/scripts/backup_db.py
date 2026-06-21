#!/usr/bin/env python
"""One-off DB backup to durable object storage (R2/local).

Cron example (nightly 03:15):
    15 3 * * *  cd /app/backend && /app/venv/bin/python scripts/backup_db.py
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from backup import backup_db  # noqa: E402

if __name__ == "__main__":
    result = backup_db()
    print(f"DB backup uploaded → {result['key']} "
          f"({result['size']} bytes, backend={result['backend']})")
