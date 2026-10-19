"""POST /api/telemetry/session — frontend POSTs session record at end of session.

Audit backend-security-11 (fixed 2026-10-18): the route was anonymous,
unbounded and unrate-limited, and wrote to the container's own disk. Now: a
login is required, the project must be the caller's (404 otherwise — the same
answer as a missing one), the record is size-bounded, the caller's IP is rate
limited, and the log lives under SAMATU_DATA_DIR when that is set
(TELEMETRY_LOG_PATH still wins).
"""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

import auth as _auth
import db
from telemetry.session_log import append_session, SessionRecord

router = APIRouter(prefix="/api/telemetry", tags=["telemetry"])

MAX_GESTURES = 2000


class SessionPayload(BaseModel):
    project_id: str = Field(min_length=1, max_length=200)
    started_at: int
    finished_at: int
    total_seconds: int
    gestures: list[dict] = Field(default_factory=list, max_length=MAX_GESTURES)
    exported: bool = False


@router.post("/session")
def log_session(payload: SessionPayload, request: Request) -> dict:
    user = _auth.require_user(request)
    from main import _check_rate_limit, _client_key  # lazy: main imports this router
    _check_rate_limit(_client_key(request), "telemetry-session")
    user_filter = None if user.get("is_admin") else user["id"]
    if db.get_project(payload.project_id, user_id=user_filter) is None:
        raise HTTPException(status_code=404, detail=f"Project {payload.project_id} not found")
    record = SessionRecord(**payload.model_dump())
    append_session(record)
    return {"ok": True}
