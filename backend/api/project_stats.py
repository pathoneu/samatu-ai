"""GET /api/projects/{project_id}/stats

Lightweight project dashboard payload — counts + confidence distribution
+ verification progress (from the annotation store) + calibration state.

Pure read; no Vision, no DB write. ~5-15ms.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

import db as _db
import auth as _auth

REPO_ROOT = Path(__file__).resolve().parents[2]
ANNOTATIONS_ROOT = Path(__file__).resolve().parents[1] / "data" / "annotations"
CALIB_ROOT = Path(__file__).resolve().parents[1] / "data" / "calibrations"

FIXTURES = {
    "berzas": REPO_ROOT / "docs/superpowers/fixtures/2026-05-26-berzu-g-24/app-output-to-the-dot.json",
}

router = APIRouter(prefix="/api/projects", tags=["stats"])


def _load_project(request: Request, project_id: str, fixture: str | None) -> dict[str, Any]:
    """Resolve the parsed KŽ for the stats payload.

    P1 (2026-07-04 pentest, pass 3): AUTH + URL-project ownership FIRST, ALWAYS —
    BEFORE the fixture branch. Previously ``?fixture=`` returned before
    ``require_user`` ran, and the handler then read
    ``data/annotations/{URL_id}.json`` + ``data/calibrations/{URL_id}.json``
    keyed by the attacker's URL project_id → an anonymous
    ``GET /stats?fixture=berzas`` leaked another tenant's verification progress +
    calibration metadata. The URL project_id is what keys those per-user stores,
    so it MUST be owned regardless of ``fixture``. The fixture may still seed the
    reference KŽ body, but never authorizes the store reads. Mirrors the N1
    calibrate fix.
    """
    user = _auth.require_owned_project(request, project_id)  # 401 anon / 404 foreign — MUST precede fixture
    if fixture:
        p = FIXTURES.get(fixture)
        if not p or not p.exists():
            raise HTTPException(status_code=404, detail=f"unknown fixture: {fixture}")
        return json.loads(p.read_text(encoding="utf-8"))
    # Ownership already confirmed above; re-fetch the row as the parsed payload.
    user_filter = None if user.get("is_admin") else user["id"]
    proj = _db.get_project(project_id, user_id=user_filter)
    if not proj:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")
    return proj


def _read_json_safe(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


@router.get("/{project_id}/stats")
async def get_project_stats(
    request: Request,
    project_id: str,
    fixture: str | None = Query(default=None),
) -> dict[str, Any]:
    parsed = _load_project(request, project_id, fixture)
    rooms = parsed.get("patalpos") or []
    santrauka = parsed.get("santrauka") or {}

    # Counts
    n_rooms = len(rooms)
    total_area_m2 = sum(float(r.get("plotas_m2") or 0) for r in rooms)
    total_wall_gross_m2 = sum(
        float(r.get("perimetras_m") or 0) * float(r.get("lubu_aukstis_m") or 0)
        for r in rooms
    )
    n_openings = sum(
        sum(int(e.get("kiekis") or 1)
            for e in (r.get("elementai") or [])
            if (e.get("tipas") or "").lower() in ("duris", "pasleptos_duris", "langas", "stoglangis"))
        for r in rooms
    )
    n_niches = sum(
        sum(int(e.get("kiekis") or 1)
            for e in (r.get("elementai") or [])
            if (e.get("tipas") or "").lower() == "nisa_led")
        for r in rooms
    )

    # Confidence distribution (rooms' overall confidence string)
    conf_dist: dict[str, int] = {"high": 0, "medium": 0, "low": 0}
    for r in rooms:
        c = (r.get("confidence") or "medium").lower()
        if c not in conf_dist:
            conf_dist[c] = 0
        conf_dist[c] += 1

    # Verification progress (from annotation store; if present)
    annot_path = ANNOTATIONS_ROOT / f"{project_id}.json"
    annotations = _read_json_safe(annot_path) or {}
    verification = annotations.get("verification_state") or {}
    n_confirmed = sum(1 for v in verification.values() if v == "confirmed")
    n_corrected = sum(1 for v in verification.values() if v == "corrected")
    n_unverified = max(0, n_rooms - n_confirmed - n_corrected)

    # Calibration state
    calib_path = CALIB_ROOT / f"{project_id}.json"
    calibration = _read_json_safe(calib_path) or {}
    n_calibrated_metrics = sum(
        1 for v in (calibration.get("factors") or {}).values()
        if isinstance(v, dict) and v.get("applied")
    )

    return {
        "project_id": project_id,
        "rooms": {
            "count": n_rooms,
            "total_area_m2": round(total_area_m2, 2),
            "total_wall_gross_m2": round(total_wall_gross_m2, 2),
            "confidence_distribution": conf_dist,
        },
        "openings": {
            "doors_plus_windows_count": n_openings,
            "led_niches_count": n_niches,
        },
        "santrauka": {
            k: santrauka.get(k) for k in (
                "dazymo_plotas_total_m2", "dazymo_excl_garazas_total_m2",
                "nisu_metrai_total", "plyteles_grindys_m2_total",
                "plyteles_sienos_m2_total", "kampai_m_total",
                "angokrasciu_gkp_m_total",
            ) if santrauka.get(k) is not None
        },
        "verification": {
            "confirmed": n_confirmed,
            "corrected": n_corrected,
            "unverified": n_unverified,
            "complete_pct": round(
                (n_confirmed + n_corrected) / n_rooms * 100.0, 1
            ) if n_rooms else 0.0,
        },
        "calibration": {
            "applied_metrics": n_calibrated_metrics,
            "updated_at": calibration.get("updated_at"),
        },
    }
