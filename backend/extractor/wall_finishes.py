"""Which finish each room's WALLS get, read from the drawing as drawn — per wall face (v4, 2026-10-26).

Until now a room's wall finish came from the finish sheets' TEXT (apdailos_reader: a sheet naming one room) or from
its purpose (a „tambūras" is not painted, a kitchen gets a 1,2 m tile band round the whole room). Text cannot say
which wall of which room a finish sits on, and the purpose rule is a guess (objektas_a: the hall's 52 m² of wall
painted 0, the kitchen's 33 m² band). The drawing does say, in two places:

  · the WALL-FINISH PLAN (sienų apdailos / dažymo / išklotinių ir apdailų planas): every finish is a coloured line
    drawn along the wall faces it covers, and the sheet's legend names each colour („Dažymas balta spalva",
    „Plytelės …", „Vaikiški tapetai", „Siena dengiama plokšte", „Veidrodis", „Glaistoma dažoma …", „Tekstūrinis
    tinkas"). The length of each colour along a room's outline is that finish's share of the room's walls — per
    wall face (each edge of the outline). A face with no line is a face the plan does not finish (a kitchen wall
    behind its cabinets, a built-in wardrobe wall), and an opening;
  · the ELEVATIONS (sienų išklotinės, extractor/elevation_panels.py): a finish zone drawn on a wall face —
    the kitchen backsplash between the counter and the wall cabinets, a tile field to 1,2 m — is the zone's own
    width × height, read from the elevation's dimension strings and marker labels.

This module is the plan part: geometry from the PDF's vector paths (PDFium, `pdf_vectors.page_paths`) and the
text layer's legend lines with their colours (`floor_coverings._page_text`). No model, no image. A legend line
must name a WALL finish and the legend must hold a paint line (a floor plan's tile legend is not a wall plan); a
colour two legend lines share is no key. Never raises.

Frame: DISPLAY points (origin top-left, /Rotate applied) — the frame of `pdf_vectors`, the outlines and the badges.
"""
from __future__ import annotations

import math
import re
from typing import Sequence

from shapely.geometry import LineString, MultiLineString, Point, Polygon
from shapely.ops import unary_union

from . import pdf_vectors

SOURCE = "sienu_apdailos_planas"          # room["_sienu_apdaila"]["saltinis"]: read off the wall-finish plan
CLASSES = ("dazymas", "plyteles", "tapetai", "plokste", "veidrodis", "molio_tinkas", "kita_danga")
CLASS_LT = {"dazymas": "dažoma", "plyteles": "plytelės", "tapetai": "tapetai", "plokste": "plokštė",
            "veidrodis": "veidrodis", "molio_tinkas": "dekoratyvinis tinkas", "kita_danga": "kita danga"}

# legend text → class (folded: upper case, no diacritics); first hit wins, so the specific finishes stand first
_CLASS_WORDS: tuple[tuple[str, re.Pattern], ...] = (
    ("molio_tinkas", re.compile(r"\bMOLIO TINK|DEKORATYVIN\w* TINK|TEKSTURIN\w* TINK|\bKALKIN\w* TINK|VENECIJIEC")),
    ("kita_danga", re.compile(r"\bMIKROCEMENT|\bBETONO EFEKT")),
    ("tapetai", re.compile(r"\bTAPET")),
    ("plyteles", re.compile(r"\bPLYTEL|\bMOZAIK|AKMENS MASES")),
    ("veidrodis", re.compile(r"\bVEIDROD")),
    ("plokste", re.compile(r"\bPLOKST|\bPANEL")),
    ("dazymas", re.compile(r"\bDAZ(OMA|YMAS|YTI|OMOS|OMAS|AI|U)\b|\bDAZOM|\bDAZYM")),
)
# a legend line that is not a WALL finish (the floor, the ceiling, skirting, lights …)
_NOT_WALL = re.compile(r"GRIND|\bLUB(U|OS|Y)\b|GRINDJUOST|SVIEST|ROZET|JUNGIKL|LED\b|NISA|NISOS|KARNIZ")
TITLE_RE = re.compile(r"SIEN\w* (APDAIL|DAZYM)|ISKLOTINIU IR APDAIL|APDAILU PLANAS|APDAILOS PLANAS|DAZYMO PLANAS")

