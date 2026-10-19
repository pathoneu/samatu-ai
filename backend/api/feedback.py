"""POST /api/projects/{project_id}/feedback — 👍 / 👎 plus one optional line (Pathon v3 W5-C, C10 / #170, #203).

Two things are rated:
  * the paid read as a whole (`kind: "skaitymas"`) — one journal row, `ivertinimas.skaitymas`;
  * a found symbol (`kind: "simbolis"`) — 👎 means „neieškoti tokių": the symbol's box becomes a NEGATIVE
    example, and the next „Rasti panašius" search (`/api/cv/find-symbol`) drops candidates that look more like
    it than like his boxed example (`negatives_for` + `apply_negatives`, used by api/cv_tools.py).

Everything is a row of the corrections journal (source `ivertinimas`) — the journal stays the one record of
what he decided, and „Atšaukti" is one more row that takes the decision back (`undo: true`), so nothing is
ever deleted. No paid call, no „fix with AI": the rating is recorded and used, that is all.
"""
from __future__ import annotations

import hashlib
import logging
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

import db as _db
from api.free_reread import _project_for

log = logging.getLogger("samatu.feedback")

router = APIRouter(prefix="/api/projects", tags=["feedback"])

SOURCE = "ivertinimas"
MAX_NEGATIVES = 5            # the newest few — each one is another shape search on the page
NEGATIVE_IOU = 0.3
# the same symbol scores a little differently turned or mirrored (resampling): within this margin a candidate
# counts as looking as much like the negative as like his example
NEGATIVE_MARGIN = 0.03


class FeedbackBody(BaseModel):
    kind: Literal["skaitymas", "simbolis"]
    up: bool = False
    line: str | None = Field(default=None, max_length=200)
    # a found symbol: its sheet (1-based) and box in display-frame page fractions [x0, y0, x1, y1]
    page: int | None = Field(default=None, ge=1)
    box_pct: list[float] | None = Field(default=None, min_length=4, max_length=4)
    klass: str | None = Field(default=None, max_length=80)
    undo: bool = False


def _box_ok(b: list[float] | None) -> bool:
    if not b:
        return False
    x0, y0, x1, y1 = (float(v) for v in b)
    return 0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1


def _box_key(page: int, box: list[float]) -> str:
    raw = f"{page}:" + ",".join(f"{float(v):.4f}" for v in box)
    return hashlib.sha1(raw.encode()).hexdigest()[:12]


@router.post("/{project_id}/feedback")
def api_feedback(request: Request, project_id: str, body: FeedbackBody):
    _project_for(request, project_id)
    from main import _check_rate_limit, _client_key
    _check_rate_limit(_client_key(request), "feedback")
    line = (body.line or "").strip() or None

    if body.kind == "skaitymas":
        verdict = "atsaukta" if body.undo else ("taip" if body.up else "ne")
        written = _db.log_correction_once(
            project_id=project_id, field_path="ivertinimas.skaitymas", old_value=None,
            new_value={"ivertinimas": verdict}, source=SOURCE, note=line)
        return {"status": "ok", "kind": "skaitymas", "ivertinimas": verdict, "duplicate": not written}

    if body.page is None or not _box_ok(body.box_pct):
        raise HTTPException(status_code=400, detail="Rastam simboliui reikia lapo ir rėmelio")
    x0, y0, x1, y1 = (float(v) for v in body.box_pct)
    key = _box_key(body.page, body.box_pct)
    negative = (not body.up) and not body.undo
    written = _db.log_correction_once(
        project_id=project_id, field_path=f"ivertinimas.simbolis.{body.page}.{key}", old_value=None,
        new_value={"ivertinimas": "atsaukta" if body.undo else ("taip" if body.up else "ne"),
                   "neieskoti": negative, "lapas": body.page, "box_pct": [x0, y0, x1, y1],
                   "klase": body.klass},
        source=SOURCE, note=line)
    return {"status": "ok", "kind": "simbolis", "neieskoti": negative, "key": key, "duplicate": not written}


