"""Plan-area annotations — the designer's own room areas written on the plan.

WHY (2026-09-06, item 3 of the €0 generalisation work). A project with no
patalpų eksplikacija table (objektas_g) leaves the rooms to Vision alone, and
Vision invented a third bathroom there (5,64 m² — its own tiles, paint and one
of every fixture). But the same drawing carries the designer's room areas as
TEXT on the lubų planas („37.86 m²" standing alone inside each room), and a
text layer is read exactly, deterministically and for free. This lane turns
those labels into the table the drawing does not print:

  · a Vision room whose area matches a label within ±3 % is CONFIRMED;
  · a room within ±20 % of one unclaimed label ADOPTS the label's value (the
    Vision figure is kept beside it for the check sheet);
  · a room no label supports is FLAGGED — never deleted (evidence-first: the
    contractor sees „ploto užrašo plane neradau" and decides), and
  · the labels' sum anchors the ceiling quantity, so an invented room cannot
    move it (founder rule: „lubos visada kaip iš eksplikacijos").

WHAT IS A ROOM AREA LABEL. A number with one or two decimals followed by
„m²"/„m2" that stands ALONE — no words within one text line above or below
it. A label in a block of words is something else: „laminuota grindų danga
76.65 m²" is a material total, „6vnt. / 3.70 m²" a tile-count label, and a
table row („02. San. mazgas 4.00 m²") belongs to the table lane. Characters
are read individually and re-joined, because CAD exports often space digits so
that `extract_words` breaks „7.25" into four one-character words.

The module is pure: bytes in, dicts out. No model call, no network. The text
layer is read with pypdfium2 (already a dependency, Apache/BSD) — pdfplumber
needs a minute per page on a 20 MB drawing because pdfminer parses the object
streams the renders live in; PDFium reads the same three pages in 0.1 s.
Character boxes are converted into pdfplumber's display frame (points from the
top-left, /Rotate applied) so the crops use the same plain division as the
eksplikacija row. pdfplumber remains the fallback when pypdfium2 is missing.
"""
from __future__ import annotations

import re
from collections import Counter
from io import BytesIO
from typing import Any, Iterable, Sequence

__all__ = [
    "CONFIRM_TOL", "ADOPT_TOL", "MIN_CANDIDATES", "SOURCE_LABEL",
    "read_area_annotations", "reconcile_rooms_with_annotations",
    "plan_pages_from_classification", "text_pages_from_classification",
    "most_common_page", "read_author_figures", "scan_text_layer", "lane_warnings",
    "read_height_statements", "apply_height_statements", "HEIGHT_SOURCE",
]

CONFIRM_TOL = 0.03      # a Vision area this close to a label IS that label
ADOPT_TOL = 0.20        # this close to one unclaimed label → take the label's value
FRAME_ADOPT_TOL = 0.25  # a label inside the room's outline is its area this close — or when the words beside it name the room
MIN_CANDIDATES = 3      # fewer standalone labels than this is not „the table"
SOURCE_LABEL = "plano_uzrasas"   # plotas_saltinis written by this lane

_NUM_CHARS = set("0123456789.,")
_AREA_RE = re.compile(r"^\d{1,3}[.,]\d{1,2}$")
_UNIT_RE = re.compile(r"^m[²2],?$")
_WORDY_RE = re.compile(r"[A-Za-zĄČĘĖĮŠŲŪŽąčęėįšųūž]{3,}|\d+\s*vnt", re.IGNORECASE)
# Words that make a nearby „N.NN m²" a material total, a count label or a
# building total — NOT a room. A room NAME next to the number („Miegamasis /
# 14.26 m²", the commonest convention) leaves it a room label; the name is
# kept as context. Matched as lower-cased, diacritics-folded prefixes.
_NOT_A_ROOM_WORDS = (
    "vnt", "danga", "dang", "laminat", "parket", "plytel", "akmens", "vinil",
    "kilim", "linoleum", "daz", "glaist", "tink", "grunt", "tapet", "medziag",
    "sien", "grind", "lub", "bendr", "viso", "suma", "naudingas", "gyvenam",
    "kaina", "eur", "spalv", "ral", "ncs", "storis", "pakuot", "kiek",
)
_PLAN_TYPES = {"floor_plan", "ceiling_plan"}

_CHAR_GAP_PT = 7.0      # digits further apart than this are two numbers (cap; see _gap_limit)
_CHAR_OVERLAP_PT = 1.0  # float rounding / kerning may put x0 a hair before the previous x1
_BASELINE_PT = 2.5      # same text line
_UNIT_GAP_PT = 14.0     # „m²" sits this close to the right of its number
_NEIGHBOUR_PT = 16.0    # one text line above / below
_NEIGHBOUR_X_PT = 30.0  # horizontal reach of the label block
_DUP_VIEW_SHARE = 0.6   # a page whose labels mostly repeat an accepted page's is the same rooms drawn again
_SHARED_FRAME_SHARE = 0.6   # this share of labels inside SOME room outline ⇒ the sheets share a frame

_FOLD = str.maketrans("ąčęėįšųūžĄČĘĖĮŠŲŪŽ", "aceeisuuzACEEISUUZ")


def _fold(text: str) -> str:
    return str(text or "").translate(_FOLD).lower()


def _is_not_a_room_word(word: str) -> bool:
    w = _fold(word).strip(".,:;()")
    return any(w.startswith(pref) or (pref == "vnt" and "vnt" in w) for pref in _NOT_A_ROOM_WORDS)


def _f(v: Any) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f else None


def plan_pages_from_classification(puslapiai: Sequence[dict] | None) -> list[int]:
    """1-based page numbers the main pass classified as a floor or ceiling plan.
    Empty when nothing is classified — the caller then reads every page."""
    out: list[int] = []
    for p in puslapiai or []:
        if not isinstance(p, dict):
            continue
        tipas = str(p.get("tipas") or p.get("type") or "").strip().lower()
        nr = _f(p.get("page") or p.get("nr") or p.get("puslapis"))
        if tipas in _PLAN_TYPES and nr:
            out.append(int(nr))
    return sorted(set(out))


def _gap_limit(size: float) -> float:
    """How far apart two digits of ONE number may sit: up to 0.8 em, capped."""
    return max(2.0, min(_CHAR_GAP_PT, 0.8 * float(size or 0)))


def _lines(chars: list[dict]) -> list[list[dict]]:
    """Chars clustered into text lines (same baseline within _BASELINE_PT),
    each line sorted left to right. A sweep, not a rounding bucket — two chars
    of one word must never land in different lines because they straddle a
    bucket boundary."""
    out: list[list[dict]] = []
    for c in sorted(chars, key=lambda c: float(c["top"])):
        if out and abs(float(c["top"]) - float(out[-1][0]["top"])) <= _BASELINE_PT:
            out[-1].append(c)
        else:
            out.append([c])
    for line in out:
        line.sort(key=lambda c: float(c["x0"]))
    return out


def _words(chars: list[dict]) -> list[dict]:
    """Words rebuilt from characters: a new word at a space, or at a gap wider
    than 0.3 em (min 1 pt). Same shape as pdfplumber's `extract_words` items."""
    out: list[dict] = []
    for line in _lines(chars):
        cur: dict | None = None
        for c in line:
            t = c["text"]
            size = float(c.get("size") or 0)
            if t.isspace():
                cur = None
                continue
            if cur is not None and float(c["x0"]) - cur["x1"] <= max(1.0, 0.3 * size):
                cur["text"] += t
                cur["x1"] = max(cur["x1"], float(c["x1"]))
                cur["top"] = min(cur["top"], float(c["top"]))
                cur["bottom"] = max(cur["bottom"], float(c["bottom"]))
                continue
            cur = {"text": t, "x0": float(c["x0"]), "x1": float(c["x1"]),
                   "top": float(c["top"]), "bottom": float(c["bottom"])}
            out.append(cur)
    return out


