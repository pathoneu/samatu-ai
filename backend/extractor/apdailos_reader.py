"""Read IŠKLOTINIŲ IR APDAILŲ PLANAS (wall finish plan) page from a project PDF.

LT interjero projektuose paskutiniai puslapiai paprastai turi:
- `GRINDŲ PLANAS` (floor finishes)
- `IŠKLOTINIŲ IR APDAILŲ PLANAS` (wall finishes — colored lines + markers)

Šis modulis randa tokį puslapį, paleidžia fokusuotą Vision call'ą ant jo
vieno, ir grąžina per-room finish breakdown. Naudojama `extract_interior`
flow'e po pass-1, kad pakeistume hardcoded `walls_paint` heuristics
(`tamburas: 0`, `garazas: 0`, ir t.t.) realiu projekto specifikuotu apdailos
plotu.

2026-05-27 — pirma versija (Berzas fixture testas: -11,6% → -4,3% walls accuracy).

RECONSTRUCTED 2026-06-09: the original .py was never committed and was lost;
this is rebuilt from the surviving cpython-314.pyc (verbatim SYSTEM_PROMPT,
schema, signatures, constants) + the universal_rules consumer contract
(sienu_apdailos_breakdown drives the apdailos paint branch at lines 707-745).
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

from models_config import model_for  # role: "apdailos" — resolved at call time
MAX_TOKENS = 4096

SYSTEM_PROMPT = """Tu esi LT interjero brėžinio analizės agentas. Tau duotas vienas puslapis — IŠKLOTINIŲ IR APDAILŲ PLANAS (wall finishes plan).

Šis puslapis rodo, KAIP apdailinta KIEKVIENA siena KIEKVIENAME kambaryje. Skirtingos sienos apdailos pažymėtos:
- skirtingomis spalvomis (linijomis ant brėžinio)
- markers (a1-a9, b1-b3, c1-c4, ir t.t.) iš legendos

Tavo darbas: kiekvienam pateiktam kambariui nustatyti, KOKIA YRA DOMINUOJANTI sienų apdaila ir kokia DALIS sienų yra padengta kuriuo finišu.

Apdailos tipai (skaityk iš puslapio legendos — pavadinimai ir spalvos gali skirtis):
- "dazymas" — sienos dažomos
- "plyteles" — plytelės (skirtingi tipai grupuojami čia: porcelain, didžiaformatės, ir t.t.)
- "tapetai" — tapetai (vaikiški ar dekoratyviniai)
- "plokste" — siena dengiama plokšte (medienos panelis, akmuo, t.t.)
- "veidrodis" — veidrodinė siena
- "molio_tinkas" — molio / kalkinis dekoratyvinis tinkas, sienų dekoravimas tinku (NE dažymas!)
- "kita_danga" — mikrocementas, betono efektas, kita ištisinė danga (NE dažymas, NE plytelės)

SVARBU: skaityk iš APDAILOS PLANO / IŠKLOTINIŲ puslapio, NE iš vizualizacijų
(renderių). Jei matai tik vizualizaciją — pažymėk pastabose "low confidence".

Grąžink TIK JSON, jokios prozos. Ne markdown fences."""

_USER_SCHEMA = """

Output schema (JSON):
{
  "patalpos": [
    {
      "nr": "101",
      "pavadinimas": "...",
      "sienu_apdaila": {
        "dazymas_share": 0.0..1.0,
        "plyteles_share": 0.0..1.0,
        "tapetai_share": 0.0..1.0,
        "plokste_share": 0.0..1.0,
        "veidrodis_share": 0.0..1.0,
        "molio_tinkas_share": 0.0..1.0,
        "kita_danga_share": 0.0..1.0
      },
      "plyteliu_aukstis_m": null | number,
      "pastabos": "trumpai ką matei brėžinyje"
    }
  ]
}

