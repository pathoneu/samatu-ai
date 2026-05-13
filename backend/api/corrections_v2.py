"""Per-quantity corrections + Patikrinta verified state (Week 5 Task 5.1).

The pre-existing `recompute-quantities` endpoint covers ASSUMPTION edits
(paint_class, lubu_aukstis, gestures). This one is for AUDIT edits that
the user makes directly on a quantity card:

- update: change a single line's quantity ("we measured 6.5, AI said 5.0").
- verify: mark a line as "Patikrinta" (source becomes "verified").

Storage: file-system-backed JSONL at `data/corrections/<project_id>.jsonl`.
Beta has no auth/DB yet (memory: project_spend_caps_disabled). Once auth
lands, swap the JSONL backend for a DB table.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/corrections", tags=["corrections"])

CORRECTIONS_DIR = Path(__file__).resolve().parents[2] / "data" / "corrections"


def _project_path(project_id: str) -> Path:
    if not project_id or "/" in project_id or ".." in project_id:
        raise HTTPException(status_code=400, detail="Invalid project_id")
    CORRECTIONS_DIR.mkdir(parents=True, exist_ok=True)
    return CORRECTIONS_DIR / f"{project_id}.jsonl"


class CorrectionOp(BaseModel):
    op: Literal["update", "add", "delete", "relabel", "verify"]
    target_type: Literal["quantity_line", "opening", "tile_zone", "symbol", "room"] = "quantity_line"
    target_code: str | None = None
    target_id: str | None = None
    before: dict | None = None
    after: dict | None = None
    reason: str | None = None


class CorrectionBatch(BaseModel):
    project_id: str
    operations: list[CorrectionOp]


class CorrectionEvent(BaseModel):
    timestamp: str
    user_id: str | None = None
    project_id: str
    op: str
    target_type: str
    target_code: str | None = None
    target_id: str | None = None
    before: dict | None = None
    after: dict | None = None
    reason: str | None = None


class CorrectionLog(BaseModel):
    project_id: str
    events: list[CorrectionEvent]


def append_correction(project_id: str, op: CorrectionOp, user_id: str | None = None) -> CorrectionEvent:
    event = CorrectionEvent(
        timestamp=datetime.now(timezone.utc).isoformat(),
        user_id=user_id,
        project_id=project_id,
        op=op.op,
        target_type=op.target_type,
        target_code=op.target_code,
        target_id=op.target_id,
        before=op.before,
        after=op.after,
        reason=op.reason,
    )
    with _project_path(project_id).open("a", encoding="utf-8") as f:
        f.write(event.model_dump_json() + "\n")
    return event


def load_correction_events(project_id: str) -> list[CorrectionEvent]:
    p = _project_path(project_id)
    if not p.exists():
        return []
    out: list[CorrectionEvent] = []
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(CorrectionEvent.model_validate_json(line))
    return out


def apply_corrections(lines: list[dict], events: list[CorrectionEvent]) -> list[dict]:
    """Replay correction events onto a lines array.

    Order matters: events are applied in chronological order. The latest
    `update` wins; `verify` upgrades source to "verified" without changing
    the value.
    """
    out: list[dict] = [{**line} for line in lines]
    for event in events:
        if event.target_type != "quantity_line":
            continue
        if event.op == "update":
            for line in out:
                if line.get("code") == event.target_code:
                    if event.after:
                        line.update(event.after)
                    line["source"] = "user"
        elif event.op == "verify":
            for line in out:
                if line.get("code") == event.target_code:
                    line["source"] = "verified"
    return out


@router.post("/{project_id}")
def post_corrections(project_id: str, batch: CorrectionBatch) -> dict[str, Any]:
    if batch.project_id != project_id:
        raise HTTPException(
            status_code=400,
            detail=f"Body project_id ({batch.project_id}) does not match URL ({project_id})",
        )
    n = 0
    for op in batch.operations:
        append_correction(project_id, op)
        n += 1
    return {"applied": n}


@router.get("/{project_id}", response_model=CorrectionLog)
def get_corrections(project_id: str) -> CorrectionLog:
    return CorrectionLog(
        project_id=project_id,
        events=load_correction_events(project_id),
    )
