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
import statistics
import time
from typing import Optional

import anthropic
import pdfplumber
from pdf2image import convert_from_bytes

from models_config import model_for  # role: "sanitary" — resolved at call time
# Raised 2026-07-29 for the SAME reason apdailos_reader was (see its comment):
# Opus 5 runs extended thinking BY DEFAULT and it counts against this cap, so a
# snug max_tokens is shared between a variable-length thinking block and the
# answer — the answer gets cut mid-JSON and the reader silently returns nothing.
# Measured on apdailos: 2,776 output tokens one run, 4,757 the next, same PDF.
# 16384 leaves ~14k for thinking and stays under the SDK non-streaming ceiling
# (MAX_TOKENS_NONSTREAMING_CEILING = 21_333, above which the client raises
# before any HTTP call).
MAX_TOKENS = 16384
from .prompt import PROVIDER_MAX_IMG_PX as MAX_IMG_PX  # 2576 on Opus 4.8 (was 1568)
from .response_text import response_text
# `bide` added 2026-07-29: the contractor bills "Bide dušiukų potinkinės dalies
# įrengimas" + "…virštinkinės dalies montavimas" on berzas AND objektas_b, and
# no reader produced the count — the emit layer could only raise a kiekis=null
# checklist row. It is enumerable (see the prompt below), so it is a fixture,
# not a TODO.
# `plautuves` added 2026-07-29: the prompt used to say "praustuvės/kriauklės",
# and "kriauklė" covers a KITCHEN sink — so a live probe on berzas enumerated
# the virtuvės and skalbyklos plautuvės inside praustuves_count (4 = 2 real
# praustuvės + 2 plautuvės, 3/3 voting rounds agreeing). The emit layer bills
# "Plautuvės montavimas" off a separate room-type count, so on any project with
# a room classified `virtuve` the same sink was billed twice. Praustuvė and
# plautuvė are separate contractor lines (lazunu nr 32/33 bills both), so they
# get separate keys here and each line consumes exactly one of them.
_FIXTURE_KEYS = ("praustuves", "plautuves", "klozetai", "vonios", "dusai",
                 "wc_remai", "bide")

SYSTEM_PROMPT = """Tu skaitai LT santechnikos / vandentiekio brėžinį.

SVARBU: ENUMERUOK kiekvieną santechnikos prietaisą ATSKIRU įrašu (point-list) — NE bendrą skaičių iš akies. Tankūs simboliai praleidžiami, jei skaičiuoji „iš akies"; surašyk kiekvieną atskirai ir tik tada suskaičiuok.

Ieškok: praustuvės (vonios/WC/san. mazgo praustuvai), plautuvės (virtuvės/skalbyklos kriauklės), klozetai (WC rėmai), vonios, dušai (dušo galvos/trapai), bidė dušiukai (higieniniai dušai).

KAIP ATSKIRTI (čia daromos klaidos):
· PRAUSTUVĖ = rankų plovimo praustuvas DRĖGNOJE patalpoje (vonia, WC, san. mazgas). PLAUTUVĖ = virtuvės arba skalbyklos kriauklė (indams, ūkinė). Sąmatoje tai DVI ATSKIROS eilutės, todėl virtuvės ar skalbyklos kriauklė NIEKADA nėra praustuvė — rašyk ją kaip „plautuve". Sprendžia PATALPA, kurioje yra taškas, ne simbolio forma: „maišytuvo pajungimas iš stalviršio" virtuvėje = plautuvė; toks pat simbolis vonioje = praustuvė. Jei patalpa nenurodyta ir negali nuspręsti — rašyk praustuve.
· VONIA = maudymosi vonia — didelis stačiakampis arba ovalas užapvalintais galais, dažnai su prierašu „vonia". DUŠAS = dušo zona: dušo galva, trapas arba linijinis latakas, dušo padėklas. Dušo padėklas NĖRA vonia. Jei nesi tikras, kad tai vonia — įrašyk kaip dušą. Vonia ir dušas skaičiuojami ATSKIRAI, net kai yra toje pačioje patalpoje.
· BIDĖ DUŠIUKAS (higieninis dušas) = mažas potinkinis vandens taškas arba maišytuvo dalis SIENOJE ŠALIA KLOZETO, dažnai su altitude h≈1000–1100 mm. Tai nėra dušas (dušas turi galvą ir trapą) ir nėra atskiras pastatomas bidė unitazas. LT brėžiniuose žodis „bidė" dažnai NEparašomas — atpažįstama iš vietos (prie klozeto) ir altitudės.
· Bidė kiekio NIEKADA nespėk pagal klozetų kiekį — jie nesutampa. Skaičiuok tik tuos taškus, kuriuos MATAI brėžinyje; jei nė vieno nematai, rašyk 0.

Grąžink TIK JSON, jokios prozos, be markdown fences."""

