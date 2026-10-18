"""Tables with a box for every row and every cell — the generic reader under the schedules (Pathon v3, track C).

Until now only the eksplikacija had a table parser that knew where its rows stand (`pdfplumber_eksplikacija`,
`eksplikacija_row_bbox`); the door schedule was read from word positions with no boxes at all, and no other table
(windows, finishes, tiles) was read without a model. This module reads ANY ruled table on a sheet, €0, no model:
pdfplumber `find_tables` (the eksplikacija reader's tool) gives the ruling, and every row and cell keeps its box so
a schedule row can be cropped and shown on the drawing („Rodyti brėžinyje").

The eksplikacija reader's tolerance tricks are reused BY IMPORT, not copied:
  · merged rows — `_split_multiline_row`: pdfplumber returns two table lines drawn without a rule between them as
    one row whose cells hold „D1\\nD2"; split only when every multi-line cell has the same number of lines (a
    wrapped „Dešininės,\\nbeapvadinės" is one cell, not two rows);
  · header text — `_fold_header` (lower case, LT letters folded, punctuation to spaces) for the title row test;
  · numbers — the schedules (extractor/schedules.py) parse cells with `_parse_number_preserving_decimals`.
And the tricks that are this module's own:
  · merged header cells — a header cell drawn across two columns (pdfplumber: the left column holds the box, the
    covered one None) gives its text to both columns; a cell drawn down two header rows is read once;
  · a multi-row header is accepted only with that structural evidence (a merged cell) — a table whose first rows
    are all words (a finish schedule) must not lose its first rooms to the header;
  · a title row ruled inside the table (one cell across the whole width) is the table's title, not a header;
  · ruled pieces — a piece starting within 6 pt under a table with the same column edges continues it (a last
    row ruled apart, objektas_h p2's legend); a piece that repeats the header drops the repeat.

THE FRAME. Every `bbox_pct` and `cell_bboxes` entry here is in the PDFium DISPLAY frame — fractions of the page
AS DISPLAYED (/Rotate applied), origin top-left, y down — the frame of `sheet_zones` zones, room `polygon_pct`
and the evidence crops (api/evidence.py renders with PDFium). The page size comes from `sheet_zones.display_frame`
(PDFium `get_size`), never from where the content lies (the /Rotate 270 trap of objektas_e). pdfplumber's boxes
are in its page frame (pdfminer applies /Rotate); `sheet_zones` measured that frame against PDFium on objektas_a
p6 (/Rotate 270) and synthetic /Rotate 90 / 270 sheets: once the page box origin is subtracted it IS the display
frame, so a box is (x − x_origin) / page.width etc. Tested here at /Rotate 0, 90 and 270.

A sheet without a text layer (a scan) answers `status: "no_text"` and no tables — a raster table is not guessed.
A sheet drawing more objects than the cap is not laid out (`status: "too_heavy"`), and says so.

Table: {table_id, page, bbox_pct, title, header: [str per column], header_rows, cols, pieces,
        rows: [{row_idx, cells: [str], bbox_pct, cell_bboxes: [bbox_pct | None], split}],
        header_cells: [{cells, bbox_pct, cell_bboxes}]}
"""
from __future__ import annotations

import collections
import copy
import hashlib
import io
import logging
import re
import threading
from typing import Iterable

from .pdfplumber_eksplikacija import _fold_header, _split_multiline_row
from .sheet_zones import (_TABLE_WORDS, MIN_TEXT_CHARS, NO_TEXT, TABLE_MAX_OBJECTS, TABLE_MAX_PAGE_SHARE,
                          TABLE_MIN_FILLED, display_frame)

log = logging.getLogger("samatu.table_reader")

TABLES_VERSION = 1
STATUSES = ("ok", "no_text", "no_page", "too_heavy", "failed")
MIN_ROWS = 2                 # a header and one row — a door schedule of one door is a schedule
MIN_COLS = 2
MAX_HEADER_ROWS = 3
PIECE_GAP_PT = 6.0           # a ruled piece starting this close under a table continues it (sheet_zones.LEGEND_TABLE_GAP_PT)
PIECE_EDGE_PT = 2.0          # …when its column edges stand within this of the table's
TITLE_REACH_PT = 18.0        # a title line ends at most this far above the table
TITLE_ROW_SHARE = 0.8        # one cell across this share of the width is a title row
TITLE_MAX = 80
CELL_MAX = 240
_TITLE_WORDS = _TABLE_WORDS          # a line that names a table (sheet_zones: eksplikacija, žiniaraštis, …)
SOUP_TOKENS = 3              # a cell holding this many number tokens is dimension strings caught in a ruled box…
SOUP_SHARE = 0.4             # …and when this share of the filled cells are such, the „table" is a piece of drawing
LINE_PT = 3.0                # words of one line start within this of each other (door_schedule._LINE_PT)
_CACHE_MAX = 64

