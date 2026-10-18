"""Legend rows — a legend box split into its rows: the drawn glyph (the symbol the plan repeats) and the text
that names it. €0, no model call: the PDF's text layer and its path objects.

Pathon v3, track B (docs/superpowers/specs/2026-10-18-pathon-v3-design.md §4; waves 2–4 plan, track W2-A, A1).
The person accepts a suggested legend (W1-E's `legenda` zone, extractor/sheet_zones.py) or draws a box; each
row found here becomes a count type whose glyph is the template the counters look for (vector_symbols
`count_glyph_instances` for a coloured glyph, cv_match `batch_find_symbol` for a black one).

HOW. Inside the box: the phrases of the text layer (sheet_zones.read_phrases — every text direction, DISPLAY
frame) and the painted path objects (PDFium, with their real fill / stroke paint: a stroked circle is not
„red" because the fill colour left over from the previous object was red). Marks bigger than a symbol or a
material sample (table rules, the frame) are not glyphs. Marks touching each other are one cluster; a row's
glyph is every cluster in the row's band between the previous text on that line and the row's text (left
style, the usual way) — two symbols on one row (objektas_d) are one row's glyph — or right of the text in a
column of their own (right style, objektas_g); the side with more rows wins, like sheet_zones. A text line
with no glyph directly under a row continues its text; a single symbol character in front of a text („⊗
Šviestuvas") is a text glyph. The legend's heading is its label, never a row.

Row: {row_id, page, glyph_bbox_pct, glyph_box_pt, glyph_kind: spalvotas|juodas|tekstas, colour, glyph_text,
      text, text_bbox_pct, countable, reason_lt}
  glyph_bbox_pct / text_bbox_pct — DISPLAY frame fractions (0–1, top-left origin, /Rotate applied), the frame
      the zones, the room outlines and the evidence crops use (api/evidence `rect`);
  glyph_box_pt — the glyph in UNROTATED mediabox points from the top-left, the viewer's measurement space
      (cv_tools `box_pt`), through sheet_zones.zone_to_mediabox_pt;
  glyph_kind — spalvotas: a coloured mark is part of it (the vector counter); juodas: black / grey marks only
      (the shape search); tekstas: the glyph is a character of the text layer;
  countable — False for a material or line sample (a hatch box, a line) — that row is an area or a length, not
      pieces — with the reason in Lithuanian.

A sheet with no text layer, or a box that holds only a pasted picture, answers `status: "be_teksto"` and no
rows: nothing is guessed. Never raises.
"""
from __future__ import annotations

import hashlib
import logging
import re

from .sheet_zones import (
    GLYPH_MAX_PT, GLYPH_MIN_PT, GLYPH_REACH_PT, LEGEND_HEADING_RE, MIN_TEXT_CHARS, SWATCH_MAX_H_PT, SWATCH_MAX_W_PT,
    _is_number_phrase, display_frame, read_phrases, read_zones, zone_to_mediabox_pt,
)

log = logging.getLogger("samatu.legend_rows")

KINDS = ("spalvotas", "juodas", "tekstas")
COLOUR_SPREAD = 0.12          # max − min of r, g, b (0–1) at or above this is a colour — vector_symbols._is_greyish
WHITE = 0.94                  # a paint this light on every channel draws nothing visible on the sheet
BAND_EM = 0.6                 # a glyph belongs to a row when its centre is within this many line heights of the text
CONTINUE_EM = 1.0             # a glyph-less line this close under a row (in line heights) continues its text
ALIGN_PT = 3.0                # … when its text starts this close to the row's text
ZONE_PAD = 0.004              # a suggested zone is tight around its glyphs and text: read a little around it
MAX_MARKS = 20_000            # a box this busy is a piece of the plan, not a legend
COUNTABLE_COMPACT_PT = 16.0   # vector_symbols: a symbol is at most this big across…
COUNTABLE_THIN_PT = 4.0       # …or a slot this thin…
COUNTABLE_LONG_PT = 120.0     # …and this long
_BULLETS = set("-–—•·*‒")
_SYMBOL_CHAR = re.compile(r"^[^\w\s]$|^[A-ZĄČĘĖĮŠŲŪŽ]$")

NO_TEXT_LT = "Lape nėra teksto sluoksnio — legendos eilučių perskaityti negalima; pažymėkite ženklus rankiniu būdu."
PICTURE_LT = ("Legenda įklijuota kaip paveikslėlis — joje nėra teksto, eilučių perskaityti negalima; "
              "pažymėkite ženklus rankiniu būdu.")
SAMPLE_LT = "Tai medžiagos ar linijos pavyzdys, ne ženklas — skaičiuojamas plotas ar ilgis, ne vienetai."


# ── marks (PDFium, real paint) ─────────────────────────────────────────────


def _rgb(c) -> tuple[float, float, float] | None:
    if c is None:
        return None
    return (round(c[0] / 255, 3), round(c[1] / 255, 3), round(c[2] / 255, 3))


def is_colour(rgb) -> bool:
    return bool(rgb) and max(rgb) - min(rgb) >= COLOUR_SPREAD


def _visible(rgb) -> bool:
    return bool(rgb) and min(rgb) < WHITE


def read_marks(pdf_bytes: bytes, page: int, region: tuple[float, float, float, float] | None = None) -> tuple[list[dict], bool]:
    """(marks, truncated): every PATH and IMAGE object of a 1-based page whose box centre lies in `region`
    (display points), as {x0, top, x1, bottom, fill, stroke, image} — fill / stroke the PAINTED colours (0–1 RGB),
    None where that paint is off. Display frame from PDFium's own page size and /Rotate (display_frame), never
    guessed from where the content lies. Read under PDFIUM_LOCK."""
    from .pdf_vectors import _to_display
    from .pdfium_guard import PDFIUM_LOCK
    try:
        import ctypes

        import pypdfium2 as pdfium
        import pypdfium2.raw as C
    except ImportError:
        return [], False
    frame = display_frame(pdf_bytes, page)
    if frame is None:
        return [], False
    W, H, rotation, _n = frame
    k = (int(rotation) // 90) % 4
    Wu, Hu = (H, W) if k in (1, 3) else (W, H)
    out: list[dict] = []
    truncated = False
    with PDFIUM_LOCK:
        try:
            doc = pdfium.PdfDocument(pdf_bytes)
        except Exception:  # noqa: BLE001
            return [], False
        try:
            pg = doc[page - 1]
            try:
                r, g, b, a = (ctypes.c_uint() for _ in range(4))
                fillmode, stroke_on = ctypes.c_int(), ctypes.c_int()
                for obj in pg.get_objects(max_depth=4):
                    if obj.type not in (C.FPDF_PAGEOBJ_PATH, C.FPDF_PAGEOBJ_IMAGE):
                        continue
                    try:
                        left, bottom, right, top = obj.get_bounds()
                    except Exception:  # noqa: BLE001
                        continue
                    pts = [(left, bottom), (right, bottom), (left, top), (right, top)]
                    parent = obj.container
                    while parent is not None:
                        ma, mb, mc, md, me, mf = parent.get_matrix().get()
                        pts = [(ma * x + mc * y + me, mb * x + md * y + mf) for x, y in pts]
                        parent = parent.container
                    disp = [_to_display(x, y, Wu, Hu, k) for x, y in pts]
                    xs = [p[0] for p in disp]
                    ys = [p[1] for p in disp]
                    m = {"x0": min(xs), "top": min(ys), "x1": max(xs), "bottom": max(ys),
                         "fill": None, "stroke": None, "image": obj.type == C.FPDF_PAGEOBJ_IMAGE}
                    if region is not None:
                        cx, cy = (m["x0"] + m["x1"]) / 2, (m["top"] + m["bottom"]) / 2
                        if not (region[0] <= cx <= region[2] and region[1] <= cy <= region[3]):
                            continue
                    if not m["image"]:
                        handle = obj.raw
                        if not C.FPDFPath_GetDrawMode(handle, fillmode, stroke_on):
                            fillmode.value, stroke_on.value = 0, 1
                        if fillmode.value and C.FPDFPageObj_GetFillColor(handle, r, g, b, a) and a.value:
                            m["fill"] = _rgb((r.value, g.value, b.value))
                        if stroke_on.value and C.FPDFPageObj_GetStrokeColor(handle, r, g, b, a) and a.value:
                            m["stroke"] = _rgb((r.value, g.value, b.value))
                    out.append(m)
                    if len(out) > MAX_MARKS:
                        truncated = True
                        break
            finally:
                pg.close()
        except Exception:  # noqa: BLE001 — a broken page has no marks
            return out, truncated
        finally:
            doc.close()
    return out, truncated


def _is_glyph_mark(m: dict) -> bool:
    """A mark that can be (part of) a legend glyph: a picture, or a visible path no bigger than a material
    sample. A black or grey line longer than a symbol is a table rule or an underline, never a glyph."""
    w, h = m["x1"] - m["x0"], m["bottom"] - m["top"]
    if m["image"]:
        return max(w, h) <= SWATCH_MAX_W_PT and min(w, h) >= GLYPH_MIN_PT
    paints = [p for p in (m["fill"], m["stroke"]) if _visible(p)]
    if not paints:
        return False
    if max(w, h) > SWATCH_MAX_W_PT or min(w, h) > SWATCH_MAX_H_PT:
        return False
    if not _visible(m["fill"]):
        # an outline bigger than a symbol both ways is a table cell or a ring drawn around something (objektas_h
        # p3: the legend table's cells, a detector's reach circle of the plan under it); a black line longer than
        # a symbol is a rule or an underline. A material sample is a FILLED box.
        if min(w, h) > GLYPH_MAX_PT:
            return False
        if max(w, h) > GLYPH_MAX_PT and not any(is_colour(p) for p in paints):
            return False
    return max(w, h) >= 0.8


def _clusters(marks: list[dict]) -> list[dict]:
    """Marks touching each other (0,8 pt) → one cluster {x0, top, x1, bottom, marks}."""
    from .vector_symbols import _clusters as touching
    out = []
    for grp in touching(marks):
        out.append({"x0": min(m["x0"] for m in grp), "top": min(m["top"] for m in grp),
                    "x1": max(m["x1"] for m in grp), "bottom": max(m["bottom"] for m in grp), "marks": grp})
    return out


# ── rows ────────────────────────────────────────────────────────────────────


def _band(ph: dict) -> tuple[float, float]:
    return ph["top"] - BAND_EM * ph["h"], ph["bottom"] + BAND_EM * ph["h"]


def _same_line(a: dict, b: dict) -> bool:
    return min(a["bottom"], b["bottom"]) - max(a["top"], b["top"]) >= 0.5 * min(a["h"], b["h"])


def _row_glyphs(phrases: list[dict], clusters: list[dict], side: str) -> dict[int, list[int]]:
    """phrase index → the clusters that are its glyph, for one side."""
    used: set[int] = set()
    got: dict[int, list[int]] = {}
    for pi, ph in sorted(enumerate(phrases), key=lambda t: (t[1]["top"], t[1]["x0"])):
        lo, hi = _band(ph)
        others = [o for oi, o in enumerate(phrases) if oi != pi and _same_line(o, ph)]
        if side == "left":
            limit = max([ph["x0"] - GLYPH_REACH_PT] + [o["x1"] for o in others if o["x1"] <= ph["x0"] + 0.5])
            pick = [ci for ci, c in enumerate(clusters) if ci not in used
                    and lo <= (c["top"] + c["bottom"]) / 2 <= hi
                    and c["x1"] <= ph["x0"] + 1.5 and c["x0"] >= limit - 0.5]
        else:
            limit = min([ph["x1"] + GLYPH_REACH_PT] + [o["x0"] for o in others if o["x0"] >= ph["x1"] - 0.5])
            pick = [ci for ci, c in enumerate(clusters) if ci not in used
                    and lo <= (c["top"] + c["bottom"]) / 2 <= hi
                    and c["x0"] >= ph["x1"] - 1.5 and c["x1"] <= limit + 0.5]
        if pick:
            used.update(pick)
            got[pi] = pick
    return got


def _hex(rgb) -> str | None:
    if not rgb:
        return None
    return "#" + "".join(f"{int(round(min(max(v, 0.0), 1.0) * 255)):02x}" for v in rgb[:3])


def _kind_and_colour(marks: list[dict]) -> tuple[str, str | None]:
    best = None
    best_area = -1.0
    for m in marks:
        for p in (m["fill"], m["stroke"]):
            if is_colour(p):
                area = max((m["x1"] - m["x0"]) * (m["bottom"] - m["top"]), 0.01)
                if area > best_area:
                    best, best_area = p, area
    return ("spalvotas", _hex(best)) if best else ("juodas", None)


def _countable(box: tuple[float, float, float, float]) -> bool:
    w, h = box[2] - box[0], box[3] - box[1]
    long, short = max(w, h), min(w, h)
    return long <= COUNTABLE_COMPACT_PT or (short <= COUNTABLE_THIN_PT and long <= COUNTABLE_LONG_PT)


def _pct(b, W: float, H: float) -> list[float]:
    clip = lambda v: min(max(v, 0.0), 1.0)  # noqa: E731
    return [round(clip(b[0] / W), 5), round(clip(b[1] / H), 5), round(clip(b[2] / W), 5), round(clip(b[3] / H), 5)]


class _Frame:
    """The frame the rows are paired in. A CAD sheet is drawn unrotated and turned by /Rotate (objektas_a,
    objektas_e): its legend reads left to right in the UNROTATED mediabox, not on the screen — the rows are
    paired there and the boxes turned back. A sheet whose legend reads left to right as displayed is paired
    as displayed."""

    def __init__(self, W: float, H: float, rotation: int, mediabox: bool):
        self.W, self.H, self.rot = W, H, int(rotation) % 360
        self.mediabox = mediabox and self.rot != 0
        self.Wm, self.Hm = (H, W) if self.rot % 180 == 90 else (W, H)

    def _box(self, pts) -> tuple[float, float, float, float]:
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return min(xs), min(ys), max(xs), max(ys)

    def to_work(self, b) -> tuple[float, float, float, float]:
        if not self.mediabox:
            return tuple(b)
        x = zone_to_mediabox_pt({"bbox_pct": [b[0] / self.W, b[1] / self.H, b[2] / self.W, b[3] / self.H]},
                                (self.Wm, self.Hm), self.rot)
        return tuple(x)

    def to_display(self, b) -> tuple[float, float, float, float]:
        if not self.mediabox:
            return tuple(b)
        from .cv_match import _rotate_pct
        pts = [_rotate_pct(x / self.Wm, y / self.Hm, self.rot) for x, y in ((b[0], b[1]), (b[2], b[1]), (b[0], b[3]), (b[2], b[3]))]
        x0, y0, x1, y1 = self._box(pts)
        return x0 * self.W, y0 * self.H, x1 * self.W, y1 * self.H


def _horizontal_share(phrases: list[dict], fr: "_Frame") -> float:
    """Share of the phrases (of 3+ characters) whose box in `fr`'s frame is wider than tall — text that reads
    along x there."""
    long = [ph for ph in phrases if len(ph["text"]) >= 3]
    if not long:
        return 1.0
    flat = 0
    for ph in long:
        x0, y0, x1, y1 = fr.to_work((ph["x0"], ph["top"], ph["x1"], ph["bottom"]))
        flat += (x1 - x0) >= (y1 - y0)
    return flat / len(long)


def _moved(d: dict, box) -> dict:
    return {**d, "x0": box[0], "top": box[1], "x1": box[2], "bottom": box[3]}


def _row_id(page: int, glyph_pct: list[float], text: str) -> str:
    key = f"{page}|{','.join(f'{v:.3f}' for v in glyph_pct)}|{text}".encode("utf-8")
    return f"p{page}-" + hashlib.blake2b(key, digest_size=4).hexdigest()


def _empty(page: int, status: str, detail: str | None, frame=None, bbox_pct=None) -> dict:
    W, H, rot = (frame[0], frame[1], frame[2]) if frame else (0.0, 0.0, 0)
    return {"page": int(page), "status": status, "detail": detail, "width_pt": W, "height_pt": H, "rotation": rot,
            "bbox_pct": list(bbox_pct) if bbox_pct else None, "label": None, "side": None, "rows": []}


def split_legend_rows(pdf_bytes: bytes, page: int, bbox_pct) -> dict:
    """{page, status: ok|be_teksto|no_page|failed, detail, width_pt, height_pt, rotation, bbox_pct, label, side,
    rows: [row]} for the legend inside `bbox_pct` ([x0, y0, x1, y1], DISPLAY-frame fractions) of a 1-based
    page. See the module docstring for a row. Never raises."""
    try:
        return _split(pdf_bytes, int(page), [float(v) for v in bbox_pct])
    except Exception as exc:  # noqa: BLE001 — a legend reading never sinks its caller
        log.warning("legend rows failed on page %s: %r", page, exc)
        return _empty(page, "failed", "legendos eilučių perskaityti nepavyko", bbox_pct=bbox_pct)


def _split(pdf_bytes: bytes, page: int, bbox_pct: list[float]) -> dict:
    frame = display_frame(pdf_bytes, page) if pdf_bytes and page >= 1 else None
    if frame is None or frame[0] <= 0 or frame[1] <= 0:
        return _empty(page, "no_page", "tokio lapo brėžinyje nėra", bbox_pct=bbox_pct)
    W, H, rotation, _n = frame
    x0, y0, x1, y1 = (min(max(v, 0.0), 1.0) for v in bbox_pct)
    if x1 <= x0 or y1 <= y0:
        return _empty(page, "ok", "rėmelis tuščias — nubrėžkite jį per visą legendą", frame, bbox_pct)
    region = (x0 * W, y0 * H, x1 * W, y1 * H)
    base = _empty(page, "ok", None, frame, [x0, y0, x1, y1])
    notes: list[str] = []

    phrases, n_chars, text_ok = read_phrases(pdf_bytes, page, (W, H))
    if not text_ok:
        notes.append("dalies lapo teksto rėmas nesutampa su lapo pasukimu — tas tekstas nenaudotas")
    inside = [ph for ph in phrases
              if region[0] <= (ph["x0"] + ph["x1"]) / 2 <= region[2] and region[1] <= (ph["top"] + ph["bottom"]) / 2 <= region[3]]
    marks, truncated = read_marks(pdf_bytes, page, region)
    if n_chars < MIN_TEXT_CHARS:
        return {**base, "status": "be_teksto", "detail": NO_TEXT_LT}
    if not inside:
        if any(m["image"] for m in marks):
            return {**base, "status": "be_teksto", "detail": PICTURE_LT}
        notes.append("rėmelyje nėra teksto eilučių — nubrėžkite jį per legendos ženklus ir jų pavadinimus")
        return {**base, "detail": "; ".join(notes)}
    if truncated:
        notes.append("rėmelyje per daug brėžinio linijų — tai plano dalis, ne legenda")
        return {**base, "detail": "; ".join(notes)}

    label = None
    texts = []
    for ph in inside:
        if ph["n_words"] <= 6 and LEGEND_HEADING_RE.match(ph["fold"]):
            label = label or ph["text"].rstrip(": ")
            continue
        if _is_number_phrase(ph):
            continue
        texts.append(ph)
    # the frame the legend reads left to right in: as displayed, or the unrotated sheet (a turned CAD sheet)
    fr = _Frame(W, H, rotation, mediabox=False)
    if int(rotation) % 360:
        turned = _Frame(W, H, rotation, mediabox=True)
        if _horizontal_share(texts, turned) >= 0.5 and (int(rotation) % 360 == 180 or _horizontal_share(texts, fr) < 0.5):
            fr = turned
    if _horizontal_share(texts, fr) < 0.5:
        notes.append("legendos tekstas lape pasuktas skersai — eilučių perskaityti negalima; pažymėkite ženklus rankiniu būdu")
        return {**base, "detail": "; ".join(notes), "label": label}
    texts = [_moved(ph, fr.to_work((ph["x0"], ph["top"], ph["x1"], ph["bottom"]))) for ph in texts]
    clusters = _clusters([_moved(m, fr.to_work((m["x0"], m["top"], m["x1"], m["bottom"])))
                          for m in marks if _is_glyph_mark(m)])

    best_side, best = "left", {}
    for side in ("left", "right"):
        got = _row_glyphs(texts, clusters, side)
        if len(got) > len(best):
            best_side, best = side, got

    rows: list[dict] = []
    row_of: dict[int, dict] = {}
    skipped = 0
    for pi, ph in sorted(enumerate(texts), key=lambda t: (t[1]["top"], t[1]["x0"])):
        if pi in best:
            gm = [m for ci in best[pi] for m in clusters[ci]["marks"]]
            gbox = (min(m["x0"] for m in gm), min(m["top"] for m in gm), max(m["x1"] for m in gm), max(m["bottom"] for m in gm))
            kind, colour = _kind_and_colour(gm)
            row = {"phrase": ph, "gbox": gbox, "kind": kind, "colour": colour, "glyph_text": None,
                   "text": ph["text"], "tbox": (ph["x0"], ph["top"], ph["x1"], ph["bottom"]),
                   "countable": _countable(gbox)}
            rows.append(row)
            row_of[pi] = row
            continue
        # the same line, right after a row's text (a gap the phrase reader split at) — still that row
        prev_same = [r for r in rows if _same_line(r["phrase"], ph) and r["tbox"][2] <= ph["x0"] + 0.5]
        if prev_same and best_side == "left":
            r = max(prev_same, key=lambda r: r["tbox"][2])
            r["text"] += " " + ph["text"]
            r["tbox"] = (r["tbox"][0], min(r["tbox"][1], ph["top"]), max(r["tbox"][2], ph["x1"]), max(r["tbox"][3], ph["bottom"]))
            continue
        # a line under a row, aligned with its text: the row's text goes on
        above = [r for r in rows if 0 <= ph["top"] - r["tbox"][3] <= CONTINUE_EM * max(ph["h"], r["phrase"]["h"])
                 and abs(ph["x0"] - r["tbox"][0]) <= ALIGN_PT]
        if above:
            r = max(above, key=lambda r: r["tbox"][3])
            r["text"] += " " + ph["text"]
            r["tbox"] = (min(r["tbox"][0], ph["x0"]), r["tbox"][1], max(r["tbox"][2], ph["x1"]), max(r["tbox"][3], ph["bottom"]))
            continue
        # a symbol character in front of the text („⊗ Šviestuvas", „T Termostatas")
        if ph["n_words"] >= 2 and _SYMBOL_CHAR.match(ph["first"]) and ph["first"] not in _BULLETS:
            gw = ph["h"] * 0.9
            gbox = (ph["x0"], ph["top"], ph["x0"] + gw, ph["bottom"])
            rest = ph["text"][len(ph["first"]):].strip()
            rows.append({"phrase": ph, "gbox": gbox, "kind": "tekstas", "colour": None, "glyph_text": ph["first"],
                         "text": rest, "tbox": (ph["x0"] + gw, ph["top"], ph["x1"], ph["bottom"]), "countable": True})
            continue
        skipped += 1

    out_rows = []
    rot = int(rotation)
    Wm, Hm = (H, W) if rot % 180 == 90 else (W, H)
    for r in sorted(rows, key=lambda r: (r["tbox"][1], r["tbox"][0])):
        gpct = _pct(fr.to_display(r["gbox"]), W, H)
        text = re.sub(r"\s+", " ", r["text"]).strip()
        out_rows.append({
            "row_id": _row_id(page, gpct, text),
            "page": page,
            "glyph_bbox_pct": gpct,
            "glyph_box_pt": zone_to_mediabox_pt({"bbox_pct": gpct}, (Wm, Hm), rot),
            "glyph_kind": r["kind"],
            "colour": r["colour"],
            "glyph_text": r["glyph_text"],
            "text": text,
            "text_bbox_pct": _pct(fr.to_display(r["tbox"]), W, H),
            "countable": bool(r["countable"]),
            "reason_lt": None if r["countable"] else SAMPLE_LT,
        })
    if skipped:
        notes.append(f"{skipped} teksto eil. be ženklo prie jų — ne legendos eilutės")
    if not out_rows:
        notes.append("rėmelyje neradau eilučių su ženklu — patikrinkite, ar jis apima ženklus ir pavadinimus")
    return {**base, "detail": "; ".join(notes) or None, "label": label, "side": best_side if best else None,
            "rows": out_rows}


def suggest_legend_rows(pdf_bytes: bytes, page: int, zones: list[dict] | None = None) -> dict:
    """The rows of every `legenda` zone of a 1-based page (W1-E's sheet zones, read here when `zones` is not
    given): {page, status, detail, legends: [{zone, ...split_legend_rows}]}. A sheet without a legend zone
    answers no legends and says so — the person then draws the box."""
    if zones is None:
        z = read_zones(pdf_bytes, page)
        status, detail, zones = z.get("status"), z.get("detail"), z.get("zones") or []
        if status in ("no_page", "no_text", "failed"):
            return {"page": int(page), "status": "be_teksto" if status == "no_text" else status,
                    "detail": NO_TEXT_LT if status == "no_text" else detail, "legends": []}
    legends = []
    for zone in zones:
        if zone.get("kind") != "legenda":
            continue
        x0, y0, x1, y1 = zone["bbox_pct"]
        box = [max(0.0, x0 - ZONE_PAD), max(0.0, y0 - ZONE_PAD), min(1.0, x1 + ZONE_PAD), min(1.0, y1 + ZONE_PAD)]
        legends.append({"zone": zone, **split_legend_rows(pdf_bytes, page, box)})
    return {"page": int(page), "status": "ok",
            "detail": None if legends else "šiame lape legendos nerasta — nubrėžkite rėmelį per ją",
            "legends": legends}


__all__ = ["KINDS", "NO_TEXT_LT", "is_colour", "read_marks", "split_legend_rows", "suggest_legend_rows"]
