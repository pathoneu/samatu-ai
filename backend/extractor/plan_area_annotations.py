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

The module is pure: bytes in, dicts out. No model call, no network.
"""
from __future__ import annotations

import re
from collections import Counter
from io import BytesIO
from typing import Any, Iterable, Sequence

__all__ = [
    "CONFIRM_TOL", "ADOPT_TOL", "MIN_CANDIDATES", "SOURCE_LABEL",
    "read_area_annotations", "reconcile_rooms_with_annotations",
    "plan_pages_from_classification", "most_common_page",
]

CONFIRM_TOL = 0.03      # a Vision area this close to a label IS that label
ADOPT_TOL = 0.20        # this close to one unclaimed label → take the label's value
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


def _number_runs(page) -> list[dict]:
    """Numbers rebuilt from single characters on one text line.

    `extract_words` may split a character-spaced „7.25" into four words; the
    characters themselves are always there. Digit/./, characters that follow
    each other on one line within _gap_limit are one number. A letter closes
    the run (so „3.52m2" is 3.52 and a stray 2); a space is neutral — the gap
    rule decides, because CAD exports sometimes pad digits with spaces."""
    chars = [c for c in (page.chars or []) if isinstance(c.get("text"), str) and c["text"]]
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


def read_area_annotations(pdf_bytes: bytes,
                          pages: Iterable[int] | None = None) -> list[dict]:
    """Every „N.NN m²" label on the given (1-based) pages, standalone or not.

    Returns dicts: page, value_m2, standalone, context (the words that made it
    a block, empty when standalone), bbox [x0, top, x1, bottom] in PDF points
    from the page top (the convention `room_facts._bbox_pdf_to_pct` expects),
    page_width, page_height. Order: page, then top-to-bottom, left-to-right.
    A PDF without a text layer yields []."""
    import pdfplumber  # local import — keeps the module importable without it in tests that never read a PDF

    wanted = set(int(p) for p in pages) if pages else None
    out: list[dict] = []
    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        for pn, page in enumerate(pdf.pages, 1):
            if wanted and pn not in wanted:
                continue
            try:
                words = page.extract_words() or []
                runs = _number_runs(page)
            except Exception:  # noqa: BLE001 — a broken page is not a lane failure
                continue
            units = [w for w in words if _UNIT_RE.match(str(w.get("text") or ""))]
            for run in runs:
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
                    "bbox": [round(run["x0"], 2), round(run["top"], 2),
                             round(float(unit["x1"]), 2), round(max(run["bottom"], float(unit["bottom"])), 2)],
                    "page_width": round(float(page.width), 2),
                    "page_height": round(float(page.height), 2),
                })
    out.sort(key=lambda a: (a["page"], a["bbox"][1], a["bbox"][0]))
    return out


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


def reconcile_rooms_with_annotations(rooms: Sequence[dict],
                                     annotations: Sequence[dict],
                                     *,
                                     confirm_tol: float = CONFIRM_TOL,
                                     adopt_tol: float = ADOPT_TOL) -> dict:
    """Confirm, adopt or flag each Vision room against the standalone labels.

    Mutates `rooms` (the pipeline's own list) and returns a summary:
      status       "insufficient" (fewer than MIN_CANDIDATES labels — nothing
                   touched) | "applied"
      candidates   number of standalone labels
      sum_m2       their sum — the ceiling anchor when applied
      confirmed / adopted / unconfirmed   room nr lists
      unclaimed    labels no room took, [{page, value_m2}]
      pages        the pages the labels came from

    Rooms whose area came from a table or from the user are never touched.
    A confirmed or adopted room gets `plotas_saltinis = "plano_uzrasas"` and
    `_plotas_uzrasas` {page, value_m2, bbox, page_width, page_height}; an
    adopted one also keeps `_plotas_pries_uzrasa_m2` (what Vision read). A
    room no label supports gets `_area_unconfirmed = True`.
    """
    cands, skipped_pages = _candidate_labels(annotations)
    summary: dict[str, Any] = {
        "status": "insufficient", "candidates": len(cands),
        "sum_m2": round(sum(float(a["value_m2"]) for a in cands), 2),
        "confirmed": [], "adopted": [], "unconfirmed": [], "unclaimed": [],
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

    claimed: set[int] = set()

    def _claim(room: dict, idx: int, adopted: bool) -> None:
        a = cands[idx]
        claimed.add(idx)
        if adopted:
            room["_plotas_pries_uzrasa_m2"] = round(float(room.get("plotas_m2") or 0), 2)
            room["plotas_m2"] = float(a["value_m2"])
        room["plotas_saltinis"] = SOURCE_LABEL
        room.pop("_area_unconfirmed", None)
        room["_plotas_uzrasas"] = {
            "page": a.get("page"), "value_m2": a["value_m2"], "bbox": a.get("bbox"),
            "page_width": a.get("page_width"), "page_height": a.get("page_height"),
        }

    pending: list[dict] = []
    for r in rooms:
        if not isinstance(r, dict) or _untouchable(r):
            continue
        v = _f(r.get("plotas_m2"))
        if v is None or v <= 0:
            pending.append(r)
            continue
        best = min(((_rel(float(cands[i]["value_m2"]), v), i)
                    for i in range(len(cands)) if i not in claimed), default=None)
        if best is not None and best[0] <= confirm_tol:
            _claim(r, best[1], adopted=False)
            summary["confirmed"].append(r.get("nr"))
        else:
            pending.append(r)

    for r in pending:
        v = _f(r.get("plotas_m2"))
        best = None
        if v and v > 0:
            best = min(((_rel(float(cands[i]["value_m2"]), v), i)
                        for i in range(len(cands)) if i not in claimed), default=None)
        if best is not None and best[0] <= adopt_tol:
            _claim(r, best[1], adopted=True)
            summary["adopted"].append(r.get("nr"))
        else:
            r["_area_unconfirmed"] = True
            summary["unconfirmed"].append(r.get("nr"))

    summary["unclaimed"] = [{"page": cands[i].get("page"), "value_m2": cands[i]["value_m2"]}
                            for i in range(len(cands)) if i not in claimed]
    summary["status"] = "applied"
    return summary


def most_common_page(annotations: Sequence[dict]) -> int | None:
    pages = [int(a["page"]) for a in annotations if a.get("standalone") and a.get("page")]
    return Counter(pages).most_common(1)[0][0] if pages else None
