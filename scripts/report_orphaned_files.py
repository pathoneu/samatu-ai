#!/usr/bin/env python
"""READ-ONLY report: stored files of projects that no longer exist (2026-09-30).

Until backend/project_purge.py (2026-09-29), deleting a project dropped only
the database row. The drawing stayed in storage (R2 in production, local
disk elsewhere) and every id-keyed side store kept its files. This script lists
what is left behind: every stored drawing and every id-keyed side file whose
project id is no longer in the `projects` table, with counts and total bytes.

It never deletes, moves or writes anything, and it has no option to. What to do
with the list is a separate, deliberate decision.

What it reads, the same way the backend does:
  · the database at db._DB_PATH (SAMATU_DB_PATH, else backend/data/samatu.db),
    opened read-only;
  · the drawing storage chosen by storage.get_storage() (R2 when the backend
    would use R2 — ENV=production or STORAGE_BACKEND=r2 with the four R2_*
    variables — else LOCAL_STORAGE_DIR / SAMATU_DATA_DIR / backend/data/pdf_store),
    keys under "projects/";
  · the side stores project_purge knows by project id: annotations,
    calibrations, legends (<id>.json), evidence crops and F2/F3 line files
    (<id>/ folders), at the roots those modules use.

Not covered: CV page renders (named by the PDF's content hash, not by project
id), in-memory caches, the append-only symbol-training corpus and the
per-architect legend aggregate (none of them are keyed by project id).

Usage (from the repository root or backend/):
    python scripts/report_orphaned_files.py          # table
    python scripts/report_orphaned_files.py --json   # machine-readable
Exit code 0 = report printed, 2 = the database could not be opened.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BACKEND = REPO / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

PDF_PREFIX = "projects/"


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


def project_ids(db_path: Path) -> set[str]:
    """Every project id in the database — opened read-only, never created."""
    uri = Path(db_path).resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as c:
        return {str(r[0]) for r in c.execute("SELECT id FROM projects")}


def side_stores() -> list[tuple[str, Path, str]]:
    """(name, root, shape) for the id-keyed side stores project_purge clears.
    shape "file" = <id>.json directly under the root; "dir" = an <id>/ folder."""
    from api import annotations, calibrate, evidence, exports_v2, legends
    return [
        ("annotations", Path(annotations.DATA_ROOT), "file"),
        ("calibrations", Path(calibrate.CALIB_ROOT), "file"),
        ("legends", Path(legends.LEGENDS_DIR), "file"),
        ("evidence_cache", Path(evidence.CACHE_ROOT), "dir"),
        ("exports", Path(exports_v2.PROJECTS_DIR), "dir"),
    ]


def _side_entries(root: Path, shape: str):
    """(project_id, bytes, path) for every entry of one side store."""
    if not root.is_dir():
        return
    for p in sorted(root.iterdir()):
        if shape == "file" and p.is_file() and p.suffix == ".json":
            yield p.stem, p.stat().st_size, str(p)
        elif shape == "dir" and p.is_dir():
            size = sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
            yield p.name, size, str(p)


def _drawing_entries(backend):
    for key, size in backend.list_keys(PDF_PREFIX):
        name = key[len(PDF_PREFIX):]
        if "/" in name or not name.endswith(".pdf"):
            continue          # not a project drawing (e.g. a half-written .tmp)
        yield name[:-len(".pdf")], int(size), key


def collect() -> dict:
    """The whole report as a dict. Raises sqlite3.Error when the database
    cannot be opened."""
    import db
    import storage

    db_path = Path(db._DB_PATH)
    live = project_ids(db_path)
    backend = storage.get_storage()
    use_r2, why = storage.r2_decision()

    stores: dict[str, dict] = {}
    orphans: list[dict] = []

    def scan(name: str, entries) -> None:
        row = {"scanned": 0, "orphaned": 0, "bytes": 0}
        for pid, size, where in entries:
            row["scanned"] += 1
            if pid in live:
                continue
            row["orphaned"] += 1
            row["bytes"] += size
            orphans.append({"store": name, "project_id": pid, "bytes": size, "where": where})
        stores[name] = row

    scan("drawings", _drawing_entries(backend))
    for name, root, shape in side_stores():
        scan(name, _side_entries(root, shape))

    return {
        "db_path": str(db_path),
        "projects_in_db": len(live),
        "storage": {"backend": "r2" if use_r2 else "local", "why": why,
                    "where": getattr(backend, "bucket", None) or str(getattr(backend, "root", ""))},
        "stores": stores,
        "orphans": orphans,
        "total": {"orphaned": len(orphans),
                  "bytes": sum(o["bytes"] for o in orphans),
                  "project_ids": len({o["project_id"] for o in orphans})},
    }


def _mb(n: int) -> str:
    return f"{n / (1024 * 1024):.2f} MB"


def _print_table(report: dict) -> None:
    st = report["storage"]
    print("Orphaned files report (read-only: nothing was deleted)")
    print(f"Database: {report['db_path']} — {report['projects_in_db']} projects")
    print(f"Drawings storage: {st['backend']} ({st['where']}) — {st['why']}")
    print()
    print(f"{'store':<16}{'scanned':>9}{'orphaned':>10}{'bytes':>14}")
    for name, row in report["stores"].items():
        print(f"{name:<16}{row['scanned']:>9}{row['orphaned']:>10}{row['bytes']:>14}")
    tot = report["total"]
    print(f"{'total':<16}{'':>9}{tot['orphaned']:>10}{tot['bytes']:>14}"
          f"   ({_mb(tot['bytes'])}, {tot['project_ids']} deleted project ids)")
    if report["orphans"]:
        print()
        print("Orphaned entries (store, project id, bytes, location):")
        for o in report["orphans"]:
            print(f"  {o['store']:<16}{o['project_id']:<40}{o['bytes']:>12}  {o['where']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only report of stored files whose project no longer exists.")
    parser.add_argument("--json", action="store_true", help="print the report as JSON")
    args = parser.parse_args(argv)
    _load_env()
    try:
        report = collect()
    except sqlite3.Error as exc:
        import db
        print(f"Could not open the database read-only at {db._DB_PATH}: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_table(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
