"""Sheet zones — WHERE on a sheet the plan, the legend, the tables, the title block and the notes are.

Pathon v3, track A (docs/superpowers/specs/2026-10-18-pathon-v3-design.md §4): until now every zone was a
fixed fraction — the title block is (0,40; 0,70)–(1; 1) (page_classifier._ANTSPAUDAS_BBOX), a badge below
0,88 of the height is „in the title block" (room_locator.TITLE_BLOCK_FRAC). Nothing found the plan
viewport, a „SUTARTINIAI ŽYMĖJIMAI" block, a schedule or the notes, nor two plans on one sheet. This
module reads them from what the PDF already carries, €0, no model call:

  planas      the wall solid (pdf_vectors.wall_fills, the same grey fills the geometry lane outlines rooms
              from): groups of walls whose boxes overlap or nearly touch are one drawing; a drawing with a
              real share of the sheet's walls, two directions and no strip shape is a plan viewport — two
              viewports on one sheet are two zones — widened to the dimension strings written around it and
              named by a „… PLANAS" title just above or below it;
  legenda     a heading („SUTARTINIAI ŽYMĖJIMAI", „LUBŲ PLANO ŽYMĖJIMAI", „SUTARTINIS ŽYMĖJIMAS:",
              „ŽYMĖJIMAI", „SUTARTINIAI ŽENKLAI", „LEGENDA", „PAAIŠKINIMAI") with a column of rows under it,
              each carrying a drawn glyph — a symbol of 2–12 pt or a material swatch up to 110 × 45 pt —
              left of its text, or right of it in a symbol column (objektas_g); or a ruled table the heading
              titles, or whose header cell says „Žymėjimas";
  antspaudas  the title block: the fixed crop (page_classifier._ANTSPAUDAS_BBOX) confirmed by the document
              code (`_DOC_CODE_RE` → the dalis, "read") or by three title-block words ("assumed"), tightened
              to the ruled table the code stands in, the sheet frame's lower rows that hold it, or its text;
  lentele     a ruled table (pdfplumber `find_tables`, the eksplikacija reader's tool) of ≥ 3 rows × 2
              columns with text in its cells and words in its first row — not the sheet's frame, not a wall
              grid inside a plan; label = its title above it, else its header row;
  pastabos    a block of prose lines: three with a „PASTABOS" heading, else four lines and 20 words; a
              column of short paragraphs starting at one x is one block;
  kita        what is ambiguous — a legend heading with no glyph rows under it — with the reason.

A sheet without a text layer and without vector walls (a scan) answers no zones and says so
(`read_zones(...)["detail"] = "nėra teksto sluoksnio"`): nothing is guessed. Every other empty or partial
answer says why in `detail` too (a reader's frame that disagrees with the page's turn, a sheet too heavy to
lay out for tables).

Zone: {kind, bbox_pct: [x0, y0, x1, y1], label: str | None, confidence: "read" | "assumed",
       evidence: {source: "teksto_sluoksnis" | "vektoriai" | "lentele" | "antspaudo_kirpimas", detail: str}}
Zones may overlap and nest (a plan's dimension strings run under a legend beside it; a legend can sit in the
title block's band): at a point the innermost zone wins and a plan comes last (`zone_at`).

THE THREE FRAMES (inventory 2026-10-18, gap 7) — every bbox_pct here is in the second one:
  1. pdfplumber page frame — points from the page's top-left, /Rotate applied by pdfminer (vector_symbols,
     door_schedule, find_tables). Measured on objektas_a p6 (/Rotate 270) and on synthetic /Rotate 90 and
     270 sheets: a word or a table lands within 0,05 % of PDFium's display position, so a pdfplumber box
     over (page.width, page.height) IS a display fraction once the page box origin is subtracted.
  2. PDFium DISPLAY frame — PDF points, origin top-left, y down, /Rotate applied (pdf_vectors, the
     character reader, room `polygon_pct`, `_vieta`, evidence crops). `bbox_pct` = display points / the page
     size as displayed (PDFium's `get_size`, which has /Rotate applied — `display_frame`). The wall and
     character readers take this frame from the page too (pdf_vectors.page_frames, 2026-10-18); until then
     they guessed it from where the content lay and were wrong on objektas_e's turned sheets. A reader whose
     frame still disagrees with the page is not used (`read_phrases`, `_detect`) — a guard that should no
     longer fire.
  3. Unrotated MEDIABOX points, origin top-left — the viewer's measurement space (cv_tools `box_pt`;
     clicks arrive in it). `zone_to_mediabox_pt` turns a zone into it; `cv_match._rotate_pct` is the
     same turn the other way (mediabox → display).

PDFium is read only under `pdfium_guard.PDFIUM_LOCK` (pdf_vectors and the character reader take it; the
glyph reader below takes it itself). Results are cached per PDF digest and page.
"""
from __future__ import annotations

import collections
import copy
import hashlib
import io
import logging
import re
import threading
import unicodedata
from typing import Iterable, Sequence

log = logging.getLogger("samatu.sheet_zones")

ZONES_VERSION = 2            # 2 (2026-10-18): the readers take the frame from the page — turned sheets keep their text and plan
KINDS = ("planas", "legenda", "lentele", "antspaudas", "pastabos", "kita")
SOURCES = ("teksto_sluoksnis", "vektoriai", "lentele", "antspaudo_kirpimas")
NO_TEXT = "nėra teksto sluoksnio"

MIN_TEXT_CHARS = 8           # fewer real characters than this: the sheet has no text layer worth reading
MIN_WALLS = 4                # fewer wall-shaped fills is a swatch or a logo, not a plan (api/page_geometry.MIN_WALLS)
WALL_JOIN_PT = 6.0           # wall pieces closer than this belong to one group (a door opening is bridged by the ring)
PLAN_MIN_SHARE = 0.15        # a group of walls is its own plan only with this share of the sheet's wall area…
PLAN_ATTACH_PT = 60.0        # …a smaller group this close to a plan is part of it (a column, a free wall); farther, ignored
PLAN_MIN_SIDE_PT = 60.0      # a plan is a drawing in two directions: both sides at least this (≈ 21 mm)…
PLAN_MAX_ASPECT = 6.0        # …and not a strip (objektas_e p16: a schedule's grey bars are thin, long fills too)
PLAN_MERGE_PT = 12.0         # groups whose boxes overlap or come this close are ONE plan (objektas_h: partitions drawn apart from the shell)
PLAN_PAD_PT = 60.0           # dimension strings this far outside the walls are the plan's (≈ 21 mm on paper)
TABLE_MIN_ROWS = 3
TABLE_MIN_COLS = 2
TABLE_MAX_PAGE_SHARE = 0.45  # a ruled box bigger than this is the sheet's frame, not a table
TABLE_MIN_FILLED = 0.30      # share of cells with text — wall lines drawn as boxes make empty „tables"
TABLE_MIN_TEXT_ROWS = 3
TABLE_MAX_OBJECTS = 150_000  # a sheet drawing more objects is not laid out for tables (see _detect)…
REREAD_TABLE_MAX_OBJECTS = 40_000   # …and in the free re-read, which reads every plan sheet at once, this many
                                    # (objektas_g: 50–60 k objects a sheet, 3,8 s of pdfplumber layout each, no table)
