"""Haiku 4.5 page classifier (canonical plan Week 3 Task 3.3).

Replaces the legacy 4700-token mega-prompt that ran the same instructions
across every page type (floor plan, ceiling, išklotinė, electrical, etc.).
Routing per page is ~$0.001/page (Haiku 4.5) — cheap relative to Opus 4.7
extraction cost — and Opus's specialised prompts stay focused.

When confidence < 0.85 we expose `top_2` so the specialised Opus prompt
can handle the wrong-page-type case without a full re-classify roundtrip.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json

import anthropic

HAIKU_MODEL = "claude-haiku-4-5-20251001"


class PageType(str, Enum):
    FLOOR_PLAN = "floor_plan"
    CEILING_PLAN = "ceiling_plan"
    WALL_ELEVATION = "wall_elevation"
    ELECTRICAL = "electrical"
    PLUMBING = "plumbing"
    EKSPLIKACIJA = "eksplikacija"
    LEGEND = "legend"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class PageClassification:
    """Output of one page classification."""
    page_type: PageType
    confidence: float
    top_2: PageType | None = None


_CLASSIFIER_SYSTEM = """You classify a Lithuanian construction drawing page.

Return strict JSON:
  {
    "page_type": "floor_plan" | "ceiling_plan" | "wall_elevation" |
                 "electrical" | "plumbing" | "eksplikacija" | "legend" | "unknown",
    "confidence": 0.0-1.0,
    "top_2": same enum or null
  }

Hints:
- "Aukšto planas" / wall hatching + room polygons → floor_plan
- "Lubų planas" / dropped-ceiling zones + light fixtures → ceiling_plan
- "Sienų išklotinė" / vertical wall view + tile zones → wall_elevation
- "Rozečių/apšvietimo planas" / electrical symbols → electrical
- "Santechnikos planas" / plumbing fixtures → plumbing
- "Patalpų eksplikacija" / room schedule table → eksplikacija
- Symbol legend with key-value rows → legend

If confidence < 0.95, set top_2 to the second-best candidate.
"""

_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["page_type", "confidence"],
    "properties": {
        "page_type": {"type": "string", "enum": [pt.value for pt in PageType]},
        "confidence": {"type": "number"},
        "top_2": {
            "type": ["string", "null"],
            "enum": [pt.value for pt in PageType] + [None],
        },
    },
}


def parse_classification(payload: dict) -> PageClassification:
    """Convert Haiku JSON output into a typed `PageClassification`."""
    return PageClassification(
        page_type=PageType(payload["page_type"]),
        confidence=float(payload["confidence"]),
        top_2=PageType(payload["top_2"]) if payload.get("top_2") else None,
    )


def _call_haiku(image_b64: str, client: anthropic.Anthropic | None = None) -> PageClassification:
    """Single-page classification via Haiku 4.5.

    Production callers pass their own client; tests inject a fake.
    """
    client = client or anthropic.Anthropic()
    resp = client.messages.create(
        model=HAIKU_MODEL,
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
                "json_schema": {"name": "PageClassification", "schema": _SCHEMA},
            },
            "effort": "low",
        },
    )
    payload = json.loads(resp.content[0].text)
    return parse_classification(payload)


def classify_page(image_b64: str, client: anthropic.Anthropic | None = None) -> PageClassification:
    """Public entry: route a single rendered page to its type.

    Caller is responsible for batching pages and dispatching to the
    appropriate specialised Opus prompt. Errors propagate — we'd rather
    surface a failed classification than silently route to the wrong prompt.
    """
    return _call_haiku(image_b64, client=client)
