"""Audit trail rendering (Week 6 Task 6.4).

Pure converter: takes correction events (any dict/obj with the documented
keys) and renders rows ready for splicing into F2/F3 export (Week 7). The
original JSONL feed (`corrections_v2`) was removed 2026-06-21; the durable
correction log now lives in the `corrections` DB table and would need a
translation pass before it can be fed here.
"""
from __future__ import annotations

from typing import Any


def audit_trail_rows(events: list[dict | Any]) -> list[dict]:
    """Convert correction events to flat audit rows.

    Each event becomes one row with stable keys (timestamp, op, target_code,
    old_value, new_value, reason, source_before, source_after) so the F2
    export can render them as a customer-facing audit column.
    """
    rows: list[dict] = []
    for e in events or []:
        # Tolerate either CorrectionEvent (Pydantic) or plain dict input.
        get = e.get if isinstance(e, dict) else lambda k, d=None: getattr(e, k, d)
        before = get("before") or {}
        after = get("after") or {}
        op = get("op") or ""
        rows.append({
            "timestamp": str(get("timestamp") or ""),
            "user_id": get("user_id") or "",
            "project_id": get("project_id") or "",
            "op": op,
            "target_type": get("target_type") or "",
            "target_code": get("target_code") or "",
            "target_id": get("target_id") or "",
            "old_value": before.get("quantity") if isinstance(before, dict) else None,
            "new_value": after.get("quantity") if isinstance(after, dict) else None,
            "reason": get("reason") or "",
            # source_before / source_after derived from the op:
            "source_before": "ai" if op == "update" else None,
            "source_after": "user" if op == "update" else ("verified" if op == "verify" else None),
        })
    return rows


def audit_history_strings(events: list[dict | Any]) -> dict[str, list[str]]:
    """Group events by `target_code` and render human-readable lines.

    Output: `{ "angokrasciai_lm": ["5.0→6.5 (extra reveal at hidden door)"] }`.
    Used by F2 export to populate the per-row `audit_history` column.
    """
    out: dict[str, list[str]] = {}
    for row in audit_trail_rows(events):
        code = row.get("target_code")
        if not code:
            continue
        old = row.get("old_value")
        new = row.get("new_value")
        reason = row.get("reason") or ""
        if row["op"] == "verify":
            line = "Patikrinta"
        else:
            line = f"{old}→{new}"
        if reason:
            line = f"{line} ({reason})"
        out.setdefault(code, []).append(line)
    return out
