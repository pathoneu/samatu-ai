"""Which floor covering the FLOOR PLAN draws in each room — read, not guessed
from the room's purpose.

Until 2026-09-20 every room's floor followed its purpose („tambūras → plytelės",
„techninė patalpa → laminatas") and the check sheet said so in amber: „Brėžinys
nesako". The drawing does say. Both out-of-sample projects carry a floor-covering
sheet with a text layer, in two conventions:

  · `uzrasas` — the covering is WRITTEN inside the room („plytelės … 60×60 cm …
    3,95 m²", „laminuota grindų danga 76,65 m²");
  · `rastas`  — the covering is a coloured HATCH and its legend line is written
    in the SAME colour (a brown herringbone + brown „Grindys – …, eglutės
    raštas"; orange, green and blue grids + three tile lines).

On those two sheets the purpose rule was wrong exactly where the drawing is
plain: an entrance hall drawn with parquet, a plant room labelled with tiles.

Conservative on purpose — a wrong „read" is worse than a question:
  · only TILES and SOFT coverings are claimed (the engine's two billed floors);
    concrete, epoxy, decking are left alone;
  · skirting, grout, laying-start and heating lines are not coverings;
  · a black or grey legend is not a colour key; a legend line inside a room is
    a label, not a key;
  · a hatch must COVER the room (morphological closing of its strokes ≥ 35 % of
    the room), so dimension lines or a skirting line in the same colour do not
    count; two kinds of covering in one room, or a label against a hatch, is
    not a reading.
Nothing here measures a quantity: the room's area stays the stated one.

Frame: DISPLAY points (origin top-left, /Rotate applied) — the frame of
`pdf_vectors`, the outlines and the badges.
"""
from __future__ import annotations

import ctypes
import re
from typing import Iterable, Sequence

from shapely.geometry import Point, Polygon

from . import pdf_vectors
from .pdfium_guard import PDFIUM_LOCK
from .plan_area_annotations import _quarter_turn

TILE_RE = re.compile(r"plytel|akmens\s+mas|keramin", re.I)
SOFT_RE = re.compile(r"parket|laminat|laminuot|vinil|\blvt\b|\bspc\b|\bpvc\b|kilimin|linole|kamštin|grindlent", re.I)
FLOOR_WORD_RE = re.compile(r"\bgrindys\b|grind[ųu]\s+dang", re.I)
NOT_A_COVERING_RE = re.compile(
    r"grindjuost|juostel|klojimo|si[ūu]l|tarpai|slenkst|šild|sild|kolektor|termostat|\bplanas\b|pripjov|"
    r"hidroizol|\bsien|beton|epoksid|poliuret|šlifuot|liejam|teras", re.I)
# a TITLE, in the nominative: a note on an elevation sheet („siūles suvesti … vadovautis grindų
# planu") made two wall-tile sheets of a real project look like floor plans
FLOOR_TITLE_RE = re.compile(r"grind[ųu]\s+(dang(ų|u|os)\s+)?planas\b", re.I)
TITLE_MAX_CHARS = 70
AREA_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*m\s*[²2]", re.I)
BARE_NUMBER_RE = re.compile(r"^[\d.,\s]+$")

CLOSE_M = 0.65            # a hatch's strokes are closed over gaps up to 2 × this (a 120 × 120 cm tile grid)
CLOSE_PAGE_SHARE = 0.03   # …as a share of the page width when the sheet's scale is unknown
MIN_SHARE = 0.35          # of the room covered by one kind of covering
MIXED_SHARE = 0.25        # a second KIND this large → not a reading
MIN_SEGMENTS = 8          # sampled stroke points inside the room below which nothing is a hatch
POINT_R_M = 0.8           # a room known only by the place of its number: the disc looked at
LABEL_R_M = 2.0           # …and how far from that place a label may be written
COLOUR_TOL = 0.05
MIN_CHROMA = 0.15         # a legend colour must be a COLOUR (not black, not grey)
LABEL_LINES = 6
WALL_INSET_PT = 1.5
CORE_BAND_SHARE = 0.3     # the wall band is at most this share of √area
MIN_CORE_SHARE = 0.02     # of the room; below it the room is judged whole