TOO_HEAVY = "lentelių neieškota — lape per daug brėžinio objektų"
NO_TABLES_TEXT = NO_TEXT + " — lentelės (jei jos yra) nuskenuotos, programa jų perskaityti negali"

# a cell that carries data, not a heading: a number (sizes, areas, counts — „125+15*", „2,10 m"), a code (D-1, L2,
# VD-3) or a room number (01, 1.02)
_NUMBER_CELL_RE = re.compile(r"[-+]?\d[\d\s.,+×x*/-]*(?:\s*(?:m²|m2|m³|m3|mm|cm|m|vnt\.?|kg|l))?", re.IGNORECASE)
_CODE_CELL_RE = re.compile(r"[A-ZĄČĘĖĮŠŲŪŽ]{1,3}\s?[-.]?\s?\d{1,3}[a-zA-Z]?\*?")

_cache: "collections.OrderedDict[tuple, dict]" = collections.OrderedDict()
_cache_lock = threading.Lock()


def _letters(text: str) -> int:
    return sum(ch.isalpha() for ch in text)


def is_data_cell(text: str | None) -> bool:
    """True for a cell that holds a value (a number or a code), False for a heading word or an empty cell."""
    t = " ".join(str(text or "").split())
    if not t:
        return False
    return bool(_NUMBER_CELL_RE.fullmatch(t) or _CODE_CELL_RE.fullmatch(t))


def _clean(text: str | None) -> str:
    return " ".join(str(text or "").split())[:CELL_MAX]
class _Frame:
    """Page points ↔ the table's READING frame ↔ display-frame fractions.

    pdfplumber gives every box in its page frame (= the display frame once the page box origin is subtracted,
    see the module docstring). A table whose text runs sideways on the displayed sheet (a schedule turned on an
    A1 sheet, or a sheet drawn upright under a /Rotate that turns it) is read in its text's own frame — the
    words left to right, the lines downwards — so its rows are the rows a person reads, not the display's
    columns. Every box handed out is turned back into display fractions (`pct`)."""

    def __init__(self, pg, W: float, H: float, direction: str = "right"):
        self.ox, self.oy = float(pg.bbox[0]), float(pg.bbox[1])
        self.pw, self.ph = float(pg.width) or 1.0, float(pg.height) or 1.0
        self.W, self.H = W, H
        self.direction = direction

    def _fwd(self, x: float, y: float) -> tuple[float, float]:
        X, Y = x - self.ox, y - self.oy
        d = self.direction
        if d == "down":          # text advances down the display, lines stack to the left
            return Y, self.pw - X
        if d == "up":            # text advances up, lines stack to the right
            return self.ph - Y, X
        if d == "left":
            return self.pw - X, self.ph - Y
        return X, Y

    def _back(self, u: float, v: float) -> tuple[float, float]:
        d = self.direction
        if d == "down":
            return self.pw - v, u
        if d == "up":
            return v, self.ph - u
        if d == "left":
            return self.pw - u, self.ph - v
        return u, v

    @staticmethod
    def _corners(f, b) -> tuple[float, float, float, float]:
        x0, y0, x1, y1 = (float(v) for v in b)
        pts = [f(x0, y0), f(x1, y1)]
        return (round(min(p[0] for p in pts), 2), round(min(p[1] for p in pts), 2),
                round(max(p[0] for p in pts), 2), round(max(p[1] for p in pts), 2))

    def to_reading(self, b) -> tuple[float, float, float, float]:
        """A page-point box (pdfplumber) → the reading frame."""
        return self._corners(self._fwd, b)

    def pct(self, b) -> list[float]:
        """A reading-frame box → [x0, y0, x1, y1] display fractions."""
        clip = lambda v: min(max(v, 0.0), 1.0)  # noqa: E731
        x0, y0, x1, y1 = self._corners(self._back, b)
        return [round(clip(x0 / self.pw), 5), round(clip(y0 / self.ph), 5),
                round(clip(x1 / self.pw), 5), round(clip(y1 / self.ph), 5)]

    def word(self, w: dict) -> dict:
        x0, top, x1, bottom = self.to_reading((w["x0"], w["top"], w["x1"], w["bottom"]))
        return {**w, "x0": x0, "top": top, "x1": x1, "bottom": bottom}


