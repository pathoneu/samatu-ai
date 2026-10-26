"""The finish ZONES the elevations (sienų išklotinės) draw on a wall face — read from the PDF's vector paths and its
text layer, no model, no image (v4, 2026-10-26).

An LT interior set draws each wall as an unfolded panel: the walls between two plan markers („a6" … „a5", „h1" …
„h4" — the same labels stand at the room's corners on the wall-finish plan) side by side, the marker labels under
the panel at the face ends. A finish that covers only part of a face is drawn on it as an outlined field — the
kitchen backsplash between the counter and the wall cabinets, a panel behind the bed, a mirror — and named by a
leader: a text line („Kronosceramiche plytelės lux venna 280x120cm", „Dengiama siena iš mėlynos spalvos plokštės")
with a hairline from the text to a dot inside the field. A sheet titled „Plytelių išklotinės" draws the tile
layout itself: the joints are a grid of coloured lines, as high as the tiles go.

What is read, per elevation sheet:
  · marker rows — single tokens that look like marker labels, three or more on one height: the faces between
    neighbours, each face a pair of labels and its x-span on the sheet;
  · leaders — a black hairline with one end at a finish text (wall_finishes.finish_class) and the other inside the
    smallest closed rectangle that holds it: that rectangle is the ZONE, its class the text's, its width × height
    the rectangle's size at the sheet's scale (the scale the geometry lane read from the sheet's own dimension
    lines). A zone that sits in no face's span, or is as big as a face's whole height band, is not a zone;
  · tile layouts — a marker row whose heading names „plytelių išklotinės": per face, how high the grid's coloured
    lines reach.

The faces are tied to rooms by the plan (`match_faces`): both labels of a face stand at the same room's outline on a
plan sheet. Nothing here is a quantity yet — wall_finishes / universal_rules decide what the zones take out of the
painted wall. Frame: DISPLAY points (origin top-left, /Rotate applied). Never raises.
"""
from __future__ import annotations

import re
from typing import Sequence

from . import pdf_vectors
from .wall_finishes import CLASS_LT, _fold, finish_class

MARKER_RE = re.compile(r"^(?:[A-Za-z]{1,2}-?\d{1,2}[a-z]?|\d{1,2}[a-z])$")
ROW_DY_PT = 6.0            # markers of one row stand on one height
MIN_ROW = 2                # a row is at least one face (two markers)
LEADER_END_PT = 4.0        # a leader starts this close to its text
MIN_ZONE_M = 0.2           # a zone is at least this wide and high
MAX_BAND_M = 7.0           # a panel stands at most this high above its markers
TILE_LAYOUT_RE = re.compile(r"PLYTELIU ISKLOTIN")
GRID_MIN_LINES = 4         # a tile layout grid has at least this many joint lines on a face


def _phrases(pdf_bytes: bytes, page: int) -> list[dict]:
    from .sheet_zones import display_frame, read_phrases
    fr = display_frame(pdf_bytes, page)
    if fr is None:
        return []
    ph, _n, _ok = read_phrases(pdf_bytes, page, (fr[0], fr[1]))
    return ph


def _level(p: dict) -> bool:
    """A phrase that reads left to right ON THE SHEET AS DISPLAYED (its box is as tall as its glyphs)."""
    h = float(p.get("h") or 0)
    if h <= 0:
        return p.get("turn", 0) == 0
    return abs((p["bottom"] - p["top"]) - h) <= 0.5 * h


def marker_rows(phrases: Sequence[dict]) -> list[list[dict]]:
    """Rows of marker labels, each sorted left to right: [{label, x, y}]."""
    marks = []
    for p in phrases:
        t = str(p.get("text") or "").strip()
        if _level(p) and MARKER_RE.match(t):
            marks.append({"label": t.lower(), "x": (p["x0"] + p["x1"]) / 2, "y": (p["top"] + p["bottom"]) / 2})
    rows: list[list[dict]] = []
    for m in sorted(marks, key=lambda m: m["y"]):
        if rows and abs(rows[-1][-1]["y"] - m["y"]) <= ROW_DY_PT:
            rows[-1].append(m)
        else:
            rows.append([m])
    out = []
    for r in rows:
        r = sorted(r, key=lambda m: m["x"])
        # one series of labels per row (a6 … a1): the letters must agree, else it is a table of codes
        prefixes = {re.sub(r"\d.*$", "", m["label"]) or re.sub(r"^\d+", "", m["label"]) for m in r}
        if len(r) >= MIN_ROW and len(prefixes) <= 3:
            out.append(r)
    return out


