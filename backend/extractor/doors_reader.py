"""Focused Vision pass to count ALL doors in an interior project.

LT interjero Vision pass-1 dažnai miss'ina:
- Lauko duris (priekinis įėjimas, terasa, garažo lauko) — kartais traktuoja
  kaip "ne interjero scope" ir nepriskaičiuoja
- Koridoriaus / Holo duris — kiekvieną prirašo PASKIRTIES kambariui (Berniuko,
  Vonia), o pats Koridorius lieka su 0 durų.
- Slankiojančias / harmonika duris kurios atrodo netipiškai

2026-05-27 (Objektas A calibration): pass-1 grąžino 10 durų (durys_total), o per-room
elementai sum = 9. Kontraktoriaus truth = 14 durys (per item 18 "Durų angų
paruošimas: 39,2 m" = 14 × 2,8 m). Trūko 4-5 durų, daugiausia exterior +
koridoriaus.

Šis modulis paleidžia fokusuotą Vision call'ą ant floor_plan puslapio su
imperative instrukcija "count ALL doors INCLUDING exterior". Grąžina total
project door count + per-room breakdown.

RECONSTRUCTED 2026-06-09 from the surviving cpython-314.pyc (verbatim prompts,
schema, signatures, constants) + the caller contract in vision_call.py.
"""
from __future__ import annotations

import base64
import io
import json
import re
import time
from typing import Optional

import anthropic
import pdfplumber
from pdf2image import convert_from_bytes

from models_config import model_for  # role: "doors" — resolved at call time
from .response_text import read_answer, usage_meta
from .universal_rules import normalize_paskirtis
# Raised 2026-07-29 for the SAME reason apdailos_reader was (see its comment):
# Opus 5 runs extended thinking BY DEFAULT and it counts against this cap, so a
# snug max_tokens is shared between a variable-length thinking block and the
# answer — the answer gets cut mid-JSON and the reader silently returns nothing.
# Measured on apdailos: 2,776 output tokens one run, 4,757 the next, same PDF.
# 16384 leaves ~14k for thinking and stays under the SDK non-streaming ceiling
# (MAX_TOKENS_NONSTREAMING_CEILING = 21_333, above which the client raises
# before any HTTP call).
MAX_TOKENS = 16384

SYSTEM_PROMPT = """Tu esi LT interjero brėžinio durų inventorizacijos agentas. Tau duotas vienas puslapis — aukšto planas (floor_plan).

Tavo VIENAS DARBAS: suskaičiuoti VISAS DURIS, kurias matai brėžinyje. Niekas kitkas tau nesvarbu.

DURŲ TIPAI (visi count'inami):
- Standartinės vidaus durys: linija + lanko žymėjimas (atsidarymas)
- Paslėptos / beapvadinės durys: plonas tarpas sienoje BE lanko, kartais žymėjimas „beapvadinės"
- Slankiojančios: dvigubas stačiakampis su rodykle
- Harmonika: zigzago raštas
- Lauko durys: ant external sienos (priekinis įėjimas, terasa, balkonas)
- Garažo durys: didelės dvigubos arba kelinės

KO DAŽNAI PRALEIDŽIAMA (atsidirbk šitas atskirai):
1. PRIEKINIS ĮĖJIMAS (lauko durys į Tambūrą iš lauko) — privaloma būti
2. GARAŽO LAUKO DURYS — privaloma būti jei yra garažas
3. TERASOS / BALKONO DURYS (sliding glass) — pažiūrėk visus external sienos taškus
4. KORIDORIAUS DURYS — koridorius PRIVALO turėti duris į kiekvieną gretimą kambarį. Jei matai koridorių su 4 kaimynais, jis turi >= 4 duris.
5. EN-SUITE DURYS — durys iš miegamojo į savo vonią (atskira nuo durų iš koridoriaus)

NIEKADA negrąžink markdown ``` fences ar prozos. Tik JSON."""

