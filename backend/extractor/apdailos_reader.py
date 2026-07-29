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
from .response_text import response_text

# 2026-07-29 — THE INTERMITTENT-FAILURE FIX. 4096 was too snug for THIS reader
# and it was truncating the answer mid-JSON on most runs:
#   measured on berzas (11 rooms, 12 išklotinių pages)
#     - full answer  ≈ 6 344 chars ≈ 2 400 output tokens
#     - the ONE success (10:38) reported output_tokens = 2 776 → thinking was
#       only ~370 tokens that run; it fit under 4 096 by ~1 300 tokens
#     - the two 12:0x failures died at char 3 664 and char 4 789 of the SAME
#       answer with `Expecting ',' delimiter` — i.e. the body stopped mid-object
#       at 58% and 79% of the way through. Thinking had eaten ~2 300-2 700 of
#       the cap. Opus 5 has thinking ON BY DEFAULT and it counts against
#       max_tokens, so a 4 096 cap on a ~2 400-token answer is a coin flip.
# Caps are FREE (billing is by actuals — see a709250), so buy real headroom:
# ~14k for thinking on top of the largest answer we have ever produced.
#
# CEILING — do not raise past 21_333 without switching to streaming. This is a
# NON-STREAMING call, and the SDK refuses non-streaming requests it predicts
# will exceed 10 minutes (_base_client._calculate_nonstreaming_timeout:
# 3600 * max_tokens / 128_000 > 600). At 21_334 it raises ValueError BEFORE any
# HTTP call — which this reader would classify as a non-retryable error and
# degrade on, i.e. the exact silent failure being fixed here, from a new cause.
# Raising the cap does NOT buy longer thinking either: on Opus 5 thinking depth
# is set by `output_config.effort` (default high), not by max_tokens — the cap
# only decides whether the answer fits alongside it.
MAX_TOKENS = 16384
MAX_TOKENS_NONSTREAMING_CEILING = 21_333

# CLAUDE.md: "every external API call: retry logic, max 3 retries". Bounded on
# purpose (a709250 capped retry multiplication) — only transport-class failures
# are retried. A `refusal` or a `max_tokens` stop_reason is NOT retried: the
# payload is unchanged, so a retry is a coin flip, not a fix (the fix for
# max_tokens is the cap above; the fix for a refusal is a human).
MAX_ATTEMPTS = 3
RETRY_SLEEP_S = 1.0  # × attempt number; monkeypatched to 0 in tests

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


