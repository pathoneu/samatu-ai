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
# Raised 2026-07-29 for the SAME reason apdailos_reader was (see its comment):
# Opus 5 runs extended thinking BY DEFAULT and it counts against this cap, so a
# snug max_tokens is shared between a variable-length thinking block and the
# answer — the answer gets cut mid-JSON and the reader silently returns nothing.
# Measured on apdailos: 2,776 output tokens one run, 4,757 the next, same PDF.
# 16384 leaves ~14k for thinking and stays under the SDK non-streaming ceiling
# (MAX_TOKENS_NONSTREAMING_CEILING = 21_333, above which the client raises
# before any HTTP call).
MAX_TOKENS = 16384
# Keep each rendered page's long edge under Claude's silent-downscale threshold so
# small door tags/annotations stay legible (research #2). 1568 px is the pre-Opus
# limit; staying at/below it guarantees no provider downscale.
from .prompt import PROVIDER_MAX_IMG_PX as MAX_IMG_PX  # 2576 on Opus 4.8 (was 1568)
from .response_text import read_answer, run_until_refused, stopped_round_metas, usage_meta
MAX_DOOR_PAGES = 6

# A door TAG: D-1, D1, VD-2. Case-sensitive and without „LD" (2026-09-23, checked on the corpus): the LD-1 /
# LD-2 / LD-3 the earlier pattern took for door tags on objektas_a are the CURTAIN-NICHE details of the
# ceiling plan, and the lowercase d1 … d4 it matched on two more sheets are fragments of running text.
_TAG_RE = re.compile(r"\b(?:D|VD|ID)-?\d{1,2}\b")
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
    pages = (_find_door_pages(pdf_bytes, page_classifications) if page_classifications
             else _find_door_pages(pdf_bytes))
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
        client = client or anthropic.Anthropic(max_retries=1)
        resp = client.messages.create(
            model=model, max_tokens=MAX_TOKENS,
            system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": content}],
        )
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "pages": rendered, "beapvadines_count": 0,
                "_error": f"Vision call failed: {exc}", "_elapsed_s": round(time.time() - t0, 2)}

    # Text blocks only — block 0 is a ThinkingBlock on thinking-enabled
    # models, and reading .text off it killed this reader mid-run.
    raw, stopped = read_answer(resp, reader="door_type_reader", page=rendered)
    # Billed whatever the answer says: every return from here on carries the
    # call's usage (2026-10-05: the no-JSON and broken-JSON returns did not).
    meta = usage_meta(resp, model)
    if stopped:  # refused / cut off: named, billed tokens kept (2026-09-30)
        return {"status": "error", "pages": rendered, "beapvadines_count": 0,
                "_error": stopped, "_elapsed_s": round(time.time() - t0, 2), "_meta": meta}
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return {"status": "error", "pages": rendered, "beapvadines_count": 0,
                "_error": "no JSON", "_raw": raw[:400], "_elapsed_s": round(time.time() - t0, 2),
                "_meta": meta}
    try:
        parsed = json.loads(m.group(0))
    except json.JSONDecodeError as je:
        return {"status": "error", "pages": rendered, "beapvadines_count": 0,
                "_error": f"JSON parse: {je}", "_raw": raw[:400], "_elapsed_s": round(time.time() - t0, 2),
                "_meta": meta}

    return {
        "status": "ok", "pages": rendered,
        "doors": parsed.get("doors") or [],
        "beapvadines_count": _safe_count(parsed.get("beapvadines_count")),
        "standartines_count": _safe_count(parsed.get("standartines_count")),
        "stumdomos_count": _safe_count(parsed.get("stumdomos_count")),
        "bendras_tipas": parsed.get("bendras_tipas"),
        "pastabos": parsed.get("pastabos"),
        "_elapsed_s": round(time.time() - t0, 2),
        "_meta": meta,
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
        if not runs:
            return {"status": "error", "beapvadines_count": 0}
        stopped = stopped_round_metas(runs)  # billed rounds without a usable answer
        return {**runs[0], "_round_metas": stopped} if stopped else runs[0]
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
    out["_round_metas"] = ([r.get("_meta") or {} for r in ok]
                           + stopped_round_metas(runs))
    return out


def read_door_types_voted(pdf_bytes: bytes, rooms: list[dict],
                          page_classifications: Optional[list] = None,
                          client=None, n: int = 3) -> dict:
    """Self-consistency wrapper: run read_door_types n times, median/mode-vote the
    counts (Opus 4.8 has no temperature knob — sampling N times is the only
    stability lever for this recall-critical single-pass reader)."""
    runs = run_until_refused(
        lambda: read_door_types(pdf_bytes, rooms, page_classifications, client), n)
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