COLOUR_TOL = 0.06          # a plan line is a legend colour when every channel is this close
MIN_CHROMA = 0.12          # a legend colour must be a COLOUR (a grey or black sample is the drawing's ink)
SAMPLE_REACH_PT = 140.0    # the line sample stands left of its legend text, at most this far
INSIDE_M = 0.04            # a finish line is drawn on or just inside the room's wall face: outward slack
REACH_M = 0.30             # a point of the outline is finished by a line this close to it
STEP_M = 0.05              # the outline is looked at every this many metres
MIN_SHARE_READ = 0.25      # a room whose outline the plan's lines cover less than this is not read
GAP_FILL_M = 0.35           # a stretch with no line this short beside a finished one is the line stopping short
MIN_CLASS_M = 0.3          # a finish along less of a room's outline than this is a neighbour's line round a corner
FACE_COVER_MIN = 0.10      # a face the lines cover less than this share of is one the plan does not finish…
FACE_UNFINISHED_MIN_M = 0.5  # …when, without its openings, at least this much wall is left


def _fold(text) -> str:
    import unicodedata
    s = unicodedata.normalize("NFD", str(text or "").upper())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.split())


def finish_class(text: str | None) -> str | None:
    """The wall-finish class a legend line names, else None."""
    f = _fold(text)
    if not f or _NOT_WALL.search(f):
        return None
    for klase, rx in _CLASS_WORDS:
        if rx.search(f):
            return klase
    return None


def _chroma(c) -> float:
    return (max(c) - min(c)) if c else 0.0


def _same(a, b) -> bool:
    return a is not None and b is not None and all(abs(x - y) <= COLOUR_TOL for x, y in zip(a, b))


def _bbox(subs) -> tuple[float, float, float, float]:
    xs = [x for s in subs for x, _ in s]
    ys = [y for s in subs for _, y in s]
    return min(xs), min(ys), max(xs), max(ys)


def read_legend(pdf_bytes: bytes, page: int) -> dict:
    """{rows: [{klase, colour, tekstas, box}], title: bool, box} — the legend lines of one sheet that name a wall
    finish, each with the colour of the line sample drawn left of it. A colour two lines share is dropped."""
    from .floor_coverings import _lines, _page_text
    W, H, plain, chars = _page_text(pdf_bytes, page)
    out = {"rows": [], "title": bool(TITLE_RE.search(_fold(plain))), "box": None}
    if not chars:
        return out
    lines = _lines(chars)
    paths = pdf_vectors.page_paths(pdf_bytes, page, strokes=True)
    named = [(ln, finish_class(ln["text"])) for ln in lines if len(ln["text"]) <= 90]
    named = [(ln, k) for ln, k in named if k]
    if not named:
        return out
    # every coloured piece left of a legend line votes for the NEAREST line on its height only — rows stand close
    # together and the next row's sample must not colour this one (objektas_a: „Vaikiški tapetai" took the blue of
    # „Veidrodis" under it)
    votes: list[dict[tuple, float]] = [{} for _ in named]
    for q in paths:
        col = q["stroke"] if _chroma(q["stroke"]) >= MIN_CHROMA else (q["fill"] if _chroma(q["fill"]) >= MIN_CHROMA else None)
        if col is None:
            continue
        key = tuple(round(v, 2) for v in col)
        for sub in q["subpaths"]:
            x0, y0, x1, y1 = _bbox([sub])
            cy = (y0 + y1) / 2
            best, bd = None, None
            for i, (ln, _k) in enumerate(named):
                hgt = max(ln["bottom"] - ln["top"], 4.0)
                if x1 > ln["x0"] + 1 or x0 < ln["x0"] - SAMPLE_REACH_PT or (y1 - y0) > 2.5 * hgt:
                    continue
                d = abs(cy - (ln["top"] + ln["bottom"]) / 2)
                if d <= 0.75 * hgt and (bd is None or d < bd):
                    best, bd = i, d
            if best is not None:
                votes[best][key] = max(votes[best].get(key, -1e9), x1)
    rows = []
    for (ln, klase), v in zip(named, votes):
        if not v:
            continue
        # the sample is the colour drawn right up to the text (a symbol of the plan further left is not it)
        colour = max(v, key=v.get)
        rows.append({"klase": klase, "colour": colour, "tekstas": ln["text"],
                     "box": [ln["x0"] - SAMPLE_REACH_PT, ln["top"], ln["x1"], ln["bottom"]]})
    keep = [r for r in rows if sum(1 for o in rows if _same(o["colour"], r["colour"])) == 1]
    out["rows"] = keep
    if keep:
        out["box"] = [min(r["box"][0] for r in keep), min(r["box"][1] for r in keep),
                      max(r["box"][2] for r in keep), max(r["box"][3] for r in keep)]
    return out


