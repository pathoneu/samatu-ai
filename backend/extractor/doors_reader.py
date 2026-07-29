"""Focused Vision pass to count ALL doors in an interior project.

LT interjero Vision pass-1 dažnai miss'ina:
- Lauko duris (priekinis įėjimas, terasa, garažo lauko) — kartais traktuoja
  kaip "ne interjero scope" ir nepriskaičiuoja
- Koridoriaus / Holo duris — kiekvieną prirašo PASKIRTIES kambariui (Berniuko,
  Vonia), o pats Koridorius lieka su 0 durų.
- Slankiojančias / harmonika duris kurios atrodo netipiškai

2026-05-27 (Berzas calibration): pass-1 grąžino 10 durų (durys_total), o per-room
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
from .response_text import response_text
MAX_TOKENS = 3072

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
  "exterior_count": number,
  "audit_trail": "kelias kuriuo ėjai per planą — pradėjau nuo X, mačiau Y..."
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
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for i, page in enumerate(pdf.pages):
                txt = (page.extract_text() or "").upper()
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
) -> dict:
    """Count all doors via focused Vision call on the floor_plan page.

    Returns {status, page, doors, total_count, interior_count, exterior_count,
    _elapsed_s, _meta}."""
    t0 = time.time()
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
    raw = response_text(resp)
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
        "audit_trail": parsed.get("audit_trail"),
        "_elapsed_s": round(time.time() - t0, 2),
        "_meta": {"input_tokens": getattr(usage, "input_tokens", None),
                  "output_tokens": getattr(usage, "output_tokens", None), "model": model},
    }


def merge_doors_into_rooms(rooms: list[dict], doors_result: dict) -> int:
    """Replace ALL per-room door elements with doors_reader output.

    doors_reader is authoritative: when it returns status "ok" we TRUST its
    enumeration entirely and drop pass-1 door attributions from every room
    (otherwise the SAME physical door is counted in both rooms it connects).
    Each door is attributed to the FIRST room in `between` (the "owner") so
    that sum(per_room_doors) == doors_result.total_count.

    Returns the count of rooms whose elementai got modified."""
    if doors_result.get("status") != "ok":
        return 0
    doors = doors_result.get("doors") or []
    if not doors:
        return 0
    by_nr = {str(r.get("nr") or ""): r for r in rooms}
    entrance_rooms = [r for r in rooms if (r.get("paskirtis") or "").lower() in _ENTRANCE]
    modified: set[str] = set()

    # First pass — strip stale pass-1 doors from every room.
    for room in rooms:
        existing = room.get("elementai") or []
        kept = [e for e in existing if (e.get("tipas") or "").lower() not in ("duris", "pasleptos_duris")]
        if len(kept) != len(existing):
            room["elementai"] = kept
            modified.add(str(room.get("nr") or ""))

    # Second pass — re-attribute each door to the FIRST room in `between`.
    for d in doors:
        between = d.get("between") or []
        tipas = (d.get("tipas") or "standart").lower()
        is_exterior = "exterior" in between or tipas == "garazo"
        target_nr = None
        if is_exterior:
            target_nr = next((str(x) for x in between if x != "exterior" and str(x) in by_nr), None)
            if target_nr is None and entrance_rooms:
                target_nr = str(entrance_rooms[0].get("nr"))
        else:
            target_nr = next((str(x) for x in between if str(x) in by_nr), None)
        if not target_nr or target_nr not in by_nr:
            continue
        # Coerce Vision-supplied dims defensively: a non-numeric value (e.g.
        # "large", null) must fall back to the LT default, not ValueError-crash
        # the whole merge and silently drop EVERY door. (audit 2026-07-05)
        def _mm(v, dflt):
            try:
                return int(float(v))
            except (TypeError, ValueError):
                return dflt
        new_door = {
            "tipas": "pasleptos_duris" if tipas == "pasleptos" else "duris",
            "kiekis": 1,
            "plotis_mm": _mm(d.get("plotis_mm"), 900),
            "aukstis_mm": _mm(d.get("aukstis_mm"), 2100),
            "_exterior": is_exterior,
        }
        by_nr[target_nr].setdefault("elementai", []).append(new_door)
        modified.add(target_nr)
    return len(modified)