_USER_SCHEMA = """

Galimi exterior taškai: priekinis įėjimas (Tambūras/Holas), garažo lauko, terasa.

Output JSON:
{
  "doors": [
    {
      "id": "d1",
      "tipas": "standart" | "pasleptos" | "slankiojanti" | "harmonika" | "garazo",
      "plotis_mm": number,
      "aukstis_mm": number,
      "between": ["101", "exterior"] | ["103", "108"] | etc.,
      "pastabos": "trumpa pastaba"
    }
  ],
  "total_count": number,
  "interior_count": number,
  "exterior_count": number
}

PROCEDŪRA (sek griežtai):
1. Identifikuok kiekvieno kambario kontūrą plane.
2. Kiekvienam kambariui — perskaičiuok visas duris jo sienose. Kambariai bus listinami `between` masyve.
3. Po to atskirai patikrink: ar yra priekinis lauko įėjimas? ar yra garažo lauko durys? ar yra terasos durys?
4. Patikrink koridorių(s) — kiekvienas turi durims į visus tiesiogiai prijungtus kambarius.
5. Suskaičiuok `total_count`. NETIKĖK, kad standartinis namas turi tik 5-10 durų — daugumoje LT namų yra 12-16."""

_ENTRANCE = frozenset({"tamburas", "garazas", "tambūras", "holas"})


def build_user_text(rooms_summary: list[dict]) -> str:
    lines = ["Eksplikacijos patalpos:"]
    for r in rooms_summary:
        nr = r.get("nr") or "?"
        nm = r.get("pavadinimas") or ""
        plotas = r.get("plotas_m2")
        lines.append(f"  {nr} {nm}  ({plotas} m²)")
    return "\n".join(lines) + _USER_SCHEMA


def _find_floor_plan_page(pdf_bytes: bytes, page_classifications: Optional[list] = None) -> int:
    """Find a floor_plan page (1-based). Priorities:
    1. From pass-1 page classifications (if provided)
    2. pdfplumber text scan for "AUKŠTO PLANAS" / "PLANAS" titles
    3. Fallback to page 2 (typical LT layout)."""
    for c in (page_classifications or []):
        if (c.get("tipas") or "") == "floor_plan":
            try:
                return int(c.get("nr"))
            except (TypeError, ValueError):
                pass
    try:
        from .pdf_page_cache import page_texts  # shared parse, not a fresh open
        for i, raw in enumerate(page_texts(pdf_bytes)):
            txt = (raw or "").upper()
            if "AUKŠTO PLANAS" in txt or "PIRMO AUKŠTO" in txt:
                return i + 1
    except Exception as exc:  # noqa: BLE001
        print(f"[doors_reader] pdfplumber scan failed: {exc}")
    return 2


def _render_page_b64(pdf_bytes: bytes, page_nr_1based: int, dpi: int = 220) -> Optional[str]:
    try:
        imgs = convert_from_bytes(pdf_bytes, dpi=dpi,
                                  first_page=page_nr_1based, last_page=page_nr_1based)
        if not imgs:
            return None
        buf = io.BytesIO()
        imgs[0].save(buf, format="PNG")
        return base64.standard_b64encode(buf.getvalue()).decode("ascii")
    except Exception as exc:  # noqa: BLE001
        print(f"[doors_reader] render page failed: {exc}")
        return None


