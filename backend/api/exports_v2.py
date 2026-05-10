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

import db
from api.corrections_v2 import load_correction_events
from extractor.audit_trail import audit_trail_rows
from extractor.f2_export import (
    build_f2_export,
    export_to_csv,
)

router = APIRouter(prefix="/api/export/v2", tags=["export"])

PROJECTS_DIR = Path(__file__).resolve().parents[2] / "data" / "projects"


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
    return [_pozicija_to_line(p, i) for i, p in enumerate(pozicijos)]


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
