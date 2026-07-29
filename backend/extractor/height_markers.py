"""Deterministic ceiling-height marker scanner.

LT projektiniai pjūviai (sections) annotate vertical levels with markers like
`+0.000` (floor reference), `+2.800` / `+3.000` (ceiling slab top), `+5.700`
(2nd floor ceiling or ridge). When Vision misses these on the cover/section
page, the system falls back to the 2.80 m default — burying real ceilings
above 3 m and skewing every wall-paint quantity downstream.

This scanner reads the PDF text layer (no Vision call) and surfaces the
plausible ceiling-height candidates so the extractor can use them as a
deterministic fallback. Reference: docs/2026-05-07-launch-status.md §3.
"""
from __future__ import annotations

import io
import re

# +3.000 / +2,800 / ±0.000 / + 3.000 — sign followed by decimal value.
# Capture group 1 is the numeric portion (handles both `.` and `,` decimals).
_HEIGHT_MARKER_RE = re.compile(r'[+±]\s*(\d+[.,]\d{1,3})')

# Plausible ceiling height range for LT residential / commercial buildings.
# Below 2.0 m is impractical (post-2000 modern minimum is 2.5–2.65 m); above
# 4.5 m is more likely a ridge / roof / mansard apex than a ceiling slab.
MIN_CEILING_M = 2.0
MAX_CEILING_M = 4.5


def scan_page_height_markers(
    pdf_bytes: bytes,
    page_nrs: tuple[int, ...] = (1,),
) -> list[dict]:
    """Scan the given PDF pages for elevation/ceiling-height markers.

    Args:
        pdf_bytes: Raw PDF bytes.
        page_nrs: 1-indexed page numbers to scan. Defaults to (1,) because
            the cover/section is almost always page 1 of LT interior projects.

    Returns:
        List of {"page": int, "raw": str, "value_m": float} dicts for each
        plausible match within MIN/MAX_CEILING_M. Order preserves page order
        and within-page text order. Empty list on any pdfplumber error
        (defensive — caller treats absence as "no signal", not as failure).
    """
    try:
        import pdfplumber
    except ImportError:
        return []

    out: list[dict] = []
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for pn in page_nrs:
                if pn < 1 or pn > len(pdf.pages):
                    continue
                try:
                    text = pdf.pages[pn - 1].extract_text() or ""
                except Exception:
                    continue
                for m in _HEIGHT_MARKER_RE.finditer(text):
                    raw = m.group(0)
                    val_str = m.group(1).replace(',', '.')
                    try:
                        val = float(val_str)
                    except ValueError:
                        continue
                    if MIN_CEILING_M <= val <= MAX_CEILING_M:
                        out.append({"page": pn, "raw": raw, "value_m": val})
    except Exception:
        return []
    return out


def best_ceiling_candidate(markers: list[dict]) -> dict | None:
    """Pick the largest in-range marker as the most likely ceiling height.

    LT pjūviai typically annotate (in ascending order): `±0.000` floor,
    `+2.400`–`+2.500` beam undersides, `+2.800`–`+3.200` ceiling slab top,
    `+5.700`+ second-floor ceiling or ridge. The largest value still inside
    [MIN_CEILING_M, MAX_CEILING_M] is — within a single floor — almost
    always the actual ceiling slab top.

    For multi-floor buildings the caller should rerun per-floor; the
    universal fallback uses the largest single-floor candidate.
    """
    if not markers:
        return None
    return max(markers, key=lambda m: m["value_m"])


# 2026-05-11 W2: salvage heights from Vision warnings[] narrative.
#
# Even with the imperative prompt iteration that fixed projektas_1
# (commit be422a7), Vision still narrates rather than structures on
# some PDFs — specifically when there's value-ambiguity ("švarus
# lubų aukštis" = clean/finished vs raw) or room-mapping ambiguity
# ("3200mm visose voniose" — which bathrooms exactly). This salvage
# pass mines the free-text warnings for known height patterns and
# applies them deterministically.

# "300cm", "320cm", "294cm" — centimetres
_HEIGHT_CM_RE = re.compile(r'(\d{3})\s*cm\b')
# "3.20m", "2,82 m", "5,7m" — explicit metres
_HEIGHT_M_RE = re.compile(r'(\d[.,]\d{1,2})\s*m\b')
# "3200mm", "2800mm" — millimetres
_HEIGHT_MM_RE = re.compile(r'(\d{4})\s*mm\b')
# "+3000", "+3.000", "+3,000" — drafting marker
_HEIGHT_MARKER_RE = re.compile(r'\+\s*(\d[.,]?\d{1,3})')

