"""Week 6 Task 6.4 — audit trail rows + history strings."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from extractor.audit_trail import (  # noqa: E402
    audit_trail_rows,
    audit_history_strings,
)


def test_audit_trail_rows_serializes_dict_events():
    events = [
        {
            "timestamp": "2026-05-10T12:00:00+00:00",
            "project_id": "p1", "op": "update", "target_type": "quantity_line",
            "target_code": "angokrasciai_lm",
            "before": {"quantity": 5.0}, "after": {"quantity": 6.5},
            "reason": "extra reveal at hidden door",
        },
        {
            "timestamp": "2026-05-10T12:01:00+00:00",
            "project_id": "p1", "op": "verify", "target_type": "quantity_line",
            "target_code": "dazymo_plotas_total_m2",
        },
    ]
    rows = audit_trail_rows(events)
    assert len(rows) == 2
    assert rows[0]["target_code"] == "angokrasciai_lm"
    assert rows[0]["old_value"] == 5.0
    assert rows[0]["new_value"] == 6.5
    assert rows[0]["reason"] == "extra reveal at hidden door"
    assert rows[0]["source_after"] == "user"
    assert rows[1]["op"] == "verify"
    assert rows[1]["source_after"] == "verified"


def test_audit_history_strings_groups_by_target_code():
    events = [
        {
            "timestamp": "2026-05-10T12:00:00+00:00",
            "project_id": "p1", "op": "update", "target_type": "quantity_line",
            "target_code": "angokrasciai_lm",
            "before": {"quantity": 5.0}, "after": {"quantity": 6.5},
            "reason": "missed hidden door",
        },
        {
            "timestamp": "2026-05-10T12:05:00+00:00",
            "project_id": "p1", "op": "update", "target_type": "quantity_line",
            "target_code": "angokrasciai_lm",
            "before": {"quantity": 6.5}, "after": {"quantity": 7.0},
        },
        {
            "timestamp": "2026-05-10T12:10:00+00:00",
            "project_id": "p1", "op": "verify", "target_type": "quantity_line",
            "target_code": "angokrasciai_lm",
        },
    ]
    history = audit_history_strings(events)
    assert "angokrasciai_lm" in history
    lines = history["angokrasciai_lm"]
    assert len(lines) == 3
    assert "missed hidden door" in lines[0]
    assert "Patikrinta" in lines[2]


def test_empty_events_returns_empty():
    assert audit_trail_rows([]) == []
    assert audit_history_strings([]) == {}


def test_pydantic_event_works_too():
    """Tolerate dataclass-like inputs as well as dicts."""
    class FakeEvent:
        def __init__(self, **kw):
            self.__dict__.update(kw)

    events = [FakeEvent(
        timestamp="2026-05-10T12:00:00",
        project_id="p1", op="update", target_type="quantity_line",
        target_code="x",
        before={"quantity": 1}, after={"quantity": 2},
        reason="test",
    )]
    rows = audit_trail_rows(events)
    assert rows[0]["old_value"] == 1
    assert rows[0]["new_value"] == 2