TABLE_IN_PLAN_FILLED = 0.7   # a ruled grid inside a plan's walls is the walls, unless nearly every cell has text
GLYPH_MAX_PT = 12.0          # a legend glyph: a drawn mark at most this big (≈ 4 mm)…
GLYPH_MIN_PT = 2.0           # …and at least this (a hatch dot is no glyph)…
SWATCH_MAX_W_PT = 110.0      # …or a material swatch (a hatch, a fill or a line sample) at most this wide —
SWATCH_MAX_H_PT = 45.0       # …and this tall (objektas_d's ceiling legend: 92 × 31 pt grey boxes)
GLYPH_REACH_PT = 70.0        # a row's glyph stands at most this far left of its text
LEGEND_MIN_ROWS = 2
LEGEND_ROW_GAP_EM = 3.5      # rows of one legend follow each other within this many line heights
LEGEND_MAX_ROWS = 60
LEGEND_TABLE_GAP_PT = 6.0    # a ruled piece starting this close under a legend table continues it
LEGEND_ALIGN_PT = 10.0       # the rows' text (glyph left) or glyphs (glyph right) start within this of the first row's
NOTES_MIN_LINES = 3
NOTES_MIN_LINES_UNHEADED = 4
NOTES_MIN_WORDS_UNHEADED = 20
NOTES_LINE_GAP_EM = 2.2
NOTES_ALIGN_PT = 3.0
NOTES_PARAGRAPH_GAP_EM = 15.0
PHRASE_GAP_EM = 1.2          # words further apart than this many line heights are two phrases
LINE_OVERLAP = 0.5
ANTSPAUDAS_CLUSTER_EM = 5.0
ANTSPAUDAS_CLUSTER_PT = 25.0
LABEL_MAX = 80
PLAN_TITLE_REACH = 0.12      # a „… PLANAS" title within this share of the height below/above a plan names it

_CACHE_MAX = 64
_cache: "collections.OrderedDict[tuple[bytes, int, int], dict]" = collections.OrderedDict()
_cache_lock = threading.Lock()

# ── text ────────────────────────────────────────────────────────────────────


def fold(text: str | None) -> str:
    """Lowercase, Lithuanian letters without their marks, spaces collapsed: „ŽYMĖJIMAI:" → „zymejimai:"."""
    s = unicodedata.normalize("NFKD", str(text or ""))
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).lower()
    return re.sub(r"\s+", " ", s).strip()


# A legend's heading (folded). At most two words before it („SIENŲ PLANO ŽYMĖJIMAI", „M3 SUTARTINIS
# ŽYMĖJIMAS"), and the heading word ENDS the phrase — „Žymėjimas Sienų tipas" is a table's header row,
# which the table rule reads. A singular „Žymėjimas" alone is a column header, not a heading: it needs
# „sutartinis" before it or a colon after it (objektas_d „ŽYMĖJIMAS:").
LEGEND_HEADING_RE = re.compile(
    r"^(?:[\w.]+\s+){0,2}(?:sutartin\w*\s+(?:zymejim\w*|zenkl\w*)\s*:?|zymejimai\s*:?|zenklai\s*:?|legenda\s*:?"
    r"|paaiskinimai\s*:?|zymejimas\s*:|paaiskinimas\s*:)$")
NOTES_HEADING_RE = re.compile(r"^(?:bendrosios\s+|bendros\s+)?pastab(?:os|a)\b")
PLAN_TITLE_RE = re.compile(r"\b(planas|pjuvis|isklotin\w*|fasadas|schema)\b")
# Words a title block carries when its document code is not in the usual place
_TITLE_BLOCK_WORDS = ("lapas", "lapu", "laida", "stadija", "mastelis", "data", "projektavo", "projekto vadovas",
                      "pv", "pdv", "uzsakovas", "objektas", "brez", "dokumento zymuo", "statinys", "adresas", "parengta")
_BULLETS = set("-–—•·*‒")


def _phrases_of_direction(words: list[dict]) -> list[dict]:
    """Words of ONE text direction (their own left-to-right frame) → phrases: words on one line with
    gaps under PHRASE_GAP_EM line heights."""
    out: list[dict] = []
    lines: list[list[dict]] = []
    for w in sorted(words, key=lambda w: (w["top"], w["x0"])):
        h = max(w["bottom"] - w["top"], 1.0)
        for line in lines:
            ref = line[0]
            rh = max(ref["bottom"] - ref["top"], 1.0)
            overlap = min(w["bottom"], ref["bottom"]) - max(w["top"], ref["top"])
            if overlap >= LINE_OVERLAP * min(h, rh):
                line.append(w)
                break
        else:
            lines.append([w])
    for line in lines:
        line.sort(key=lambda w: w["x0"])
        cur: list[dict] = []
        for w in line:
            h = max(w["bottom"] - w["top"], 1.0)
            if cur and w["x0"] - cur[-1]["x1"] > PHRASE_GAP_EM * h:
                out.append(_phrase(cur))
                cur = []
            cur.append(w)
        if cur:
            out.append(_phrase(cur))
    return out


def _phrase(words: list[dict]) -> dict:
    text = " ".join(w["text"] for w in words)
    return {"text": text, "fold": fold(text), "n_words": len(words),
            "x0": min(w["x0"] for w in words), "x1": max(w["x1"] for w in words),
            "top": min(w["top"] for w in words), "bottom": max(w["bottom"] for w in words),
            "h": max(min(w["bottom"] - w["top"] for w in words), 1.0), "first": words[0]["text"]}