# 2026-07-07 fix (objektas_b pastoliai collapse): double-height living spaces
# are real ceilings — Vision narrated "dvigubo aukščio lubas (~5.7m)" for the
# 62 m² svetainė but MAX_CEILING_M=4.5 (a page-marker band meant to reject
# RIDGE markers on sections) threw the value away, so every room kept 2.82 m
# and the virš-3m split + pastolių line zeroed out against a contractor who
# bills 68.28 m² of >3m ceiling and 90 d.d. of tall scaffolds. In the salvage
# lane the value comes from Vision's own sentence about a NAMED room's lubos —
# far stronger context than a bare drafting marker — so allow up to a
# double-height interior, but only when the warning actually talks about
# lubos/aukštis (guards against wall-LENGTH narrations like "siena 5.2m ilgio").
MAX_NARRATED_CEILING_M = 6.5
_CEILING_CONTEXT_RE = re.compile(r'lub|aukš', re.IGNORECASE)


def _to_metres(raw: str, unit: str, max_m: float = MAX_CEILING_M) -> float | None:
    """Convert raw numeric string + unit to metres. Returns None if outside
    the plausible ceiling range [MIN_CEILING_M, max_m] to keep noise out of
    structured data."""
    try:
        val = float(raw.replace(',', '.'))
    except ValueError:
        return None
    if unit == "cm":
        val = val / 100.0
    elif unit == "mm":
        val = val / 1000.0
    elif unit == "marker":
        # "+3000" → 3.000 m; "+3.000" → 3.000 m; "+3,2" → 3.2 m
        if val > 100:        # bare integer like 3000
            val = val / 1000.0
    if not (MIN_CEILING_M <= val <= max_m):
        return None
    return val


def salvage_heights_from_warnings(
    warnings: list,
    rooms: list[dict],
) -> dict:
    """Mine height info out of Vision's free-text warnings when the
    structured `lubu_auksciai` / `lubu_auksciai_by_nr` fields stayed
    empty.

    Strategy: for each warning text, scan for room names (from
    `rooms[].pavadinimas`) that co-occur with a height pattern within
    the same warning. If a clear pairing exists, write into the
    returned dict.

    Conservative: only emits a mapping when room name + height appear
    in the SAME warning text. We don't try to be clever across multiple
    warnings or rooms.
    """
    if not warnings or not rooms:
        return {}
    result: dict[str, float] = {}

    # Index room names (case-insensitive, longest first to win against
    # partial overlaps like "Vonia" vs "Vaikų vonia").
    room_names = sorted(
        {(r.get("pavadinimas") or "").strip() for r in rooms if r.get("pavadinimas")},
        key=lambda n: -len(n),
    )

    # 2026-07-04 fix (Rangovas B GKP height-split): compound room names like
    # "Svetainė/valgomasis/virtuvė" never substring-matched warnings that name
    # only one component ("… svetainė ~3000mm iš vizualizacijos"), so the
    # narrated height was silently dropped and the room kept the 2.82 default —
    # zeroing the virš-3m GKP/paint split. Index each "/"-separated component
    # (≥5 chars, compound-separator split only — NOT whitespace, to avoid
    # generic-word false positives) as an alias for the canonical name.
    name_variants: list[tuple[str, str]] = []
    for name in room_names:
        lc = name.lower()
        name_variants.append((lc, name))
        for part in re.split(r"[/,+]", lc):
            part = part.strip()
            if len(part) >= 5 and part != lc:
                name_variants.append((part, name))
    name_variants.sort(key=lambda t: -len(t[0]))

    for w in warnings:
        if isinstance(w, dict):
            text = " ".join(filter(None, [
                w.get("message"),
                w.get("code"),
            ])) or ""
        else:
            text = str(w)
        if not text:
            continue

        # Collect every plausible height value from this single warning.
        # Warnings that explicitly talk about lubos/aukštis get the extended
        # double-height band; anything else keeps the strict scanner band.
        max_m = (MAX_NARRATED_CEILING_M if _CEILING_CONTEXT_RE.search(text)
                 else MAX_CEILING_M)
        heights: list[float] = []
        for m in _HEIGHT_MARKER_RE.finditer(text):
            v = _to_metres(m.group(1), "marker", max_m)
            if v is not None:
                heights.append(v)
        for m in _HEIGHT_M_RE.finditer(text):
            v = _to_metres(m.group(1), "m", max_m)
            if v is not None:
                heights.append(v)
        for m in _HEIGHT_CM_RE.finditer(text):
            v = _to_metres(m.group(1), "cm", max_m)
            if v is not None:
                heights.append(v)
        for m in _HEIGHT_MM_RE.finditer(text):
            v = _to_metres(m.group(1), "mm", max_m)
            if v is not None:
                heights.append(v)

        if not heights:
            continue

        # Pick the height most likely to be the "main" reading in this
        # warning: max value (since the bug being salvaged is
        # always "Vision saw a non-default height" — the default 2.82
        # would not have been worth narrating).
        height = max(heights)

        # Find every room name mentioned in this warning text.
        # Apply the height to all rooms named here. If none named,
        # try paskirtis-based generic phrases ("vonios", "gyvenamosios").
        text_lc = text.lower()
        matched_rooms: list[str] = []
        for variant, canonical in name_variants:
            if variant in text_lc and canonical not in matched_rooms:
                matched_rooms.append(canonical)

        # Paskirtis-based fallback. Generic phrases like "visose voniose"
        # or "gyvenamoms patalpoms" map to all rooms with the matching
        # paskirtis. Order matters: more-specific phrases first.
        if not matched_rooms:
            paskirtis_phrases = {
                "vonia": ["voniose", "vonios", "vonioje", "vonioms",
                          "san. mazgu", "san. mazguose"],
                "wc": ["wc", "tualet"],
                "virtuve": ["virtuv"],
                "gyvenamoji": ["gyvenamiems patalp", "gyvenamomis", "gyvenamose"],
                "miegamoji": ["miegam"],
                "koridorius": ["koridor"],
                "skalbykla": ["skalb"],
                "garazas": ["garaž"],
            }
            for canonical_p, triggers in paskirtis_phrases.items():
                if not any(t in text_lc for t in triggers):
                    continue
                for room in rooms:
                    name = (room.get("pavadinimas") or "").strip()
                    room_p = (room.get("paskirtis") or "").lower()
                    if not name or name in result:
                        continue
                    # Match by paskirtis OR by name keyword (e.g.
                    # "vonia" room named "Vaikų san. mazgas" has
                    # paskirtis "vonia" or "san_mazgas")
                    if canonical_p in room_p or any(
                        t in name.lower() for t in triggers
                    ):
                        matched_rooms.append(name)

        for name in matched_rooms:
            # First match wins per room — keep the height from the
            # warning that explicitly named it.
            result.setdefault(name, height)

    return result


