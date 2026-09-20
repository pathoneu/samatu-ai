"""One lock for every PDFium call in the process.

PDFium is not thread-safe — not even across different documents (pypdfium2's
own documentation: „it is not allowed to call pdfium functions simultaneously
across different threads"). Until 2026-09-20 PDFium ran only inside an
extraction's worker thread; the evidence endpoint now renders regions with it
and is asked for six crops at once, from the threadpool. A collision is a
segfault of the API process, not an exception, so the rule is structural:
whoever opens a `PdfDocument` holds `PDFIUM_LOCK` until it is closed.

Re-entrant, because readers call each other (the geometry lane reads a page's
paths while it holds the page's text). Generators must not hold it across a
`yield` — they read everything under the lock and yield afterwards.
"""
from __future__ import annotations

import threading

PDFIUM_LOCK = threading.RLock()