TAISYKLĖS:
- Sumos shares per kambarį turi būti ≈ 1.0.
- Jei matai SOLID spalvotą liniją tik dalies sienos ilgyje, įvertink share procentaliai.
- Jei plytelės eina tik iki tam tikro aukščio (pvz. iki 1,5m kabinete prie darbo stalo) — pažymėk `plyteliu_aukstis_m`.
- Jei plytelės eina IKI LUBŲ (typical vonia / san) — palik `plyteliu_aukstis_m: null`.
- Veidrodis paprastai mažas plotas (0.05-0.15 share).
- Jei kambariui apdaila nematyti — pažymėk pastabose "low confidence" ir spėk pagal paskirtį (vonia/san = 0.85+ plytelės; garazas/tambūras = 0.8+ dažymas; miegamasis/kabinetas/gyvenamoji = 0.8+ dažymas)."""


def build_user_text(rooms: list[dict]) -> str:
    """Room list + output schema. The model maps each listed room to a finish
    breakdown keyed by its nr."""
    lines = ["Kambariai (priskirk apdailą kiekvienam pagal nr):"]
    for r in rooms:
        nr = r.get("nr") or "?"
        nm = r.get("pavadinimas") or ""
        plotas = r.get("plotas_m2")
        lines.append(f"  {nr} {nm}  ({plotas} m²)")
    return "\n".join(lines) + _USER_SCHEMA


def _find_apdailos_page(pdf_bytes: bytes) -> Optional[int]:
    """Scan PDF text layer for 'IŠKLOTINIŲ' or 'APDAILŲ PLANAS' title.

    Returns 1-based page index, or None if no such page found.

    2026-06-11 hardening (Bacevičiaus experiment): pages titled VIZUALIZACIJA
    (renders) are EXCLUDED — the reader was classifying finishes from renders
    and self-reporting "low confidence" on half the rooms. Among the remaining
    candidates, a page whose title mentions IŠKLOTIN wins over a generic
    APDAILŲ match (išklotinės carry the per-wall finish markers)."""
    pages = _find_apdailos_pages(pdf_bytes)
    return pages[0] if pages else None


# Cap on pages sent in one finish-reading call. Bacevičiaus probe: 11 išklotinių
# pages = ~25k input tokens, confident reads for 8/15 rooms (vs 1/15 single-page).
MAX_APDAILOS_PAGES = 12


def _find_apdailos_pages(pdf_bytes: bytes) -> list[int]:
    """ALL candidate finish pages (1-based), best-priority first.

    Large TPs carry per-room sienų išklotinės across MANY sheets (Bacevičiaus:
    pages 12-22, 1-2 rooms each) — a single page structurally cannot describe
    every room's finish, which is why the single-page read self-reported "low
    confidence" on 14/15 rooms. Multi-page reading restored confident reads."""
    candidates: list[tuple[int, int]] = []  # (priority, 1-based page)
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for i, page in enumerate(pdf.pages):
                txt = (page.extract_text() or "").upper()
                if "VIZUALIZACIJ" in txt:
                    continue
                if "IŠKLOTIN" in txt or "ISKLOTIN" in txt:
                    candidates.append((0, i + 1))
                elif "APDAILŲ PLANAS" in txt or "APDAILU PLANAS" in txt or "APDAILOS PLANAS" in txt:
                    candidates.append((1, i + 1))
    except Exception as exc:  # noqa: BLE001
        print(f"[apdailos_reader] pdfplumber scan failed: {exc}")
    candidates.sort()
    return [pg for _prio, pg in candidates[:MAX_APDAILOS_PAGES]]


def _render_page_b64(pdf_bytes: bytes, page_nr_1based: int, dpi: int = 200) -> Optional[str]:
    try:
        imgs = convert_from_bytes(pdf_bytes, dpi=dpi,
                                  first_page=page_nr_1based, last_page=page_nr_1based)
        if not imgs:
            return None
        buf = io.BytesIO()
        imgs[0].save(buf, format="PNG")
        return base64.standard_b64encode(buf.getvalue()).decode("ascii")
    except Exception as exc:  # noqa: BLE001
        print(f"[apdailos_reader] render page failed: {exc}")
        return None


