"""Eksplikacija (room schedule) specialized prompt — Vision fallback only.

Primary path: pdfplumber deterministic table extraction
(`backend/extractor/pdfplumber_eksplikacija.py`). This Vision prompt is only
invoked when text-layer extraction fails (scanned PDFs, Ghostscript-flattened
drawings).
"""
from .base_system import BASE_RULES

EKSPLIKACIJA_PROMPT = BASE_RULES + """

PAGE TYPE: ROOM SCHEDULE (Patalpų eksplikacija).

Extract structured table:
{
  "rooms": [
    {
      "number": "101",
      "name": "Svetainė",
      "area_m2": 28.40,        // BYTE-EXACT iš lentelės
      "floor_finish": "parketas",
      "wall_finish": "dažymas",
      "ceiling_finish": "dažymas"
    }
  ]
}

KRITIŠKA: jei plotas eksplikacijoje 63,45 m² — tu grąžini 63.45 (NE 63.4).
Decimal precision iš lentelės yra autoritarinis šaltinis prieš polygon-derived plotus.

Šis prompt'as kviečiamas tik kai pdfplumber nepavyko (nėra text layer, scanned).
"""