FURNITURE_RE = re.compile(r"\bGAMINAM|\bBALDAI\b|\bBALD\w* |\bLENTYN|\bSPINT|\bSTALCI|\bKABYKL")


def label_class(text: str) -> str | None:
    """A leader text's class: `baldai` for something MADE and stood in front of the wall („Gaminama iš baltos
    spalvos plokštės", „Baldai gaminami …", shelves) — the wall behind it is not finished by it — else the wall
    finish it names (wall_finishes.finish_class), else None."""
    f = _fold(text)
    if FURNITURE_RE.search(f) and not re.search(r"\bDENGIAM", f):
        return "baldai"
    return finish_class(text)


def _label_blocks(phrases: Sequence[dict]) -> list[dict]:
    """Leader texts: lines stacked under each other (aligned left or right, at most a line apart) are one label;
    a label is kept when its joined text names a wall finish or a piece of furniture (`label_class`)."""
    lines = sorted((p for p in phrases if _level(p)), key=lambda p: (p["top"], p["x0"]))
    used: set[int] = set()
    out = []
    for i, p in enumerate(lines):
        if i in used:
            continue
        block = [p]
        used.add(i)
        hgt = max(p["bottom"] - p["top"], 3.0)
        for j in range(i + 1, len(lines)):
            q = lines[j]
            if j in used:
                continue
            gap = q["top"] - block[-1]["bottom"]
            if gap > 0.9 * hgt:
                if q["top"] > block[-1]["bottom"] + 4 * hgt:
                    break
                continue
            if gap < -0.3 * hgt:
                continue
            last = block[-1]
            if abs(q["x1"] - last["x1"]) < 3 * hgt or abs(q["x0"] - last["x0"]) < 3 * hgt:
                block.append(q)
                used.add(j)
                if len(block) >= 4:
                    break
        text = " ".join(str(b.get("text") or "") for b in block).strip()
        klase = label_class(text)
        if klase:
            out.append({"klase": klase, "tekstas": text, "lines": block,
                        "x0": min(b["x0"] for b in block), "x1": max(b["x1"] for b in block),
                        "top": p["top"], "bottom": max(b["bottom"] for b in block)})
    return out


def _hairline_ends(paths: Sequence[dict]) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    """(start, end) of every black / dark stroked open subpath longer than 15 pt — the candidates for leaders."""
    out = []
    for q in paths:
        if q["fill"] is not None or q["stroke"] is None or max(q["stroke"]) > 0.35:
            continue
        for sub in q["subpaths"]:
            if len(sub) < 2:
                continue
            a, b = sub[0], sub[-1]
            if ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5 > 15:
                out.append((a, b))
    return out


def _leader_tips(ends: Sequence[tuple], label: dict) -> list[tuple[float, float]]:
    """The far ends of the hairlines that start at this label (at its first line's left or right end)."""
    first = label["lines"][0]
    ys = (first["top"], first["bottom"], (first["top"] + first["bottom"]) / 2)
    tips = []
    for s0, s1 in ends:
        for a, b in ((s0, s1), (s1, s0)):
            near_x = min(abs(a[0] - first["x0"]), abs(a[0] - first["x1"])) <= LEADER_END_PT
            if near_x and min(abs(a[1] - y) for y in ys) <= LEADER_END_PT:
                tips.append(b)
    return tips


def _rects(paths: Sequence[dict]) -> list[tuple[float, float, float, float]]:
    """Closed rectangles (axis-aligned subpaths of 4–5 points) — the outlines a zone can be."""
    out = []
    for q in paths:
        for sub in q["subpaths"]:
            if not (4 <= len(sub) <= 6):
                continue
            xs = sorted({round(x, 1) for x, _ in sub})
            ys = sorted({round(y, 1) for _, y in sub})
            closed = abs(sub[0][0] - sub[-1][0]) < 0.6 and abs(sub[0][1] - sub[-1][1]) < 0.6
            if closed and len(xs) == 2 and len(ys) == 2:
                out.append((xs[0], ys[0], xs[1], ys[1]))
    return out


