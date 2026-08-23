"""extractor.eksplikacija_reader — focused pre-pass Vision call for LT schedule tables.

Why a pre-pass?
    Main Vision extractor reads room areas via dimension-chain inference, which
    has 5-22% CV across runs (Phase 6.5.2). LT projects almost always include
    an EKSPLIKACIJA (room schedule) and DURŲ/LANGŲ SPECIFIKACIJOS (door/window
    schedules) — these tables hold EXACT values. Reading them first and using
    them as anchors in the main extract eliminates inference variance for
    rooms/openings that are listed in the tables.

This module performs ONLY table extraction. It never infers — if a table is
not present on any page, it returns empty arrays. Failure modes are soft:
on hard error returns a result with `_error` set and empty payload arrays.
"""
from __future__ import annotations

import json
import re as _re
import time
from typing import Any

import anthropic

from models_config import model_for  # call-time model resolution
from .vision_call import pdf_to_b64_images

__all__ = ["read_eksplikacija"]


# =============================================================================
# PROMPT — Lithuanian, table-only, no inference
# =============================================================================
SYSTEM_TEXT = """Tu esi LT statybinių brėžinių lentelių parser'is. Tavo VIENINTELĖ užduotis — iš pateiktų PDF puslapių rasti ir tiksliai nuskaityti šias lenteles:

1) EKSPLIKACIJA (patalpų sąrašas, dažniausiai stulpeliai: Nr., Pavadinimas, Plotas m², kartais Perimetras m, Lubų aukštis m).
2) DURŲ SPECIFIKACIJA (durų sąrašas: žymėjimas D1/D2/..., plotis mm, aukštis mm, tipas, kiekis).
3) LANGŲ SPECIFIKACIJA (langų sąrašas: žymėjimas L1/L2/..., plotis mm, aukštis mm, tipas, kiekis).

GRIEŽTOS TAISYKLĖS:
- Grąžink TIK strukturuotą JSON pagal nurodytą schemą. Jokio markdown, jokių paaiškinimų, jokių ```json``` blokų.
- NIEKADA NEINFERINK reikšmių. Jei lentelės nėra arba langelio reikšmė neaiški — palik tuščią masyvą arba lauką null.
- Lietuviški simboliai (ąčęėįšųūžĄČĘĖĮŠŲŪŽ) PRIVALO būti išsaugoti tiksliai.
- Patalpų numeriai gali būti formato "M01", "1.01", "101", "K-01" — palik EXACT kaip lentelėje.
- Plotas matuojamas m² (kvadratiniais metrais), perimetras m (metrais).

**KRITIŠKAI SVARBU — DECIMAL TIKSLUMAS (du-žingsnių procesas):**

Kiekvienai skaitinei reikšmei (plotas, perimetras, lubų aukštis, plotis_mm, aukštis_mm) PRIVALAI:

ŽINGSNIS 1: Pridėk `_raw_text` lauką su EXACT tuo, ką matai langelyje, simbolis-į-simbolį.
   - Pavyzdys: jei langelyje matosi `63,45`, tu rašai `_raw_text: "63,45"`.
   - Pavyzdys: jei langelyje yra `12.30 m²`, tu rašai `_raw_text: "12.30 m²"`.
   - Tai užtikrina, kad nieko neapvalinai mintyse — kopijuoji raides.

ŽINGSNIS 2: TIK po ŽINGSNIO 1, parse'ink į numeric lauką:
   - Pakeisk lietuvišką kablelį `,` į tašką `.`
   - Atmesk vienetus (`m`, `m²`, `mm`, `vnt.`)
   - **Išsaugok VISUS decimal'us** — `63,45` → `63.45` (NE `63.4`).
   - **NIEKADA neapvalink** „kad būtų tvarkingiau". Sistema priima ir `63.45`, ir `63.4500001`.

GRIEŽTAS DRAUDIMAS:
- Negalvok „šitą galima suapvalinti iki 1 decimal place". JOKIO apvalinimo.
- Klaidos čia kainuoja tikslumą: 63.45 vs 63.4 = 0.05 m² delta × 15 patalpų = 0.75 m² = realūs pinigai.
- Jei abejoji ar gerai matai — žiūrėk vaizdą didesnėje rezoliucijoje (tu turi access).
- Jei langelis tikrai blur'is ir nematyti paskutinio decimal — palik `null` su pastaba `"_raw_text": "63,4? (paskutinis skaičius neaiškus)"`.

- Durų/langų matmenys MILIMETRAIS (mm). Jei lentelėje nurodyta cm/m — konvertuok į mm tiksliai (be apvalinimo).
- Kiekis (vnt.) — sveikas skaičius. Jei nenurodyta, naudok 1.
- Kiekvienam patalpos įrašui pridėk `row_idx` (0-based eilės numeris lentelėje) ir `page` (1-based PDF puslapis, kuriame lentelė rasta).
- Kiekvienai schedule pozicijai pridėk `page` (1-based PDF puslapis).
- `eksplikacija_source_page` — vienintelis puslapis, kuriame yra eksplikacija (pirmas, jei jų keli). Jei nerasta — null.
- Jei tos pačios lentelės kopija pasikartoja keliuose puslapiuose, naudok pirmąjį radimą.
"""


