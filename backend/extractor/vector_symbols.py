"""Deterministic SYMBOL counter for vector drawings ($0, no Vision call): a legend row's glyph is a
template, its instances on the plan are counted from the PDF's own paths.

WHY (2026-09-24, the founder's „100 %" question). On objektas_h Vision counted 10 diffusers; the drawing's
legend has three rows — „Ištraukimo difuzorius" (blue filled circle), „Padavimo difuzorius" (red) and „Plyšinis
difuzorius" (a blue bar) — and the plan carries 3 + 4 + 2 of them: 9, his row to the piece. On objektas_d the
row „Priglaistomi apvalūs difuzoriai" shows TWO symbols side by side (a blue and a red ring with four petals);
the plan carries 3 + 3, Vision said 4, he billed 6. On objektas_b the same plan is printed on two sheets
(ceiling + lighting) with the same legend — 18 round diffusers and 2 double-line slot diffusers, once. On
objektas_g the symbol is a composite (a pale box with four arrows) — 4 supply + 4 extract. The paths are all
there, so the count needs no model.

HOW. Coloured path objects (curves / lines / rects; black and grey are the walls and dimensions, never a
symbol here) are clustered with neighbours of the same colour and fill (gap 0,8 pt) into GLYPHS: a compact
glyph is ≤ 16 pt across, an elongated one (a slot, a double line) is ≤ 4 pt thin and ≤ 120 pt long; a cluster
too big to be one symbol (a ring whose petals touch it, a hatch) is split back into its own primitives. A
filled shape drawn again as an outline on top of itself is ONE glyph. For each legend label the caller asks
about (a regex over the page text) the coloured glyphs just left of the label's row are grouped into
SYMBOLS: the largest glyph is the anchor, everything within 2 × its size is its parts — a second symbol on the
same row (objektas_d) becomes a second anchor. An INSTANCE on the page is a glyph of the anchor's class
(colour, fill, size ±35 %; an elongated anchor: same thickness, at least 60 % of its length, drawn to length)
with at least 60 % of the template's parts around it, outside the legend area; the candidate with the most
parts wins its neighbourhood (a petal never counts beside its ring). A later sheet whose instances stand at
the same positions repeats the plan and is not summed.

LIMITS, measured on the corpus: works where the symbol is a coloured, distinct class (H, D, B, G diffusers);
a black-only symbol is not counted (the black paths are also the walls); light fixtures on H share colour and
size across kinds and differ only in strokes that fragment inconsistently — NOT counted here (the plan's ~33
light symbols against his 20 „priglaistomi" are also a scope choice, not a count). Never raises; a page
without the label returns `defined=False`.
"""
from __future__ import annotations

import collections
import hashlib
import io
import math
import re
import threading
import time

# a legend LABEL in the nominative — the same rule symbol_legend.py uses to tell a legend row from prose
DIFFUSER_LABEL_RE = re.compile(r"(?<!\w)dif[uū]zori(?:us|ai)(?!\w)", re.IGNORECASE)
_GAP_PT = 0.8
_COMPACT_MAX_PT = 16.0        # a compact symbol's largest side
_THIN_SHORT_MAX_PT = 4.0      # an elongated symbol (slot, double line): its short side …
_THIN_LONG_MAX_PT = 120.0     # … and its long side
_MIN_GLYPH_PT = 1.5
_SIZE_TOL = 0.35
_LONG_MIN_SHARE = 0.6         # a slot drawn to length is at least this share of the legend's bar …
_LONG_MAX_RATIO = 5.0         # … and at most this many times it (a wall line of the same colour is not one)
_PARTS_MIN_SHARE = 0.6
_LEGEND_WINDOW_PT = 90.0      # the symbols of a row stand this close left of its first word
_ROW_TOL_PT = 8.0
_SAME_SPOT_PCT = 0.003        # two sheets' instances at the same page fraction = the same plan printed twice
_REPEAT_SHARE = 0.8


def _colour(o: dict) -> tuple:
    c = o.get("non_stroking_color") if o.get("fill") else o.get("stroking_color")
    if isinstance(c, (list, tuple)):
        return tuple(round(float(x), 2) for x in c)
    if isinstance(c, (int, float)):
        return (round(float(c), 2),)
    return ("?",)


def _is_greyish(col: tuple) -> bool:
    if len(col) < 3 or not all(isinstance(x, (int, float)) for x in col[:3]):
        return True
    r, g, b = col[0], col[1], col[2]
    return max(r, g, b) - min(r, g, b) < 0.12


def _fits(w: float, h: float) -> bool:
    long, short = max(w, h), min(w, h)
    if long < _MIN_GLYPH_PT:
        return False
    if long <= _COMPACT_MAX_PT:
        return True
    return short <= _THIN_SHORT_MAX_PT and long <= _THIN_LONG_MAX_PT


def _make_glyph(col: tuple, fill: bool, x0: float, x1: float, y0: float, y1: float, n: int) -> dict:
    w, h = x1 - x0, y1 - y0
    long, short = max(w, h), min(w, h)
    return {"col": col, "fill": fill, "cx": (x0 + x1) / 2, "cy": (y0 + y1) / 2, "w": w, "h": h, "n": n,
            "long": long, "short": short, "thin": short <= _THIN_SHORT_MAX_PT and long >= max(6.0, 3 * short)}


