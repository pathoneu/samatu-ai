"""Annotation persistence for the upcoming PDF Annotator UI.

GET  /api/projects/{project_id}/annotations  → load saved canvas + symbols
PUT  /api/projects/{project_id}/annotations  → overwrite with new payload

Storage is file-based under ``backend/data/annotations/{project_id}.json``
so the feature works the moment the frontend ships, without depending on
Firestore / Postgres. When the project moves to a real DB this module
becomes a thin facade; the on-disk format is the canonical schema.

The payload is a free-form JSON object — callers (the Fabric.js canvas)
serialise their own state via ``fabric.Canvas.toJSON()`` and we round-trip
it untouched. The only invariants we enforce:
  - payload must be a JSON object (not array / scalar)
  - max 256 KB per project (rejects abuse)
  - schema_version key is rewritten on save so old clients know whether
    to migrate
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Request

import auth as _auth
import db as _db

# Storage root. Lives under backend/data so it inherits the existing
# .gitignore rule (backend/data/*.db) without polluting source control.
DATA_ROOT = Path(__file__).resolve().parents[1] / "data" / "annotations"
DATA_ROOT.mkdir(parents=True, exist_ok=True)

SCHEMA_VERSION = 1
MAX_PAYLOAD_BYTES = 256 * 1024

router = APIRouter(prefix="/api/projects", tags=["annotations"])


def _path_for(project_id: str) -> Path:
    # Basic safety: project_id is user-supplied — reject anything that could
    # escape the data directory. Project IDs in the existing app are uuid4
    # strings; allow alnum / dash / underscore only.
    if not project_id or not all(c.isalnum() or c in ("-", "_") for c in project_id):
        raise HTTPException(status_code=400, detail="invalid project_id")
    return DATA_ROOT / f"{project_id}.json"


def _require_project_access(request: Request, project_id: str) -> dict:
    """Auth + ownership gate (F1, 2026-07-04 pentest).

    These file-backed annotation routes previously had NO auth and NO ownership
    check — any anonymous caller who knew a project UUID could read/overwrite/
    DELETE that project's annotations. Mirror the owner-scoping guard used across
    main.py's project routes and exports_v2._require_project_access: require a
    logged-in user (401 if not), then scope db.get_project to the caller (admins
    see all). A missing/foreign project returns 404 — NOT 403 — so we don't leak
    the existence of other users' projects. Returns the caller's user dict.
    """
    user = _auth.require_user(request)  # 401 if not logged in
    user_filter = None if user.get("is_admin") else user["id"]
    if _db.get_project(project_id, user_id=user_filter) is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    return user


@router.get("/{project_id}/annotations")
def get_annotations(project_id: str, request: Request) -> dict[str, Any]:
    """Return the saved annotation payload for a project, or an empty
    stub when nothing is saved yet."""
    _require_project_access(request, project_id)
    p = _path_for(project_id)
    if not p.exists():
        return {
            "schema_version": SCHEMA_VERSION,
            "project_id": project_id,
            "canvas": None,
            "symbols": [],
            "measurements": [],
            "calibration_scale_mm_per_px": None,
            "updated_at": None,
        }
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"corrupt store: {exc}") from exc


@router.put("/{project_id}/annotations")
def put_annotations(
    project_id: str,
    request: Request,
    payload: dict[str, Any] = Body(...),
) -> dict[str, Any]:
    """Overwrite the project's annotation payload.

    Accepts any JSON object up to 256 KB. We don't validate the Fabric.js
    canvas structure server-side — the client owns its serialisation
    format. We just stamp ``schema_version`` and ``updated_at`` so
    consumers can detect staleness.
    """
    _require_project_access(request, project_id)
    p = _path_for(project_id)

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="payload must be a JSON object")

    body = json.dumps(payload, ensure_ascii=False)
    if len(body.encode("utf-8")) > MAX_PAYLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"payload exceeds {MAX_PAYLOAD_BYTES} bytes",
        )

    payload["schema_version"] = SCHEMA_VERSION
    payload["project_id"] = project_id
    payload["updated_at"] = int(time.time())

    # Atomic write
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)

    return {"ok": True, "updated_at": payload["updated_at"]}


@router.delete("/{project_id}/annotations")
def delete_annotations(project_id: str, request: Request) -> dict[str, Any]:
    _require_project_access(request, project_id)
    p = _path_for(project_id)
    existed = p.exists()
    if existed:
        p.unlink()
    return {"ok": True, "existed": existed}