def classify_line(text: str | None) -> str | None:
    """`plyteles` / `minksta` when the line names a floor covering, else None."""
    t = (text or "").strip()
    if not t or NOT_A_COVERING_RE.search(t):
        return None
    if TILE_RE.search(t):
        return "plyteles"
    if SOFT_RE.search(t) or FLOOR_WORD_RE.search(t):
        return "minksta"
    return None


# ── the text layer, with colours ─────────────────────────────────────────────

def _page_text(pdf_bytes: bytes, page_nr: int) -> tuple[float, float, str, list[dict]]:
    """(width, height, plain text, chars) of a 1-based page as displayed; chars
    are {text, x0, top, x1, bottom, size, colour}. An unreadable file or page
    is an empty page."""
    try:
        import pypdfium2 as pdfium
        import pypdfium2.raw as C
    except ImportError:
        return 0.0, 0.0, "", []
    with PDFIUM_LOCK:
        try:
            doc = pdfium.PdfDocument(pdf_bytes)
        except Exception:  # noqa: BLE001 — not a PDF
            return 0.0, 0.0, "", []
        try:
            if not (1 <= int(page_nr) <= len(doc)):
                return 0.0, 0.0, "", []
            page = doc[int(page_nr) - 1]
            tp = None
            try:
                Wd, Hd = (float(v) for v in page.get_size())
                k = (int(page.get_rotation() or 0) // 90) % 4
                W, H = (Hd, Wd) if k in (1, 3) else (Wd, Hd)          # the page before /Rotate
                tp = page.get_textpage()
                plain = tp.get_text_bounded() or ""
                r, g, b, a = (ctypes.c_uint() for _ in range(4))
                chars: list[dict] = []
                for i in range(tp.count_chars()):
                    t = tp.get_text_range(i, 1)
                    if not t or t in ("\r", "\n") or (len(t) == 1 and ord(t) < 32):
                        continue
                    # only text that reads left to right on the sheet AS DISPLAYED: a
                    # vertical dimension string's digits fall on a label's baseline by
                    # chance and ended up inside its quote („13vnt. 5 0 3.95 m 0").
                    # PDFium's angle grows clockwise; /Rotate turns the page clockwise.
                    if (_quarter_turn(C.FPDFText_GetCharAngle(tp, i)) + k) % 4 != 0:
                        continue
                    left, bottom, right, top = tp.get_charbox(i, loose=True)
                    pts = [pdf_vectors._to_display(x, y, W, H, k)
                           for x, y in ((left, bottom), (right, bottom), (left, top), (right, top))]
                    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
                    colour = None
                    if C.FPDFText_GetFillColor(tp, i, r, g, b, a):
                        colour = (round(r.value / 255, 2), round(g.value / 255, 2), round(b.value / 255, 2))
                    chars.append({"text": t, "x0": min(xs), "x1": max(xs), "top": min(ys), "bottom": max(ys),
                                  "size": max(max(ys) - min(ys), 1.0), "colour": colour})
                return Wd, Hd, plain, chars
            except Exception:  # noqa: BLE001 — a page without a text layer reads nothing
                return 0.0, 0.0, "", []
            finally:
                try:
                    if tp is not None:
                        tp.close()
                except Exception:  # noqa: BLE001
                    pass
                page.close()
        finally:
            doc.close()


def _lines(chars: Sequence[dict]) -> list[dict]:
    """Horizontal text lines rebuilt from characters: one BASELINE (a letter
    with a caron is taller than its neighbours, so tops differ and bottoms do
    not), left to right, split where the gap is wider than three character
    heights. {text, x0, top, x1, bottom, size, colour} — the colour most of
    the line's letters have."""
    rows: list[dict] = []                       # clusters of one baseline
    for c in sorted(chars, key=lambda c: c["bottom"]):
        row = rows[-1] if rows else None
        if row is not None and abs(row["bottom"] - c["bottom"]) <= 0.3 * max(c["size"], row["size"]):
            row["chars"].append(c)
            continue
        rows.append({"bottom": c["bottom"], "size": c["size"], "chars": [c]})
    out: list[dict] = []
    for row in rows:
        cur: list[dict] = []
        runs: list[list[dict]] = []
        for c in sorted(row["chars"], key=lambda c: c["x0"]):
            if cur and c["x0"] - max(ch["x1"] for ch in cur) > 3.0 * c["size"]:
                runs.append(cur)
                cur = []
            cur.append(c)
        if cur:
            runs.append(cur)
        for run in runs:
            parts: list[str] = []
            last_x1 = None
            for ch in run:
                if last_x1 is not None and not ch["text"].isspace() and parts and not parts[-1].isspace() \
                        and ch["x0"] - last_x1 > 0.25 * ch["size"]:
                    parts.append(" ")
                parts.append(ch["text"])
                last_x1 = ch["x1"]
            text = re.sub(r"\s+", " ", "".join(parts)).strip()
            if not text:
                continue
            votes: dict[tuple, int] = {}
            for ch in run:
                if ch.get("colour") is not None and not ch["text"].isspace():
                    votes[ch["colour"]] = votes.get(ch["colour"], 0) + 1
            out.append({"text": text, "x0": min(ch["x0"] for ch in run), "x1": max(ch["x1"] for ch in run),
                        "top": min(ch["top"] for ch in run), "bottom": max(ch["bottom"] for ch in run),
                        "size": max(ch["size"] for ch in run),
                        "colour": max(votes, key=votes.get) if votes else None})
    out.sort(key=lambda l: (l["top"], l["x0"]))
    return _fold_raised_twos(out)


def _fold_raised_twos(lines: list[dict]) -> list[dict]:
    """„3.95 m" with a small raised „2" after it is „3.95 m²". CAD writes the
    two as separate text runs on different baselines, so line by line the „2"
    arrives as a line of its own ABOVE the number."""
    twos = [l for l in lines if l["text"] in ("2", "²")]
    if not twos:
        return lines
    gone: set[int] = set()
    for two in twos:
        for base in lines:
            if base is two or not re.search(r"m$", base["text"]) or two["size"] >= 0.9 * base["size"]:
                continue
            beside = -0.3 * base["size"] <= two["x0"] - base["x1"] <= 0.8 * base["size"]
            raised = base["top"] - 0.6 * base["size"] <= two["top"] <= base["top"] + 0.5 * base["size"]
            if beside and raised:
                base["text"] += "²"
                base["x1"] = max(base["x1"], two["x1"])
                gone.add(id(two))
                break
    return [l for l in lines if id(l) not in gone]


def find_floor_sheets(pdf_bytes: bytes, pages: Iterable[int] | None) -> list[int]:
    """The 1-based pages whose own text calls them a floor(-covering) plan —
    „GRINDŲ DANGŲ PLANAS", „GRINDŲ PLANAS" — and not the heating plan."""
    out: list[int] = []
    for pn in sorted({int(p) for p in (pages or [])}):
        _, _, plain, _ = _page_text(pdf_bytes, pn)
        for line in plain.splitlines():
            if len(line.strip()) <= TITLE_MAX_CHARS and FLOOR_TITLE_RE.search(line) \
                    and not re.search(r"šild|sild", line, re.I):
                out.append(pn)
                break
    return out


# ── evidence ─────────────────────────────────────────────────────────────────

def _chroma(colour) -> float:
    return (max(colour) - min(colour)) if colour else 0.0


def _same_colour(a, b) -> bool:
    return a is not None and b is not None and all(abs(x - y) <= COLOUR_TOL for x, y in zip(a, b))


def _label_blocks(lines: Sequence[dict]) -> list[dict]:
    """A covering line with the lines written directly under it (size, count,
    area) — one label as the drawing writes it."""
    blocks = []
    used: set[int] = set()
    for i, ln in enumerate(lines):
        klase = classify_line(ln["text"])
        if klase is None or i in used:
            continue
        block = [ln]
        used.add(i)
        last = ln
        for j in range(i + 1, len(lines)):
            nxt = lines[j]
            if j in used or len(block) >= LABEL_LINES:
                continue
            if BARE_NUMBER_RE.match(nxt["text"]):
                continue                               # a dimension string that happens to sit among the label's lines
            if nxt["top"] - last["bottom"] > 0.9 * last["size"] or nxt["top"] < last["top"]:
                continue
            overlap = min(nxt["x1"], ln["x1"]) - max(nxt["x0"], ln["x0"])
            if overlap < -2.0 * ln["size"]:
                continue
            other = classify_line(nxt["text"])
            if other is not None and (other != klase or not _same_colour(nxt["colour"], ln["colour"])):
                break                                  # the next covering's own line (a legend lists them one under another)
            block.append(nxt)
            used.add(j)
            last = nxt
        text = " ".join(b["text"] for b in block)
        area = AREA_RE.search(text)
        blocks.append({
            "klase": klase, "tekstas": text,
            "plotas_m2": float(area.group(1).replace(",", ".")) if area else None,
            "centre": ((ln["x0"] + ln["x1"]) / 2, (ln["top"] + ln["bottom"]) / 2),
            "bbox": (min(b["x0"] for b in block), min(b["top"] for b in block),
                     max(b["x1"] for b in block), max(b["bottom"] for b in block)),
            "colour": ln["colour"],
        })
    return blocks


def _room_shapes(rooms: Sequence[dict], m_per_pt: float | None, W: float) -> dict[str, dict]:
    r_pt = (POINT_R_M / m_per_pt) if m_per_pt else CLOSE_PAGE_SHARE * W * 1.2
    shapes: dict[str, dict] = {}
    for room in rooms or []:
        nr = str(room.get("nr") or "").strip()
        if not nr:
            continue
        poly = room.get("polygon")
        shape = None
        if isinstance(poly, (list, tuple)) and len(poly) >= 3:
            try:
                shape = Polygon([(float(x), float(y)) for x, y in poly])
                if not shape.is_valid:
                    shape = shape.buffer(0)
                if shape.is_empty or shape.area <= 0:
                    shape = None
            except Exception:  # noqa: BLE001
                shape = None
        point = room.get("point")
        if shape is not None:
            shapes[nr] = {"shape": shape, "own": True}
        elif isinstance(point, (list, tuple)) and len(point) == 2:
            shapes[nr] = {"shape": Point(float(point[0]), float(point[1])).buffer(r_pt), "own": False,
                          "point": (float(point[0]), float(point[1]))}
    return shapes


def _sample_points(paths: Sequence[Sequence[tuple[float, float]]], step: float):
    """Points every `step` along the strokes — an (n, 2) array."""
    import numpy as np
    chunks = []
    for pts in paths:
        a = np.asarray(pts, dtype=float)
        if a.ndim != 2 or len(a) < 2:
            continue
        for p0, p1 in zip(a[:-1], a[1:]):
            n = max(1, int(np.hypot(*(p1 - p0)) / step))
            t = np.linspace(0.0, 1.0, n + 1)[:, None]
            chunks.append(p0 + (p1 - p0) * t)
    return np.vstack(chunks) if chunks else np.zeros((0, 2))


def _hatch_share(region, core, points, close_pt: float) -> float:
    """How much of the room's CORE a hatch covers.

    The hatch's stroke points that lie INSIDE the room are put on a coarse grid
    and closed over gaps up to 2 × `close_pt` (a 120 × 120 cm tile grid); the
    answer is the closed area's share of the core.

    The core is the room less a band along its walls. A tile grid is drawn from
    a laying-start point and its last line is the wall itself — never in the
    hatch's colour — so the band beside a wall is closed from one side only and
    must not be asked for (a fully tiled 2,0 × 2,4 m bathroom measured 30 % of
    the ROOM, 100 % of its core).

    A raster, not shapely buffers: 2 280 herringbone strokes on a real sheet
    took 6 s to buffer and union per sheet; this takes milliseconds. Only
    points inside the room are used, so a neighbour's hatch never closes
    across the wall."""
    import cv2
    import numpy as np
    from shapely import contains_xy

    if len(points) < MIN_SEGMENTS or core.area <= 0:
        return 0.0
    x0, y0, x1, y1 = region.bounds
    near = points[(points[:, 0] >= x0) & (points[:, 0] <= x1) & (points[:, 1] >= y0) & (points[:, 1] <= y1)]
    if len(near) < MIN_SEGMENTS:
        return 0.0
    inside = near[contains_xy(region, near[:, 0], near[:, 1])]
    if len(inside) < MIN_SEGMENTS:
        return 0.0
    cell = max(close_pt / 4.0, 0.75)
    r = int(round(close_pt / cell))
    pad = 2 * r + 1
    cols = int((x1 - x0) / cell) + 1 + 2 * pad
    rows = int((y1 - y0) / cell) + 1 + 2 * pad

    def to_cells(xy):
        return np.column_stack((((xy[:, 0] - x0) / cell).astype(int) + pad, ((xy[:, 1] - y0) / cell).astype(int) + pad))

    ink = np.zeros((rows, cols), dtype=np.uint8)
    c = to_cells(inside)
    ink[c[:, 1], c[:, 0]] = 1
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))
    closed = cv2.erode(cv2.dilate(ink, kernel), kernel, borderType=cv2.BORDER_CONSTANT, borderValue=0)

    mask = np.zeros((rows, cols), dtype=np.uint8)
    for poly in (core.geoms if hasattr(core, "geoms") else [core]):
        ring = np.asarray(poly.exterior.coords, dtype=float)
        cv2.fillPoly(mask, [to_cells(ring).astype(np.int32)], 1)
    total = int(mask.sum())
    if total <= 0:
        return 0.0
    return float((closed & mask).sum() / total)


