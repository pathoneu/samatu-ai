"""Where on the plan each room is — the seed every geometry unit needs.

Order of trust: the room's AREA LABEL (`_plotas_uzrasas`, architects' plans —
an earlier lane already placed it), then the room's NUMBER BADGE written
inside the room on a plan page (designer plans: „01"…„11" in a small box;
objektas_h 2026-09-17: 11/11 found), then Vision's box (`bbox_pct`, coarse).
The source is recorded so the sheet can say it.

A badge is a 1–2 digit word in a small font inside the drawing area that
STANDS ALONE — or the room's own number of three digits and more („101",
„102"… the way architects number the rooms of a house; objektas_a
2026-09-21: 10 of 11 rooms had no place until these were read), which is
written larger, so it gets its own size limit (LONG_BADGE_*). The small-font
rule is NOT loosened for short numbers: measured, that cost objektas_h two
outlines and turned objektas_b's furniture item numbers into rooms. Numbers in the room TABLE match too, so a word is rejected as a
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

Behind `SAMATU_ROOMS_BY_ZONES=1` (Pathon v3 W5-B, B3; default OFF — nothing
changes): on a sheet whose zones (extractor/sheet_zones.py) name at least one
plan viewport, a badge counts only when it stands inside a `planas` zone and
no title block, legend, table or notes block holds it (`zone_at`: the
innermost zone wins, a plan comes last) — instead of the fixed 0,88 cut. A
sheet with no plan zone keeps the cut. The zones are read with the free
re-read's table cap, so the re-read's own `_meta.zonos` reuses the cache.
"""
from __future__ import annotations

import os
from typing import Sequence

from .plan_area_annotations import _iter_pages, _words

BADGE_MAX_H_PT = 6.5
BADGE_MAX_W_PT = 9.0
LONG_BADGE_MIN_DIGITS = 3        # „101": a house's room number, written larger than a designer's „01"
LONG_BADGE_MAX_H_PT = 14.0       # …but still a label in a room, not a sheet title
TABLE_ROW_PT = 14.0              # numbers stacked closer than this are a table column, not rooms
COLUMN_ALIGN_PT = 1.5
SAME_LINE_PT = 2.5
TOUCH_EM = 1.2                   # another number within this many badge heights is the same number, split
TITLE_BLOCK_FRAC = 0.88          # a badge below this fraction of the height is in the title block
ROOMS_BY_ZONES_ENV = "SAMATU_ROOMS_BY_ZONES"


def rooms_by_zones() -> bool:
    """The zone-based badge filter (B3) — off unless the flag says 1 / true / yes / on."""
    return os.environ.get(ROOMS_BY_ZONES_ENV, "0").strip().lower() in ("1", "true", "yes", "on")


def plan_zone_filter(pdf_bytes: bytes, page: int):
    """For a sheet with plan zones: a function (cx, cy display fractions) → True when a badge there is in a
    plan and in nothing that is not a room (title block, legend, table, notes, ambiguous). None when the
    sheet has no plan zone (scan, no walls, failed reading) — the caller keeps the 0,88 cut."""
    try:
        from .sheet_zones import REREAD_TABLE_MAX_OBJECTS, read_zones, zone_at
        zones = read_zones(pdf_bytes, int(page), table_max_objects=REREAD_TABLE_MAX_OBJECTS).get("zones") or []
    except Exception:  # noqa: BLE001 — zones are a refinement; without them the old cut stands
        return None
    if not any(z.get("kind") == "planas" for z in zones):
        return None

    def in_plan(cx: float, cy: float) -> bool:
        z = zone_at(zones, cx, cy)
        return z is not None and z.get("kind") == "planas"
    return in_plan


def _nr_int(nr) -> int | None:
    s = "".join(ch for ch in str(nr or "") if ch.isdigit())
    return int(s) if s else None


def _has_digit(text: str) -> bool:
    return any(ch.isdigit() for ch in text)


def _short_number(text: str) -> bool:
    return text.isdigit() and 1 <= len(text) <= 2


def _long_number(text: str) -> bool:
    return text.isdigit() and LONG_BADGE_MIN_DIGITS <= len(text) <= 4 and not text.startswith("0")


def _badge_words(words: list[dict], long_numbers: frozenset[str] = frozenset()) -> list[dict]:
    """The words of ONE text direction (its own left-to-right frame) that are badges. `long_numbers` are
    the three-and-more-digit room numbers being looked for: only those exact words count, never any
    3–4 digit number (the sheet is full of dimensions)."""
    numbers = [w for w in words if _short_number(w["text"]) or (w["text"] in long_numbers and _long_number(w["text"]))]
    out = []
    for w in numbers:
        height = w["bottom"] - w["top"]
        if _short_number(w["text"]):
            if height > BADGE_MAX_H_PT or (w["x1"] - w["x0"]) > BADGE_MAX_W_PT:
                continue
        elif height > LONG_BADGE_MAX_H_PT:
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
        long_numbers = frozenset(str(n) for n in want if _long_number(str(n)))
        by_zones = rooms_by_zones()
        zone_filters: dict[int, object] = {}
        for pn, W, H, chars, to_display in directions:
            if by_zones and int(pn) not in zone_filters:
                zone_filters[int(pn)] = plan_zone_filter(pdf_bytes, int(pn))
            in_plan = zone_filters.get(int(pn)) if by_zones else None
            for w in _badge_words(_words(chars), long_numbers):
                x0, top, x1, bottom = to_display([w["x0"], w["top"], w["x1"], w["bottom"]])
                if in_plan is not None:
                    if not in_plan((x0 + x1) / 2 / float(W), (top + bottom) / 2 / float(H)):
                        continue
                elif top > TITLE_BLOCK_FRAC * H:
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
