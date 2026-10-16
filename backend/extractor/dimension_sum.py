"""Perimeter = the dimension strings the plan writes along the room's walls,
added up. The founder's rule (2026-09-10, repeated 2026-09-17): „perskaityti
skaičius ir sudėti", never measure. The outline is only the map that says
which strings are this room's walls, and the check that the sum agrees with
the outline's length (±CONTROL_TOL).

What decides that a string is a wall's length was MEASURED on objektas_h's
wall painting plan (2026-09-19, 51 strings against the designer's own wall
lines): the string's dimension line runs corner to corner — its ends within
0,02 m of the wall's ends — while its distance from the wall varies (0,11–
0,22 m as a rule, up to 0,94 m where the wall is crowded). So the ENDS
decide: a wall is stated by the nearest row of strings, within NEAR_M, that
starts at one corner, ends at the other and has no hole in it (one string, or
a chain „1200 | 900 | 1900"). A wardrobe's „1500" beside the wall starts and
ends nowhere near the corners; an outside chain to the wall axes („4300" over
a 4,00 m wall) runs past them. The layout sheet's strings are furniture
(objektas_h: 91 of 109); the walls' are on another ALIGNED sheet, so strings
are gathered from every sheet of the plan group and mapped onto the base page.

A string on the room's own side of the wall is preferred to one beyond the
wall, and the wall's one string to a chain that adds up to it. A row must also
AGREE with its wall's outline length (WALL_TOL): the corner tolerance alone
let a 0,8 m door string pass for a 0,95 m wall (objektas_g room 06). A length
written once serves the equal wall OPPOSITE (same extent): designers rarely
write a number twice — `saltinis = "priesinga_siena"` says whose it is.

Short pieces nobody dimensioned (< SHORT_EDGE_M — a 0,15 m step in the
outline) have no number to read: they are counted from the outline, up to
SHORT_SHARE of the perimeter, and the sum says how much (`is_konturo_m`).
A SLANTED wall is stated by the one string written along a slanted dimension
line parallel to it, ends opposite the wall's corners (objektas_h 2026-09-21:
„2060" along the bedroom's slanted wall).

Writes on the room: `_sienos` [{edge_pct, ilgis_m|None, saltinis "eilute" |
"priesinga_siena" | "konturas" | None, eilutes [{text, value_m, page, line_pct —
the string's dimension line on its own sheet}], kontrole_m}] and either perimetras_m +
perimetras_saltinis="matmenu_eilutes" + _perimetras_suma, or the outline's
length as perimetras_m with perimetras_saltinis="konturo_ivertis" (an ESTIMATE:
the sheet shows a blank and offers it; the sąmata rows need a number) +
_perimetras_priezastis + _perimetras_ivertis_m + _perimetras_ivertis_saltinis=
"konturas" — the length matched to the table's area when the lane's outline is off
it (`_matched_to_table`, `_perimetras_suma["pagal_plota"]` keeps the outline's own
length). Rooms whose perimeter someone STATED
(plan pair, table, user) are left alone; rooms whose outline is only Vision's
box or a browser flood-fill are skipped — those cannot say which strings are
its walls; an outline
that disagrees with the table states nothing (one of the two is wrong, and a
sum along the wrong walls would look exact).
"""
from __future__ import annotations

import math
from typing import Sequence

from shapely.geometry import Point, Polygon

from .sheet_alignment import base_page, to_base
from .vector_rooms import SOURCE as VECTOR_SOURCE

