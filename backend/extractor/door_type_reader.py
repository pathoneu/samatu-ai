"""Door-type reader — read frameless ("beapvadinės") door designation from the
drawing's TEXT (tags / annotations / notes), not from the door glyph.

WHY (2026-06-14, council 5/5 + deep research, verified on the real PDFs):
  - Door frame type is structurally NOT encoded in the plan glyph: a frameless
    and a standard door draw the SAME (wall gap + leaf + swing arc). Asking a VLM
    to classify frame type from the symbol is asking it to hallucinate.
  - LT TP PDFs carry the type as TEXT: plan annotations ("Durų anga ... skirta
    beapvadinėms durims"), door tags (LD-1 ×7 / LD-2 ×3 / LD-3 ×2), and numbered
    notes ("18. Stumdomos durys"). Reading text is Claude's ~90% regime vs ~40%
    for drawing graphics.
  - Measured failure it fixes: Objektas A frameless doors tagged 2 of ~8 → "Durų angų
    paruošimas beapvadinėms durims" 10.2 m vs contractor 39.2 m.

The result is RECONCILED against the glyph-detected count and any disagreement is
SURFACED as a confidence flag (geltona) — never silently overwritten. The merge
RAISES, never lowers, against a contradicting plan symbol, and a governing-note
default ("visos vidaus durys — beapvadinės") is applied only on the premium
archetype, flagged. (Rejected: silent max(); blunt archetype default.)

v4 Phase 3c-2 (2026-10-25): TEXT-FIRST. The reader used to send the sheet images to a model and ask it to read
the tags; now it reads the TEXT LAYER of the same sheets itself (local OCR behind `SAMATU_OCR` for a sheet without
one): every word „beapvad…" / „stumdom…" outside a governing note is one door of that kind at its place, a line
that says ALL interior doors are frameless is the governing note. No model call, no image, no client.
"""
from __future__ import annotations

import re
import statistics
import time
from typing import Optional

MAX_DOOR_PAGES = 6

# A door TAG: D-1, D1, VD-2. Case-sensitive and without „LD" (2026-09-23, checked on the corpus): the LD-1 /
# LD-2 / LD-3 the earlier pattern took for door tags on objektas_a are the CURTAIN-NICHE details of the
# ceiling plan, and the lowercase d1 … d4 it matched on two more sheets are fragments of running text.
_TAG_RE = re.compile(r"\b(?:D|VD|ID)-?\d{1,2}\b")
_PREMIUM = {"premium"}


def _safe_count(v, default: int = 0) -> int:
    """Coerce a count to int; non-numeric (e.g. '3+', '3 durys', null) →
    default. A hallucinated non-numeric count must NOT ValueError-crash the whole
    door-type read and abort extraction (audit 2026-07-06 — sanitary_fixture_reader
    and doors_reader already had this; door_type_reader was the missed reader)."""
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default

def _find_door_pages(pdf_bytes: bytes, pages_meta=None) -> list[int]:
    """1-based pages carrying door tags or type annotations (text-first). Skips
    pure title pages; prefers pages with door tags or 'beapvad'/'stumdom'/'durų anga'.

    Text-blind fallback (2026-08-23): on a rasterised PDF the text scan finds
    nothing and the reader skipped silently. Pass-1's page classification is
    image-based, so fall back to its door/window schedule and floor-plan pages
    (door tags live on the pertvarų planas). Text hits still win when present."""
    hits: list[tuple[int, int]] = []  # (priority, page)
    try:
        # Shared parse. This locator is called once PER VOTING ROUND
        # (read_door_types_voted runs the whole function n times), so before
        # the cache a 3-round vote re-parsed the document three times.
        from .pdf_page_cache import page_texts
        from .door_schedule import _HEADING_RE
        for i, raw in enumerate(page_texts(pdf_bytes)):
            t = raw or ""
            tl = t.lower()
            has_tag = bool(_TAG_RE.search(t))
            has_anno = ("beapvad" in tl or "stumdom" in tl or "durų anga" in tl
                        or "duru anga" in tl)
            if _HEADING_RE.search(t):
                hits.append((-1, i + 1))                       # the door schedule itself comes first
            elif has_tag and has_anno:
                hits.append((0, i + 1))
            elif has_tag or has_anno:
                hits.append((1, i + 1))
    except Exception as exc:  # noqa: BLE001
        print(f"[door_type_reader] pdfplumber scan failed: {exc}")
    hits.sort()
    if not hits:
        from .apdailos_reader import _classified_pages
        fallback = _classified_pages(pages_meta, ("door_window_schedule", "floor_plan"))
        if fallback:
            print(f"[door_type_reader] no text-layer hits — using Pass-1 classified "
                  f"pages {fallback[:MAX_DOOR_PAGES]}")
        return fallback[:MAX_DOOR_PAGES]
    return [pg for _p, pg in hits[:MAX_DOOR_PAGES]]


