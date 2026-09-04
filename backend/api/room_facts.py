"""GET /api/projects/{project_id}/rooms/{room_nr}/facts — the room check sheet.

The read side of „AI shows its homework" (2026-09-04). One room, six facts with
the drawing region behind each, and every sąmata line that room contributes to,
from the contribution ledger.

All the judgement lives in `extractor/room_facts.py` so it is testable without
HTTP; this file is auth, scoping, the prose scrubber and the crop URLs.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, Request

import auth as _auth
import db as _db
from extractor import user_text as _user_text
from extractor.room_facts import build_room_facts

log = logging.getLogger("samatu.room_facts")

router = APIRouter(prefix="/api/projects", tags=["room-facts"])


# Plain `def`, like /api/projects/{id}: a sqlite read plus a JSON blob parse,
# and the check sheet fetches one per room as the contractor walks them.
@router.get("/{project_id}/rooms/{room_nr}/facts")
def api_room_facts(request: Request, project_id: str, room_nr: str,
                   dpi: int | None = Query(None, ge=40, le=160)):
    user = _auth.require_user(request)
    user_filter = None if user.get("is_admin") else user["id"]
    project = _db.get_project(project_id, user_id=user_filter)
    if not project:
        raise HTTPException(status_code=404,
                            detail=f"Project {project_id} not found")

    payload = build_room_facts(project, room_nr)
    if payload is None:
        raise HTTPException(status_code=404, detail=f"Patalpa {room_nr} nerasta")

    from extractor.room_facts import attach_crop_urls
    attach_crop_urls(payload, project_id, dpi)
    # Same guard as /api/projects/{id}: prose persisted by an older engine is
    # never trusted on the way out. `sentence` and `formula` are generated
    # fresh here, but `included_because` / `excluded_because` / `reason` ride
    # in from the stored blob.
    return _user_text.scrub_prose(payload)
