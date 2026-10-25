"""Read the wall finishes the IŠKLOTINĖS / APDAILOS sheets write — TEXT-FIRST (v4 Phase 3c-2, 2026-10-25).

LT interjero projektuose paskutiniai puslapiai paprastai turi `GRINDŲ PLANAS`, `IŠKLOTINIŲ IR APDAILŲ PLANAS` and
the per-room `… IŠKLOTINĖS`. Until v4 3c-2 a model looked at those sheet images and ESTIMATED each room's finish
shares from coloured lines (and, by its own prompt, guessed from the room type when it could not see them). That is
gone. Now the sheets' TEXT is read (text layer; local OCR behind `SAMATU_OCR` for a sheet without one):

  · a sheet whose title or text names exactly ONE room of the project (its number or its unique name) is that
    room's sheet; the finish words on it („dažoma", „plytelės", „tapetai", „dekoratyvinis tinkas", „mikrocementas",
    „plokštė", „veidrodis") are the room's finish KINDS, each with the words that named it;
  · a room whose sheets name ONE finish kind gets that kind as its whole wall finish (share 1,0 — the sheet names
    nothing else); a room whose sheets name several gets the kinds listed and NO shares — how much of the wall each
    covers is a measure of the drawing, not of its text, and is left to him (the rows keep their room-type rule);
  · with a client, the finish sheets' TEXT may be structured by text/schema_llm.py (which room, which kind, every
    value substring-guarded); the model never sees a sheet.

Returns the same shape as before ({status, page, pages, patalpos, _error, _elapsed_s, _meta}); `patalpos[]` rows carry
`sienu_apdaila` only when a single kind decides it, plus `apdailos_rusys` and `pastabos` (the words, the sheet).
"""
from __future__ import annotations

import re
import time
import unicodedata
from typing import Optional

TEXT_SOURCE = "tekstas"       # room["_apdailos_saltinis"] / _meta["saltinis"] of a reading of the text layer
MAX_ATTEMPTS = 3              # kept for callers that read it (the text reading makes no call)

# finish kind → the words that name it on a finish sheet (folded: upper case, no diacritics)
FINISH_WORDS: tuple[tuple[str, re.Pattern], ...] = (
    ("molio_tinkas", re.compile(r"\bMOLIO TINK|\bDEKORATYVIN\w* TINK|\bKALKIN\w* TINK|\bVENECIJIEC")),
    ("kita_danga", re.compile(r"\bMIKROCEMENT|\bBETONO EFEKT")),
    ("tapetai", re.compile(r"\bTAPET")),
    ("plyteles", re.compile(r"\bPLYTEL|\bMOZAIK")),
    ("plokste", re.compile(r"\bPLOKST\w*(?! LUB)|\bPANEL")),
    ("veidrodis", re.compile(r"\bVEIDROD")),
    ("dazymas", re.compile(r"\bDAZ(OMA|YMAS|YTI|OMOS|OMAS|AI)\b|\bDAZOM")),
)


def _fold(text) -> str:
    s = unicodedata.normalize("NFD", str(text or "").upper())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.split())


def build_user_text(rooms: list[dict]) -> str:
    """The room list as the schema reader gets it (nr, name, area) — text only."""
    lines = ["Kambariai (priskirk apdailą kiekvienam pagal nr):"]
    for r in rooms:
        lines.append(f"  {r.get('nr') or '?'} {r.get('pavadinimas') or ''}  ({r.get('plotas_m2')} m²)")
    return "\n".join(lines)


def _find_apdailos_page(pdf_bytes: bytes) -> Optional[int]:
    """Scan PDF text layer for 'IŠKLOTINIŲ' or 'APDAILŲ PLANAS' title.

    Returns 1-based page index, or None if no such page found.

    2026-06-11 hardening (Rangovas B experiment): pages titled VIZUALIZACIJA
    (renders) are EXCLUDED — the reader was classifying finishes from renders
    and self-reporting "low confidence" on half the rooms. Among the remaining
    candidates, a page whose title mentions IŠKLOTIN wins over a generic
    APDAILŲ match (išklotinės carry the per-wall finish markers)."""
    pages = _find_apdailos_pages(pdf_bytes)
    return pages[0] if pages else None


