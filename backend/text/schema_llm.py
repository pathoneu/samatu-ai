"""The ONE model call the readers may make: already-extracted TEXT in → schema JSON out, every value guarded (v4
Phase 3c-2; plan 2026-10-24 §1 R3, §3.2).

A reader that could not parse a table, a schedule, a finish note or a legend deterministically may hand the TEXT it
read (text layer, or local OCR) to `structure()`. The model never sees the sheet: the request carries text blocks
only (the guard test in tests/test_text_first_readers_2026_10_25.py fails on an image or document block anywhere
under backend/text or in a reader). For every field the model returns `{"value": …, "source_text": "…"}`, and a
value is kept only when:

  · its `source_text` is a substring of the input text (whitespace and case folded), and
  · a number appears in that `source_text` as written (LT decimal comma or point; „2 400" as one number) and is
    the value; a text value appears in its `source_text`; an enum value is one of the allowed values.

Anything else is REFUSED — the field is dropped and listed in `refused` with why; an item whose key field is
refused is dropped whole. The model never emits a number that was not literally in the text (R3).

No client → `status: "no_client"` and nothing (the eval and the tests run without a key). Retries: max 3 on a
transport error (CLAUDE.md). Never raises.

    structure(text, fields={"nr": "text", "plotas_m2": "number", ...}, key="nr", instruction="…", client=…)
      -> {status: ok|no_client|empty|error|refused, items: [{field: value, "_saltinis": {field: source_text}}],
          refused: [{index, field, value, source_text, kodel}], _meta: {model, input_tokens, output_tokens}}
"""
from __future__ import annotations

import json
import logging
import re
import time
import unicodedata
from typing import Any

log = logging.getLogger("samatu.schema_llm")

MAX_INPUT_CHARS = 60_000
MAX_TOKENS = 8192
MAX_ATTEMPTS = 3
RETRY_SLEEP_S = 1.0
ROLE = "text_schema"

_SYSTEM = (
    "Tu struktūruoji JAU IŠTRAUKTĄ statybinio brėžinio TEKSTĄ į JSON. Paveikslėlio nematai ir nespėji. "
    "Kiekvienam laukui grąžink {\"value\": reikšmė, \"source_text\": \"tikslus teksto gabalas, iš kurio ji\"}. "
    "source_text turi būti nukopijuotas iš pateikto teksto raidė į raidę. Jei reikšmės tekste nėra — "
    "{\"value\": null, \"source_text\": null}. Niekada neskaičiuok, neapvalink ir nekeisk skaičių. "
    "Grąžink TIK JSON: {\"items\": [ ... ]}."
)


def _norm(s: Any) -> str:
    t = unicodedata.normalize("NFC", str(s or "")).lower()
    return " ".join(t.split())


_NUM = re.compile(r"(?<![\d.,])\d{1,3}(?:[   ]\d{3})+(?:[.,]\d+)?(?![\d])|(?<![\d.,])\d+(?:[.,]\d+)?(?![\d])")


def numbers_in(text: str) -> list[float]:
    """Every number written in `text`, as it is written: „12,30" → 12.3, „2 400" → 2400.0, „1.070" → 1.07
    (a point is a decimal point here; the reader that knows a thousands point converts its own field)."""
    out: list[float] = []
    for m in _NUM.finditer(str(text or "")):
        raw = re.sub(r"[   ]", "", m.group(0)).replace(",", ".")
        try:
            out.append(float(raw))
        except ValueError:
            continue
    return out


def check_value(kind, value: Any, source_text: Any, haystack_norm: str) -> str | None:
    """None when the value may stay; else why it is refused (Lithuanian, for the evidence list)."""
    if value is None:
        return None
    if not isinstance(source_text, str) or not source_text.strip():
        return "nėra šaltinio teksto"
    if _norm(source_text) not in haystack_norm:
        return "šaltinio teksto tekste nėra"
    if isinstance(kind, (list, tuple, set, frozenset)):
        return None if value in kind else "reikšmė ne iš leistinų"
    if kind in ("number", "integer"):
        if isinstance(value, bool):
            return "ne skaičius"
        try:
            v = float(value)
        except (TypeError, ValueError):
            return "ne skaičius"
        if kind == "integer" and not v.is_integer():
            return "ne sveikas skaičius"
        if not any(abs(v - n) <= 1e-9 * max(1.0, abs(n)) for n in numbers_in(source_text)):
            return "skaičiaus šaltinio tekste nėra"
        return None
    if _norm(value) not in _norm(source_text):
        return "reikšmės šaltinio tekste nėra"
    return None


