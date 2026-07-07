"""Spreadsheet formula-injection neutralisation (F6, 2026-07-04 pentest).

CSV / XLSX exports (F2/F3, Excel) write user- and AI-supplied strings — row
labels, aprašymas, notes. If such a string starts with one of the formula-trigger
characters (= + - @) or a leading control char (tab / CR / LF), a spreadsheet
that opens the file will EVALUATE it as a formula. Since F2/F3 documents are
shared with third parties (užsakovas, auditor), a crafted label like
`=HYPERLINK("http://evil","click")` becomes a live formula in their Excel.

CSV Injection / Formula Injection is OWASP's canonical name. The standard
mitigation (Google Sheets, LibreOffice guidance, OWASP) is to prefix the risky
cell value with a single quote so the spreadsheet treats it as literal text.

This module is deliberately dependency-free so both the extractor CSV writer and
the openpyxl Excel writer can import it.
"""
from __future__ import annotations

from typing import Any

# Leading characters that make a spreadsheet start parsing a formula.
_FORMULA_TRIGGERS = ("=", "+", "-", "@")
# Leading control characters that some spreadsheets strip, re-exposing a trigger
# underneath (and that enable other cell-break tricks).
_CONTROL_LEADS = ("\t", "\r", "\n")


def sanitize_spreadsheet_cell(value: Any) -> Any:
    """Return a spreadsheet-safe version of ``value``.

    - Non-string values (int / float / None / bool) pass through untouched —
      numeric cells must stay numeric.
    - A string whose first character is a formula trigger (= + - @) or a leading
      tab/CR/LF is prefixed with a single quote ``'`` so the spreadsheet renders
      it as literal text instead of evaluating it.
    - All other strings pass through unchanged.
    """
    if not isinstance(value, str):
        return value
    if value and (value[0] in _FORMULA_TRIGGERS or value[0] in _CONTROL_LEADS):
        return "'" + value
    return value