_USER_SCHEMA = """

Output JSON:
{
  "prietaisai": [{"tipas": "praustuve"|"plautuve"|"klozetas"|"vonia"|"dusas"|"bide"|"kita", "vieta": "trumpa nuoroda (patalpa/altitudė)"}],
  "praustuves_count": number,
  "plautuves_count": number,
  "klozetai_count": number,
  "vonios_count": number,
  "dusai_count": number,
  "wc_remai_count": number,
  "bide_count": number,
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


# Roles a santechnikos planas can never have. Used only to VETO a text hit —
# `floor_plan` is deliberately absent, because a combined plan legitimately
# carries the plumbing layout.
_NON_PLUMBING_TIPAI = frozenset({
    "electrical", "ceiling_plan", "wall_elevation", "non_relevant", "title_page",
    "finish_schedule", "specification", "section", "site_plan", "facade",
    "structural",
})
# Title-block words — present on the sheet that IS the plumbing plan.
_TITLE_HINTS = ("SANTECH", "VANDENTIEK")
# An annotation any drawing may carry (every išklotinė that labels a mixer
# matches it), so it only decides when no title-block hit exists.
_WEAK_HINTS = ("MAIŠYTUV", "MAISYTUV")


def _find_sanitary_pages(pdf_bytes: bytes, pages_meta: list[dict] | None = None,
                         limit: int = 2) -> list[int]:
    """Pick the santechnikos-plano page(s) to read, best evidence first.

    1. pages the page classifier already labelled `plumbing` — the only
       POSITIVE signal that a sheet is the plumbing plan;
    2. pages whose text carries a title-block word (SANTECHNIKOS/VANDENTIEKIS);
    3. pages that merely mention a maišytuvas.
    Tiers 2-3 drop any page the classifier assigned to a different role.

    WHY (2026-07-29 audit of all 6 registry PDFs): the old bare-text scan took
    the first two hits in page order, so on romainiai it read two išklotinės
    (pages 16-17, "maišytuvas" annotations) while the sheets naming SANTECHNIKA
    sat at 23-24 — and those two are the apšvietimo planas, i.e. that project
    has no plumbing sheet at all. On objektas_b it burned one of the two slots
    on the baldų planas (page 2). Both cases count fixtures off a drawing that
    is not a plumbing plan. berzas is unaffected (page 4 is classified
    `plumbing` and is the only hit either way).
    """
    role: dict[int, str] = {}
    for p in pages_meta or []:
        try:
            nr = int(p.get("nr"))
        except (TypeError, ValueError):
            continue
        if nr >= 1:                       # a classifier can emit nr=0/null
            role[nr] = (p.get("tipas") or "").lower()
    classified = sorted(nr for nr, t in role.items() if t == "plumbing")
    if classified:
        return classified[:limit]
    strong: list[int] = []
    weak: list[int] = []
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for i, page in enumerate(pdf.pages):
                nr = i + 1
                if role.get(nr) in _NON_PLUMBING_TIPAI:
                    continue
                t = (page.extract_text() or "").upper()
                if any(h in t for h in _TITLE_HINTS):
                    strong.append(nr)
                elif any(h in t for h in _WEAK_HINTS):
                    weak.append(nr)
    except Exception as exc:  # noqa: BLE001
        print(f"[sanitary_fixture_reader] scan failed: {exc}")
    return (strong or weak)[:limit]


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


def read_fixtures(pdf_bytes: bytes, rooms: list[dict], client=None,
                  pages_meta: list[dict] | None = None) -> dict:
    """Point-list-then-count of sanitary fixtures. Returns
    {status, pages, counts:{praustuves,klozetai,...}, prietaisai, _elapsed_s, _meta}.

    `pages_meta` is the main pass's `puslapiai` page classification; passing it
    lets the page picker use the `plumbing` label instead of guessing from text.
    """
    t0 = time.time()
    pages = _find_sanitary_pages(pdf_bytes, pages_meta)
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
        model = model_for("sanitary")  # call-time resolution (MODEL_OVERRIDE etc.)
        client = client or anthropic.Anthropic(max_retries=1)
        resp = client.messages.create(
            model=model, max_tokens=MAX_TOKENS,
            system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": content}],
        )
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "_error": f"Vision call failed: {exc}",
                "_elapsed_s": round(time.time() - t0, 2)}
    # Text blocks only — block 0 is a ThinkingBlock on thinking-enabled
    # models, and reading .text off it killed this reader mid-run.
    raw = response_text(resp)
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
        # Coerce defensively: a non-numeric count (e.g. "3+") must not
        # ValueError-crash the whole read and abort fixture reconciliation. (audit 2026-07-05)
        "counts": {k: _safe_count(parsed.get(f"{k}_count")) for k in _FIXTURE_KEYS},
        "prietaisai": parsed.get("prietaisai") or [],
        "_elapsed_s": round(time.time() - t0, 2),
        "_meta": {"input_tokens": getattr(usage, "input_tokens", None),
                  "output_tokens": getattr(usage, "output_tokens", None), "model": model},
    }


def _safe_count(v, default: int = 0) -> int:
    """Coerce a Vision count to int; non-numeric (e.g. '3+', null) → default."""
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def _mode_int(values, default: int = 0) -> int:
    """Mode of integer reads, MEDIAN on a tie (not max — no covert oracle drift)."""
    vals = [_safe_count(v) for v in values if v is not None]
    if not vals:
        return default
    modes = statistics.multimode(vals)
    if len(modes) == 1:
        return modes[0]
    return int(round(statistics.median(vals)))


def _aggregate_fixture_votes(runs: list[dict]) -> dict:
    """Median/mode-aggregate N read_fixtures runs per fixture key + record spread."""
    ok = [r for r in runs if r.get("status") == "ok"]
    if not ok:
        return runs[0] if runs else {"status": "error"}
    out = dict(ok[0])
    merged = {}
    spread = {}
    for k in _FIXTURE_KEYS:
        vals = [int((r.get("counts") or {}).get(k) or 0) for r in ok]
        merged[k] = _mode_int(vals)
        spread[k] = max(vals) - min(vals)
    out["counts"] = merged
    out["_vote"] = {"n": len(ok), "spread": spread}
    # Cost metering (2026-07-04): voting made N Anthropic calls, but only ok[0]'s
    # _meta survived above. Expose EVERY OK round's _meta so the extraction flow
    # can roll each into _meta.extra_calls (priced per-model).
    out["_round_metas"] = [r.get("_meta") or {} for r in ok]
    return out


def read_fixtures_voted(pdf_bytes: bytes, rooms: list[dict], client=None, n: int = 3,
                        pages_meta: list[dict] | None = None) -> dict:
    """Self-consistency wrapper: run read_fixtures n times, median/mode-vote each
    fixture count (the only stability lever on Opus 4.8 for this single-pass reader)."""
    runs = [read_fixtures(pdf_bytes, rooms, client, pages_meta) for _ in range(max(1, n))]
    return _aggregate_fixture_votes(runs)


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
    # `vonios` in the MAIN prompt means "vonios + dušo padėklai" — bathtubs and
    # shower trays in ONE integer (prompt.py). Merged with max() it stays
    # conflated, which is fine for the consumers that want every wet fixture
    # (skylių gręžimas), but it cannot decide whether a BATHTUB mixer exists:
    # a shower-only flat would be billed a vonios maišytuvas it never gets.
    # This reader counts tubs and showers separately, so publish its tub-only
    # number under its own key and leave `vonios` untouched. Absent key ⇒ no
    # tub evidence at all (reader skipped) — the emit layer must then ask,
    # not guess.
    if (reader_counts or {}).get("vonios") is not None:
        merged["vonios_kubilai"] = _safe_count(reader_counts.get("vonios"))
    return {"merged": merged, "raised": raised, "any_raised": bool(raised)}
