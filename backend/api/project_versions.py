"""Project versions: list, read, compare, restore (togal-v2 W10, 2026-10-16).

    GET  /api/projects/{id}/versions                   → [{id, created_at, saltinis, pavadinimas,
                                                          dydis, suspausta, dabartine}] newest first
    GET  /api/projects/{id}/versions/{vid}             → the version with its data
    GET  /api/projects/{id}/versions/{a}/diff/{b}      → api.version_diff.diff_projects(a, b);
                                                          either side may be „dabartine" (the
                                                          project as it is now)
    POST /api/projects/{id}/versions/{vid}/restore     → the project becomes that version; the
                                                          state it replaces is kept first as a
                                                          'grazinta' version

The versions are written by `db.upsert_project` itself (see db.py, block above
`versions_to_keep`). Every handler checks ownership before it looks at anything
else, and answers 404 alike for a project that is not the caller's and one that
does not exist. Nothing here calls a model.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request

import auth as _auth
import db as _db
from api.version_diff import diff_projects
from extractor import user_text

log = logging.getLogger("samatu.project_versions")

router = APIRouter(prefix="/api/projects", tags=["project-versions"])

CURRENT = "dabartine"
NOT_FOUND = "Projektas nerastas"
NO_VERSION = "Tokios versijos nėra"


def _owner(request: Request, project_id: str) -> str | None:
    """The user filter for this caller, after checking the project is theirs."""
    user = _auth.require_user(request)
    user_filter = None if user.get("is_admin") else user["id"]
    if not _db.project_version_owner_ok(project_id, user_filter):
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    return user_filter


def _side(project_id: str, ref: str, user_filter: str | None) -> dict:
    if ref == CURRENT:
        p = _db.get_project(project_id, user_id=user_filter)
        if not p:
            raise HTTPException(status_code=404, detail=NOT_FOUND)
        return p
    v = _db.get_project_version(project_id, ref, user_id=user_filter)
    if v is None:
        raise HTTPException(status_code=404, detail=NO_VERSION)
    return v["data"]


@router.get("/{project_id}/versions")
def list_versions(request: Request, project_id: str):
    user_filter = _owner(request, project_id)
    versions = _db.list_project_versions(project_id, user_filter)
    if versions is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    return {"versions": versions}


@router.get("/{project_id}/versions/{version_id}")
def get_version(request: Request, project_id: str, version_id: str):
    user_filter = _owner(request, project_id)
    v = _db.get_project_version(project_id, version_id, user_id=user_filter)
    if v is None:
        raise HTTPException(status_code=404, detail=NO_VERSION)
    v["data"] = user_text.scrub_prose(v["data"])
    return v


@router.get("/{project_id}/versions/{a}/diff/{b}")
def diff_versions(request: Request, project_id: str, a: str, b: str):
    user_filter = _owner(request, project_id)
    return diff_projects(_side(project_id, a, user_filter), _side(project_id, b, user_filter))


@router.post("/{project_id}/versions/{version_id}/restore")
def restore_version(request: Request, project_id: str, version_id: str):
    user_filter = _owner(request, project_id)
    saved = _db.restore_project_version(project_id, version_id, user_id=user_filter)
    if saved is None:
        raise HTTPException(status_code=404, detail=NO_VERSION)
    log.info("project %s restored to version %s", project_id, version_id)
    return user_text.scrub_prose(saved)
