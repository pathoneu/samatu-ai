"""Haiku 4.5 page classifier (canonical plan Week 3 Task 3.3).

Replaces the legacy 4700-token mega-prompt that ran the same instructions
across every page type (floor plan, ceiling, išklotinė, electrical, etc.).
Routing per page is ~$0.001/page (Haiku 4.5) — cheap relative to Opus 4.7
extraction cost — and Opus's specialised prompts stay focused.

When confidence < 0.85 we expose `top_2` so the specialised Opus prompt
can handle the wrong-page-type case without a full re-classify roundtrip.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path
import json
import re

import anthropic
import pdfplumber

# Model tiers — pick at call site. Default is the historical Haiku
# choice, but stogai V1 bake-off (2026-05-14) treats this as a
# parameter, not a default. Promote based on empirical evaluation
# results, not assumption.
HAIKU_MODEL = "claude-haiku-4-5-20251001"
SONNET_MODEL = "claude-sonnet-4-6"
OPUS_MODEL = "claude-opus-4-7"
# Empirical default (set 2026-05-14 from A LAIDA bake-off, commit e7f99f3):
# Sonnet matches Opus on `roof_type_hint` (the safety-critical signal —
# Haiku failed) at 5× lower cost. Opus stays available for premium /
# customer-facing extractions where the 5× cost is worth absolute max
# accuracy. Re-validate this default whenever the eval set grows.
DEFAULT_MODEL = SONNET_MODEL

# LT statybų projektų dalies (sections) — codes as they appear in the
# `Dokumento žymuo` field of the antspaudas (title block):
#   BD = Bendroji dalis             SP = Sklypo planas
#   SA = Statybinė architektūra     SK = Statybinės konstrukcijos
#   VVN = Vandentiekio ir nuotekynių     E = Elektrotechnika
#   ŠVOK = Šildymas, vėdinimas, oro kondicionavimas (ASCII fallback: SVOK)
_DALIES = ("BD", "SP", "SA", "SK", "VVN", "ŠVOK", "SVOK", "E")

# Lower-right crop covers most LT studio antspaudai (40-100% width, 70-100%
# height). Tuned empirically against `1_BD.pdf`, `03_SA.pdf`, `SA-02.pdf`.
_ANTSPAUDAS_BBOX = (0.40, 0.70, 1.00, 1.00)

# Match the document-code pattern `*-DALIS{sep}DOCTYPE` where the
# separator between dalis and doc-type is either `.` or `-`. LT studios
# differ: `P2515-TDP-SA.ŽN` (Endive/Jektera-style) vs `ARCH-22-12-TS-BD-TS`
# (Mai-style). The dalis must be preceded by `-` or whitespace (so we
# don't match LT capitals appearing mid-word) and followed by 1-4
# capital letters (the doc-type suffix: AR aiškinamasis raštas, ŽN
# žiniaraštis, TS techninės specifikacijos, BR brėžinys, …).
_DOC_CODE_RE = re.compile(
    r"[-\s]\s*(" + "|".join(_DALIES) + r")[.\-][A-ZŠŽĄČĘĖĮŲŪ]{1,4}"
)


class PageType(str, Enum):
    FLOOR_PLAN = "floor_plan"
    CEILING_PLAN = "ceiling_plan"
    WALL_ELEVATION = "wall_elevation"
    SECTION = "section"          # Pjūvis: vertical cut + slab height markers (+0.000 / +2.800)
    STOGO_PLANAS = "stogo_planas"  # Roof plan — top-down view of roof with slopes/ridges
    ELECTRICAL = "electrical"
    PLUMBING = "plumbing"
    EKSPLIKACIJA = "eksplikacija"
    LEGEND = "legend"
    UNKNOWN = "unknown"


class Dalis(str, Enum):
    """LT statybų projekto dalies (building-section codes) — values
    match what appears in the antspaudas `Dokumento žymuo` field."""
    BD = "BD"        # Bendroji dalis
    SP = "SP"        # Sklypo planas
    SA = "SA"        # Statybinė architektūra
    SK = "SK"        # Statybinės konstrukcijos
    VVN = "VVN"      # Vandentiekio ir nuotekynių
    SVOK = "ŠVOK"    # Šildymas, vėdinimas, oro kondicionavimas
    E = "E"          # Elektrotechnika
    UNKNOWN = "unknown"


class RoofTypeHint(str, Enum):
    """Roof-shape hint extracted from drawings — drives strategy dispatch."""
    DVISLAITIS = "dvislaitis"            # two-slope gable
    KETURSLAITIS = "keturslaitis"        # four-slope hip
    VIENSLAITIS = "vienslaitis"          # mono-pitch shed
    MANSARDINIS = "mansardinis"          # mansard
    PLOKSCIAS = "plokscias"              # flat
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class PageClassification:
    """Output of one page classification.

    `dalis` and `roof_type_hint` are additive (Phase 1 T2). Image-only
    callers may leave them as None; the hybrid classifier (T3) populates
    `dalis` from antspaudas text and asks Haiku for `roof_type_hint`.
    """
    page_type: PageType
    confidence: float
    top_2: PageType | None = None
    dalis: Dalis | None = None
    roof_type_hint: RoofTypeHint | None = None


_CLASSIFIER_SYSTEM = """You classify a Lithuanian construction drawing page.

