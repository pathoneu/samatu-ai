"""Opus 4.7 vision call (canonical plan Week 3 Task 3.1).

Replaces the legacy regex-repair fallback with native `output_config.format`
strict JSON schema enforcement (GA on Opus 4.7 in 2026). Sets explicit 1h
cache TTL to dodge the March 2026 silent default-TTL regression to 5min.

Cache invariant: SYSTEM block carries the breakpoint; MESSAGES carry images.
Reversing this would invalidate the prompt cache on every PDF.

Why a v2 file rather than editing legacy `vision_call.py` directly:
  The legacy module is wired into the live `/extract-interior` route. We add
  this v2 helper alongside it so new specialized prompts can adopt strict
  JSON without disturbing in-flight beta traffic. When the page-router cutover
  lands, the existing route swaps `vision_call.py` → `vision_call_v2`.
"""
from __future__ import annotations

from typing import Any

import anthropic

from models_config import model_for

DEFAULT_MAX_TOKENS = 12_000

# Heavy vision turns on Fable 5 can run many minutes — per-call timeout
# override (never mutate the caller's global client config).
VISION_TIMEOUT_S = 600.0


def call_opus_vision(
    client: anthropic.Anthropic,
    *,
    system_text: str,
    messages: list[dict],
    schema: dict,
    effort: str = "high",
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> Any:
    """Call Opus 4.7 vision with strict JSON output.

    Args:
        client: Anthropic SDK client.
        system_text: Lithuanian role/instruction text. Cached server-side
            with explicit 1h TTL.
        messages: User-role content array. Image blocks must NOT precede the
            cache breakpoint (rule 7 of plan hard rules).
        schema: JSON schema dict describing the expected response shape.
        effort: `"high"` (Pass 1) or `"xhigh"` (Pass 2 measurement).
        max_tokens: Output cap.

    Returns:
        Anthropic Message object whose content is guaranteed valid JSON
        matching `schema` (or stop_reason='refusal' on schema impossibility).
    """
    return client.with_options(timeout=VISION_TIMEOUT_S).messages.create(
        model=model_for("vision_pass1"),
        max_tokens=max_tokens,
        system=[
            {
                "type": "text",
                "text": system_text,
                "cache_control": {"type": "ephemeral", "ttl": "1h"},
            }
        ],
        messages=messages,
        output_config={
            "format": {
                "type": "json_schema",
                "json_schema": {"name": "primitives", "schema": schema},
            },
            "effort": effort,
        },
    )


def build_image_message(pages: list[dict], final_instruction: str) -> dict:
    """Compose the user-role message with text-label-before-image structure.

    Anthropic guidance (R2): Claude works best when each image is preceded by
    a short text label. Pattern:
        [text:"Page 1 of N:", image, text:"Page 2 of N:", image, ..., text:final]
    """
    n = len(pages)
    content: list[dict] = []
    for p in pages:
        content.append({"type": "text", "text": f"Page {p['page_index']} of {n}:"})
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": p["image_b64"],
            },
        })
    content.append({"type": "text", "text": final_instruction})
    return {"role": "user", "content": content}
