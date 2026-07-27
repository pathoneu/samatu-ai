"""POST /api/projects/{project_id}/export-excel → Excel file download.

Two sheets:
  - "AI Sąmata" — straight from the calculator's santrauka + per-room
    breakdown.
  - "Patikslinta Sąmata" — same lines with the user's calibration
    factors applied (only present when a calibration exists for this
    project).

The endpoint streams the file; the Annotator wires it to a download
button.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

import db as _db
import auth as _auth
import storage as _storage
from extractor.spreadsheet_safety import sanitize_spreadsheet_cell as _safe

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = {
    "berzas": REPO_ROOT / "docs/superpowers/fixtures/2026-05-26-berzu-g-24/app-output-to-the-dot.json",
}

# Same SAMATU_DATA_DIR root as api/calibrate.py writes to (2026-07-27 audit, 6).
CALIB_ROOT = _storage.data_path(
    "calibrations", Path(__file__).resolve().parents[1] / "data" / "calibrations")


# Headline KŽ rows for the Excel summary. (label, santrauka_field, unit)
KZ_ROWS = [
    ("Dažymo plotas (visas)",         "dazymo_plotas_total_m2",       "m²", "dazymo_plotas_m2"),
    ("Dažymo plotas (be garažo)",     "dazymo_excl_garazas_total_m2", "m²", "dazymo_excl_garazas_m2"),
    ("Sienos / lubos – glaistymas",   "dazymo_plotas_total_m2",       "m²", "dazymo_plotas_m2"),
    ("Dažymo kampai",                 "kampai_m_total",               "m",  "kampu_metrai_m"),
    ("Angokraščiai",                  "angokrasciu_gkp_m_total",      "m",  "angokrasciai_m"),
    ("GKP lubos iki 3m",              "gkp_lubu_m2_total",            "m²", "gkp_lubu_iki_3m_m2"),
    ("GKP lubos virš 3m",             "gkp_lubu_virs_3m_m2_total",    "m²", None),
    ("LED nišų ilgis",                "nisu_metrai_total",            "m",  "led_nisos_m"),
    ("PVC / parketas / laminatas",    "pvc_grindys_m2_total",         "m²", None),
    ("Plytelės grindyse",             "plyteles_grindys_m2_total",    "m²", "plyteles_grindyse_m2"),
    ("Plytelės sienose",              "plyteles_sienos_m2_total",     "m²", "plyteles_sienose_m2"),
    ("Išlyginamasis grindims",        "isliginamasis_m2_total",       "m²", None),
    ("Grindjuostės",                  "grindjuosciu_m_total",         "m",  None),
    ("Hidroizoliacija (vnt)",         "hidroizoliacijos_vnt",         "vnt", None),
]


router = APIRouter(prefix="/api/projects", tags=["export-excel"])


def _load_project(request: Request, project_id: str, fixture: str | None) -> dict[str, Any]:
    """Resolve the parsed KŽ written into the XLSX.

    P2 (2026-07-04 pentest, pass 3): AUTH + URL-project ownership FIRST, ALWAYS —
    BEFORE the fixture branch. Previously ``?fixture=`` returned before
    ``require_user`` ran; the endpoint then called ``_load_calibration(project_id)``
    which reads ``data/calibrations/{URL_id}.json`` keyed by the attacker's URL
    project_id, so an anonymous ``POST /export-excel?fixture=berzas`` produced an
    XLSX leaking another tenant's secret calibration ``user_value`` totals (their
    KNOWN category quantities). The URL project_id keys that per-user store, so it
    MUST be owned regardless of ``fixture``. Fixture may seed the reference body
    only. Mirrors the N1 calibrate fix.
    """
    user = _auth.require_owned_project(request, project_id)  # 401 anon / 404 foreign — MUST precede fixture
    if fixture:
        p = FIXTURES.get(fixture)
        if not p or not p.exists():
            raise HTTPException(status_code=404, detail=f"unknown fixture: {fixture}")
        return json.loads(p.read_text(encoding="utf-8"))
    user_filter = None if user.get("is_admin") else user["id"]
    proj = _db.get_project(project_id, user_id=user_filter)
    if not proj:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    return proj


def _load_calibration(project_id: str) -> dict[str, Any] | None:
    p = CALIB_ROOT / f"{project_id}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _write_kz_sheet(ws, parsed: dict[str, Any], calibration: dict[str, Any] | None) -> None:
    title_font = Font(bold=True, size=12)
    header_font = Font(bold=True)
    header_fill = PatternFill(start_color="FFEEEEEE", end_color="FFEEEEEE", fill_type="solid")
    align_left = Alignment(horizontal="left")
    align_right = Alignment(horizontal="right")

    santrauka = parsed.get("santrauka") or {}
    # F6 (2026-07-04 pentest): the project name is user/AI-supplied text — a
    # leading = + - @ would be evaluated as a formula when the .xlsx is opened.
    project_name = _safe(parsed.get("pavadinimas") or parsed.get("name") or "Projektas")

    ws["A1"] = project_name
    ws["A1"].font = title_font
    ws.merge_cells("A1:D1")

    ws["A3"] = "Kategorija"
    ws["B3"] = "AI"
    ws["C3"] = "Patikslinta"
    ws["D3"] = "Vnt."
    for cell in (ws["A3"], ws["B3"], ws["C3"], ws["D3"]):
        cell.font = header_font
        cell.fill = header_fill

    factors = (calibration or {}).get("factors") or {}
    row = 4
    for label, field, unit, calib_key in KZ_ROWS:
        ai_val = float(santrauka.get(field) or 0)
        ws.cell(row=row, column=1, value=label).alignment = align_left
        ws.cell(row=row, column=2, value=round(ai_val, 2)).alignment = align_right

        calibrated_val = None
        if calib_key and calib_key in factors and factors[calib_key].get("applied"):
            calibrated_val = round(ai_val * float(factors[calib_key]["factor"]), 2)
            # If the user set an explicit override, prefer it
            if "user_value" in factors[calib_key]:
                calibrated_val = round(float(factors[calib_key]["user_value"]), 2)
        if calibrated_val is not None:
            cc = ws.cell(row=row, column=3, value=calibrated_val)
            cc.alignment = align_right
            cc.font = Font(bold=True, color="FF92400E")  # amber-700
        ws.cell(row=row, column=4, value=unit).alignment = align_left
        row += 1

    # Column widths
    ws.column_dimensions["A"].width = 36
    ws.column_dimensions["B"].width = 14
    ws.column_dimensions["C"].width = 14
    ws.column_dimensions["D"].width = 8

    # Per-room block
    row += 2
    ws.cell(row=row, column=1, value="Patalpos").font = title_font
    row += 1
    for h, c in zip(
        ("Nr.", "Pavadinimas", "Plotas (m²)", "Perimetras (m)", "Dažymas (m²)"),
        (1, 2, 3, 4, 5),
    ):
        cell = ws.cell(row=row, column=c, value=h)
        cell.font = header_font
        cell.fill = header_fill
    row += 1
    for r in parsed.get("patalpos") or []:
        # F6: room nr + name are user/AI text — neutralise formula injection.
        # Plotas / perimetras / dažymas stay numeric (untouched).
        ws.cell(row=row, column=1, value=_safe(str(r.get("nr") or "")))
        ws.cell(row=row, column=2, value=_safe(str(r.get("pavadinimas") or "")))
        ws.cell(row=row, column=3, value=round(float(r.get("plotas_m2") or 0), 2)).alignment = align_right
        ws.cell(row=row, column=4, value=round(float(r.get("perimetras_m") or 0), 2)).alignment = align_right
        ws.cell(row=row, column=5, value=round(float(r.get("dazymo_plotas_m2") or 0), 2)).alignment = align_right
        row += 1


@router.post("/{project_id}/export-excel")
async def export_excel(
    request: Request,
    project_id: str,
    fixture: str | None = Query(default=None),
) -> StreamingResponse:
    parsed = _load_project(request, project_id, fixture)
    calibration = _load_calibration(project_id)

    wb = Workbook()
    ws_ai = wb.active
    ws_ai.title = "AI Sąmata"
    _write_kz_sheet(ws_ai, parsed, calibration=None)

    if calibration:
        ws_calib = wb.create_sheet("Patikslinta Sąmata")
        _write_kz_sheet(ws_calib, parsed, calibration=calibration)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    fname = f"samata-{project_id}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )
