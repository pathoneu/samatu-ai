"""Pipeline 1 — Baseline Claude Vision direct.

Renders the page, sends to Claude Sonnet, asks "count instances of
{symbol_code}." No legend grounding, no tools, no chain. Reference
for "if we hadn't built anything else, what would AI alone do?"
"""

from __future__ import annotations
import os
import time
import base64
import json
from io import BytesIO
from pathlib import Path

import anthropic
from PIL import Image

from detector_bench.core.types import Detector, DetectionResult, BBox
from detector_bench.core.pdf_loader import render_page
from detector_bench.core.first_pass_count import _extract_json_object

CLAUDE_MODEL = "claude-sonnet-4-6"
# Anthropic Sonnet 4.6 input pricing: $3/MTok input, $15/MTok output (approx).
# Each call sends ~1.5 MB image as base64 → ~2000 tokens; ~50 tokens output.
# Cost ≈ ($3 * 2000 / 1e6) + ($15 * 50 / 1e6) ≈ $0.0068 per call. Round to $0.01.
COST_PER_CALL_USD = 0.01


class BaselineVisionDetector(Detector):
    name = "p1_baseline_vision"

    def setup(self, pdf_path: Path) -> None:
        # No setup — each detect() is independent.
        pass

    def detect(self, pdf_path: Path, page_nr: int, symbol_code: str) -> DetectionResult:
        t0 = time.time()
        try:
            arr = render_page(pdf_path, page_nr, dpi=200)
            img = Image.fromarray(arr)
            buf = BytesIO()
            img.save(buf, format="PNG")
            b64 = base64.b64encode(buf.getvalue()).decode("ascii")

            client = anthropic.Anthropic()
            resp = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=200,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64}},
                            {"type": "text", "text": (
                                f"How many instances of the symbol '{symbol_code}' appear on this construction "
                                f"drawing? Return ONLY a JSON object: {{\"count\": <integer>}}. "
                                f"No prose, no explanation."
                            )},
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
            # Sonnet 4.6 sometimes prefaces JSON with chain-of-thought even when
            # told not to. Reuse the same fallback as first_pass_count.
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                data = _extract_json_object(text)
                if data is None:
                    raise ValueError(
                        f"Claude returned non-JSON, no embedded {{...}} found:\n{text[:500]}"
                    )
            count = int(data["count"])
            return DetectionResult(
                count=count, bboxes=[],
                runtime_s=time.time() - t0, cost_usd=COST_PER_CALL_USD,
                errors=[], notes=f"raw response: {text[:100]}",
            )
        except Exception as e:
            return DetectionResult(
                count=0, bboxes=[],
                runtime_s=time.time() - t0, cost_usd=COST_PER_CALL_USD,
                errors=[str(e)],
                notes="failed",
            )