def _points_inside(region, points) -> int:
    from shapely import contains_xy
    if len(points) == 0:
        return 0
    return int(contains_xy(region, points[:, 0], points[:, 1]).sum())


def _pct(bbox, W: float, H: float, pad: float = 0.0) -> list[float]:
    x0, y0, x1, y1 = bbox
    return [round(max(0.0, x0 / W - pad), 4), round(max(0.0, y0 / H - pad), 4),
            round(min(1.0, x1 / W + pad), 4), round(min(1.0, y1 / H + pad), 4)]


def read_floor_coverings(pdf_bytes: bytes, page: int, rooms: Sequence[dict],
                         m_per_pt: float | None = None) -> dict:
    """What the floor sheet `page` draws in each of `rooms`
    ([{nr, polygon: [[x, y] …] | None, point: (x, y) | None}] in that page's
    display points). Returns {"rooms": {nr: {danga, irodymas, tekstas,
    plotas_m2, rect_pct, page}}, "legenda": [{tekstas, klase, spalva, page, rect_pct}],
    "dvi_dangos": {nr: [tekstas, …]}, "page"}. A room that is not in "rooms"
    was not read — it is never guessed here; "dvi_dangos" names the rooms where
    the sheet WRITES two kinds of covering, with what it writes."""
    out = {"rooms": {}, "legenda": [], "dvi_dangos": {}, "page": int(page)}
    W, H, _, chars = _page_text(pdf_bytes, page)
    if W <= 0 or H <= 0 or not rooms:
        return out
    shapes = _room_shapes(rooms, m_per_pt, W)
    if not shapes:
        return out
    own = {nr: s["shape"].buffer(2.0) for nr, s in shapes.items() if s["own"]}
    blocks = _label_blocks(_lines(chars))

    # 1. what is WRITTEN in the room
    label_r = (LABEL_R_M / m_per_pt) if m_per_pt else CLOSE_PAGE_SHARE * W * 3
    written: dict[str, list[dict]] = {}
    legend: list[dict] = []
    for blk in blocks:
        c = Point(*blk["centre"])
        home = next((nr for nr, shape in own.items() if shape.contains(c)), None)
        if home is None:
            near = [(Point(*s["point"]).distance(c), nr) for nr, s in shapes.items() if not s["own"]]
            near = [(d, nr) for d, nr in near if d <= label_r]
            if near:
                home = min(near)[1]
        if home is not None:
            written.setdefault(home, []).append(blk)
        elif _chroma(blk["colour"]) >= MIN_CHROMA:
            legend.append(blk)                       # outside every room and coloured: a key
    # …unless it is the colour the sheet writes its labels in: a label outside
    # every room (a terrace, a room we have no place for) is then an annotation
    # like the ones inside, and that colour's lines are dimension lines.
    annotation = [b["colour"] for blks in written.values() for b in blks if b["colour"] is not None]
    legend = [blk for blk in legend if not any(_same_colour(blk["colour"], c) for c in annotation)]

    # 2. what is HATCHED in the room, in a legend line's colour
    hatched: dict[str, dict[str, tuple[float, dict]]] = {}      # nr → kind → (share of the core, its legend line)
    if legend:
        import numpy as np
        close_pt = (CLOSE_M / m_per_pt) if m_per_pt else CLOSE_PAGE_SHARE * W
        strokes: dict[tuple, list] = {}
        for path in pdf_vectors.page_paths(pdf_bytes, page, strokes=True):
            if path.get("fill") is not None or path.get("stroke") is None:
                continue
            key = next((blk["colour"] for blk in legend if _same_colour(blk["colour"], path["stroke"])), None)
            if key is not None:
                strokes.setdefault(key, []).extend(sub for sub in path["subpaths"] if len(sub) >= 2)
        by_colour = {key: _sample_points(subs, max(close_pt / 8.0, 0.4)) for key, subs in strokes.items()}
        for nr, s in shapes.items():
            region = s["shape"].buffer(-WALL_INSET_PT) if s["own"] else s["shape"]
            if region.is_empty or region.area <= 0:
                continue
            # the band along the walls that is not asked for: up to `close_pt`,
            # less in a small room (a 0,9 m wide WC still has a core)
            if s["own"]:
                band = min(close_pt, CORE_BAND_SHARE * region.area ** 0.5)
                core = region.buffer(-band)
                if core.is_empty or core.area < MIN_CORE_SHARE * region.area:
                    core = region             # a sliver of a room: judged whole
            else:
                # no walls here — the disc's edge is ours, so the strokes just
                # outside it close the hatch and the disc itself is what is judged
                core, region = region, region.buffer(close_pt)
            # one KIND of covering at a time: two tile formats in one bathroom
            # (two colours) are one tiled floor, and their strokes close together
            for klase in {blk["klase"] for blk in legend}:
                keys = [blk for blk in legend if blk["klase"] == klase and len(by_colour.get(blk["colour"], ())) > 0]
                if not keys:
                    continue
                points = np.vstack([by_colour[blk["colour"]] for blk in keys])
                share = _hatch_share(region, core, points, close_pt)
                if share <= 0:
                    continue
                # the legend line most of this room's hatch is drawn in
                lead = max(keys, key=lambda blk: _points_inside(region, by_colour[blk["colour"]]))
                hatched.setdefault(nr, {})[klase] = (share, lead)

    # 3. one kind of covering, from evidence that agrees
    for nr, s in shapes.items():
        labels = written.get(nr) or []
        label_kinds = {b["klase"] for b in labels}
        shares = {k: v[0] for k, v in (hatched.get(nr) or {}).items()}
        big = {k for k, v in shares.items() if v >= MIXED_SHARE}
        hatch_kind = None
        if len(big) == 1 and shares[next(iter(big))] >= MIN_SHARE:
            hatch_kind = next(iter(big))
        if len(label_kinds) > 1:
            # two coverings WRITTEN in one room: not ours to choose — say both
            out["dvi_dangos"][nr] = [b["tekstas"] for b in labels]
            continue
        if len(big) > 1:
            continue
        if label_kinds and hatch_kind and hatch_kind not in label_kinds:
            continue
        if label_kinds:
            blk = labels[0]
            out["rooms"][nr] = {"danga": blk["klase"], "irodymas": "uzrasas", "tekstas": blk["tekstas"],
                                "plotas_m2": blk["plotas_m2"], "rect_pct": _pct(blk["bbox"], W, H, 0.01),
                                "page": int(page)}
        elif hatch_kind:
            blk = hatched[nr][hatch_kind][1]
            out["rooms"][nr] = {"danga": hatch_kind, "irodymas": "rastas", "tekstas": blk["tekstas"],
                                "plotas_m2": None, "rect_pct": _pct(s["shape"].bounds, W, H, 0.01),
                                "page": int(page)}
    out["legenda"] = [{"tekstas": b["tekstas"], "klase": b["klase"], "spalva": list(b["colour"]),
                       "page": int(page), "rect_pct": _legend_rect_pct(b["bbox"], W, H)} for b in legend]
    return out


def _legend_rect_pct(bbox, W: float, H: float) -> list[float]:
    """A legend line's box widened to the LEFT by a few text heights, where a key draws its colour swatch —
    the crop beside the floor fact shows the swatch and the words together (Pathon v3 W5-D, D1)."""
    x0, top, x1, bottom = bbox
    h = max(bottom - top, 1.0)
    return _pct((max(0.0, x0 - 6.0 * h), top - 0.6 * h, x1 + 0.6 * h, bottom + 0.6 * h), W, H, 0.0)