def read_doors_from_plan(
    pdf_bytes: bytes,
    rooms: list[dict],
    page_classifications: Optional[list] = None,
    client=None,
    page: Optional[int] = None,
) -> dict:
    """Count all doors via focused Vision call on the floor_plan page.

    ``page`` (1-based, original numbering) reads that sheet; without it the
    first floor_plan page is located as before. ``rooms`` are the rooms listed
    to the reader — pass only the rooms drawn on that sheet.

    Returns {status, page, doors, total_count, interior_count, exterior_count,
    _elapsed_s, _meta}."""
    t0 = time.time()
    if page is None:
        page = _find_floor_plan_page(pdf_bytes, page_classifications)
    if not page:
        return {"status": "skipped", "page": None, "doors": [], "total_count": 0,
                "_error": "no floor_plan page found", "_elapsed_s": round(time.time() - t0, 2)}
    b64 = _render_page_b64(pdf_bytes, page)
    if not b64:
        return {"status": "error", "page": page, "doors": [], "total_count": 0,
                "_error": "page render failed", "_elapsed_s": round(time.time() - t0, 2)}
    rooms_summary = [{"nr": r.get("nr"), "pavadinimas": r.get("pavadinimas"),
                      "plotas_m2": r.get("plotas_m2")}
                     for r in rooms if r.get("nr") or r.get("pavadinimas")]
    user_text = build_user_text(rooms_summary)
    try:
        model = model_for("doors")  # call-time resolution (MODEL_OVERRIDE etc.)
        client = client or anthropic.Anthropic(max_retries=1)
        resp = client.messages.create(
            model=model, max_tokens=MAX_TOKENS,
            system=[{"type": "text", "text": SYSTEM_PROMPT,
                     "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64",
                                             "media_type": "image/png", "data": b64}},
                {"type": "text", "text": user_text},
            ]}],
        )
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "page": page, "doors": [], "total_count": 0,
                "_error": f"Vision call failed: {exc}", "_elapsed_s": round(time.time() - t0, 2)}

    # Text blocks only — block 0 is a ThinkingBlock on thinking-enabled
    # models, and reading .text off it killed this reader mid-run.
    # A refused or cut-off answer is named, and its billed tokens kept in
    # _meta (2026-09-30: page 2 of objektas_g was refused and read as
    # "no JSON in response", its 5,497 input tokens never counted).
    raw, stopped = read_answer(resp, reader="doors_reader", page=page)
    if stopped:
        u = usage_meta(resp, model)
        return {"status": "error", "page": page, "doors": [], "total_count": 0,
                "_error": stopped, "_elapsed_s": round(time.time() - t0, 2),
                "_meta": {"input_tokens": u["input_tokens"],
                          "output_tokens": u["output_tokens"], "model": model}}
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return {"status": "error", "page": page, "doors": [], "total_count": 0,
                "_error": "no JSON in response", "_raw_excerpt": raw[:500],
                "_elapsed_s": round(time.time() - t0, 2)}
    try:
        parsed = json.loads(m.group(0))
    except json.JSONDecodeError as je:
        return {"status": "error", "page": page, "doors": [], "total_count": 0,
                "_error": f"JSON parse error: {je}", "_raw_excerpt": raw[:500],
                "_elapsed_s": round(time.time() - t0, 2)}

    doors = parsed.get("doors") or []
    total = int(parsed.get("total_count") or len(doors))
    ext = int(parsed.get("exterior_count") or sum(
        1 for d in doors if "exterior" in (d.get("between") or []) or (d.get("tipas") == "garazo")))
    usage = getattr(resp, "usage", None)
    return {
        "status": "ok", "page": page, "doors": doors,
        "total_count": total, "exterior_count": ext, "interior_count": total - ext,
        "_elapsed_s": round(time.time() - t0, 2),
        "_meta": {"input_tokens": getattr(usage, "input_tokens", None),
                  "output_tokens": getattr(usage, "output_tokens", None), "model": model},
    }


def rooms_by_plan_page(rooms: list[dict]) -> dict[int, list[dict]]:
    """Rooms grouped by the sheet the first pass placed them on (`puslapio_nr`,
    ORIGINAL 1-based numbering — the numbering `pdf_bytes` is rendered in).
    Rooms that name no sheet are left out."""
    out: dict[int, list[dict]] = {}
    for r in rooms:
        try:
            p = int(r.get("puslapio_nr"))
        except (TypeError, ValueError):
            continue
        if p > 0:
            out.setdefault(p, []).append(r)
    return dict(sorted(out.items()))


