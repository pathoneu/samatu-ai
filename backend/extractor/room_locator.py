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
rule was NOT loosened to a bigger FIXED cap for short numbers: measured
(2026-09-21), that cost objektas_h two outlines and turned objektas_b's
furniture item numbers into rooms. Since 2026-10-24 the cap is relative to the
sheet's dimension strings (below) — tighter than 6,5 pt on objektas_h. Numbers in the room TABLE match too, so a word is rejected as a
badge when it is a cell of a COLUMN — another short number sits straight
above or below it within TABLE_ROW_PT („01", „02", „03"… down the table;
rooms are metres apart, table rows a few millimetres) — when another number
touches it on its line (a piece of a letter-spaced dimension string: „8" +
„85"), or when it lies in the title block (the lowest part of the page). A
NAME to the right does not disqualify: objektas_h's badge „4" has the
furniture label „LENTYNOS" on its line. When the same digit appears twice,
the badge nearest to Vision's box wins.

HOW TALL A BADGE MAY BE (2026-10-24). A fixed 6,5 pt cap rejected every badge of two real drawings:
objektas_i writes its badges 6,6 pt tall over dimension strings 6,55 pt tall (0 of 17 rooms located), and
objektas_j2 writes them 11,0 pt over strings 6,62–8,27 pt. A badge is a label in the drawing's own annotation
font family, so it is measured against the sheet's DIMENSION STRINGS (their median height, every text
direction, PDFium boxes): at most BADGE_VS_DIMENSION (2,0) times as tall — measured ratios i 1,01,
objektas_h 1,20 (3,5 / 2,91), j2 1,33–1,66 — and never above BADGE_CEILING_PT (14 pt: a sheet title or a
title-block number). A sheet with fewer than MIN_REFERENCE_STRINGS strings keeps the old 6,5 pt cap. The width
cap grows in the same proportion. Measured on the corpus' stored rooms: objektas_a, c, g, h locate exactly as
before; objektas_b's 15 circled room numbers (7,0 pt over 7,0–10,2 pt strings) and objektas_d's 4 boxed ones
are now found where only Vision's box placed them — each checked on the sheet.

SEVERAL UNITS ON ONE SHEET (2026-10-24). When the room table holds two or more units that repeat their numbers
(pdfplumber_eksplikacija.stacked_unit_rooms: rooms keyed „1-3", „2-3" with `_vienetas` and `_nr_brezinyje`),
a badge „3" is matched to the unit whose part of the sheet it stands in (`units_of_badges`). Rooms without
`_vienetas` never reach that path.

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

BADGE_MAX_H_PT = 6.5             # a sheet with no dimension string to measure against keeps the old fixed cap
BADGE_MAX_W_PT = 9.0
BADGE_VS_DIMENSION = 2.0         # a badge is at most this many times the height of the sheet's dimension strings
BADGE_CEILING_PT = 14.0          # …and never taller than this — a sheet title, a title-block number
MIN_REFERENCE_STRINGS = 5        # dimension strings a sheet needs before their height is the yardstick
MIN_UNIT_BADGES = 3              # a unit's part of a sheet shows at least this many room numbers
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


def dimension_text_height(chars: list[dict]) -> list[float]:
    """The heights of the dimension strings („4200", „2,45") among these characters — the yardstick a badge is
    measured against (plan_dimensions' own reading of a string)."""
    from .plan_dimensions import _dimension_runs, _value_m
    return [r["bottom"] - r["top"] for r in _dimension_runs(chars)
            if len(r["text"]) >= 3 and _value_m(r["text"]) is not None and r["bottom"] > r["top"]]


