import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
from telemetry.session_log import append_session, SessionRecord


def test_append_session_writes_jsonl_line(tmp_path, monkeypatch):
    log_file = tmp_path / "session_log.jsonl"
    monkeypatch.setenv("TELEMETRY_LOG_PATH", str(log_file))

    record = SessionRecord(
        project_id="proj-abc",
        started_at=1714740000,
        finished_at=1714740900,
        total_seconds=900,
        gestures=[
            {"type": "G1", "timestamp_ms_from_start": 500,
             "target": {"kind": "room", "id": "K1"},
             "outcome": "success", "duration_ms": 3200},
        ],
        exported=True,
    )
    append_session(record)

    lines = log_file.read_text().splitlines()
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed["project_id"] == "proj-abc"
    assert parsed["total_seconds"] == 900
    assert parsed["gestures"][0]["type"] == "G1"


def test_append_session_appends_does_not_overwrite(tmp_path, monkeypatch):
    log_file = tmp_path / "session_log.jsonl"
    monkeypatch.setenv("TELEMETRY_LOG_PATH", str(log_file))

    for i in range(3):
        append_session(SessionRecord(
            project_id=f"proj-{i}", started_at=0, finished_at=1,
            total_seconds=1, gestures=[], exported=False,
        ))

    lines = log_file.read_text().splitlines()
    assert len(lines) == 3
