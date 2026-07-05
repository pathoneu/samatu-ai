"""Empirical test of door-arc detection on real project floor plans.

Goal: measure false-positive rate before committing the detector
into the production pipeline. If on real architectural drawings the
detector returns hundreds of "arcs" that aren't door swings, the
median-scale signal is noise.
"""

from __future__ import annotations

import base64
import io
import sys
from math import pi
from pathlib import Path

import cv2
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))


def detect_door_arcs(image_np: np.ndarray) -> list[dict]:
    gray = cv2.cvtColor(image_np, cv2.COLOR_RGB2GRAY) if len(image_np.shape) == 3 else image_np
    binary = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, 11, 2,
    )
    edges = cv2.Canny(binary, 50, 150)
    circles = cv2.HoughCircles(
        edges, cv2.HOUGH_GRADIENT, dp=1, minDist=20,
        param1=50, param2=15, minRadius=10, maxRadius=80,
    )
    results = []
    if circles is None:
        return results
    circles = np.uint16(np.around(circles))
    for x, y, r in circles[0]:
        mask = np.zeros_like(binary)
        cv2.circle(mask, (int(x), int(y)), int(r), 255, 1)
        overlap = cv2.bitwise_and(mask, edges)
        pixel_count = np.sum(overlap > 0)
        circumference_px = 2 * pi * float(r)
        if circumference_px <= 0:
            continue
        arc_fraction = pixel_count / circumference_px
        if 0.15 < arc_fraction < 0.45:
            results.append({
                "center_x": int(x), "center_y": int(y),
                "radius_px": int(r),
                "confidence": min(arc_fraction / 0.25, 1.0),
            })
    return results


def compute_scale_from_arcs(arcs: list[dict]) -> tuple[float | None, list[float]]:
    if not arcs:
        return None, []
    top = sorted(arcs, key=lambda a: a["confidence"], reverse=True)[:8]
    standard_widths_mm = [700, 800, 900, 1000]
    all_scales = []
    for arc in top:
        rpx = arc["radius_px"]
        if rpx <= 0:
            continue
        for w_mm in standard_widths_mm:
            scale = w_mm / rpx
            if 2.0 < scale < 80.0:
                all_scales.append(scale)
    if not all_scales:
        return None, []
    return float(np.median(all_scales)), all_scales


def page_to_np(pdf_path: Path, page_idx: int) -> np.ndarray | None:
    from extractor.vision_call import pdf_to_b64_images
    pages = pdf_to_b64_images(pdf_path.read_bytes())
    by_idx = {p["page_index"]: p["image_b64"] for p in pages}
    if page_idx not in by_idx:
        return None
    img_bytes = base64.b64decode(by_idx[page_idx])
    arr = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB) if img is not None else None


def main() -> int:
    projects = [
        ("berzas", "docs/superpowers/fixtures/2026-05-26-berzu-g-24/project.pdf", 2),
        ("objektas_b", "docs/superpowers/fixtures/2026-06-01-batch-5/Nr. 1/TP_Objektas B_2025naujausias.pdf", 1),
        ("ciurliu", "docs/superpowers/fixtures/2026-06-01-batch-5/Nr. 2/Techninio projekto planai_20250501 (a3)_2.pdf", 1),
        ("lazunu", "docs/superpowers/fixtures/2026-06-01-batch-5/Nr. 5/Apmatavimai-Layout4.pdf", 1),
    ]
    print(f"\n{'project':<14} {'page':<5} {'arcs':>5} {'scale (median)':>15} {'sane scales':>15}")
    print("─" * 60)
    for slug, pdf_path, page_idx in projects:
        full_path = REPO_ROOT / pdf_path
        if not full_path.exists():
            print(f"  {slug}: PDF not found")
            continue
        img = page_to_np(full_path, page_idx)
        if img is None:
            print(f"  {slug}: could not render page")
            continue
        arcs = detect_door_arcs(img)
        scale, all_scales = compute_scale_from_arcs(arcs)
        n_sane = len(all_scales)
        scale_s = f"{scale:.2f}" if scale else "—"
        print(f"  {slug:<14} {page_idx:<5} {len(arcs):>5} {scale_s:>15} {n_sane:>15}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