def is_wall_finish_legend(legend: dict) -> bool:
    """A wall-finish plan's key: it names a paint line and at least one wall finish line in all."""
    return any(r["klase"] == "dazymas" for r in legend.get("rows") or [])


def find_finish_sheets(pdf_bytes: bytes, pages: Sequence[int]) -> dict[int, dict]:
    """{page: legend} of the sheets whose legend is a wall-finish key (`is_wall_finish_legend`)."""
    out: dict[int, dict] = {}
    for p in sorted({int(x) for x in pages or []}):
        try:
            leg = read_legend(pdf_bytes, p)
        except Exception:  # noqa: BLE001 — an unreadable sheet is no finish sheet
            continue
        if is_wall_finish_legend(leg):
            out[p] = leg
    return out


def _class_lines(pdf_bytes: bytes, page: int, legend: dict) -> dict[str, object]:
    """{klase: MultiLineString} — every drawn piece in a legend colour, outside the legend itself."""
    paths = pdf_vectors.page_paths(pdf_bytes, page, strokes=True)
    box = legend.get("box")
    pieces: dict[str, list] = {}
    for q in paths:
        col = q["stroke"] if _chroma(q["stroke"]) >= MIN_CHROMA else (q["fill"] if _chroma(q["fill"]) >= MIN_CHROMA else None)
        if col is None:
            continue
        row = next((r for r in legend["rows"] if _same(r["colour"], col)), None)
        if row is None:
            continue
        for sub in q["subpaths"]:
            if len(sub) < 2:
                continue
            x0, y0, x1, y1 = _bbox([sub])
            if box and x0 >= box[0] - 2 and x1 <= box[2] + 2 and y0 >= box[1] - 6 and y1 <= box[3] + 6:
                continue
            try:
                pieces.setdefault(row["klase"], []).append(LineString(sub))
            except Exception:  # noqa: BLE001 — a degenerate piece
                continue
    return {k: unary_union(v) for k, v in pieces.items() if v}


def _faces(poly: Polygon) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    ring = list(poly.exterior.coords)
    return [(ring[i], ring[i + 1]) for i in range(len(ring) - 1) if ring[i] != ring[i + 1]]


def _poly(ring) -> Polygon | None:
    try:
        poly = Polygon([(float(x), float(y)) for x, y in ring]).buffer(0)
    except Exception:  # noqa: BLE001
        return None
    if poly.is_empty or poly.geom_type != "Polygon":
        return None
    return poly


def _nearest_class(p: Point, mine: dict, reach: float) -> str | None:
    best, bd = None, reach
    for k, g in mine.items():
        d = g.distance(p)
        if d <= bd:
            best, bd = k, d
    return best


