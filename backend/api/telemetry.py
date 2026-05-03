"""POST /api/telemetry/session — frontend POSTs session record at end of session."""
from fastapi import APIRouter
from pydantic import BaseModel
from telemetry.session_log import append_session, SessionRecord

router = APIRouter(prefix="/api/telemetry", tags=["telemetry"])


class SessionPayload(BaseModel):
    project_id: str
    started_at: int
    finished_at: int
    total_seconds: int
    gestures: list[dict]
    exported: bool = False


@router.post("/session")
def log_session(payload: SessionPayload) -> dict:
    record = SessionRecord(**payload.model_dump())
    append_session(record)
    return {"ok": True}