# Cap on pages sent in one finish-reading call. Rangovas B probe: 11 išklotinių
# pages = ~25k input tokens, confident reads for 8/15 rooms (vs 1/15 single-page).
MAX_APDAILOS_PAGES = 12


def _classified_pages(pages_meta, tipai: tuple[str, ...]) -> list[int]:
    """Pages Pass-1 classified as one of `tipai`, in priority order of `tipai`
    then page order. Shared by the text-blind fallbacks below."""
    role: dict[int, str] = {}
    for p in pages_meta or []:
        try:
            nr = int(p.get("nr"))
        except (TypeError, ValueError, AttributeError):
            continue
        if nr >= 1:
            role[nr] = (p.get("tipas") or "").lower()
    out: list[int] = []
    for t in tipai:
        out.extend(sorted(nr for nr, r in role.items() if r == t and nr not in out))
    return out


def _find_apdailos_pages(pdf_bytes: bytes, pages_meta=None) -> list[int]:
    """ALL candidate finish pages (1-based), best-priority first.

    TEXT-BLIND FALLBACK (2026-08-23, flattened-scan ablation): the title-word
    scan below needs a text layer. On a rasterised re-export (iLovePDF-style,
    common for LT drawings) it finds nothing, this reader silently returned
    `skipped`, every room fell to paskirtis finish defaults, and Objektas A's wall
    paint came out −31.6% — while Pass-1 had classified p10 finish_schedule
    and p11–17 wall_elevation perfectly from the images. So when the text scan
    yields nothing, use that classification (same pattern as
    sanitary_fixture_reader). Text hits still win when present: that keeps
    every text-layer project byte-identical.

    Large TPs carry per-room sienų išklotinės across MANY sheets (Rangovas B:
    pages 12-22, 1-2 rooms each) — a single page structurally cannot describe
    every room's finish, which is why the single-page read self-reported "low
    confidence" on 14/15 rooms. Multi-page reading restored confident reads."""
    candidates: list[tuple[int, int]] = []  # (priority, 1-based page)
    try:
        from .pdf_page_cache import page_texts  # shared parse, not a 7th open
        for i, raw in enumerate(page_texts(pdf_bytes)):
            txt = (raw or "").upper()
            if "VIZUALIZACIJ" in txt:
                continue
            if "IŠKLOTIN" in txt or "ISKLOTIN" in txt:
                candidates.append((0, i + 1))
            elif "APDAILŲ PLANAS" in txt or "APDAILU PLANAS" in txt or "APDAILOS PLANAS" in txt:
                candidates.append((1, i + 1))
    except Exception as exc:  # noqa: BLE001
        print(f"[apdailos_reader] pdfplumber scan failed: {exc}")
    candidates.sort()
    if not candidates:
        fallback = _classified_pages(pages_meta, ("wall_elevation", "finish_schedule"))
        if fallback:
            print(f"[apdailos_reader] no title hits — using the sheet kinds "
                  f"pages {fallback[:MAX_APDAILOS_PAGES]}")
        return fallback[:MAX_APDAILOS_PAGES]
    return [pg for _prio, pg in candidates[:MAX_APDAILOS_PAGES]]


def _sheet_text(pdf_bytes: bytes, page: int) -> str:
    try:
        from .pdf_page_cache import page_texts
        texts = page_texts(pdf_bytes)
        t = texts[page - 1] if 1 <= page <= len(texts) else ""
    except Exception:  # noqa: BLE001
        t = ""
    if len((t or "").strip()) < 8:
        try:
            from text.ocr import ocr_enabled, ocr_page
            if ocr_enabled():
                _w, _h, words = ocr_page(pdf_bytes, page)
                t = " ".join(w.text for w in words)
        except Exception:  # noqa: BLE001
            pass
    return t or ""