def negatives_for(project_id: str) -> list[dict]:
    """The symbols he said „neieškoti tokių" about and has not taken back: the LATEST row per box decides.
    → [{page, box_pct, klase}], newest first, at most MAX_NEGATIVES."""
    try:
        rows = _db.list_corrections(project_id, limit=500)
    except Exception as exc:  # noqa: BLE001 — a journal hiccup never breaks the search
        log.warning("negatives read failed for %s: %r", project_id, exc)
        return []
    # newest first — two rows in the same second (a 👎 and its „Atšaukti") are ordered by their id
    rows = sorted(rows, key=lambda r: (str(r.get("occurred_at") or ""), int(r.get("id") or 0)), reverse=True)
    seen: set[str] = set()
    out: list[dict] = []
    for r in rows:
        fp = str(r.get("field_path") or "")
        if r.get("source") != SOURCE or not fp.startswith("ivertinimas.simbolis."):
            continue
        if fp in seen:
            continue
        seen.add(fp)
        v = r.get("new_value") if isinstance(r.get("new_value"), dict) else {}
        if v.get("neieskoti") and isinstance(v.get("box_pct"), list) and v.get("lapas"):
            out.append({"page": int(v["lapas"]), "box_pct": [float(x) for x in v["box_pct"]], "klase": v.get("klase")})
        if len(out) >= MAX_NEGATIVES:
            break
    return out


def _iou(a, b) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ix = max(0.0, min(ax + aw, bx + bw) - max(ax, bx))
    iy = max(0.0, min(ay + ah, by + bh) - max(ay, by))
    inter = ix * iy
    union = aw * ah + bw * bh - inter
    return inter / union if union > 0 else 0.0


def apply_negatives(candidates: list[dict], page_raster, page_idx: int, negatives: list[dict], render, search,
                    min_score: float, dpi: int) -> tuple[list[dict], int]:
    """Drop the candidates that look at least as much like a negative example as like his boxed example.

    `candidates` are the shape search's (raster px bbox [x, y, w, h], score). For each negative its crop is cut
    from its own sheet's raster (`render(page_idx0, dpi)`, display frame — box_pct is display-frame too) and
    searched on this page with the same search; a candidate whose window a negative finds with a score no lower
    than the candidate's own (less NEGATIVE_MARGIN) is dropped. The candidate he boxed himself (`is_source`) always stays.
    → (kept candidates, how many were dropped)."""
    if not negatives or not candidates:
        return candidates, 0
    hits: list[tuple[list[float], float]] = []
    for neg in negatives:
        try:
            src = page_raster if neg["page"] - 1 == page_idx else render(neg["page"] - 1, dpi)
            h, w = src.shape[:2]
            x0, y0, x1, y1 = neg["box_pct"]
            px = [int(round(x0 * w)), int(round(y0 * h)), int(round(x1 * w)), int(round(y1 * h))]
            crop = src[max(0, px[1]):px[3], max(0, px[0]):px[2]]
            if crop.size == 0 or crop.shape[0] < 4 or crop.shape[1] < 4:
                continue
            found = search(page_raster, crop, min_score=min_score, max_results=500, dpi=dpi)
            hits.extend((c["bbox"], float(c["score"])) for c in found.get("candidates", []))
            if neg["page"] - 1 == page_idx:      # the very symbol he rejected
                hits.append(([px[0], px[1], px[2] - px[0], px[3] - px[1]], 1.0))
        except Exception as exc:  # noqa: BLE001 — one unreadable negative is skipped, never fails the search
            log.warning("negative example skipped: %r", exc)
    if not hits:
        return candidates, 0
    kept, dropped = [], 0
    for c in candidates:
        if c.get("is_source"):
            kept.append(c)
            continue
        if any(_iou(c["bbox"], hb) > NEGATIVE_IOU and hs >= float(c["score"]) - NEGATIVE_MARGIN for hb, hs in hits):
            dropped += 1
            continue
        kept.append(c)
    return kept, dropped