# =============================================================================
# JSON SCHEMA — locked output shape
# =============================================================================
OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["eksplikacija_source_page", "patalpos", "schedule_tables"],
    "properties": {
        "eksplikacija_source_page": {"type": ["integer", "null"]},
        "patalpos": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["nr", "pavadinimas", "plotas_m2", "plotas_m2_raw",
                             "row_idx", "page"],
                "properties": {
                    "nr": {"type": "string"},
                    "pavadinimas": {"type": "string"},
                    "plotas_m2": {"type": ["number", "null"]},
                    # PRIVALOMA — modelis turi cituoti raw cell tekstą prieš
                    # parse'iną į skaičių. Kitaip jis tendentingai apvalina.
                    "plotas_m2_raw": {"type": ["string", "null"], "description": "Literal cell text from table (e.g. '63,45 m²'). REQUIRED — forces non-rounding by making model copy chars before parsing."},
                    "perimetras_m": {"type": ["number", "null"]},
                    "perimetras_m_raw": {"type": ["string", "null"]},
                    "lubu_aukstis_m": {"type": ["number", "null"]},
                    "lubu_aukstis_m_raw": {"type": ["string", "null"]},
                    "row_idx": {"type": "integer"},
                    "page": {"type": "integer"},
                },
            },
        },
        "schedule_tables": {
            "type": "object",
            "additionalProperties": False,
            "required": ["durys", "langai"],
            "properties": {
                "durys": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["id", "page"],
                        "properties": {
                            "id": {"type": "string"},
                            "plotis_mm": {"type": ["integer", "null"]},
                            "aukstis_mm": {"type": ["integer", "null"]},
                            "tipas": {"type": ["string", "null"]},
                            "kiekis": {"type": ["integer", "null"]},
                            "page": {"type": "integer"},
                        },
                    },
                },
                "langai": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["id", "page"],
                        "properties": {
                            "id": {"type": "string"},
                            "plotis_mm": {"type": ["integer", "null"]},
                            "aukstis_mm": {"type": ["integer", "null"]},
                            "tipas": {"type": ["string", "null"]},
                            "kiekis": {"type": ["integer", "null"]},
                            "page": {"type": "integer"},
                        },
                    },
                },
            },
        },
    },
}