def text_direction(chars: list[dict], bbox) -> str:
    """Which way the text inside `bbox` (page points) runs on the displayed sheet: right | down | left | up —
    a vote of the characters' own direction (pdfplumber turns their matrix with the page)."""
    x0, top, x1, bottom = bbox
    votes: collections.Counter = collections.Counter()
    for ch in chars:
        cx, cy = (ch["x0"] + ch["x1"]) / 2, (ch["top"] + ch["bottom"]) / 2
        if not (x0 <= cx <= x1 and top <= cy <= bottom) or str(ch.get("text") or "").isspace():
            continue
        m = ch.get("matrix") or (1, 0, 0, 1, 0, 0)
        a, b = float(m[0]), float(m[1])
        if abs(a) >= abs(b):
            votes["right" if a > 0 else "left"] += 1
        else:
            votes["down" if b < 0 else "up"] += 1
    return votes.most_common(1)[0][0] if votes else "right"


def _centre_in(ch: dict, bbox) -> bool:
    cx, cy = (ch["x0"] + ch["x1"]) / 2, (ch["top"] + ch["bottom"]) / 2
    return bbox[0] <= cx <= bbox[2] and bbox[1] <= cy <= bbox[3]


def _reading_char(fr: "_Frame", ch: dict) -> dict:
    x0, top, x1, bottom = fr.to_reading((ch["x0"], ch["top"], ch["x1"], ch["bottom"]))
    return {"text": str(ch.get("text") or ""), "x0": x0, "top": top, "x1": x1, "bottom": bottom}


def _cell_text(chars: list[dict], box) -> str:
    """The text of one cell from characters already in the reading frame: lines top to bottom, characters left to
    right, a space where the gap is wider than a third of the letter height (pdfplumber's x_tolerance spirit)."""
    inside = sorted((c for c in chars if _centre_in(c, box) and c["text"]), key=lambda c: (c["top"], c["x0"]))
    spaces = [c for c in inside if c["text"].isspace()]
    inside = [c for c in inside if not c["text"].isspace()]
    lines: list[list[dict]] = []
    for c in inside:
        h = max(c["bottom"] - c["top"], 1.0)
        if lines and abs(c["top"] - lines[-1][0]["top"]) <= h * 0.5:
            lines[-1].append(c)
        else:
            lines.append([c])
    out = []
    for ln in lines:
        ln.sort(key=lambda c: c["x0"])
        text = ""
        for i, c in enumerate(ln):
            gap_from = ln[i - 1]["x1"] if i else None
            spaced = gap_from is not None and (
                c["x0"] - gap_from > min(3.0, (c["bottom"] - c["top"]) / 3)
                or any(gap_from - 0.5 <= sp["x0"] <= c["x0"] + 0.5 and abs(sp["top"] - c["top"]) <= 3 for sp in spaces))
            if spaced and not text.endswith(" "):
                text += " "
            text += c["text"]
        out.append(text.strip())
    return "\n".join(t for t in out if t)


# ── one ruled piece ─────────────────────────────────────────────────────────


def _piece(t, chars: list[dict], pg, W: float, H: float) -> dict | None:
    """A pdfplumber Table → {bbox, colx, rows: [{cells: [box|None], texts: [str|None], bbox}], frame} with every
    box in the table's READING frame (see `_Frame`); rows and columns are grouped there the way pdfplumber groups
    them (a row = the cells sharing a top, a column = a distinct left edge)."""
    try:
        rows = list(t.rows)
        texts = t.extract() or []
    except Exception:  # noqa: BLE001 — a table pdfplumber cannot extract is no table
        return None
    if not rows or len(rows) != len(texts):
        return None
    text_of: dict[tuple, str | None] = {}
    for r, tx in zip(rows, texts):
        for cell, text in zip(r.cells, list(tx) + [None] * (len(r.cells) - len(tx))):
            if cell is not None:
                text_of[tuple(float(v) for v in cell)] = text
    fr = _Frame(pg, W, H, text_direction(chars, t.bbox))
    cells = [(fr.to_reading(b), txt) for b, txt in text_of.items()]
    inside = [_reading_char(fr, ch) for ch in chars if _centre_in(ch, t.bbox)]
    if fr.direction != "right":
        # pdfplumber orders a cell's characters top to bottom, which reads text running UP the sheet backwards
        # („1D" for „D1"): a sideways table's cells are read again from their characters in the reading frame
        cells = [(box, _cell_text(inside, box)) for box, _ in cells]
    if not cells:
        return None
    colx = sorted({c[0][0] for c in cells})
    by_top: dict[float, dict[float, tuple]] = {}
    for box, txt in cells:
        by_top.setdefault(box[1], {})[box[0]] = (box, txt)
    out_rows = []
    for top in sorted(by_top):
        row = by_top[top]
        boxes = [row.get(x, (None, None))[0] for x in colx]
        present = [b for b in boxes if b is not None]
        out_rows.append({"cells": boxes, "texts": [row.get(x, (None, None))[1] for x in colx],
                         "bbox": (min(b[0] for b in present), min(b[1] for b in present),
                                  max(b[2] for b in present), max(b[3] for b in present))})
    every = [c[0] for c in cells]
    bbox = (min(b[0] for b in every), min(b[1] for b in every), max(b[2] for b in every), max(b[3] for b in every))
    return {"bbox": bbox, "colx": colx, "rows": out_rows, "pieces": 1, "frame": fr, "chars": inside,
            "page_bbox": tuple(float(v) for v in t.bbox)}