def _along(line: LineString, mine: dict, step: float, reach: float, debug: list | None = None) -> dict[str, float]:
    """{klase: length} — how much of `line` (in its own units) each class covers."""
    L = line.length
    n = max(1, int(round(L / step)))
    pts = [line.interpolate((i + 0.5) / n, normalized=True) for i in range(n)]
    cls = [_nearest_class(p, mine, reach) for p in pts]
    # a short run with no line next to a finished stretch is where the designer's line stops short of a corner or
    # a dash ends — not a wall without finish (an opening is wider than GAP_FILL_M)
    fill = max(1, int(GAP_FILL_M / step))
    i = 0
    while i < n:
        if cls[i] is not None:
            i += 1
            continue
        j = i
        while j < n and cls[j] is None:
            j += 1
        left = cls[i - 1] if i > 0 else None
        right = cls[j] if j < n else None
        if (j - i) <= fill and (left or right):
            for t in range(i, j):
                cls[t] = left if (left and (t - i) < (j - i) / 2 or not right) else right
        i = j
    got: dict[str, float] = {}
    for p, best in zip(pts, cls):
        if best:
            got[best] = got.get(best, 0.0) + L / n
        if debug is not None:
            debug.append((p.x, p.y, best))
    return got


def _arc(ext: LineString, a: tuple[float, float], b: tuple[float, float]) -> LineString | None:
    """The shorter piece of the room's outline between the points nearest `a` and `b`."""
    from shapely.ops import linemerge, substring
    s1, s2 = ext.project(Point(a)), ext.project(Point(b))
    L = ext.length
    lo, hi = sorted((s1, s2))
    if hi - lo <= L / 2:
        piece = substring(ext, lo, hi)
    else:
        piece = linemerge(unary_union([substring(ext, hi, L), substring(ext, 0, lo)]))
    return piece if isinstance(piece, LineString) and piece.length > 0 else None


