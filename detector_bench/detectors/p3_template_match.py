"""Pipeline 3 — cv2.matchTemplate from auto-extracted legend glyphs.

For each (page, symbol_code):
  1. Load template at legends/<pdf_stem>/<symbol_code>.png (cropped legend glyph)
  2. Render the page at the same DPI (200)
  3. Multi-scale, multi-rotation template match
  4. Non-maximum suppression on matches above threshold
  5. Return count + bboxes
"""

from __future__ import annotations
import time
from pathlib import Path

import numpy as np
import cv2

from detector_bench.core.types import Detector, DetectionResult, BBox
from detector_bench.core.pdf_loader import render_page

# Tuneable — affects precision/recall heavily.
DEFAULT_THRESHOLD = 0.75
SCALES = [0.85, 1.0, 1.15]              # tolerance for scale variation
ROTATIONS = [0, 90, 180, 270]           # symbols often rotated 90° on plumbing/HVAC
NMS_IOU_THRESHOLD = 0.3                 # suppress overlapping detections


def _rotate(img: np.ndarray, angle: int) -> np.ndarray:
    if angle == 0:
        return img
    if angle == 90:
        return np.rot90(img, k=1)
    if angle == 180:
        return np.rot90(img, k=2)
    if angle == 270:
        return np.rot90(img, k=3)
    raise ValueError(f"unsupported rotation: {angle}")


def _nms(boxes: list[tuple[int, int, int, int, float]], iou_thresh: float) -> list[tuple[int, int, int, int, float]]:
    """Non-max suppression. Boxes: list of (x, y, w, h, score)."""
    if not boxes:
        return []
    boxes_np = np.array([[b[0], b[1], b[0] + b[2], b[1] + b[3]] for b in boxes], dtype=np.float32)
    scores = np.array([b[4] for b in boxes])
    keep = []
    idxs = np.argsort(-scores)
    while len(idxs) > 0:
        i = idxs[0]
        keep.append(i)
        if len(idxs) == 1:
            break
        rest = idxs[1:]
        xx1 = np.maximum(boxes_np[i, 0], boxes_np[rest, 0])
        yy1 = np.maximum(boxes_np[i, 1], boxes_np[rest, 1])
        xx2 = np.minimum(boxes_np[i, 2], boxes_np[rest, 2])
        yy2 = np.minimum(boxes_np[i, 3], boxes_np[rest, 3])
        w = np.maximum(0, xx2 - xx1)
        h = np.maximum(0, yy2 - yy1)
        inter = w * h
        a_i = (boxes_np[i, 2] - boxes_np[i, 0]) * (boxes_np[i, 3] - boxes_np[i, 1])
        a_rest = (boxes_np[rest, 2] - boxes_np[rest, 0]) * (boxes_np[rest, 3] - boxes_np[rest, 1])
        iou = inter / (a_i + a_rest - inter + 1e-6)
        idxs = rest[iou < iou_thresh]
    return [boxes[k] for k in keep]


class TemplateMatchDetector(Detector):
    name = "p3_template_match"

    def __init__(self, threshold: float = DEFAULT_THRESHOLD) -> None:
        self.threshold = threshold

    def setup(self, pdf_path: Path) -> None:
        self._pdf_stem = Path(pdf_path).stem

    def detect(self, pdf_path: Path, page_nr: int, symbol_code: str) -> DetectionResult:
        t0 = time.time()
        # Sanitize symbol_code → filename (must match crop_glyph_templates)
        safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in symbol_code)
        template_path = Path(f"/Users/ignasgaldikas/samatu-ai/legends/{self._pdf_stem}/{safe}.png")
        if not template_path.exists():
            return DetectionResult(
                count=0, bboxes=[], runtime_s=time.time() - t0,
                cost_usd=0.0, errors=[f"template not found: {template_path}"],
                notes="missing template",
            )

        page = render_page(pdf_path, page_nr, dpi=200)
        template = cv2.imread(str(template_path), cv2.IMREAD_GRAYSCALE)
        if template is None or template.size == 0:
            return DetectionResult(
                count=0, bboxes=[], runtime_s=time.time() - t0,
                cost_usd=0.0, errors=["template empty"], notes="bad template",
            )

        h_p, w_p = page.shape
        all_matches: list[tuple[int, int, int, int, float]] = []
        for scale in SCALES:
            for angle in ROTATIONS:
                rot = _rotate(template, angle)
                t_h = max(8, int(rot.shape[0] * scale))
                t_w = max(8, int(rot.shape[1] * scale))
                if t_h >= h_p or t_w >= w_p:
                    continue
                resized = cv2.resize(rot, (t_w, t_h), interpolation=cv2.INTER_AREA)
                res = cv2.matchTemplate(page, resized, cv2.TM_CCOEFF_NORMED)
                ys, xs = np.where(res >= self.threshold)
                for x, y in zip(xs, ys):
                    score = float(res[y, x])
                    all_matches.append((int(x), int(y), t_w, t_h, score))

        kept = _nms(all_matches, NMS_IOU_THRESHOLD)
        bboxes = [
            BBox(
                x_pct=b[0] / w_p, y_pct=b[1] / h_p,
                w_pct=b[2] / w_p, h_pct=b[3] / h_p,
            )
            for b in kept
        ]
        return DetectionResult(
            count=len(kept), bboxes=bboxes,
            runtime_s=time.time() - t0, cost_usd=0.0, errors=[],
            notes=f"threshold={self.threshold} scales={SCALES} rots={ROTATIONS} raw={len(all_matches)} nms={len(kept)}",
        )
