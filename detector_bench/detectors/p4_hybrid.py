"""Pipeline 4 — Hybrid: text positions as anchors, template match as confirmer.

For each text occurrence of a keyword (e.g. "Rozetė") on the page:
  1. Get its bbox from pdfplumber
  2. Crop a small neighborhood around it (extend by ~150 px)
  3. Run template match within that neighborhood
  4. If template matches → count this anchor as a confirmed symbol

This catches symbols that have both a label AND a glyph, with high precision.
Symbols with NO text label fall back to template-match-on-whole-page.
"""

from __future__ import annotations
import time
import re
from pathlib import Path

import numpy as np
import cv2
import pdfplumber

from detector_bench.core.types import Detector, DetectionResult, BBox
from detector_bench.core.pdf_loader import render_page, get_page_dims_pdf
from detector_bench.detectors.p2_text_driven import _keywords_for
from detector_bench.detectors.p3_template_match import (
    TemplateMatchDetector, SCALES, ROTATIONS, _rotate, _nms,
)

NEIGHBORHOOD_PX = 200          # search radius around each text anchor


class HybridDetector(Detector):
    name = "p4_hybrid"

    def __init__(self, threshold: float = 0.65) -> None:
        # Lower threshold than pure template — text confirms presence,
        # template just confirms type.
        self.threshold = threshold

    def setup(self, pdf_path: Path) -> None:
        self._pdf_stem = Path(pdf_path).stem
        import json
        legend_json = Path(f"/Users/ignasgaldikas/samatu-ai/legends/{self._pdf_stem}.json")
        self._legend: dict[str, str] = {}
        if legend_json.exists():
            for it in json.loads(legend_json.read_text()):
                self._legend[it["symbol_code"]] = it.get("description_lt", "")

    def detect(self, pdf_path: Path, page_nr: int, symbol_code: str) -> DetectionResult:
        t0 = time.time()
        keywords = _keywords_for(symbol_code, self._legend.get(symbol_code))
        safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in symbol_code)
        template_path = Path(f"/Users/ignasgaldikas/samatu-ai/legends/{self._pdf_stem}/{safe}.png")
        page_arr = render_page(pdf_path, page_nr, dpi=200)
        h_p, w_p = page_arr.shape

        try:
            pdf_w_pt, pdf_h_pt = get_page_dims_pdf(pdf_path, page_nr)
        except Exception as e:
            return DetectionResult(
                count=0, bboxes=[], runtime_s=time.time() - t0,
                cost_usd=0.0, errors=[f"page dims: {e}"], notes="failed",
            )
        # Convert PDF points → pixels at 200 DPI
        pt_to_px_x = w_p / pdf_w_pt
        pt_to_px_y = h_p / pdf_h_pt

        # Step 1: text anchors via pdfplumber
        anchors: list[tuple[int, int]] = []  # (x_px, y_px) of each text occurrence
        try:
            with pdfplumber.open(str(pdf_path)) as pdf:
                page = pdf.pages[page_nr - 1]
                words = page.extract_words(extra_attrs=["x0", "x1", "top", "bottom"])
                for w in words:
                    txt = (w.get("text") or "").lower()
                    for kw in keywords:
                        if re.search(kw, txt, re.IGNORECASE):
                            cx = (w["x0"] + w["x1"]) / 2
                            cy = (w["top"] + w["bottom"]) / 2
                            anchors.append((int(cx * pt_to_px_x), int(cy * pt_to_px_y)))
                            break
        except Exception as e:
            return DetectionResult(
                count=0, bboxes=[], runtime_s=time.time() - t0,
                cost_usd=0.0, errors=[f"pdfplumber: {e}"], notes="failed",
            )

        # Step 2: if template exists, confirm each anchor
        confirmed_bboxes: list[BBox] = []
        if template_path.exists() and anchors:
            template = cv2.imread(str(template_path), cv2.IMREAD_GRAYSCALE)
            if template is not None and template.size > 0:
                for (ax, ay) in anchors:
                    x0 = max(0, ax - NEIGHBORHOOD_PX)
                    x1 = min(w_p, ax + NEIGHBORHOOD_PX)
                    y0 = max(0, ay - NEIGHBORHOOD_PX)
                    y1 = min(h_p, ay + NEIGHBORHOOD_PX)
                    nbh = page_arr[y0:y1, x0:x1]
                    if nbh.size == 0:
                        continue
                    found = False
                    for scale in SCALES:
                        for angle in ROTATIONS:
                            rot = _rotate(template, angle)
                            t_h = max(8, int(rot.shape[0] * scale))
                            t_w = max(8, int(rot.shape[1] * scale))
                            if t_h >= nbh.shape[0] or t_w >= nbh.shape[1]:
                                continue
                            resized = cv2.resize(rot, (t_w, t_h), interpolation=cv2.INTER_AREA)
                            res = cv2.matchTemplate(nbh, resized, cv2.TM_CCOEFF_NORMED)
                            if res.max() >= self.threshold:
                                ys, xs = np.where(res == res.max())
                                yy, xx = int(ys[0]), int(xs[0])
                                bx = (x0 + xx) / w_p
                                by = (y0 + yy) / h_p
                                bw = t_w / w_p
                                bh = t_h / h_p
                                confirmed_bboxes.append(BBox(bx, by, bw, bh))
                                found = True
                                break
                        if found:
                            break

                # Fallback if no anchors confirmed: full-page template match
                if not confirmed_bboxes:
                    fallback = TemplateMatchDetector(threshold=self.threshold + 0.10)
                    fallback.setup(pdf_path)
                    return fallback.detect(pdf_path, page_nr, symbol_code)

                return DetectionResult(
                    count=len(confirmed_bboxes), bboxes=confirmed_bboxes,
                    runtime_s=time.time() - t0, cost_usd=0.0, errors=[],
                    notes=f"text anchors={len(anchors)} confirmed={len(confirmed_bboxes)}",
                )

        # No template: use text count alone
        return DetectionResult(
            count=len(anchors), bboxes=[],
            runtime_s=time.time() - t0, cost_usd=0.0, errors=[],
            notes=f"text-only (no template): anchors={len(anchors)}",
        )
