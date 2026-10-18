"""GET /api/projects/{project_id}/questions — Patikra as a short list of questions.

The read side of „programa siūlo — jūs patvirtinate" (2026-09-21): everything in the project that
still waits for a person, grouped by kind, each with the program's own proposed answer. All the
judgement lives in `extractor/project_questions.py` (and, under it, in the very facts the room sheet
shows); this file is auth, owner scoping and the prose scrubber. Saves nothing.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request

import auth as _auth
import db as _db
from extractor import user_text as _user_text
from extractor.project_questions import build_questions

log = logging.getLogger("samatu.project_questions")

router = APIRouter(prefix="/api/projects", tags=["project-questions"])


# Plain `def`, like the room facts: a sqlite read plus pure work on the stored blob.
@router.get("/{project_id}/questions")
def api_project_questions(request: Request, project_id: str):
    """`?lenteles=1` adds the questions that set the drawing's schedules against what was read elsewhere
    (extractor/project_questions.RECONCILE_KINDS) — asked for by a check sheet that can answer them. Read
    from the query by hand, AFTER the owner check (a typed parameter would be validated before it)."""
    user = _auth.require_user(request)
    user_filter = None if user.get("is_admin") else user["id"]
    project = _db.get_project(project_id, user_id=user_filter)
    if not project:
        raise HTTPException(status_code=404, detail="Projektas nerastas")
    lenteles = str(request.query_params.get("lenteles") or "").strip().lower() in ("1", "true", "taip")
    try:
        payload = build_questions(project, lenteles=lenteles)
    except Exception as exc:  # noqa: BLE001 — a malformed legacy blob is not a 500 trace
        log.error("project questions failed project=%s: %r", project_id, exc)
        raise HTTPException(status_code=500,
                            detail="Nepavyko sudaryti klausimų sąrašo — atidarykite patalpas po vieną") from exc
    # sentences ride in from the facts, and those may quote prose an older engine stored
    return _user_text.scrub_prose(payload)
