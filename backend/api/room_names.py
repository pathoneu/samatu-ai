"""GET /api/projects/{project_id}/rooms/{room_nr}/name-hints — what the drawing writes inside a room's outline.

Why (Pathon v3 W5-C, C3 / coverage #39): a room outlined without a row in the room table has no name the
program can trust — the builder would type it. The plan usually says it right there: „VIRTUVĖ", „WC", a
„BOILERIS" in the corner. This route reads the text layer of the room's sheet, keeps the words whose middle
lies inside the room's outline, and turns the ones that name a kind of room into proposals — „Ar tai
virtuvė? [Taip] [Kita…]" in the room sheet. A proposal only: nothing is saved here, the answer goes down
the room edit path the room sheet already uses (and offers Undo there).

Read-only, owner-scoped, rate-limited like the other PDF readers, €0 (the PDF's own text, no Vision). A
scan with no text layer, a room with no outline or no words inside it answers with an empty list and a
`status` saying which — never an error.
"""
from __future__ import annotations

import logging
import unicodedata

from fastapi import APIRouter, HTTPException, Request
from shapely.geometry import Point, Polygon

from api.free_reread import NO_PDF, _project_for

log = logging.getLogger("samatu.room_names")

router = APIRouter(prefix="/api/projects", tags=["room-names"])

MAX_WORDS = 24          # the words shown as „plane užrašyta" — enough to recognise the room, never a page dump
MAX_HINTS = 3

# word stem (folded: lower case, no diacritics) → (name the builder reads, paskirtis the engine knows).
# Ordered: the first stem that matches a word wins for that word. A room name beats a fixture („VONIA" the
# room vs. a bath tub drawn in a kitchen-living space is rare enough; a fixture is the weaker hint).
_ROOM_WORDS: list[tuple[str, str, str]] = [
    ("virtuv", "Virtuvė", "virtuve"),
    ("valgom", "Valgomasis", "valgomasis"),
    ("svetain", "Svetainė", "gyvenamoji"),
    ("miegam", "Miegamasis", "miegamoji"),
    ("vaik", "Vaiko kambarys", "miegamoji"),
    ("vonios", "Vonios kambarys", "vonia"),
    ("vonia", "Vonios kambarys", "vonia"),
    ("dus", "Vonios kambarys", "vonia"),
    ("san.", "San. mazgas", "san"),
    ("sanmazg", "San. mazgas", "san"),
    ("wc", "WC", "wc"),
    ("tualet", "WC", "wc"),
    ("koridor", "Koridorius", "koridorius"),
    ("holas", "Holas", "holas"),
    ("prieskamb", "Prieškambaris", "koridorius"),
    ("tambur", "Tambūras", "tambūras"),
    ("drabuzin", "Drabužinė", "drabuzine"),
    ("rubin", "Rūbinė", "rubine"),
    ("sandel", "Sandėliukas", "sandeliukas"),
    ("katilin", "Katilinė", "katiline"),
    ("boiler", "Katilinė", "katiline"),
    ("katil", "Katilinė", "katiline"),
    ("skalbykl", "Skalbykla", "skalbykla"),
    ("garaz", "Garažas", "garazas"),
    ("kabinet", "Darbo kambarys", "kabinetas"),
    ("darbo", "Darbo kambarys", "kabinetas"),
    ("pirt", "Pirtis", "pirtis"),
    ("sauna", "Pirtis", "pirtis"),
    ("laiptin", "Laiptinė", "laiptine"),
    ("teras", "Terasa", "terasa"),
    ("balkon", "Balkonas", "terasa"),
    ("techn", "Techninė patalpa", "techpatalpa"),
]


def _fold(text: str) -> str:
    s = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode("ascii")
    return s.lower().strip()