# ═══════════════════════════════════════════════════════════════════════════
# POSITIONED ceiling-altitude markers (2026-07-29)
# ═══════════════════════════════════════════════════════════════════════════
#
# The scanner above throws away the one thing that makes a lubų-plano marker
# unambiguous: WHERE it is printed. `scan_page_height_markers` collapses a
# whole sheet into "the largest plausible value", and Vision — asked to read
# the same sheet holistically — collapses it the other way, into "+2800 visos
# kitos patalpos". Both readings lose the room→value pairing that the drawing
# states explicitly by placing each altitude inside a room outline.
#
# Measured case — Beržų g. 24, page 6 (LUBŲ PLANAS). Its legend literally
# says "Lubų apačios altitudė, aukštis nuo grindų, mm", and the text layer
# carries 14 positioned markers. Room 101 (Tambūras) is bracketed by two
# `+3400`; the nearest `+2800` sits past the wall in 103/107. Three separate
# production Vision runs read that room 2.8 / 2.8 / 3.4 — a coin flip on
# 42.5 m² of high wall and 11.0 m² of high ceiling. Point-in-polygon over the
# printed markers returns 3.4 on all three, from the same bytes, for free.
#
# Two deliberate limits:
#   • ONLY pages the extract itself classified `ceiling_plan`. On a section
#     a "+2800" is a level on a vertical drawing and the room polygons are
#     floor-plan-frame percentages, so containment would be meaningless; on
#     a floor plan a "+3.000" can be the slab level of the storey above.
#     Widening this needs its own evidence.
#   • A frame-agreement gate (below). Room polygons come from Vision looking
#     at the FLOOR-plan page; using them on the ceiling-plan page assumes both
#     sheets place the drawing in the same frame. That assumption is checked,
#     not asserted — see `frame_agreement`.

# A standalone marker token as `extract_words()` yields it: "+2800", "+3.400",
# "±0.000". Anchored — "A+2800" or "2800" alone is not an altitude marker.
_POSITIONED_MARKER_RE = re.compile(r'^[+±]\s*(\d+(?:[.,]\d{1,3})?)$')
# A bare room number as printed on the plan: "101", "12". 2–4 digits.
_ROOM_NR_TOKEN_RE = re.compile(r'^\d{2,4}$')

# Positioned markers get the wider band the warnings salvage uses: a double
# -height slice is real, and unlike a bare section marker this value is
# geometrically tied to one room, so a stray ridge value cannot go project-wide.
POSITIONED_MIN_M = MIN_CEILING_M
POSITIONED_MAX_M = MAX_NARRATED_CEILING_M

# Frame-agreement gate. Of the rooms that carry a polygon/bbox, this share
# must have their own room-number label printed inside their own outline on
# the marker page before we trust the two frames to be the same. Beržų scores
# 10/11 and 11/11 across runs; a section page or a mismatched sheet scores ~0.
MIN_FRAME_AGREEMENT = 0.6
MIN_AGREEING_ROOMS = 3


