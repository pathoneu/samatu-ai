"""Text-first readers (plan 2026-10-24 §3.2): the PDF text layer, and local OCR for sheets without one.

`ocr.py` — local OCR (R6: nothing leaves the machine), behind the flag `SAMATU_OCR` (default OFF).
`layer.py` — one entry point that gives a sheet's characters from the text layer, or from OCR when the
layer has nothing usable and the flag is on, in the shape every reader already consumes.
"""
