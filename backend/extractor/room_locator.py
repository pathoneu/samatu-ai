"""Where on the plan each room is — the seed every geometry unit needs.

Order of trust: the room's AREA LABEL (`_plotas_uzrasas`, architects' plans —
an earlier lane already placed it), then the room's NUMBER BADGE written
inside the room on a plan page (designer plans: „01"…„11" in a small box;
objektas_h 2026-09-17: 11/11 found), then Vision's box (`bbox_pct`, coarse).
The source is recorded so the sheet can say it.

A badge is a 1–2 digit word in a small font inside the drawing area that
STANDS ALONE. Numbers in the room TABLE match too, so a word is rejected as a
badge when it is a cell of a COLUMN — another short number sits straight
above or below it within TABLE_ROW_PT („01", „02", „03"… down the table;
rooms are metres apart, table rows a few millimetres) — when another number
touches it on its line (a piece of a letter-spaced dimension string: „8" +
„85"), or when it lies in the title block (the lowest part of the page). A
NAME to the right does not disqualify: objektas_h's badge „4" has the
furniture label „LENTYNOS" on its line. When the same digit appears twice,
the badge nearest to Vision's box wins.

Text comes from the shared character reader (PDFium; pdfplumber needs ~60 s to
open objektas_g), one text direction at a time, so a turned sheet's badges are
read in the direction they are written.

Writes nothing; returns {nr: {page, cx, cy, W, H, saltinis}} with cx, cy as
page fractions (display frame, origin top-left) and W, H the page size in
points.
"""
from __future__ import annotations

from typing import Sequence

from .plan_area_annotations import _iter_pages, _words

BADGE_MAX_H_PT = 6.5
BADGE_MAX_W_PT = 9.0
TABLE_ROW_PT = 14.0              # numbers stacked closer than this are a table column, not rooms
COLUMN_ALIGN_PT = 1.5
SAME_LINE_PT = 2.5
TOUCH_EM = 1.2                   # another number within this many badge heights is the same number, split
TITLE_BLOCK_FRAC = 0.88          # a badge below this fraction of the height is in the title block


def _nr_int(nr) -> int | None:
    s = "".join(ch for ch in str(nr or "") if ch.isdigit())
    return int(s) if s else None


def _has_digit(text: str) -> bool:
    return any(ch.isdigit() for ch in text)


def _short_number(text: str) -> bool:
    return text.isdigit() and 1 <= len(text) <= 2


def _badge_words(words: list[dict]) -> list[dict]:
    """The words of ONE text direction (its own left-to-right frame) that are badges."""
    numbers = [w for w in words if _short_number(w["text"])]
    out = []
    for w in numbers:
        height = w["bottom"] - w["top"]
        if height > BADGE_MAX_H_PT or (w["x1"] - w["x0"]) > BADGE_MAX_W_PT:
            continue
        # a cell of a table column: another short number straight above or below
        if any(o is not w and 0 < abs(o["top"] - w["top"]) <= TABLE_ROW_PT
               and min(abs(o["x0"] - w["x0"]), abs(o["x1"] - w["x1"]),
                       abs((o["x0"] + o["x1"]) - (w["x0"] + w["x1"])) / 2) <= COLUMN_ALIGN_PT
               for o in numbers):
            continue
        # a number TOUCHING it on its line: the two are one number, split
        reach = TOUCH_EM * max(height, 1.0)
        if any(o is not w and _has_digit(o["text"]) and abs(o["top"] - w["top"]) <= SAME_LINE_PT
               and o["x0"] - w["x1"] <= reach and w["x0"] - o["x1"] <= reach for o in words):
            continue
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
    pages = [int(p) for p in plan_pages]
    if pages:
        try:
            directions = list(_iter_pages(pdf_bytes, pages))
        except Exception:  # noqa: BLE001 — no text layer is not a failure
            directions = []
        for pn, W, H, chars, to_display in directions:
            for w in _badge_words(_words(chars)):
                x0, top, x1, bottom = to_display([w["x0"], w["top"], w["x1"], w["bottom"]])
                if top > TITLE_BLOCK_FRAC * H:
                    continue
                n = int(w["text"])
                for r in want.get(n, []):
                    key = str(r.get("nr"))
                    if key in found and found[key]["saltinis"] == "plotas_uzrasas":
                        continue
                    cand = {"page": int(pn), "cx": (x0 + x1) / 2 / float(W), "cy": (top + bottom) / 2 / float(H),
                            "W": float(W), "H": float(H), "saltinis": "zenkliukas"}
                    prev = found.get(key)
                    if prev is None or _distance_to_bbox(r, cand) < _distance_to_bbox(r, prev):
                        found[key] = cand
    # 3. Vision's box
    for r in rooms:
        key = str(r.get("nr"))
        c = _bbox_centre(r)
        if key not in found and c is not None:
            found[key] = {"page": int(r.get("puslapio_nr") or (pages[0] if pages else 1)),
                          "cx": c[0], "cy": c[1], "W": None, "H": None, "saltinis": "bbox"}
    return found
