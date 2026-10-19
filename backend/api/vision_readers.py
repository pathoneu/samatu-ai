"""Paid fallback readers for a RASTER legend or schedule (Pathon v3 W5-D, D4 / D5) — CONDITIONAL, OFF by default.

The €0 readers (extractor/legend_rows.py, extractor/table_reader.py + schedules.py) read the PDF's text layer and
paths; a legend or schedule pasted as a picture has neither. For those two cases only, a model can read the box
the person drew:

  GET  /api/projects/{id}/vision-readers           → {enabled, kaina, sakinys} — may the UI offer it at all
  POST /api/projects/{id}/legend/vision-read       → {page, bbox_pct, patvirtinta} → legend rows to REVIEW
  POST /api/projects/{id}/schedule/vision-read     → {page, bbox_pct, patvirtinta} → schedule rows to REVIEW

Rules (programme non-negotiables 4 and 7):
  · behind SAMATU_VISION_LEGEND (default "0"): with it off both POSTs answer 403 and nothing is called;
  · a per-run OK: a request without `patvirtinta: true` answers 409 with the cost sentence the dialog shows —
    no model call happens until the person said yes to THAT run;
  · the owner check first, then the spend cap and reservation (main._billable_user), the rate bucket;
  · the answer is a PROPOSAL: nothing is saved here; the rows go through the same review-before-create the €0
    rows do (W2-B's review panel / the schedule questions). The deterministic reader stays first — the UI offers
    this only where it answered `be_teksto` / found no table.
  · tests stub the model; nothing here was run against Vision during development.
"""
from __future__ import annotations

import base64
import logging
import os

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from api.free_reread import NO_PDF, _project_for

log = logging.getLogger("samatu.vision_readers")

router = APIRouter(prefix="/api/projects", tags=["vision-readers"])

FLAG_ENV = "SAMATU_VISION_LEGEND"
# An estimate for one box, said BEFORE the run (one image call on the legend role / the schedule reader).
COST_LT = "apie 0,10–0,30 € už vieną rėmelį"
OFF_LT = "Brangesnis skaitymas išjungtas — paveikslėliu įklijuotą legendą ar lentelę pažymėkite rankiniu būdu."
ASK_LT = ("Ši legenda / lentelė įklijuota paveikslėliu, nemokamai jos perskaityti negaliu. Perskaityti mokamai? "
          f"Kaina — {COST_LT}. Perskaitytas eilutes pirmiausia peržiūrėsite, niekas nebus sukurta be jūsų.")
DPI = 200


def enabled() -> bool:
    return os.environ.get(FLAG_ENV, "0") == "1"


class ReadBody(BaseModel):
    page: int = 1
    bbox_pct: list[float] | None = None
    patvirtinta: bool = False


def _pdf(project_id: str) -> bytes:
    from storage import get_storage, pdf_key
    try:
        data = get_storage().get(pdf_key(project_id))
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=502, detail="Nepavyko pasiekti brėžinio saugyklos")
    if not data:
        raise HTTPException(status_code=404, detail=NO_PDF)
    return data


def _crop_b64(pdf: bytes, page: int, bbox_pct, project_id: str) -> tuple[str, str]:
    """(base64 JPEG of the box, media type) — the evidence renderer, so the model sees what the crop shows him."""
    from io import BytesIO

    from PIL import Image

    from api.evidence import render_crop
    rect = [float(v) for v in (bbox_pct or [0.0, 0.0, 1.0, 1.0])]
    if len(rect) != 4 or not (0 <= rect[0] < rect[2] <= 1 and 0 <= rect[1] < rect[3] <= 1):
        raise HTTPException(status_code=400, detail="Netinkamas rėmelis")
    png = render_crop(pdf, int(page), rect, DPI, cache_key=project_id)
    img = Image.open(BytesIO(png)).convert("RGB")
    buf = BytesIO()
    img.save(buf, "JPEG", quality=88)
    return base64.b64encode(buf.getvalue()).decode("ascii"), "image/jpeg"