_FRAMELESS = re.compile(r"beapvad|be apvad|paslept\w* stakt|slept\w* stakt", re.IGNORECASE)
_SLIDING = re.compile(r"stumdom|slankioj", re.IGNORECASE)
_ALL_DOORS = re.compile(r"\bvis(os|ų|u)\b.{0,40}\bdur", re.IGNORECASE)


def _page_lines(pdf_bytes: bytes, page: int) -> list[str]:
    """The sheet's text lines (text layer; local OCR behind SAMATU_OCR when the sheet has none)."""
    from text.page_kind import _lines, _ocr_signal

    from .pdf_page_cache import page_signals
    sigs = page_signals(pdf_bytes)
    if not 1 <= page <= len(sigs):
        return []
    sig = sigs[page - 1]
    if len(str(sig.get("text") or "").strip()) < 8:
        sig = _ocr_signal(pdf_bytes, page, sig)
    return [t for t, _x, _y in _lines(sig)]


def read_door_types(pdf_bytes: bytes, rooms: list[dict],
                    page_classifications: Optional[list] = None,
                    client=None) -> dict:
    """Read door types from the drawing's TEXT. Returns
    {status, pages, doors, beapvadines_count, standartines_count, stumdomos_count, bendras_tipas, pastabos,
     _elapsed_s, _meta}. `doors` lists every line that named a frameless or sliding door, with its sheet — the
    evidence. `client` is accepted for the old call shape and never used (no model call)."""
    t0 = time.time()
    pages = (_find_door_pages(pdf_bytes, page_classifications) if page_classifications
             else _find_door_pages(pdf_bytes))
    meta = {"model": None, "input_tokens": 0, "output_tokens": 0, "saltinis": "tekstas"}
    if not pages:
        return {"status": "skipped", "pages": [], "beapvadines_count": 0,
                "_error": "no door tag/annotation page found",
                "_elapsed_s": round(time.time() - t0, 2), "_meta": meta}
    doors: list[dict] = []
    frameless = sliding = 0
    governing = None
    read_pages: list[int] = []
    for pg in pages:
        lines = _page_lines(pdf_bytes, pg)
        if not lines:
            continue
        read_pages.append(pg)
        for line in lines:
            low = line.lower()
            if _FRAMELESS.search(low) and _ALL_DOORS.search(low):
                governing = governing or {"tipas": "beapvadines", "page": pg, "tekstas": line[:160]}
                continue
            if _FRAMELESS.search(low):
                frameless += 1
                doors.append({"zyme": None, "tipas": "beapvadines", "kiekis": 1, "page": pg, "tekstas": line[:160]})
            elif _SLIDING.search(low):
                sliding += 1
                doors.append({"zyme": None, "tipas": "stumdomos", "kiekis": 1, "page": pg, "tekstas": line[:160]})
    if not read_pages:
        return {"status": "skipped", "pages": pages, "beapvadines_count": 0,
                "_error": "the door sheets carry no readable text", "_elapsed_s": round(time.time() - t0, 2),
                "_meta": meta}
    note = (f"Perskaityta iš brėžinio teksto: {frameless} beapvadinių, {sliding} stumdomų durų užrašų"
            + (f"; bendra pastaba „{governing['tekstas']}“ ({governing['page']} lapas)" if governing else ""))
    return {
        "status": "ok", "pages": read_pages, "doors": doors[:40],
        "beapvadines_count": frameless, "standartines_count": 0, "stumdomos_count": sliding,
        "bendras_tipas": governing["tipas"] if governing else None,
        "bendra_pastaba": governing, "pastabos": note,
        "_elapsed_s": round(time.time() - t0, 2), "_meta": meta,
    }