def read_phrases(pdf_bytes: bytes, page: int, frame: tuple[float, float] | None = None) -> tuple[list[dict], int, bool]:
    """(phrases in the DISPLAY frame, real character count, frame_ok) of a 1-based page, every text direction.
    Phrase: {text, fold, n_words, x0, top, x1, bottom (display points), h (glyph height in its own frame),
    first (its first word), turn (the direction's quarter turns)}.

    `frame` is the page's true display size (`display_frame`). The character reader takes the same frame
    from the page (pdf_vectors.page_frames); until 2026-10-18 it guessed it from where the characters lay and
    put objektas_e's turned sheets (17 of 45) in another frame. A direction whose frame still disagrees is
    NOT used — `frame_ok` is False — rather than placing zones where nothing is (a guard, no longer expected
    to fire)."""
    from .plan_area_annotations import _iter_pages, _words
    out: list[dict] = []
    n_chars = 0
    frame_ok = True
    try:
        directions = list(_iter_pages(pdf_bytes, [int(page)]))
    except Exception:  # noqa: BLE001 — no readable text is a sheet without text, not a failure
        return [], 0, True
    for turn, (_pn, Wd, Hd, chars, to_display) in enumerate(directions):
        n_chars += sum(1 for c in chars if not str(c.get("text") or "").isspace())
        if frame and (abs(float(Wd) - frame[0]) > 1.0 or abs(float(Hd) - frame[1]) > 1.0):
            frame_ok = False
            continue
        for ph in _phrases_of_direction(_words(chars)):
            x0, top, x1, bottom = to_display([ph["x0"], ph["top"], ph["x1"], ph["bottom"]])
            out.append({**ph, "x0": x0, "top": top, "x1": x1, "bottom": bottom, "turn": turn})
    return out, n_chars, frame_ok


def display_frame(pdf_bytes: bytes, page: int) -> tuple[float, float, int, int] | None:
    """(width, height, rotation, objects) of a 1-based page AS DISPLAYED — PDFium's page size, which has
    /Rotate applied (objektas_e: MediaBox 842 × 1191, /Rotate 270 → 1191 × 842) — and how many objects its
    content stream draws (free to ask). None for a missing page."""
    from .pdfium_guard import PDFIUM_LOCK
    try:
        import pypdfium2 as pdfium
    except ImportError:
        return None
    with PDFIUM_LOCK:
        try:
            doc = pdfium.PdfDocument(pdf_bytes)
        except Exception:  # noqa: BLE001
            return None
        try:
            if not (1 <= page <= len(doc)):
                return None
            pg = doc[page - 1]
            try:
                import pypdfium2.raw as C
                w, h = (float(v) for v in pg.get_size())
                return w, h, int(pg.get_rotation() or 0) % 360, int(C.FPDFPage_CountObjects(pg.raw))
            finally:
                pg.close()
        except Exception:  # noqa: BLE001
            return None
        finally:
            doc.close()


def _is_number_phrase(ph: dict) -> bool:
    return bool(re.fullmatch(r"[\d\s.,+\-±/xX×]+", ph["text"])) and any(c.isdigit() for c in ph["text"])


_TABLE_WORDS = re.compile(r"eksplikacij|ziniarast|specifikacij|lentel|sarasas|suvestin|kiekiai")


def _title_like(ph: dict) -> bool:
    """A table's title: mostly capitals („DURŲ ŽINIARAŠTIS"), or a table word („Vidinių angų (durų)
    žiniaraštis"). A note's tail just above a table („(tikslinama pagal …") is not one."""
    letters = [ch for ch in ph["text"] if ch.isalpha()]
    if letters and sum(ch.isupper() for ch in letters) >= 0.6 * len(letters):
        return True
    return bool(_TABLE_WORDS.search(ph["fold"]))


def _is_prose(ph: dict) -> bool:
    words = [w for w in ph["text"].split() if sum(ch.isalpha() for ch in w) >= 2]
    return len(words) >= 3


# ── vectors: walls and small drawn marks ────────────────────────────────────


def _wall_groups(pdf_bytes: bytes, page: int) -> list[dict]:
    """Groups of wall pieces that are one plan each: {bounds: (x0, top, x1, bottom), pieces, area}."""
    from shapely.geometry import box as _sbox
    from shapely.ops import unary_union

    from .pdf_vectors import wall_fills
    fills = wall_fills(pdf_bytes, page)
    if len(fills) < MIN_WALLS:
        return []
    grown = unary_union([f.buffer(WALL_JOIN_PT / 2) for f in fills])
    parts = list(grown.geoms) if grown.geom_type == "MultiPolygon" else [grown]
    groups = []
    for part in parts:
        inside = [f for f in fills if part.intersects(f.representative_point())]
        if not inside:
            continue
        b = unary_union(inside).bounds
        groups.append({"bounds": b, "pieces": len(inside), "area": sum(f.area for f in inside)})
    # one plan is often drawn in several pieces that do not touch (the shell, the partitions, a stair):
    # boxes that overlap or nearly touch are one drawing; two viewports stand apart
    merged = True
    while merged:
        merged = False
        for i in range(len(groups)):
            for j in range(i + 1, len(groups)):
                a, b = groups[i], groups[j]
                if _sbox(*a["bounds"]).distance(_sbox(*b["bounds"])) <= PLAN_MERGE_PT:
                    groups[i] = {"bounds": _union(a["bounds"], b["bounds"]), "pieces": a["pieces"] + b["pieces"],
                                 "area": a["area"] + b["area"]}
                    del groups[j]
                    merged = True
                    break
            if merged:
                break
    total = sum(g["area"] for g in groups) or 1.0
    groups.sort(key=lambda g: -g["area"])

    def drawing(g) -> bool:
        w, h = g["bounds"][2] - g["bounds"][0], g["bounds"][3] - g["bounds"][1]
        return min(w, h) >= PLAN_MIN_SIDE_PT and max(w, h) <= PLAN_MAX_ASPECT * min(w, h)
    plans = [g for g in groups if g["area"] >= PLAN_MIN_SHARE * total and g["pieces"] >= MIN_WALLS and drawing(g)]
    for g in groups:
        if g in plans:
            continue
        near = None
        for p in plans:
            d = _sbox(*p["bounds"]).distance(_sbox(*g["bounds"]))
            if d <= PLAN_ATTACH_PT and (near is None or d < near[0]):
                near = (d, p)
        if near is not None:
            p = near[1]
            p["bounds"] = _union(p["bounds"], g["bounds"])
            p["pieces"] += g["pieces"]
            p["area"] += g["area"]
    return plans


