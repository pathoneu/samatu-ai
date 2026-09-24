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
import io
import math
import re

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
    # a lone hairline (a table border beside the label) is never a symbol
    pool = [g for g in pool if not (g["short"] < 0.3 and g["long"] > 30 and not _has_twin(g, pool))]
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
