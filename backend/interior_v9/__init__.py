"""
V9 — Vector + Set-of-Marks + Multi-pass pipeline (skill A.5 + A.2 + A.3).

Architektūra:
1. pdfplumber → lines + rects → Shapely polygonize (su endpoint snap)
2. Per puslapį pre-skaičiuoti polygons + plotai (DETERMINISTINIS)
3. Render PDF + SoM overlay (raudoni skaičiai per polygon)
4. Vision call: KLASIFIKACIJA tik (paskirtis, pavadinimas) — NE matavimas
5. Multi-pass (3 nepriklausomi) → median paskirtis vote
6. V8 universal_engine pritaiko formules

Privalumai prieš V7/V8:
- Plotai DETERMINISTINIAI (visada tas pats rezultatas)
- Vision tik atpažįsta KAS (paskirtis), nematuoja
- ~60% mažiau Vision tokens (mažiau JSON output'o)
- bbox koordinates 100% tikslūs (iš vector PDF)
- Mažesnė variance (mažesnis ploto klaidos)
"""
from .pipeline_v9 import extract_v9
from .vector_polygons import build_room_polygons
from .som_renderer import render_pdf_with_som
from .vision_classifier import classify_rooms_with_som
from .symbol_detector import (
    detect_symbols,
    detect_symbols_bundled,
    detect_all_symbols_for_pdf,
    count_symbols_by_template,
    list_symbol_types_for_page_type,
    SYMBOL_TYPES,
)

__all__ = [
    "extract_v9",
    "build_room_polygons",
    "render_pdf_with_som",
    "classify_rooms_with_som",
    "detect_symbols",
    "detect_all_symbols_for_pdf",
    "count_symbols_by_template",
    "list_symbol_types_for_page_type",
    "SYMBOL_TYPES",
]