def _marks(pdf_bytes: bytes, page: int, W: float, H: float, rotation: int) -> list[dict]:
    """Every drawn path's box on the page, display frame: {x0, top, x1, bottom, fill, stroke}. Boxes only —
    no segment is walked — so a heavy sheet costs one call per object. Read under PDFIUM_LOCK."""
    from .pdf_vectors import _to_display
    from .pdfium_guard import PDFIUM_LOCK
    try:
        import ctypes

        import pypdfium2 as pdfium
        import pypdfium2.raw as C
    except ImportError:
        return []
    k = (int(rotation) // 90) % 4
    Wu, Hu = (H, W) if k in (1, 3) else (W, H)
    out: list[dict] = []
    with PDFIUM_LOCK:
        try:
            doc = pdfium.PdfDocument(pdf_bytes)
        except Exception:  # noqa: BLE001
            return []
        try:
            if not (1 <= page <= len(doc)):
                return []
            pg = doc[page - 1]
            try:
                r, g, b, a = (ctypes.c_uint() for _ in range(4))
                for obj in pg.get_objects(max_depth=4):
                    if obj.type != C.FPDF_PAGEOBJ_PATH:
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
                    fill = stroke = None
                    handle = obj.raw
                    if C.FPDFPageObj_GetFillColor(handle, r, g, b, a):
                        fill = (r.value, g.value, b.value)
                    if C.FPDFPageObj_GetStrokeColor(handle, r, g, b, a):
                        stroke = (r.value, g.value, b.value)
                    out.append({"x0": min(xs), "top": min(ys), "x1": max(xs), "bottom": max(ys),
                                "fill": fill, "stroke": stroke})
            finally:
                pg.close()
        except Exception:  # noqa: BLE001 — a broken page has no marks
            return out
        finally:
            doc.close()
    return out


def _coloured(rgb) -> bool:
    if not rgb:
        return False
    r, g, b = rgb
    return max(r, g, b) - min(r, g, b) > 40          # not black, white or a grey


def _is_glyph(m: dict) -> bool:
    """A mark that can stand at the start of a legend row: a small symbol, or a material swatch. Only ever
    asked for marks beside the text rows under a legend heading, so a swatch need not be coloured."""
    w, h = m["x1"] - m["x0"], m["bottom"] - m["top"]
    if GLYPH_MIN_PT <= max(w, h) <= GLYPH_MAX_PT:
        return True
    return w <= SWATCH_MAX_W_PT and h <= SWATCH_MAX_H_PT and min(w, h) >= GLYPH_MIN_PT and max(w, h) > GLYPH_MAX_PT


# ── tables ──────────────────────────────────────────────────────────────────


def _tables(pdf_bytes: bytes, page: int, W: float, H: float) -> list[dict]:
    """Ruled tables with text: {x0, top, x1, bottom (display points), rows, cols, header, filled, cells}."""
    try:
        from . import pdf_page_cache  # noqa: F401 — installs the lazy pdfminer debug log (53 s → 1 s per open)
        import pdfplumber
    except ImportError:
        return []
    out: list[dict] = []
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            if not (1 <= page <= len(pdf.pages)):
                return []
            pg = pdf.pages[page - 1]
            try:
                ox, oy = float(pg.bbox[0]), float(pg.bbox[1])
                pw, ph = float(pg.width), float(pg.height)
                sx, sy = (W / pw if pw else 1.0), (H / ph if ph else 1.0)
                for t in pg.find_tables() or []:
                    try:
                        rows = t.extract() or []
                    except Exception:  # noqa: BLE001
                        continue
                    x0, top, x1, bottom = (float(v) for v in t.bbox)
                    box = ((x0 - ox) * sx, (top - oy) * sy, (x1 - ox) * sx, (bottom - oy) * sy)
                    cells = [str(c or "").strip() for row in rows for c in row]
                    filled = sum(1 for c in cells if c)
                    text_rows = [row for row in rows if any(str(c or "").strip() for c in row)]
                    cols = max((len(row) for row in rows), default=0)
                    header = next((" · ".join(re.sub(r"\s+", " ", str(c)).strip() for c in row if str(c or "").strip())
                                   for row in rows if any(str(c or "").strip() for c in row)), "")
                    row_boxes = []
                    for row in getattr(t, "rows", None) or []:
                        rb = getattr(row, "bbox", None)
                        if rb:
                            row_boxes.append(((rb[0] - ox) * sx, (rb[1] - oy) * sy, (rb[2] - ox) * sx, (rb[3] - oy) * sy))
                    out.append({"x0": box[0], "top": box[1], "x1": box[2], "bottom": box[3], "row_boxes": row_boxes,
                                "rows": len(rows), "text_rows": len(text_rows), "cols": cols,
                                "filled": (filled / len(cells)) if cells else 0.0, "header": header,
                                "first_row": next((row for row in rows if any(str(c or "").strip() for c in row)), [])})
            finally:
                try:
                    pg.close()
                except Exception:  # noqa: BLE001
                    pass
    except Exception:  # noqa: BLE001 — a page pdfplumber cannot lay out has no tables we can read
        return out
    return out


def _real_table(t: dict, W: float, H: float) -> str | None:
    """None when `t` is a table worth a zone, else why not (kept for the report script)."""
    area = (t["x1"] - t["x0"]) * (t["bottom"] - t["top"])
    if area >= TABLE_MAX_PAGE_SHARE * W * H:
        return "lapo rėmelis"
    if t["rows"] < TABLE_MIN_ROWS or t["cols"] < TABLE_MIN_COLS:
        return "per mažai eilučių ar stulpelių"
    if t["text_rows"] < TABLE_MIN_TEXT_ROWS or t["filled"] < TABLE_MIN_FILLED:
        return "langeliuose beveik nėra teksto"
    if not any(sum(ch.isalpha() for ch in str(c or "")) >= 3 for c in t["first_row"]):
        return "pirmoje eilutėje nėra žodžių — tai matmenys sienų tinklelyje"
    return None


# ── zones ───────────────────────────────────────────────────────────────────


def _union(a, b):
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))


def _box(ph: dict) -> tuple[float, float, float, float]:
    return (ph["x0"], ph["top"], ph["x1"], ph["bottom"])


def _inside(b, region, tol: float = 0.0) -> bool:
    x0, y0, x1, y1 = b
    return x0 >= region[0] - tol and y0 >= region[1] - tol and x1 <= region[2] + tol and y1 <= region[3] + tol


def _centre_in(b, region) -> bool:
    cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
    return region[0] <= cx <= region[2] and region[1] <= cy <= region[3]


def _overlap_share(b, region) -> float:
    ix = max(0.0, min(b[2], region[2]) - max(b[0], region[0]))
    iy = max(0.0, min(b[3], region[3]) - max(b[1], region[1]))
    a = max((b[2] - b[0]) * (b[3] - b[1]), 1e-9)
    return ix * iy / a


def _pct(b, W: float, H: float) -> list[float]:
    x0, y0, x1, y1 = b
    clip = lambda v: min(max(v, 0.0), 1.0)  # noqa: E731
    return [round(clip(x0 / W), 4), round(clip(y0 / H), 4), round(clip(x1 / W), 4), round(clip(y1 / H), 4)]


