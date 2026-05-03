"""Pipeline 6 — Claude Sonnet 4.6 with tool use, orchestrating a CV counter.

Claude reads the legend page, then for each symbol calls a tool we provide:
    count_via_template(symbol_code, page_nr) → int

The tool internally runs cv2.matchTemplate (Pipeline 3 logic). Claude's value:
deciding which symbol is which and providing context-aware threshold tuning
("this is a small icon, use higher threshold; this is a large badge, use
lower threshold"). For our benchmark we let it use a default threshold and
just return the deterministic count.
"""

from __future__ import annotations
import os
import time
import json
import base64
from io import BytesIO
from pathlib import Path

import anthropic
from PIL import Image

from detector_bench.core.types import Detector, DetectionResult, BBox
from detector_bench.core.pdf_loader import render_page
from detector_bench.detectors.p3_template_match import TemplateMatchDetector

CLAUDE_MODEL = "claude-sonnet-4-6"
COST_PER_CALL_USD = 0.02  # Higher than baseline due to tool roundtrips


class ClaudeToolOrchestratedDetector(Detector):
    name = "p6_claude_tool_orch"

    def __init__(self) -> None:
        self._template_det = TemplateMatchDetector(threshold=0.75)

    def setup(self, pdf_path: Path) -> None:
        self._template_det.setup(pdf_path)

    def detect(self, pdf_path: Path, page_nr: int, symbol_code: str) -> DetectionResult:
        t0 = time.time()
        if not os.environ.get("ANTHROPIC_API_KEY"):
            return DetectionResult(
                count=0, bboxes=[], runtime_s=0.0, cost_usd=0.0,
                errors=["ANTHROPIC_API_KEY not set"], notes="skipped",
            )

        try:
            arr = render_page(pdf_path, page_nr, dpi=200)
            img = Image.fromarray(arr)
            buf = BytesIO()
            img.save(buf, format="PNG")
            b64 = base64.b64encode(buf.getvalue()).decode("ascii")

            tools = [{
                "name": "count_via_template",
                "description": "Count instances of a symbol on the current page via deterministic OpenCV template match. Returns integer count.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "symbol_code": {"type": "string", "description": "Symbol code from the legend"},
                        "threshold": {"type": "number", "description": "Match threshold 0-1 (default 0.75)"},
                    },
                    "required": ["symbol_code"],
                },
            }]

            client = anthropic.Anthropic()
            messages = [{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64}},
                    {"type": "text", "text": (
                        f"You are counting symbol '{symbol_code}' on this construction drawing. "
                        f"Use the count_via_template tool to get a deterministic count. "
                        f"Adjust threshold if you think the default 0.75 is too strict (small/varied symbols) "
                        f"or too lenient (common-looking glyphs). Return ONLY the final integer count via the tool result; "
                        f"no prose."
                    )},
                ],
            }]

            # Tool-use loop
            count = 0
            for _ in range(3):  # max 3 iterations
                resp = client.messages.create(
                    model=CLAUDE_MODEL,
                    max_tokens=2000,
                    tools=tools,
                    messages=messages,
                )
                if resp.stop_reason == "tool_use":
                    tool_blocks = [b for b in resp.content if b.type == "tool_use"]
                    if not tool_blocks:
                        break
                    tu = tool_blocks[0]
                    args = tu.input or {}
                    sym = args.get("symbol_code", symbol_code)
                    thr = float(args.get("threshold", 0.75))
                    self._template_det.threshold = thr
                    sub = self._template_det.detect(pdf_path, page_nr, sym)
                    count = sub.count
                    messages.append({"role": "assistant", "content": resp.content})
                    messages.append({
                        "role": "user",
                        "content": [{
                            "type": "tool_result",
                            "tool_use_id": tu.id,
                            "content": str(sub.count),
                        }],
                    })
                else:
                    # End of conversation; final count was set in last tool_result
                    break

            return DetectionResult(
                count=count, bboxes=[],  # Tool doesn't propagate bboxes back
                runtime_s=time.time() - t0, cost_usd=COST_PER_CALL_USD,
                errors=[],
                notes="claude orchestrated template match",
            )
        except Exception as e:
            return DetectionResult(
                count=0, bboxes=[], runtime_s=time.time() - t0,
                cost_usd=COST_PER_CALL_USD, errors=[str(e)], notes="failed",
            )
