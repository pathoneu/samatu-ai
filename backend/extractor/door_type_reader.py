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
  - Measured failure it fixes: Beržų frameless doors tagged 2 of ~8 → "Durų angų
    paruošimas beapvadinėms durims" 10.2 m vs contractor 39.2 m.

The result is RECONCILED against the glyph-detected count and any disagreement is
SURFACED as a confidence flag (geltona) — never silently overwritten. The merge
RAISES, never lowers, against a contradicting plan symbol, and a governing-note
default ("visos vidaus durys — beapvadinės") is applied only on the premium
archetype, flagged. (Rejected: silent max(); blunt archetype default.)
"""
from __future__ import annotations

import base64
import io
import json
import re
import statistics
import time
from typing import Optional

import anthropic
import pdfplumber
from pdf2image import convert_from_bytes

from models_config import model_for  # role: "doors" — resolved at call time
MAX_TOKENS = 4096
# Keep each rendered page's long edge under Claude's silent-downscale threshold so
# small door tags/annotations stay legible (research #2). 1568 px is the pre-Opus
# limit; staying at/below it guarantees no provider downscale.
from .prompt import PROVIDER_MAX_IMG_PX as MAX_IMG_PX  # 2576 on Opus 4.8 (was 1568)
MAX_DOOR_PAGES = 6

_TAG_RE = re.compile(r"\b(?:LD|D)-?\d\b", re.IGNORECASE)
_PREMIUM = {"premium"}


def _safe_count(v, default: int = 0) -> int:
    """Coerce a Vision count to int; non-numeric (e.g. '3+', '3 durys', null) →
    default. A hallucinated non-numeric count must NOT ValueError-crash the whole
    door-type read and abort extraction (audit 2026-07-06 — sanitary_fixture_reader
    and doors_reader already had this; door_type_reader was the missed reader)."""
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default

SYSTEM_PROMPT = """Tu skaitai LT vidaus apdailos brėžinio DURŲ ŽYMĖJIMUS ir ANOTACIJAS — NE durų grafinį simbolį (lanką).

SVARBU: durų TIPO (beapvadinės vs standartinės) NEGALIMA nustatyti iš durų simbolio — jis abiem atvejais vienodas. Tipą skaityk TIK iš TEKSTO: durų žymių (pvz. LD-1, D-2), anotacijų (pvz. „Durų anga iki lubų, skirta beapvadinėms durims"), legendos ir pastabų (pvz. „18. Stumdomos durys").