def badge_height_cap(dimension_heights: Sequence[float]) -> float:
    """The tallest a short badge may be on a sheet whose dimension strings are this tall (see the module
    docstring): BADGE_VS_DIMENSION × their median, never above BADGE_CEILING_PT; the fixed BADGE_MAX_H_PT
    when the sheet has fewer than MIN_REFERENCE_STRINGS strings to measure against."""
    hs = sorted(float(h) for h in dimension_heights if h and h > 0)
    if len(hs) < MIN_REFERENCE_STRINGS:
        return BADGE_MAX_H_PT
    median = hs[len(hs) // 2] if len(hs) % 2 else (hs[len(hs) // 2 - 1] + hs[len(hs) // 2]) / 2
    return min(BADGE_CEILING_PT, BADGE_VS_DIMENSION * median)


def _unit(room: dict) -> int | None:
    """The unit (one of several dwellings drawn on one plan) a room belongs to — set by the room-table reader
    when stacked tables repeat their numbers (pdfplumber_eksplikacija.stacked_unit_rooms); None otherwise."""
    u = room.get("_vienetas")
    try:
        return int(u) if u is not None else None
    except (TypeError, ValueError):
        return None


def _drawn_nr(room: dict):
    """The number written on the plan: a unit room's own number („3" of „2-3"), else the room's key."""
    return room.get("_nr_brezinyje") if _unit(room) is not None and room.get("_nr_brezinyje") else room.get("nr")


def _split_two(items: list[tuple[int, int, float, float]]):
    """The axis-parallel line that best separates two units' badges on one sheet: (left/top, right/bottom) or
    None. The best line puts the most room numbers on BOTH of its sides (the units repeat each other's numbers)
    and, among those, has the widest empty band around it. Each side keeps at least MIN_UNIT_BADGES numbers."""
    best = None
    for axis in (2, 3):
        order = sorted(items, key=lambda it: it[axis])
        for i in range(len(order) - 1):
            a, b = order[:i + 1], order[i + 1:]
            na, nb = {it[1] for it in a}, {it[1] for it in b}
            if len(na) < MIN_UNIT_BADGES or len(nb) < MIN_UNIT_BADGES:
                continue
            both = len(na & nb)
            if both < MIN_UNIT_BADGES:
                continue
            gap = order[i + 1][axis] - order[i][axis]
            score = (both, gap)
            if best is None or score > best[0]:
                best = (score, a, b)
    return (best[1], best[2]) if best else None


def units_of_badges(seen: Sequence[tuple[int, int, dict]], rooms: Sequence[dict]) -> dict[int, int]:
    """{index into `seen` → unit} for the badges that can be told apart; a badge missing from the answer serves
    no unit room.

    Several units drawn on one sheet (objektas_i, 2026-10-24: a semi-detached house, rooms 1–8 and 1–9 on its
    partitions plan) put the same number in two places. The badges of one unit stand together, so the sheet is
    cut by the axis-parallel line that leaves the most numbers on both sides (`_split_two`, repeated while there
    are more units than parts). Each part is then the unit whose numbers it shows best: most of its numbers in
    that unit's table and fewest that are not, then fewest of the unit's numbers missing (a single-unit sheet
    showing 1–8 is the unit numbered 1–8, not the one numbered 1–9); a tie is left unassigned, never guessed.
    Every page is read on its own; a part matched to no unit serves nobody."""
    numbers: dict[int, set[int]] = {}
    for r in rooms:
        u, n = _unit(r), _nr_int(_drawn_nr(r))
        if u is not None and n is not None:
            numbers.setdefault(u, set()).add(n)
    out: dict[int, int] = {}
    pages: dict[int, list[tuple[int, int, float, float]]] = {}
    for k, (pn, n, cand) in enumerate(seen):
        pages.setdefault(int(pn), []).append((k, int(n), float(cand["cx"]), float(cand["cy"])))
    for pn, items in pages.items():
        parts = [items]
        while len(parts) < len(numbers):
            cut = None
            for i, part in enumerate(parts):
                two = _split_two(part)
                if two is not None:
                    cut = (i, two)
                    break
            if cut is None:
                break
            i, (a, b) = cut
            parts[i:i + 1] = [a, b]
        taken: set[int] = set()
        scored = []
        for i, part in enumerate(parts):
            shown = {it[1] for it in part}
            for u, have in numbers.items():
                scored.append(((len(shown & have) - len(shown - have), -len(have - shown)), i, u))
        scored.sort(key=lambda s: (s[0], -s[1], -s[2]), reverse=True)
        assigned: dict[int, int] = {}
        for score, i, u in scored:
            if i in assigned or u in taken:
                continue
            rivals = [s for s in scored if s[1] == i and s[2] != u and s[2] not in taken and s[0] == score]
            if rivals or score[0] <= 0:
                continue
            assigned[i] = u
            taken.add(u)
        for i, u in assigned.items():
            for it in parts[i]:
                out[it[0]] = u
    return out


def _badge_words(words: list[dict], long_numbers: frozenset[str] = frozenset(),
                 max_h: float = BADGE_MAX_H_PT) -> list[dict]:
    """The words of ONE text direction (its own left-to-right frame) that are badges. `long_numbers` are
    the three-and-more-digit room numbers being looked for: only those exact words count, never any
    3–4 digit number (the sheet is full of dimensions). `max_h` = the sheet's badge height cap
    (`badge_height_cap`); the width cap grows with it in the same proportion."""
    numbers = [w for w in words if _short_number(w["text"]) or (w["text"] in long_numbers and _long_number(w["text"]))]
    max_w = BADGE_MAX_W_PT * max(1.0, max_h / BADGE_MAX_H_PT)
    out = []
    for w in numbers:
        height = w["bottom"] - w["top"]
        if _short_number(w["text"]):
            if height > max_h or (w["x1"] - w["x0"]) > max_w:
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
        n = _nr_int(_drawn_nr(r))
        if n is not None:
            want.setdefault(n, []).append(r)
    units = sorted({_unit(r) for r in rooms if _unit(r) is not None})
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
        # the yardstick per sheet: its dimension strings in every text direction (a plan's vertical strings
        # are the same font as its horizontal ones)
        dim_heights: dict[int, list[float]] = {}
        for pn, _W, _H, chars, _td in directions:
            dim_heights.setdefault(int(pn), []).extend(dimension_text_height(chars))
        caps = {pn: badge_height_cap(hs) for pn, hs in dim_heights.items()}
        seen: list[tuple[int, int, dict]] = []          # (page, number, candidate) in reading order
        for pn, W, H, chars, to_display in directions:
            if by_zones and int(pn) not in zone_filters:
                zone_filters[int(pn)] = plan_zone_filter(pdf_bytes, int(pn))
            in_plan = zone_filters.get(int(pn)) if by_zones else None
            for w in _badge_words(_words(chars), long_numbers, caps.get(int(pn), BADGE_MAX_H_PT)):
                x0, top, x1, bottom = to_display([w["x0"], w["top"], w["x1"], w["bottom"]])
                if in_plan is not None:
                    if not in_plan((x0 + x1) / 2 / float(W), (top + bottom) / 2 / float(H)):
                        continue
                elif top > TITLE_BLOCK_FRAC * H:
                    continue
                seen.append((int(pn), int(w["text"]), {"page": int(pn), "cx": (x0 + x1) / 2 / float(W),
                                                        "cy": (top + bottom) / 2 / float(H), "W": float(W),
                                                        "H": float(H), "saltinis": "zenkliukas"}))
        unit_of = units_of_badges(seen, rooms) if len(units) > 1 else None
        # The plan's ROOM-NUMBER sheet is the one showing the most of the wanted numbers; a badge there is never
        # displaced by the same digit on another sheet (objektas_b: the furniture plan numbers its furniture
        # 1–18 in the badges' size, and its „13" — a bidet in room 10 — stood nearer Vision's box for room 13
        # than the circled „13" on the partitions plan). Other sheets still seat the rooms that sheet lacks.
        shown: dict[int, set[int]] = {}
        for pn, n, _c in seen:
            if n in want:
                shown.setdefault(pn, set()).add(n)
        rank = {pn: i for i, pn in enumerate(sorted(shown, key=lambda p: (-len(shown[p]), pages.index(p) if p in pages else p)))}
        for k, (pn, n, cand) in enumerate(seen):
            for r in want.get(n, []):
                if unit_of is not None and _unit(r) is not None and unit_of.get(k) != _unit(r):
                    continue                            # this badge stands in another unit's plan
                key = str(r.get("nr"))
                if key in found and found[key]["saltinis"] == "plotas_uzrasas":
                    continue
                prev = found.get(key)
                if prev is None:
                    found[key] = dict(cand)
                    continue
                r_new, r_old = rank.get(pn, len(rank)), rank.get(int(prev["page"]), len(rank))
                if r_new < r_old or (r_new == r_old and _distance_to_bbox(r, cand) < _distance_to_bbox(r, prev)):
                    found[key] = dict(cand)
    # 3. Vision's box
    for r in rooms:
        key = str(r.get("nr"))
        c = _bbox_centre(r)
        if key not in found and c is not None:
            found[key] = {"page": int(r.get("puslapio_nr") or (pages[0] if pages else 1)),
                          "cx": c[0], "cy": c[1], "W": None, "H": None, "saltinis": "bbox"}
    return found