def _zone(kind: str, b, W: float, H: float, label: str | None, confidence: str, source: str, detail: str) -> dict:
    return {"kind": kind, "bbox_pct": _pct(b, W, H), "label": (label or None) and str(label)[:LABEL_MAX],
            "confidence": confidence, "evidence": {"source": source, "detail": detail}}


def _title_block(phrases, tables, W, H) -> dict | None:
    from .page_classifier import _ANTSPAUDAS_BBOX, _DOC_CODE_RE
    cx0, cy0, cx1, cy1 = _ANTSPAUDAS_BBOX
    crop = (cx0 * W, cy0 * H, cx1 * W, cy1 * H)
    in_crop = [ph for ph in phrases if _centre_in(_box(ph), crop)]
    if not in_crop:
        return None
    code_ph, code = None, None
    for ph in in_crop:
        m = _DOC_CODE_RE.search(" " + ph["text"])
        if m:
            code_ph, code = ph, ("ŠVOK" if m.group(1) == "SVOK" else m.group(1))
            break
    if code_ph is None:
        hits = [ph for ph in in_crop if any(re.search(r"\b" + re.escape(wd) + r"\b", ph["fold"]) for wd in _TITLE_BLOCK_WORDS)]
        if len(hits) < 3:
            return None
        seed, confidence = hits[0], "assumed"
        detail = f"lapo kampe {len(hits)} antspaudo žodžiai, dokumento žymens nerasta"
    else:
        seed, confidence = code_ph, "read"
        detail = f"dokumento žymuo „{code_ph['text'][:40]}“ — dalis {code}"
    # the ruled table the seed stands in (title blocks are usually one), else the text cluster around it
    holder = [t for t in tables if _centre_in(_box(seed), (t["x0"], t["top"], t["x1"], t["bottom"]))
              and (t["x1"] - t["x0"]) * (t["bottom"] - t["top"]) < TABLE_MAX_PAGE_SHARE * W * H]
    if holder:
        t = min(holder, key=lambda t: (t["x1"] - t["x0"]) * (t["bottom"] - t["top"]))
        b = (t["x0"], t["top"], t["x1"], t["bottom"])
        return _zone("antspaudas", b, W, H, code or "antspaudas", confidence, "lentele", detail + "; antspaudo lentelė")
    # the sheet's frame drawn as one ruled box with the title block as its lowest rows (designer sheets,
    # objektas_h: a band across the whole width) — the frame's rows below the crop's top that hold title text
    band = None
    for t in tables:
        if (t["x1"] - t["x0"]) * (t["bottom"] - t["top"]) < TABLE_MAX_PAGE_SHARE * W * H:
            continue
        for rb in t.get("row_boxes") or []:
            if rb[1] >= crop[1] - 1 and any(_centre_in(_box(ph), rb) for ph in in_crop):
                band = rb if band is None else _union(band, rb)
        if band is not None and _centre_in(_box(seed), band):
            return _zone("antspaudas", band, W, H, code or "antspaudas", confidence, "lentele",
                         detail + "; apatinės lapo rėmelio eilutės")
        band = None
    b = _box(seed)
    members = [seed]
    grew = True
    while grew:
        grew = False
        for ph in in_crop:
            if ph in members:
                continue
            reach = max(ANTSPAUDAS_CLUSTER_PT, ANTSPAUDAS_CLUSTER_EM * max(ph["h"], seed["h"]))
            pb = _box(ph)
            if pb[0] <= b[2] + reach and pb[2] >= b[0] - reach and pb[1] <= b[3] + reach and pb[3] >= b[1] - reach:
                members.append(ph)
                b = _union(b, pb)
                grew = True
    return _zone("antspaudas", b, W, H, code or "antspaudas", confidence, "antspaudo_kirpimas", detail)


def _legend_rows(head: dict, phrases: list[dict], glyphs: list[dict], taken) -> tuple[list[dict], tuple]:
    """Rows under a legend heading that carry a drawn glyph: (rows, bbox). A row: {phrase, glyph, side}.

    The glyph stands LEFT of the row's text (the usual way) or RIGHT of it in a column of its own (objektas_g:
    „El. taškas | Žymėjimas"); both are tried and the side with more rows is the legend's. One glyph — the
    marks drawn over each other as one symbol — belongs to one row: a row's second line is no second row."""
    best: tuple[list[dict], tuple] = ([], _box(head))
    for side in ("left", "right"):
        got = _legend_rows_on(head, phrases, glyphs, taken, side)
        if len(got[0]) > len(best[0]):
            best = got
    return best


def _legend_rows_on(head: dict, phrases: list[dict], glyphs: list[dict], taken, side: str) -> tuple[list[dict], tuple]:
    h = head["h"]
    region_b = _box(head)
    rows: list[dict] = []
    used: set[int] = set()
    bottom = head["bottom"]
    pitch = 0.0                  # the tallest glyph so far: swatch rows stand that far apart
    candidates = sorted((ph for ph in phrases if ph is not head and ph["top"] >= head["top"] + 0.5 * h
                         and not any(_centre_in(_box(ph), z) for z in taken)), key=lambda ph: (ph["top"], ph["x0"]))
    left = head["x0"] - GLYPH_REACH_PT
    anchor = None                # a legend is a COLUMN: the rows' text starts (left) or their glyphs stand (right) in line
    for ph in candidates:
        if len(rows) >= LEGEND_MAX_ROWS:
            break
        if ph["top"] > bottom + LEGEND_ROW_GAP_EM * max(h, ph["h"]) * (2 if not rows else 1) + 1.5 * pitch:
            break
        if ph["x0"] < left or ph["x0"] > head["x1"] + 4 * GLYPH_REACH_PT:
            continue
        if _is_number_phrase(ph):
            continue
        if side == "left" and anchor is not None and abs(ph["x0"] - anchor) > LEGEND_ALIGN_PT:
            continue
        band = (ph["top"] - 0.6 * ph["h"], ph["bottom"] + 0.6 * ph["h"])
        glyph = None
        for i, g in enumerate(glyphs):
            if i in used:
                continue
            gc = (g["top"] + g["bottom"]) / 2
            if not band[0] <= gc <= band[1]:
                continue
            if side == "left":
                if g["x1"] <= ph["x0"] + 1.5 and g["x1"] >= ph["x0"] - GLYPH_REACH_PT:
                    if glyph is None or g["x1"] > glyph[1]["x1"]:
                        glyph = (i, g)
            elif g["x0"] >= ph["x1"] - 1.5 and g["x0"] <= ph["x1"] + GLYPH_REACH_PT \
                    and (anchor is None or abs((g["x0"] + g["x1"]) / 2 - anchor) <= LEGEND_ALIGN_PT):
                if glyph is None or g["x0"] < glyph[1]["x0"]:
                    glyph = (i, g)
        if glyph is not None:
            # the whole symbol: every mark drawn over the chosen one
            i0, g0 = glyph
            box_g = (g0["x0"], g0["top"], g0["x1"], g0["bottom"])
            for i, g in enumerate(glyphs):
                if i not in used and g["x0"] <= box_g[2] + 1 and g["x1"] >= box_g[0] - 1 \
                        and g["top"] <= box_g[3] + 1 and g["bottom"] >= box_g[1] - 1:
                    used.add(i)
                    box_g = _union(box_g, (g["x0"], g["top"], g["x1"], g["bottom"]))
            used.add(i0)
            mark = {"x0": box_g[0], "top": box_g[1], "x1": box_g[2], "bottom": box_g[3]}
        elif side == "left" and len(ph["first"]) == 1 and not ph["first"].isalnum() and ph["first"] not in _BULLETS:
            mark = {"x0": ph["x0"], "top": ph["top"], "x1": ph["x0"] + ph["h"], "bottom": ph["bottom"], "text": ph["first"]}
        else:
            continue
        rows.append({"phrase": ph, "glyph": mark, "side": side})
        if anchor is None:
            anchor = ph["x0"] if side == "left" else (mark["x0"] + mark["x1"]) / 2
        bottom = max(bottom, ph["bottom"], mark["bottom"])
        pitch = max(pitch, mark["bottom"] - mark["top"])
        region_b = _union(region_b, _union(_box(ph), (mark["x0"], mark["top"], mark["x1"], mark["bottom"])))
    return rows, region_b