def _glyphs(page) -> list[dict]:
    prims = []
    for kind, objs in (("c", page.curves), ("l", page.lines), ("r", page.rects)):
        for o in objs:
            col = _colour(o)
            if _is_greyish(col):
                continue
            w = o["x1"] - o["x0"]
            h = o["bottom"] - o["top"]
            if not _fits(w, h):
                continue
            prims.append({"k": kind, "x0": o["x0"], "x1": o["x1"], "top": o["top"], "bottom": o["bottom"],
                          "col": col, "fill": bool(o.get("fill"))})
    by_key: dict = collections.defaultdict(list)
    for p in prims:
        by_key[(p["col"], p["fill"])].append(p)
    out: list[dict] = []
    for key, ps in by_key.items():
        for g in _clusters(ps):
            x0 = min(p["x0"] for p in g)
            x1 = max(p["x1"] for p in g)
            y0 = min(p["top"] for p in g)
            y1 = max(p["bottom"] for p in g)
            if _fits(x1 - x0, y1 - y0):
                out.append(_make_glyph(key[0], key[1], x0, x1, y0, y1, len(g)))
                continue
            # too big to be one symbol (a ring whose petals touch it, a hatch): each primitive on its own
            for p in g:
                if _fits(p["x1"] - p["x0"], p["bottom"] - p["top"]):
                    out.append(_make_glyph(key[0], key[1], p["x0"], p["x1"], p["top"], p["bottom"], 1))
    return _merge_coincident(out)