def read_doors_from_plan_pages(
    pdf_bytes: bytes,
    rooms: list[dict],
    page_classifications: Optional[list] = None,
    client=None,
) -> dict:
    """One focused door read per plan sheet that holds rooms (audit
    2026-09-30, vision-pipeline-6).

    The single read of the first floor_plan page used to replace the doors of
    EVERY room, so on a project whose rooms sit on two sheets (two storeys)
    the rooms on the sheet it did not read lost their doors. The sheets come
    from the rooms themselves — the same `puslapio_nr` the adjacency pass
    resolves its floor page from (`vision_call._resolve_floor_b64`), taken
    per sheet instead of the modal one. Each read lists only that sheet's
    rooms. One paid call per sheet.

    When no room names its sheet, the old single read of the first
    floor_plan page runs and applies to all rooms (`_all_rooms`).

    Returns {status, page, pages_read, pages_unread, page_results, doors,
    total_count, interior_count, exterior_count, _elapsed_s, _round_metas}.
    ``status`` is "ok" when at least one sheet was read."""
    t0 = time.time()
    groups = rooms_by_plan_page(rooms)
    if groups:
        page_results = [read_doors_from_plan(pdf_bytes, page_rooms, page_classifications,
                                             client=client, page=p)
                        for p, page_rooms in groups.items()]
    else:
        single = read_doors_from_plan(pdf_bytes, rooms, page_classifications, client=client)
        single["_all_rooms"] = True
        page_results = [single]
    ok = [r for r in page_results if r.get("status") == "ok"]
    out = {
        "status": "ok" if ok else (page_results[0].get("status") or "error"),
        "page": ok[0].get("page") if ok else page_results[0].get("page"),
        "pages_read": [r.get("page") for r in ok],
        "pages_unread": [r.get("page") for r in page_results if r.get("status") != "ok"],
        "page_results": page_results,
        "doors": [d for r in ok for d in (r.get("doors") or [])],
        "total_count": sum(int(r.get("total_count") or 0) for r in ok),
        "exterior_count": sum(int(r.get("exterior_count") or 0) for r in ok),
        "interior_count": sum(int(r.get("interior_count") or 0) for r in ok),
        "_elapsed_s": round(time.time() - t0, 2),
        # every billed call, for vision_call._reader_call_metas
        "_round_metas": [r["_meta"] for r in page_results if r.get("_meta")],
    }
    if not ok:
        out["_error"] = "; ".join(f"{r.get('page')}: {r.get('_error')}" for r in page_results)
    return out


def merge_doors_by_page(rooms: list[dict], result: dict) -> int:
    """Merge each sheet's doors into the rooms ON THAT SHEET only.

    Rooms on a sheet that was not read (its call failed, or no read ran) keep
    the doors the first pass gave them. Per-sheet `_unattributed` counts are
    summed into ``result["_unattributed"]``; ``result["_kept_pass1_pages"]``
    lists the sheets whose answer was too unplaceable to trust (see
    merge_doors_into_rooms). Returns the count of rooms that gained a door."""
    if result.get("status") != "ok":
        return 0
    groups = rooms_by_plan_page(rooms)
    gained = 0
    unattributed = 0
    kept: list = []
    for pr in result.get("page_results") or []:
        if pr.get("status") != "ok":
            continue
        page_rooms = rooms if pr.get("_all_rooms") else groups.get(pr.get("page")) or []
        if not page_rooms:
            continue
        gained += merge_doors_into_rooms(page_rooms, pr)
        unattributed += int(pr.get("_unattributed") or 0)
        if pr.get("_kept_pass1_doors"):
            kept.append(pr.get("page"))
    result["_unattributed"] = unattributed
    if kept:
        result["_kept_pass1_pages"] = kept
        result["_kept_pass1_doors"] = True
    return gained