def _same_columns(a: dict, b: dict) -> bool:
    if len(a["colx"]) != len(b["colx"]):
        return False
    return all(abs(x - y) <= PIECE_EDGE_PT for x, y in zip(a["colx"], b["colx"]))


def _row_texts(row: dict) -> list[str]:
    return [_clean(t) for t in row["texts"]]


def _join_pieces(pieces: list[dict]) -> list[dict]:
    """A ruled piece starting just under a table, with the same column edges, is the table continued."""
    pieces = sorted(pieces, key=lambda p: (p["bbox"][1], p["bbox"][0]))
    out: list[dict] = []
    for p in pieces:
        host = next((q for q in out if q["frame"].direction == p["frame"].direction
                     and 0 <= p["bbox"][1] - q["bbox"][3] <= PIECE_GAP_PT and _same_columns(q, p)), None)
        if host is None:
            out.append(p)
            continue
        rows = p["rows"]
        if rows and host["rows"] and _row_texts(rows[0]) == _row_texts(host["rows"][0]):
            rows = rows[1:]                                    # the header drawn again over the continued piece
        host["rows"] = host["rows"] + rows
        b, c = host["bbox"], p["bbox"]
        host["bbox"] = (min(b[0], c[0]), min(b[1], c[1]), max(b[2], c[2]), max(b[3], c[3]))
        host["pieces"] += 1
        host["chars"] = host["chars"] + p["chars"]
    return out


def _real(p: dict, pw: float, ph: float) -> str | None:
    """None when the piece is a table worth reading, else why not (the report script prints it)."""
    x0, top, x1, bottom = p["bbox"]
    if (x1 - x0) * (bottom - top) >= TABLE_MAX_PAGE_SHARE * pw * ph:
        return "lapo rėmelis"
    n_rows = sum(1 for r in p["rows"] if any(_clean(t) for t in r["texts"]))
    if n_rows < MIN_ROWS or len(p["colx"]) < MIN_COLS:
        return "per mažai eilučių ar stulpelių"
    cells = [_clean(t) for r in p["rows"] for t, c in zip(r["texts"], r["cells"]) if c is not None]
    if not cells or sum(1 for c in cells if c) / len(cells) < TABLE_MIN_FILLED:
        return "langeliuose beveik nėra teksto"
    if not any(_letters(c) >= 3 for c in cells):
        return "jokiame langelyje nėra žodžio — tai matmenys sienų tinklelyje"
    filled = [c for c in cells if c]
    soup = sum(1 for c in filled if sum(1 for tok in c.split() if _numeric_token(tok)) >= SOUP_TOKENS)
    if soup >= SOUP_SHARE * len(filled):
        return "langeliuose — brėžinio matmenų skaičiai, ne lentelės įrašai"
    return None


def _numeric_token(tok: str) -> bool:
    digits = sum(ch.isdigit() for ch in tok)
    return digits > 0 and digits >= 0.5 * len(tok)


# ── header, title, rows ─────────────────────────────────────────────────────


def _col_centres(p: dict) -> list[float]:
    """The x the columns start at, and where each one ends (the next start or the table's right edge)."""
    xs = p["colx"]
    ends = xs[1:] + [p["bbox"][2]]
    return [(a + b) / 2 for a, b in zip(xs, ends)]


