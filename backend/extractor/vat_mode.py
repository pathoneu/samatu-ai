"""Is the 21 % PVM line printed? One rule for every client document.

`vat_mode` is the contractor's own choice, stored on the project and sent with
every export:

  "standard"     21 % PVM is added — even when the drawing label says
                 „renovacija".
  "reverse_vat"  atvirkštinis PVM (PVMĮ 96 str.): the customer accounts for
                 it, and no PVM line is printed.

Absent (or any other value) keeps the rule stored projects and old clients
were built on: reverse only when the project's `archetipas` reads
"renovacija". That label is read off the drawing, not chosen by him, which is
why the export dialog names it and asks him to check (audit 2026-09-29,
exports-money-2). The frontend twin is `frontend/src/lib/vatMode.js`.
"""
from __future__ import annotations

from typing import Any

VAT_STANDARD = "standard"
VAT_REVERSE = "reverse_vat"


def is_reverse_vat(data: Any) -> bool:
    """True when the document must carry no PVM line."""
    if not isinstance(data, dict):
        return False
    mode = str(data.get("vat_mode") or "").strip().lower()
    if mode == VAT_REVERSE:
        return True
    if mode == VAT_STANDARD:
        return False
    return str(data.get("archetipas") or "").strip().lower() == "renovacija"


# The PVM rates the contractor can pick (Settings › PVM tarifas, and the export
# dialog): 21 % standard, 9 % reduced, 0 %. v3 W7-A M4 (2026-10-18): the rate
# used to stop at the browser — both exports printed 21 % whatever he chose.
VAT_RATES = (21, 9, 0)
DEFAULT_VAT_RATE = 21


def vat_rate_percent(data: Any) -> int:
    """The PVM % a document adds: 0 under reverse VAT (the line is not printed
    at all — `is_reverse_vat`), else the payload's `vat_rate` when it is one of
    VAT_RATES, else 21. Strings ("9", "9,0", "9 %") are read; anything else
    falls back to 21 so a stray value can never zero the tax."""
    if not isinstance(data, dict):
        return DEFAULT_VAT_RATE
    if is_reverse_vat(data):
        return 0
    raw = data.get("vat_rate")
    if isinstance(raw, bool) or raw is None:
        return DEFAULT_VAT_RATE
    try:
        if isinstance(raw, str):
            raw = raw.replace("%", "").replace(",", ".").strip()
        value = float(raw)
    except (TypeError, ValueError):
        return DEFAULT_VAT_RATE
    rate = int(round(value))
    return rate if abs(value - rate) < 1e-9 and rate in VAT_RATES else DEFAULT_VAT_RATE