def guard_items(raw_items: Any, fields: dict, key: str | None, text: str) -> tuple[list[dict], list[dict]]:
    """(kept items, refused fields) — the guard alone, without a model (tests and callers that got JSON elsewhere)."""
    hay = _norm(text)
    kept: list[dict] = []
    refused: list[dict] = []
    for i, it in enumerate(raw_items if isinstance(raw_items, list) else []):
        if not isinstance(it, dict):
            continue
        out: dict = {}
        src: dict = {}
        drop = False
        for f, kind in fields.items():
            cell = it.get(f)
            if isinstance(cell, dict):
                value, source = cell.get("value"), cell.get("source_text")
            else:
                value, source = cell, None
            if value is None:
                continue
            why = check_value(kind, value, source, hay)
            if why:
                refused.append({"index": i, "field": f, "value": value, "source_text": source, "kodel": why})
                if f == key:
                    drop = True
                continue
            out[f] = int(value) if kind == "integer" else (float(value) if kind == "number" else value)
            src[f] = source
        if drop or not out or (key and key not in out):
            continue
        out["_saltinis"] = src
        kept.append(out)
    return kept, refused


def _text_only(messages: list[dict]) -> bool:
    for m in messages:
        c = m.get("content")
        blocks = c if isinstance(c, list) else [{"type": "text", "text": c}]
        if any(not isinstance(b, dict) or b.get("type") != "text" for b in blocks):
            return False
    return True


def structure(text: str, *, fields: dict, instruction: str, key: str | None = None, client=None,
              max_items: int = 200) -> dict:
    """See the module docstring. `fields` = {name: "number" | "integer" | "text" | [allowed values]}."""
    started = time.monotonic()
    out = {"status": "ok", "items": [], "refused": [], "_meta": {"model": None, "input_tokens": 0, "output_tokens": 0}}
    text = str(text or "")
    if not text.strip():
        out["status"] = "empty"
        return out
    if client is None:
        out["status"] = "no_client"
        return out
    try:
        from models_config import model_for
        model = model_for(ROLE)
    except Exception:  # noqa: BLE001
        model = None
    out["_meta"]["model"] = model
    schema = ", ".join(f'"{f}": {{"value": {("viena iš " + json.dumps(list(k), ensure_ascii=False)) if isinstance(k, (list, tuple, set, frozenset)) else k}, "source_text": "…"}}'
                       for f, k in fields.items())
    user = (f"{instruction}\n\nKiekvienas elementas: {{{schema}}}. Daugiausia {max_items} elementų.\n\n"
            f"TEKSTAS:\n<<<\n{text[:MAX_INPUT_CHARS]}\n>>>")
    messages = [{"role": "user", "content": [{"type": "text", "text": user}]}]
    if not _text_only(messages):           # by construction — the guard test also checks the source
        out["status"] = "error"
        return out
    resp = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            resp = client.messages.create(model=model, max_tokens=MAX_TOKENS,
                                          system=[{"type": "text", "text": _SYSTEM}], messages=messages)
            break
        except Exception as exc:  # noqa: BLE001
            log.warning("schema_llm attempt %s failed: %r", attempt, exc)
            if attempt == MAX_ATTEMPTS:
                out["status"] = "error"
                out["_meta"]["error"] = type(exc).__name__
                return out
            time.sleep(RETRY_SLEEP_S * attempt)
    try:
        from extractor.response_text import read_answer, usage_meta
        raw, stopped = read_answer(resp, reader="schema_llm")
        out["_meta"].update(usage_meta(resp, model))
        if stopped:
            out["status"] = "error"
            out["_meta"]["stopped"] = stopped
            return out
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        payload = json.loads(m.group(0)) if m else {}
    except Exception:  # noqa: BLE001
        out["status"] = "error"
        return out
    items, refused = guard_items((payload or {}).get("items"), fields, key, text)
    out["items"] = items[:max_items]
    out["refused"] = refused
    if refused and not items:
        out["status"] = "refused"
    out["_meta"]["seconds"] = round(time.monotonic() - started, 2)
    return out