def _owner_text(p: dict, r: int, c: int) -> str:
    """The text of the cell that covers column c of row r: its own, a cell drawn across from the left, or one
    drawn down from a header row above."""
    row = p["rows"][r]
    if c < len(row["cells"]) and row["cells"][c] is not None:
        return _clean(row["texts"][c])
    centre = _col_centres(p)[c] if c < len(p["colx"]) else None
    if centre is None:
        return ""
    for k in range(c - 1, -1, -1):
        cell = row["cells"][k] if k < len(row["cells"]) else None
        if cell is not None:
            return _clean(row["texts"][k]) if float(cell[2]) > centre else ""
    for up in range(r - 1, -1, -1):
        cell = p["rows"][up]["cells"][c] if c < len(p["rows"][up]["cells"]) else None
        if cell is not None:
            return _clean(p["rows"][up]["texts"][c]) if float(cell[3]) > row["bbox"][1] + 1 else ""
    return ""


def _is_title_row(p: dict, r: int) -> bool:
    row = p["rows"][r]
    present = [(cell, t) for cell, t in zip(row["cells"], row["texts"]) if cell is not None and _clean(t)]
    width = p["bbox"][2] - p["bbox"][0]
    return (len(p["colx"]) >= 2 and len(present) == 1 and width > 0
            and (float(present[0][0][2]) - float(present[0][0][0])) >= TITLE_ROW_SHARE * width)


def _merged(p: dict, r: int) -> bool:
    """Row r has a cell drawn across columns, or a column covered from the row above — the evidence that the
    header goes on below it."""
    return any(cell is None for cell in p["rows"][r]["cells"])


def _lines_of(chars: list[dict], box) -> list[list[dict]]:
    inside = sorted((c for c in chars if _centre_in(c, box) and c["text"].strip()), key=lambda c: (c["top"], c["x0"]))
    lines: list[list[dict]] = []
    for c in inside:
        if lines and abs(c["top"] - lines[-1][0]["top"]) <= max(c["bottom"] - c["top"], 1.0) * 0.5:
            lines[-1].append(c)
        else:
            lines.append([c])
    return lines


def _band(chars: list[dict]) -> tuple[float, float, float, float]:
    return (min(c["x0"] for c in chars) - 1, min(c["top"] for c in chars) - 1,
            max(c["x1"] for c in chars) + 1, max(c["bottom"] for c in chars) + 1)


def _line_text(p: dict, line: list[dict]) -> str:
    """One line of characters as text, the spaces the PDF wrote kept."""
    band = _band(line)
    spaces = [c for c in p["chars"] if c["text"].isspace() and _centre_in(c, band)]
    return " ".join(_cell_text(line + spaces, band).split())


def _title_row_header(p: dict, r: int) -> tuple[str | None, list[str] | None, list[dict]]:
    """A first row drawn as ONE cell across the table, read line by line:
      · a first line that names a table („PATALPŲ EKSPLIKACIJA", „DURŲ ŽINIARAŠTIS") or does not spread over the
        columns is the title;
      · lines whose words stand over two or more columns, none a value, are the header (objektas_h: „Nr. PATALPA
        m2" under the title, no rule between them; objektas_b p1: the header itself is that first line);
      · lines carrying values are data rows written in the same cell (objektas_b p1: rooms 01–05 under the header,
        ruled off only from room 06 on) — each a row with the box of its own line.
    Returns (title, header per column or None, data rows)."""
    row = p["rows"][r]
    whole = next(_clean(t) for t in row["texts"] if _clean(t))
    cell = next(c for c, t in zip(row["cells"], row["texts"]) if c is not None and _clean(t))
    lines = _lines_of(p["chars"], cell)
    if len(lines) < 2:
        return whole, None, []
    ends = p["colx"][1:] + [p["bbox"][2]]

    def parts(ln: list[dict]) -> list[str]:
        out = []
        for a, b in zip(p["colx"], ends):
            part = [c for c in ln if a <= (c["x0"] + c["x1"]) / 2 < b]
            out.append(_line_text(p, part) if part else "")
        return out

    title = None
    first = 0
    p0 = parts(lines[0])
    if _TITLE_WORDS.search(_fold_header(_line_text(p, lines[0]))) or sum(1 for x in p0 if x) < 2:
        title = _line_text(p, lines[0]) or whole
        first = 1
    cols = [""] * len(p["colx"])
    k = first
    while k < len(lines):
        ps = parts(lines[k])
        if any(is_data_cell(x) for x in ps) or sum(1 for x in ps if x) < 2:
            break
        cols = [f"{a} {b}".strip() for a, b in zip(cols, ps)]
        k += 1
    header = cols if sum(1 for c in cols if c) >= 2 else None
    data = []
    for ln in lines[k:]:
        ps = parts(ln)
        if not any(ps):
            continue
        band = _band(ln)
        y0, y1 = max(cell[1], band[1]), min(cell[3], band[3])
        boxes = [(a, y0, b, y1) for a, b in zip(p["colx"], ends)]
        data.append({"texts": ps, "bbox": (p["bbox"][0], y0, p["bbox"][2], y1), "cells": boxes, "split": True})
    if header is None and not data:
        return whole, None, []
    return title, header, data


