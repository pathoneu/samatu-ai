"""extractor.eksplikacija_reader — pre-pass reader of the LT schedule tables, TEXT-FIRST (v4 Phase 3c-2).

v4 3c-2 (2026-10-25): no model looks at a page any more. The tables are read from the text layer
(`pdfplumber_eksplikacija`, deterministic); when that finds none, the TEXT of the sheets that carry a table heading
(text layer, or local OCR behind `SAMATU_OCR` for a sheet without one) may be structured by a language model through
`text/schema_llm.py` — every value must stand in that text as written, else it is refused (plan R3). No text, no
table: the reading goes on without one and says so.

The rest of this docstring is the module's history.

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


__all__ = ["read_eksplikacija"]


MAX_TABLE_PAGES = 4
_HEADING = _re.compile(r"EKSPLIKACIJ|PATALP\w* (S\u0104RA\u0160AS|SARASAS)|DUR\u0172 SPECIFIKACIJ|LANG\u0172 SPECIFIKACIJ|DURU SPECIFIKACIJ|LANGU SPECIFIKACIJ", _re.IGNORECASE)


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


def _table_texts(pdf_bytes: bytes) -> list[tuple[int, str]]:
    """(page, text) of the sheets whose text carries a room-table or door / window schedule heading — the text
    layer, else local OCR behind SAMATU_OCR. At most MAX_TABLE_PAGES sheets."""
    out: list[tuple[int, str]] = []
    try:
        from .pdf_page_cache import page_texts
        texts = page_texts(pdf_bytes)
    except Exception:  # noqa: BLE001
        return out
    for i, t in enumerate(texts):
        t = t or ""
        if len(t.strip()) < 8:
            try:
                from text.ocr import ocr_enabled, ocr_page
                if ocr_enabled():
                    _w, _h, words = ocr_page(pdf_bytes, i + 1)
                    t = " ".join(w.text for w in words)
            except Exception:  # noqa: BLE001
                t = ""
        if _HEADING.search(t):
            out.append((i + 1, t))
        if len(out) >= MAX_TABLE_PAGES:
            break
    return out


_ROOM_FIELDS = {"nr": "text", "pavadinimas": "text", "plotas_m2": "number", "perimetras_m": "number",
                "lubu_aukstis_m": "number"}
_OPENING_FIELDS = {"id": "text", "plotis_mm": "number", "aukstis_mm": "number", "tipas": "text", "kiekis": "integer"}


def _schema_fallback(pdf_bytes: bytes, client) -> dict | None:
    """The tables structured from the sheets' TEXT by text/schema_llm.py (substring-guarded), or None."""
    pages = _table_texts(pdf_bytes)
    if not pages or client is None:
        return None
    from text.schema_llm import structure
    text = "\n\n".join(f"[lapas {p}]\n{t}" for p, t in pages)
    rooms = structure(text, fields=_ROOM_FIELDS, key="nr", client=client,
                      instruction="Iš teksto ištrauk PATALPŲ EKSPLIKACIJOS eilutes: patalpos numeris, pavadinimas, "
                                  "plotas m², perimetras m ir lubų aukštis m, jei jie parašyti.")
    doors = structure(text, fields=_OPENING_FIELDS, key="id", client=client,
                      instruction="Iš teksto ištrauk DURŲ SPECIFIKACIJOS eilutes: žymėjimas (D1…), plotis mm, "
                                  "aukštis mm, tipas, kiekis.")
    wins = structure(text, fields=_OPENING_FIELDS, key="id", client=client,
                     instruction="Iš teksto ištrauk LANGŲ SPECIFIKACIJOS eilutes: žymėjimas (L1…), plotis mm, "
                                 "aukštis mm, tipas, kiekis.")
    strip = lambda items: [{k: v for k, v in it.items()} for it in items]  # noqa: E731 — keep _saltinis
    result = {
        "eksplikacija_source_page": pages[0][0] if rooms.get("items") else None,
        "patalpos": strip(rooms.get("items") or []),
        "schedule_tables": {"durys": strip(doors.get("items") or []), "langai": strip(wins.get("items") or [])},
        "_meta": {"saltinis": "tekstas+schema_llm", "pages": [p for p, _ in pages],
                  "atmesta": len(rooms.get("refused") or []) + len(doors.get("refused") or []) + len(wins.get("refused") or []),
                  "model": rooms.get("_meta", {}).get("model"),
                  "input_tokens": sum(int((r.get("_meta") or {}).get("input_tokens") or 0) for r in (rooms, doors, wins)),
                  "output_tokens": sum(int((r.get("_meta") or {}).get("output_tokens") or 0) for r in (rooms, doors, wins))},
    }
    return result


def read_eksplikacija(pdf_bytes: bytes, client=None) -> dict:
    """Pre-pass extraction of eksplikacija + schedule tables from a LT PDF.

    Args:
        pdf_bytes: full PDF
        client: the reading's model client, used only by text/schema_llm.py on the sheets' TEXT (None: no call)

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
            # Measured on the six fixture PDFs after the widening: objektas_a,
            # objektas_c and the holdout still MISS; objektas_b (15 rooms) and the
            # fifth in-sample project (11) were already hits and return
            # byte-identical numbers; objektas_d
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
        # Soft failure — continue to the text schema path
        print(f"[eksplikacija_reader] pdfplumber pre-pass error (non-fatal): {exc}")

    # Step 1 (v4 3c-2): no image is ever sent. The sheets' TEXT (text layer / OCR) → schema_llm, guarded.
    try:
        fb = _schema_fallback(pdf_bytes, client)
    except Exception as exc:  # noqa: BLE001
        print(f"[eksplikacija_reader] text schema fallback failed (non-fatal): {exc}")
        fb = None
    if fb and (fb.get("patalpos") or fb["schedule_tables"]["durys"] or fb["schedule_tables"]["langai"]):
        fb["_meta"]["elapsed_s"] = round(time.time() - t0, 2)
        return fb
    return {
        **_empty_payload(),
        "_error": "no table in the drawing's text",
        "_meta": {"input_tokens": int(((fb or {}).get("_meta") or {}).get("input_tokens") or 0),
                  "output_tokens": int(((fb or {}).get("_meta") or {}).get("output_tokens") or 0),
                  "cache_read_tokens": 0, "elapsed_s": round(time.time() - t0, 2), "saltinis": "tekstas"},
    }


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
