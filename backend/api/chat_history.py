"""GET / PUT /api/projects/{project_id}/chat-history — Pokalbis keeps its history per project across reloads
(Pathon v3 W5-C, C12 F-chat-history).

The chat lived in React state only: a reload, another tab or tomorrow's visit started it empty, and the
question he asked about room 04 yesterday was gone. The history is a small list of plain messages — the
question and the answer text, the thumbs he gave, what the chat was given — kept in its OWN table, never in
the project blob (the browser writes the whole blob back on every save; a server-side field there would be
lost to the next save from an older cached copy).

Owner-gated like every project route (ownership before anything else), bounded (the newest MAX_MESSAGES,
each text cut at MAX_TEXT), no model call. PUT replaces the list; an empty list clears it — the browser keeps
the previous list for its „Atšaukti".
"""
from __future__ import annotations

import json
import logging
from typing import Any, Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

import db as _db
from api.free_reread import _project_for

log = logging.getLogger("samatu.chat_history")

router = APIRouter(prefix="/api/projects", tags=["chat-history"])

MAX_MESSAGES = 100
MAX_TEXT = 4000

_SCHEMA = """
CREATE TABLE IF NOT EXISTS chat_history (
    project_id  TEXT PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
    messages    TEXT NOT NULL,
    updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
)
"""


def _ensure(c) -> None:
    c.execute(_SCHEMA)


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    text: str = Field(max_length=20000)
    isError: bool | None = None
    vote: Literal["up", "down"] | None = None
    question: str | None = Field(default=None, max_length=2000)
    given: Any = None


class ChatHistoryBody(BaseModel):
    messages: list[ChatMessage] = Field(default_factory=list, max_length=1000)


def clean_messages(messages: list[dict]) -> list[dict]:
    """The newest MAX_MESSAGES, each text cut at MAX_TEXT, only the known keys, empty texts dropped."""
    out: list[dict] = []
    for m in messages[-MAX_MESSAGES:]:
        text = str(m.get("text") or "")[:MAX_TEXT]
        if not text.strip():
            continue
        item = {"role": m.get("role"), "text": text}
        for k in ("isError", "vote", "question"):
            if m.get(k) not in (None, ""):
                item[k] = m[k] if k != "question" else str(m[k])[:2000]
        if isinstance(m.get("given"), (dict, list)):
            given = json.dumps(m["given"], ensure_ascii=False)
            if len(given) <= 4000:
                item["given"] = m["given"]
        out.append(item)
    return out


def read_history(project_id: str) -> list[dict]:
    with _db._conn() as c:
        _ensure(c)
        row = c.execute("SELECT messages FROM chat_history WHERE project_id = ?", (project_id,)).fetchone()
    if not row:
        return []
    try:
        data = json.loads(row["messages"] or "[]")
        return data if isinstance(data, list) else []
    except (TypeError, ValueError):
        log.warning("chat history of %s is unreadable — starting empty", project_id)
        return []


def write_history(project_id: str, messages: list[dict]) -> None:
    with _db._conn() as c:
        _ensure(c)
        if not messages:
            c.execute("DELETE FROM chat_history WHERE project_id = ?", (project_id,))
            return
        c.execute(
            "INSERT INTO chat_history (project_id, messages, updated_at) VALUES (?, ?, strftime('%Y-%m-%dT%H:%M:%SZ', 'now')) "
            "ON CONFLICT(project_id) DO UPDATE SET messages = excluded.messages, updated_at = excluded.updated_at",
            (project_id, json.dumps(messages, ensure_ascii=False)),
        )


@router.get("/{project_id}/chat-history")
def api_chat_history(request: Request, project_id: str):
    _project_for(request, project_id)
    return {"messages": read_history(project_id)}


@router.put("/{project_id}/chat-history")
def api_chat_history_put(request: Request, project_id: str, body: ChatHistoryBody):
    _project_for(request, project_id)
    messages = clean_messages([m.model_dump() for m in body.messages])
    write_history(project_id, messages)
    return {"status": "ok", "count": len(messages)}
