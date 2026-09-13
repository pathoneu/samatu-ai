"""pilot_report — what the telemetry log says about each project, in one table.

The pilot's questions (council verdict 5, 2026-09-13), answered from
`backend/telemetry/session_log.jsonl` alone:

  • minutes from first opening the project to its first export;
  • facts accepted vs corrected on the check sheet, rooms stamped verified;
  • rows priced / edited, deleted, added in the sąmata table;
  • whether an export happened at all, and how many.

Project ids only — the log carries no names, prices or client data, and this
report prints nothing that is not in the log.

Run:  python scripts/pilot_report.py [--log PATH] [--json]
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path

DEFAULT_LOG = Path(__file__).resolve().parents[1] / "backend" / "telemetry" / "session_log.jsonl"

# Event type → the column it counts into.
_FACT_CORRECTIONS = {"fact_number", "fact_choice", "opening_adjust", "opening_size"}
_ROW_EDITS = {"row_edit", "kainynas_apply"}


@dataclass
class ProjectStats:
    project_id: str
    sessions: int = 0
    minutes: float = 0.0
    first_opened_at: int | None = None
    first_export_at: int | None = None
    exports: int = 0
    facts_accepted: int = 0
    facts_corrected: int = 0
    rooms_verified: int = 0
    rooms_added: int = 0
    scope_changes: int = 0
    rows_edited: int = 0
    rows_deleted: int = 0
    rows_added: int = 0
    rereads: int = 0
    corrected_rooms: set = field(default_factory=set)

    @property
    def minutes_to_first_export(self) -> float | None:
        if self.first_opened_at is None or self.first_export_at is None:
            return None
        return round(max(0, self.first_export_at - self.first_opened_at) / 60.0, 1)

    def as_row(self) -> dict:
        d = asdict(self)
        d.pop("corrected_rooms", None)
        d["rooms_with_corrections"] = len(self.corrected_rooms)
        d["minutes"] = round(self.minutes, 1)
        d["minutes_to_first_export"] = self.minutes_to_first_export
        return d


def read_log(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out: list[dict] = []
    for ln in path.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            rec = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict) and rec.get("project_id"):
            out.append(rec)
    return out


def summarize(records: list[dict]) -> list[ProjectStats]:
    by: dict[str, ProjectStats] = {}
    for rec in records:
        pid = str(rec.get("project_id"))
        st = by.setdefault(pid, ProjectStats(project_id=pid))
        st.sessions += 1
        st.minutes += float(rec.get("total_seconds") or 0) / 60.0
        started = rec.get("started_at")
        if isinstance(started, (int, float)):
            st.first_opened_at = int(started) if st.first_opened_at is None else min(st.first_opened_at, int(started))
        for g in rec.get("gestures") or []:
            if not isinstance(g, dict):
                continue
            typ = str(g.get("type") or "")
            tgt = g.get("target") if isinstance(g.get("target"), dict) else {}
            room = tgt.get("room")
            if typ == "fact_accept":
                st.facts_accepted += 1
            elif typ in _FACT_CORRECTIONS:
                st.facts_corrected += 1
                if room is not None:
                    st.corrected_rooms.add(str(room))
            elif typ == "room_verified":
                st.rooms_verified += 1
            elif typ == "room_add":
                st.rooms_added += 1
            elif typ == "scope_change":
                st.scope_changes += 1
            elif typ in _ROW_EDITS:
                st.rows_edited += 1
            elif typ == "row_delete":
                st.rows_deleted += 1
            elif typ == "row_add":
                st.rows_added += 1
            elif typ == "reread":
                st.rereads += 1
            elif typ == "export":
                st.exports += 1
                if isinstance(started, (int, float)):
                    at = int(started) + int((g.get("timestamp_ms_from_start") or 0) / 1000)
                    st.first_export_at = at if st.first_export_at is None else min(st.first_export_at, at)
        if rec.get("exported") and st.exports == 0:
            # older records: the flag without the event
            st.exports += 1
            fin = rec.get("finished_at")
            if isinstance(fin, (int, float)):
                st.first_export_at = int(fin) if st.first_export_at is None else min(st.first_export_at, int(fin))
    return sorted(by.values(), key=lambda s: (s.first_opened_at or 0, s.project_id))


def render_table(stats: list[ProjectStats]) -> str:
    head = (f"{'project':<38} {'sess':>4} {'min':>6} {'→exp':>6} {'exp':>3} "
            f"{'ok':>4} {'fix':>4} {'rooms':>5} {'ver':>4} {'r.ed':>4} {'r.del':>5} {'r.add':>5} {'re':>2}")
    lines = [head, "─" * len(head)]
    for s in stats:
        mte = s.minutes_to_first_export
        lines.append(
            f"{s.project_id[:38]:<38} {s.sessions:>4} {s.minutes:>6.1f} {('—' if mte is None else f'{mte:.0f}'):>6} "
            f"{s.exports:>3} {s.facts_accepted:>4} {s.facts_corrected:>4} {len(s.corrected_rooms):>5} "
            f"{s.rooms_verified:>4} {s.rows_edited:>4} {s.rows_deleted:>5} {s.rows_added:>5} {s.rereads:>2}")
    lines.append("")
    lines.append("sess = sessions, min = minutes open, →exp = minutes from first opening to first export, "
                 "exp = exports, ok = facts accepted, fix = facts corrected, rooms = rooms with a correction, "
                 "ver = rooms stamped verified, r.ed/r.del/r.add = rows edited/deleted/added, re = re-reads")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--log", default=str(DEFAULT_LOG))
    ap.add_argument("--json", action="store_true", help="machine-readable rows instead of the table")
    args = ap.parse_args(argv)
    stats = summarize(read_log(Path(args.log)))
    if args.json:
        print(json.dumps([s.as_row() for s in stats], ensure_ascii=False, indent=2))
    else:
        print(render_table(stats) if stats else f"no sessions in {args.log}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