def _mode_int(values, default: int = 0) -> int:
    """Mode of integer reads, MEDIAN on a tie (kept for callers that aggregate several reads)."""
    vals = [_safe_count(v) for v in values if v is not None]
    if not vals:
        return default
    modes = statistics.multimode(vals)
    if len(modes) == 1:
        return modes[0]
    return int(round(statistics.median(vals)))


def read_door_types_voted(pdf_bytes: bytes, rooms: list[dict],
                          page_classifications: Optional[list] = None,
                          client=None, n: int = 3) -> dict:
    """The old voting entry point. The text reading is deterministic — one read, `_vote.spread` 0."""
    out = read_door_types(pdf_bytes, rooms, page_classifications, client)
    if out.get("status") == "ok":
        out["_vote"] = {"n": 1, "beapvadines_values": [int(out.get("beapvadines_count") or 0)], "spread": 0}
    return out


def reconcile_frameless(plan_frameless: int, reader_frameless: int,
                        bendras_tipas: Optional[str], n_interior_doors: int,
                        archetipas: Optional[str]) -> dict:
    """Reconcile glyph-detected vs text-read frameless-door count. RAISES, never
    lowers, against a contradicting plan symbol; surfaces disagreement as geltona.
    Returns {count, confidence, reason}."""
    plan = int(plan_frameless or 0)
    reader = int(reader_frameless or 0)
    premium = (archetipas or "").lower() in _PREMIUM

    # Governing note "visos vidaus durys — beapvadinės" + premium → apply to all
    # interior doors, flagged. Narrative-gated, raise-only, never silent.
    if bendras_tipas == "beapvadines" and premium and n_interior_doors > max(plan, reader):
        return {"count": int(n_interior_doors), "confidence": "geltona",
                "reason": (f"Brėžinyje nuoroda „visos vidaus durys — beapvadinės" + chr(34) +
                           f"; pritaikyta visoms {n_interior_doors} vidaus durims — patikrinkite pagal durų specifikaciją")}
    if bendras_tipas == "beapvadines" and not premium:
        # Surface the governing note but don't auto-expand on a non-premium project.
        return {"count": max(plan, reader), "confidence": "geltona",
                "reason": f"Brėžinio pastaba mini beapvadines duris — pritaikyta tik aiškiai pažymėtoms ({max(plan, reader)}); patikrinkite pagal durų specifikaciją"}

    if reader > plan:
        return {"count": reader, "confidence": "geltona",
                "reason": f"Brėžinio žymėse rasta {reader} beapvadinių durų, plane matyti {plan} — patikrinkite pagal durų specifikaciją"}
    if reader < plan and reader > 0:
        # conflict — keep the plan count, surface both, never silently lower
        return {"count": plan, "confidence": "geltona",
                "reason": f"Plane matyti {plan} beapvadinių durų, o žymėse — {reader}: skaičiai nesutampa, patikrinkite pagal durų specifikaciją"}
    # agree: the text confirms the plan count
    if reader == plan and reader > 0:
        return {"count": plan, "confidence": "zalia", "reason": ""}
    # the reader found no door-type text at all: the plan's symbols stand alone — and a frameless door draws
    # the same as a framed one, so this is NOT confirmed (2026-09-23: it was called green on two projects
    # whose drawings say nothing about door types)
    if plan:
        return {"count": plan, "confidence": "geltona",
                "reason": (f"Durų tipo užrašų brėžinyje neradau — {plan} beapvadinės pažymėtos tik pagal "
                           "simbolį plane; patikrinkite pagal durų žiniaraštį")}
    return {"count": 0, "confidence": "geltona",
            "reason": "Durų tipo teksto nerasta — beapvadinių durų skaičius nepatikrintas"}
