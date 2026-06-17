"""Sanitary-fixture reader — improve fixture COUNT recall via point-list-then-count
on the santechnikos (plumbing) plan.

WHY (2026-06-14, deep research #3): the main pass under-counts repeated sanitary
symbols (Beržų praustuvės read 3, truth 5) because a single "how many sinks?"
glance blurs dense symbols. Asking Claude to ENUMERATE each fixture as a list and
counting len() removes the blurry-glance error (FSC-147: point→label→count beats
bare-number counting). Live probe on Beržų: 3 → 4 praustuvės.

This does NOT solve fixture detection (no clean fixture schedule exists in LT TP
PDFs — research confirmed); it's a modest, honest recall bump. Counts are
RECONCILED with detected_symbols_summary (raise to the higher, flag the
disagreement) — never silently overwritten. Skylių-gręžimas + fixture lines
consume the reconciled counts.
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

MODEL = "claude-opus-4-8"
MAX_TOKENS = 4096
MAX_IMG_PX = 1568
_FIXTURE_KEYS = ("praustuves", "klozetai", "vonios", "dusai", "wc_remai")

SYSTEM_PROMPT = """Tu skaitai LT santechnikos / vandentiekio brėžinį.

SVARBU: ENUMERUOK kiekvieną santechnikos prietaisą ATSKIRU įrašu (point-list) — NE bendrą skaičių iš akies. Tankūs simboliai praleidžiami, jei skaičiuoji „iš akies"; surašyk kiekvieną atskirai ir tik tada suskaičiuok.

Ieškok: praustuvės/kriauklės (maišytuvo pajungimai), klozetai (WC rėmai), vonios, dušai (dušo galvos/trapai), bidė.

Grąžink TIK JSON, jokios prozos, be markdown fences."""

_USER_SCHEMA = """

Output JSON:
{
  "prietaisai": [{"tipas": "praustuve"|"klozetas"|"vonia"|"dusas"|"bide"|"kita", "vieta": "trumpa nuoroda (patalpa/altitudė)"}],
  "praustuves_count": number,
  "klozetai_count": number,
  "vonios_count": number,
  "dusai_count": number,
  "wc_remai_count": number,
  "pastabos": "trumpai"
}"""


def build_user_text(rooms: list[dict]) -> str:
    wet = [r for r in (rooms or [])
           if (r.get("paskirtis") or "").lower() in ("vonia", "wc", "san", "virtuve", "skalbykla")]
    lines = ["Drėgnos/santechnikos patalpos (kontekstui):"]
    for r in wet:
        lines.append(f"  {r.get('nr') or '?'} {r.get('pavadinimas') or ''}")
    lines.append("\nSurask ir IŠVARDINK kiekvieną santechnikos prietaisą plane atskiru įrašu, "
                 "tada suskaičiuok pagal tipą.")
    return "\n".join(lines) + _USER_SCHEMA


def _find_sanitary_pages(pdf_bytes: bytes) -> list[int]:
    hits: list[int] = []
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for i, page in enumerate(pdf.pages):
                t = (page.extract_text() or "").upper()
                if "SANTECH" in t or "MAIŠYTUV" in t or "MAISYTUV" in t or "VANDENTIEK" in t:
                    hits.append(i + 1)
    except Exception as exc:  # noqa: BLE001
        print(f"[sanitary_fixture_reader] scan failed: {exc}")
    return hits[:2]


def _render_page_b64(pdf_bytes: bytes, page_nr: int) -> Optional[str]:
    try:
        imgs = convert_from_bytes(pdf_bytes, dpi=200, first_page=page_nr, last_page=page_nr)
        if not imgs:
            return None
        img = imgs[0]
        if max(img.size) > MAX_IMG_PX:
            k = MAX_IMG_PX / max(img.size)
            img = img.resize((int(img.width * k), int(img.height * k)))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.standard_b64encode(buf.getvalue()).decode("ascii")
    except Exception as exc:  # noqa: BLE001
        print(f"[sanitary_fixture_reader] render {page_nr} failed: {exc}")
        return None


def read_fixtures(pdf_bytes: bytes, rooms: list[dict], client=None) -> dict:
    """Point-list-then-count of sanitary fixtures. Returns
    {status, pages, counts:{praustuves,klozetai,...}, prietaisai, _elapsed_s, _meta}."""
    t0 = time.time()
    pages = _find_sanitary_pages(pdf_bytes)
    if not pages:
        return {"status": "skipped", "_error": "no santechnika page",
                "_elapsed_s": round(time.time() - t0, 2)}
    content: list[dict] = []
    rendered: list[int] = []
    for pg in pages:
        b64 = _render_page_b64(pdf_bytes, pg)
        if b64:
            content.append({"type": "text", "text": f"[Santechnikos planas, PDF psl. {pg}]"})
            content.append({"type": "image", "source": {"type": "base64",
                                                        "media_type": "image/png", "data": b64}})
            rendered.append(pg)
    if not rendered:
        return {"status": "error", "_error": "render failed",
                "_elapsed_s": round(time.time() - t0, 2)}
    content.append({"type": "text", "text": build_user_text(rooms)})
    try:
        client = client or anthropic.Anthropic()
        resp = client.messages.create(
            model=MODEL, max_tokens=MAX_TOKENS,
            system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": content}],
        )
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "_error": f"Vision call failed: {exc}",
                "_elapsed_s": round(time.time() - t0, 2)}
    raw = resp.content[0].text if getattr(resp, "content", None) else ""
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return {"status": "error", "_error": "no JSON", "_raw": raw[:300],
                "_elapsed_s": round(time.time() - t0, 2)}
    try:
        parsed = json.loads(m.group(0))
    except json.JSONDecodeError as je:
        return {"status": "error", "_error": f"JSON parse: {je}",
                "_elapsed_s": round(time.time() - t0, 2)}
    usage = getattr(resp, "usage", None)
    return {
        "status": "ok", "pages": rendered,
        "counts": {k: int(parsed.get(f"{k}_count") or 0) for k in _FIXTURE_KEYS},
        "prietaisai": parsed.get("prietaisai") or [],
        "_elapsed_s": round(time.time() - t0, 2),
        "_meta": {"input_tokens": getattr(usage, "input_tokens", None),
                  "output_tokens": getattr(usage, "output_tokens", None), "model": MODEL},
    }


def reconcile_fixture_counts(symbols: dict, reader_counts: dict) -> dict:
    """Reconcile detected_symbols_summary with the point-list reader counts.

    RAISES each fixture count to the higher of the two (point-list enumeration
    catches symbols the full-sheet glance misses), and reports which were raised
    so the dependent lines can be flagged. Returns
    {merged: {...}, raised: [keys], any_raised: bool}."""
    merged = dict(symbols or {})
    raised: list[str] = []
    for k in _FIXTURE_KEYS:
        sym = int((symbols or {}).get(k) or 0)
        rd = int((reader_counts or {}).get(k) or 0)
        if rd > sym:
            merged[k] = rd
            raised.append(k)
        else:
            merged[k] = sym
    return {"merged": merged, "raised": raised, "any_raised": bool(raised)}