def read_apdailos_finishes(
    pdf_bytes: bytes,
    rooms: list[dict],
    apdailos_page: Optional[int] = None,
    client=None,
) -> dict:
    """Read wall finish breakdown per room from the IŠKLOTINIŲ IR APDAILŲ
    PLANAS page.

    Returns {status, page, patalpos, _error, _elapsed_s, _meta}.
    """
    t0 = time.time()
    pages = [apdailos_page] if apdailos_page else _find_apdailos_pages(pdf_bytes)
    if not pages:
        return {"status": "skipped", "page": None, "patalpos": [],
                "_error": "no apdailos page found", "_elapsed_s": round(time.time() - t0, 2),
                "_meta": {}}
    content: list[dict] = []
    rendered: list[int] = []
    for pg in pages:
        b64 = _render_page_b64(pdf_bytes, pg, dpi=150 if len(pages) > 3 else 200)
        if b64:
            content.append({"type": "text", "text": f"[Apdailos/išklotinių lapas, PDF psl. {pg}]"})
            content.append({"type": "image", "source": {"type": "base64",
                                                        "media_type": "image/png", "data": b64}})
            rendered.append(pg)
    page = rendered[0] if rendered else None
    if not rendered:
        return {"status": "error", "page": pages[0], "patalpos": [],
                "_error": "page render failed", "_elapsed_s": round(time.time() - t0, 2),
                "_meta": {}}
    user_text = build_user_text(rooms)
    if len(rendered) > 1:
        user_text += ("\n\nPASTABA: pateikti VISI projekto apdailos/išklotinių lapai "
                      "(po 1-2 patalpas lape). Surask kiekvienos patalpos lapą ir "
                      "skaityk apdailą iš jo žymėjimų/legendos.")
    content.append({"type": "text", "text": user_text})
    try:
        model = model_for("apdailos")  # call-time resolution (MODEL_OVERRIDE etc.)
        client = client or anthropic.Anthropic()
        resp = client.messages.create(
            model=model, max_tokens=MAX_TOKENS,
            system=[{"type": "text", "text": SYSTEM_PROMPT,
                     "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": content}],
        )
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "page": page, "patalpos": [],
                "_error": f"Vision call failed: {exc}",
                "_elapsed_s": round(time.time() - t0, 2), "_meta": {}}

    raw = resp.content[0].text if getattr(resp, "content", None) else ""
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return {"status": "error", "page": page, "patalpos": [],
                "_error": "no JSON in response", "_raw_excerpt": raw[:500],
                "_elapsed_s": round(time.time() - t0, 2), "_meta": {}}
    try:
        parsed = json.loads(m.group(0))
    except json.JSONDecodeError as je:
        return {"status": "error", "page": page, "patalpos": [],
                "_error": f"JSON parse error: {je}", "_raw_excerpt": raw[:500],
                "_elapsed_s": round(time.time() - t0, 2), "_meta": {}}

    usage = getattr(resp, "usage", None)
    return {
        "status": "ok", "page": page, "pages": rendered,
        "patalpos": parsed.get("patalpos") or [],
        "_error": None, "_elapsed_s": round(time.time() - t0, 2),
        "_meta": {"input_tokens": getattr(usage, "input_tokens", None),
                  "output_tokens": getattr(usage, "output_tokens", None),
                  "model": model},
    }


def merge_apdailos_into_rooms(rooms: list[dict], apdailos_result: dict) -> int:
    """Attach apdailos finish shares to each matching room (by nr).

    Mutates `rooms` in place. Returns number of rooms updated.

    On each room, sets:
        room["sienu_apdailos_breakdown"] = {dazymas_share, plyteles_share, ...}
        room["plyteliu_aukstis_m"] = number | None  (only if not already set)
        room["_apdailos_pastabos"] = str
    """
    if apdailos_result.get("status") != "ok":
        return 0
    by_nr = {str(p.get("nr")): p for p in (apdailos_result.get("patalpos") or [])}
    n = 0
    for room in rooms:
        p = by_nr.get(str(room.get("nr")))
        if not p:
            continue
        breakdown = p.get("sienu_apdaila")
        if breakdown:
            room["sienu_apdailos_breakdown"] = breakdown
        if room.get("plyteliu_aukstis_m") is None and p.get("plyteliu_aukstis_m") is not None:
            room["plyteliu_aukstis_m"] = p.get("plyteliu_aukstis_m")
        if p.get("pastabos"):
            room["_apdailos_pastabos"] = p.get("pastabos")
            # 2026-06-11 (Bacevičiaus experiment): the reader SELF-REPORTS when
            # it is guessing ("low confidence; spėjimas pagal paskirtį" on 8/15
            # rooms) — and that signal was ignored while the guessed finishes
            # flowed into 🟢 paint quantities. Propagate it so the confidence
            # post-pass can demote finish-derived lines.
            low = p["pastabos"].lower()
            if "low confidence" in low or "spėjim" in low or "spejim" in low:
                room["_apdailos_confidence"] = "low"
        n += 1
    return n
