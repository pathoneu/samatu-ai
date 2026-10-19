"""Bathtub and floor-drain rows (Pathon v3 W5-E, E5; CLAUDE.md §1.14) — behind flag ``SAMATU_BATH_DRAIN_ROWS``
(default off: nothing changes with it off).

  · „Vonios montavimas" — from the sanitary reader's tub-only count (``detected_symbols_summary.vonios_kubilai``,
    the count the bathtub-mixer row already rides on). A tub-or-tray symbol with no tub reading becomes the
    blank row with a question, never a guessed 1.
  · „Trapų montavimas" — from a LEGEND count only (W2-A counts a legend row; the count → row path (W5-D) stores
    it as ``parsed["_legendos_kiekiai"]`` (see CONTRACT below) = {kind: {"kiekis": n, "tekstas": legend row text}}). No count, no row:
    the main pass's glance (`trapai`) is not a reading and no paid prompt is changed.

CONTRACT ``parsed["_legendos_kiekiai"]`` (writer: W5-D; nothing writes it yet) — a dict keyed by count kind:

    {"trapai": {"kiekis": 3,                      # int ≥ 1 — pieces counted on the drawing
                "tekstas": "Trapas",              # the legend row's own text, quoted in the evidence sentence
                "row_id": "…", "page": 4}}        # optional: the legend row and its sheet

  A missing key, a kind without an entry, or ``kiekis`` < 1 means no count and no row. Only ``trapai`` is read
  here today; other kinds may share the dict.

Pure helpers; the rows themselves are appended by vision_call._build_pozicijos_from_rooms.
"""
from __future__ import annotations

import os
import re

FLAG_ENV = "SAMATU_BATH_DRAIN_ROWS"
LEGEND_COUNTS_KEY = "_legendos_kiekiai"

BATHTUB_ROW = "Vonios montavimas"
DRAIN_ROW = "Trapų montavimas"
DRAIN_RE = re.compile(r"\btrap", re.IGNORECASE)


def enabled() -> bool:
    return os.environ.get(FLAG_ENV) == "1"


def legend_count(parsed: dict, kind: str) -> tuple[int, str] | None:
    """(count, the legend row's text) W2-B stored for one kind, or None."""
    store = parsed.get(LEGEND_COUNTS_KEY) if isinstance(parsed, dict) else None
    hit = store.get(kind) if isinstance(store, dict) else None
    if not isinstance(hit, dict):
        return None
    try:
        n = int(float(hit.get("kiekis")))
    except (TypeError, ValueError):
        return None
    return (n, str(hit.get("tekstas") or "").strip()) if n > 0 else None


def fixture_rows(parsed: dict, *, tubs_read: int | None, tub_or_tray_glance: int, skyrius: str) -> list[dict]:
    """The rows to add (empty with the flag off)."""
    if not enabled():
        return []
    out: list[dict] = []
    if tubs_read and tubs_read > 0:
        out.append({"skyrius": skyrius, "aprasymas": BATHTUB_ROW, "vnt": "vnt", "kiekis": int(tubs_read),
                    "saltinis": "simboliai_brezinyje",
                    "_confidence_reason": f"Vonios suskaičiuotos santechnikos plane: {int(tubs_read)} vnt."})
    elif tubs_read is None and tub_or_tray_glance > 0:
        out.append({"skyrius": skyrius, "aprasymas": f"{BATHTUB_ROW} — suveskite kiekį", "vnt": "vnt",
                    "kiekis": None, "saltinis": "checklist",
                    "_confidence_reason": "Plane yra vonia arba dušo padėklas, bet neaišku kuri — "
                                          "patikrinkite santechnikos planą ir įrašykite vonių skaičių."})
    drains = legend_count(parsed, "trapai")
    if drains:
        n, text = drains
        out.append({"skyrius": skyrius, "aprasymas": DRAIN_ROW, "vnt": "vnt", "kiekis": n,
                    "saltinis": "simboliai_brezinyje",
                    "_confidence_reason": f"Suskaičiuota brėžinyje pagal legendos eilutę „{text or 'trapas'}“: {n} vnt."})
    return out