def _clusters(ps: list[dict]) -> list[list[dict]]:
    """Primitives of one colour+fill class grouped by touching bboxes (gap ≤ 0,8 pt). A cell grid keeps it
    near-linear — a sheet of thousands of dimension lines in one colour (objektas_g) is the normal case."""
    n = len(ps)
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    cell = 16.0
    grid: dict = collections.defaultdict(list)
    for i, p in enumerate(ps):
        for cx in range(int((p["x0"] - _GAP_PT) // cell), int((p["x1"] + _GAP_PT) // cell) + 1):
            for cy in range(int((p["top"] - _GAP_PT) // cell), int((p["bottom"] + _GAP_PT) // cell) + 1):
                grid[(cx, cy)].append(i)
    for members in grid.values():
        if len(members) < 2:
            continue
        for a_i in range(len(members)):
            i = members[a_i]
            a = ps[i]
            for b_i in range(a_i + 1, len(members)):
                j = members[b_i]
                if find(i) == find(j):
                    continue
                b = ps[j]
                if (b["x0"] - a["x1"] > _GAP_PT or a["x0"] - b["x1"] > _GAP_PT
                        or b["top"] - a["bottom"] > _GAP_PT or a["top"] - b["bottom"] > _GAP_PT):
                    continue
                parent[find(i)] = find(j)
    groups: dict = collections.defaultdict(list)
    for i in range(n):
        groups[find(i)].append(ps[i])
    return list(groups.values())


def _merge_coincident(glyphs: list[dict]) -> list[dict]:
    """A filled circle drawn again as an outline on top of itself (objektas_b, _h), or the same path twice,
    is ONE glyph — the filled / busier one carries the class."""
    glyphs.sort(key=lambda g: g["cx"])
    keep: list[dict] = []
    dead: set[int] = set()
    for i, a in enumerate(glyphs):
        if i in dead:
            continue
        best = a
        for j in range(i + 1, len(glyphs)):
            b = glyphs[j]
            if b["cx"] - a["cx"] > 1.0:
                break
            if j in dead or abs(b["cy"] - a["cy"]) > 1.0 or abs(b["w"] - a["w"]) > 1.5 or abs(b["h"] - a["h"]) > 1.5:
                continue
            dead.add(j)
            if (b["fill"], b["n"]) > (best["fill"], best["n"]):
                best = b
        keep.append(best)
    return keep


def _same_class(a: dict, b: dict) -> bool:
    if a["col"] != b["col"] or a["fill"] != b["fill"]:
        return False
    if a["thin"]:
        return (b["thin"] and abs(b["short"] - a["short"]) <= max(_SIZE_TOL * a["short"], 0.6)
                and _LONG_MIN_SHARE * a["long"] <= b["long"] <= _LONG_MAX_RATIO * a["long"])
    return (not b["thin"] and abs(a["w"] - b["w"]) <= _SIZE_TOL * max(a["w"], 0.5)
            and abs(a["h"] - b["h"]) <= _SIZE_TOL * max(a["h"], 0.5))


def _dist(a: dict, b: dict) -> float:
    return math.hypot(a["cx"] - b["cx"], a["cy"] - b["cy"])


def _radius(anchor: dict) -> float:
    return 2.0 * anchor["long"]


def _is_part(anchor: dict, g: dict) -> bool:
    if g is anchor or g["long"] > 1.5 * anchor["long"]:
        return False
    if anchor["thin"]:
        # a double line's parts are its parallel twins (objektas_b's slot diffuser), nothing else
        return (g["thin"] and g["col"] == anchor["col"] and abs(g["long"] - anchor["long"]) <= 0.35 * anchor["long"]
                and _dist(g, anchor) <= 6.0)
    # a part stands beside or diagonally around its anchor (objektas_d's petals at 1,25 × size), never a full
    # legend row below or above it
    return (_dist(g, anchor) <= _radius(anchor)
            and abs(g["cy"] - anchor["cy"]) <= 1.4 * max(anchor["long"], 4.0))


def _template(anchor: dict, glyphs: list[dict], other_rows_cy: list[float] = ()) -> dict:
    def other_row(g: dict) -> bool:
        return any(abs(g["cy"] - cy) <= 5 and abs(g["cy"] - anchor["cy"]) > 5 for cy in other_rows_cy)
    parts = [g for g in glyphs if _is_part(anchor, g) and not other_row(g)]
    return {"anchor": anchor, "radius": _radius(anchor), "parts": parts}


def _parts_present(cand: dict, template: dict, near: list[dict]) -> float:
    parts = template["parts"]
    if not parts:
        return 1.0
    hit = 0
    used: set[int] = set()
    for p in parts:
        for k, g in enumerate(near):
            if k in used:
                continue
            if _same_class(p, g):
                used.add(k)
                hit += 1
                break
    return hit / len(parts)


def _count_instances(template: dict, glyphs: list[dict], legend_box: tuple) -> list[dict]:
    anchor = template["anchor"]
    lx0, ly0, lx1, ly1 = legend_box
    radius = template["radius"]
    scored: list[tuple] = []
    for g in glyphs:
        if g is anchor or not _same_class(anchor, g):
            continue
        if lx0 <= g["cx"] <= lx1 and ly0 <= g["cy"] <= ly1:
            continue
        near = [o for o in glyphs if o is not g and _is_part(g, o)]
        share = _parts_present(g, template, near)
        if share < _PARTS_MIN_SHARE:
            continue
        scored.append((-share, -len(near), g["cy"], g["cx"], g))
    scored.sort(key=lambda t: t[:4])
    dedupe = radius if not anchor["thin"] else 6.0
    found: list[dict] = []
    for _, _, _, _, g in scored:
        if any(_dist(g, f) <= dedupe for f in found):
            continue                                           # the same symbol's other part (a ring's petal, a twin line)
        found.append(g)
    return found


def _has_twin(g: dict, pool: list[dict]) -> bool:
    return any(o is not g and o["col"] == g["col"] and abs(o["long"] - g["long"]) <= 0.35 * g["long"]
               and _dist(o, g) <= 6.0 for o in pool)


def _row_anchors(pool: list[dict]) -> list[dict]:
    """The symbols of one legend row: the largest glyph is an anchor, everything within its radius is its
    parts, what is left starts the next symbol (objektas_d: two rings with petals side by side)."""
    # a lone hairline (a table border beside the label, a dimension line round a material sample) is never a
    # symbol: as an anchor it has no parts and every line of its colour on the sheet is an „instance" (B2-A:
    # objektas_e p11, a box over the material column took the sample's red dimension lines → 124 on one sheet).
    # A slot diffuser's double line has its twin and stays (objektas_b).
    pool = [g for g in pool if not (g["short"] < 0.3 and g["thin"] and not _has_twin(g, pool))]
    pool.sort(key=lambda g: (-g["long"], -g["fill"]))
    anchors: list[dict] = []
    while pool:
        a = pool.pop(0)
        anchors.append(a)
        pool = [g for g in pool if not _is_part(a, g)]
    return anchors


def _repeats_earlier(instances: list[dict], earlier: list[dict]) -> bool:
    if not instances or not earlier:
        return False
    same = sum(1 for i in instances
               if any(abs(i["x_pct"] - e["x_pct"]) <= _SAME_SPOT_PCT and abs(i["y_pct"] - e["y_pct"]) <= _SAME_SPOT_PCT
                      for e in earlier))
    return same / len(instances) >= _REPEAT_SHARE


def count_legend_symbols(pdf_bytes: bytes, label_re: re.Pattern = DIFFUSER_LABEL_RE, pages: list[int] | None = None) -> dict:
    """{defined, count, pages, rows: [{page, label, colour, size_pt, parts, count, kartojasi}],
    per_label: {label: count}, instances: [{page, x_pct, y_pct, label}]} for the symbols whose legend label
    matches `label_re`. `defined` is False when no page carries such a label beside a glyph. A sheet that
    repeats an earlier sheet's plan keeps its rows (`kartojasi`) but adds nothing to `count`."""
    out: dict = {"defined": False, "count": 0, "pages": [], "rows": [], "per_label": {}, "instances": []}
    try:
        from .pdf_page_cache import page_texts
        texts = [t or "" for t in page_texts(pdf_bytes)]
    except Exception:  # noqa: BLE001
        return out
    candidates = [i + 1 for i, t in enumerate(texts) if label_re.search(t)]
    if pages:
        candidates = [p for p in candidates if p in set(pages)]
    if not candidates:
        return out
    counted: dict = collections.defaultdict(list)                # label → instances of the sheets already counted
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for pg in candidates[:4]:
                page = pdf.pages[pg - 1]
                W, H = float(page.width), float(page.height)
                words = page.extract_words()
                labels = [w for w in words if label_re.search(w["text"])]
                if not labels:
                    continue
                glyphs = _glyphs(page)
                rows_cy = [(w["top"] + w["bottom"]) / 2 for w in labels]
                seen_rows: set[tuple] = set()
                page_rows: list[dict] = []
                page_instances: list[dict] = []
                for lw in labels:
                    cy = (lw["top"] + lw["bottom"]) / 2
                    # the label's row: the CONTIGUOUS words left of the label word on its line („Priglaistomas
                    # padavimo difuzorius") — a dimension figure standing farther left on the same line is not
                    same_line = sorted((w for w in words if abs(w["top"] - lw["top"]) < 4 and w["x0"] <= lw["x0"]),
                                       key=lambda w: -w["x0"])
                    row = [lw]
                    for w in same_line:
                        if w is lw or w["x0"] >= lw["x0"]:
                            continue
                        if row[-1]["x0"] - w["x1"] > 12:
                            break
                        row.append(w)
                    lx = min(w["x0"] for w in row)
                    row_key = (round(lx), round(cy))
                    if row_key in seen_rows:                     # „Plyšinis difuzorius": two words match one row
                        continue
                    seen_rows.add(row_key)
                    label = " ".join(w["text"] for w in sorted(row, key=lambda w: w["x0"]))
                    pool = [g for g in glyphs if lx - _LEGEND_WINDOW_PT <= g["cx"] <= lx - 1 and abs(g["cy"] - cy) <= _ROW_TOL_PT]
                    for anchor in _row_anchors(pool):
                        template = _template(anchor, glyphs, [c for c in rows_cy if abs(c - cy) > 5])
                        legend_box = (lx - 50, cy - 80, lx + 300, cy + 80)
                        inst = _count_instances(template, glyphs, legend_box)
                        instances = [{"page": pg, "x_pct": round(g["cx"] / W, 4), "y_pct": round(g["cy"] / H, 4),
                                      "label": label[:40]} for g in inst]
                        page_rows.append({"page": pg, "label": label[:60], "colour": list(anchor["col"]),
                                          "size_pt": round(anchor["long"], 1), "parts": len(template["parts"]),
                                          "count": len(inst), "kartojasi": False, "_inst": instances})
                        page_instances.extend(instances)
                        out["defined"] = True
                if not page_rows:
                    continue
                if pg not in out["pages"]:
                    out["pages"].append(pg)
                # the same plan printed on another sheet (objektas_b: the ceiling and the lighting plan both
                # carry the diffusers) — the instances stand at the same page fractions; counted once
                repeats = bool(counted) and _repeats_earlier(page_instances, [i for v in counted.values() for i in v])
                for r in page_rows:
                    inst = r.pop("_inst")
                    r["kartojasi"] = repeats
                    if not repeats:
                        counted[r["label"]].extend(inst)
                        out["instances"].extend(inst)
                        out["per_label"][r["label"]] = out["per_label"].get(r["label"], 0) + r["count"]
                    out["rows"].append(r)
    except Exception:  # noqa: BLE001 — a page we cannot read counts nothing
        return out
    out["count"] = sum(out["per_label"].values())
    return out


def scan_vector_symbols(pdf_bytes: bytes) -> dict:
    """The families counted from the drawing's own paths — today the diffusers; LT sentence for the person."""
    dif = count_legend_symbols(pdf_bytes, DIFFUSER_LABEL_RE)
    if dif["defined"]:
        parts = []
        for label, n in dif["per_label"].items():
            anchors = sum(1 for r in dif["rows"] if r["label"] == label and not r["kartojasi"])
            parts.append(f"„{label}“ × {n}" + (f" ({anchors} ženklai)" if anchors > 1 else ""))
        repeated = sorted({r["page"] for r in dif["rows"] if r["kartojasi"]})
        tail = (f"; {'lapas' if len(repeated) == 1 else 'lapai'} {', '.join(str(p) for p in repeated)} kartoja tą patį planą — "
                f"antrą kartą neskaičiuota" if repeated else "")
        dif["sakinys"] = (f"Difuzoriai suskaičiuoti iš brėžinio ženklų pagal legendą (lapas "
                          f"{', '.join(str(p) for p in dif['pages'] if p not in repeated)}): {'; '.join(parts)}"
                          f" — iš viso {dif['count']}{tail}.")
    else:
        dif["sakinys"] = "Difuzorių ženklo legendoje neradau — iš brėžinio kelių nesuskaičiuota."
    return {"difuzoriai": dif}


# ── generalised: any coloured legend glyph, every sheet, instances with boxes (Pathon v3, W2-A A2) ──────────
#
# `count_legend_symbols` above stays the diffusers' entry (a label regex, the first 4 sheets that carry the
# label, point instances) — the free re-read and the paid pass read it, its numbers do not move. The entry
# below takes the TEMPLATE from a legend row instead (extractor/legend_rows.py: a glyph box on a sheet), so any
# coloured symbol a legend explains can be counted, on every sheet, with each instance's box:
#   * the glyphs inside the row's glyph box are the template — the largest is the anchor, the rest its parts,
#     a second symbol on the row a second anchor (objektas_d), exactly the rules above;
#   * a sheet is read only when PDFium sees a path painted in one of the template's colours on it (a cheap
#     pass — pdfplumber's full read of a heavy sheet costs seconds, PDFium's look at its paths a tenth of one);
#   * a sheet whose reader frame disagrees with the page as displayed (sheet_zones.display_frame) is not used
#     and said so — the counter never places a mark where nothing is;
#   * no instance inside a legend, a table or the title block (sheet_zones zones, `zone_at`), inside the
#     template's own glyph or legend box, or with the row's first word right beside it (the same legend
#     printed on another sheet);
#   * a sheet whose instances stand where an earlier sheet's do repeats that plan (`kartojasi`) and adds
#     nothing — the rule above;
#   * a time budget: what is not read in time is listed, and the answer says it is partial.

GLYPH_CACHE_MAX = 48
TIME_BUDGET_S = 40.0
_COLOUR_TOL = 4                 # 0–255 — pdfplumber rounds colours to two decimals
_BOX_PAD_PT = 1.5
ZONE_KINDS_WITHOUT_MARKS = ("legenda", "lentele", "antspaudas")
_COPY_GAP_PT = 30.0             # a legend copy's first word starts this close right of its glyph
_glyph_cache: "collections.OrderedDict[tuple, dict]" = collections.OrderedDict()
_glyph_lock = threading.Lock()


def clear_glyph_cache() -> None:
    """Drop the per-sheet glyph cache (tests)."""
    with _glyph_lock:
        _glyph_cache.clear()


def _page_glyphs(pdf, digest: bytes, pg: int) -> dict:
    """{W, H, ox, oy, glyphs} of a 1-based page through pdfplumber — cached per PDF digest and page."""
    key = (digest, pg)
    with _glyph_lock:
        hit = _glyph_cache.get(key)
        if hit is not None:
            _glyph_cache.move_to_end(key)
            return hit
    page = pdf.pages[pg - 1]
    x0, top, _x1, _bottom = (float(v) for v in page.bbox)
    res = {"W": float(page.width), "H": float(page.height), "ox": x0, "oy": top, "glyphs": _glyphs(page)}
    with _glyph_lock:
        _glyph_cache[key] = res
        _glyph_cache.move_to_end(key)
        while len(_glyph_cache) > GLYPH_CACHE_MAX:
            _glyph_cache.popitem(last=False)
    return res


def _rgb255(col: tuple) -> tuple[int, ...] | None:
    if len(col) != 3 or not all(isinstance(v, (int, float)) for v in col):
        return None
    return tuple(int(round(float(v) * 255)) for v in col)


def _colour_pages(pdf_bytes: bytes, classes: list[tuple[tuple, float]], pages: list[int]) -> list[int] | None:
    """The pages (of `pages`) on which PDFium sees a path painted in one of the template classes' colours and
    of about its size — `classes` = [(pdfplumber colour tuple, the anchor's longest side in pt)]; a wall or a
    dimension line drawn in the same colour does not make a sheet worth reading. None when a colour is not
    plain RGB, or PDFium cannot read the file — then every page is read."""
    want = [(_rgb255(c), float(size)) for c, size in classes]
    if not want or any(w is None for w, _ in want):
        return None
    from .pdfium_guard import PDFIUM_LOCK
    try:
        import ctypes

        import pypdfium2 as pdfium
        import pypdfium2.raw as C
    except ImportError:
        return None

    def near(rgb, long: float) -> bool:
        # a symbol's parts are at most its size (a ring's petal is smaller); a form scaled in its container is
        # rare enough that the size window stays wide
        return any(all(abs(a - b) <= _COLOUR_TOL for a, b in zip(rgb, w)) and 0.15 * size <= long <= 1.6 * size + 1.0
                   for w, size in want)
    out: list[int] = []
    with PDFIUM_LOCK:
        try:
            doc = pdfium.PdfDocument(pdf_bytes)
        except Exception:  # noqa: BLE001
            return None
        try:
            r, g, b, a = (ctypes.c_uint() for _ in range(4))
            fillmode, stroke_on = ctypes.c_int(), ctypes.c_int()
            for pg in pages:
                if not (1 <= pg <= len(doc)):
                    continue
                page = doc[pg - 1]
                try:
                    for obj in page.get_objects(max_depth=4):
                        if obj.type != C.FPDF_PAGEOBJ_PATH:
                            continue
                        h = obj.raw
                        if not C.FPDFPath_GetDrawMode(h, fillmode, stroke_on):
                            continue
                        try:
                            left, bottom, right, top = obj.get_bounds()
                        except Exception:  # noqa: BLE001
                            continue
                        long = max(right - left, top - bottom)
                        if ((fillmode.value and C.FPDFPageObj_GetFillColor(h, r, g, b, a) and near((r.value, g.value, b.value), long))
                                or (stroke_on.value and C.FPDFPageObj_GetStrokeColor(h, r, g, b, a)
                                    and near((r.value, g.value, b.value), long))):
                            out.append(pg)
                            break
                finally:
                    page.close()
        except Exception:  # noqa: BLE001
            return None
        finally:
            doc.close()
    return out


def _templates_in_box(glyphs: list[dict], box: tuple) -> list[dict]:
    """The symbols inside a legend row's glyph box (pdfplumber points): anchors with their parts."""
    x0, y0, x1, y1 = box
    pool = [g for g in glyphs if x0 - _BOX_PAD_PT <= g["cx"] <= x1 + _BOX_PAD_PT and y0 - _BOX_PAD_PT <= g["cy"] <= y1 + _BOX_PAD_PT]
    return [{"anchor": a, "radius": _radius(a), "parts": [g for g in pool if _is_part(a, g)]} for a in _row_anchors(list(pool))]


def _instance_box(g: dict, template: dict, glyphs: list[dict]) -> tuple[float, float, float, float]:
    """An instance's box: its anchor glyph and the parts of the template's classes around it."""
    x0, y0 = g["cx"] - g["w"] / 2, g["cy"] - g["h"] / 2
    x1, y1 = g["cx"] + g["w"] / 2, g["cy"] + g["h"] / 2
    for o in glyphs:
        if o is g or not _is_part(g, o) or not any(_same_class(p, o) for p in template["parts"]):
            continue
        x0, y0 = min(x0, o["cx"] - o["w"] / 2), min(y0, o["cy"] - o["h"] / 2)
        x1, y1 = max(x1, o["cx"] + o["w"] / 2), max(y1, o["cy"] + o["h"] / 2)
    return x0, y0, x1, y1


def _first_word(text: str | None) -> str | None:
    from .sheet_zones import fold
    words = fold(text or "").split()
    return words[0] if words and len(words[0]) >= 3 else None


def _legend_copy(box: tuple, words: list[dict], first: str) -> bool:
    """The same legend row printed on another sheet: the row's first word starts right of the glyph."""
    from .sheet_zones import fold
    cy = (box[1] + box[3]) / 2
    return any(abs((w["top"] + w["bottom"]) / 2 - cy) <= 4.0 and 0 <= w["x0"] - box[2] <= _COPY_GAP_PT
               and fold(w["text"]).startswith(first) for w in words)


def _answer(t: dict) -> dict:
    return {"row_id": t.get("row_id"), "status": "ok", "defined": False, "count": 0, "anchors": 0, "parts": 0,
            "per_page": [], "instances": [], "kiti": [], "fallback": False, "legend_copies": 0, "partial": False,
            "pages_not_read": [],
            "pages_skipped": [], "uz_zonu": [], "detail": None}


def count_glyph_instances_many(pdf_bytes: bytes, templates: list[dict], pages: list[int] | None = None, *,
                               zones: bool = True, exclude: dict | None = None, other_sheets: bool = False,
                               time_budget_s: float | None = None) -> list[dict]:
    """Count several legend rows at once (each sheet read once). `templates`: [{page, glyph_bbox_pct, text?,
    legend_bbox_pct?, row_id?}] — boxes in DISPLAY fractions (legend_rows). `pages`: 1-based sheets to count
    on (default: every sheet). `zones`: drop instances in a legend / table / title-block zone (sheet_zones);
    `exclude`: {page: [bbox_pct, …]} more boxes to drop; `other_sheets`: also read the sheets that do not carry
    the row's legend text (their instances go to `kiti`, not into the count). One answer per template:
    {row_id, status: ok|nera_zenklo|no_page|failed, defined, count, anchors, parts,
     per_page: [{page, count, kartojasi, legenda_lape}], instances: [{page, box_pct, x_pct, y_pct}] (DISPLAY
     fractions; a repeated sheet's are not listed), kiti: [instance] (sheets without the legend, not counted),
     legend_copies, partial, pages_not_read, pages_skipped: [{page, reason}], uz_zonu: [{page, x_pct, y_pct,
     zona}] (matches inside a legend / table / title-block zone — listed, never counted), detail}. `nera_zenklo`: the row's
     glyph is no coloured path — the shape search counts it. Never raises."""
    answers = [_answer(t) for t in templates]
    if not templates:
        return answers
    budget = TIME_BUDGET_S if time_budget_s is None else float(time_budget_s)
    try:
        return _count_many(pdf_bytes, templates, pages, zones, exclude or {}, other_sheets, budget,
                           time.monotonic(), answers)
    except Exception:  # noqa: BLE001 — a count never sinks its caller
        import logging
        logging.getLogger("samatu.vector_symbols").warning("glyph count failed", exc_info=True)
        for a in answers:
            a.update(status="failed", detail="ženklų suskaičiuoti nepavyko", instances=[], count=0)
        return answers


def _count_many(pdf_bytes, templates, pages, zones, exclude, other_sheets, budget, started, answers) -> list[dict]:
    import pdfplumber

    from .sheet_zones import REREAD_TABLE_MAX_OBJECTS, display_frame, read_zones, zone_at
    digest = hashlib.blake2b(pdf_bytes, digest_size=16).digest()
    frames: dict[int, tuple | None] = {}
    zone_cache: dict[int, list] = {}

    def frame_ok(pg: int, info: dict) -> bool:
        if pg not in frames:
            frames[pg] = display_frame(pdf_bytes, pg)
        f = frames[pg]
        return bool(f) and abs(info["W"] - f[0]) <= 1.0 and abs(info["H"] - f[1]) <= 1.0

    def page_zones(pg: int) -> list:
        if pg not in zone_cache:
            zone_cache[pg] = read_zones(pdf_bytes, pg, table_max_objects=REREAD_TABLE_MAX_OBJECTS).get("zones") or []
        return zone_cache[pg]

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        n_pages = len(pdf.pages)                # not pdf_page_cache.page_count: that reads every sheet's text
        wanted = sorted({int(p) for p in (pages or range(1, n_pages + 1)) if 1 <= int(p) <= n_pages})
        # 1. the templates, each from its row's own sheet
        groups: list[list[dict] | None] = []
        for t, ans in zip(templates, answers):
            pg = int(t.get("page") or 0)
            if not 1 <= pg <= n_pages:
                ans.update(status="no_page", detail="tokio lapo brėžinyje nėra")
                groups.append(None)
                continue
            info = _page_glyphs(pdf, digest, pg)
            if not frame_ok(pg, info):
                ans.update(status="nera_zenklo", detail="lapo rėmas nesutampa su lapo pasukimu — ženklas imamas pagal formą")
                groups.append(None)
                continue
            gx0, gy0, gx1, gy1 = (float(v) for v in t["glyph_bbox_pct"])
            box = (info["ox"] + gx0 * info["W"], info["oy"] + gy0 * info["H"],
                   info["ox"] + gx1 * info["W"], info["oy"] + gy1 * info["H"])
            tpls = _templates_in_box(info["glyphs"], box)
            if not tpls:
                ans.update(status="nera_zenklo", detail="legendos ženklas nespalvotas — skaičiuojama pagal jo formą")
                groups.append(None)
                continue
            ans.update(defined=True, anchors=len(tpls), parts=sum(len(x["parts"]) for x in tpls))
            groups.append(tpls)
        live = [i for i, g in enumerate(groups) if g]
        if not live:
            return answers
        # 2. which sheets carry one of the colours at all (cheap), and which of those carry the row's own legend
        # text (PDFium's text, cheap): a legend explains the sheet it stands on. objektas_b p10, a sheet with no
        # ventilation legend, draws red circles of the extract diffuser's size for something else — counted
        # there they would be 3 diffusers too many. Sheets without the legend are read only when asked
        # (`other_sheets`) or when the legend's sheets hold no instance (a legend printed on a sheet of its own).
        classes = sorted({(tp["anchor"]["col"], round(tp["anchor"]["long"], 1)) for i in live for tp in groups[i]}, key=str)
        coloured = _colour_pages(pdf_bytes, classes, wanted)
        own_pages = {int(templates[i]["page"]) for i in live} & set(wanted)
        candidates = wanted if coloured is None else sorted(set(coloured) | own_pages)
        texts = _folded_texts(pdf_bytes, digest, candidates)
        keys = {i: _row_key(templates[i].get("text")) for i in live}

        def legend_sheet(i: int, pg: int) -> bool:
            return keys[i] is None or keys[i] in texts.get(pg, "")
        own = {int(templates[i]["page"]) for i in live}
        first = [p for p in candidates if any(legend_sheet(i, p) for i in live)]
        first = [p for p in first if p in own] + [p for p in first if p not in own]
        rest = [p for p in candidates if p not in first]
        counted: dict[int, list[dict]] = {i: [] for i in live}
        others: dict[int, list[dict]] = {i: [] for i in live}

        def read(seq: list[int]) -> None:
            for k, pg in enumerate(seq):
                if time.monotonic() - started > budget:
                    for i in live:
                        answers[i]["partial"] = True
                        answers[i]["pages_not_read"] = sorted(set(answers[i]["pages_not_read"]) | set(seq[k:]))
                    return
                info = _page_glyphs(pdf, digest, pg)
                if not frame_ok(pg, info):
                    for i in live:
                        answers[i]["pages_skipped"].append({"page": pg, "reason": "lapo rėmas nesutampa su lapo pasukimu — lapas neskaičiuotas"})
                    continue
                words = None
                for i in live:
                    found, copies, words = _instances_on(pdf, pg, info, templates[i], groups[i], exclude, zones,
                                                         page_zones, words, zone_at, answers[i]["uz_zonu"])
                    answers[i]["legend_copies"] += copies
                    if not found:
                        continue
                    if legend_sheet(i, pg):
                        repeats = _repeats_earlier(found, counted[i])
                        answers[i]["per_page"].append({"page": pg, "count": len(found), "kartojasi": repeats,
                                                       "legenda_lape": True})
                        if not repeats:
                            counted[i].extend(found)
                    else:
                        others[i].append({"page": pg, "found": found})
                pdf.pages[pg - 1].close()               # its glyphs are cached; free the layout of a heavy sheet

        read(first)
        if rest and (other_sheets or any(not counted[i] for i in live)):
            read(rest)
        for i in live:
            a = answers[i]
            fallback = not counted[i] and bool(others[i])
            for o in others[i]:
                repeats = _repeats_earlier(o["found"], counted[i]) if fallback else False
                a["per_page"].append({"page": o["page"], "count": len(o["found"]), "kartojasi": repeats,
                                      "legenda_lape": False})
                if fallback and not repeats:
                    counted[i].extend(o["found"])
                elif not fallback:
                    a["kiti"].extend(o["found"])
            a["per_page"].sort(key=lambda r: r["page"])
            a["fallback"] = fallback
            a["instances"] = counted[i]
            a["count"] = len(counted[i])
            notes = []
            if fallback:
                notes.append("legendos eilutė stovi kitame lape nei ženklai — suskaičiuota visuose lapuose")
            if a["kiti"]:
                pages_k = sorted({x["page"] for x in a["kiti"]})
                notes.append(f"panašių ženklų yra ir lapuose be šios legendos ({', '.join(map(str, pages_k))}) — "
                             f"jie neįskaičiuoti; patikrinkite, ar tai tas pats ženklas")
            if a["partial"]:
                notes.append("ne visi lapai perskaityti per skirtą laiką — suskaičiuota tik dalis")
            a["detail"] = "; ".join(notes) or None
    return answers


def _instances_on(pdf, pg, info, t, tpls, exclude, zones, page_zones, words, zone_at, listed=None):
    """(instances, legend copies dropped, words) of one template on one read sheet. A match inside a legend,
    table or title-block zone is no instance; it is appended to `listed` as {page, x_pct, y_pct, zona}
    (W5-D D2: listed, never a mark)."""
    glyphs = info["glyphs"]
    W, H, ox, oy = info["W"], info["H"], info["ox"], info["oy"]
    drop = [tuple(float(v) for v in b) for b in (exclude.get(pg) or exclude.get(str(pg)) or [])]
    if int(t["page"]) == pg:
        drop.append(tuple(float(v) for v in t["glyph_bbox_pct"]))
        if t.get("legend_bbox_pct"):
            drop.append(tuple(float(v) for v in t["legend_bbox_pct"]))
    first = _first_word(t.get("text"))
    found: list[dict] = []
    copies = 0
    for tp in tpls:
        for g in _count_instances(tp, glyphs, (0.0, 0.0, -1.0, -1.0)):
            cx, cy = (g["cx"] - ox) / W, (g["cy"] - oy) / H
            if any(b[0] <= cx <= b[2] and b[1] <= cy <= b[3] for b in drop):
                continue
            if zones:
                z = zone_at(page_zones(pg), cx, cy)
                if z is not None and z.get("kind") in ZONE_KINDS_WITHOUT_MARKS:
                    if listed is not None and len(listed) < 200:
                        listed.append({"page": pg, "x_pct": round(cx, 4), "y_pct": round(cy, 4), "zona": str(z.get("kind"))})
                    continue
            bx = _instance_box(g, tp, glyphs)
            if first:
                if words is None:
                    words = pdf.pages[pg - 1].extract_words()
                if _legend_copy(bx, words, first):
                    copies += 1
                    continue
            found.append({"page": pg, "box_pct": [round(min(max(v, 0.0), 1.0), 5) for v in
                                                  ((bx[0] - ox) / W, (bx[1] - oy) / H, (bx[2] - ox) / W, (bx[3] - oy) / H)],
                          "x_pct": round(cx, 4), "y_pct": round(cy, 4)})
    return found, copies, words


_text_cache: "collections.OrderedDict[tuple, str]" = collections.OrderedDict()


def _folded_texts(pdf_bytes: bytes, digest: bytes, pages: list[int]) -> dict[int, str]:
    """{page: its text, folded} through PDFium's text page (cheap — no layout), cached per PDF and page."""
    from .pdfium_guard import PDFIUM_LOCK
    from .sheet_zones import fold
    out: dict[int, str] = {}
    missing = []
    with _glyph_lock:
        for pg in pages:
            hit = _text_cache.get((digest, pg))
            if hit is None:
                missing.append(pg)
            else:
                out[pg] = hit
    if not missing:
        return out
    try:
        import pypdfium2 as pdfium
    except ImportError:
        return out
    with PDFIUM_LOCK:
        try:
            doc = pdfium.PdfDocument(pdf_bytes)
        except Exception:  # noqa: BLE001
            return out
        try:
            for pg in missing:
                if not (1 <= pg <= len(doc)):
                    continue
                page = doc[pg - 1]
                try:
                    tp = page.get_textpage()
                    try:
                        out[pg] = fold(tp.get_text_range())
                    finally:
                        tp.close()
                except Exception:  # noqa: BLE001
                    out[pg] = ""
                finally:
                    page.close()
        finally:
            doc.close()
    with _glyph_lock:
        for pg in missing:
            if pg in out:
                _text_cache[(digest, pg)] = out[pg]
        while len(_text_cache) > 4 * GLYPH_CACHE_MAX:
            _text_cache.popitem(last=False)
    return out


def _row_key(text: str | None) -> str | None:
    """The first three words of a legend row's text, folded — what the row's sheets carry."""
    from .sheet_zones import fold
    words = [w for w in fold(text or "").split() if any(ch.isalpha() for ch in w)]
    if not words or len("".join(words[:3])) < 4:
        return None
    return " ".join(words[:3])


def count_glyph_instances(pdf_bytes: bytes, template_glyph: dict, pages: list[int] | None = None, **kw) -> dict:
    """One legend row's glyph counted on every sheet — see `count_glyph_instances_many`."""
    return count_glyph_instances_many(pdf_bytes, [template_glyph], pages, **kw)[0]
