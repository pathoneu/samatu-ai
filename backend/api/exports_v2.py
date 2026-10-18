"""F2/F3 export HTTP API (Week 7 Task 7.1).

Endpoints:
  GET /api/export/v2/f2/{project_id}.json?vat_mode=...  → F2Export JSON
  GET /api/export/v2/f2/{project_id}.csv?vat_mode=...   → CSV stream
  GET /api/export/v2/f3/{project_id}.json?vat_mode=...  → F3Export JSON

Reads:
  - lines from data/projects/<project_id>/lines.json (when present)

The customer-facing audit column is not currently sourced: the legacy
corrections_v2 JSONL store was removed (2026-06-21). The durable correction
log now lives in the `corrections` DB table (db.list_corrections); wiring the
F2/F3 audit column at it is a follow-up — its schema (field_path / room_nr /
JSON-string values) differs from the audit_trail row shape, so it needs a
translation pass before it can be spliced in.

When the project store is not yet wired, the endpoint returns 501 with a
clear message — the export builder is fully tested via direct
function calls in `backend/tests/extractor/test_f2_export.py`.
"""
from __future__ import annotations

import io
import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response

import auth as _auth
import db
import storage as _storage
from extractor.audit_trail import audit_trail_rows
from extractor.f2_export import (
    build_f2_export,
    export_to_csv,
)

router = APIRouter(prefix="/api/export/v2", tags=["export"])

# 2026-07-27 audit (finding 6): repo-root/data/projects is inside the container
# image on Render. SAMATU_DATA_DIR re-roots it at the persistent disk; unset →
# the legacy path, unchanged.
PROJECTS_DIR = _storage.data_path(
    "projects", Path(__file__).resolve().parents[2] / "data" / "projects")


def _require_project_access(request: Request, project_id: str) -> dict:
    """Auth + ownership gate for every F2/F3 export route.

    Closes an IDOR / unauthenticated-data-exposure gap (2026-06-21): these routes
    previously took only a project_id path param, so any caller who knew (or
    guessed) a project UUID could GET the project's full priced line-item export
    (quantities + unit prices + grand totals) with no login and no ownership
    check. Delegates to the canonical gate, auth.require_owned_project
    (require_user → admin sees all, otherwise scope db.get_project to user["id"]).

    Raises 401 if not logged in, and 404 — the same answer — both when the
    project belongs to another user and when there is no such project, so the
    API never says whether an id exists (docs/SECURITY.md §3; these routes
    answered 403 for a foreign project until 2026-09-29). Returns the caller's
    user dict.
    """
    user = _auth.require_owned_project(request, project_id)
    # Tier gate (billing M1): F2/F3 belong to the paid plans. Ownership first —
    # a foreign id is a 404 before any plan is looked at. A no-op while
    # BILLING_ENABLED is off.
    from billing.entitlements import require_feature
    require_feature(user, "f2f3_export")
    return user


_SALTINIS_TO_F2_SOURCE = {
    "ai_vision": "ai", "vision": "ai",
    "skaiciuota_is_brezinio": "rule", "rule": "rule",
    "paskirtis_default": "rule",
    "user_override": "user",
    "rankinis": "user",
    "patikrinta": "verified", "verified": "verified",
    "baseline": "rule",
}


def _pozicija_to_line(p: dict, idx: int) -> dict:
    """Translate the LT `pozicija` record stored in db into the line shape
    f2_export expects. Pure: no I/O, easy to swap for unit tests.
    """
    code = (p.get("code") or p.get("kodas")
            or p.get("id") or f"poz-{idx + 1:03d}")
    saltinis = (p.get("saltinis") or p.get("source") or "rule").lower()
    confidence = "green" if p.get("verified") else (
        p.get("confidence") or "yellow"
    )
    return {
        "code": str(code),
        "label_lt": p.get("aprasymas") or p.get("label_lt") or "",
        "unit": p.get("vnt") or p.get("unit") or "",
        "quantity": float(p.get("kiekis") or p.get("quantity") or 0),
        "unit_price_eur_be_pvm": p.get("ikainis_eur")
            or p.get("unit_price_eur_be_pvm"),
        "confidence": confidence,
        "source": _SALTINIS_TO_F2_SOURCE.get(saltinis, "rule"),
        "source_pages": p.get("source_pages") or (
            [p["puslapio_nr"]] if p.get("puslapio_nr") else []
        ),
        "notes": p.get("notes") or p.get("pastabos"),
    }


