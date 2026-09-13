"""scripts/pilot_report.py — the pilot's questions answered from the session log.

Synthetic records only; project ids are placeholders.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("pilot_report", ROOT / "scripts" / "pilot_report.py")
pilot_report = importlib.util.module_from_spec(_spec)
sys.modules["pilot_report"] = pilot_report
_spec.loader.exec_module(pilot_report)


def _g(typ, ms, **target):
    return {"type": typ, "target": target, "outcome": "success", "duration_ms": 0, "timestamp_ms_from_start": ms}


def _write(tmp_path, records):
    p = tmp_path / "session_log.jsonl"
    p.write_text("".join(json.dumps(r) + "\n" for r in records) + "not json\n", encoding="utf-8")
    return p


def test_the_report_answers_the_pilot_questions_per_project(tmp_path):
    log = _write(tmp_path, [
        # project A: opened at t=1000, two sessions, exported in the second
        {"project_id": "proj-a", "started_at": 1000, "finished_at": 1300, "total_seconds": 300, "exported": False,
         "gestures": [_g("fact_accept", 5000, kind="fact", id="plotas", room="01"),
                      _g("fact_number", 9000, kind="fact", id="perimetras_m", room="01"),
                      _g("opening_adjust", 12000, kind="opening", id="duris", room="03"),
                      _g("room_verified", 20000, kind="room", id="01")]},
        {"project_id": "proj-a", "started_at": 2000, "finished_at": 2600, "total_seconds": 600, "exported": True,
         "gestures": [_g("row_delete", 30000, kind="row", id="Slenksniai"),
                      _g("row_edit", 40000, kind="row", id="Sienų glaistymas/dažymas"),
                      _g("row_add", 41000, kind="row", id=""),
                      _g("export", 120000, kind="export", id="excel")]},
        # project B: a blink, nothing done, an older record with the flag but no event
        {"project_id": "proj-b", "started_at": 5000, "finished_at": 5040, "total_seconds": 40, "exported": True,
         "gestures": []},
    ])
    stats = pilot_report.summarize(pilot_report.read_log(log))
    by = {s.project_id: s for s in stats}
    a = by["proj-a"]
    assert a.sessions == 2 and round(a.minutes, 1) == 15.0
    assert a.facts_accepted == 1 and a.facts_corrected == 2 and a.rooms_verified == 1
    assert sorted(a.corrected_rooms) == ["01", "03"]
    assert a.rows_edited == 1 and a.rows_deleted == 1 and a.rows_added == 1
    assert a.exports == 1
    assert a.first_opened_at == 1000 and a.first_export_at == 2000 + 120
    assert a.minutes_to_first_export == round(1120 / 60, 1)
    b = by["proj-b"]
    assert b.exports == 1 and b.first_export_at == 5040 and b.minutes_to_first_export == round(40 / 60, 1)
    assert b.facts_accepted == 0 and b.facts_corrected == 0

    rows = [s.as_row() for s in stats]
    assert rows[0]["project_id"] == "proj-a" and rows[0]["rooms_with_corrections"] == 2
    assert "corrected_rooms" not in rows[0]
    table = pilot_report.render_table(stats)
    assert "proj-a" in table and "proj-b" in table and "→exp" in table


def test_a_missing_or_empty_log_is_not_an_error(tmp_path):
    assert pilot_report.read_log(tmp_path / "nope.jsonl") == []
    assert pilot_report.summarize([]) == []
    assert pilot_report.main(["--log", str(tmp_path / "nope.jsonl")]) == 0