Return strict JSON:
  {
    "page_type": "floor_plan" | "ceiling_plan" | "wall_elevation" |
                 "section" | "stogo_planas" | "electrical" | "plumbing" |
                 "eksplikacija" | "legend" | "unknown",
    "confidence": 0.0-1.0,
    "top_2": same enum or null,
    "dalis": "BD" | "SP" | "SA" | "SK" | "VVN" | "ŠVOK" | "E" | "unknown" | null,
    "roof_type_hint": "dvislaitis" | "keturslaitis" | "vienslaitis" |
                      "mansardinis" | "plokscias" | "unknown" | null
  }

Hints — page_type:
- "Aukšto planas" / wall hatching + room polygons → floor_plan
- "Lubų planas" / dropped-ceiling zones + light fixtures → ceiling_plan
- "Sienų išklotinė" / vertical wall view + tile zones → wall_elevation
- "Pjūvis" / vertical building cross-section with `±0.000`/`+2.800`
  level markers → section  (canonical source for ceiling slab heights)
- "Stogo planas" / top-down view of the roof showing slopes, ridges
  (kraigai), valleys (latakai), chimneys → stogo_planas  (canonical
  source for roof geometry: footprint, eaves, roof type)
- "Rozečių/apšvietimo planas" / electrical symbols → electrical
- "Santechnikos planas" / plumbing fixtures → plumbing
- "Patalpų eksplikacija" / room schedule table → eksplikacija
- Symbol legend with key-value rows → legend

Hints — dalis (LT building-section code from the antspaudas title block):
- BD = Bendroji dalis     SP = Sklypo planas     SA = Statybinė architektūra
- SK = Statybinės konstrukcijos    VVN = Vandentiekio/ nuotekynių
- ŠVOK = Šildymas, vėdinimas, oro kondicionavimas    E = Elektrotechnika
Return null if no antspaudas is visible or the code cannot be read.

Hints — roof_type_hint (only set when the page shows a roof plan or
roof-relevant pjūvis; otherwise null):
- Two slopes meeting at a single ridge + two gable walls → dvislaitis
- Four slopes meeting at a ridge or apex, all sides slope → keturslaitis
- Single sloped plane, one high wall and one low → vienslaitis
- Double slope on each side with a break line → mansardinis
- Roof pitch ≤ 3° with parapet → plokscias