def read_rooms(pdf_bytes: bytes, page: int, legend: dict, m_per_pt: float, rings: dict[str, Sequence],
               openings: dict[str, list] | None = None, markers: dict[str, tuple] | None = None,
               elevation: Sequence[dict] | None = None, face_rooms: dict[tuple, str] | None = None,
               imaginary: dict[str, list] | None = None, debug: list | None = None) -> dict[str, dict]:
    """What the wall-finish plan `page` draws along each room's outline (`rings`: display points on `page`), face by
    face; with the elevation sheets' faces (`face_rooms` from elevation_panels.match_faces, `markers` the labels on
    `page`), what each elevation face carries.

    Record: {saltinis, page, konturas_m, klases_m, padengta_m, nepazymeta_m, sienos: [{ilgis_m, klases, angos_m,
    nepazymeta}], isklotines: {sienos: {"a6–a5": {ilgis_m, klases}}, zonos, plyteles, baldai, nepamatuota,
    puslapiai}}"""
    if not m_per_pt or m_per_pt <= 0:
        return {}
    lines = _class_lines(pdf_bytes, page, legend)
    if not lines:
        return {}
    step, reach = STEP_M / m_per_pt, REACH_M / m_per_pt
    openings = openings or {}
    out: dict[str, dict] = {}
    polys = {nr: p for nr, p in ((nr, _poly(r)) for nr, r in rings.items()) if p is not None}
    for nr, poly in polys.items():
        zone = poly.buffer(INSIDE_M / m_per_pt)
        mine = {}
        for k, g in lines.items():
            inside = g.intersection(zone)
            if not inside.is_empty:
                mine[k] = inside
        faces, totals, unfinished, open_m = [], {}, 0.0, 0.0
        cuts = [LineString([p1, p2]) for p1, p2 in (imaginary or {}).get(nr) or []]
        for a, b in _faces(poly):
            seg = LineString([a, b])
            Lm = seg.length * m_per_pt
            if any(c.buffer(1.0).contains(seg) for c in cuts):
                # the line dividing an open space between two rooms is an edge of the room, no wall of either
                faces.append({"ilgis_m": round(Lm, 3), "klases": {}, "menama": True})
                open_m += Lm
                continue
            got = _along(seg, mine, step, reach, debug)
            cov = sum(got.values()) * m_per_pt
            face = {"ilgis_m": round(Lm, 3), "klases": {k: round(v * m_per_pt, 3) for k, v in got.items()}}
            if cov < FACE_COVER_MIN * Lm:
                # a face the plan draws no finish along: minus the openings in it, what is left is a wall the plan
                # does not finish (a kitchen wall behind its cabinets, a wardrobe wall)
                gaps = 0.0
                for p1, p2, width_m in openings.get(nr) or []:
                    mid = Point((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2)
                    if seg.distance(mid) <= reach:
                        gaps += float(width_m or 0)
                left = Lm - gaps
                face["angos_m"] = round(gaps, 3)
                if left >= FACE_UNFINISHED_MIN_M:
                    face["nepazymeta"] = True
                    face["nepazymeta_m"] = round(left, 3)
            faces.append(face)
            for k, v in got.items():
                totals[k] = totals.get(k, 0.0) + v * m_per_pt
        outline_m = poly.exterior.length * m_per_pt - open_m
        gaps_m = sum(float(w or 0) for _p1, _p2, w in openings.get(nr) or [])
        # a colour along less than MIN_CLASS_M of the outline is the neighbour's line reaching round a corner
        covered = sum(v for v in totals.values() if v >= MIN_CLASS_M)
        out[nr] = {"saltinis": SOURCE, "page": int(page), "konturas_m": round(outline_m, 3),
                   "klases_m": {k: round(v, 3) for k, v in totals.items() if v >= MIN_CLASS_M},
                   "padengta_m": round(covered, 3), "angos_m": round(gaps_m, 3), "menamos_m": round(open_m, 3),
                   "nepazymeta_m": round(max(0.0, outline_m - gaps_m - covered), 3), "sienos": faces}
        # the elevation faces of this room: what the plan draws along each (the outline between its two labels)
        if face_rooms and markers:
            ext = LineString(list(poly.exterior.coords))
            sienos = {}
            for (fa, fb), owner in face_rooms.items():
                if owner != nr or fa not in markers or fb not in markers:
                    continue
                arc = _arc(ext, markers[fa], markers[fb])
                if arc is None:
                    continue
                got = _along(arc, mine, step, reach)
                sienos[f"{fa}–{fb}"] = {"ilgis_m": round(arc.length * m_per_pt, 3),
                                        "klases": {k: round(v * m_per_pt, 3) for k, v in got.items()}}
            if sienos:
                out[nr]["isklotines"] = {"sienos": sienos}
    if face_rooms and elevation:
        for sheet in elevation:
            for kind in ("zonos", "plyteles", "baldai", "nepamatuota"):
                for z in sheet.get(kind) or []:
                    nr = face_rooms.get((z["a"], z["b"]))
                    if nr not in out:
                        continue
                    el = out[nr].setdefault("isklotines", {"sienos": {}})
                    el.setdefault(kind, []).append({**z, "page": sheet["page"], "siena": f"{z['a']}–{z['b']}"})
                    pages = el.setdefault("puslapiai", [])
                    if sheet["page"] not in pages:
                        pages.append(sheet["page"])
    # a room the plan draws nothing along while it finishes the others: the plan leaves it unfinished
    finished = sum(1 for r in out.values() if r["padengta_m"] >= MIN_SHARE_READ * r["konturas_m"])
    for r in out.values():
        if r["padengta_m"] <= 0 and finished >= 3:
            r["tuscia"] = True
    return out


def is_read(rec: dict | None) -> bool:
    """A plan record the calculation takes: the plan's lines reach the room's outline, or the plan draws nothing
    along it at all while it finishes other rooms (`tuscia`: the plan leaves this room unfinished)."""
    if not isinstance(rec, dict) or rec.get("saltinis") != SOURCE:
        return False
    L = float(rec.get("konturas_m") or 0)
    if L <= 0:
        return False
    if rec.get("tuscia"):
        return True
    return float(rec.get("padengta_m") or 0) >= MIN_SHARE_READ * L