def _marker_value_m(raw: str) -> float | None:
    """Parse a positioned marker token into metres, or None.

    LT lubų planai print altitudes in mm (`+3400`); pjūviai print metres
    (`+3.400`). Same >100 heuristic the warnings salvage uses.
    """
    m = _POSITIONED_MARKER_RE.match(raw.strip())
    if not m:
        return None
    try:
        val = float(m.group(1).replace(',', '.'))
    except ValueError:
        return None
    if val > 100:            # bare mm integer
        val = val / 1000.0
    if not (POSITIONED_MIN_M <= val <= POSITIONED_MAX_M):
        return None
    return round(val, 3)


def scan_positioned_page_tokens(
    pdf_bytes: bytes,
    page_nrs: tuple[int, ...] | list[int],
) -> dict:
    """Read altitude markers AND room-number labels off the given pages,
    each with its centre expressed as a fraction of page width/height.

    Percent coordinates (not points) because that is the space room
    ``polygon_pct`` / ``bbox_pct`` already live in, and it survives the
    A1-vs-A3 sheet-size differences across a project set.

    Returns ``{"markers": [...], "labels": [...]}``; both lists are empty on
    any pdfplumber failure (absence = "no signal", never a hard failure).
    """
    try:
        import pdfplumber
    except ImportError:
        return {"markers": [], "labels": []}

    markers: list[dict] = []
    labels: list[dict] = []
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for pn in page_nrs:
                if pn < 1 or pn > len(pdf.pages):
                    continue
                page = pdf.pages[pn - 1]
                width = float(page.width or 0)
                height = float(page.height or 0)
                if width <= 0 or height <= 0:
                    continue
                try:
                    words = page.extract_words()
                except Exception:
                    continue
                for w in words:
                    text = str(w.get("text") or "").strip()
                    if not text:
                        continue
                    try:
                        x_pct = ((float(w["x0"]) + float(w["x1"])) / 2) / width
                        y_pct = ((float(w["top"]) + float(w["bottom"])) / 2) / height
                    except (KeyError, TypeError, ValueError):
                        continue
                    value = _marker_value_m(text)
                    if value is not None:
                        markers.append({"page": pn, "raw": text, "value_m": value,
                                        "x_pct": x_pct, "y_pct": y_pct,
                                        "page_w": width, "page_h": height})
                    elif _ROOM_NR_TOKEN_RE.match(text):
                        labels.append({"page": pn, "nr": text.lstrip("0") or "0",
                                       "x_pct": x_pct, "y_pct": y_pct,
                                       "page_w": width, "page_h": height})
    except Exception:
        return {"markers": [], "labels": []}
    return {"markers": markers, "labels": labels}


def _room_outline(room: dict) -> tuple[list[tuple[float, float]], float] | None:
    """Return (polygon_points_pct, area_pct) for a room, or None.

    Prefers ``polygon_pct`` (a real traced outline when the polygon lane
    produced one); falls back to the ``bbox_pct`` rectangle.
    """
    poly = room.get("polygon_pct")
    pts: list[tuple[float, float]] = []
    if isinstance(poly, (list, tuple)) and len(poly) >= 3:
        for p in poly:
            try:
                pts.append((float(p[0]), float(p[1])))
            except (TypeError, ValueError, IndexError):
                pts = []
                break
    if len(pts) < 3:
        bb = room.get("bbox_pct")
        if not isinstance(bb, dict):
            return None
        try:
            x, y = float(bb["x"]), float(bb["y"])
            w, h = float(bb["w"]), float(bb["h"])
        except (KeyError, TypeError, ValueError):
            return None
        if w <= 0 or h <= 0:
            return None
        pts = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
    # Shoelace area — the "most specific" tie-break when outlines overlap.
    area = abs(sum(pts[i][0] * pts[(i + 1) % len(pts)][1]
                   - pts[(i + 1) % len(pts)][0] * pts[i][1]
                   for i in range(len(pts)))) / 2.0
    return pts, area


def _point_in_polygon(x: float, y: float,
                      pts: list[tuple[float, float]]) -> bool:
    """Ray-casting point-in-polygon. Boundary counts as inside-ish (a marker
    printed exactly on a traced wall line belongs to that room)."""
    inside = False
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            x_cross = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x <= x_cross:
                inside = not inside
    return inside


def _centroid(pts: list[tuple[float, float]]) -> tuple[float, float]:
    return (sum(p[0] for p in pts) / len(pts),
            sum(p[1] for p in pts) / len(pts))


def _norm_nr(raw) -> str:
    s = str(raw or "").strip()
    return (s.lstrip("0") or "0") if s.isdigit() else s.lower()