# Compact instruction block; full schema sent inline so the model has the
# exact structure to emit. Kept short — Vision tokens are expensive.
USER_INSTRUCTION = (
    "Iš šių PDF puslapių išgauk eksplikaciją ir durų/langų specifikacijas. "
    "Grąžink TIK JSON pagal šią schemą (ATKREIPK DĖMESĮ — tikslūs lauko vardai):\n\n"
    + json.dumps(OUTPUT_SCHEMA, ensure_ascii=False, indent=2)
    + "\n\n"
    + "**KRITIŠKAI SVARBU — DECIMAL TIKSLUMAS PER `_raw` LAUKUS:**\n"
    + "Kiekvienai patalpai PRIVALAI grąžinti `plotas_m2_raw` lauką su EXACT "
    + "celės tekstu prieš parse'iną. Jei celėj rašo `63,45 m²`, tu rašai:\n"
    + "  `\"plotas_m2_raw\": \"63,45 m²\"`\n"
    + "  `\"plotas_m2\": 63.45`\n"
    + "TADA tu negalėsi suapvalinti — pirma kopijuoji simbolius, paskui "
    + "konvertuoji. Tai apsaugo nuo `63,45 → 63.4` truncation'o.\n"
    + "Jei nematote celės — `plotas_m2_raw: null`, `plotas_m2: null`.\n\n"
    + "Jei lentelė nerasta — atitinkamas masyvas tuščias, "
    + "eksplikacija_source_page = null."
)


# =============================================================================
# Helpers
# =============================================================================
def _empty_payload() -> dict:
    """Canonical empty result shape (no tables found)."""
    return {
        "eksplikacija_source_page": None,
        "patalpos": [],
        "schedule_tables": {"durys": [], "langai": []},
    }


def _repair_json(text: str) -> str:
    """Best-effort JSON repair: strip code fences, quote bare keys, drop trailing commas.

    Mirrors vision_call._repair_json so behavior is consistent across the pipeline.
    """
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        if text.endswith("```"):
            text = text[:-3]
    # Quote unquoted keys
    text = _re.sub(r'([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', text)
    # Drop trailing commas
    text = _re.sub(r',(\s*[}\]])', r'\1', text)
    return text


def _parse_raw_number(raw: str | None) -> float | None:
    """Parse a literal cell text (e.g. '63,45 m²') into a float, preserving all decimals.

    Used as recovery when the model rounded its `_value` despite CoT instruction —
    we re-derive the number from `_raw` which preserves character-level fidelity.
    Returns None if raw is empty/unparseable.
    """
    if not raw or not isinstance(raw, str):
        return None
    # Strip units, whitespace; replace LT comma with dot
    cleaned = _re.sub(r"[a-zA-Z²³µ\s]+", "", raw).replace(",", ".")
    cleaned = cleaned.strip(".·-")
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return None


def _recover_decimals(item: dict, raw_field_pairs: list[tuple[str, str]]) -> None:
    """For each (numeric_field, raw_field) pair, if `_raw` has more decimals than
    `_value`, prefer the parsed `_raw`. Mutates item in place."""
    for num_field, raw_field in raw_field_pairs:
        raw = item.get(raw_field)
        if not raw:
            continue
        from_raw = _parse_raw_number(raw)
        if from_raw is None:
            continue
        cur = item.get(num_field)
        # If current is None, or differs from raw-derived, prefer raw-derived.
        if cur is None or abs(float(cur) - from_raw) > 1e-9:
            item[num_field] = from_raw


def _normalize_payload(parsed: dict) -> dict:
    """Coerce model output into the locked shape, filling missing keys with empties."""
    out = _empty_payload()

    src = parsed.get("eksplikacija_source_page")
    if isinstance(src, int):
        out["eksplikacija_source_page"] = src

    patalpos = parsed.get("patalpos")
    if isinstance(patalpos, list):
        out["patalpos"] = [p for p in patalpos if isinstance(p, dict)]
        # Decimal recovery: prefer numbers parsed from `_raw` text if they
        # have more precision than the model's `_value` field.
        for p in out["patalpos"]:
            _recover_decimals(p, [
                ("plotas_m2",      "plotas_m2_raw"),
                ("perimetras_m",   "perimetras_m_raw"),
                ("lubu_aukstis_m", "lubu_aukstis_m_raw"),
            ])

    sched = parsed.get("schedule_tables") or {}
    if isinstance(sched, dict):
        durys = sched.get("durys")
        langai = sched.get("langai")
        out["schedule_tables"]["durys"] = (
            [d for d in durys if isinstance(d, dict)] if isinstance(durys, list) else []
        )
        out["schedule_tables"]["langai"] = (
            [l for l in langai if isinstance(l, dict)] if isinstance(langai, list) else []
        )
    return out