def _find_apdailos_pages(pdf_bytes: bytes) -> list[int]:
    """ALL candidate finish pages (1-based), best-priority first.

    Large TPs carry per-room sienų išklotinės across MANY sheets (Rangovas B:
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


def _is_retryable(exc: Exception) -> bool:
    """True for transport-class failures that a second identical call can fix.

    Deliberately narrow: connection/timeout/rate-limit/5xx. A 400 (bad request),
    401/403 (auth) or 404 is deterministic — retrying it only burns time.
    """
    for name in ("APIConnectionError", "APITimeoutError", "RateLimitError",
                 "InternalServerError", "APIStatusError"):
        cls = getattr(anthropic, name, None)
        if cls is not None and isinstance(exc, cls):
            if name == "APIStatusError":  # only 429/5xx of the generic status class
                status = getattr(exc, "status_code", None)
                return status is not None and (status == 429 or status >= 500)
            return True
    return False


def _salvage_patalpos(raw: str) -> list[dict]:
    """Recover every COMPLETE room object from a truncated ``patalpos`` array.

    A body cut off by ``max_tokens`` is unparseable as a whole, but the rooms
    that DID arrive are intact JSON objects. Losing 11/11 rooms because the
    11th was half-written is the failure this reader kept shipping; recovering
    8/11 and disclosing the gap is strictly better (CLAUDE.md §"Honest
    disclosure beats clever fixes").
    """
    i = raw.find('"patalpos"')
    if i < 0:
        return []
    start = raw.find("[", i)
    if start < 0:
        return []
    dec = json.JSONDecoder()
    out: list[dict] = []
    pos = start + 1
    n = len(raw)
    while pos < n:
        while pos < n and raw[pos] in " \t\r\n,":
            pos += 1
        if pos >= n or raw[pos] != "{":
            break
        try:
            obj, pos = dec.raw_decode(raw, pos)
        except ValueError:
            break  # first incomplete object — everything after it is truncated
        if isinstance(obj, dict):
            out.append(obj)
    return out


def _parse_patalpos(raw: str) -> tuple[Optional[list[dict]], Optional[str]]:
    """(patalpos, note). ``None`` patalpos = hard failure, ``[]`` = the model
    genuinely returned no rooms, ``note`` set = salvaged from a broken body."""
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if m:
        try:
            parsed = json.loads(m.group(0))
        except json.JSONDecodeError as je:
            salvaged = _salvage_patalpos(raw)
            if salvaged:
                return salvaged, f"JSON parse error ({je}) — salvaged {len(salvaged)} patalpas"
            return None, f"JSON parse error: {je}"
        pat = parsed.get("patalpos") if isinstance(parsed, dict) else None
        if isinstance(pat, list):
            return [p for p in pat if isinstance(p, dict)], None
        return None, "response JSON has no 'patalpos' list"
    salvaged = _salvage_patalpos(raw)
    if salvaged:
        return salvaged, f"no complete JSON object — salvaged {len(salvaged)} patalpas"
    return None, "no JSON in response"


def read_apdailos_finishes(
    pdf_bytes: bytes,
    rooms: list[dict],
    apdailos_page: Optional[int] = None,
    client=None,
) -> dict:
    """Read wall finish breakdown per room from the IŠKLOTINIŲ IR APDAILŲ
    PLANAS page.

    Returns {status, page, pages, patalpos, _error, _elapsed_s, _meta} where
    ``status`` is one of:
      ok       — the whole answer parsed
      partial  — the body was cut short (or otherwise unparseable as a whole)
                 and only the rooms that fully arrived were salvaged; the
                 caller MUST still disclose (rooms without a breakdown fall
                 back to paskirtis defaults)
      error    — nothing usable; ``_error`` names the cause
      skipped  — no išklotinių/apdailų page in this PDF

    ``_meta`` is populated on EVERY path: model, pages, max_tokens, per-attempt
    log, stop_reason, token usage and (on failure) the exception class. A run
    artifact must never again leave a post-mortem guessing why this reader
    produced nothing.
    """
    t0 = time.time()
    pages = [apdailos_page] if apdailos_page else _find_apdailos_pages(pdf_bytes)
    if not pages:
        return {"status": "skipped", "page": None, "pages": [], "patalpos": [],
                "_error": "no apdailos page found", "_elapsed_s": round(time.time() - t0, 2),
                "_meta": {"pages": [], "page_source": "explicit" if apdailos_page else "scan"}}
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
        return {"status": "error", "page": pages[0], "pages": [], "patalpos": [],
                "_error": "page render failed", "_elapsed_s": round(time.time() - t0, 2),
                "_meta": {"pages": [], "candidate_pages": pages}}
    user_text = build_user_text(rooms)
    if len(rendered) > 1:
        user_text += ("\n\nPASTABA: pateikti VISI projekto apdailos/išklotinių lapai "
                      "(po 1-2 patalpas lape). Surask kiekvienos patalpos lapą ir "
                      "skaityk apdailą iš jo žymėjimų/legendos.")
    content.append({"type": "text", "text": user_text})

    model = model_for("apdailos")  # call-time resolution (MODEL_OVERRIDE etc.)
    client = client or anthropic.Anthropic(max_retries=1)
    # Every attempt is recorded — a post-mortem must be able to see WHY this
    # reader produced nothing without re-running a €2.5 extraction.
    attempts: list[dict] = []
    resp = None
    last_exc: Optional[Exception] = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            resp = client.messages.create(
                model=model, max_tokens=MAX_TOKENS,
                system=[{"type": "text", "text": SYSTEM_PROMPT,
                         "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": content}],
            )
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            retryable = _is_retryable(exc)
            attempts.append({"attempt": attempt, "outcome": "exception",
                             "error_class": type(exc).__name__,
                             "error": str(exc)[:200], "retryable": retryable})
            print(f"[apdailos_reader] attempt {attempt}/{MAX_ATTEMPTS} failed "
                  f"({type(exc).__name__}): {exc}")
            if retryable and attempt < MAX_ATTEMPTS:
                time.sleep(RETRY_SLEEP_S * attempt)
                continue
            break
        attempts.append({"attempt": attempt, "outcome": "response",
                         "stop_reason": getattr(resp, "stop_reason", None)})
        break

    def _meta(**extra) -> dict:
        usage = getattr(resp, "usage", None)
        m = {"model": model, "pages": rendered, "max_tokens": MAX_TOKENS,
             "attempts": attempts, "attempt_count": len(attempts),
             "stop_reason": getattr(resp, "stop_reason", None),
             # Tokens on EVERY path, not just success: a truncated call is a
             # billed call, and an unmetered euro is a dishonest euro (a709250).
             "input_tokens": getattr(usage, "input_tokens", None),
             "output_tokens": getattr(usage, "output_tokens", None),
             "cache_read_tokens": getattr(usage, "cache_read_input_tokens", None),
             "cache_write_tokens": getattr(usage, "cache_creation_input_tokens", None)}
        m.update(extra)
        return m

    if resp is None:
        return {"status": "error", "page": page, "pages": rendered, "patalpos": [],
                "_error": f"Vision call failed after {len(attempts)} attempt(s): {last_exc}",
                "_elapsed_s": round(time.time() - t0, 2),
                "_meta": _meta(error_class=type(last_exc).__name__ if last_exc else None)}

    stop_reason = getattr(resp, "stop_reason", None)
    if stop_reason == "refusal":
        # HTTP 200 with an empty body — a safety classifier stopped it. Never
        # retried (identical payload); disclosed instead.
        return {"status": "error", "page": page, "pages": rendered, "patalpos": [],
                "_error": "safety refusal (stop_reason=refusal)",
                "_elapsed_s": round(time.time() - t0, 2), "_meta": _meta()}

    # Text blocks only — block 0 is a ThinkingBlock on thinking-enabled
    # models, and reading .text off it killed this reader mid-run.
    raw = response_text(resp)
    patalpos, note = _parse_patalpos(raw)
    truncated = stop_reason == "max_tokens"
    if patalpos is None:
        reason = note or "no JSON in response"
        if truncated:
            reason = (f"atsakymas nutrūko ties max_tokens={MAX_TOKENS} "
                      f"(nepavyko išgelbėti nė vienos patalpos): {reason}")
        return {"status": "error", "page": page, "pages": rendered, "patalpos": [],
                "_error": reason, "_raw_excerpt": raw[:500],
                "_elapsed_s": round(time.time() - t0, 2),
                "_meta": _meta(truncated=truncated, raw_chars=len(raw))}

    # A truncated-but-salvaged read is NOT "ok" — the rooms that never arrived
    # must keep falling back visibly (the caller warns on "partial").
    partial = bool(truncated or note)
    if truncated and not note:
        # Parsed cleanly but the body still hit the cap — the rooms after the
        # cut never arrived. Name it rather than reporting a reasonless partial.
        note = f"atsakymas nutrūko ties max_tokens={MAX_TOKENS}"
    return {
        "status": "partial" if partial else "ok",
        "page": page, "pages": rendered,
        "patalpos": patalpos,
        "_error": note if partial else None,
        "_elapsed_s": round(time.time() - t0, 2),
        "_meta": _meta(truncated=truncated, raw_chars=len(raw),
                       salvaged=bool(note), rooms_returned=len(patalpos)),
    }


def merge_apdailos_into_rooms(rooms: list[dict], apdailos_result: dict) -> int:
    """Attach apdailos finish shares to each matching room (by nr).

    Mutates `rooms` in place. Returns number of rooms updated.

    On each room, sets:
        room["sienu_apdailos_breakdown"] = {dazymas_share, plyteles_share, ...}
        room["plyteliu_aukstis_m"] = number | None  (only if not already set)
        room["_apdailos_pastabos"] = str
    """
    # "partial" = the body was truncated and only some rooms survived. Merging
    # them is right — the rooms that did NOT arrive simply keep no breakdown,
    # so universal_rules still marks them `_tile_read_missing` and the caller
    # still fires the degradation warning.
    if apdailos_result.get("status") not in ("ok", "partial"):
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
