"""POST /api/projects/{project_id}/revalidate — re-run AI patikrinimai
on already-extracted project data without re-uploading the PDF.

Why: validators (cross_page_validator + apply_lt_sanity) only run during
the original /extract-interior call. After the underlying validator code
gets bug-fixed (e.g. the 2026-05-10 room_aukstas_from_nr fix that
mis-parsed "1.2" as floor 1), every existing project keeps its old stale
warnings until the PDF is re-uploaded.

This endpoint reads the saved project payload, re-runs the same two
validators that the live extract pipeline runs, rebuilds the
`lt_sanity` UI mirror, persists the freshened warnings, and returns the
updated payload so the frontend can swap state without a full reload.

Auth: same as GET /api/projects — owner or admin.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request

import auth as _auth
import db

log = logging.getLogger("samatu_ai")

router = APIRouter(prefix="/api/projects", tags=["revalidate"])


def _build_lt_sanity_mirror(parsed: dict, rooms_count: int) -> dict:
    """Mirror of the same shape main.py emits at /extract-interior + /recompute-interior.

    Frontend's SanityWarningsBanner reads `project.lt_sanity.warnings[]`,
    so we have to keep this payload byte-compatible with the original
    extractor pipeline. Ref: backend/main.py around line 4742.
    """
    flat_warnings = parsed.get("_lt_warnings") or []
    ui_warnings: list[dict] = []
    for w in flat_warnings:
        level = w.get("level", "INFO")
        if level == "WARN":
            level = "WARNING"
        ui_warnings.append({
            "level": level,
            "room": w.get("patalpa_nr") or w.get("room") or "",
            "field": w.get("field", ""),
            "value": w.get("value"),
            "expected": w.get("expected"),
            "message": w.get("message", ""),
        })
    n_err = sum(1 for w in ui_warnings if w["level"] == "ERROR")
    n_warn = sum(1 for w in ui_warnings if w["level"] == "WARNING")
    n_info = sum(1 for w in ui_warnings if w["level"] == "INFO")
    return {
        "warnings": ui_warnings,
        "summary": {
            "rooms_count": rooms_count,
            "total_area_m2": round(parsed.get("bendras_plotas_m2", 0) or 0, 1),
            "warnings_count": n_err + n_warn,
            "errors": n_err,
            "warnings": n_warn,
            "info": n_info,
        },
    }


def _revalidate_payload(payload: dict) -> dict:
    """Run cross_page_validator + apply_lt_sanity on the project payload,
    return a NEW dict with refreshed warnings.

    Pure function — no DB writes. Safe to unit-test.
    """
    # Defensive copy so a partial run can't half-update the saved blob.
    parsed = dict(payload)
    rooms = parsed.get("patalpos") or []

    # 1. cross_page_validator (eksplikacija sums, multi-floor reconciliation,
    # door/window count cross-checks, etc.). Append warnings to the same
    # `warnings` list the extractor pipeline uses so downstream consumers
    # don't need to know which validator emitted what.
    cross_warnings: list[dict] = []
    try:
        from extractor.cross_page_validator import validate_consistency
        cross_warnings = validate_consistency(parsed) or []
    except Exception:
        # Don't fail the whole revalidate if one rule throws — but do NOT put
        # str(exc) in front of the user (2026-07-28 audit): these warnings render
        # verbatim in SanityWarningsBanner, so a stack-y Python message ("KeyError:
        # 'plotas_m2'", a file path) ended up in the estimator's UI — noise to
        # them, internals leaked to anyone they share the screen with. Generic LT
        # in the UI, full traceback in the log.
        log.exception("revalidate: validate_consistency failed")
        cross_warnings = [{
            "level": "WARN",
            "field": "cross_page_validator",
            "message": "Nepavyko atlikti kryžminio puslapių patikrinimo — "
                       "kiekius patikrinkite rankiniu būdu.",
            "source": "revalidate",
        }]

    # Replace prior cross_page warnings (same `source` tag) so re-running
    # doesn't accumulate stale entries; KEEP warnings tagged from anywhere
    # else (e.g. the large-PDF banner emitted at upload time).
    existing = [
        w for w in (parsed.get("warnings") or [])
        if w.get("source") not in ("cross_page_validator", "revalidate")
    ]
    for w in cross_warnings:
        existing.append({
            "level": (w.get("level") or "WARN").upper(),
            "field": w.get("field", ""),
            "patalpa_nr": w.get("patalpa_nr"),
            "message": w.get("message_lt") or w.get("message", ""),
            "suggestion": w.get("suggestion"),
            "source": "cross_page_validator",
        })
    parsed["warnings"] = existing

    # 2. apply_lt_sanity (STR rules, mansardinis svoris, area/perimeter sanity).
    # This rebuilds parsed["_lt_warnings"] in-place AND mutates room rounding
    # but never mutates a quantity in a way that affects pricing.
    try:
        from extractor.lt_rules import apply_lt_sanity
        parsed = apply_lt_sanity(parsed)
    except Exception:
        log.exception("revalidate: apply_lt_sanity failed")
        parsed.setdefault("warnings", []).append({
            "level": "WARN",
            "field": "lt_sanity",
            "message": "Nepavyko pritaikyti LT taisyklių patikros — "
                       "kiekius patikrinkite rankiniu būdu.",
            "source": "revalidate",
        })

    # 3. Rebuild the UI mirror that SanityWarningsBanner consumes.
    parsed["lt_sanity"] = _build_lt_sanity_mirror(parsed, rooms_count=len(rooms))
    parsed["_revalidated"] = True
    return parsed


@router.post("/{project_id}/revalidate")
async def revalidate_project(request: Request, project_id: str) -> dict:
    """Re-run AI patikrinimai on the saved project; persist + return."""
    user = _auth.require_user(request)
    user_filter = None if user.get("is_admin") else user["id"]
    project = db.get_project(project_id, user_id=user_filter)
    if not project:
        raise HTTPException(
            status_code=404, detail=f"Project {project_id} not found",
        )

    refreshed = _revalidate_payload(project)
    try:
        db.upsert_project(project_id, refreshed, user_id=user["id"])
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    return {
        "status": "ok",
        "warnings_count": refreshed.get("lt_sanity", {})
                                   .get("summary", {})
                                   .get("warnings_count", 0),
        "rooms_count": len(refreshed.get("patalpos") or []),
        "lt_sanity": refreshed.get("lt_sanity"),
        # Also return updated rooms so the frontend can refresh aukstas
        # grouping in the UI sidebar without a full project reload.
        "patalpos": refreshed.get("patalpos") or [],
    }