def _notes(phrases: list[dict], taken: list[tuple]) -> list[list[dict]]:
    """Blocks of prose lines (≥ NOTES_MIN_LINES) outside the zones already found."""
    prose = [ph for ph in phrases if (_is_prose(ph) or NOTES_HEADING_RE.match(ph["fold"]))
             and not any(_overlap_share(_box(ph), z) > 0.5 for z in taken)]
    prose.sort(key=lambda ph: (ph["top"], ph["x0"]))
    blocks: list[list[dict]] = []
    for ph in prose:
        for blk in blocks:
            last = blk[-1]
            b = _block_box(blk)
            gap = ph["top"] - last["bottom"]
            if -0.5 * ph["h"] <= gap <= NOTES_LINE_GAP_EM * max(ph["h"], last["h"]) and ph["x0"] <= b[2] and ph["x1"] >= b[0]:
                blk.append(ph)
                break
        else:
            blocks.append([ph])
    # a column of notes written in short paragraphs (objektas_h p3: callouts beside the plan, one under the
    # other) is one zone: blocks that start at the same x and follow each other closely are joined
    joined = True
    while joined:
        joined = False
        blocks.sort(key=lambda blk: _block_box(blk)[1])
        for i in range(len(blocks) - 1):
            a, b = _block_box(blocks[i]), _block_box(blocks[i + 1])
            h = max(blocks[i][-1]["h"], blocks[i + 1][0]["h"])
            if abs(a[0] - b[0]) <= NOTES_ALIGN_PT and 0 <= b[1] - a[3] <= NOTES_PARAGRAPH_GAP_EM * h:
                blocks[i] = blocks[i] + blocks[i + 1]
                del blocks[i + 1]
                joined = True
                break
    def enough(blk) -> bool:
        if any(NOTES_HEADING_RE.match(ph["fold"]) for ph in blk):
            return len(blk) >= NOTES_MIN_LINES
        # without a „PASTABOS" heading a block must be dense: three short lines are a callout or a label
        return len(blk) >= NOTES_MIN_LINES_UNHEADED and sum(len(ph["text"].split()) for ph in blk) >= NOTES_MIN_WORDS_UNHEADED
    return [b for b in blocks if enough(b)]


def _block_box(blk):
    b = _box(blk[0])
    for ph in blk[1:]:
        b = _union(b, _box(ph))
    return b


def _plan_label(b, phrases, H) -> str | None:
    best = None
    for ph in phrases:
        if not PLAN_TITLE_RE.search(ph["fold"]) or ph["n_words"] > 6 or "(" in ph["text"]:
            continue
        if ph["x1"] < b[0] or ph["x0"] > b[2]:
            continue
        if ph["top"] >= b[3] - 0.5 * ph["h"]:
            d = max(ph["top"] - b[3], 0.0)
        elif ph["bottom"] <= b[1] + 0.5 * ph["h"]:
            d = max(b[1] - ph["bottom"], 0.0)
        else:
            continue                         # a title inside the drawing names a detail, not the plan
        rank = (0 if "planas" in ph["fold"] else 1, d)          # „… PLANAS" before a section or detail title
        if d <= PLAN_TITLE_REACH * H and (best is None or rank < best[0]):
            best = (rank, ph["text"])
    return best[1] if best else None