def _header_split(p: dict) -> tuple[str | None, int, int, list[str] | None, list[dict]]:
    """(title row text, index of the first header row, number of header rows, the header written inside the
    title row or None, data rows written inside the title row)."""
    rows = p["rows"]
    start = 0
    while start < len(rows) and not any(_clean(t) for t in rows[start]["texts"]):
        start += 1
    title = None
    inline = None
    extra: list[dict] = []
    if start < len(rows) and _is_title_row(p, start):
        title, inline, extra = _title_row_header(p, start)
        start += 1
    n = 0
    for r in range(start, start if extra else min(len(rows), start + MAX_HEADER_ROWS)):
        texts = _row_texts(rows[r])
        if not any(texts) or any(is_data_cell(t) for t in texts):
            break
        if n >= 1 and not _merged(p, r - 1) and not _merged(p, r):
            break                                              # a second all-words row with no merged cell is data
        n += 1
    return title, start, n, inline, extra


def _header(p: dict, first: int, n: int) -> list[str]:
    out = []
    for c in range(len(p["colx"])):
        parts: list[str] = []
        for r in range(first, first + n):
            t = _owner_text(p, r, c)
            if t and t not in parts:
                parts.append(t)
        out.append(" ".join(parts))
    return out


def _words(pg) -> list[dict]:
    try:
        return pg.extract_words(keep_blank_chars=False, use_text_flow=False, x_tolerance=2, y_tolerance=3) or []
    except Exception:  # noqa: BLE001
        return []


def _lines_in(words: list[dict], box) -> list[tuple[float, float]]:
    """(top, bottom) of each text line whose words stand inside `box` (page points)."""
    x0, top, x1, bottom = box
    inside = sorted((w for w in words if w["x0"] >= x0 - 1 and w["x1"] <= x1 + 1
                     and w["top"] >= top - 1 and w["bottom"] <= bottom + 1), key=lambda w: w["top"])
    lines: list[list[dict]] = []
    for w in inside:
        if lines and w["top"] - lines[-1][0]["top"] <= LINE_PT:
            lines[-1].append(w)
        else:
            lines.append([w])
    return [(min(w["top"] for w in ln), max(w["bottom"] for w in ln)) for ln in lines]


def _title_above(chars: list[dict], box) -> str | None:
    """The line written just above the table, across its width — „DURŲ ŽINIARAŠTIS" (characters in the reading
    frame, so a sideways table's title reads the right way round)."""
    x0, top, x1, _ = box
    near = [c for c in chars if top - TITLE_REACH_PT <= c["bottom"] <= top + 1.0 and c["top"] < top
            and c["x1"] >= x0 - 2 and c["x0"] <= x1 + 2 and c["text"]]
    if not near:
        return None
    if not any(c["text"].strip() for c in near):
        return None
    lowest = max(c["top"] for c in near if c["text"].strip())
    line = [c for c in near if abs(lowest - c["top"]) <= LINE_PT]
    band = (min(c["x0"] for c in line) - 1, min(c["top"] for c in line) - 1,
            max(c["x1"] for c in line) + 1, max(c["bottom"] for c in line) + 1)
    text = " ".join(_cell_text(line, band).split())
    letters = [ch for ch in text if ch.isalpha()]
    upper = sum(ch.isupper() for ch in letters) / len(letters) if letters else 0.0
    # a title names a table or is written in capitals — a drawing's note that happens to stand above the table
    # („Mazgas iš viršaus", objektas_b p1) is not its title
    if not (_TITLE_WORDS.search(_fold_header(text)) or (upper >= 0.8 and len(text.split()) <= 8)):
        return None
    return text[:TITLE_MAX] or None