def _number_runs(chars: list[dict]) -> list[dict]:
    """Numbers rebuilt from single characters on one text line.

    `extract_words` may split a character-spaced „7.25" into four words; the
    characters themselves are always there. Digit/./, characters that follow
    each other on one line within _gap_limit are one number. A letter closes
    the run (so „3.52m2" is 3.52 and a stray 2); a space is neutral — the gap
    rule decides, because CAD exports sometimes pad digits with spaces."""
    runs: list[dict] = []
    for line in _lines(chars):
        cur: dict | None = None
        for c in line:
            t = c["text"]
            if t.isspace():
                continue
            if t not in _NUM_CHARS:
                cur = None
                continue
            x0, x1, top, bottom = (float(c["x0"]), float(c["x1"]), float(c["top"]), float(c["bottom"]))
            size = float(c.get("size") or 0)
            if cur is not None and -_CHAR_OVERLAP_PT <= x0 - cur["x1"] <= _gap_limit(cur["size"] or size):
                cur["text"] += t
                cur["x1"] = max(cur["x1"], x1)
                cur["bottom"] = max(cur["bottom"], bottom)
                continue
            cur = {"text": t, "x0": x0, "x1": x1, "top": top, "bottom": bottom, "size": size}
            runs.append(cur)
    return [r for r in runs if _AREA_RE.match(r["text"])]


# ── the text layer, one page at a time ───────────────────────────────────────

_TWO_PI = 6.283185307179586


def _identity(bbox):
    return list(bbox)


def _quarter_turn(angle_rad: float) -> int:
    """0, 1, 2 or 3 quarter turns counter-clockwise — the direction the text reads."""
    return int(round((float(angle_rad) % _TWO_PI) / (_TWO_PI / 4))) % 4


def _turn_box(box: list[float], k: int, W: float, H: float) -> list[float]:
    """A top-origin box turned by `k` quarter turns CLOCKWISE on a W×H page
    (the sheet is physically turned so text drawn at k·90° CCW reads left to
    right). k=1: (x, y) → (H − y, x); k=2: (W − x, H − y); k=3: (y, W − x)."""
    x0, top, x1, bottom = (float(v) for v in box)
    pts = [(x0, top), (x1, top), (x0, bottom), (x1, bottom)]
    if k == 1:
        pts = [(H - y, x) for x, y in pts]
    elif k == 2:
        pts = [(W - x, H - y) for x, y in pts]
    elif k == 3:
        pts = [(y, W - x) for x, y in pts]
    xs = [q[0] for q in pts]
    ys = [q[1] for q in pts]
    return [min(xs), min(ys), max(xs), max(ys)]


def _iter_pages_pdfium(pdf_bytes: bytes, wanted: set[int] | None):
    """`_iter_pages_pdfium_unlocked`, read in full under the process-wide PDFium
    lock and yielded afterwards — a generator must not hold the lock across a
    `yield` (pdfium_guard)."""
    from .pdfium_guard import PDFIUM_LOCK
    with PDFIUM_LOCK:
        items = list(_iter_pages_pdfium_unlocked(pdf_bytes, wanted))
    yield from items