Tavo darbas:
1. Suskaičiuok visas durų žymes/instancijas, kurias matai (pagal žymę ir kiekį).
2. Kiekvienai — perskaityk TIPĄ iš teksto: "beapvadines" (paslėpta stakta, anotacija „beapvadinėms durims"), "stumdomos" (slankiojančios), "standartines".
3. Jei brėžinyje yra BENDRA nuoroda visoms vidaus durims (pvz. „visos vidaus durys — beapvadinės") — užpildyk `bendras_tipas`.

Grąžink TIK JSON, jokios prozos, be markdown fences."""

_USER_SCHEMA = """

Output JSON:
{
  "doors": [{"zyme": "LD-1", "tipas": "beapvadines"|"standartines"|"stumdomos", "kiekis": number}],
  "beapvadines_count": number,
  "standartines_count": number,
  "stumdomos_count": number,
  "bendras_tipas": "beapvadines" | null,
  "pastabos": "trumpai — iš kur perskaitei tipą (anotacija/žymė/pastaba)"
}"""


def build_user_text(rooms: list[dict]) -> str:
    lines = ["Projekto patalpos (kontekstui — durys jungia šias patalpas):"]
    for r in rooms:
        lines.append(f"  {r.get('nr') or '?'} {r.get('pavadinimas') or ''}  ({r.get('plotas_m2')} m²)")
    lines.append("\nPerskaityk durų žymes/anotacijas/pastabas ir nustatyk kiek durų yra "
                 "BEAPVADINĖS (paslėpta stakta). Tipą imk iš TEKSTO, ne iš simbolio.")
    return "\n".join(lines) + _USER_SCHEMA


def _find_door_pages(pdf_bytes: bytes) -> list[int]:
    """1-based pages carrying door tags or type annotations (text-first). Skips
    pure title pages; prefers pages with door tags or 'beapvad'/'stumdom'/'durų anga'."""
    hits: list[tuple[int, int]] = []  # (priority, page)
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for i, page in enumerate(pdf.pages):
                t = (page.extract_text() or "")
                tl = t.lower()
                has_tag = bool(_TAG_RE.search(t))
                has_anno = ("beapvad" in tl or "stumdom" in tl or "durų anga" in tl
                            or "duru anga" in tl)
                if has_tag and has_anno:
                    hits.append((0, i + 1))
                elif has_tag or has_anno:
                    hits.append((1, i + 1))
    except Exception as exc:  # noqa: BLE001
        print(f"[door_type_reader] pdfplumber scan failed: {exc}")
    hits.sort()
    return [pg for _p, pg in hits[:MAX_DOOR_PAGES]]


def _render_page_b64(pdf_bytes: bytes, page_nr_1based: int) -> Optional[str]:
    """Render a page and cap its long edge at MAX_IMG_PX so door tags don't get
    silently downscaled to sub-pixel by the provider."""
    try:
        imgs = convert_from_bytes(pdf_bytes, dpi=200,
                                  first_page=page_nr_1based, last_page=page_nr_1based)
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
        print(f"[door_type_reader] render page {page_nr_1based} failed: {exc}")
        return None


def read_door_types(pdf_bytes: bytes, rooms: list[dict],
                    page_classifications: Optional[list] = None,
                    client=None) -> dict:
    """Read door types from the drawing text. Returns
    {status, pages, doors, beapvadines_count, standartines_count, stumdomos_count,
     bendras_tipas, _elapsed_s, _meta}."""
    t0 = time.time()
    pages = _find_door_pages(pdf_bytes)
    if not pages:
        return {"status": "skipped", "pages": [], "beapvadines_count": 0,
                "_error": "no door tag/annotation page found",
                "_elapsed_s": round(time.time() - t0, 2)}
    content: list[dict] = []
    rendered: list[int] = []
    for pg in pages:
        b64 = _render_page_b64(pdf_bytes, pg)
        if b64:
            content.append({"type": "text", "text": f"[Durų žymėjimų/anotacijų lapas, PDF psl. {pg}]"})
            content.append({"type": "image", "source": {"type": "base64",
                                                        "media_type": "image/png", "data": b64}})
            rendered.append(pg)
    if not rendered:
        return {"status": "error", "pages": pages, "beapvadines_count": 0,
                "_error": "page render failed", "_elapsed_s": round(time.time() - t0, 2)}
    content.append({"type": "text", "text": build_user_text(rooms)})
    try:
        model = model_for("doors")  # call-time resolution (MODEL_OVERRIDE etc.)
        client = client or anthropic.Anthropic()
        resp = client.messages.create(
            model=model, max_tokens=MAX_TOKENS,
            system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": content}],
        )
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "pages": rendered, "beapvadines_count": 0,
                "_error": f"Vision call failed: {exc}", "_elapsed_s": round(time.time() - t0, 2)}

    raw = resp.content[0].text if getattr(resp, "content", None) else ""
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return {"status": "error", "pages": rendered, "beapvadines_count": 0,
                "_error": "no JSON", "_raw": raw[:400], "_elapsed_s": round(time.time() - t0, 2)}
    try:
        parsed = json.loads(m.group(0))
    except json.JSONDecodeError as je:
        return {"status": "error", "pages": rendered, "beapvadines_count": 0,
                "_error": f"JSON parse: {je}", "_raw": raw[:400], "_elapsed_s": round(time.time() - t0, 2)}

    usage = getattr(resp, "usage", None)
    return {
        "status": "ok", "pages": rendered,
        "doors": parsed.get("doors") or [],
        "beapvadines_count": _safe_count(parsed.get("beapvadines_count")),
        "standartines_count": _safe_count(parsed.get("standartines_count")),
        "stumdomos_count": _safe_count(parsed.get("stumdomos_count")),
        "bendras_tipas": parsed.get("bendras_tipas"),
        "pastabos": parsed.get("pastabos"),
        "_elapsed_s": round(time.time() - t0, 2),
        "_meta": {"input_tokens": getattr(usage, "input_tokens", None),
                  "output_tokens": getattr(usage, "output_tokens", None), "model": model},
    }


def _mode_int(values, default: int = 0) -> int:
    """Mode of integer reads, MEDIAN on a tie. NOT max — max would covertly
    drift the count up toward the oracle (the thing the culture forbids)."""
    vals = [_safe_count(v) for v in values if v is not None]
    if not vals:
        return default
    modes = statistics.multimode(vals)
    if len(modes) == 1:
        return modes[0]
    return int(round(statistics.median(vals)))


def _aggregate_door_votes(runs: list[dict]) -> dict:
    """Median/mode-aggregate N read_door_types runs. Keeps the representative
    run's shape, overrides the counts with the voted value, and records the
    spread so the caller can flag run-to-run disagreement (geltona)."""
    ok = [r for r in runs if r.get("status") == "ok"]
    if not ok:
        return runs[0] if runs else {"status": "error", "beapvadines_count": 0}
    beap_vals = [int(r.get("beapvadines_count") or 0) for r in ok]
    beap = _mode_int(beap_vals)
    rep = next((r for r in ok if int(r.get("beapvadines_count") or 0) == beap), ok[0])
    out = dict(rep)
    out["beapvadines_count"] = beap
    out["standartines_count"] = _mode_int([int(r.get("standartines_count") or 0) for r in ok])
    out["stumdomos_count"] = _mode_int([int(r.get("stumdomos_count") or 0) for r in ok])
    out["_vote"] = {"n": len(ok), "beapvadines_values": beap_vals,
                    "spread": max(beap_vals) - min(beap_vals)}
    # Cost metering (2026-07-04): voting made N Anthropic calls, but only the
    # representative round's _meta survived above — the other rounds' tokens
    # were dropped, undercounting spend. Expose EVERY OK round's _meta so the
    # extraction flow can roll each into _meta.extra_calls (priced per-model).
    out["_round_metas"] = [r.get("_meta") or {} for r in ok]
    return out


def read_door_types_voted(pdf_bytes: bytes, rooms: list[dict],
                          page_classifications: Optional[list] = None,
                          client=None, n: int = 3) -> dict:
    """Self-consistency wrapper: run read_door_types n times, median/mode-vote the
    counts (Opus 4.8 has no temperature knob — sampling N times is the only
    stability lever for this recall-critical single-pass reader)."""
    runs = [read_door_types(pdf_bytes, rooms, page_classifications, client)
            for _ in range(max(1, n))]
    return _aggregate_door_votes(runs)


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
                           f"; pritaikyta visoms {n_interior_doors} vidaus durims (pradinis pass rado {plan}) — patikrink")}
    if bendras_tipas == "beapvadines" and not premium:
        # Surface the governing note but don't auto-expand on a non-premium project.
        return {"count": max(plan, reader), "confidence": "geltona",
                "reason": f"Pastaba mini beapvadines duris, bet archetipas ne premium — pritaikyta tik aiškiai pažymėtoms ({max(plan, reader)}); patikrink"}

    if reader > plan:
        return {"count": reader, "confidence": "geltona",
                "reason": f"Anotacijose/žymėse rasta {reader} beapvadinių durų, pradinis pass rado {plan} — patikrink"}
    if reader < plan and reader > 0:
        # conflict — keep the plan count, surface both, never silently lower
        return {"count": plan, "confidence": "geltona",
                "reason": f"Plane rasta {plan} beapvadinių durų, žymėse/anotacijose {reader} — nesutampa, patikrink"}
    # agree (or reader gave nothing): trust the plan count
    if reader == plan and reader > 0:
        return {"count": plan, "confidence": "zalia", "reason": ""}
    return {"count": plan, "confidence": "zalia" if plan else "geltona",
            "reason": "" if plan else "Durų tipo teksto nerasta — beapvadinių durų skaičius nepatikrintas"}