def _load_project_lines(project_id: str) -> list[dict]:
    """Lines come from one of two sources, in priority order:

    1. `data/projects/<id>/lines.json` — explicit per-project override
       a samatininkas can hand-edit before export.
    2. The live project record's `pozicijos[]` field — the same data the
       Kiekiai tab renders, translated into F2Row's expected shape.

    Pre-2026-05-10 only #1 was supported, so every project hit 501. Now
    falling through to #2 means F2/F3 export Just Works™ for any saved
    project.
    """
    override = PROJECTS_DIR / project_id / "lines.json"
    if override.exists():
        return json.loads(override.read_text(encoding="utf-8"))

    project = db.get_project(project_id)
    if not project:
        raise HTTPException(
            status_code=404,
            detail=f"Project {project_id} not found.",
        )
    pozicijos = project.get("pozicijos") or []
    if not pozicijos:
        raise HTTPException(
            status_code=409,
            detail=(
                "Project has no pozicijos[] yet. Run extraction or place "
                f"a manual line list at data/projects/{project_id}/lines.json."
            ),
        )
    # togal-v2 W9: the „Kodas" column prints the row's cost code — his typed
    # one (it lives on darbu_sarasas), else the rinkinys / family / section
    # code — instead of the row's internal id. A legacy row with nothing to
    # go on keeps the old id fallback.
    from api.sudetis import effective_kodas
    by_id = {str(r.get("id")): r for r in (project.get("darbu_sarasas") or [])
             if isinstance(r, dict) and r.get("id")}
    lines = []
    for i, p in enumerate(pozicijos):
        src = {**p, **{k: by_id[str(p.get("id"))][k]
                       for k in ("kodas", "rinkinys_id", "skyrius_enum")
                       if str(p.get("id")) in by_id and by_id[str(p.get("id"))].get(k) is not None}}
        kodas = None if p.get("code") else effective_kodas(src, _own_assemblies(project))
        lines.append(_pozicija_to_line({**p, "kodas": kodas} if kodas else p, i))
    return lines


def _own_assemblies(project: dict) -> list[dict]:
    try:
        uid = project.get("user_id")
        return db.list_assemblies(user_id=uid) if uid else []
    except Exception:  # noqa: BLE001 — his own codes are an extra
        return []


def _audit_rows(project_id: str) -> list[dict]:
    # The legacy corrections_v2 JSONL store (the only source that ever fed this
    # audit column) was removed 2026-06-21. The durable correction log lives in
    # the `corrections` DB table now, but its schema differs from the
    # audit_trail row shape and F2/F3 is not exposed in the UI, so emit no audit
    # rows until that translation is built. Returns [] — same behaviour the
    # endpoint had in production, where the JSONL was never written.
    return audit_trail_rows([])


@router.get("/f2/{project_id}.json", dependencies=[Depends(_require_project_access)])
def export_f2_json(
    project_id: str,
    vat_mode: str = Query("be_pvm", pattern="^(be_pvm|with_pvm|reverse_vat)$"),
    project_age_years: int | None = None,
) -> dict:
    lines = _load_project_lines(project_id)
    audit = _audit_rows(project_id)
    export = build_f2_export(project_id, lines, audit, vat_mode, project_age_years)
    return {
        "project_id": export.project_id,
        "vat_mode": export.vat_mode,
        "project_age_years": export.project_age_years,
        "rows": [r.__dict__ for r in export.rows],
        "grand_total_eur_be_pvm": export.grand_total_eur_be_pvm,
        "grand_total_eur_with_pvm": export.grand_total_eur_with_pvm,
        "pvm_rate": export.pvm_rate,
        "footer_notes": export.footer_notes,
    }


@router.get("/f2/{project_id}.csv", dependencies=[Depends(_require_project_access)])
def export_f2_csv(
    project_id: str,
    vat_mode: str = Query("be_pvm", pattern="^(be_pvm|with_pvm|reverse_vat)$"),
    project_age_years: int | None = None,
) -> Response:
    lines = _load_project_lines(project_id)
    audit = _audit_rows(project_id)
    export = build_f2_export(project_id, lines, audit, vat_mode, project_age_years)
    csv_text = export_to_csv(export)
    return Response(
        content=csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{project_id}.f2.csv"'},
    )


@router.get("/f3/{project_id}.json", dependencies=[Depends(_require_project_access)])
def export_f3_json(
    project_id: str,
    vat_mode: str = Query("be_pvm", pattern="^(be_pvm|with_pvm|reverse_vat)$"),
    project_age_years: int | None = None,
) -> dict:
    """F3 reuses F2 schema; layout split happens at downstream rendering.
    Marker `format=f3` lets the renderer apply different headings.
    """
    body = export_f2_json(project_id, vat_mode, project_age_years)
    body["format"] = "f3"
    return body
