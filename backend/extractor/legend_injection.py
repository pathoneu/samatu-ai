"""Sonnet 4.6 legend extractor + Opus prompt injection helper.

Replaces hard-coded color/glyph mappings (the legacy mega-prompt assumed
specific colors meant specific things; that broke whenever an architect
used a different convention) with per-project legends extracted dynamically.
Output is spliced into specialized Opus prompts so when an architect uses
different conventions, recognition stays accurate.

Stage 1 (here): `extract_legend(image_b64)` runs Sonnet 4.6 on the legend
page and returns a structured mapping.
Stage 2: `build_legend_block(legend)` renders that mapping as a text block;
`inject_legend(prompt, legend)` composes the final system text used by
`vision_call_v2.call_opus_vision`.
"""
from __future__ import annotations

import json
import anthropic

from models_config import model_for  # role: "legend" — resolved at call time
from .response_text import ModelStopped, read_answer, usage_meta


_LEGEND_SYSTEM = """Extract the symbol legend from this LT construction drawing.

Return strict JSON:
{
  "symbols": [
    {
      "glyph": "string|null",            // textual glyph description (e.g. "circle_with_cross")
      "colored_line": "#RRGGBB|null",    // colored stroke if applicable
      "colored_hatch": "#RRGGBB|null",   // colored area fill if applicable
      "meaning": "led_strip|ceiling_light|smoke_detector|...",
      "confidence": 0.0-1.0
    }
  ]
}

Guidelines:
- Three rule layers (Council R3): glyph (iconic mark), colored_line (stroke
  pattern + color), colored_hatch (area fill + color). They are NOT mutually
  exclusive but you should populate only the field(s) the legend actually
  uses. A glyph alone → only `glyph`. A colored stroke without iconic mark
  → only `colored_line`.
- Do not invent meaning. If a row's text is illegible, return raw text in
  `meaning` prefixed with `unknown:` so the user can override later.
"""


_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["symbols"],
    "properties": {
        "symbols": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["meaning"],
                "properties": {
                    "glyph": {"type": ["string", "null"]},
                    "colored_line": {"type": ["string", "null"]},
                    "colored_hatch": {"type": ["string", "null"]},
                    "meaning": {"type": "string"},
                    "confidence": {"type": "number"},
                },
            },
        },
    },
}


def extract_legend(legend_image_b64: str, client: anthropic.Anthropic | None = None) -> dict:
    """Run the legend-role model over a legend page; return canonical mapping
    (plus a `_meta` block with model + token usage for cost telemetry)."""
    client = client or anthropic.Anthropic(max_retries=1)
    model = model_for("legend")  # call-time resolution (MODEL_OVERRIDE etc.)
    resp = client.messages.create(
        model=model,
        max_tokens=4096,  # raised at Opus 5 cutover: thinking counts against the cap
        system=[{
            "type": "text",
            "text": _LEGEND_SYSTEM,
            "cache_control": {"type": "ephemeral", "ttl": "1h"},
        }],
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": "Legend page:"},
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": legend_image_b64,
                    },
                },
            ],
        }],
        output_config={
            "format": {"type": "json_schema", "json_schema": {"name": "Legend", "schema": _SCHEMA}},
            "effort": "high",
        },
    )
    raw, stopped = read_answer(resp, reader="legend_injection")
    if stopped:  # refused / cut off: named, usage kept (2026-09-30)
        raise ModelStopped(stopped, usage_meta(resp, model))
    legend = json.loads(raw)
    usage = getattr(resp, "usage", None)
    legend["_meta"] = {
        "model": model,
        "input_tokens": getattr(usage, "input_tokens", None),
        "output_tokens": getattr(usage, "output_tokens", None),
    }
    return legend


def build_legend_block(legend: dict) -> str:
    """Render the legend dict as a text block to splice into Opus prompts.

    Inserted between BASE_RULES and the page-type-specific instructions so
    Opus reads the project's own conventions BEFORE applying any defaults.
    """
    lines = ["PROJECT LEGEND (USE INSTEAD OF GENERIC COLOR CONVENTIONS):"]
    for sym in legend.get("symbols", []) or []:
        keys = []
        for k in ("glyph", "colored_line", "colored_hatch"):
            v = sym.get(k)
            if v:
                keys.append(f"{k}={v}")
        if not keys:
            continue
        lines.append(f"- {', '.join(keys)} → {sym.get('meaning', 'unknown')}")
    if len(lines) == 1:
        # No legend extracted — be explicit.
        lines.append("(no legend detected; do not apply default color rules)")
    lines.append(
        "If a visual mark is not in this legend, return type='unknown_symbol' "
        "with visual properties; do not guess from generic color rules."
    )
    return "\n".join(lines)


def inject_legend(prompt: str, legend: dict | None) -> str:
    """Compose final system text with legend block placed before page-type rules."""
    if not legend:
        return prompt
    return f"{prompt}\n\n{build_legend_block(legend)}"