def read_sheet(pdf_bytes: bytes, page: int, m_per_pt: float | None) -> dict:
    """{page, faces: [{a, b, x0, x1, y, y_top}], zonos / baldai: [{a, b, klase, tekstas, plotis_m, aukstis_m,
    plotas_m2, rect}], plyteles: [{a, b, aukstis_m}], nepamatuota: [{a, b, klase, tekstas}]} of one elevation sheet. Without a scale nothing is measured."""
    out = {"page": int(page), "faces": [], "zonos": [], "baldai": [], "plyteles": [], "nepamatuota": []}
    if not m_per_pt or m_per_pt <= 0:
        return out
    phrases = _phrases(pdf_bytes, page)
    rows = marker_rows(phrases)
    if not rows:
        return out
    paths = pdf_vectors.page_paths(pdf_bytes, page, strokes=True)
    band = MAX_BAND_M / m_per_pt
    faces = []
    tops = sorted(r[0]["y"] for r in rows)
    for r in rows:
        y = r[0]["y"]
        above = [t for t in tops if t < y - ROW_DY_PT]
        y_top = max([y - band] + [t + ROW_DY_PT for t in above])
        for m1, m2 in zip(r, r[1:]):
            if m1["label"] == m2["label"] or m2["x"] - m1["x"] < MIN_ZONE_M / m_per_pt:
                continue
            faces.append({"a": m1["label"], "b": m2["label"], "x0": m1["x"], "x1": m2["x"], "y": y, "y_top": y_top})
    out["faces"] = [{k: (round(v, 1) if isinstance(v, float) else v) for k, v in f.items()} for f in faces]

    def face_of(x: float, y: float):
        for f in faces:
            if f["x0"] - 1 <= x <= f["x1"] + 1 and f["y_top"] <= y <= f["y"]:
                return f
        return None

    rects = _rects(paths)
    ends = _hairline_ends(paths)
    seen = set()
    for lab in _label_blocks(phrases):
        for tip in _leader_tips(ends, lab):
            f = face_of(*tip)
            if f is None:
                continue
            inside = [r for r in rects if r[0] <= tip[0] <= r[2] and r[1] <= tip[1] <= r[3]
                      and (r[2] - r[0]) * m_per_pt >= MIN_ZONE_M and (r[3] - r[1]) * m_per_pt >= MIN_ZONE_M
                      and r[1] >= f["y_top"] - 1 and r[3] <= f["y"] + 1]
            if not inside:
                continue
            r = min(inside, key=lambda r: (r[2] - r[0]) * (r[3] - r[1]))
            key = (round(r[0]), round(r[1]), round(r[2]), round(r[3]))
            if key in seen:
                continue
            seen.add(key)
            w = (min(r[2], f["x1"]) - max(r[0], f["x0"])) * m_per_pt
            h = (r[3] - r[1]) * m_per_pt
            if w < MIN_ZONE_M:
                continue
            # the smallest outline round the dot is the face's own frame: the field itself has no outline of its
            # own (a hatch bounded by a dashed line) — nothing is measured, the label stays evidence
            whole = w >= 0.92 * (f["x1"] - f["x0"]) * m_per_pt and lab["klase"] != "plyteles"
            if whole and len([x for x in faces if x["y"] == f["y"]]) > 1:
                out["nepamatuota"].append({"a": f["a"], "b": f["b"], "klase": lab["klase"],
                                                          "tekstas": lab["tekstas"][:120]})
                continue
            out["baldai" if lab["klase"] == "baldai" else "zonos"].append({"a": f["a"], "b": f["b"], "klase": lab["klase"], "tekstas": lab["tekstas"][:120],
                                 "plotis_m": round(w, 3), "aukstis_m": round(h, 3), "plotas_m2": round(w * h, 3),
                                 "rect": [round(v, 1) for v in r]})
    # tile layouts: a row whose heading (just above its panel) names „plytelių išklotinės"
    heads = [p for p in phrases if TILE_LAYOUT_RE.search(_fold(p.get("text")))]
    for f in faces:
        if not any(f["y_top"] <= (h["top"] + h["bottom"]) / 2 <= f["y"] for h in heads):
            continue
        # the joints: the colour whose LONG straight strokes (≥ 0,3 m — a joint runs a tile's length; the
        # markers' dashes and the dimension ticks are short) are the most inside the face; their height is the tiles'
        by_col: dict[tuple, list] = {}
        for q in paths:
            col = q["stroke"]
            if col is None or q["fill"] is not None or max(col) - min(col) < 0.12:
                continue
            for sub in q["subpaths"]:
                for (x1, y1), (x2, y2) in zip(sub, sub[1:]):
                    if not (min(x1, x2) >= f["x0"] + 1 and max(x1, x2) <= f["x1"] - 1
                            and min(y1, y2) >= f["y_top"] and max(y1, y2) <= f["y"]):
                        continue
                    if max(abs(x2 - x1), abs(y2 - y1)) * m_per_pt < 0.3 or min(abs(x2 - x1), abs(y2 - y1)) > 1.0:
                        continue                                 # short, or not a straight joint
                    by_col.setdefault(tuple(col), []).append((min(y1, y2), max(y1, y2)))
        if not by_col:
            continue
        col, segs = max(by_col.items(), key=lambda kv: len(kv[1]))
        if len(segs) >= GRID_MIN_LINES:
            top = min(a for a, _ in segs)
            bottom = max(b for _, b in segs)
            out["plyteles"].append({"a": f["a"], "b": f["b"], "aukstis_m": round((bottom - top) * m_per_pt, 3)})
    return out