def _room_resolver(rooms: list[dict]):
    """`between` entries → the room dict. The schema asks for room NUMBERS, but
    a reader answer arrives as "1" for "01", as an int, or as the room's NAME —
    on the second fresh objektas_g run (2026-09-10) none of the eleven doors
    matched a room, so every one was dropped after the pass-1 doors had already
    been erased. Numbers are matched exactly, then without leading zeros; a
    name only when it is unique."""
    by_nr: dict[str, dict] = {}
    by_short: dict[str, list[dict]] = {}
    by_name: dict[str, list[dict]] = {}
    for r in rooms:
        nr = str(r.get("nr") or "").strip()
        if nr:
            by_nr[nr] = r
            by_short.setdefault(nr.lstrip("0") or "0", []).append(r)
        nm = " ".join(str(r.get("pavadinimas") or "").lower().split())
        if nm:
            by_name.setdefault(nm, []).append(r)

    def resolve(x) -> dict | None:
        if x is None:
            return None
        key = str(x).strip()
        if not key or key.lower() == "exterior":
            return None
        if key in by_nr:
            return by_nr[key]
        short = by_short.get(key.lstrip("0") or "0")
        if short and len(short) == 1:
            return short[0]
        nm = " ".join(key.lower().split())
        named = by_name.get(nm)
        if named and len(named) == 1:
            return named[0]
        # "01 Svetainė" / "P-07" / "07 (miegamasis)" — the number LEADS the
        # string. A number after a name („Miegamasis 2") names the room, it
        # is not room 02 (2026-09-15 review).
        m = re.match(r"^\s*(?:[A-Za-z]{1,2}[-.\s]?)?0*(\d{1,3})(?![.,]\d)(?![A-Za-z]{2})", key)
        if m:
            short = by_short.get(m.group(1).lstrip("0") or "0")
            if short and len(short) == 1:
                return short[0]
        return None
    return resolve


def merge_doors_into_rooms(rooms: list[dict], doors_result: dict) -> int:
    """Replace the per-room door elements with the doors_reader enumeration.

    doors_reader is authoritative when its doors can be PLACED: each door is
    attributed to the FIRST room in `between` (the "owner") so that the rooms'
    doors add up to `total_count` and a door is never counted in both rooms it
    connects. Doors the resolver cannot place are counted in
    `doors_result["_unattributed"]`; when fewer than half of the doors can be
    placed the pass-1 doors are LEFT ALONE (an unplaceable enumeration must
    not erase what the first read found — 2026-09-10).

    Returns the count of rooms that gained a door."""
    if doors_result.get("status") != "ok":
        return 0
    doors = doors_result.get("doors") or []
    if not doors:
        return 0
    resolve = _room_resolver(rooms)
    entrance_rooms = [r for r in rooms
                      if normalize_paskirtis(r.get("paskirtis") or "") in _ENTRANCE]

    def _mm(v, dflt):
        try:
            return int(float(v))
        except (TypeError, ValueError):
            return dflt

    placed: list[tuple[dict, dict]] = []
    unattributed = 0
    for d in doors:
        between = d.get("between") or []
        if not isinstance(between, list):
            between = [between]
        tipas = (d.get("tipas") or "standart").lower()
        is_exterior = any(str(x).lower() == "exterior" for x in between) or tipas == "garazo"
        target = next((r for r in (resolve(x) for x in between) if r is not None), None)
        if target is None and is_exterior and entrance_rooms:
            target = entrance_rooms[0]
        if target is None:
            unattributed += 1
            continue
        placed.append((target, {
            "tipas": "pasleptos_duris" if tipas == "pasleptos" else "duris",
            "kiekis": 1,
            "plotis_mm": _mm(d.get("plotis_mm"), 900),
            "aukstis_mm": _mm(d.get("aukstis_mm"), 2100),
            "_exterior": is_exterior,
        }))
    doors_result["_unattributed"] = unattributed
    if not placed or len(placed) * 2 < len(doors):
        doors_result["_kept_pass1_doors"] = True
        return 0

    for room in rooms:
        existing = room.get("elementai") or []
        kept = [e for e in existing if (e.get("tipas") or "").lower() not in ("duris", "pasleptos_duris")]
        if len(kept) != len(existing):
            room["elementai"] = kept
    gained: set[int] = set()
    for target, new_door in placed:
        target.setdefault("elementai", []).append(new_door)
        gained.add(id(target))
    return len(gained)
