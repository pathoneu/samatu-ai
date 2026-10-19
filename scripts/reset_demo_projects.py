#!/usr/bin/env python3
"""Put the two demo projects back to their walkthrough start state (Pathon v3 B2-B item 9).

The founder's walk changes the demo projects in the live database (2026-10-19: rooms 04 + 05 of
demo-objektas_h merged). The e2e suite's „pristine" snapshot (frontend/e2e/.state/pristine.db) is only a
copy of the live file taken when a run starts — it carries whatever the walk left, so it cannot be the
source. The pristine state is taken from each project's own version history instead (project_versions):

  * demo-objektas_h — the NEWEST stored version that is the founder guide's start state, by the same
    fingerprint the e2e global setup checks (frontend/e2e/state.js START: 11 rooms, 04 = 26,31 m², 05 not
    merged, kampai 475,66 m, lubos 143,27 m², no confirmed sheet scale, no measurements, no count types,
    no drawing revisions, no sheet overrides);
  * demo-objektas_g — its „Pradinė būsena" version (the state before the first edit after versioning
    shipped); no versions at all means it was never edited since → nothing to do.

The restore goes through db.restore_project_version, so the state it replaces is written first as a
„grąžinta" version: the reset itself can be undone from the project's „Versijos" list. No other project is
read or written. A project already in its start state is left alone.

    venv/bin/python scripts/reset_demo_projects.py --dry-run            # what it would do
    venv/bin/python scripts/reset_demo_projects.py                      # do it
    venv/bin/python scripts/reset_demo_projects.py --db path/to/samatu.db --dry-run

The browser keeps a write-through copy of each project (localStorage); the restored row carries a newer
updated_at, so an open tab picks the restored state up on reload. Reload the demo tabs after a reset.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEMO_H = "demo-objektas_h"
DEMO_G = "demo-objektas_g"

# frontend/e2e/state.js START — keep the two in step
START_H = {"rooms": 11, "a04": 26.31, "merged05": None, "kampai": 475.66, "lubos": 143.27,
           "confirmedScales": 0, "measurements": 0, "countTypes": 0, "revisions": 0, "sheetOverrides": 0}


def fingerprint(p: dict) -> dict:
    """frontend/e2e/state.js fingerprint(), without updated_at."""
    rooms = {str(r.get("nr")): r for r in (p.get("patalpos") or []) if isinstance(r, dict)}
    scales = [s for s in (p.get("pageScalesDurable") or {}).values()]
    totals = p.get("v8_totals") or {}
    lubos = totals.get("bendras_plotas_m2")
    return {
        "rooms": len(p.get("patalpos") or []),
        "a04": (rooms.get("04") or {}).get("plotas_m2"),
        "merged05": (rooms.get("05") or {}).get("_sujungta_i"),
        "kampai": totals.get("kampai_m"),
        "lubos": None if lubos is None else round(lubos * 100) / 100,
        "confirmedScales": sum(1 for s in scales if isinstance(s, dict) and s.get("confirmed")),
        "measurements": len(p.get("measurements") or []),
        "countTypes": len(p.get("countTypes") or []),
        "revisions": len((p.get("_meta") or {}).get("brezinio_leidimai") or []),
        "sheetOverrides": len(p.get("sheet_overrides") or {}),
    }


def mismatch(fp: dict, want: dict) -> list[str]:
    return [f"{k}: {fp.get(k)!r} (want {v!r})" for k, v in want.items() if fp.get(k) != v]


def pick_version(db, project_id: str) -> tuple[dict | None, str]:
    """(the version to restore, why) — (None, why) when there is none to restore."""
    versions = db.list_project_versions(project_id) or []
    if project_id == DEMO_H:
        for v in versions:                                          # newest first
            full = db.get_project_version(project_id, v["id"])
            if full and not mismatch(fingerprint(full["data"]), START_H):
                return v, "newest version that is the founder guide's start state"
        return None, "no stored version is the founder guide's start state"
    first = [v for v in versions if v.get("pavadinimas") == "Pradinė būsena"]
    if first:
        return first[-1], "its „Pradinė būsena“ version"
    if not versions:
        return None, "no versions — never edited since versioning shipped"
    return None, "no „Pradinė būsena“ version"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--db", default=str(REPO / "backend" / "data" / "samatu.db"),
                    help="the SQLite file (default: backend/data/samatu.db of this checkout)")
    ap.add_argument("--dry-run", action="store_true", help="say what would be restored, write nothing")
    ap.add_argument("--only", choices=[DEMO_H, DEMO_G], help="reset one of the two")
    args = ap.parse_args(argv)

    db_path = Path(args.db).resolve()
    if not db_path.exists():
        print(f"No database at {db_path}", file=sys.stderr)
        return 2
    os.environ["SAMATU_DB_PATH"] = str(db_path)
    sys.path.insert(0, str(REPO / "backend"))
    import db  # noqa: E402 — the path is set above
    db._DB_PATH = db_path          # also when db was imported before (tests): this file, no other

    print(f"database: {db_path}{'  (dry run — nothing is written)' if args.dry_run else ''}")
    failed = 0
    for pid in [args.only] if args.only else [DEMO_H, DEMO_G]:
        current = db.get_project(pid)
        if current is None:
            print(f"{pid}: not in this database — skipped")
            continue
        v, why = pick_version(db, pid)
        now_fp = fingerprint(current)
        print(f"{pid}: now {now_fp}")
        if v is None:
            print(f"  nothing to restore: {why}")
            if pid == DEMO_H and mismatch(now_fp, START_H):
                failed += 1
            continue
        listed = {x["id"]: x for x in db.list_project_versions(pid) or []}
        if listed.get(v["id"], {}).get("dabartine"):
            print(f"  already in its start state (= version {v['id']}, {v['created_at']}) — left alone")
            continue
        target_fp = fingerprint(db.get_project_version(pid, v["id"])["data"])
        diff = [f"{k} {now_fp.get(k)!r} → {target_fp.get(k)!r}" for k in target_fp if now_fp.get(k) != target_fp.get(k)]
        print(f"  restore version {v['id']} ({v['created_at']}, {v['saltinis']}"
              f"{', ' + v['pavadinimas'] if v.get('pavadinimas') else ''}) — {why}")
        print(f"  changes: {'; '.join(diff) if diff else 'none in the fingerprint (other content differs)'}")
        if args.dry_run:
            continue
        saved = db.restore_project_version(pid, v["id"])
        if saved is None:
            print("  RESTORE FAILED", file=sys.stderr)
            failed += 1
            continue
        after = fingerprint(db.get_project(pid))
        bad = mismatch(after, START_H) if pid == DEMO_H else []
        print(f"  restored; the replaced state is kept as a „grąžinta“ version (undo from „Versijos“)"
              + (f" — BUT not the start state: {bad}" if bad else ""))
        failed += bool(bad)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