If confidence < 0.95, set top_2 to the second-best candidate.
"""

_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["page_type", "confidence"],
    "properties": {
        "page_type": {"type": "string", "enum": [pt.value for pt in PageType]},
        "confidence": {"type": "number"},
        # All enums include the "unknown" sentinel — Anthropic's
        # structured-output engine rejects `["string", "null"]` type
        # arrays, so we use "unknown" as the in-band null. Parser
        # collapses `top_2 == "unknown"` to None (no second candidate),
        # but preserves UNKNOWN for `dalis` / `roof_type_hint` (semantic:
        # model tried and couldn't tell, vs. wasn't asked).
        "top_2": {"type": "string", "enum": [pt.value for pt in PageType]},
        "dalis": {"type": "string", "enum": [d.value for d in Dalis]},
        "roof_type_hint": {"type": "string", "enum": [r.value for r in RoofTypeHint]},
    },
}


def _coerce_enum(enum_cls, raw):
    """Map a JSON value to an enum member, or None if absent/null."""
    if raw is None:
        return None
    return enum_cls(raw)


def parse_classification(payload: dict) -> PageClassification:
    """Convert vision-model JSON output into a typed `PageClassification`.

    Tolerant of pre-T2 payloads (no `dalis` / `roof_type_hint` keys) and
    of explicit nulls. For `page_type` / `dalis` / `roof_type_hint` the
    string `"unknown"` is preserved as the enum's UNKNOWN sentinel (NOT
    collapsed to None — model tried and couldn't tell). For `top_2`
    only, `"unknown"` collapses to None (a "second-best of unknown"
    is meaningless).
    """
    top_2_raw = payload.get("top_2")
    top_2 = (
        PageType(top_2_raw)
        if top_2_raw and top_2_raw != "unknown"
        else None
    )
    return PageClassification(
        page_type=PageType(payload["page_type"]),
        confidence=float(payload["confidence"]),
        top_2=top_2,
        dalis=_coerce_enum(Dalis, payload.get("dalis")),
        roof_type_hint=_coerce_enum(RoofTypeHint, payload.get("roof_type_hint")),
    )


def _call_haiku(
    image_b64: str,
    client: anthropic.Anthropic | None = None,
    model: str = DEFAULT_MODEL,
) -> PageClassification:
    """Single-page classification via a Claude vision model.

    Function name kept for backward compatibility — `model` may be Haiku,
    Sonnet, or Opus. Production callers pass their own client; tests
    inject a fake.
    """
    client = client or anthropic.Anthropic()
    resp = client.messages.create(
        model=model,
        max_tokens=200,
        system=[{
            "type": "text",
            "text": _CLASSIFIER_SYSTEM,
            "cache_control": {"type": "ephemeral", "ttl": "1h"},
        }],
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": "Classify this page:"},
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": image_b64,
                    },
                },
            ],
        }],
        output_config={
            "format": {
                "type": "json_schema",
                "schema": _SCHEMA,
            },
        },
    )
    payload = json.loads(resp.content[0].text)
    return parse_classification(payload)


def _extract_antspaudas_text(pdf_path: str | Path, page_num: int) -> str | None:
    """Extract the LT dalis code from a page's antspaudas (title block).

    LT brėžiniai stamp the dalis code in the lower-right title block via a
    document number like `P2515-TDP-SA.ŽN`. This function crops to the
    lower-right region, extracts text via pdfplumber, and matches the
    document-code pattern. Raster-flattened pages (no text layer) and
    cover sheets (no antspaudas) return None — Haiku vision fallback
    (Phase 1 T3) handles those.

    Args:
        pdf_path: Path to the PDF file.
        page_num: 1-indexed page number.

    Returns:
        Detected dalis code (one of BD/SP/SA/SK/VVN/ŠVOK/E) or None if no
        recognisable code is present. The ASCII variant `SVOK` is
        normalised to `ŠVOK`.

    Raises:
        ValueError: if `page_num < 1`.
        IndexError: if `page_num` exceeds the PDF's page count.
    """
    if page_num < 1:
        raise ValueError(f"page_num is 1-indexed; got {page_num}")

    with pdfplumber.open(str(pdf_path)) as pdf:
        if page_num > len(pdf.pages):
            raise IndexError(
                f"page_num {page_num} out of range (PDF has {len(pdf.pages)} pages)"
            )
        page = pdf.pages[page_num - 1]
        w, h = page.width, page.height
        x0, y0, x1, y1 = _ANTSPAUDAS_BBOX
        crop = page.within_bbox((w * x0, h * y0, w * x1, h * y1))
        text = crop.extract_text() or ""

    match = _DOC_CODE_RE.search(text)
    if not match:
        return None
    code = match.group(1)
    return "ŠVOK" if code == "SVOK" else code


def classify_page(
    image_b64: str,
    client: anthropic.Anthropic | None = None,
    *,
    pdf_path: str | Path | None = None,
    page_num: int | None = None,
    model: str = DEFAULT_MODEL,
) -> PageClassification:
    """Public entry: classify one rendered page (hybrid text-first + vision).

    Pure-image callers (legacy) get vision-only behaviour. When BOTH
    `pdf_path` and `page_num` are supplied, `_extract_antspaudas_text`
    runs first; if it finds a dalis code, that value OVERRIDES the
    vision model's answer for `dalis` (text is deterministic, vision is
    probabilistic). Page type and roof-type hint always come from the
    vision model.

    `model` selects Haiku/Sonnet/Opus — empirical bake-off result drives
    the choice in production.

    Raster-flattened pages whose antspaudas can't be read by pdfplumber
    silently fall through to the vision model's value — this is the
    fallback the plan calls out for studios that flatten their PDFs.

    Errors propagate — we'd rather surface a failed classification than
    silently route to the wrong downstream prompt.
    """
    result = _call_haiku(image_b64, client=client, model=model)
    if pdf_path is not None and page_num is not None:
        text_dalis = _extract_antspaudas_text(pdf_path, page_num)
        if text_dalis is not None:
            result = replace(result, dalis=Dalis(text_dalis))
    return result