def _iter_pages_pdfium_unlocked(pdf_bytes: bytes, wanted: set[int] | None):
    """Chars are analysed in a frame where the sheet's text reads left to
    right; `to_display` maps a finished bbox into the display frame (/Rotate
    applied, points from the top-left — what pdf2image renders and the crops
    use).

    Two rotations are undone, in order: the page's /Rotate, and the DRAWING's
    own turn — CAD exports often place a landscape sheet turned 90° inside a
    portrait page with no /Rotate at all (objektas_a's grindų planas: every
    character at π/2). Each text direction with real text is analysed in its
    own frame (one item yielded per direction), so a plan's vertical dimension
    strings neither outvote its horizontal labels nor pollute them. Character
    size is the box height in that frame, not the font's nominal size, which
    PDFium reports before the drawing's scale."""
    import pypdfium2 as pdfium
    import pypdfium2.raw as C

    from .pdf_vectors import check_content_frame, page_frames

    doc = pdfium.PdfDocument(pdf_bytes)
    try:
        for idx in range(len(doc)):
            pn = idx + 1
            if wanted and pn not in wanted:
                continue
            page = doc[idx]
            tp = None
            try:
                # The character boxes live in the page BEFORE /Rotate (W×H);
                # `get_size` is the page as displayed (Wd×Hd), and `to_display`
                # turns the boxes into it (pdf_vectors.page_frames). objektas_a's
                # /Rotate 270 sheets: displayed 1191×842, boxes up to y = 945 of
                # 842×1191 (2026-09-10). The boxes no longer settle the frame:
                # on objektas_e's turned sheets they stay inside the short side,
                # fit both frames, and the guess put 17 sheets' text elsewhere.
                W, H, Wd, Hd, rotation = page_frames(page)
                tp = page.get_textpage()
                n = tp.count_chars()
                boxes: list[tuple[str, tuple[float, float, float, float], int]] = []
                turns = [0, 0, 0, 0]
                for i in range(n):
                    t = tp.get_text_range(i, 1)
                    if not t or t in ("\r", "\n") or (len(t) == 1 and ord(t) < 32):
                        continue                      # PDFium's synthetic line breaks
                    k = _quarter_turn(C.FPDFText_GetCharAngle(tp, i))
                    boxes.append((t, tp.get_charbox(i, loose=True), k))   # advance box: one top/bottom per line, like pdfplumber
                    if not t.isspace():
                        turns[k] += 1
                check_content_frame(W, H, max((bx[2] for _, bx, _ in boxes), default=0.0),
                                    max((bx[3] for _, bx, _ in boxes), default=0.0), "text", pn)
                raw: list[tuple[str, list[float], int]] = []
                for t, (l, b, r, tt), k in boxes:
                    raw.append((t, [l, H - tt, r, H - b], k))
                # Every direction with real text is analysed in ITS OWN frame — a
                # plan full of vertical dimension strings must not outvote its
                # horizontal room labels, and a drawing turned 90° on the page must
                # not lose its legend to a horizontal title block. A character
                # belongs to exactly one direction, so nothing is read twice.
                for k in sorted(range(4), key=lambda k: (k != 0, -turns[k])):
                    if turns[k] < 8:
                        continue
                    # PDFium's angle grows CLOCKWISE on the page as displayed: 3π/2 is
                    # text reading upward (a sheet turned counter-clockwise), which
                    # needs one CLOCKWISE quarter turn to read left to right — hence 4−k.
                    tk = (4 - k) % 4
                    Wa, Ha = (H, W) if tk in (1, 3) else (W, H)
                    chars: list[dict] = []
                    for t, box, kk in raw:
                        if kk != k:
                            continue
                        x0, top, x1, bottom = _turn_box(box, tk, W, H) if tk else box
                        chars.append({"text": t, "x0": x0, "x1": x1, "top": top, "bottom": bottom,
                                      "size": max(bottom - top, 1.0)})

                    def to_display(bbox, tk=tk, rot=rotation, W=W, H=H, Wa=Wa, Ha=Ha):
                        box = list(bbox)
                        if tk:
                            # undo the analysis turn (tk clockwise → 4−tk clockwise on the turned page)
                            box = _turn_box(box, (4 - tk) % 4, Wa, Ha)
                        if rot:
                            box = _turn_box(box, (rot // 90) % 4, W, H)
                        return box
                    yield pn, Wd, Hd, chars, (to_display if (tk or rotation) else _identity)
            finally:
                try:
                    if tp is not None:
                        tp.close()
                except Exception:  # noqa: BLE001
                    pass
                page.close()
    finally:
        doc.close()


def _iter_pages_pdfplumber(pdf_bytes: bytes, wanted: set[int] | None):
    """Fallback without pypdfium2. Rotated sheets are read as pdfplumber lays
    them out (vertical text on a /Rotate 90 page) — a known limitation."""
    import pdfplumber

    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        for pn, page in enumerate(pdf.pages, 1):
            if wanted and pn not in wanted:
                continue
            try:
                chars = [{"text": c["text"], "x0": float(c["x0"]), "x1": float(c["x1"]),
                          "top": float(c["top"]), "bottom": float(c["bottom"]),
                          "size": float(c.get("size") or 0)}
                         for c in (page.chars or [])
                         if isinstance(c.get("text"), str) and c["text"] and c.get("upright", True)]
            except Exception:  # noqa: BLE001 — a broken page is not a lane failure
                continue
            yield pn, float(page.width), float(page.height), chars, _identity


def _iter_pages(pdf_bytes: bytes, pages: Iterable[int] | None):
    """(page_nr, display_width, display_height, chars, to_display) for the
    wanted 1-based pages — possibly several items per page, one per text
    direction. Chars are {text, x0, x1, top, bottom, size} in a frame where
    they read left to right; `to_display` maps a bbox in that frame into the
    display frame the crops use."""
    wanted = set(int(p) for p in pages) if pages else None
    try:
        import pypdfium2  # noqa: F401
    except ImportError:
        yield from _iter_pages_pdfplumber(pdf_bytes, wanted)
        return
    yield from _iter_pages_pdfium(pdf_bytes, wanted)


def _annotations_on_page(pn: int, W: float, H: float, chars: list[dict], to_display=_identity) -> list[dict]:
    words = _words(chars)
    units = [w for w in words if _UNIT_RE.match(str(w.get("text") or ""))]
    out: list[dict] = []
    for run in _number_runs(chars):
        unit = next((u for u in units
                     if abs(float(u["top"]) - run["top"]) <= 4.0
                     and 0 <= float(u["x0"]) - run["x1"] <= _UNIT_GAP_PT), None)
        if unit is None:
            continue
        box_x0 = run["x0"] - _NEIGHBOUR_X_PT
        box_x1 = float(unit["x1"]) + _NEIGHBOUR_X_PT
        context: list[str] = []
        for w in words:
            wx0, wx1, wtop = float(w["x0"]), float(w["x1"]), float(w["top"])
            if w is unit:
                continue
            # the number's own characters (as one word or several)
            if wx0 >= run["x0"] - 0.5 and wx1 <= run["x1"] + 0.5 and abs(wtop - run["top"]) <= _BASELINE_PT:
                continue
            if wx1 > box_x0 and wx0 < box_x1 and abs(wtop - run["top"]) <= _NEIGHBOUR_PT:
                text = str(w.get("text") or "")
                if _WORDY_RE.search(text):
                    context.append(text)
        value = _f(run["text"].replace(",", "."))
        if value is None or value <= 0:
            continue
        # a material / total / count word in the block disqualifies it;
        # a room name (or nothing) beside the number keeps it a room label
        standalone = not any(_is_not_a_room_word(w) for w in context)
        out.append({
            "page": pn,
            "value_m2": round(value, 2),
            "standalone": standalone,
            "context": " ".join(context)[:80],
            "bbox": [round(v, 2) for v in to_display(
                [run["x0"], run["top"], float(unit["x1"]), max(run["bottom"], float(unit["bottom"]))])],
            "page_width": round(W, 2),
            "page_height": round(H, 2),
        })
    return out


def read_area_annotations(pdf_bytes: bytes,
                          pages: Iterable[int] | None = None) -> list[dict]:
    """Every „N.NN m²" label on the given (1-based) pages, standalone or not.

    Returns dicts: page, value_m2, standalone, context (the words that made it
    a block, empty when standalone), bbox [x0, top, x1, bottom] in PDF points
    from the page top (the convention `room_facts._bbox_pdf_to_pct` expects),
    page_width, page_height. Order: page, then top-to-bottom, left-to-right.
    A PDF without a text layer yields []."""
    return scan_text_layer(pdf_bytes, pages, figures=False)["annotations"]


def _rel(a: float, b: float) -> float:
    return abs(a - b) / b if b else float("inf")


def _candidate_labels(annotations: Sequence[dict]) -> tuple[list[dict], list[int]]:
    """The standalone labels that together form „the table".

    The same rooms are usually labelled on several sheets (pertvarų, grindų,
    lubų planas). Summing all of them would double the ceiling anchor, so
    pages are taken richest-first and a page whose values mostly (≥ 60 %)
    repeat what is already accepted is the same rooms drawn again — skipped.
    A page with genuinely new values (another floor) is added."""
    by_page: dict[int, list[dict]] = {}
    for a in annotations:
        if a.get("standalone") and _f(a.get("value_m2")):
            by_page.setdefault(int(a.get("page") or 0), []).append(a)
    accepted: list[dict] = []
    skipped: list[int] = []
    for page, labels in sorted(by_page.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        if accepted:
            pool = [float(a["value_m2"]) for a in accepted]
            dup = sum(1 for a in labels if any(_rel(float(a["value_m2"]), v) <= 0.01 for v in pool))
            if dup / len(labels) >= _DUP_VIEW_SHARE:
                skipped.append(page)
                continue
        accepted.extend(labels)
    return accepted, skipped


def _polygon_pct(room: dict) -> list[tuple[float, float]]:
    poly = room.get("polygon_pct") or []
    out: list[tuple[float, float]] = []
    for q in poly if isinstance(poly, (list, tuple)) else []:
        if isinstance(q, dict) and _f(q.get("x")) is not None and _f(q.get("y")) is not None:
            out.append((float(q["x"]), float(q["y"])))
        elif isinstance(q, (list, tuple)) and len(q) >= 2 and _f(q[0]) is not None and _f(q[1]) is not None:
            out.append((float(q[0]), float(q[1])))
    return out if len(out) >= 3 else []


def _inside(pt: tuple[float, float], poly: list[tuple[float, float]]) -> bool:
    x, y = pt
    n = len(poly)
    ins = False
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / ((y2 - y1) or 1e-9) + x1:
            ins = not ins
    return ins


def _label_centre_pct(a: dict) -> tuple[float, float] | None:
    bbox, W, H = a.get("bbox"), _f(a.get("page_width")), _f(a.get("page_height"))
    if not (isinstance(bbox, (list, tuple)) and len(bbox) == 4 and W and H):
        return None
    try:
        return ((float(bbox[0]) + float(bbox[2])) / 2 / W, (float(bbox[1]) + float(bbox[3])) / 2 / H)
    except (TypeError, ValueError):
        return None


def reconcile_rooms_with_annotations(rooms: Sequence[dict],
                                     annotations: Sequence[dict],
                                     *,
                                     confirm_tol: float = CONFIRM_TOL,
                                     adopt_tol: float = ADOPT_TOL) -> dict:
    """Confirm, adopt or flag each Vision room against the standalone labels.

    WHERE the label stands decides first, its VALUE second. The floor plan the
    rooms were outlined on and the sheet the labels are printed on usually share
    one frame (same title block, plan in the same place) — objektas_g: every
    label of the lubų planas falls inside a room outline of the pertvarų planas.
    When at least _SHARED_FRAME_SHARE of the labels fall inside some outline:
      · a label inside exactly one room IS that room's area — confirmed when
        within ±3 %, adopted within ±FRAME_ADOPT_TOL or when the words beside
        the label name the room; a label further off is NOT taken (audit
        2026-09-29, geometry-lanes-7: Vision's box drifted onto the next room's
        label and the room took its area, at any distance) — it stays
        unclaimed with `patalpoje` = the room it lies in, and the room goes on
        to the value rule (`reason = "label_differs"` if nothing else fits);
      · a label inside several rooms means the outlines overlap — the closest
        by value takes it, the others are the same room drawn twice
        (`_area_unconfirmed_reason = "duplicate_of:<nr>"`), kept, never deleted;
      · a label inside no room is unclaimed — a room the model did not return;
      · a room with no label inside falls back to the value rule below.
    Without a shared frame (or without outlines) the value rule alone applies:
    within ±3 % → confirmed, one unclaimed label within ±20 % → adopted, else
    `_area_unconfirmed` (`reason = "no_label"`).

    Confirmed or adopted, the room's area becomes the LABEL's value — the label
    is the fact; Vision's figure is kept beside it when it differs.

    Mutates `rooms` (the pipeline's own list) and returns a summary:
      status       "insufficient" (fewer than MIN_CANDIDATES labels — nothing
                   touched) | "applied"
      geometry     "shared_frame" | "value_only"
      candidates   number of standalone labels
      sum_m2       their sum — the ceiling anchor when applied
      confirmed / adopted / unconfirmed   room nr lists
      duplicates   [{nr, of}] rooms whose only label lies in another room too
      unclaimed    labels no room took, [{page, value_m2}]
      pages        the pages the labels came from

    Rooms whose area came from a table or from the user are never touched.
    A confirmed or adopted room gets `plotas_saltinis = "plano_uzrasas"` and
    `_plotas_uzrasas` {page, value_m2, bbox, page_width, page_height}, and
    keeps `_plotas_pries_uzrasa_m2` (what Vision read) whenever that differs.
    A room whose own outline holds a label too far off to take carries it as
    `_plotas_uzrasas_kitas` {page, value_m2, bbox, page_width, page_height}.
    """
    cands, skipped_pages = _candidate_labels(annotations)
    summary: dict[str, Any] = {
        "status": "insufficient", "geometry": "value_only", "candidates": len(cands),
        "sum_m2": round(sum(float(a["value_m2"]) for a in cands), 2),
        "confirmed": [], "adopted": [], "unconfirmed": [], "duplicates": [], "unclaimed": [],
        "pages": sorted({int(a["page"]) for a in cands}),
        "duplicate_view_pages": skipped_pages,
    }
    if len(cands) < MIN_CANDIDATES:
        return summary

    def _untouchable(r: dict) -> bool:
        src = str(r.get("plotas_saltinis") or "").lower()
        return (src in ("eksplikacija", "user_override", "manual", SOURCE_LABEL)
                or r.get("plotas_source") in ("eksplikacija", "manual")
                or bool(r.get("manual_override")))

    live = [r for r in rooms if isinstance(r, dict) and not _untouchable(r)]
    claimed: set[int] = set()
    settled: set[int] = set()          # ids of rooms already decided

    def _claim(room: dict, idx: int, adopted: bool) -> None:
        a = cands[idx]
        claimed.add(idx)
        settled.add(id(room))
        # the label is the fact — confirmed or adopted, the room's area is the label's
        _take_label_value(room, float(a["value_m2"]))
        room["plotas_saltinis"] = SOURCE_LABEL
        room.pop("_area_unconfirmed", None)
        room.pop("_area_unconfirmed_reason", None)
        room.pop("_plotas_uzrasas_kitas", None)
        room["_plotas_uzrasas"] = _label_record(a)
        (summary["adopted"] if adopted else summary["confirmed"]).append(room.get("nr"))

    def _flag(room: dict, reason: str) -> None:
        settled.add(id(room))
        room["_area_unconfirmed"] = True
        room["_area_unconfirmed_reason"] = reason
        summary["unconfirmed"].append(room.get("nr"))

    # ── geometry: which outlines contain each label ──────────────────────────
    polys = [(r, _polygon_pct(r)) for r in live]
    polys = [(r, pg) for r, pg in polys if pg]
    containing: dict[int, list[dict]] = {}
    if polys:
        for i, a in enumerate(cands):
            c = _label_centre_pct(a)
            if c is None:
                continue
            containing[i] = [r for r, pg in polys if _inside(c, pg)]
        inside_any = sum(1 for i in containing if containing[i])
        if inside_any / len(cands) >= _SHARED_FRAME_SHARE:
            summary["geometry"] = "shared_frame"

    far: dict[int, dict] = {}          # label → the room it lies in but is too far from to be its area
    if summary["geometry"] == "shared_frame":
        # labels inside exactly one room first (unambiguous), then shared ones
        for i, a in sorted(containing.items(), key=lambda kv: (len(kv[1]) != 1, kv[0])):
            hosts = [r for r in containing[i] if id(r) not in settled]
            if not hosts or i in claimed:
                continue
            val = float(cands[i]["value_m2"])
            hosts.sort(key=lambda r: _rel(val, _f(r.get("plotas_m2")) or 0.0) if _f(r.get("plotas_m2")) else float("inf"))
            # The label is the room's when its value is near the room's, or the words beside it name the room —
            # never by position alone: Vision's box may have drifted onto the neighbour's label.
            host = next((r for r in hosts if not (_f(r.get("plotas_m2")) or 0) > 0
                         or _rel(val, float(r["plotas_m2"])) <= FRAME_ADOPT_TOL
                         or _names_room(cands[i], r, live)), None)
            if host is None:
                far[i] = hosts[0]
                hosts[0]["_plotas_uzrasas_kitas"] = _label_record(cands[i])
                continue
            hosts = [host] + [r for r in hosts if r is not host]
            v = _f(host.get("plotas_m2"))
            _claim(host, i, adopted=not (v and v > 0 and _rel(val, v) <= confirm_tol))
            for other in hosts[1:]:
                # the same spot on the plan, drawn as another room — the label
                # cannot be both rooms' area; keep it, say what it looks like
                if not any(j != i and other in containing.get(j, []) for j in containing):
                    _flag(other, f"duplicate_of:{host.get('nr')}")
                    summary["duplicates"].append({"nr": other.get("nr"), "of": host.get("nr")})

    # ── value: whatever geometry left undecided ──────────────────────────────
    pending = [r for r in live if id(r) not in settled]
    for r in pending:
        v = _f(r.get("plotas_m2"))
        if v is None or v <= 0:
            continue
        best = min(((_rel(float(cands[i]["value_m2"]), v), i)
                    for i in range(len(cands)) if i not in claimed), default=None)
        if best is not None and best[0] <= confirm_tol:
            _claim(r, best[1], adopted=False)
    for r in [r for r in live if id(r) not in settled]:
        v = _f(r.get("plotas_m2"))
        best = None
        if v and v > 0:
            best = min(((_rel(float(cands[i]["value_m2"]), v), i)
                        for i in range(len(cands)) if i not in claimed), default=None)
        if best is not None and best[0] <= adopt_tol:
            _claim(r, best[1], adopted=True)
        else:
            _flag(r, "label_differs" if r.get("_plotas_uzrasas_kitas") else "no_label")
    for i, host in far.items():
        if i in claimed:                   # another room's value took it: it was that room's label after all
            _release_far_label(host, cands[i], [cands[j] for j, h in far.items() if h is host and j not in claimed])

    # An unclaimed label carries its position too, so the sheet can offer
    # „pridėti kaip patalpą" with the crop and the room lands on the right spot;
    # one that lies inside a room whose area it is too far from names that room.
    summary["unclaimed"] = [{**_label_record(cands[i]),
                             **({"patalpoje": far[i].get("nr")} if i in far else {})}
                            for i in range(len(cands)) if i not in claimed]
    summary["status"] = "applied"
    return summary


_GENERIC_NAME_WORDS = ("kambarys", "patalpa", "patalpos", "zona", "erdve", "vieta")


def _label_record(a: dict) -> dict:
    return {"page": a.get("page"), "value_m2": a["value_m2"], "bbox": a.get("bbox"),
            "page_width": a.get("page_width"), "page_height": a.get("page_height")}


def _release_far_label(room: dict, taken: dict, still_far: Sequence[dict]) -> None:
    """A label that lay in `room`'s outline, too far from its area to be its own, was another room's after all:
    the room's record of it goes — to the next such label in its outline nobody took, if there is one — and
    with none left there, its question is the plain „no label" again."""
    if room.get("_plotas_uzrasas_kitas") != _label_record(taken):
        return
    if still_far:
        room["_plotas_uzrasas_kitas"] = _label_record(still_far[0])
        return
    room.pop("_plotas_uzrasas_kitas", None)
    if room.get("_area_unconfirmed_reason") == "label_differs":
        room["_area_unconfirmed_reason"] = "no_label"


def _take_label_value(room: dict, value: float) -> None:
    """The room's area becomes the label's; Vision's figure is kept beside it when it differs."""
    old = _f(room.get("plotas_m2"))
    if old and old > 0 and round(old, 2) != round(value, 2):
        room["_plotas_pries_uzrasa_m2"] = round(old, 2)
    room["plotas_m2"] = value


def _name_tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]{4,}", _fold(text)) if w not in _GENERIC_NAME_WORDS}


def _same_word(a: str, b: str) -> bool:
    """One word in two endings („vonia" / „vonios"): a common stem of all but the last two letters, at least four."""
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n >= max(4, min(len(a), len(b)) - 2)


def _names_room(label: dict, room: dict, live: Sequence[dict]) -> bool:
    """The words written beside the label name this room — and no other room of the drawing carries that word
    (two „Miegamasis" cannot be told apart by name)."""
    near = _name_tokens(str(label.get("context") or ""))
    own = _name_tokens(str(room.get("pavadinimas") or ""))
    words = {w for w in own if any(_same_word(w, c) for c in near)}
    if not words:
        return False
    others = [r for r in live if r is not room]
    return not any(_same_word(w, o) for w in words for r in others for o in _name_tokens(str(r.get("pavadinimas") or "")))


def most_common_page(annotations: Sequence[dict]) -> int | None:
    pages = [int(a["page"]) for a in annotations if a.get("standalone") and a.get("page")]
    return Counter(pages).most_common(1)[0][0] if pages else None


# ── 3c: the author's own figures ─────────────────────────────────────────────
# Designers often total their own drawing in a legend: „Sienų dažai 320 m²",
# „laminuota grindų danga 76.65 m²", „Grindjuostės … 53,69 m", „Sienų plytelės
# 60×120 – 38 vnt.". They are one more reading of the same drawing — shown
# BESIDE ours on the check sheet, never used as a value (founder rule: the
# engine computes from the drawing; other people's numbers only check it).

_FIG_UNIT_RE = re.compile(
    r"(?<![\d.,])(\d{1,4}(?:[.,]\d{1,2})?)\s*(m²|m2|vnt\.?|kompl\.?|m)(?![A-Za-zĄČĘĖĮŠŲŪŽąčęėįšųūž²0-9])")
_FIG_FAMILIES = (
    # (family key, words that name it — folded, lower-case prefixes, units it makes sense in)
    ("grindu_danga", ("lamin", "parket", "vinil", "kilim", "linoleum", "grindu dang", "grindų dang", "danga"), ("m2",)),
    ("grindjuostes", ("grindjuost",), ("m",)),
    ("sienu_dazymas", ("sienu daz", "sienų daž", "dazai", "dažai", "dazom", "dažom", "glaist"), ("m2",)),
    ("lubu_dazymas", ("lubu daz", "lubų daž",), ("m2",)),
    ("plyteles", ("plytel", "akmens mas", "keram"), ("m2", "vnt")),
    ("tapetai", ("tapet",), ("m2",)),
    ("karnizai", ("karniz", "moldin", "list"), ("m",)),
    ("led", ("led", "profil"), ("m",)),
    ("gkp", ("gipso", "gkp", "gk "), ("m2",)),
)
_HEIGHT_TAIL_RE = re.compile(r"(\bh\b|\bH\b|aukšt\w*|aukst\w*)\s*[-–:=]?\s*$", re.I)
_MIN_FIGURE = {"m2": 1.0, "m": 2.0, "vnt": 1, "kompl": 1}


def _norm_unit(u: str) -> str:
    """The plan's unit spelling through the one unit table (`kv.m` and `kvm`
    are m², `kompl.` is a kompl) — the two-line map here knew only „m²"."""
    from .row_scorecard import normalize_unit   # a leaf module: no cycle
    canon = normalize_unit(u)
    if len(canon) == 1:
        return next(iter(canon))
    return u.lower().rstrip(".")


def _line_text(line: list[dict]) -> str:
    """One text line rebuilt from characters (CAD exports split words into
    single spaced glyphs, which `extract_words` cannot re-join)."""
    out: list[str] = []
    prev: dict | None = None
    for c in line:
        t = c["text"]
        if prev is not None and float(c["x0"]) - float(prev["x1"]) > 0.35 * float(c.get("size") or 8):
            out.append(" ")
        if t.isspace():
            if out and out[-1] != " ":
                out.append(" ")
        else:
            out.append(t)
        prev = c
    return re.sub(r"\s+", " ", "".join(out)).strip()


def _family_of(label: str, unit: str) -> str | None:
    f = _fold(label)
    for key, words, units in _FIG_FAMILIES:
        if unit in units and any(w in f for w in words):
            return key
    return None


_NOTE_LINE_RE = re.compile(r"^\s*\*|pastab|[:;]\s*$", re.I)
_LABEL_SPLIT_RE = re.compile(r"[;:]|m²|m2\b|\bvnt\.?|\bkompl\.?", re.I)


def _has_letters(text: str, n: int = 3) -> bool:
    return sum(ch.isalpha() for ch in text) >= n


def _label_lines_above(lines: list[list[dict]], texts: list[str], i: int,
                       reach_pt: float = 48.0, max_lines: int = 2) -> list[int]:
    """Indices of up to `max_lines` label-like text lines above line `i`.

    Legend blocks are interleaved, by `top`, with rotated dimension fragments
    („0.610", „2 . 4") that carry no letters — those are skipped, not taken as
    the label. A note paragraph („*PASTABA: …", a line ending in „:") is not a
    label either — the walk stops there."""
    out: list[int] = []
    top_i = float(lines[i][0]["top"])
    j = i - 1
    while j >= 0 and top_i - float(lines[j][0]["top"]) <= reach_pt and len(out) < max_lines:
        t = texts[j]
        if _has_letters(t):
            if _NOTE_LINE_RE.search(t) or len(t.split()) > 8:
                break
            out.append(j)
        j -= 1
    return list(reversed(out))


def _clean_label(text: str) -> str:
    """Drop the debris rotated dimension strings leave in a rebuilt line:
    one-character tokens („5 0 0", „A", „."), and leading number-only tokens
    („0.595 Grindjuostės…" → „Grindjuostės…")."""
    toks = [t for t in text.split() if not (len(t) == 1 and not t.isalpha()) and not (len(t) == 1 and t.isalpha() and t.isupper() is False and t not in ("i", "ir", "į"))]
    toks = [t for t in toks if len(t) > 1 or t.lower() in ("i", "į")]
    while toks and re.fullmatch(r"[\d.,]+", toks[0]):
        toks.pop(0)
    while toks and re.fullmatch(r"[\d.,]+", toks[-1]):
        toks.pop()
    return " ".join(toks)


def _trim_label(text: str, unit: str | None = None) -> str:
    """The last phrase of the label block — after the last „;", „:", or an
    earlier quantity („101 Tambūras 11.01 m² Grindjuostės, h=60 mm" →
    „Grindjuostės, h=60 mm") — with the dimension debris removed."""
    def _last_phrase(t: str) -> str:
        parts = [x for x in _LABEL_SPLIT_RE.split(t) if x and x.strip()]
        out = parts[-1] if parts else t
        out = re.sub(r"^[\s\-–:,.()~]+|[\s\-–:,.(~]+$", "", out)
        return _clean_label(out)[:80]

    # an EARLIER statement on the same rebuilt line („… 53,69m Grindjuostės (iš
    # plytelių) …") ends where its quantity ends — the label starts after it.
    # Unless what follows names no family and what precedes does: „Plytelių
    # klojimo 13vnt. 3.95 m²" is ONE statement with a count and an area.
    last = None
    for last in _FIG_UNIT_RE.finditer(text):
        pass
    if last is not None:
        after = _last_phrase(text[last.end():])
        if unit is None or _family_of(after, unit) or not _family_of(_last_phrase(text), unit):
            return after
    return _last_phrase(text)


def _figures_on_page(pn: int, W: float, H: float, chars: list[dict],
                     room_labels: set[tuple], seen: set[tuple], to_display=_identity) -> list[dict]:
    out: list[dict] = []
    lines = _lines(chars)
    texts = [_line_text(l) for l in lines]
    for i, txt in enumerate(texts):
        for m in _FIG_UNIT_RE.finditer(txt):
            unit = _norm_unit(m.group(2))
            value = _f(m.group(1).replace(",", "."))
            if value is None or value < _MIN_FIGURE.get(unit, 1):
                continue
            if unit == "m2" and (pn, round(value, 2)) in room_labels:
                continue                     # a room's own area, read by the room lane
            before = txt[:m.start()].strip()
            if _HEIGHT_TAIL_RE.search(before):
                continue                     # „h - 1,20 m": a height, not a quantity
            used_lines = [i]
            # the last sentence before the number (a note may share the baseline: „…KITAIP. LED juosta; …")
            _whole = _clean_label(re.sub(r"[;:]", " ", re.split(r"(?<=[.!?])\s+", before)[-1]))[:80]
            if _family_of(_trim_label(before, unit), unit):
                label_src = _trim_label(before, unit)
            elif _family_of(_whole, unit) == "led":
                # „LED juosta; šviesos šaltinis - 24,00 m;" (objektas_i): the legend names the strip before the
                # „;" and the length after it — the whole line is the label (v4 3b, 2026-10-25). Only for the
                # LED family, so no other family's anchor moves.
                label_src = _whole
            else:
                above = _label_lines_above(lines, texts, i)
                if not above:
                    continue
                used_lines = above + [i]
                label_src = _trim_label(" ".join(texts[j] for j in above) + " " + before, unit)
            family = _family_of(label_src, unit)
            if family is None:
                continue
            key = (_fold(label_src), value, unit)
            if key in seen:
                continue
            seen.add(key)
            cs = [c for j in used_lines for c in lines[j]]
            out.append({
                "page": pn, "label": label_src, "value": round(value, 2), "unit": unit,
                "family": family,
                "bbox": [round(v, 2) for v in to_display(
                    [min(float(c["x0"]) for c in cs), min(float(c["top"]) for c in cs),
                     max(float(c["x1"]) for c in cs), max(float(c["bottom"]) for c in cs)])],
                "page_width": round(W, 2),
                "page_height": round(H, 2),
            })
    return out


def scan_text_layer(pdf_bytes: bytes, pages: Iterable[int] | None = None, *,
                    figures: bool = True) -> dict:
    """ONE pass over the text layer: {"annotations", "figures", "heights", "dimensions"}.

    `annotations` are the „N.NN m²" labels (see `read_area_annotations`);
    `figures` the designer's quantity statements (see `read_author_figures`) —
    skipped when `figures=False`. Both lists are sorted by page, then
    top-to-bottom, left-to-right."""
    annotations: list[dict] = []
    figs: list[dict] = []
    heights: list[dict] = []
    dimensions: list[dict] = []
    stated: dict[int, set[int]] = {}
    seen: set[tuple] = set()
    for pn, W, H, chars, to_display in _iter_pages(pdf_bytes, pages):
        try:
            ann = _annotations_on_page(pn, W, H, chars, to_display)
        except Exception:  # noqa: BLE001 — a broken page is not a lane failure
            continue
        annotations.extend(ann)
        try:
            # the wall lengths the plan states (plan_dimensions) — same pass,
            # same frames, so a dimension and a label never disagree on where —
            # and the scale the sheet writes, which the strings' scale must match
            from .plan_dimensions import _dimensions_on_page, stated_scales_on_page
            dimensions.extend(_dimensions_on_page(pn, W, H, chars, to_display))
            stated.setdefault(pn, set()).update(stated_scales_on_page(chars))
        except Exception:  # noqa: BLE001
            pass
        if figures:
            room_labels = {(a["page"], a["value_m2"]) for a in ann if a.get("standalone")}
            try:
                figs.extend(_figures_on_page(pn, W, H, chars, room_labels, seen, to_display))
            except Exception:  # noqa: BLE001
                pass
            try:
                heights.extend(_height_statements_on_page(pn, W, H, chars, to_display))
            except Exception:  # noqa: BLE001
                pass
    if dimensions:
        try:
            # the hairline under each string — what makes a string a wall
            # length rather than a mounting height (plan_dimensions module doc)
            from .plan_dimensions import attach_dimension_lines
            attach_dimension_lines(pdf_bytes, dimensions, stated)
        except Exception:  # noqa: BLE001
            pass
    annotations.sort(key=lambda a: (a["page"], a["bbox"][1], a["bbox"][0]))
    figs.sort(key=lambda a: (a["page"], a["bbox"][1], a["bbox"][0]))
    dimensions.sort(key=lambda a: (a["page"], a["bbox"][1], a["bbox"][0]))
    return {"annotations": annotations, "figures": figs, "heights": heights,
            "dimensions": dimensions}


def read_author_figures(pdf_bytes: bytes, pages: Iterable[int] | None = None) -> list[dict]:
    """The designer's own quantity statements on the given (1-based) pages.

    A statement is a number + unit (m², m, vnt, kompl) whose own line, or the
    label-like text lines just above it, name a material family (paint, floor
    covering, skirting, tiles, wallpaper, cornice, LED, GKP). Height notes
    („h 1,20 m", „H 0.3m"), bare dimensions and the ROOM-AREA labels the plan
    lane reads („14.26 m²" standing in a room) are not statements. Returns
    dicts: page, label (≤ 80 chars), value, unit ("m2" | "m" | "vnt" |
    "kompl"), family, bbox [x0, top, x1, bottom] in PDF points from the page
    top, page_width, page_height. Duplicates (same label, value, unit on a
    later sheet) are dropped; order is page, then top-to-bottom."""
    return scan_text_layer(pdf_bytes, pages, figures=True)["figures"]


def text_pages_from_classification(puslapiai: Sequence[dict] | None) -> list[int]:
    """1-based pages worth reading for text: every classified page except the
    renders („unknown" — visualisations, which carry no drawing text and cost
    seconds each to parse). Empty when nothing is classified — read all."""
    out: list[int] = []
    for p in puslapiai or []:
        if not isinstance(p, dict):
            continue
        tipas = str(p.get("tipas") or p.get("type") or "").strip().lower()
        nr = _f(p.get("page") or p.get("nr") or p.get("puslapis"))
        if nr and tipas and tipas not in ("unknown", "visualization", "vizualizacija", "render"):
            out.append(int(nr))
    return sorted(set(out))


def _lt_num(v: Any) -> str:
    try:
        return f"{float(v):.2f}".replace(".", ",")
    except (TypeError, ValueError):
        return "0,00"


def reclaim_after_refinement(rooms: Sequence[dict], lane: dict,
                             confirm_tol: float = CONFIRM_TOL) -> list[str]:
    """A second look at the rooms the lane left unconfirmed, after a LATER
    step refined their areas (Step 2.5 zoom re-reads wall dimensions): a room
    now within ±3 % of a label nobody claimed takes that label as CONFIRMED.

    Confirm only — never adopt. The first pass may adopt within ±20 % because
    Vision's first figure is coarse; a zoomed figure is precise, so a 19 %
    miss there is a different room's label (on the second fresh objektas_g run
    a bedroom read at 8,22 m² sat 19 % from the hall's 6,90 m² label).
    Mutates the rooms and the lane summary; returns the room numbers claimed.
    """
    if not lane or lane.get("status") != "applied":
        return []
    unclaimed = list(lane.get("unclaimed") or [])
    by_nr = {str(r.get("nr")): r for r in rooms if isinstance(r, dict)}
    claimed: list[str] = []
    for nr in list(lane.get("unconfirmed") or []):
        r = by_nr.get(str(nr))
        if not r or str(r.get("_area_unconfirmed_reason") or "").startswith("duplicate_of:"):
            continue
        v = float(r.get("plotas_m2") or 0)
        if v <= 0 or not unclaimed:
            continue
        scored = sorted((abs(float(u["value_m2"]) - v) / float(u["value_m2"]), i)
                        for i, u in enumerate(unclaimed) if float(u.get("value_m2") or 0) > 0)
        if not scored or scored[0][0] > confirm_tol:
            continue
        u = unclaimed.pop(scored[0][1])
        _take_label_value(r, float(u["value_m2"]))           # the label is the fact
        r["plotas_saltinis"] = SOURCE_LABEL
        r["_plotas_uzrasas"] = {k: u.get(k) for k in ("page", "value_m2", "bbox", "page_width", "page_height")}
        r.pop("_area_unconfirmed", None)
        r.pop("_area_unconfirmed_reason", None)
        r.pop("_plotas_uzrasas_kitas", None)
        # the label lay in ANOTHER room's outline, too far from its area to be its own — it was this room's
        host = by_nr.get(str(u.get("patalpoje") or ""))
        if host is not None and host is not r:
            _release_far_label(host, u, [x for x in unclaimed if str(x.get("patalpoje") or "") == str(u.get("patalpoje"))])
        lane["unconfirmed"] = [x for x in lane["unconfirmed"] if str(x) != str(nr)]
        lane.setdefault("confirmed", []).append(nr)
        claimed.append(str(nr))
    lane["unclaimed"] = unclaimed
    return claimed


def lane_warnings(lane: dict, rooms: Sequence[dict]) -> list[dict]:
    """The user-facing warnings one applied lane result produces — shared by
    the live pipeline and the cache backfill so the two never drift. Says what
    to check, never how the pipeline works (LT-string guard)."""
    if not lane or lane.get("status") != "applied":
        return []
    by_nr = {str(r.get("nr")): r for r in rooms if isinstance(r, dict)}
    out: list[dict] = []
    for nr in lane.get("unconfirmed") or []:
        r = by_nr.get(str(nr)) or {}
        name = r.get("pavadinimas") or nr
        reason = str(r.get("_area_unconfirmed_reason") or "no_label")
        if reason.startswith("duplicate_of:"):
            of = reason.split(":", 1)[1]
            of_name = (by_nr.get(of) or {}).get("pavadinimas") or of
            msg = (f"Patalpa „{name}“ ({_lt_num(r.get('plotas_m2'))} m²) plane persidengia su "
                   f"patalpa „{of_name}“ ir savo ploto užrašo neturi – greičiausiai ta pati "
                   "patalpa įskaičiuota du kartus. Patikrinkite ir nereikalingą išjunkite.")
        elif reason == "label_differs" and isinstance(r.get("_plotas_uzrasas_kitas"), dict):
            other = r["_plotas_uzrasas_kitas"]
            msg = (f"Patalpos „{name}“ vietoje plane (psl. {other.get('page')}) užrašyta "
                   f"{_lt_num(other.get('value_m2'))} m², o skaičiuoju su {_lt_num(r.get('plotas_m2'))} m² – "
                   "skirtumas per didelis, kad būtų tas pats plotas. Patikrinkite, kurios patalpos tai "
                   "užrašas, ir įrašykite tikrą plotą.")
        else:
            msg = (f"Patalpos „{name}“ ({_lt_num(r.get('plotas_m2'))} m²) ploto užrašo plane "
                   "neradau, nors kitos patalpos jį turi – patikrinkite, ar tokia patalpa yra "
                   "ir ar ji nesidubliuoja.")
        out.append({"level": "WARN", "code": "room_area_unconfirmed", "severity": "high",
                    "room": nr, "message": msg})
    shared = lane.get("geometry") == "shared_frame"
    flagged = {str(nr) for nr in lane.get("unconfirmed") or []}
    for u in lane.get("unclaimed") or []:
        inside = str(u.get("patalpoje") or "")
        if inside:
            if inside in flagged:
                continue                   # the room's own warning above already says it
            name = (by_nr.get(inside) or {}).get("pavadinimas") or inside
            out.append({
                "level": "WARN", "code": "plan_area_unclaimed", "severity": "med", "room": inside,
                "message": (f"Plane (psl. {u.get('page')}) užrašytas plotas {_lt_num(u.get('value_m2'))} m² "
                            f"stovi patalpos „{name}“ vietoje, bet jos plotas "
                            f"{_lt_num((by_nr.get(inside) or {}).get('plotas_m2'))} m² – patikrinkite, kuriai "
                            "patalpai šis užrašas priklauso."),
            })
            continue
        out.append({
            "level": "WARN" if shared else "INFO", "code": "plan_area_unclaimed",
            "severity": "med" if shared else "low",
            "message": (f"Plane (psl. {u.get('page')}) užrašytas plotas {_lt_num(u.get('value_m2'))} m² "
                        + ("nepatenka į jokią patalpą – greičiausiai trūksta patalpos; pridėkite ją, jei ji jūsų."
                           if shared else
                           "nepriskirtas jokiai patalpai – galbūt trūksta patalpos.")),
        })
    return out


# ── the plan's own ceiling height („H - 2820") ───────────────────────────────
# Some designers write a room's height on the plan. When a room carries only
# OUR default (2,82 m, `section_average`), that statement is the drawing's
# number for the same thing: the room keeps the value the statement gives and
# the sheet says „užrašytas plane" instead of „prielaida".
#
# A stamp is a ROOM ceiling height only when its surroundings say so
# (2026-10-05). objektas_a's santechnikos sheet carries four bare
# „h=2600 mm" — each under „Kondicionierius", the air-conditioner's mounting
# height — and the lane used to give 2,6 m to EVERY room with a default label
# (room 102 is 3,4 m on the drawing). Now:
#   · its own line may hold only the stamp, numbers and ceiling words — a soffit
#     or fixture height („Kaktos pab. h - 2390", „spintoje h - 2,20 m", a height
#     inside a sentence) is skipped by its words, as before;
#   · the words right around it (`context`, the annotation block) are read: a
#     word that names no room and is no ceiling word — „Kondicionierius" — makes
#     the stamp an annotation of something else, and it sets no height;
#   · it sets the height of ONE room it is tied to: with ceiling words
#     („Lubų aukštis H=2700", `ceiling`) the room its block names, else the one
#     room whose outline holds it; a bare stamp only inside a room's outline next
#     to that room's own label (its number or name in the block). A stamp tied
#     to no room sets nothing — never the rooms elsewhere on the plan. objektas_d's
#     „H - 2820" stands alone in the living room, with no label beside it: it is
#     no longer spread over the flat (its value is our default anyway).

HEIGHT_SOURCE = "plano_uzrasas"
_HEIGHT_RE = re.compile(
    r"(?<![\w.,])(?:H|h)\s*[-=:–]?\s*(\d{4}|\d[.,]\d{2})\s*(?:mm|m)?(?![\w])")
_NOT_A_STOREY_WORDS = ("kakt", "niš", "nis", "spint", "sviest", "šviest", "bald", "lentyn",
                       "rozet", "jungik", "dus", "duš", "galv", "montuo", "isvad", "išvad",
                       "nuo", "iki", "pakab", "lub", "grind")
# Words that make a stamp a ceiling height, on _fold-ed text: „lubų aukštis",
# „patalpos aukštis", „aukštis (nuo grindų) iki lubų", „lubos". Taken out of the
# text before the reject words above are looked for, so „lub" there still turns
# away „lubų niša" / „pakabinamos lubos" but not „lubų aukštis".
_CEILING_RE = re.compile(
    r"(?<![^\W\d_])(?:(?:lubu|lubos|patalp\w*)\s+auksti\w*|auksti\w*\s+(?:nuo\s+grindu\s+)?iki\s+lubu"
    r"|auksti\w*\s+patalp\w*|lubos|lubu)(?![^\W\d_])")
# How far around the stamp its annotation block reaches, in the stamp's own
# character heights: a label line just above it („Kondicionierius" sits 1 pt
# over objektas_a's stamps) up to a room tag's number three lines up.
_BLOCK_X_EM = 1.5
_BLOCK_UP_EM = 4.5
_BLOCK_DOWN_EM = 1.5
_UNIT_WORDS = frozenset({"mm", "cm", "kv"})


def _height_value(token: str) -> float | None:
    v = _f(token.replace(",", "."))
    if v is None:
        return None
    if v > 100:            # millimetres
        v = v / 1000.0
    return round(v, 3) if 2.2 <= v <= 4.5 else None


def _line_text_mapped(line: list[dict]) -> tuple[str, list[dict | None]]:
    """`_line_text(line)` and, for each of its characters, the char it was built
    from (None for a space the gap rule put in) — so a match in the text has a
    box of its own, not the whole baseline's."""
    raw: list[tuple[str, dict | None]] = []
    prev: dict | None = None
    for c in line:
        t = c["text"]
        if prev is not None and float(c["x0"]) - float(prev["x1"]) > 0.35 * float(c.get("size") or 8):
            raw.append((" ", None))
        if t.isspace():
            raw.append((" ", None))
        else:
            raw.extend((ch, c) for ch in t)
        prev = c
    text: list[str] = []
    src: list[dict | None] = []
    for ch, c in raw:
        if ch.isspace():
            if not text or text[-1] == " ":
                continue
            ch, c = " ", None
        text.append(ch)
        src.append(c)
    while text and text[-1] == " ":
        text.pop()
        src.pop()
    return "".join(text), src


def _annotation_block(words: list[dict], box: list[float]) -> str:
    """The words around a stamp's own box — the lines just above it up to a room
    tag's height, the line below, the numbers beside it — as one text, line by
    line, top to bottom. Not in it: the stamp's own words, and the words of its
    own line (the caller lets that line hold ceiling words only — a window that
    cut „Lubų aukštis" in half must not leave an „aukštis" behind)."""
    x0, top, x1, bottom = box
    em = max(bottom - top, 1.0)
    wx0, wx1 = x0 - _BLOCK_X_EM * em, x1 + _BLOCK_X_EM * em
    wy0, wy1 = top - _BLOCK_UP_EM * em, bottom + _BLOCK_DOWN_EM * em

    def own_line(w: dict) -> bool:
        return abs(w["top"] - top) <= _BASELINE_PT and (
            any(ch.isalpha() for ch in w["text"]) or (w["x0"] >= x0 - 0.5 and w["x1"] <= x1 + 0.5))

    near = [w for w in words
            if w["x1"] >= wx0 and w["x0"] <= wx1 and w["bottom"] >= wy0 and w["top"] <= wy1
            and not own_line(w)]
    lines: list[list[dict]] = []
    for w in sorted(near, key=lambda w: (w["top"], w["x0"])):
        if lines and abs(w["top"] - lines[-1][0]["top"]) <= _BASELINE_PT:
            lines[-1].append(w)
        else:
            lines.append([w])
    return " ".join(" ".join(w["text"] for w in sorted(l, key=lambda w: w["x0"])) for l in lines)


def _height_statements_on_page(pn: int, W: float, H: float, chars: list[dict], to_display=_identity) -> list[dict]:
    out: list[dict] = []
    words: list[dict] | None = None          # built for the first stamp: most pages state none
    for line in _lines(chars):
        txt, src = _line_text_mapped(line)
        if not txt or len(txt) > 60:
            continue                      # a note paragraph, not a stamp
        folded = _fold(txt)
        ceiling_line = bool(_CEILING_RE.search(folded))
        unworded = _CEILING_RE.sub(" ", folded)
        if any(w in unworded for w in _NOT_A_STOREY_WORDS):
            continue
        # A stamp stands alone on its line („H - 2820", possibly repeated) or
        # with ceiling words; a height inside a sentence („ap. h - 2260 mm, kai
        # …") describes a soffit, a niche or a fixture — its words give it away.
        if any(ch.isalpha() for ch in _HEIGHT_RE.sub(" ", unworded)):
            continue
        for m in _HEIGHT_RE.finditer(txt):
            v = _height_value(m.group(1))
            if v is None:
                continue
            own = [c for c in src[m.start():m.end()] if c is not None]
            box = [min(float(c["x0"]) for c in own), min(float(c["top"]) for c in own),
                   max(float(c["x1"]) for c in own), max(float(c["bottom"]) for c in own)]
            if words is None:
                words = _words(chars)
            context = _annotation_block(words, box)
            out.append({
                "page": pn, "value_m": v, "text": m.group(0).strip()[:40],
                "bbox": [round(x, 2) for x in to_display(box)],
                "page_width": round(W, 2), "page_height": round(H, 2),
                "ceiling": ceiling_line or bool(_CEILING_RE.search(_fold(context))),
                "context": context[:80],
            })
    return out


def read_height_statements(pdf_bytes: bytes, pages: Iterable[int] | None = None) -> list[dict]:
    """Height stamps on the given pages: [{page, value_m, text, bbox, page_width,
    page_height, ceiling, context}] — `bbox` is the stamp's own box, `ceiling`
    whether ceiling words go with it, `context` the words around it. Which room
    a stamp belongs to, if any, is `apply_height_statements`' question."""
    out: list[dict] = []
    for pn, W, H, chars, to_display in _iter_pages(pdf_bytes, pages):
        try:
            out.extend(_height_statements_on_page(pn, W, H, chars, to_display))
        except Exception:  # noqa: BLE001
            continue
    return out


_DEFAULT_HEIGHT_SOURCES = ("section_average", "default_fallback", "height_gate_reattributed",
                           "height_gate_clamped", "")


def _room_outline(room: dict, page: Any) -> list[tuple[float, float]]:
    """The room's outline in page fractions — its polygon, else its box — when
    the room is drawn on `page`; [] when it is not, or has neither."""
    if _f(room.get("puslapio_nr")) is None or _f(room.get("puslapio_nr")) != _f(page):
        return []
    poly = _polygon_pct(room)
    if poly:
        return poly
    b = room.get("bbox_pct")
    if isinstance(b, dict) and all(_f(b.get(k)) is not None for k in ("x", "y", "w", "h")):
        x, y, w, h = (float(b[k]) for k in ("x", "y", "w", "h"))
        if w > 0 and h > 0:
            return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
    return []


def _nr_key(token: Any) -> str:
    t = str(token or "").strip()
    head, dot, tail = t.partition(".")
    return (head.lstrip("0") or "0") + dot + tail if t else ""


def _tie_statement(stmt: dict, rooms: Sequence[dict]) -> tuple[str, dict | None]:
    """("element", None) — the words around the stamp name something that is not
    a room; ("room", room) — the ONE room the stamp states the height of;
    ("untied", None) — no such room."""
    text = _fold(stmt.get("context") or "")
    named: list[dict] = []
    names: dict[str, list[dict]] = {}
    for r in rooms:
        name = " ".join(_fold(r.get("pavadinimas") or "").split())
        if len(name) >= 2:                                   # „WC" is a room's whole name
            names.setdefault(name, []).append(r)
    for name in sorted(names, key=len, reverse=True):      # „vonios kambarys 1" before „vonios kambarys"
        pattern = r"(?<![^\W_])" + re.escape(name) + r"(?![^\W_])"
        if len(names[name]) == 1 and re.search(pattern, text):
            named.append(names[name][0])
            text = re.sub(pattern, " ", text)
    text = re.sub(r"[²³]", " ", _CEILING_RE.sub(" ", text))        # „m²" is a unit, not a word
    if [w for w in re.findall(r"[^\W\d_]{2,}", text) if w not in _UNIT_WORDS]:
        return "element", None
    by_nr: dict[str, list[dict]] = {}
    for r in rooms:
        if str(r.get("nr") or "").strip():
            by_nr.setdefault(_nr_key(r.get("nr")), []).append(r)
    # a room number stands on its own: not „25,30" (an area), not the „2" of „m2"
    for tok in re.findall(r"(?<![\w.,])\d+(?:\.\d+)?(?![\w,])", text):
        for r in by_nr.get(_nr_key(tok), []):
            if not any(r is n for n in named):
                named.append(r)
    centre = _label_centre_pct(stmt)
    inside = [r for r in rooms if centre is not None and _inside(centre, _room_outline(r, stmt.get("page")))]
    if stmt.get("ceiling"):
        if len(named) == 1:
            return "room", named[0]
        if not named and len(inside) == 1:
            return "room", inside[0]
        return "untied", None
    if len(named) == 1 and any(named[0] is r for r in inside):
        return "room", named[0]
    return "untied", None


def apply_height_statements(rooms: Sequence[dict], statements: Sequence[dict]) -> dict:
    """Give a room that carries only our default height the height the plan
    states FOR THAT ROOM (`_tie_statement`). A stamp that annotates something
    else, or that no single room can claim, sets nothing; a room two different
    stated heights claim is left to its readers. Returns {status, value_m,
    rooms, statements, elements, untied} — `status` "none" (no stamp read),
    "applied", "nothing_to_do" (the rooms it belongs to have their own height),
    "ambiguous" or "not_tied" (no stamp belongs to a room)."""
    stmts = [s for s in statements or [] if isinstance(s, dict) and _f(s.get("value_m")) is not None]
    if not stmts:
        return {"status": "none", "value_m": None, "rooms": []}
    live = [r for r in rooms if isinstance(r, dict)]
    claims: dict[int, list[dict]] = {}
    elements = untied = 0
    for s in stmts:
        kind, room = _tie_statement(s, live)
        if kind == "element":
            elements += 1
        elif room is None:
            untied += 1
        else:
            claims.setdefault(id(room), []).append(s)
    touched: list[str] = []
    conflicting: list[str] = []
    for r in live:
        own = claims.get(id(r))
        if not own:
            continue
        vals = sorted({float(s["value_m"]) for s in own})
        if vals[-1] - vals[0] > 0.011:
            conflicting.append(str(r.get("nr")))
            continue                       # two heights for one room: its readers decide
        src = str(r.get("lubu_aukstis_saltinis") or "").strip().lower()
        if src not in _DEFAULT_HEIGHT_SOURCES:
            continue                       # a reader or the user already said something
        if r.get("_height_marker_evidence"):
            continue
        first = own[0]
        r["lubu_aukstis_m"] = vals[0]
        r["lubu_aukstis_saltinis"] = HEIGHT_SOURCE
        r["_lubu_aukstis_uzrasas"] = {"page": first.get("page"), "text": first.get("text"),
                                       "bbox": first.get("bbox"), "page_width": first.get("page_width"),
                                       "page_height": first.get("page_height")}
        touched.append(str(r.get("nr")))
    tied_values = sorted({float(s["value_m"]) for own in claims.values() for s in own})
    status = ("applied" if touched else "ambiguous" if conflicting
              else "nothing_to_do" if claims else "not_tied")
    out = {"status": status, "value_m": tied_values[0] if len(tied_values) == 1 else None,
           "rooms": touched, "statements": len(stmts), "elements": elements, "untied": untied}
    if conflicting:
        out["conflicting"] = conflicting
    return out