def frame_agreement(labels: list[dict], rooms: list[dict]) -> dict:
    """How many rooms have their own number printed inside their own outline
    on the marker page.

    This is the honest check on the cross-page assumption: room outlines are
    read off the FLOOR plan, markers off the CEILING plan. If both sheets
    frame the drawing identically the labels land inside; if the sheets are
    scaled/offset differently, or the page is a section, they do not — and
    the caller declines to assign anything.
    """
    agree, total = 0, 0
    for room in rooms:
        outline = _room_outline(room)
        if outline is None:
            continue
        pts, _ = outline
        total += 1
        nr = _norm_nr(room.get("nr"))
        if not nr:
            continue
        if any(lbl.get("nr") == nr and _point_in_polygon(
                float(lbl["x_pct"]), float(lbl["y_pct"]), pts)
                for lbl in labels):
            agree += 1
    ratio = (agree / total) if total else 0.0
    return {"agree": agree, "total": total, "ratio": round(ratio, 3)}


def assign_markers_to_rooms(markers: list[dict], labels: list[dict],
                            rooms: list[dict]) -> dict:
    """Assign each positioned altitude marker to the room whose outline
    contains it, and reduce the per-room marker set to one height.

    Reduction rule: the DOMINANT value (most markers), tie broken by the
    marker printed nearest the room centroid — the most specific reading
    the drawing offers for that room. A room bracketed by two `+3400` with
    one `+2800` clipping its edge reads 3.4, which is what the drawing says.

    Returns a dict that always carries ``ok`` and ``reason``; when ``ok`` is
    False the caller must keep whatever heights it already had.
    """
    out: dict = {
        "ok": False,
        "reason": "",
        "frame": {"agree": 0, "total": 0, "ratio": 0.0},
        "by_nr": {},
        "evidence": {},
        "unassigned": [],
        "rooms_without_marker": [],
    }
    if not markers:
        out["reason"] = "no_positioned_markers"
        return out
    if not rooms:
        out["reason"] = "no_rooms"
        return out

    outlines: list[tuple[str, list[tuple[float, float]], float]] = []
    for room in rooms:
        outline = _room_outline(room)
        if outline is None:
            continue
        pts, area = outline
        outlines.append((str(room.get("nr") or "").strip(), pts, area))
    if not outlines:
        out["reason"] = "no_room_outlines"
        return out

    frame = frame_agreement(labels, rooms)
    out["frame"] = frame
    if frame["agree"] < MIN_AGREEING_ROOMS or frame["ratio"] < MIN_FRAME_AGREEMENT:
        out["reason"] = (f"frame_mismatch({frame['agree']}/{frame['total']}) — "
                         f"room numbers are not printed inside their own "
                         f"outlines on the marker page")
        return out

    hits: dict[str, list[dict]] = {}
    for marker in markers:
        mx, my = float(marker["x_pct"]), float(marker["y_pct"])
        candidates = [(area, nr, pts) for nr, pts, area in outlines
                      if nr and _point_in_polygon(mx, my, pts)]
        if not candidates:
            out["unassigned"].append({"raw": marker["raw"],
                                      "value_m": marker["value_m"],
                                      "page": marker["page"]})
            continue
        # Smallest containing outline wins — the most specific room.
        area, nr, pts = min(candidates, key=lambda c: c[0])
        cx, cy = _centroid(pts)
        hits.setdefault(nr, []).append({
            **marker,
            "_dist": ((mx - cx) ** 2 + (my - cy) ** 2) ** 0.5,
        })

    for nr, ms in hits.items():
        counts: dict[float, int] = {}
        for m in ms:
            counts[m["value_m"]] = counts.get(m["value_m"], 0) + 1
        nearest_by_value: dict[float, float] = {}
        for m in ms:
            v = m["value_m"]
            if v not in nearest_by_value or m["_dist"] < nearest_by_value[v]:
                nearest_by_value[v] = m["_dist"]
        chosen = min(counts, key=lambda v: (-counts[v], nearest_by_value[v]))
        out["by_nr"][nr] = chosen
        out["evidence"][nr] = {
            "chosen_m": chosen,
            "page": ms[0]["page"],
            "markers": sorted(m["raw"] for m in ms),
            "values_m": sorted(m["value_m"] for m in ms),
        }

    out["rooms_without_marker"] = [
        str(r.get("nr") or "").strip() for r in rooms
        if str(r.get("nr") or "").strip() not in out["by_nr"]
    ]
    out["ok"] = bool(out["by_nr"])
    if not out["ok"]:
        out["reason"] = "no_marker_fell_inside_any_room"
    return out


