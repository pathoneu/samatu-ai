#!/usr/bin/env python
"""READ-ONLY report: which nightly DB backups a prune would delete (2026-10-05).

backend/backup.py can prune old snapshots (backups/samatu-<stamp>.db) after a
good nightly backup, but only once SAMATU_BACKUP_KEEP_DAYS is set — until then
nothing is ever deleted, and a deleted account's data lives on in every old
snapshot. Choosing that number is a decision; this script shows what a given
number would do, before anyone sets it: for the configured storage, every
snapshot a prune would delete and every one it would keep, by the same rule the
prune uses (backup.retention_plan — the newest 7 are always kept, whatever
their age; any key that is not exactly a backup name is never touched).

It never deletes, moves or writes anything, and it has no option to.

What it reads, the same way the backend does: the storage chosen by
storage.get_storage() — R2 when the backend would use R2 (ENV=production or
STORAGE_BACKEND=r2 with the four R2_* variables), else LOCAL_STORAGE_DIR /
SAMATU_DATA_DIR / backend/data/pdf_store — keys under "backups/".

Usage (from the repository root or backend/):
    python scripts/report_backup_retention.py --days 30          # table
    python scripts/report_backup_retention.py --days 30 --json   # machine-readable
Without --days it uses SAMATU_BACKUP_KEEP_DAYS when that is set.
Exit code 0 = report printed, 2 = no valid number of days.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BACKEND = REPO / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def _load_env() -> None:
    """main.py calls load_dotenv() from backend/: the first .env found walking
    up from there, never overriding variables already set."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    for d in (BACKEND, *BACKEND.parents):
        if (d / ".env").is_file():
            load_dotenv(d / ".env")
            return


def collect(days: int, now: datetime.datetime | None = None) -> dict:
    """The whole report as a dict. Lists the storage; deletes nothing."""
    import backup
    import storage

    now = now or datetime.datetime.now(datetime.timezone.utc)
    backend = storage.get_storage()
    use_r2, why = storage.r2_decision()
    sizes = dict(backend.list_keys(backup.BACKUP_PREFIX))
    plan = backup.retention_plan(list(sizes), days, now=now)

    def row(key: str) -> dict:
        taken = backup.snapshot_time(key)
        return {"key": key, "bytes": sizes[key], "taken_at": taken.isoformat(),
                "age_days": round((now - taken).total_seconds() / 86400, 1)}

    would_delete = [row(k) for k in plan["delete"]]
    keep = [row(k) for k in plan["keep"]]
    return {
        "days": days,
        "now": now.isoformat(),
        "cutoff": plan["cutoff"],
        "keep_newest": backup.KEEP_NEWEST,
        "configured_keep_days": backup.backup_keep_days(warn=False),
        "storage": {"backend": "r2" if use_r2 else "local", "why": why,
                    "where": getattr(backend, "bucket", None) or str(getattr(backend, "root", ""))},
        "would_delete": would_delete,
        "keep": keep,
        "ignored": [{"key": k, "bytes": sizes[k]} for k in plan["ignored"]],
        "total": {"snapshots": len(would_delete) + len(keep),
                  "would_delete": len(would_delete),
                  "would_delete_bytes": sum(r["bytes"] for r in would_delete),
                  "keep": len(keep)},
    }


def _mb(n: int) -> str:
    return f"{n / (1024 * 1024):.2f} MB"


def _print_table(report: dict) -> None:
    st, tot = report["storage"], report["total"]
    configured = report["configured_keep_days"]
    print("Backup retention report (read-only: nothing was deleted)")
    print(f"Storage: {st['backend']} ({st['where']}) — {st['why']}")
    print(f"Rule: delete snapshots taken before {report['cutoff']} "
          f"({report['days']} days), always keep the newest {report['keep_newest']}")
    print("Configured now: " + (f"SAMATU_BACKUP_KEEP_DAYS={configured}" if configured
                                else "SAMATU_BACKUP_KEEP_DAYS unset — the backend prunes nothing"))
    print()
    print(f"Snapshots: {tot['snapshots']}   would delete: {tot['would_delete']} "
          f"({_mb(tot['would_delete_bytes'])})   keep: {tot['keep']}")
    for title, rows in (("WOULD DELETE", report["would_delete"]), ("KEEP", report["keep"])):
        print()
        print(f"{title} ({len(rows)}):")
        for r in rows:
            print(f"  {r['key']:<40}{r['age_days']:>8} d{r['bytes']:>14}")
    if report["ignored"]:
        print()
        print(f"NOT A BACKUP NAME — never touched ({len(report['ignored'])}):")
        for r in report["ignored"]:
            print(f"  {r['key']:<40}{'':>10}{r['bytes']:>14}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only: which nightly DB backups a prune would delete.")
    parser.add_argument("--days", help="days of snapshots to keep (whole number >= 1); "
                        "default: SAMATU_BACKUP_KEEP_DAYS")
    parser.add_argument("--json", action="store_true", help="print the report as JSON")
    args = parser.parse_args(argv)
    _load_env()
    import backup
    raw = args.days if args.days is not None else os.environ.get("SAMATU_BACKUP_KEEP_DAYS")
    days = backup.parse_keep_days(raw)
    if days is None:
        print("Give the days to keep: --days N (a whole number >= 1). "
              "SAMATU_BACKUP_KEEP_DAYS is unset or not such a number.", file=sys.stderr)
        return 2
    report = collect(days)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_table(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