def _detect(pdf_bytes: bytes, page: int, table_max_objects: int | None = None) -> dict:
    from .pdf_vectors import page_geometry, page_paths
    frame = display_frame(pdf_bytes, page)
    base = {"page": int(page), "width_pt": 0.0, "height_pt": 0.0, "rotation": 0,
            "versija": ZONES_VERSION, "zones": [], "status": "ok", "detail": None}
    if frame is None or frame[0] <= 0 or frame[1] <= 0:
        return {**base, "status": "no_page", "detail": "tokio lapo brėžinyje nėra"}
    W, H, rotation, n_objects = frame
    base.update(width_pt=W, height_pt=H, rotation=rotation)
    notes: list[str] = []
    phrases, n_chars, text_ok = read_phrases(pdf_bytes, page, (W, H))
    if not text_ok:
        notes.append("dalies teksto lapo rėmas nesutampa su lapo pasukimu — tas tekstas nenaudotas")
    # the wall reader takes its frame from the page (pdf_vectors.page_frames); a disagreement is a guard only
    Wv, Hv, _ = page_geometry(pdf_bytes, page)
    groups: list[dict] = []
    if abs(Wv - W) <= 1.0 and abs(Hv - H) <= 1.0:
        groups = _wall_groups(pdf_bytes, page)
    elif page_paths(pdf_bytes, page):
        notes.append("sienų brėžinio rėmas nesutampa su lapo pasukimu — planas nenustatytas")
    if n_chars < MIN_TEXT_CHARS and not groups and not notes:
        return {**base, "status": "no_text", "detail": NO_TEXT}
    if notes:
        base["detail"] = "; ".join(notes)
    zones: list[dict] = []
    taken: list[tuple] = []           # boxes of specific zones, display points

    tables: list[dict] = []
    if n_chars >= MIN_TEXT_CHARS:
        if n_objects <= (TABLE_MAX_OBJECTS if table_max_objects is None else table_max_objects):
            tables = _tables(pdf_bytes, page, W, H)
        else:
            # pdfplumber lays out every object to find ruled tables: objektas_b's hatched sheets (200–300 k
            # objects) cost 12–24 s each and held no table. Skipped, and said.
            notes.append(f"lentelių neieškota — lape per daug brėžinio objektų ({n_objects})")
            base["detail"] = "; ".join(notes)
    wall_boxes = [g["bounds"] for g in groups]

    # 1. legend headings (their glyph rows, or a table they title) — before the title block: on a sheet whose
    # frame is one ruled box, the title block's frame row can hold the legend too (objektas_a p6, p9)
    heads = [ph for ph in phrases if ph["n_words"] <= 6 and LEGEND_HEADING_RE.match(ph["fold"])]
    legend_tables: set[int] = set()
    glyphs: list[dict] | None = None
    for head in sorted(heads, key=lambda ph: (ph["top"], ph["x0"])):
        if any(_centre_in(_box(head), z) for z in taken):
            continue
        # a table the heading titles (just above it) or heads (inside its first row)
        titled = None
        for i, t in enumerate(tables):
            if i in legend_tables or _real_table(t, W, H):
                continue
            tb_box = (t["x0"], t["top"], t["x1"], t["bottom"])
            above = 0 <= t["top"] - head["bottom"] <= 3 * head["h"] and head["x0"] <= t["x1"] and head["x1"] >= t["x0"]
            if above or _centre_in(_box(head), tb_box):
                titled = (i, t)
                break
        if titled:
            i, t = titled
            legend_tables.add(i)
            b = _union(_box(head), (t["x0"], t["top"], t["x1"], t["bottom"]))
            n_rows = t["text_rows"]
            # a ruled piece that goes on right under it is the same legend (objektas_h p2: its last row
            # „T Termostatas" is ruled apart, a point below)
            grew = True
            while grew:
                grew = False
                for j, u in enumerate(tables):
                    if j in legend_tables or (u["x1"] - u["x0"]) * (u["bottom"] - u["top"]) >= TABLE_MAX_PAGE_SHARE * W * H:
                        continue
                    overlap = min(u["x1"], b[2]) - max(u["x0"], b[0])
                    if 0 <= u["top"] - b[3] <= LEGEND_TABLE_GAP_PT and overlap >= 0.7 * min(u["x1"] - u["x0"], b[2] - b[0]):
                        legend_tables.add(j)
                        b = _union(b, (u["x0"], u["top"], u["x1"], u["bottom"]))
                        n_rows += u["text_rows"]
                        grew = True
            zones.append(_zone("legenda", b, W, H, head["text"].rstrip(": "), "read", "lentele",
                               f"antraštė „{head['text'][:40]}“ virš lentelės, {n_rows} eil."))
            taken.append(b)
            continue
        if glyphs is None:
            glyphs = [m for m in _marks(pdf_bytes, page, W, H, rotation) if _is_glyph(m)]
        rows, b = _legend_rows(head, phrases, glyphs, taken)
        if len(rows) >= LEGEND_MIN_ROWS:
            zones.append(_zone("legenda", b, W, H, head["text"].rstrip(": "), "read", "vektoriai",
                               f"antraštė „{head['text'][:40]}“ ir {len(rows)} eil. su ženklu"))
        else:
            b = _box(head) if not rows else b
            zones.append(_zone("kita", b, W, H, head["text"].rstrip(": "), "assumed", "teksto_sluoksnis",
                               f"legendos antraštė „{head['text'][:40]}“, bet po ja rasta {len(rows)} eil. su ženklu"))
        taken.append(b)

    # 2. the title block (it may hold a legend found above: zones nest, `zone_at` takes the innermost)
    tb = _title_block(phrases, tables, W, H) if phrases else None
    if tb:
        zones.append(tb)
        x0, y0, x1, y1 = tb["bbox_pct"]
        taken.append((x0 * W, y0 * H, x1 * W, y1 * H))

    # 3. tables (a table whose header row names a legend is a legend)
    for i, t in enumerate(tables):
        if i in legend_tables or _real_table(t, W, H):
            continue
        tb_box = (t["x0"], t["top"], t["x1"], t["bottom"])
        if any(_overlap_share(tb_box, z) > 0.5 for z in taken):
            continue
        if t["filled"] < TABLE_IN_PLAN_FILLED and any(_overlap_share(tb_box, wb) > 0.5 for wb in wall_boxes):
            continue                       # the walls drawn as boxes, with room labels in them (objektas_b p5, p7)
        title = next((ph["text"] for ph in sorted(phrases, key=lambda ph: t["top"] - ph["bottom"])
                      if 0 <= t["top"] - ph["bottom"] <= 3 * ph["h"] and ph["x0"] <= t["x1"] and ph["x1"] >= t["x0"]
                      and ph["n_words"] <= 8 and not _is_number_phrase(ph) and _title_like(ph)), None)
        header_cells = [fold(c) for c in t["first_row"] if str(c or "").strip()]
        if any(LEGEND_HEADING_RE.match(c.rstrip(": ")) or c.startswith("zymejim") for c in header_cells):
            zones.append(_zone("legenda", tb_box, W, H, title or t["header"], "read", "lentele",
                               f"lentelė su stulpeliu „{t['header'][:40]}“, {t['text_rows']} eil."))
        else:
            zones.append(_zone("lentele", tb_box, W, H, title or t["header"], "read", "lentele",
                               f"liniuota lentelė: {t['text_rows']} eil. × {t['cols']} stulp."))
        taken.append(tb_box)

    # 4. plan viewports: groups of walls, widened to their dimension strings
    numbers = [ph for ph in phrases if _is_number_phrase(ph)]
    for g in groups:
        b = g["bounds"]
        grown = b
        for ph in numbers:
            pb = _box(ph)
            if (pb[0] >= b[0] - PLAN_PAD_PT and pb[2] <= b[2] + PLAN_PAD_PT
                    and pb[1] >= b[1] - PLAN_PAD_PT and pb[3] <= b[3] + PLAN_PAD_PT):
                grown = _union(grown, pb)
        label = _plan_label(grown, phrases, H)
        zones.append(_zone("planas", grown, W, H, label, "read", "vektoriai",
                           f"sienų plotas ({g['pieces']} sienų dalys) ir matmenys aplink"))
    plan_boxes = [tuple(v for v in (z["bbox_pct"][0] * W, z["bbox_pct"][1] * H, z["bbox_pct"][2] * W, z["bbox_pct"][3] * H))
                  for z in zones if z["kind"] == "planas"]

    # 5. notes: prose blocks outside everything above (a plan's own labels are not prose blocks)
    for blk in _notes(phrases, taken):
        b = _block_box(blk)
        if any(_inside(b, (p[0] + PLAN_PAD_PT, p[1] + PLAN_PAD_PT, p[2] - PLAN_PAD_PT, p[3] - PLAN_PAD_PT)) for p in plan_boxes):
            continue
        head = next((ph for ph in blk if NOTES_HEADING_RE.match(ph["fold"])), None)
        zones.append(_zone("pastabos", b, W, H, head["text"].split(":")[0] if head else None,
                           "read" if head else "assumed", "teksto_sluoksnis",
                           f"{len(blk)} teksto eil." + (f", antraštė „{head['text'][:30]}“" if head else ", be antraštės")))
        taken.append(b)
    if not zones and not base["detail"]:
        base["detail"] = "lape nerasta nei vektorinių sienų, nei atpažįstamų teksto sričių"
    return {**base, "zones": zones}