# ═══════════════════════════════════════════════════════════════════════════
# LABEL-PROXIMITY fallback (2026-07-29)
# ═══════════════════════════════════════════════════════════════════════════
#
# `assign_markers_to_rooms` above is the precise lane, and it stays the
# preferred one — a traced outline states exactly which room a point is in.
# But it needs outlines, and it refuses to run unless the room numbers print
# inside their own outlines on the marker page. On Beržų g. 24 only 1 of 11
# rooms carries any geometry at all, so `frame_agreement` scores 1/1, trips
# MIN_AGREEING_ROOMS, and the corpus's richest marker sheet (14 altitudes
# against 11 rooms) yields nothing. The lane has never once fired there.
#
# The drawing offers a second pairing that needs no polygons: the room NUMBER
# is printed on the SAME sheet as the altitude, in the SAME coordinate system.
# No cross-page frame assumption to check — the two tokens are a few
# millimetres apart on one piece of paper.
#
# What it cannot do is see walls. A marker deep inside a narrow room can be
# nearer to the neighbouring room's label than to its own (Beržų: the +3400
# at (540,202) is 68 pt from 104's label and 81 pt from 101's, and it belongs
# to 101). So proximity alone is not enough, and this lane refuses rather
# than guesses in exactly that case:
#
#   • DISTANCE CAP — a marker must be printed near the room it labels.
#     Calibrated on Beržų p6: every honest marker is within 121 pt of its
#     room number (0.083 of the page diagonal); the `+3100` legend key in the
#     "Sutartiniai žymėjimai" box is 209 pt (0.144) from anything. The cap
#     sits between them and is expressed as a fraction of the page DIAGONAL
#     so it survives A1-vs-A3 sheets.
#   • AMBIGUITY MARGIN — if the second-nearest room is nearly as close, the
#     drawing has not said which room owns the marker. Drop it and say so.
#     This is what stops the +3400 above from raising 104 to 3.4.
#
# Both thresholds are calibrated on one project. That is stated, not hidden:
# they are deliberately loose enough to keep every honest Beržų marker and
# tight enough to reject its two known traps, and the lane is allowed only to
# RAISE a height (see `vision_call`), so a miss costs coverage, never a
# fabricated quantity.

# Fractions of the page diagonal. Observed on Beržų p6: honest markers
# ≤0.083, legend key 0.144; closest honest margin 0.020, the known
# cross-wall steal 0.008.
MAX_LABEL_DISTANCE_FRAC = 0.12
MIN_AMBIGUITY_MARGIN_FRAC = 0.015


def _norm_xy(tok: dict) -> tuple[float, float]:
    """Token centre in a space normalised so the page diagonal is 1.

    ``x_pct``/``y_pct`` are fractions of WIDTH and HEIGHT respectively, so
    Euclidean distance between them is skewed by the sheet's aspect ratio
    (1.41 on A-series). Scaling each axis back by its own dimension and
    dividing by the diagonal makes a distance mean "this fraction of the
    sheet", on any sheet size. Tokens without page dimensions (hand-built in
    tests, or older cached runs) fall back to a unit square.
    """
    w = float(tok.get("page_w") or 1.0) or 1.0
    h = float(tok.get("page_h") or 1.0) or 1.0
    diag = ((w * w + h * h) ** 0.5) or 1.0
    return (float(tok["x_pct"]) * w / diag, float(tok["y_pct"]) * h / diag)


