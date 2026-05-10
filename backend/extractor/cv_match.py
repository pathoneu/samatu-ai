"""Multi-scale, multi-rotation template matching with NMS dedup.

Single entrypoint: `find_similar_symbols(page, template, threshold,
scales, rotations) -> list[dict]`. Each result dict carries
{x, y, bbox, confidence, scale, rotation} so the frontend can render
markers AND reuse the bbox for the training-data writer.
"""
from __future__ import annotations

import cv2
import numpy as np

DEFAULT_SCALES = (0.85, 0.95, 1.0, 1.05, 1.15)
DEFAULT_ROTATIONS = (0, 90, 180, 270)


def _rotate(template: np.ndarray, deg: int) -> np.ndarray:
    if deg == 0:
        return template
    if deg == 90:
        return cv2.rotate(template, cv2.ROTATE_90_CLOCKWISE)
    if deg == 180:
        return cv2.rotate(template, cv2.ROTATE_180)
    if deg == 270:
        return cv2.rotate(template, cv2.ROTATE_90_COUNTERCLOCKWISE)
    raise ValueError(f"Unsupported rotation {deg}")


def _nms(candidates: list[dict], iou_threshold: float = 0.3) -> list[dict]:
    if not candidates:
        return []
    candidates = sorted(candidates, key=lambda c: -c["confidence"])
    kept: list[dict] = []
    for cand in candidates:
        ax1, ay1, aw, ah = cand["bbox"]
        ax2, ay2 = ax1 + aw, ay1 + ah
        suppressed = False
        for k in kept:
            bx1, by1, bw, bh = k["bbox"]
            bx2, by2 = bx1 + bw, by1 + bh
            ix = max(0, min(ax2, bx2) - max(ax1, bx1))
            iy = max(0, min(ay2, by2) - max(ay1, by1))
            inter = ix * iy
            union = aw * ah + bw * bh - inter
            iou = inter / union if union else 0
            if iou > iou_threshold:
                suppressed = True
                break
        if not suppressed:
            kept.append(cand)
    return kept


def find_similar_symbols(
    page: np.ndarray,
    template: np.ndarray,
    threshold: float = 0.80,
    scales: tuple[float, ...] = DEFAULT_SCALES,
    rotations: tuple[int, ...] = DEFAULT_ROTATIONS,
) -> list[dict]:
    """Return every page region matching `template` above `threshold`."""
    candidates: list[dict] = []
    for scale in scales:
        if scale != 1.0:
            new_w = max(8, int(template.shape[1] * scale))
            new_h = max(8, int(template.shape[0] * scale))
            scaled = cv2.resize(
                template, (new_w, new_h), interpolation=cv2.INTER_AREA,
            )
        else:
            scaled = template
        for deg in rotations:
            rotated = _rotate(scaled, deg)
            if (rotated.shape[0] >= page.shape[0]
                    or rotated.shape[1] >= page.shape[1]):
                continue
            result = cv2.matchTemplate(page, rotated, cv2.TM_CCOEFF_NORMED)
            ys, xs = np.where(result >= threshold)
            for x, y in zip(xs, ys):
                candidates.append({
                    "x": int(x + rotated.shape[1] // 2),
                    "y": int(y + rotated.shape[0] // 2),
                    "bbox": (
                        int(x), int(y), rotated.shape[1], rotated.shape[0],
                    ),
                    "confidence": float(result[y, x]),
                    "scale": float(scale),
                    "rotation": int(deg),
                })
    return _nms(candidates)