def _rooms_named(text_f: str, rooms: list[dict]) -> list[str]:
    """Room numbers a sheet's folded text names: its number as a word, or a name no other room shares."""
    names: dict[str, list[str]] = {}
    for r in rooms:
        nm = _fold(r.get("pavadinimas"))
        nr = str(r.get("nr") or "").strip()
        if len(nm) >= 4 and nr:
            names.setdefault(nm, []).append(nr)
    hit: set[str] = set()
    for r in rooms:
        nr = str(r.get("nr") or "").strip()
        if len(nr) >= 2 and re.search(r"(?<![\w-])(?<!\d[.,])" + re.escape(_fold(nr)) + r"(?![\w-]|[.,]\d)", text_f):
            hit.add(nr)
    for nm, nrs in names.items():
        if len(nrs) == 1 and re.search(r"(?<!\w)" + re.escape(nm) + r"(?!\w)", text_f):
            hit.add(nrs[0])
    return sorted(hit)


def _kinds_in(text_f: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for kind, rx in FINISH_WORDS:
        m = rx.search(text_f)
        if m:
            out[kind] = m.group(0)
    return out


def read_apdailos_finishes(
    pdf_bytes: bytes,
    rooms: list[dict],
    apdailos_page: Optional[int] = None,
    client=None,
    pages_meta: Optional[list] = None,
) -> dict:
    """The finish kinds each room's own sheet writes (see the module docstring). Never raises.

    status: ok (some room read) · skipped (no finish sheet, or no sheet names one room) · error (no text)."""
    t0 = time.time()
    pages = ([apdailos_page] if apdailos_page
             else _find_apdailos_pages(pdf_bytes, pages_meta) if pages_meta
             else _find_apdailos_pages(pdf_bytes))
    meta = {"model": None, "input_tokens": 0, "output_tokens": 0, "saltinis": TEXT_SOURCE, "pages": list(pages or [])}
    if not pages:
        return {"status": "skipped", "page": None, "pages": [], "patalpos": [],
                "_error": "no apdailos page found", "_elapsed_s": round(time.time() - t0, 2), "_meta": meta}
    per_room: dict[str, dict] = {}
    read_pages: list[int] = []
    texts: list[tuple[int, str]] = []
    for pg in pages:
        t = _sheet_text(pdf_bytes, pg)
        if not t.strip():
            continue
        read_pages.append(pg)
        texts.append((pg, t))
        f = _fold(t)
        named = _rooms_named(f, rooms)
        if len(named) != 1:
            continue
        kinds = _kinds_in(f)
        if not kinds:
            continue
        rec = per_room.setdefault(named[0], {"kinds": {}, "pages": []})
        for k, w in kinds.items():
            rec["kinds"].setdefault(k, (w, pg))
        rec["pages"].append(pg)
    if not read_pages:
        return {"status": "error", "page": pages[0], "pages": [], "patalpos": [],
                "_error": "the finish sheets carry no readable text", "_elapsed_s": round(time.time() - t0, 2),
                "_meta": meta}
    if not per_room and client is not None:
        per_room = _schema_rooms(texts, rooms, client, meta)
    out_rooms: list[dict] = []
    for nr, rec in per_room.items():
        kinds = rec["kinds"]
        words = "; ".join(f"„{w}“ ({pg} lapas)" for w, pg in kinds.values())
        row = {"nr": nr, "apdailos_rusys": sorted(kinds), "pastabos": f"Iš lapo teksto: {words}",
               "pages": sorted(set(rec["pages"]))}
        if len(kinds) == 1:
            row["sienu_apdaila"] = {f"{next(iter(kinds))}_share": 1.0}
        out_rooms.append(row)
    status = "ok" if out_rooms else "skipped"
    return {"status": status, "page": read_pages[0], "pages": read_pages, "patalpos": out_rooms,
            "_error": None if out_rooms else "no finish sheet names exactly one room",
            "_elapsed_s": round(time.time() - t0, 2), "_meta": meta}


def _schema_rooms(texts: list[tuple[int, str]], rooms: list[dict], client, meta: dict) -> dict[str, dict]:
    """With a client: the finish sheets' TEXT → which room has which finish kind (text/schema_llm.py, guarded)."""
    from text.schema_llm import structure
    kinds = [k for k, _ in FINISH_WORDS]
    text = "\n\n".join(f"[lapas {pg}]\n{t}" for pg, t in texts)
    res = structure(text, fields={"nr": "text", "rusis": kinds, "zodziai": "text"}, key="nr", client=client,
                    instruction=(build_user_text(rooms) + "\nIš apdailos / išklotinių lapų teksto nurodyk, kurios "
                                 "patalpos sienų apdaila kokia (rusis), ir nukopijuok žodžius, kurie ją įvardija "
                                 "(zodziai). Jokių dalių ar procentų."))
    meta["input_tokens"] = int((res.get("_meta") or {}).get("input_tokens") or 0)
    meta["output_tokens"] = int((res.get("_meta") or {}).get("output_tokens") or 0)
    meta["model"] = (res.get("_meta") or {}).get("model")
    meta["schema_llm"] = {"status": res.get("status"), "atmesta": len(res.get("refused") or [])}
    known = {str(r.get("nr") or "").strip() for r in rooms}
    out: dict[str, dict] = {}
    for it in res.get("items") or []:
        nr = str(it.get("nr") or "").strip()
        if nr not in known or not it.get("rusis"):
            continue
        out.setdefault(nr, {"kinds": {}, "pages": []})["kinds"].setdefault(it["rusis"], (it.get("zodziai") or it["rusis"], 0))
    return out


def merge_apdailos_into_rooms(rooms: list[dict], apdailos_result: dict) -> int:
    """Attach apdailos finish shares to each matching room (by nr).

    Mutates `rooms` in place. Returns number of rooms updated.

    On each room, sets:
        room["sienu_apdailos_breakdown"] = {dazymas_share, plyteles_share, ...}
        room["plyteliu_aukstis_m"] = number | None  (only if not already set)
        room["_apdailos_pastabos"] = str
        room["_apdailos_page"]  = int | None   — the sheet this room's finish
        room["_apdailos_pages"] = list[int]      was read from

    The two page fields exist for the room check sheet (2026-09-04): the
    contractor is shown the finish next to a crop of the drawing it came from,
    and until now the only record of WHICH drawing was project-level
    (`_meta.apdailos_page`). A multi-sheet read therefore could not say which
    of its pages answered a given room. It still cannot — the reader returns
    one flat room list for the whole call — so both are recorded: `page` is
    the first sheet sent, `pages` is every sheet in that call, and a renderer
    that wants to be honest offers the first and lists the rest.
    """
    # "partial" = the body was truncated and only some rooms survived. Merging
    # them is right — the rooms that did NOT arrive simply keep no breakdown,
    # so universal_rules still marks them `_tile_read_missing` and the caller
    # still fires the degradation warning.
    if apdailos_result.get("status") not in ("ok", "partial"):
        return 0
    by_nr = {str(p.get("nr")): p for p in (apdailos_result.get("patalpos") or [])}
    src_page = apdailos_result.get("page")
    src_pages = [p for p in (apdailos_result.get("pages") or []) if p]
    n = 0
    for room in rooms:
        p = by_nr.get(str(room.get("nr")))
        if not p:
            continue
        if src_page:
            room["_apdailos_page"] = src_page
        if src_pages:
            room["_apdailos_pages"] = list(src_pages)
        breakdown = p.get("sienu_apdaila")
        if breakdown:
            room["sienu_apdailos_breakdown"] = breakdown
            room["_apdailos_saltinis"] = TEXT_SOURCE if (apdailos_result.get("_meta") or {}).get("saltinis") \
                == TEXT_SOURCE else room.get("_apdailos_saltinis")
        if p.get("apdailos_rusys"):
            room["_apdailos_rusys"] = list(p["apdailos_rusys"])
        if room.get("plyteliu_aukstis_m") is None and p.get("plyteliu_aukstis_m") is not None:
            room["plyteliu_aukstis_m"] = p.get("plyteliu_aukstis_m")
        if p.get("pastabos"):
            room["_apdailos_pastabos"] = p.get("pastabos")
            # 2026-06-11 (Rangovas B experiment): the reader SELF-REPORTS when
            # it is guessing ("low confidence; spėjimas pagal paskirtį" on 8/15
            # rooms) — and that signal was ignored while the guessed finishes
            # flowed into 🟢 paint quantities. Propagate it so the confidence
            # post-pass can demote finish-derived lines.
            low = p["pastabos"].lower()
            if "low confidence" in low or "spėjim" in low or "spejim" in low:
                room["_apdailos_confidence"] = "low"
        n += 1
    return n
