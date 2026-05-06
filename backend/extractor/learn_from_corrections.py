"""Sprint 10 (autonomous half) — analyse correction log and propose prompt
annotations.

The frontend logs every user override to the `corrections` table
(field_path, old_value, new_value, source, occurred_at). Over time these
reveal systematic AI mistakes — fields where a large fraction of users
override the same way.

This script:
  1. Pulls last N days of corrections (default 30)
  2. Groups by field_path
  3. For each field where override rate > THRESHOLD, finds the dominant
     old → new pattern
  4. Emits a markdown report + a suggested annotation block for prompt.py

USAGE:
  python -m extractor.learn_from_corrections [--days 30] [--out report.md]

NOTE: This is intentionally a manual / cron-driven tool, NOT auto-applied.
The owner reviews the report, decides which suggestions are real signals
vs. one-off bugs, then edits prompt.py manually.
"""
from __future__ import annotations
import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Allow running from repo root or from backend/.
_HERE = Path(__file__).resolve().parent
if str(_HERE.parent) not in sys.path:
    sys.path.insert(0, str(_HERE.parent))

import db  # noqa: E402


THRESHOLD_OVERRIDE_RATE = 0.20   # field needs ≥20% of projects overriding it
MIN_PROJECTS_AFFECTED = 3        # don't surface single-project anomalies
TOP_N_FIELDS = 25                # report cap


def _safe_load(value):
    """Corrections store old/new as JSON-stringified. Decode robustly."""
    if value is None:
        return None
    try:
        return json.loads(value)
    except Exception:
        return value


def aggregate(days: int = 30) -> dict:
    """Group corrections by field_path. Returns:
    {
        field_path: {
            "n_corrections": int,
            "n_projects": int,
            "common_changes": [(old → new, count), ...top 5],
            "sample_old_values": [..3 examples..],
            "sample_new_values": [..3 examples..],
        }
    }
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with db._conn() as c:
        rows = c.execute("""
            SELECT project_id, field_path, old_value, new_value, occurred_at
              FROM corrections
             WHERE occurred_at >= ?
        """, (cutoff,)).fetchall()

    by_field: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_field[r["field_path"]].append(dict(r))

    out = {}
    for field, entries in by_field.items():
        projects = {e["project_id"] for e in entries}
        change_counts = Counter()
        for e in entries:
            old = _safe_load(e["old_value"])
            new = _safe_load(e["new_value"])
            key = f"{old!r} → {new!r}"
            change_counts[key] += 1
        out[field] = {
            "n_corrections": len(entries),
            "n_projects": len(projects),
            "common_changes": change_counts.most_common(5),
            "sample_old": [_safe_load(e["old_value"]) for e in entries[:3]],
            "sample_new": [_safe_load(e["new_value"]) for e in entries[:3]],
        }
    return out


def project_count_in_period(days: int) -> int:
    """How many distinct projects had ANY activity in the period — denominator
    for the override-rate calculation."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with db._conn() as c:
        row = c.execute("""
            SELECT COUNT(DISTINCT project_id) AS n
              FROM corrections
             WHERE occurred_at >= ?
        """, (cutoff,)).fetchone()
        return int(row["n"] or 0)


def render_report(agg: dict, total_projects: int, days: int) -> str:
    """Markdown report with top fields ranked by impact (n_projects)."""
    if not agg:
        return f"# Korekcijų ataskaita ({days} d.)\n\nNėra korekcijų.\n"

    fields = sorted(
        agg.items(),
        key=lambda kv: (-kv[1]["n_projects"], -kv[1]["n_corrections"]),
    )[:TOP_N_FIELDS]

    lines = [
        f"# Korekcijų ataskaita ({days} d.)",
        f"",
        f"**Periodas:** paskutinės {days} dienos · "
        f"**Aktyvūs projektai:** {total_projects} · "
        f"**Korekcijų laukų:** {len(agg)}",
        "",
        "## Top fields by impact",
        "",
        "| # | field_path | korekc. | proj. | override rate | dominuojantis pakeitimas |",
        "|---|---|---|---|---|---|",
    ]
    for i, (field, info) in enumerate(fields, 1):
        rate = info["n_projects"] / max(total_projects, 1)
        rate_pct = f"{rate*100:.0f}%"
        flagged = "🔥" if rate >= THRESHOLD_OVERRIDE_RATE and info["n_projects"] >= MIN_PROJECTS_AFFECTED else ""
        top_change = info["common_changes"][0][0] if info["common_changes"] else "—"
        # Truncate long values for table readability
        if len(top_change) > 60:
            top_change = top_change[:57] + "..."
        lines.append(
            f"| {i} {flagged} | `{field}` | {info['n_corrections']} | "
            f"{info['n_projects']} | {rate_pct} | `{top_change}` |"
        )

    lines += [
        "",
        "## Suggested prompt annotations",
        "",
        "Kiekvienas 🔥 ženklą turintis laukas yra kandidatas į prompt'o "
        f"`Common corrections to watch:` skiltį. Slenkstis: ≥{int(THRESHOLD_OVERRIDE_RATE*100)}% projektų "
        f"+ ≥{MIN_PROJECTS_AFFECTED} skirtingų projektų.",
        "",
    ]
    candidates = [
        (field, info)
        for field, info in fields
        if (info["n_projects"] / max(total_projects, 1)) >= THRESHOLD_OVERRIDE_RATE
        and info["n_projects"] >= MIN_PROJECTS_AFFECTED
    ]
    if not candidates:
        lines.append("_Šiuo metu nėra laukų, kirtusių abu slenksčius._")
    else:
        lines.append("```")
        lines.append("# Common corrections to watch (auto-generated; review before commit)")
        for field, info in candidates:
            change = info["common_changes"][0][0] if info["common_changes"] else ""
            lines.append(f"# - {field}: dažniausias pakeitimas {change}")
        lines.append("```")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=30,
                        help="Look-back window in days (default 30)")
    parser.add_argument("--out", type=str, default="-",
                        help="Output path (default: stdout)")
    args = parser.parse_args()

    agg = aggregate(args.days)
    total = project_count_in_period(args.days)
    md = render_report(agg, total, args.days)

    if args.out == "-":
        sys.stdout.write(md)
    else:
        Path(args.out).write_text(md, encoding="utf-8")
        print(f"Report written → {args.out} ({len(md)} bytes)")


if __name__ == "__main__":
    main()
