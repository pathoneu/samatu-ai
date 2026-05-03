"""Claude Sonnet first-pass count for ground-truth bootstrapping.

Given a rendered page + a list of (symbol_code, description_lt) tuples,
ask Claude to count each one. Output a draft GroundTruth that the user
edits to correct.

This is INTENTIONALLY not part of any benchmark pipeline — it's the GT
generator. Using Claude to seed Claude's-own-baseline-test would bias
results, so this is structurally separate.
"""

from __future__ import annotations
import os
import json
import base64
from io import BytesIO
from pathlib import Path

import anthropic
from PIL import Image

from detector_bench.core.pdf_loader import render_page
from detector_bench.core.ground_truth import GroundTruth

CLAUDE_MODEL = "claude-sonnet-4-6"


PROMPT_TEMPLATE = """You are counting construction symbols on a Lithuanian project drawing.

The page shows a floor plan with various symbols. The legend tells you what
each symbol code means:

{legend_block}

For each symbol code below, count how many INSTANCES appear on this page (not
in the legend itself — only on the actual drawing). Answer ONLY with valid JSON
mapping symbol_code → count. Be precise; do not approximate.

Symbols to count: {symbols}

CRITICAL OUTPUT FORMAT: Your entire response must be a single JSON object.
No prose, no explanations, no markdown fences, no thinking out loud.
First character must be `{{`, last character must be `}}`.
Example exact format: {{"iš.1": 12, "pš.1": 4}}"""


def first_pass_count(
    pdf_path: Path, page_nr: int, legend_items: list[dict],
) -> dict[str, int]:
    """Returns {symbol_code: AI's-best-guess-count}."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    if not legend_items:
        return {}

    legend_block = "\n".join(
        f"  {it['symbol_code']}: {it.get('description_lt', '')}"
        for it in legend_items
    )
    symbols = [it["symbol_code"] for it in legend_items]

    arr = render_page(Path(pdf_path), page_nr, dpi=200)
    img = Image.fromarray(arr)
    buf = BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")

    prompt = PROMPT_TEMPLATE.format(
        legend_block=legend_block, symbols=symbols,
    )

    client = anthropic.Anthropic()
    resp = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=2000,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64}},
                    {"type": "text", "text": prompt},
                ],
            }
        ],
    )
    text = resp.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json\n"):
            text = text[5:]
        text = text.rstrip("`").strip()
    # Sonnet 4.6 sometimes prefaces with chain-of-thought before the JSON
    # object even when told not to. Fall back to extracting the last balanced
    # {...} block (or first ```json fenced block) from the response.
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = _extract_json_object(text)
        if data is None:
            raise ValueError(
                f"Claude returned non-JSON, no embedded {{...}} found:\n{text[:500]}"
            )
    return {k: int(v) for k, v in data.items()}


def _extract_json_object(text: str) -> dict | None:
    """Find the last balanced {...} JSON object in arbitrary text.

    Scans right-to-left so trailing `{...}` (the actual answer) wins over any
    earlier `{` characters in prose.
    """
    # Try fenced ```json blocks first
    fence = "```json"
    if fence in text:
        rest = text.split(fence, 1)[1]
        body = rest.split("```", 1)[0].strip()
        try:
            obj = json.loads(body)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass
    # Fall back: brace-balanced scan from the right
    end = text.rfind("}")
    while end != -1:
        depth = 0
        for i in range(end, -1, -1):
            ch = text[i]
            if ch == "}":
                depth += 1
            elif ch == "{":
                depth -= 1
                if depth == 0:
                    candidate = text[i:end + 1]
                    try:
                        obj = json.loads(candidate)
                        if isinstance(obj, dict):
                            return obj
                    except json.JSONDecodeError:
                        break
        end = text.rfind("}", 0, end)
    return None
