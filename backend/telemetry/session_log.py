"""Sprint 0 Fix 6: append-only JSONL session log.

Writes one record per completed session. Sprint 4 reads this to compute
time-to-finish-KŽ and compare against manual baseline.

Schema per docs/superpowers/specs/2026-05-03-takeoff-workspace-design.md §4.8.
"""
import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path

_DEFAULT_PATH = Path("backend/telemetry/session_log.jsonl")


@dataclass
class GestureEvent:
    type: str                                # "G1".."G7"
    timestamp_ms_from_start: int
    target: dict                             # {kind: "room"|"symbol"|..., id: str}
    outcome: str                             # "success" | "error" | "cancelled"
    duration_ms: int


@dataclass
class SessionRecord:
    project_id: str
    started_at: int                          # unix seconds
    finished_at: int
    total_seconds: int
    gestures: list[dict] = field(default_factory=list)
    exported: bool = False


def _log_path() -> Path:
    return Path(os.environ.get("TELEMETRY_LOG_PATH", _DEFAULT_PATH))


def append_session(record: SessionRecord) -> None:
    """Append a session record as one JSONL line. Creates file/parents if needed."""
    p = _log_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")