NEAR_M = 1.2                # a wall's string is written at most this far from it
END_TOL_M = 0.12            # …and its row starts and ends this close to the wall's corners
TIER_PT = 0.8               # strings of one row share a dimension line
AXIS_DEG = 3.0              # a wall this close to horizontal/vertical carries a horizontal/vertical string
SLANT_PARALLEL_DEG = 4.0    # …a slanted one carries the string whose dimension line runs this parallel to it
SHORT_EDGE_M = 0.4
SHORT_SHARE = 0.05
SHORT_HOLES_MAX_M = 0.5     # undimensioned piers inside ONE wall's chain may add up to this much
HOLE_IGNORE_M = 0.03        # …and a gap this small between two strings is no gap at all
OPENING_NEAR_M = 0.6        # an opening's line (the wall's axis) lies this close to the room's face of that wall
CONTROL_TOL = 0.03
WALL_TOL = 0.03             # a row's sum agrees with its wall's own outline length this closely…
WALL_TOL_M = 0.06           # …or to this many metres (objektas_g: strings are to the FINISHED faces, 2–3 cm inside the fills)
CORNER_DEG = 20.0
SOURCE = "matmenu_eilutes"
ESTIMATE_SOURCE = "konturo_ivertis"          # perimetras_m holds the outline's length: an estimate to accept, never „read"
KEEP = ("plano_matmenys", "eksplikacija", "user_override", "manual", SOURCE)
# outlines that follow the WALLS (traced from them, or drawn by a person) — a browser flood-fill
# contour or Vision's box is a place on the plan, not the room's walls
WALL_OUTLINES = ("vektoriniai_konturai", "sienu_konturas", "corrected", "manual")
# 2026-10-06 (objektas_a on production): every room's perimeter was its outline's length, and four were SHORTER
# than any room of their area can be (104: 13,98 m around 13,51 m² — a square needs 14,70). Each of those outlines
# was kept although its area is off the table's (vector_rooms: by more than AREA_TOL, up to AREA_WARN — the lane's
# `plotas_nesutampa`). The table's area is the one the rows bill, and a shape similar to the outline with that area
# has every length × √(table / outline) — so the outline's length, as the ESTIMATE, is matched to the table's area.
# Only for the lane's own outline it flagged so, and only this far off (vector_rooms.AREA_WARN: farther, the lane
# keeps no outline at all); never a person's outline (a polygon he drew or pointed at — even one that still carries
# an older record of the lane's), never a read or summed perimeter. The outline's own length stays beside it
# (`_perimetras_suma["pagal_plota"]`).
AREA_MATCH_MAX = 0.25
# Why such an outline adds up no strings — the cause its perimeter fact names („Perimetro nesudėjau: …"). Until
# 2026-10-06 it went on „— kol nepatikrinta, kuris teisus, sienų ilgių nesumuoju", which contradicted the fact's
# own „sienas skaičiuoju su … m"; room_facts renders the copies older projects still carry in these words too.
AREA_MISMATCH_REASON = "kontūro plotas nesutampa su lentele"


def _matched_to_table(room: dict, kont: dict, length_m: float) -> dict | None:
    """The outline's length matched to the table's area — {konturo_m (the outline's own length),
    konturo_plotas_m2, lenteles_plotas_m2, koeficientas, ivertis_m} — or None: not the lane's outline, the lane
    did not flag its area, an area is missing, or the two are farther apart than AREA_MATCH_MAX."""
    if room.get("polygon_source") != VECTOR_SOURCE or not kont.get("plotas_nesutampa") or not length_m or length_m <= 0:
        return None
    try:
        drawn = float(kont.get("plotas_m2") or 0)
        table = float(room.get("plotas_m2") or 0)
    except (TypeError, ValueError):
        return None
    if drawn <= 0 or table <= 0 or abs(drawn - table) / table > AREA_MATCH_MAX:
        return None
    factor = math.sqrt(table / drawn)
    return {"konturo_m": round(length_m, 2), "konturo_plotas_m2": round(drawn, 2), "lenteles_plotas_m2": round(table, 2),
            "koeficientas": round(factor, 4), "ivertis_m": round(length_m * factor, 2)}


IMAGINARY_TOL_PT = 1.5


def _on_segment(edge, seg, tol: float) -> bool:
    """Does this outline edge lie ON the segment (both ends within `tol` of its line, inside its extent)?"""
    (ax, ay), (bx, by) = seg
    length = math.hypot(bx - ax, by - ay)
    if length <= 0:
        return False
    ux, uy = (bx - ax) / length, (by - ay) / length
    for px, py in edge:
        along = (px - ax) * ux + (py - ay) * uy
        across = abs((px - ax) * uy - (py - ay) * ux)
        if across > tol or along < -tol or along > length + tol:
            return False
    return True


