"""Pipeline 2 — Text-driven counting via pdfplumber.

For symbols whose architects label with words ("Rozetė", "Jungtukas",
"Lubinis šviestuvas"), count occurrences of those Lithuanian terms in
the PDF text layer on the given page.

We use a per-symbol-code keyword map. The map is heuristic — built from
common Lithuanian architectural vocabulary plus the legend-extractor's
description_lt field as a fallback.

Strength: zero cost, milliseconds. Strength on P1/VT (text-heavy).
Weakness: P3 has minimal annotations — text-driven returns 0 there.
"""

from __future__ import annotations
import time
import re
from pathlib import Path

import pdfplumber

from detector_bench.core.types import Detector, DetectionResult, BBox

# Per-symbol-code text patterns. Generic mapping of category → keywords.
# Specific symbol codes (iš.1, pš.1) fall through to substring match in the legend's description_lt.
SYMBOL_KEYWORDS: dict[str, list[str]] = {
    "rozete":    [r"rozet[ėeė]",       r"rozet"],
    "jungtukas": [r"jungtuk",          r"jungiklis"],
    "led_strip": [r"led\s*juost",      r"led\s*strip"],
    "lubinis_sviestuvas": [r"lubinis\s+šviestuv",  r"luba\s+šviestuv"],
    "pakabinamas_sviestuvas": [r"pakabinam[oa]s\s+šviestuv"],
    "vandens_isvedimas": [r"vandens\s+išved",  r"sifon"],
    "ventiliatorius":    [r"ventiliator"],
}


def _keywords_for(symbol_code: str, legend_description_lt: str | None = None) -> list[str]:
    """Best-effort keyword list for a symbol code. Falls back to description tokens."""
    sc = symbol_code.lower().strip()
    if sc in SYMBOL_KEYWORDS:
        return SYMBOL_KEYWORDS[sc]
    # Try substring match against description_lt (e.g. "iš.1" -> "išviršinis lubinis šviestuvas")
    if legend_description_lt:
        # Take the most distinctive lowercase word ≥4 chars
        words = re.findall(r"[a-zA-ZąčęėįšųūžĄČĘĖĮŠŲŪŽ]{4,}", legend_description_lt.lower())
        if words:
            return [re.escape(w) for w in words[:2]]
    # Last fallback — match the literal code
    return [re.escape(sc)]


class TextDrivenDetector(Detector):
    name = "p2_text_driven"

    def __init__(self) -> None:
        self._legend: dict[str, str] = {}  # symbol_code → description_lt

    def setup(self, pdf_path: Path) -> None:
        # Per-PDF legend lives at legends/<pdf_stem>.json
        import json
        legend_json = Path(f"/Users/ignasgaldikas/samatu-ai/legends/{Path(pdf_path).stem}.json")
        if legend_json.exists():
            for it in json.loads(legend_json.read_text()):
                self._legend[it["symbol_code"]] = it.get("description_lt", "")

    def detect(self, pdf_path: Path, page_nr: int, symbol_code: str) -> DetectionResult:
        t0 = time.time()
        keywords = _keywords_for(symbol_code, self._legend.get(symbol_code))
        try:
            with pdfplumber.open(str(pdf_path)) as pdf:
                if page_nr < 1 or page_nr > len(pdf.pages):
                    return DetectionResult(
                        count=0, bboxes=[], runtime_s=time.time() - t0,
                        cost_usd=0.0, errors=[f"page {page_nr} out of range"],
                    )
                page = pdf.pages[page_nr - 1]
                text = (page.extract_text() or "").lower()
            count = 0
            for kw in keywords:
                count += len(re.findall(kw, text, re.IGNORECASE))
            return DetectionResult(
                count=count, bboxes=[],
                runtime_s=time.time() - t0, cost_usd=0.0, errors=[],
                notes=f"keywords matched: {keywords}",
            )
        except Exception as e:
            return DetectionResult(
                count=0, bboxes=[], runtime_s=time.time() - t0,
                cost_usd=0.0, errors=[str(e)], notes="failed",
            )