def assign_markers_by_label_proximity(markers: list[dict], labels: list[dict],
                                      rooms: list[dict]) -> dict:
    """Assign each positioned altitude to the room whose NUMBER is printed
    nearest to it on the same sheet, refusing when the pairing is unclear.

    Same contract as `assign_markers_to_rooms`: always returns ``ok`` and
    ``reason``; when ``ok`` is False the caller keeps the heights it had.
    ``unassigned`` carries a per-marker ``reason`` so the refusals are
    inspectable rather than silent.
    """
    out: dict = {
        "ok": False,
        "reason": "",
        "method": "label_proximity",
        "by_nr": {},
        "evidence": {},
        "unassigned": [],
        "rooms_without_marker": [],
    }
    if not markers:
        out["reason"] = "no_positioned_markers"
        return out
    if not rooms:
        out["reason"] = "no_rooms"
        return out

    # Only a token that matches a real room number may steer a marker.
    # `_ROOM_NR_TOKEN_RE` ("2–4 digits") also matches dimension strings like
    # "1200"/"3200" and stray sheet numbers, which are printed all over a plan.
    known = {_norm_nr(r.get("nr")) for r in rooms if str(r.get("nr") or "").strip()}
    known.discard("")
    plan_labels = [l for l in labels if _norm_nr(l.get("nr")) in known]
    if not plan_labels:
        out["reason"] = "no_room_labels"
        return out

    # Group labels by room: a number is typically printed twice (once on the
    # plan, once in the eksplikacija table down the margin). Taking the
    # per-room MINIMUM distance means the table copy can never be mistaken
    # for a second, competing room.
    by_room: dict[str, list[dict]] = {}
    for lbl in plan_labels:
        by_room.setdefault(_norm_nr(lbl.get("nr")), []).append(lbl)

    hits: dict[str, list[dict]] = {}
    for marker in markers:
        try:
            mx, my = _norm_xy(marker)
        except (KeyError, TypeError, ValueError):
            continue
        ranked: list[tuple[float, str]] = []
        for nr, lbls in by_room.items():
            best = min((((mx - lx) ** 2 + (my - ly) ** 2) ** 0.5
                        for lx, ly in (_norm_xy(l) for l in lbls)),
                       default=None)
            if best is not None:
                ranked.append((best, nr))
        if not ranked:
            continue
        ranked.sort()
        d0, nr0 = ranked[0]
        d1 = ranked[1][0] if len(ranked) > 1 else float("inf")

        note = {"raw": marker.get("raw"), "value_m": marker.get("value_m"),
                "page": marker.get("page"), "nearest_nr": nr0,
                "distance": round(d0, 4)}
        if d0 > MAX_LABEL_DISTANCE_FRAC:
            # Printed nowhere near a room — a legend key, a title-block
            # sample, or an altitude belonging to a room we never read.
            out["unassigned"].append({**note,
                                      "reason": "too_far_from_any_room_label"})
            continue
        if (d1 - d0) < MIN_AMBIGUITY_MARGIN_FRAC:
            out["unassigned"].append({**note, "runner_up_nr": ranked[1][1],
                                      "reason": "ambiguous_between_rooms"})
            continue
        hits.setdefault(nr0, []).append({**marker, "_dist": d0})

    # Same reduction as the polygon lane: the DOMINANT value, ties broken by
    # the marker printed nearest the room's number.
    for nr, ms in hits.items():
        counts: dict[float, int] = {}
        for m in ms:
            counts[m["value_m"]] = counts.get(m["value_m"], 0) + 1
        nearest_by_value: dict[float, float] = {}
        for m in ms:
            v = m["value_m"]
            if v not in nearest_by_value or m["_dist"] < nearest_by_value[v]:
                nearest_by_value[v] = m["_dist"]
        chosen = min(counts, key=lambda v: (-counts[v], nearest_by_value[v]))
        out["by_nr"][nr] = chosen
        out["evidence"][nr] = {
            "chosen_m": chosen,
            "page": ms[0]["page"],
            "method": "label_proximity",
            "markers": sorted(str(m["raw"]) for m in ms),
            "values_m": sorted(m["value_m"] for m in ms),
        }

    out["rooms_without_marker"] = [
        str(r.get("nr") or "").strip() for r in rooms
        if _norm_nr(r.get("nr")) not in out["by_nr"]
    ]
    out["ok"] = bool(out["by_nr"])
    if not out["ok"]:
        out["reason"] = "no_marker_matched_a_room"
    return out


# ═══════════════════════════════════════════════════════════════════════════
# The lane, end to end
# ═══════════════════════════════════════════════════════════════════════════
#
# One entry point so production (`vision_call`) and the eval harness's
# deterministic tail run the SAME code. The harness measuring something the
# app does not do is how a fix gets "proven" and then fails in front of a
# customer; this is deterministic and costs no API call, so there is no
# reason for the two to differ.

# Below this gap a marker that reads LOWER than the room's existing height is
# just a rounding/plane difference. At or above it, the plan is labelling one
# ceiling plane of a split-level or double-height space (objektas_b's 5.7 m
# svetainė) — taking the marker there would delete the tall zone and zero the
# virš-3m tier with it. Keep the taller value and disclose.
SPLIT_LEVEL_GAP_M = 0.5
# Heights within this of each other are the same reading.
_HEIGHT_EPS_M = 0.05