def _corners(poly_pct: Sequence[Sequence[float]], W: float, H: float,
             also: Sequence[tuple[float, float]] = ()) -> list[tuple[float, float]]:
    """The outline's corners: vertices with a real turn at them — and the vertices at `also` (page points),
    turn or not: the end of an imaginary boundary that continues a wall face in one straight line is where a
    WALL ends, though the outline does not turn there."""
    pts = [(float(x) * W, float(y) * H) for x, y in poly_pct]
    n = len(pts)
    if n < 3:
        return []
    keep = []
    for i in range(n):
        a, b, c = pts[i - 1], pts[i], pts[(i + 1) % n]
        ang1 = math.atan2(b[1] - a[1], b[0] - a[0])
        ang2 = math.atan2(c[1] - b[1], c[0] - b[0])
        turn = abs((math.degrees(ang2 - ang1) + 180) % 360 - 180)
        if turn >= CORNER_DEG or any(math.dist(b, q) <= IMAGINARY_TOL_PT for q in also):
            keep.append(b)
    return keep if len(keep) >= 3 else pts


def _edge_frame(edge) -> tuple[bool | None, float, float, float]:
    """(horizontal? — None when slanted, start, end, position): the edge's
    extent along its axis and its other coordinate."""
    (ax, ay), (bx, by) = edge
    dx, dy = abs(bx - ax), abs(by - ay)
    tilt = math.degrees(math.atan2(min(dx, dy), max(dx, dy)))
    if tilt > AXIS_DEG:
        return None, 0.0, 0.0, 0.0
    if dx >= dy:
        return True, min(ax, bx), max(ax, bx), (ay + by) / 2
    return False, min(ay, by), max(ay, by), (ax + bx) / 2


def _strings_on_base(dims: Sequence[dict], alignment: dict) -> dict[int, list[dict]]:
    """Line-backed strings, mapped onto their plan group's base page."""
    by_base: dict[int, list[dict]] = {}
    for d in dims:
        if d.get("span_source") != "line" or not d.get("span") or d.get("line_pos") is None:
            continue
        p = int(d["page"])
        b = base_page(alignment, p)
        t = (alignment.get("transform") or {}).get(p) or {"k": 1.0, "dx": 0.0, "dy": 0.0}
        a0, a1 = (float(v) for v in d["span"])
        horiz = d.get("orientation") == "h"
        along, across = (t["dx"], t["dy"]) if horiz else (t["dy"], t["dx"])
        s0, s1 = t["k"] * a0 + along, t["k"] * a1 + along
        # where the string's dimension line is on ITS OWN sheet (page fractions) — the check sheet marks
        # the very numbers that were added, on the sheet they are written on
        W, H = float(d.get("page_width") or 0), float(d.get("page_height") or 0)
        lp = float(d["line_pos"])
        line_pct = None
        if W > 0 and H > 0:
            ends = [(a0, lp), (a1, lp)] if horiz else [(lp, a0), (lp, a1)]
            line_pct = [[round(x / W, 5), round(y / H, 5)] for x, y in ends]
        by_base.setdefault(b, []).append({"page": p, "text": str(d["text"]), "value_m": float(d["value_m"]), "horiz": horiz,
                                          "s0": min(s0, s1), "s1": max(s0, s1), "pos": t["k"] * lp + across,
                                          "line_pct": line_pct, "ilgis_pt": d.get("ilgis_pt")})
    return by_base


def _slanted_on_base(dims: Sequence[dict], alignment: dict) -> dict[int, list[dict]]:
    """Strings written along a SLANTED dimension line (plan_dimensions, `orientation == "s"`), their line's
    two ends mapped onto the plan group's base page."""
    by_base: dict[int, list[dict]] = {}
    for d in dims:
        line = d.get("line")
        if d.get("orientation") != "s" or d.get("span_source") != "line" or not line or len(line) != 2:
            continue
        p = int(d["page"])
        t = (alignment.get("transform") or {}).get(p) or {"k": 1.0, "dx": 0.0, "dy": 0.0}
        ends = [(t["k"] * float(x) + t["dx"], t["k"] * float(y) + t["dy"]) for x, y in line]
        W, H = float(d.get("page_width") or 0), float(d.get("page_height") or 0)
        line_pct = [[round(float(x) / W, 5), round(float(y) / H, 5)] for x, y in line] if W > 0 and H > 0 else None
        by_base.setdefault(base_page(alignment, p), []).append(
            {"page": p, "text": str(d["text"]), "value_m": float(d["value_m"]), "a": ends[0], "b": ends[1], "line_pct": line_pct,
             "ilgis_pt": d.get("ilgis_pt")})
    return by_base