def _split_rows(p: dict, r: int, words_of) -> list[dict]:
    """Row r as one or more data rows — two lines drawn without a rule between them are two rows, each with the
    box of its own text line when the lines can be told apart."""
    row = p["rows"][r]
    texts = [t if isinstance(t, str) else "" for t in row["texts"]]
    counts = [len([ln for ln in t.split("\n") if ln.strip()]) for t in texts]
    multi = [n for n in counts if n > 1]
    one = [{"texts": [_clean(t) for t in texts], "bbox": row["bbox"], "cells": row["cells"], "split": False}]
    if len(multi) < 2 or len(set(multi)) != 1:
        return one
    subs = _split_multiline_row(texts)
    if len(subs) <= 1:
        return one
    lines = _lines_in(words_of(), row["bbox"])
    if len(lines) != len(subs):
        # the lines cannot be told apart in the text layer: every sub-row keeps the drawn row's box
        return [{"texts": [_clean(t) for t in s], "bbox": row["bbox"], "cells": row["cells"], "split": "be_vietos"}
                for s in subs]
    out = []
    for s, (top, bottom) in zip(subs, lines):
        y0, y1 = max(row["bbox"][1], top - 1.0), min(row["bbox"][3], bottom + 1.0)
        cells = [None if c is None else (c[0], y0, c[2], y1) for c in row["cells"]]
        out.append({"texts": [_clean(t) for t in s], "bbox": (row["bbox"][0], y0, row["bbox"][2], y1), "cells": cells,
                    "split": True})
    return out


def _table(p: dict, page: int, k: int, words_of, chars: list[dict]) -> dict:
    fr: _Frame = p["frame"]
    reading_words: list[list[dict]] = []

    def words() -> list[dict]:                       # the sheet's words in this table's reading frame
        if not reading_words:
            reading_words.append([fr.word(w) for w in words_of()])
        return reading_words[0]

    title_row, first, n, inline, inline_rows = _header_split(p)
    header = _header(p, first, n) if n else []
    if inline:
        header = [" ".join(x for x in (a, b) if x) for a, b in zip(inline, header or [""] * len(inline))]
    title = title_row or _title_above([_reading_char(fr, ch) for ch in chars], p["bbox"])
    rows = []
    header_cells = []
    for r in range(first, first + n):
        row = p["rows"][r]
        header_cells.append({"cells": _row_texts(row), "bbox_pct": fr.pct(row["bbox"]),
                             "cell_bboxes": [None if c is None else fr.pct(c) for c in row["cells"]]})
    def subs():
        yield from inline_rows                       # rows written inside the title cell come first
        for r in range(first + n, len(p["rows"])):
            yield from _split_rows(p, r, words)

    for sub in subs():
        if not any(sub["texts"]):
            continue
        rows.append({"row_idx": len(rows), "cells": sub["texts"], "bbox_pct": fr.pct(sub["bbox"]),
                     "cell_bboxes": [None if c is None else fr.pct(c) for c in sub["cells"]],
                     "split": sub["split"]})
    return {"table_id": f"p{page}-t{k}", "page": int(page), "bbox_pct": fr.pct(p["bbox"]), "title": title,
            "header": header, "header_fold": [_fold_header(h) for h in header], "header_rows": n,
            "cols": len(p["colx"]), "pieces": p["pieces"], "text_direction": fr.direction, "rows": rows,
            "header_cells": header_cells}


# ── the page ────────────────────────────────────────────────────────────────


def _base(page: int) -> dict:
    return {"page": int(page), "versija": TABLES_VERSION, "status": "ok", "detail": None,
            "width_pt": 0.0, "height_pt": 0.0, "rotation": 0, "tables": [], "skipped": []}


def _read(doc, pdf_bytes: bytes, page: int, cap: int) -> dict:
    out = _base(page)
    frame = display_frame(pdf_bytes, page)
    if frame is None or frame[0] <= 0 or frame[1] <= 0 or not (1 <= page <= len(doc.pages)):
        return {**out, "status": "no_page", "detail": "tokio lapo brėžinyje nėra"}
    W, H, rotation, n_objects = frame
    out.update(width_pt=W, height_pt=H, rotation=rotation)
    if n_objects > cap:
        return {**out, "status": "too_heavy", "detail": f"{TOO_HEAVY} ({n_objects})"}
    pg = doc.pages[page - 1]
    try:
        n_chars = sum(1 for c in (pg.chars or []) if not str(c.get("text") or "").isspace())
        if n_chars < MIN_TEXT_CHARS:
            return {**out, "status": "no_text", "detail": NO_TABLES_TEXT}
        words_cache: list[list[dict]] = []

        def words_of() -> list[dict]:
            if not words_cache:
                words_cache.append(_words(pg))
            return words_cache[0]

        chars = list(pg.chars or [])
        pieces = [pc for pc in (_piece(t, chars, pg, W, H) for t in (pg.find_tables() or [])) if pc]
        k = 0
        for p in _join_pieces(pieces):
            why = _real(p, p["frame"].pw, p["frame"].ph)
            if why:
                out["skipped"].append({"bbox_pct": p["frame"].pct(p["bbox"]), "reason": why})
                continue
            k += 1
            out["tables"].append(_table(p, page, k, words_of, chars))
    finally:
        try:
            pg.close()
        except Exception:  # noqa: BLE001
            pass
    return out


