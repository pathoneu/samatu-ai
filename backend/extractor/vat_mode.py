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