def _slanted_row(strings: Sequence[dict], edge, near: float, tol: float, inside: Polygon | None, length_m: float) -> list[dict] | None:
    """The ONE string that states a slanted wall: written along a line parallel to the wall, within `near` of
    it, whose ends stand opposite the wall's two corners, and whose value is the wall's own length. The room's
    side of the wall is preferred, then the nearest."""
    (ax, ay), (bx, by) = edge
    length = math.hypot(bx - ax, by - ay)
    if length <= 0:
        return None
    ux, uy = (bx - ax) / length, (by - ay) / length
    found = []
    for s in strings:
        (px, py), (qx, qy) = s["a"], s["b"]
        sl = math.hypot(qx - px, qy - py)
        if sl <= 0:
            continue
        tilt = abs(((math.degrees(math.atan2(qy - py, qx - px)) - math.degrees(math.atan2(uy, ux))) + 90) % 180 - 90)
        if tilt > SLANT_PARALLEL_DEG:
            continue
        along = sorted(((px - ax) * ux + (py - ay) * uy, (qx - ax) * ux + (qy - ay) * uy))
        across = abs(((px + qx) / 2 - ax) * uy - ((py + qy) / 2 - ay) * ux)
        if across > near or abs(along[0]) > tol or abs(along[1] - length) > tol:
            continue
        if abs(s["value_m"] - length_m) > max(WALL_TOL * length_m, WALL_TOL_M):
            continue
        own = inside is None or inside.contains(Point((px + qx) / 2, (py + qy) / 2))
        found.append((not own, across, s))
    if not found:
        return None
    return [min(found, key=lambda f: (f[0], f[1]))[2]]


def _page_size(dims: Sequence[dict], page: int) -> tuple[float, float]:
    for d in dims:
        if int(d.get("page", 0)) == page and d.get("page_width") and d.get("page_height"):
            return float(d["page_width"]), float(d["page_height"])
    return 595.2756, 841.8898


def _fill_holes(row: Sequence[dict], e0: float, e1: float, tol: float, m_per_pt: float,
                openings: Sequence[tuple[float, float, float, str]]) -> list[dict] | None:
    """The wall from corner to corner as its PARTS in order — strings, and what fills the holes between them:
    {"text"} | {"anga_m", "i"} (the room's own opening in this wall, exactly where the hole is — a designer
    never writes a door's width into a wall chain) | {"trumpa_m"} (a pier shorter than SHORT_EDGE_M nobody
    dimensioned). A hole that is neither → None. Short fills may add up to SHORT_HOLES_MAX_M per wall."""
    parts: list[dict] = []
    short_total = 0.0

    def hole(a: float, b: float) -> bool:
        nonlocal short_total
        length = (b - a) * m_per_pt
        if length <= HOLE_IGNORE_M:
            return True                                        # the strings touch
        for g0, g1, width_m, leads_to in openings:
            if abs(g0 - a) <= tol and abs(g1 - b) <= tol:
                parts.append({"anga_m": round(width_m, 3), "i": leads_to})
                return True
        if length < SHORT_EDGE_M and short_total + length <= SHORT_HOLES_MAX_M:
            short_total += length
            parts.append({"trumpa_m": round(length, 2)})
            return True
        return False

    cur = e0
    for s in row:
        if not hole(cur, s["s0"]):
            return None
        parts.append({"text": s["text"]})
        cur = max(cur, s["s1"])
    return parts if hole(cur, e1) else None


