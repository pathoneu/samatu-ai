"""Pipeline 5 — GroundingDINO open-vocabulary detection via Replicate.

Sends the rendered page + a text prompt ("electrical outlet symbol") to a
pretrained GroundingDINO model on Replicate, gets bboxes back. Designed
specifically for "find all instances of [text description] in this image",
which is exactly our problem.

Cost: ~$0.005 per call on Replicate (varies by model; we use a public
checkpoint). Runtime: 2-5s per call.
"""

from __future__ import annotations
import os
import time
import base64
from io import BytesIO
from pathlib import Path

from PIL import Image
import replicate

from detector_bench.core.types import Detector, DetectionResult, BBox
from detector_bench.core.pdf_loader import render_page

# A widely-used GroundingDINO endpoint on Replicate. If this becomes unavailable,
# the model name needs swapping to a current alternative (any open-vocabulary
# detector with image+text input that returns bboxes works).
#
# Version ID correction (2026-05-02): the version pin from the plan
# (...921ed9e1f) was a typo and resolves to "Invalid version or not permitted".
# The actual current version of `adirik/grounding-dino` resolved live via
# `replicate.models.get(...).latest_version.id` ends in ...921ed78aa. Schema
# (image / query / box_threshold / text_threshold) is identical.
MODEL = "adirik/grounding-dino:efd10a8ddc57ea28773327e881ce95e20cc1d734c589f7dd01d2036921ed78aa"
COST_PER_CALL_USD = 0.005


class GroundingDinoDetector(Detector):
    name = "p5_grounding_dino"

    def __init__(self, threshold: float = 0.30) -> None:
        self.threshold = threshold

    def setup(self, pdf_path: Path) -> None:
        self._pdf_stem = Path(pdf_path).stem
        import json
        legend_json = Path(f"/Users/ignasgaldikas/samatu-ai/legends/{self._pdf_stem}.json")
        self._legend: dict[str, str] = {}
        if legend_json.exists():
            for it in json.loads(legend_json.read_text()):
                self._legend[it["symbol_code"]] = it.get("description_lt", "")

    def _prompt_for(self, symbol_code: str) -> str:
        # GroundingDINO works best with English noun phrases.
        # Map common LT codes → English descriptions.
        lt = self._legend.get(symbol_code, "")
        # Translate common LT terms to grounded English noun phrases
        if "rozet" in (lt + symbol_code).lower():
            return "electrical outlet . electrical socket . wall outlet"
        if "jungtuk" in (lt + symbol_code).lower() or "jungiklis" in (lt + symbol_code).lower():
            return "light switch . wall switch"
        if "lubinis" in lt.lower() or "luba" in lt.lower():
            return "ceiling light fixture . overhead luminaire"
        if "led" in (lt + symbol_code).lower():
            return "LED strip . linear LED light"
        if "ventilator" in (lt + symbol_code).lower():
            return "ventilation fan . exhaust fan"
        # Last resort: literal symbol code
        return f"{symbol_code} symbol"

    def detect(self, pdf_path: Path, page_nr: int, symbol_code: str) -> DetectionResult:
        t0 = time.time()
        if not os.environ.get("REPLICATE_API_TOKEN"):
            return DetectionResult(
                count=0, bboxes=[], runtime_s=0.0, cost_usd=0.0,
                errors=["REPLICATE_API_TOKEN not set"], notes="skipped",
            )
        try:
            arr = render_page(pdf_path, page_nr, dpi=200)
            img = Image.fromarray(arr)
            buf = BytesIO()
            img.save(buf, format="PNG")
            data_uri = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
            prompt = self._prompt_for(symbol_code)

            output = replicate.run(
                MODEL,
                input={
                    "image": data_uri,
                    "query": prompt,
                    "box_threshold": self.threshold,
                    "text_threshold": 0.20,
                },
            )
            # Output shape varies by model; common shape:
            # { "detections": [{"box": [x1,y1,x2,y2], "label": "...", "confidence": 0.5}, ...] }
            detections = []
            if isinstance(output, dict):
                detections = output.get("detections") or output.get("boxes") or []
            elif isinstance(output, list):
                detections = output
            h_p, w_p = arr.shape
            bboxes: list[BBox] = []
            for det in detections:
                box = det.get("box") if isinstance(det, dict) else det
                if not box or len(box) != 4:
                    continue
                x1, y1, x2, y2 = [float(v) for v in box]
                # Some endpoints return absolute pixels, others normalized.
                # Detect by max value; if any > 1.0 assume pixels.
                if max(x1, y1, x2, y2) > 1.0:
                    x1 /= w_p; x2 /= w_p; y1 /= h_p; y2 /= h_p
                if x2 <= x1 or y2 <= y1:
                    continue
                bboxes.append(BBox(
                    x_pct=max(0, min(1, x1)),
                    y_pct=max(0, min(1, y1)),
                    w_pct=max(0, min(1, x2 - x1)),
                    h_pct=max(0, min(1, y2 - y1)),
                ))
            return DetectionResult(
                count=len(bboxes), bboxes=bboxes,
                runtime_s=time.time() - t0, cost_usd=COST_PER_CALL_USD,
                errors=[], notes=f"prompt='{prompt}' raw_detections={len(detections)}",
            )
        except Exception as e:
            return DetectionResult(
                count=0, bboxes=[], runtime_s=time.time() - t0,
                cost_usd=COST_PER_CALL_USD, errors=[str(e)], notes="failed",
            )