def _build_user_content(pages: list[dict]) -> list[dict]:
    """Assemble Anthropic Vision user content: instruction + page images."""
    content: list[dict] = [{"type": "text", "text": USER_INSTRUCTION}]
    for p in pages:
        content.append({
            "type": "text",
            "text": f"Puslapis {p['page_index']}:",
        })
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": p["image_b64"],
            },
        })
    # T5c (2026-07-28 telemetry audit): breakpoint on the image prefix, mirroring
    # prompt.build_user_content. The system prompt already had one, but the heavy
    # part — the page images — did not, so a retry (JSON-decode failure, or a
    # transient 5xx) re-sent byte-identical images at FULL price. With the
    # breakpoint a retry reads them at ~0.1x instead.
    # Tradeoff, stated honestly: a cache write costs 1.25x, so the no-retry case
    # pays +25% on the image tokens. Break-even is a ~38% retry rate on this
    # reader; revert this hunk if the new cache_write telemetry shows retries are
    # rarer than that. Zero accuracy impact either way.
    if content and content[-1].get("type") == "image":
        content[-1]["cache_control"] = {"type": "ephemeral"}
    return content


# =============================================================================
# Public API
# =============================================================================
def read_eksplikacija(pdf_bytes: bytes, client: anthropic.Anthropic) -> dict:
    """Pre-pass extraction of eksplikacija + schedule tables from a LT PDF.

    Args:
        pdf_bytes: full PDF
        client: anthropic.Anthropic() instance (passed in to share with main extract)

    Returns: dict shaped per docstring at module top. Never raises.
        On hard failure includes `_error` key and empty payload arrays.
    """
    t0 = time.time()

    # Step 0 (Sprint A): TRY pdfplumber FIRST — deterministic, $0, byte-exact.
    # ~25% of LT projects have eksplikacija as a clean text-layer table that
    # pdfplumber.extract_tables() reads perfectly (P3-style). For those, we
    # skip Vision entirely and return the result. For other projects (P1-style
    # with rotated CAD-export, or raster scans), pdfplumber returns nothing
    # and we fall through to Vision below.
    try:
        from .pdfplumber_eksplikacija import extract_eksplikacija_pdfplumber
        pdf_attempt = extract_eksplikacija_pdfplumber(pdf_bytes)
        if pdf_attempt.get("patalpos"):
            # SUCCESS — pdfplumber found a real eksplikacija. Return immediately.
            #
            # THE RULE (restated 2026-08-23, when the parser was widened):
            # pdfplumber REPLACES the Vision read of the room table, it does
            # not merely supplement it. That is only defensible because the
            # bar for "found" is set by construction, not by hope:
            #   · the page must carry an eksplikacija heading;
            #   · >= MIN_ROOMS_THRESHOLD rows must survive BOTH the LT
            #     room-name vocabulary and the 1-500 m2 plausibility band;
            #   · a row with two plausible numbers and no column header is
            #     REFUSED, not guessed (pdfplumber_eksplikacija._try_parse_row).
            # Anything short of that returns empty and Vision runs as before.
            #
            # Measured on the six fixture PDFs after the widening: berzas,
            # ciurliu and sernu still MISS; objektas_b (15 rooms) and romainiai
            # (11) were already hits and return byte-identical numbers; lazunu
            # flipped MISS -> HIT (4 rooms) and its four areas match the cached
            # Vision read exactly. No fixture's numbers changed.
            meta = pdf_attempt.get("_meta") or {}
            sources = {}
            for r in pdf_attempt["patalpos"]:
                key = r.get("_row_source") or "scan"
                sources[key] = sources.get(key, 0) + 1
            print(f"[eksplikacija_reader] pdfplumber HIT — {len(pdf_attempt['patalpos'])} "
                  f"rooms from page {pdf_attempt.get('eksplikacija_source_page')}, "
                  f"{meta.get('elapsed_s', 0)}s, $0 "
                  f"(rows={sources}, header={meta.get('header_detected')}, "
                  f"ambiguous_rows_skipped={meta.get('ambiguous_rows', 0)}, "
                  f"tables={meta.get('tables_contributing')}, "
                  f"discarded={meta.get('tables_discarded') or []})")
            return pdf_attempt
        else:
            # The MISS branch is where the diagnostics actually MATTER, and it
            # printed none of them: `ambiguous_rows` (rows the parser refused
            # because two numbers were plausible) and `header_detected` are the
            # difference between "there is no table on this page" and "I found
            # the table and threw every row away". Measured on real files:
            # Projektas..pdf refuses 71 rows, 03_SA.pdf 25 — invisible until now.
            _m = pdf_attempt["_meta"]
            print(f"[eksplikacija_reader] pdfplumber MISS — falling through to Vision "
                  f"(scanned {_m.get('pages_scanned', 0)} pages, "
                  f"{_m.get('eksplikacija_pages_found', 0)} marked "
                  f"as eksplikacija, {_m.get('tables_examined', 0)} "
                  f"tables examined, header={_m.get('header_detected')}, "
                  f"ambiguous_rows_skipped={_m.get('ambiguous_rows', 0)}, "
                  f"discarded={_m.get('tables_discarded') or []})")
    except Exception as exc:
        # Soft failure — continue to Vision path
        print(f"[eksplikacija_reader] pdfplumber pre-pass error (non-fatal): {exc}")

    # Step 1: PDF → base64 images at HIGH DPI (300 vs main's 200).
    # Eksplikacijos lentelės skaitmenys yra mažas tekstas — 200 DPI verčia
    # modelį spėti paskutinius decimal'us. 300 DPI padaro „63,45" pixel-perfect
    # readable. ~25% daugiau tokens, bet decimal precision yra kritinė.
    try:
        pages = pdf_to_b64_images(pdf_bytes, dpi=300)
    except Exception as exc:
        return {
            **_empty_payload(),
            "_error": f"pdf_to_images_failed: {exc}",
            "_meta": {
                "input_tokens": 0,
                "output_tokens": 0,
                "cache_read_tokens": 0,
                "elapsed_s": round(time.time() - t0, 2),
            },
        }

    if not pages:
        return {
            **_empty_payload(),
            "_error": "PDF has no renderable pages",
            "_meta": {
                "input_tokens": 0,
                "output_tokens": 0,
                "cache_read_tokens": 0,
                "elapsed_s": round(time.time() - t0, 2),
            },
        }

    # System prompt with cache_control for cost optimization across runs.
    system = [
        {"type": "text", "text": SYSTEM_TEXT, "cache_control": {"type": "ephemeral"}}
    ]
    user_content = _build_user_content(pages)

    # Step 2: Vision call with retry (max 3 attempts, exponential backoff).
    last_err: Exception | None = None
    parsed: dict | None = None
    final_usage = None
    final_attempt = 0

    model = model_for("vision_pass1")  # resolved per-run (MODEL_OVERRIDE etc.)
    # F6 residual (2026-07-28): this module owns its OWN retry loop, and the
    # shared client is built with max_retries=1 — the two MULTIPLY, so 3
    # attempts became up to 6 HTTP calls (and 6 × the latency before we give
    # up). The loop below is the retry policy; the SDK's must be off inside it.
    # `with_options` is an alias of `copy` in anthropic 0.95.0: it preserves
    # api_key, base_url, timeout, default_headers/query and REUSES the same
    # httpx client (connection pool) — only max_retries changes.
    _call_client = (client.with_options(max_retries=0)
                    if hasattr(client, "with_options") else client)
    for attempt in range(3):
        final_attempt = attempt + 1
        try:
            with _call_client.messages.stream(
                model=model,
                max_tokens=8192,  # tables are small vs full extract; 8k is ample
                system=system,
                messages=[{"role": "user", "content": user_content}],
                # "medium" effort: tables are simpler than dimension chains
                output_config={"effort": "medium"},
            ) as stream:
                resp = stream.get_final_message()

            # T5b (2026-07-28 telemetry audit): `refusal` and `max_tokens` are
            # DETERMINISTIC given an unchanged payload — the retry re-sent
            # byte-identical input and re-paid for it three times to get the
            # same answer. Fail immediately, matching _run_pass1_once in
            # vision_call.py, which returns on both stop reasons. The
            # network/5xx retries in the except block below are untouched —
            # those are genuinely transient.
            if resp.stop_reason in ("refusal", "max_tokens"):
                last_err = Exception(
                    f"stop_reason={resp.stop_reason} (deterministic — not retried)")
                break

            text = "".join(
                b.text for b in resp.content if getattr(b, "type", None) == "text"
            ).strip()

            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                try:
                    parsed = json.loads(_repair_json(text))
                except json.JSONDecodeError as je:
                    last_err = je
                    if attempt == 2:
                        break
                    time.sleep(1.5 ** attempt)
                    continue

            final_usage = resp.usage
            break  # success

        except Exception as exc:
            last_err = exc
            print(f"[eksplikacija_reader] attempt {attempt + 1} failed: {exc}")
            if attempt == 2:
                break
            time.sleep(1.5 ** attempt)

    elapsed = round(time.time() - t0, 2)

    if parsed is None:
        return {
            **_empty_payload(),
            "_error": f"vision_call_failed: {last_err}",
            "_meta": {
                "input_tokens": 0,
                "output_tokens": 0,
                "cache_read_tokens": 0,
                "elapsed_s": elapsed,
                "attempts": final_attempt,
            },
        }

    # Step 3: Normalize into locked shape.
    result = _normalize_payload(parsed)

    # Step 4: Attach _meta with token usage.
    result["_meta"] = {
        "input_tokens": getattr(final_usage, "input_tokens", 0) or 0,
        "output_tokens": getattr(final_usage, "output_tokens", 0) or 0,
        "cache_read_tokens": getattr(final_usage, "cache_read_input_tokens", 0) or 0,
        "cache_write_tokens": getattr(final_usage, "cache_creation_input_tokens", 0) or 0,
        "elapsed_s": elapsed,
        "attempts": final_attempt,
        "pages_sent": len(pages),
        "model": model,
    }
    return result