def _stating_row(strings: Sequence[dict], horiz: bool, e0: float, e1: float, epos: float, near: float, tol: float,
                 inside: Polygon | None, length_m: float, m_per_pt: float = 0.0,
                 openings: Sequence[tuple[float, float, float, str]] = ()) -> tuple[list[dict], list[dict] | None] | None:
    """(the row of strings that states the wall, its PARTS when holes had to be filled — else None).

    A row runs from one end of the wall to the other without a hole (module doc for the order rows are
    tried in). Only when no such row exists is a row WITH holes taken — each hole the room's own opening
    in this wall or a short pier (`_fill_holes`), and the whole still adding up to the wall's length."""
    cands = [s for s in strings if s["horiz"] == horiz and abs(s["pos"] - epos) <= near
             and s["s0"] >= e0 - tol and s["s1"] <= e1 + tol]
    rows: list[list[dict]] = []
    for s in sorted(cands, key=lambda s: (s["page"], s["pos"])):     # a row is one sheet's strings on one dimension line
        if rows and s["page"] == rows[-1][0]["page"] and abs(s["pos"] - rows[-1][0]["pos"]) <= TIER_PT:
            rows[-1].append(s)
        else:
            rows.append([s])

    def own_side(row: list[dict]) -> bool:
        if inside is None:
            return True
        mid = (row[0]["s0"] + row[-1]["s1"]) / 2
        x, y = (mid, row[0]["pos"]) if horiz else (row[0]["pos"], mid)
        return inside.contains(Point(x, y))

    # the room's own side first; the wall's one string before a chain that adds up to it; then the nearest
    ordered = sorted(rows, key=lambda r: (not own_side(r), len(r) > 1, abs(r[0]["pos"] - epos)))
    for row in ordered:
        row.sort(key=lambda s: s["s0"])
        if abs(row[0]["s0"] - e0) > tol or abs(row[-1]["s1"] - e1) > tol:
            continue
        if any(abs(b["s0"] - a["s1"]) > tol for a, b in zip(row, row[1:])):
            continue
        # The corner tolerance alone lets a 0,8 m door string pass for a 0,95 m
        # wall (objektas_g room 06): the row's sum must be the wall's length too.
        if abs(sum(s["value_m"] for s in row) - length_m) > max(WALL_TOL * length_m, WALL_TOL_M):
            continue
        return row, None
    if m_per_pt <= 0:
        return None
    # No row runs corner to corner. A row with HOLES states the wall when every hole is accounted for
    # (objektas_h bedroom 09: „660" | the 1,40 m door to the bathroom | „1538" = the 3,60 m wall).
    for row in ordered:
        if any(b["s0"] < a["s1"] - tol for a, b in zip(row, row[1:])):
            continue                                           # strings that overlap are not one chain
        parts = _fill_holes(row, e0, e1, tol, m_per_pt, openings)
        if parts is None:
            continue
        total = sum(s["value_m"] for s in row) + sum(p.get("anga_m", 0.0) + p.get("trumpa_m", 0.0) for p in parts)
        if abs(total - length_m) > max(WALL_TOL * length_m, WALL_TOL_M):
            continue
        return row, parts
    return None


