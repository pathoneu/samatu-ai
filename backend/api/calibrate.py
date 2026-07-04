"""POST /api/projects/{project_id}/calibrate

The user enters their KNOWN totals for a few headline categories
(e.g. angokraščiai 89.39 m). The endpoint:

  1. Loads the project's saved KŽ (or the fixture for demo).
  2. For each override, computes ``factor = user_value / ai_value``.
  3. Stores the overrides + derived factors in a per-project JSON file
     under ``backend/data/calibrations/{project_id}.json``.
  4. Returns ``{ai, calibrated, factors, overrides}`` so the UI can
     render side-by-side.

Crucially: the endpoint NEVER modifies the global calculator. Each
contractor's calibration lives next to their project; the eval keeps
measuring the raw formula. When the contractor's project ships, the
final KŽ uses their calibration. When more truth files come in, we
optionally promote a calibration to the global formula via a separate
review process (not implemented here — explicit guardrail).
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query, Request

import db as _db
import auth as _auth

REPO_ROOT = Path(__file__).resolve().parents[2]
CALIB_ROOT = Path(__file__).resolve().parents[1] / "data" / "calibrations"
CALIB_ROOT.mkdir(parents=True, exist_ok=True)

FIXTURES = {
    "berzas": REPO_ROOT / "docs/superpowers/fixtures/2026-05-26-berzu-g-24/app-output-to-the-dot.json",
}

# Map of override-key → accessor returning the AI value from a parsed
# extract. Add new keys by extending this table; the endpoint
# automatically supports any new metric.
def _santrauka_field(parsed: dict, field: str) -> float:
    return float((parsed.get("santrauka") or {}).get(field) or 0.0)


def _sum_room_field(parsed: dict, field: str) -> float:
    return float(sum(float(r.get(field) or 0)
                     for r in (parsed.get("patalpos") or [])))


METRIC_ACCESSORS: dict[str, dict[str, Any]] = {
    "angokrasciai_m": {
        "label": "Angokraščiai",
        "unit": "m",
        "accessor": lambda p: _santrauka_field(p, "angokrasciu_gkp_m_total"),
    },
    "dazymo_plotas_m2": {
        "label": "Dažymo plotas",
        "unit": "m²",
        "accessor": lambda p: _santrauka_field(p, "dazymo_plotas_total_m2"),
    },
    "dazymo_excl_garazas_m2": {
        "label": "Dažymo plotas (be garažo)",
        "unit": "m²",
        "accessor": lambda p: _santrauka_field(p, "dazymo_excl_garazas_total_m2"),
    },
    "plyteles_sienose_m2": {
        "label": "Plytelės sienose",
        "unit": "m²",
        "accessor": lambda p: _santrauka_field(p, "plyteles_sienos_m2_total"),
    },
    "plyteles_grindyse_m2": {
        "label": "Plytelės grindyse",
        "unit": "m²",
        "accessor": lambda p: _santrauka_field(p, "plyteles_grindys_m2_total"),
    },
    "kampu_metrai_m": {
        "label": "Dažymo kampai",
        "unit": "m",
        "accessor": lambda p: _santrauka_field(p, "kampai_m_total"),
    },
    "gkp_lubu_iki_3m_m2": {
        "label": "GKP lubos iki 3m",
        "unit": "m²",
        "accessor": lambda p: _santrauka_field(p, "gkp_lubu_m2_total"),
    },
    "led_nisos_m": {
        "label": "LED nišų ilgis",
        "unit": "m",
        "accessor": lambda p: _santrauka_field(p, "nisu_metrai_total"),
    },
}


router = APIRouter(prefix="/api/projects", tags=["calibrate"])


def _safe_project_id(project_id: str) -> str:
    if not project_id or not all(c.isalnum() or c in ("-", "_") for c in project_id):
        raise HTTPException(status_code=400, detail="invalid project_id")
    return project_id


def _calib_path(project_id: str) -> Path:
    return CALIB_ROOT / f"{_safe_project_id(project_id)}.json"


def _load_project_for_calibration(
    request: Request,
    project_id: str,
    fixture: str | None,
) -> dict[str, Any]:
    if fixture:
        p = FIXTURES.get(fixture)
        if not p or not p.exists():
            raise HTTPException(status_code=404, detail=f"unknown fixture: {fixture}")
        return json.loads(p.read_text(encoding="utf-8"))
    user = _auth.require_user(request)
    user_filter = None if user.get("is_admin") else user["id"]
    proj = _db.get_project(project_id, user_id=user_filter)
    if not proj:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    return proj


def _require_project_access(request: Request, project_id: str) -> dict:
    """Auth + ownership gate for the GET/DELETE calibration verbs (F1,
    2026-07-04 pentest). POST was correctly gated via
    _load_project_for_calibration; GET (:228) and DELETE (:243) were missed —
    they read/deleted the per-project calibration file (which carries the user's
    KNOWN category totals) keyed only by project_id, with no auth. Require a
    login (401), scope db.get_project to the caller (admins see all); missing/
    foreign project → 404 (do not leak existence)."""
    user = _auth.require_user(request)
    user_filter = None if user.get("is_admin") else user["id"]
    if _db.get_project(project_id, user_id=user_filter) is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    return user


def compute_factors(
    parsed: dict[str, Any],
    overrides: dict[str, float],
) -> dict[str, dict[str, Any]]:
    """Pure function: compute ``factor = user_value / ai_value`` per metric.

    Returns a per-metric dict carrying ``{ai_value, user_value, factor,
    label, unit, applied}``. ``applied: false`` when the AI value is
    zero (no factor computable) or the metric is unknown.
    """
    out: dict[str, dict[str, Any]] = {}
    for key, user_val in overrides.items():
        meta = METRIC_ACCESSORS.get(key)
        if meta is None:
            out[key] = {
                "ai_value": None, "user_value": float(user_val),
                "factor": None, "applied": False,
                "reason": "unknown_metric",
            }
            continue
        ai_val = float(meta["accessor"](parsed))
        if ai_val <= 0:
            out[key] = {
                "ai_value": ai_val, "user_value": float(user_val),
                "factor": None, "applied": False,
                "reason": "ai_value_zero",
                "label": meta["label"], "unit": meta["unit"],
            }
            continue
        factor = float(user_val) / ai_val
        out[key] = {
            "ai_value": ai_val, "user_value": float(user_val),
            "factor": round(factor, 6),
            "applied": True,
            "label": meta["label"], "unit": meta["unit"],
        }
    return out


@router.post("/{project_id}/calibrate")
async def calibrate_project(
    request: Request,
    project_id: str,
    body: dict[str, Any] = Body(...),
    fixture: str | None = Query(default=None),
) -> dict[str, Any]:
    project_id = _safe_project_id(project_id)
    overrides_raw = body.get("overrides") or {}
    if not isinstance(overrides_raw, dict):
        raise HTTPException(status_code=400, detail="overrides must be a JSON object")
    try:
        overrides = {str(k): float(v) for k, v in overrides_raw.items()}
    except (TypeError, ValueError) as e:
        raise HTTPException(status_code=400, detail=f"overrides values must be numeric: {e}")

    # Optional opt-in global correction. The caller MAY supply
    # perimeter_correction_factor (≈0.99–1.01); when present, the eval
    # harness with --apply-calibration multiplies every room's perim by
    # this factor before invoking the calculator. Used for project-
    # specific Vision drift compensation; never inherited globally.
    perim_factor_raw = body.get("perimeter_correction_factor")
    perimeter_correction_factor: float | None = None
    if perim_factor_raw is not None:
        try:
            perimeter_correction_factor = float(perim_factor_raw)
        except (TypeError, ValueError) as e:
            raise HTTPException(status_code=400, detail=f"perimeter_correction_factor must be numeric: {e}")
        if not (0.90 <= perimeter_correction_factor <= 1.10):
            raise HTTPException(
                status_code=400,
                detail="perimeter_correction_factor must be in [0.90, 1.10] (a ±10% bound; "
                       "values outside this range are almost certainly not Vision drift)",
            )

    parsed = _load_project_for_calibration(request, project_id, fixture)
    factors = compute_factors(parsed, overrides)

    record = {
        "project_id": project_id,
        "fixture": fixture,
        "overrides": overrides,
        "factors": factors,
        "perimeter_correction_factor": perimeter_correction_factor,
        "updated_at": int(time.time()),
        "schema_version": 2,
    }
    # Atomic write
    p = _calib_path(project_id)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)

    return {
        "project_id": project_id,
        "factors": factors,
        "updated_at": record["updated_at"],
        "stored_at": str(p),
    }


@router.get("/{project_id}/calibrate")
async def get_calibration(project_id: str, request: Request) -> dict[str, Any]:
    project_id = _safe_project_id(project_id)
    _require_project_access(request, project_id)
    p = _calib_path(project_id)
    if not p.exists():
        return {
            "project_id": project_id, "overrides": {}, "factors": {},
            "updated_at": None,
        }
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"corrupt store: {e}")


@router.delete("/{project_id}/calibrate")
async def delete_calibration(project_id: str, request: Request) -> dict[str, Any]:
    project_id = _safe_project_id(project_id)
    _require_project_access(request, project_id)
    p = _calib_path(project_id)
    existed = p.exists()
    if existed:
        p.unlink()
    return {"ok": True, "existed": existed}
