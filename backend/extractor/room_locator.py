"""Where on the plan each room is — the seed every geometry unit needs.

Order of trust: the room's NUMBER BADGE written inside the room on a plan page
(designer plans: „01"…„11" in a small box; objektas_h 2026-09-17: 11/11
found), then the room's AREA LABEL (`_plotas_uzrasas`, architects' plans),
then Vision's box (`bbox_pct`, coarse). The source is recorded so the sheet
can say it.

A badge is a 1–2 digit word in a small font inside the drawing area. Numbers
in the room TABLE match too, so a word is rejected as a badge when another
word sits on the same line to its right within TABLE_NEIGHBOUR_PT (a table
row: „01  Tambūras  4,48"), or when it lies in the title block (the lowest
part of the page). When the same digit appears twice, the badge nearest to
Vision's box wins.

Writes nothing; returns {nr: {page, cx, cy, W, H, saltinis}} with cx, cy as
page fractions (pdfplumber frame, origin top-left) and W, H the page size in
points.
"""
from __future__ import annotations

import io
from typing import Sequence

import pdfplumber

BADGE_MAX_H_PT = 6.5
BADGE_MAX_W_PT = 9.0
TABLE_NEIGHBOUR_PT = 200.0
TITLE_BLOCK_FRAC = 0.88          # a badge below this fraction of the height is in the title block


def _nr_int(nr) -> int | None:
    s = "".join(ch for ch in str(nr or "") if ch.isdigit())
    return int(s) if s else None


def _badge_words(page) -> list[dict]:
    words = page.extract_words()
    out = []
    for w in words:
        t = w["text"]
        if not (t.isdigit() and 1 <= len(t) <= 2):
            continue
        if (w["bottom"] - w["top"]) > BADGE_MAX_H_PT or (w["x1"] - w["x0"]) > BADGE_MAX_W_PT:
            continue
        if w["top"] > TITLE_BLOCK_FRAC * page.height:
            continue
        # A table row has a NAME to the right („01  Tambūras  4,48"): an upright
        # word with letters on the same line. Numbers to the right (another
        # room's badge, a dimension string) do not disqualify.
        same_line_name = [o for o in words if o is not w
                          and abs(o["top"] - w["top"]) <= 2.5
                          and 0 < o["x0"] - w["x1"] <= TABLE_NEIGHBOUR_PT
                          and o.get("upright", True)
                          and any(ch.isalpha() for ch in o["text"])]
        if same_line_name:
            continue                                   # a table row, not a badge
        out.append(w)
    return out


def _bbox_centre(room: dict) -> tuple[float, float] | None:
    b = room.get("bbox_pct")
    if isinstance(b, dict) and all(k in b for k in ("x", "y", "w", "h")):
        try:
            return float(b["x"]) + float(b["w"]) / 2, float(b["y"]) + float(b["h"]) / 2
        except (TypeError, ValueError):
            return None
    return None


def _distance_to_bbox(room: dict, cand: dict) -> float:
    """Distance (page fractions) from a candidate to Vision's box centre; 0 without a box."""
    c = _bbox_centre(room)
    if c is None:
        return 0.0
    return ((cand["cx"] - c[0]) ** 2 + (cand["cy"] - c[1]) ** 2) ** 0.5


def locate_rooms(pdf_bytes: bytes, rooms: Sequence[dict], plan_pages: Sequence[int]) -> dict[str, dict]:
    want: dict[int, list[dict]] = {}
    for r in rooms:
        n = _nr_int(r.get("nr"))
        if n is not None:
            want.setdefault(n, []).append(r)
    found: dict[str, dict] = {}
    # 1. area labels the earlier lanes already placed
    for r in rooms:
        u = r.get("_plotas_uzrasas")
        if isinstance(u, dict) and u.get("bbox") and u.get("page_width") and u.get("page_height"):
            x0, top, x1, bottom = (float(v) for v in u["bbox"])
            W, H = float(u["page_width"]), float(u["page_height"])
            found[str(r.get("nr"))] = {"page": int(u["page"]), "cx": (x0 + x1) / 2 / W, "cy": (top + bottom) / 2 / H,
                                       "W": W, "H": H, "saltinis": "plotas_uzrasas"}
    # 2. badges on plan pages
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for pn in plan_pages:
            if not (1 <= int(pn) <= len(pdf.pages)):
                continue
            page = pdf.pages[int(pn) - 1]
            for w in _badge_words(page):
                n = int(w["text"])
                for r in want.get(n, []):
                    key = str(r.get("nr"))
                    if key in found and found[key]["saltinis"] == "plotas_uzrasas":
                        continue
                    cand = {"page": int(pn), "cx": (w["x0"] + w["x1"]) / 2 / float(page.width),
                            "cy": (w["top"] + w["bottom"]) / 2 / float(page.height),
                            "W": float(page.width), "H": float(page.height), "saltinis": "zenkliukas"}
                    prev = found.get(key)
                    if prev is None or _distance_to_bbox(r, cand) < _distance_to_bbox(r, prev):
                        found[key] = cand
    # 3. Vision's box
    for r in rooms:
        key = str(r.get("nr"))
        c = _bbox_centre(r)
        if key not in found and c is not None:
            found[key] = {"page": int(r.get("puslapio_nr") or (plan_pages[0] if plan_pages else 1)),
                          "cx": c[0], "cy": c[1], "W": None, "H": None, "saltinis": "bbox"}
    return found