def hints_from_words(words: list[str]) -> list[dict]:
    """The words inside the outline → at most MAX_HINTS proposals, each with the word that said it.
    One proposal per room name; the order is the order the words name them in."""
    out: list[dict] = []
    seen: set[str] = set()
    for word in words:
        folded = _fold(word)
        if len(folded) < 2:
            continue
        for stem, name, paskirtis in _ROOM_WORDS:
            # „wc" / „dus" are whole words; longer stems may start a longer word („VIRTUVĖ-VALGOMASIS")
            hit = folded == stem if len(stem) <= 3 else stem in folded
            if not hit:
                continue
            if name not in seen:
                seen.add(name)
                out.append({"pavadinimas": name, "paskirtis": paskirtis, "zodis": word})
            break
        if len(out) >= MAX_HINTS:
            break
    return out


def _room(project: dict, room_nr: str) -> dict | None:
    for r in project.get("patalpos") or []:
        if isinstance(r, dict) and str(r.get("nr")) == str(room_nr):
            return r
    return None


def _outline(room: dict) -> tuple[int | None, Polygon | None]:
    pts = room.get("polygon_pct")
    page = room.get("puslapio_nr") or room.get("page")
    if not isinstance(pts, list) or len(pts) < 3:
        return None, None
    try:
        ring = [(float(p[0]), float(p[1])) for p in pts]
        poly = Polygon(ring)
        if not poly.is_valid:
            poly = poly.buffer(0)
        return (int(page) if page else None), (poly if not poly.is_empty else None)
    except (TypeError, ValueError, IndexError):
        return None, None


def words_inside(pdf_bytes: bytes, page: int, outline: Polygon) -> list[str]:
    """The words of `page`'s text layer whose middle lies inside `outline` (display-frame page fractions),
    in reading order. Uses the text reader the area-label lane already uses (both text directions)."""
    from extractor.plan_area_annotations import _iter_pages, _words

    found: list[tuple[float, float, str]] = []
    for _pn, W, H, chars, to_display in _iter_pages(pdf_bytes, [page]):
        if not W or not H:
            continue
        for w in _words(chars):
            x0, top, x1, bottom = to_display((w["x0"], w["top"], w["x1"], w["bottom"]))
            cx, cy = (x0 + x1) / 2 / W, (top + bottom) / 2 / H
            text = str(w.get("text") or "").strip()
            if text and outline.contains(Point(cx, cy)):
                found.append((cy, cx, text))
    found.sort()
    return [t for _y, _x, t in found]


# Plain `def`: PDF parsing is blocking CPU — FastAPI runs it in the threadpool.
@router.get("/{project_id}/rooms/{room_nr}/name-hints")
def api_room_name_hints(request: Request, project_id: str, room_nr: str):
    project = _project_for(request, project_id)
    from main import _check_rate_limit, _client_key
    _check_rate_limit(_client_key(request), "page_geometry")

    room = _room(project, room_nr)
    if room is None:
        raise HTTPException(status_code=404, detail="Tokios patalpos projekte nėra")
    page, outline = _outline(room)
    if not page or outline is None:
        return {"room_nr": str(room_nr), "status": "no_outline", "words": [], "hints": []}

    from storage import get_storage, pdf_key
    try:
        pdf_bytes = get_storage().get(pdf_key(project_id))
    except Exception as exc:  # noqa: BLE001 — a storage hiccup is a 502, not a 500
        log.warning("name-hints pdf fetch failed for %s: %r", project_id, exc)
        raise HTTPException(status_code=502, detail="Nepavyko pasiekti brėžinio saugyklos")
    if not pdf_bytes:
        raise HTTPException(status_code=404, detail=NO_PDF)

    try:
        words = words_inside(pdf_bytes, page, outline)
    except Exception as exc:  # noqa: BLE001 — an unreadable page proposes nothing; it never breaks the sheet
        log.warning("name-hints text read failed for %s room %s: %r", project_id, room_nr, exc)
        words = []
    hints = hints_from_words(words)
    return {
        "room_nr": str(room_nr),
        "page": page,
        "status": "ok" if hints else ("no_text" if not words else "no_match"),
        "words": words[:MAX_WORDS],
        "hints": hints,
    }