def _key(digest: bytes, page: int, cap: int) -> tuple:
    return (digest, int(page), TABLES_VERSION, int(cap))


def read_pages_tables(pdf_bytes: bytes, pages: Iterable[int], *, max_objects: int | None = None) -> dict[int, dict]:
    """{page: read_page_tables(...)} for several 1-based pages, the PDF opened once. Never raises."""
    cap = TABLE_MAX_OBJECTS if max_objects is None else int(max_objects)
    want = sorted({int(p) for p in pages if int(p) >= 1})
    digest = hashlib.blake2b(pdf_bytes, digest_size=16).digest()
    result: dict[int, dict] = {}
    todo = []
    for p in want:
        with _cache_lock:
            hit = _cache.get(_key(digest, p, cap))
            if hit is not None:
                _cache.move_to_end(_key(digest, p, cap))
                result[p] = copy.deepcopy(hit)
                continue
        todo.append(p)
    if not todo:
        return result
    try:
        from . import pdf_page_cache  # noqa: F401 — installs the lazy pdfminer debug log (53 s → 1 s per open)
        import pdfplumber
    except ImportError:
        return {**result, **{p: {**_base(p), "status": "failed", "detail": "lentelių skaitymas neįdiegtas"} for p in todo}}
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as doc:
            for p in todo:
                try:
                    res = _read(doc, pdf_bytes, p, cap)
                except Exception as exc:  # noqa: BLE001 — a page we cannot lay out has no tables we can read
                    log.warning("table reader failed on page %s: %r", p, exc)
                    res = {**_base(p), "status": "failed", "detail": "lapo lentelių perskaityti nepavyko"}
                    result[p] = res
                    continue
                with _cache_lock:
                    _cache[_key(digest, p, cap)] = res
                    _cache.move_to_end(_key(digest, p, cap))
                    while len(_cache) > _CACHE_MAX:
                        _cache.popitem(last=False)
                result[p] = copy.deepcopy(res)
    except Exception as exc:  # noqa: BLE001 — an unreadable PDF has no tables
        log.warning("table reader could not open the PDF: %r", exc)
        for p in todo:
            result.setdefault(p, {**_base(p), "status": "failed", "detail": "brėžinio atidaryti nepavyko"})
    return result


def read_page_tables(pdf_bytes: bytes, page: int, *, max_objects: int | None = None) -> dict:
    """{page, versija, status: ok|no_text|no_page|too_heavy|failed, detail, width_pt, height_pt, rotation,
    tables: [table…], skipped: [{bbox_pct, reason}]} of a 1-based page (see the module docstring for the table
    shape and the frame). Cached per PDF digest, page and object cap; never raises."""
    if not pdf_bytes or int(page) < 1:
        return {**_base(int(page)), "status": "no_page", "detail": "tokio lapo brėžinyje nėra"}
    return read_pages_tables(pdf_bytes, [int(page)], max_objects=max_objects)[int(page)]


def read_tables(pdf_bytes: bytes, page: int, *, max_objects: int | None = None) -> list[dict]:
    """The ruled tables of a 1-based page: [{table_id, bbox_pct, header: [str], rows: [{cells: [str], bbox_pct,
    cell_bboxes}]}, …] (plus title, header_rows, cols, pieces, page) — boxes in the PDFium DISPLAY frame. `[]` for
    a sheet without a text layer, a heavy sheet, or no ruled table; `read_page_tables` says which."""
    return list(read_page_tables(pdf_bytes, page, max_objects=max_objects)["tables"])


def clear() -> None:
    """Drop the cache (tests)."""
    with _cache_lock:
        _cache.clear()


__all__ = ["STATUSES", "TABLES_VERSION", "clear", "is_data_cell", "read_page_tables", "read_pages_tables",
           "read_tables"]
