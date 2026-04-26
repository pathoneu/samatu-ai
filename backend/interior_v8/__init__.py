"""
V8 — UNIVERSAL Takeoff System.

Industries standart pagrindas:
- RICS NRM2 (UK)
- DIN 18363 / VOB Part C (Germany)
- CSI MasterFormat 09 91 (US)
- Sherwin-Williams / Benjamin Moore / Tikkurila kalkuliatorių formulės
- Easy Takeoffs / Togal AI / Kreo metodologijos

Pagrindinis principas:
- VISI gyvenamosios paskirties patalpos dažomos
- Vonios/WC: tik virš plytelinės juostos (default 2.0m)
- Garažas / tambūras: NEDAŽOMI (betonas)
- Drabužinės: PILNAI dažomos (Easy Takeoffs research patvirtino:
  closet interiors should be included)
- Angos > 1m² atimamos (NRM2 Section 29 rule)
- Waste factors per material type
- Coverage rates per surface

Vartotojas vėliau per Setup Wizard gali pakeisti standart taisykles
pagal SAVO praktiką (rangovo profilis).
"""

from .universal_engine import (
    extract_v8,
    UNIVERSAL_RULES,
    ROOM_TYPE_RULES,
)
from .scale_detector import (
    auto_detect_scale,
    detect_scale_from_text,
    detect_scale_from_dimensions,
    validate_scale_via_sanity,
)
from .page_classifier import (
    classify_page,
    classify_pdf,
    summarize as summarize_pages,
)
from .lt_area_calculator import (
    mansardinis_svoris, calc_room_area_with_mansard,
    is_open_space, get_open_space_paskirtis, calc_open_space_features,
)
from .lt_sanity import (
    validate_rooms as lt_validate_rooms,
    validate_v8_output as lt_validate_v8,
)
from .line_extractor import (
    extract_lines_for_page,
    extract_lines_all_pages,
)
# Eksplikacijos lentelės parser (V6 Tier 1 atstatyta)
from .eksplikacija_parser import (
    extract_eksplikacija_from_pdf,
    parse_eksplikacija_text,
)
# Vision pipeline (migrated from interior_v7)
from .vision_extract import extract_v7
from .vision_helpers import (
    _get_client, _pdf_to_pages, _resize_b64, _clean_json_text,
)
# Pasiūlymas generation (migrated from interior_v5)
from .pasiulymas import generate_pasiulymas

__all__ = [
    "extract_v8", "UNIVERSAL_RULES", "ROOM_TYPE_RULES",
    "auto_detect_scale", "detect_scale_from_text",
    "detect_scale_from_dimensions", "validate_scale_via_sanity",
    "classify_page", "classify_pdf", "summarize_pages",
    "extract_lines_for_page", "extract_lines_all_pages",
    "lt_validate_rooms", "lt_validate_v8",
    "mansardinis_svoris", "calc_room_area_with_mansard",
    "is_open_space", "get_open_space_paskirtis", "calc_open_space_features",
    "extract_v7",  # Vision pipeline
    "generate_pasiulymas",  # Pasiūlymas
]