def _key(pdf_bytes: bytes, page: int, cap: int) -> tuple[bytes, int, int, int]:
    return (hashlib.blake2b(pdf_bytes, digest_size=16).digest(), int(page), ZONES_VERSION, int(cap))


def read_zones(pdf_bytes: bytes, page: int, *, table_max_objects: int | None = None) -> dict:
    """{page, width_pt, height_pt, rotation, versija, status: ok|no_text|no_page|failed, detail, zones} for a
    1-based page. Cached per PDF digest, page and table cap; never raises. `table_max_objects`: lay out for
    tables only a sheet drawing at most this many objects (default TABLE_MAX_OBJECTS)."""
    if not pdf_bytes or int(page) < 1:
        return {"page": int(page), "width_pt": 0.0, "height_pt": 0.0, "rotation": 0, "versija": ZONES_VERSION,
                "zones": [], "status": "no_page", "detail": "tokio lapo brėžinyje nėra"}
    cap = TABLE_MAX_OBJECTS if table_max_objects is None else int(table_max_objects)
    key = _key(pdf_bytes, page, cap)
    with _cache_lock:
        hit = _cache.get(key)
        if hit is not None:
            _cache.move_to_end(key)
            return copy.deepcopy(hit)
    try:
        res = _detect(pdf_bytes, int(page), cap)
    except Exception as exc:  # noqa: BLE001 — a zone reading never sinks its caller
        log.warning("sheet zones failed on page %s: %r", page, exc)
        return {"page": int(page), "width_pt": 0.0, "height_pt": 0.0, "rotation": 0, "versija": ZONES_VERSION,
                "zones": [], "status": "failed", "detail": "lapo sričių perskaityti nepavyko"}
    with _cache_lock:
        _cache[key] = res
        _cache.move_to_end(key)
        while len(_cache) > _CACHE_MAX:
            _cache.popitem(last=False)
    return copy.deepcopy(res)


def detect_zones(pdf_bytes: bytes, page: int, *, table_max_objects: int | None = None) -> list[dict]:
    """The zones of a 1-based page (see the module docstring). `[]` for a sheet with nothing readable."""
    return list(read_zones(pdf_bytes, page, table_max_objects=table_max_objects)["zones"])


def zones_for_pages(pdf_bytes: bytes, pages: Iterable[int], *, table_max_objects: int | None = None) -> dict[str, list[dict]]:
    """{"<page>": zones} for the given pages — the shape `_meta.zonos` stores."""
    return {str(int(p)): detect_zones(pdf_bytes, int(p), table_max_objects=table_max_objects)
            for p in sorted({int(p) for p in pages if int(p) >= 1})}


_PRIORITY = {"antspaudas": 0, "lentele": 1, "legenda": 2, "pastabos": 3, "kita": 4, "planas": 5}


def sheet_type_from_zones(zones: Sequence[dict]) -> str | None:
    """The €0 sheet type the zones alone can give (Pathon v3 W5-D, D12): "legenda" for a sheet whose only content
    zone is a legend — a legend zone, no plan and no table (a title block, notes or a stray block may stand
    beside it). None otherwise: every other sheet keeps whatever type it has. No model, no prompt."""
    kinds = [str(z.get("kind")) for z in zones or [] if isinstance(z, dict)]
    if "legenda" in kinds and "planas" not in kinds and "lentele" not in kinds:
        return "legenda"
    return None


def zone_at(zones: Sequence[dict], x_pct: float, y_pct: float) -> dict | None:
    """The zone a display-frame point falls in. Where zones overlap, a plan comes last and among the others
    the INNERMOST (smallest) wins — a legend inside the title block's band is the legend."""
    hits = [z for z in zones if z["bbox_pct"][0] <= x_pct <= z["bbox_pct"][2] and z["bbox_pct"][1] <= y_pct <= z["bbox_pct"][3]]

    def order(z):
        x0, y0, x1, y1 = z["bbox_pct"]
        return (z["kind"] == "planas", (x1 - x0) * (y1 - y0), _PRIORITY.get(z["kind"], 9))
    return min(hits, key=order) if hits else None


def zone_to_mediabox_pt(zone: dict, page_size: tuple[float, float], rotation: int) -> list[float]:
    """A zone's display-frame box → [x0, y0, x1, y1] in UNROTATED mediabox points from the top-left — the
    viewer's measurement space (cv_tools `box_pt`). `page_size` is the mediabox (width, height) before
    /Rotate; `rotation` the page's /Rotate. Inverse of cv_match._rotate_pct (mediabox → display)."""
    Wm, Hm = (float(v) for v in page_size)
    rot = int(rotation) % 360
    x0, y0, x1, y1 = (float(v) for v in zone["bbox_pct"])
    xs, ys = [], []
    for dx, dy in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):
        if rot == 90:            # display (1 − y, x) ← mediabox (x, y)
            mx, my = dy, 1 - dx
        elif rot == 180:
            mx, my = 1 - dx, 1 - dy
        elif rot == 270:         # display (y, 1 − x) ← mediabox (x, y)
            mx, my = 1 - dy, dx
        else:
            mx, my = dx, dy
        xs.append(mx * Wm)
        ys.append(my * Hm)
    return [round(min(xs), 2), round(min(ys), 2), round(max(xs), 2), round(max(ys), 2)]


def clear() -> None:
    """Drop the cache (tests)."""
    with _cache_lock:
        _cache.clear()


__all__ = ["KINDS", "NO_TEXT", "ZONES_VERSION", "clear", "detect_zones", "display_frame", "fold", "read_zones",
           "zone_at", "zone_to_mediabox_pt", "zones_for_pages"]