def apply_positioned_marker_heights(parsed: dict, pdf_bytes: bytes,
                                    emit=None) -> dict:
    """Read the altitudes printed inside each room on the lubų planas and
    RAISE that room's ceiling height to match. Mutates and returns ``parsed``.

    Deterministic and zero-cost: text layer + geometry, no Vision call.

    Direction is deliberately asymmetric — the lane may raise a height or
    confirm one, never lower it. A marker labels ONE ceiling plane, so a
    marker below the height already read is at best a lower plane of the same
    room and at worst the collapse this lane exists to prevent. A miss
    therefore costs coverage, never a fabricated quantity.

    Rooms the lane could not reach keep whatever they had and are named in
    the warnings (`lt_rules.apply_lt_sanity`).
    """
    def _emit(payload: dict) -> None:
        if emit:
            try:
                emit(payload)
            except Exception:
                pass

    rooms = parsed.get("patalpos") or []
    if not rooms or not pdf_bytes:
        return parsed
    try:
        from extractor.page_classifier import canonical_tipas
    except Exception:
        return parsed

    pages = []
    for p in (parsed.get("puslapiai") or []):
        try:
            if p.get("nr") and canonical_tipas(p.get("tipas")) == "ceiling_plan":
                pages.append(int(p["nr"]))
        except (TypeError, ValueError):
            continue
    if not pages:
        return parsed

    tokens = scan_positioned_page_tokens(pdf_bytes, tuple(pages))
    # Polygon containment first — a traced outline states which room a point
    # is in; proximity only infers it. The fallback exists because outlines
    # are frequently absent (Beržų: 1 of 11 rooms).
    assign = assign_markers_to_rooms(
        tokens["markers"], tokens["labels"], rooms)
    method = "polygon_containment"
    polygon_reason = None
    if not assign["ok"]:
        polygon_reason = assign["reason"]
        fallback = assign_markers_by_label_proximity(
            tokens["markers"], tokens["labels"], rooms)
        if fallback["ok"]:
            assign, method = fallback, "label_proximity"

    lane = {
        "pages": pages,
        "n_markers": len(tokens["markers"]),
        "ok": assign["ok"],
        "reason": assign["reason"],
        "method": method if assign["ok"] else None,
        "polygon_reason": polygon_reason,
        "frame": assign.get("frame"),
        "evidence": assign.get("evidence", {}),
        "unassigned": assign.get("unassigned", []),
        "rooms_without_marker": assign.get("rooms_without_marker", []),
    }
    parsed["_height_marker_lane"] = lane

    if not assign["ok"]:
        _emit({"event": "positioned_marker_lane_skipped",
               "reason": assign["reason"], "pages": pages,
               "polygon_reason": polygon_reason,
               "n_markers": len(tokens["markers"])})
        return parsed

    by_nr = {_norm_nr(k): v for k, v in assign["by_nr"].items()}
    evidence = {_norm_nr(k): v for k, v in assign.get("evidence", {}).items()}
    by_name = dict(parsed.get("lubu_auksciai") or {})
    by_nr_map = dict(parsed.get("lubu_auksciai_by_nr") or {})
    changed, confirmed, kept_taller, kept_lower = [], [], [], []

    for room in rooms:
        nr_raw = str(room.get("nr") or "").strip()
        marker_h = by_nr.get(_norm_nr(nr_raw))
        if marker_h is None:
            continue
        try:
            prev = float(room["lubu_aukstis_m"]) if room.get(
                "lubu_aukstis_m") is not None else None
        except (TypeError, ValueError):
            prev = None

        if prev is not None and prev - marker_h >= SPLIT_LEVEL_GAP_M:
            room["_height_marker_conflict"] = {
                "marker_m": marker_h, "kept_m": prev,
                "reason": "split_level_suspected"}
            kept_taller.append({"nr": nr_raw, "marker": marker_h, "kept": prev})
            continue
        if prev is not None and marker_h < prev - _HEIGHT_EPS_M:
            # Raise-only: a lower marker is a lower plane, not a correction.
            room["_height_marker_lower_ignored"] = {
                "marker_m": marker_h, "kept_m": prev}
            kept_lower.append({"nr": nr_raw, "marker": marker_h, "kept": prev})
            continue

        # Write BOTH maps — the merge downstream is name-keyed and a stale
        # name entry would otherwise beat the marker.
        by_nr_map[nr_raw] = marker_h
        name = room.get("pavadinimas")
        if name:
            by_name[name] = marker_h
        room["lubu_aukstis_m"] = marker_h
        room["lubu_aukstis_saltinis"] = "ceiling_plan_marker"
        room["_height_source"] = "positioned_marker"
        room["_height_marker_evidence"] = evidence.get(_norm_nr(nr_raw))
        # Survives `_apply_per_room_heights`, which returns fresh dicts and is
        # NAME-keyed — Beržų alone has two rooms called "Berniuko kambarys".
        room["_height_marker_m"] = marker_h
        if prev is None or abs(prev - marker_h) >= _HEIGHT_EPS_M:
            changed.append({"nr": nr_raw, "from": prev, "to": marker_h})
        else:
            confirmed.append(nr_raw)

    parsed["lubu_auksciai"] = by_name
    parsed["lubu_auksciai_by_nr"] = by_nr_map
    lane.update({"changed": changed, "confirmed": confirmed,
                 "kept_taller": kept_taller, "kept_lower": kept_lower})

    for room in rooms:
        if room.get("_height_source"):
            continue
        nr_raw = str(room.get("nr") or "").strip()
        room["_height_source"] = (
            "vision_per_room"
            if (nr_raw in by_nr_map or room.get("pavadinimas") in by_name)
            else "global_fallback"
        )

    _emit({"event": "height_from_positioned_markers", "pages": pages,
           "method": method, "assigned": len(by_nr), "changed": changed,
           "confirmed": len(confirmed), "kept_taller": kept_taller,
           "kept_lower": kept_lower, "frame": assign.get("frame"),
           "without_marker": assign.get("rooms_without_marker", [])})
    return parsed
