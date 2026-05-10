"""F2/F3 export HTTP API (Week 7 Task 7.1).

Endpoints:
  GET /api/export/v2/f2/{project_id}.json?vat_mode=...  → F2Export JSON
  GET /api/export/v2/f2/{project_id}.csv?vat_mode=...   → CSV stream
  GET /api/export/v2/f3/{project_id}.json?vat_mode=...  → F3Export JSON

Reads:
  - lines from data/projects/<project_id>/lines.json (when present)
  - corrections from data/corrections/<project_id>.jsonl (Week 5)

When the project store is not yet wired, the endpoint returns 501 with a
clear message — the export builder is fully tested via direct
function calls in `backend/tests/extractor/test_f2_export.py`.
"""
from __future__ import annotations

import io
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from backend.api.corrections_v2 import load_correction_events
from backend.extractor.audit_trail import audit_trail_rows
from backend.extractor.f2_export import (
    build_f2_export,
    export_to_csv,
)

router = APIRouter(prefix="/api/export/v2", tags=["export"])

PROJECTS_DIR = Path(__file__).resolve().parents[2] / "data" / "projects"


def _load_project_lines(project_id: str) -> list[dict]:
    p = PROJECTS_DIR / project_id / "lines.json"
    if not p.exists():
        raise HTTPException(
            status_code=501,
            detail=(
                "Project lines store not wired yet. Place a JSON list of "
                f"line dicts at data/projects/{project_id}/lines.json or "
                "extend this endpoint to read from the live extraction "
                "result store."
            ),
        )
    return json.loads(p.read_text(encoding="utf-8"))


def _audit_rows(project_id: str) -> list[dict]:
    events = load_correction_events(project_id)
    return audit_trail_rows([e.model_dump() for e in events])


@router.get("/f2/{project_id}.json")
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


@router.get("/f2/{project_id}.csv")
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


@router.get("/f3/{project_id}.json")
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