# =============================================================================
# Smoke test (no real API call)
# =============================================================================
if __name__ == "__main__":
    import inspect

    # Verify import + symbol export
    assert "read_eksplikacija" in __all__, "read_eksplikacija missing from __all__"

    # Verify function is callable
    assert callable(read_eksplikacija), "read_eksplikacija is not callable"

    # Verify signature: (pdf_bytes: bytes, client) -> dict
    sig = inspect.signature(read_eksplikacija)
    params = list(sig.parameters.keys())
    assert params == ["pdf_bytes", "client"], (
        f"Unexpected signature: {params!r} (expected ['pdf_bytes', 'client'])"
    )

    # Verify empty-payload shape matches the documented contract
    empty = _empty_payload()
    assert set(empty.keys()) == {"eksplikacija_source_page", "patalpos", "schedule_tables"}
    assert set(empty["schedule_tables"].keys()) == {"durys", "langai"}
    assert empty["patalpos"] == []
    assert empty["schedule_tables"]["durys"] == []
    assert empty["schedule_tables"]["langai"] == []

    # Verify normalize is robust to garbage input
    assert _normalize_payload({}) == _empty_payload()
    assert _normalize_payload({"patalpos": "not-a-list"}) == _empty_payload()
    weird = _normalize_payload({
        "eksplikacija_source_page": 2,
        "patalpos": [{"nr": "M01"}, "not-a-dict"],
        "schedule_tables": {"durys": [{"id": "D1"}], "langai": None},
    })
    assert weird["eksplikacija_source_page"] == 2
    assert len(weird["patalpos"]) == 1
    assert weird["schedule_tables"]["durys"] == [{"id": "D1"}]
    assert weird["schedule_tables"]["langai"] == []

    # Verify _repair_json strips fences + trailing commas (still parseable)
    repaired = _repair_json('```json\n{"a": 1,}\n```')
    assert json.loads(repaired) == {"a": 1}, f"unexpected repair output: {repaired!r}"

    print("[eksplikacija_reader] smoke test OK — module imports cleanly, signature & shape verified.")