def sum_perimeters(rooms: Sequence[dict], dims: Sequence[dict], alignment: dict, scale_by_page: dict[int, float],
                   page_sizes: dict[int, tuple[float, float]] | None = None) -> dict:
    summary: dict[str, list[str]] = {"stated": [], "blank": [], "skipped": []}
    by_base = _strings_on_base(dims, alignment)
    slanted_by_base = _slanted_on_base(dims, alignment)
    for room in rooms:
        nr = str(room.get("nr") or "")
        if room.get("perimetras_saltinis") in KEEP and room.get("perimetras_m"):
            summary["skipped"].append(nr)
            continue
        poly_pct = room.get("polygon_pct")
        if not poly_pct or room.get("polygon_source") not in WALL_OUTLINES:
            summary["skipped"].append(nr)
            continue
        kont = room.get("_konturas") or {}
        page = int(kont.get("page") or room.get("puslapio_nr") or 1)
        base = base_page(alignment, page)
        m_per_pt = scale_by_page.get(base) or scale_by_page.get(page)
        if not m_per_pt:
            summary["skipped"].append(nr)
            continue
        W, H = (page_sizes or {}).get(page) or _page_size(dims, page)
        # the outline lives on `page`; strings are in the base page's frame
        boundary_ends = [(float(pt[0]) * W, float(pt[1]) * H) for seg in (kont.get("menamos") or []) for pt in seg]
        corners = [to_base(alignment, page, *c) for c in _corners(poly_pct, W, H, boundary_ends)]
        edges = [(corners[i], corners[(i + 1) % len(corners)]) for i in range(len(corners))] if len(corners) >= 3 else []
        inside = Polygon(corners) if len(corners) >= 3 else None
        if inside is not None and not inside.is_valid:
            inside = inside.buffer(0) if not inside.buffer(0).is_empty else None
        near, tol = NEAR_M / m_per_pt, END_TOL_M / m_per_pt
        # An open plan a person divided (vector_rooms.split_space): the boundary between the two rooms is
        # an edge of both outlines and a wall of neither — not summed, not checked, never asked a length for.
        imaginary = [(to_base(alignment, page, float(a[0]) * W, float(a[1]) * H), to_base(alignment, page, float(b[0]) * W, float(b[1]) * H))
                     for a, b in (kont.get("menamos") or [])]
        edges = [e for e in edges if not any(_on_segment(e, seg, IMAGINARY_TOL_PT) for seg in imaginary)]
        # the room's OWN openings (geometry lane, `_angos_sienose`), on the base page: what may fill a hole in a chain
        gaps = []
        rec = room.get("_angos_sienose") if isinstance(room.get("_angos_sienose"), dict) else {}
        o_page = int(rec.get("page") or page)
        oW, oH = (page_sizes or {}).get(o_page) or _page_size(dims, o_page)
        for o in rec.get("angos") or []:
            try:
                (x0, y0), (x1, y1) = o["line_pct"]
                p0 = to_base(alignment, o_page, float(x0) * oW, float(y0) * oH)
                p1 = to_base(alignment, o_page, float(x1) * oW, float(y1) * oH)
                gaps.append((p0, p1, float(o["plotis_m"]), str(o.get("i") or "")))
            except (KeyError, TypeError, ValueError):
                continue
        sienos = []
        for edge in edges:
            horiz, e0, e1, epos = _edge_frame(edge)
            control = round(math.dist(*edge) * m_per_pt, 3)
            parts = None
            if horiz is None:                                  # a slanted wall: the string written along its own slanted line
                row = _slanted_row(slanted_by_base.get(base, []), edge, near, tol, inside, control)
            else:
                on_wall = []
                for p0, p1, width_m, leads_to in gaps:
                    if (abs(p1[0] - p0[0]) >= abs(p1[1] - p0[1])) != horiz:
                        continue
                    pos = (p0[1] + p1[1]) / 2 if horiz else (p0[0] + p1[0]) / 2
                    g0, g1 = sorted((p0[0], p1[0]) if horiz else (p0[1], p1[1]))
                    if abs(pos - epos) <= OPENING_NEAR_M / m_per_pt and g0 >= e0 - tol and g1 <= e1 + tol:
                        on_wall.append((g0, g1, width_m, leads_to))
                hit = _stating_row(by_base.get(base, []), horiz, e0, e1, epos, near, tol, inside, control, m_per_pt, on_wall)
                row, parts = hit if hit else (None, None)
            length = None
            if row:
                length = sum(s["value_m"] for s in row) + sum(p.get("anga_m", 0.0) + p.get("trumpa_m", 0.0) for p in (parts or []))
            wall = {"edge_pct": [[round(edge[0][0] / W, 5), round(edge[0][1] / H, 5)],
                                 [round(edge[1][0] / W, 5), round(edge[1][1] / H, 5)]],
                    "ilgis_m": round(length, 3) if length is not None else None,
                    "saltinis": "eilute" if row else None,
                    "eilutes": [{"text": s["text"], "value_m": s["value_m"], "page": s["page"], "line_pct": s["line_pct"],
                                 "ilgis_pt": s.get("ilgis_pt")}
                                for s in (row or [])],
                    "kontrole_m": control, "istriza": horiz is None, "_frame": (horiz, e0, e1)}
            if parts:
                wall["dalys"] = parts                          # in order along the wall: what was read, what filled the holes
            sienos.append(wall)
        # A length written once: the wall OPPOSITE with the same extent is as
        # long — the same number is read for both, and the wall says whose it is.
        for s in sienos:
            if s["ilgis_m"] is not None or s["_frame"][0] is None:
                continue
            horiz, e0, e1 = s["_frame"]
            twin = next((o for o in sienos if o is not s and o["saltinis"] == "eilute" and o["_frame"][0] == horiz
                         and abs(o["_frame"][1] - e0) <= tol and abs(o["_frame"][2] - e1) <= tol), None)
            if twin is not None:
                s["ilgis_m"] = twin["ilgis_m"]
                s["saltinis"] = "priesinga_siena"
                s["eilutes"] = [dict(e) for e in twin["eilutes"]]
        repeated = sum(1 for s in sienos if s["saltinis"] == "priesinga_siena")
        for s in sienos:
            del s["_frame"]
        control_total = round(sum(s["kontrole_m"] for s in sienos), 2)
        # short pieces nobody dimensioned: no number to read — from the outline, and said so
        short = [s for s in sienos if s["ilgis_m"] is None and s["kontrole_m"] < SHORT_EDGE_M]
        from_outline = round(sum(s["kontrole_m"] for s in short), 2)
        if short and control_total and from_outline <= SHORT_SHARE * control_total:
            for s in short:
                s["ilgis_m"] = s["kontrole_m"]
                s["saltinis"] = "konturas"
        else:
            from_outline = 0.0
        missing = [s for s in sienos if s["ilgis_m"] is None]
        slanted = [s for s in missing if s["istriza"]]
        for s in sienos:
            del s["istriza"]
        room["_sienos"] = sienos
        total = round(sum(s["ilgis_m"] or 0.0 for s in sienos), 2)
        pages = sorted({int(e["page"]) for s in sienos for e in s["eilutes"]})
        texts = [e["text"] for s in sienos if s["saltinis"] == "eilute" for e in s["eilutes"]]
        # what the chains' holes added: the rooms' own openings, and piers nobody dimensioned (said with the short pieces)
        from_openings = round(sum(p.get("anga_m", 0.0) for w in sienos for p in (w.get("dalys") or [])), 2)
        from_piers = round(sum(p.get("trumpa_m", 0.0) for w in sienos for p in (w.get("dalys") or [])), 2)
        suma = {"suma_m": total, "kontrole_m": control_total, "sutampa": False, "lapai": pages, "eilutes": texts,
                "is_konturo_m": round(from_outline + from_piers, 2) if not missing else 0.0, "pakartota": repeated,
                "angos_m": from_openings if not missing else 0.0}
        if kont.get("plotas_nesutampa"):
            reason = AREA_MISMATCH_REASON
        elif not sienos:
            reason = "kontūras be sienų"
        elif missing:
            reason = f"{len(missing)} iš {len(sienos)} sienų be matmens"
            if slanted:
                reason += f" ({len(slanted)} įstriža — jos ilgis plane neužrašytas)" if len(slanted) == 1 else \
                          f" ({len(slanted)} įstrižos — jų ilgiai plane neužrašyti)"
        elif not control_total or abs(total - control_total) / control_total > CONTROL_TOL:
            reason = (f"matmenų suma {total:.2f} m nesutampa su kontūru {control_total:.2f} m").replace(".", ",")
        else:
            reason = None
        if reason is None:
            suma["sutampa"] = True
            room["perimetras_m"] = total
            room["perimetras_saltinis"] = SOURCE
            for key in ("_perimetras_priezastis", "_perimetras_ivertis_m", "_perimetras_ivertis_saltinis"):
                room.pop(key, None)
            summary["stated"].append(nr)
        else:
            # NOT a read figure — the sheet shows a blank and offers this number. It still has to BE the
            # room's perimeter: the sąmata rows (grindjuostės, silikonavimas, hidroizoliacijos juosta…)
            # are built straight from `perimetras_m`, and a None there silently zeroed objektas_g's
            # bathroom rows (eval 2026-09-19: rows within ±10 % fell 15 → 10 %). The SOURCE carries the truth.
            estimate = control_total
            matched = _matched_to_table(room, kont, control_total)
            if matched:                                # an outline whose area is off the table's: its length × √(table / outline)
                estimate = matched["ivertis_m"]
                suma["pagal_plota"] = matched
            room["perimetras_m"] = estimate if estimate > 0 else None
            room["perimetras_saltinis"] = ESTIMATE_SOURCE if estimate > 0 else None
            room["_perimetras_priezastis"] = reason
            room["_perimetras_ivertis_m"] = estimate
            room["_perimetras_ivertis_saltinis"] = "konturas"
            summary["blank"].append(nr)
        room["_perimetras_suma"] = suma
    return summary