def plan_markers(pdf_bytes: bytes, page: int) -> dict[str, tuple[float, float]]:
    """{label: (x, y)} — the marker labels written on a plan sheet (display points); a label written twice is
    dropped (it cannot place a face)."""
    seen: dict[str, list] = {}
    for p in _phrases(pdf_bytes, page):
        t = str(p.get("text") or "").strip()
        if _level(p) and MARKER_RE.match(t):
            seen.setdefault(t.lower(), []).append(((p["x0"] + p["x1"]) / 2, (p["top"] + p["bottom"]) / 2))
    return {k: v[0] for k, v in seen.items() if len(v) == 1}


def match_faces(faces: Sequence[dict], markers: dict[str, tuple[float, float]],
                rooms: dict[str, Sequence[Sequence[float]]], m_per_pt: float, reach_m: float = 1.0) -> dict[tuple, str]:
    """{(a, b): nr} — the room each elevation face belongs to: both its labels stand at that room's outline on the
    plan (within `reach_m`), and of the rooms that qualify the one nearest to both and to the face's middle."""
    from shapely.geometry import Point, Polygon
    polys = {}
    for nr, ring in rooms.items():
        try:
            pg = Polygon([(float(x), float(y)) for x, y in ring]).buffer(0)
        except Exception:  # noqa: BLE001
            continue
        if not pg.is_empty:
            polys[nr] = pg
    reach = reach_m / m_per_pt
    out = {}
    for f in faces:
        a, b = markers.get(f["a"]), markers.get(f["b"])
        if a is None or b is None:
            continue
        mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        pa, pb, pmid = Point(a), Point(b), Point(mid)
        best, bd = None, None
        for nr, pg in polys.items():
            # A marker INSIDE the room polygon is distance 0 from it. 2026-10-26 fix:
            # both branches of the ternary used to be pg.exterior.distance, so a label
            # slightly inside the room polygon beyond `reach` of the exterior ring
            # could not match that room.
            da = 0.0 if pg.contains(pa) else pg.exterior.distance(pa)
            db = 0.0 if pg.contains(pb) else pg.exterior.distance(pb)
            dm = 0.0 if pg.contains(pmid) else pg.exterior.distance(pmid)
            if da > reach or db > reach or dm > reach:
                continue
            score = da + db + dm
            if bd is None or score < bd:
                best, bd = nr, score
        if best:
            out[(f["a"], f["b"])] = best
    return out


def zone_sentence(z: dict) -> str:
    return (f"Išklotinėje ({z.get('page')} lapas, siena {z['a'].upper()}–{z['b'].upper()}) nubraižyta "
            f"{CLASS_LT.get(z['klase'], z['klase'])}: {z['plotis_m']:.2f} × {z['aukstis_m']:.2f} m "
            f"= {z['plotas_m2']:.2f} m²".replace(".", ","))