def _gate(request: Request, project_id: str, body: ReadBody) -> dict:
    project = _project_for(request, project_id)            # owner first
    if not enabled():
        raise HTTPException(status_code=403, detail=OFF_LT)
    if not body.patvirtinta:
        raise HTTPException(status_code=409, detail={"klausimas": ASK_LT, "kaina": COST_LT})
    rect = body.bbox_pct or [0.0, 0.0, 1.0, 1.0]
    if len(rect) != 4 or not (0 <= rect[0] < rect[2] <= 1 and 0 <= rect[1] < rect[3] <= 1) or body.page < 1:
        raise HTTPException(status_code=400, detail="Netinkamas rėmelis")   # before any money is reserved
    from main import _billable_user, _check_rate_limit, _client_key
    _check_rate_limit(_client_key(request), "vision-reader")
    _billable_user(request)                                 # spend cap + reservation, only for a real run
    return project


@router.get("/{project_id}/vision-readers")
def api_vision_readers_status(request: Request, project_id: str):
    _project_for(request, project_id)
    return {"enabled": enabled(), "kaina": COST_LT, "sakinys": ASK_LT if enabled() else OFF_LT}


@router.post("/{project_id}/legend/vision-read")
def api_legend_vision_read(request: Request, project_id: str, body: ReadBody):
    _gate(request, project_id, body)
    pdf = _pdf(project_id)
    image, _ = _crop_b64(pdf, body.page, body.bbox_pct, project_id)
    from extractor.legend_injection import extract_legend
    try:
        legend = extract_legend(image)
    except Exception:  # noqa: BLE001 — a model outage is a plain message, not a 500
        log.exception("vision legend read failed (project=%s)", project_id)
        raise HTTPException(status_code=502, detail="Legendos perskaityti nepavyko — bandykite vėliau arba pažymėkite rankiniu būdu.")
    rows = []
    for i, sym in enumerate(legend.get("symbols") or []):
        if not isinstance(sym, dict) or not str(sym.get("meaning") or "").strip():
            continue
        rows.append({"row_id": f"v{body.page}-{i + 1}", "page": int(body.page), "text": str(sym["meaning"]).strip(),
                     "glyph_text": sym.get("glyph"), "spalvota_linija": sym.get("colored_line"),
                     "spalvotas_uzpildas": sym.get("colored_hatch"), "saltinis": "modelis",
                     "legend_bbox_pct": body.bbox_pct, "countable": True,
                     "reason_lt": "Perskaityta mokamai iš paveikslėlio — peržiūrėkite, ar eilutė teisinga."})
    return {"status": "ok", "rows": rows, "perziureti": True, "irasyta": False, "_meta": legend.get("_meta") or {}}


@router.post("/{project_id}/schedule/vision-read")
def api_schedule_vision_read(request: Request, project_id: str, body: ReadBody):
    _gate(request, project_id, body)
    pdf = _pdf(project_id)
    image, _ = _crop_b64(pdf, body.page, body.bbox_pct, project_id)
    from extractor.vision.schedule_extractor import extract_schedule
    try:
        sched = extract_schedule(image_b64=image)
    except Exception:  # noqa: BLE001
        log.exception("vision schedule read failed (project=%s)", project_id)
        raise HTTPException(status_code=502, detail="Lentelės perskaityti nepavyko — bandykite vėliau arba įveskite rankiniu būdu.")
    data = sched.to_dict() if hasattr(sched, "to_dict") else dict(sched or {})
    rows = []
    for kind in ("durys", "langai"):
        for e in data.get(kind) or []:
            rows.append({"rusis": kind, "kodas": e.get("id"), "plotis_mm": e.get("width_mm"), "aukstis_mm": e.get("height_mm"),
                         "kiekis": e.get("count"), "lauko": e.get("is_exterior"), "pastaba": e.get("notes"),
                         "page": int(body.page), "saltinis": "modelis"})
    return {"status": "ok", "rows": rows, "perziureti": True, "irasyta": False}
