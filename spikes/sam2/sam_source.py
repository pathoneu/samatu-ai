"""SAM 2.1 room masks, local (Ultralytics) — the seed of backend/geometry/sam_source.py (plan 2026-10-24 §3.1).

Deterministic plumbing around one model call:
  render_page(pdf, page, dpi)            -> (BGR image, PageFrame)      PDFium, display space (/Rotate applied)
  load_model(weights, device)            -> SamModel                    loaded once per process
  SamModel.set_image(img)                                               image encoder (the expensive part)
  SamModel.segment(points, neg_points, box, multimask) -> [(mask, score)]   prompt decoder (cheap)
  wall_mask(img, min_wall_px)            -> bool mask of thick dark strokes (walls), thin lines removed
  negative_points_on_walls(walls, pt, n) -> nearest wall pixels around a click, for prompt variant B
  largest_component(mask, seed)          -> the connected component under the click (or the largest)
  mask_to_polygon(mask, frame, eps_m, m_per_pt, offset_px) -> GeoJSON Polygon in PDF points (display space)
  polygon_metrics(geojson, m_per_pt)     -> {area_m2, perimeter_m}

Coordinates: pixels of the full-page raster at `dpi`; PDF points = px * 72 / dpi, display orientation
(same frame as the app's `*_pct` fractions times the displayed page size). No number comes from the model
other than the binary mask; area and perimeter are shapely on the polygon.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import cv2
import numpy as np
from shapely.geometry import Polygon, mapping, shape


@dataclass(frozen=True)
class PageFrame:
    """Pixel <-> PDF-point matrix of one rendered page (display space)."""
    dpi: float
    width_pt: float
    height_pt: float
    width_px: int
    height_px: int

    @property
    def px_per_pt(self) -> float:
        return self.dpi / 72.0

    def px_to_pt(self, x: float, y: float) -> tuple[float, float]:
        k = 72.0 / self.dpi
        return x * k, y * k

    def pt_to_px(self, x: float, y: float) -> tuple[float, float]:
        k = self.dpi / 72.0
        return x * k, y * k

    def pct_to_px(self, x_pct: float, y_pct: float) -> tuple[float, float]:
        return x_pct * self.width_px, y_pct * self.height_px


def render_page(pdf_path: str | Path, page: int, dpi: float = 300) -> tuple[np.ndarray, PageFrame]:
    """1-based `page` -> BGR uint8 image in display orientation (PDFium applies /Rotate)."""
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(str(pdf_path))
    try:
        pg = doc[page - 1]
        bitmap = pg.render(scale=dpi / 72.0, rotation=0, may_draw_forms=False)
        rgb = np.asarray(bitmap.to_pil().convert("RGB"))
        h, w = rgb.shape[:2]
        # displayed size in points, taken from the bitmap PDFium drew (it already applied /Rotate)
        wpt, hpt = w * 72.0 / dpi, h * 72.0 / dpi
    finally:
        doc.close()
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR), PageFrame(dpi, float(wpt), float(hpt), w, h)


class SamModel:
    """One SAM 2.1 predictor, loaded once; `set_image` encodes, `segment` decodes prompts."""

    def __init__(self, weights: str | Path, device: str | None = None, imgsz: int = 1024):
        import torch
        from ultralytics.models.sam import SAM2Predictor

        if device is None:
            device = "mps" if torch.backends.mps.is_available() else "cpu"
        self.device = device
        self.weights = str(weights)
        self.imgsz = imgsz
        self._p = SAM2Predictor(overrides=dict(model=self.weights, conf=0.0, imgsz=imgsz, device=device,
                                               task="segment", mode="predict", save=False, verbose=False))
        self._shape: tuple[int, int] | None = None
        self.last_encode_ms = 0.0

    def set_image(self, img_bgr: np.ndarray) -> float:
        t = time.perf_counter()
        self._p.set_image(img_bgr)
        self._sync()
        self._shape = img_bgr.shape[:2]
        self.last_encode_ms = (time.perf_counter() - t) * 1000
        return self.last_encode_ms

    def _sync(self) -> None:
        """MPS/CUDA run asynchronously: without a sync the encode time lands on the next decode."""
        import torch
        if self.device == "mps":
            torch.mps.synchronize()
        elif str(self.device).startswith("cuda"):
            torch.cuda.synchronize()

    def segment(self, points: Sequence[Sequence[float]] = (), neg_points: Sequence[Sequence[float]] = (),
                box: Sequence[float] | None = None, multimask: bool = False) -> list[tuple[np.ndarray, float]]:
        """Pixel prompts in the image last passed to `set_image` -> [(bool mask HxW, predicted IoU)].
        One object: all points belong to it (label 1 positive, 0 negative)."""
        assert self._shape is not None, "set_image first"
        pts = [list(map(float, p)) for p in points] + [list(map(float, p)) for p in neg_points]
        labels = [1] * len(points) + [0] * len(neg_points)
        kw: dict = {"multimask_output": multimask}
        if pts:
            kw["points"] = [pts]
            kw["labels"] = [labels]
        if box is not None:
            kw["bboxes"] = [list(map(float, box))]
        res = self._p(**kw)[0]
        if res.masks is None:
            return []
        masks = res.masks.data.cpu().numpy().astype(bool)
        scores = res.boxes.conf.cpu().numpy().tolist() if res.boxes is not None else [0.0] * len(masks)
        return list(zip(masks, scores))


def load_model(weights: str | Path, device: str | None = None, imgsz: int = 1024) -> SamModel:
    return SamModel(weights, device, imgsz)


def wall_mask(img_bgr: np.ndarray, min_wall_px: int) -> np.ndarray:
    """Thick dark strokes: dark pixels, hatching closed, then opened by a square of `min_wall_px` so that
    text, dimension lines and furniture outlines (1–3 px) disappear and walls stay."""
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    dark = (gray < 240).astype(np.uint8)      # < 240: light-grey wall fills (objektas_g 170, objektas_h 191/232) count
    k = max(3, int(min_wall_px))
    closed = cv2.morphologyEx(dark, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    opened = cv2.morphologyEx(closed, cv2.MORPH_OPEN, np.ones((k, k), np.uint8))
    # drop blobs smaller than ~ (4k)²: filled symbols, text clumps, diffuser dots
    n, lab, stats, _ = cv2.connectedComponentsWithStats(opened, connectivity=8)
    keep = np.zeros(n, bool)
    keep[1:] = stats[1:, cv2.CC_STAT_AREA] >= (4 * k) ** 2
    return keep[lab]


def walls_only_image(walls: np.ndarray) -> np.ndarray:
    """Black walls on white, 3 channels — the drawing with furniture, text, hatching and dimensions removed."""
    im = np.full(walls.shape + (3,), 255, np.uint8)
    im[walls] = 0
    return im


def flood_fill_room(walls: np.ndarray, pt: Sequence[float]) -> np.ndarray:
    """No model: the free space connected to the click in the walls-only mask (opens through door gaps)."""
    free = (~walls).astype(np.uint8)
    h, w = free.shape
    m = np.zeros((h + 2, w + 2), np.uint8)
    x, y = int(round(pt[0])), int(round(pt[1]))
    if not free[y, x]:
        return np.zeros_like(walls)
    cv2.floodFill(free, m, (x, y), 2)
    return free == 2


def clear_floor_point(img_bgr: np.ndarray, walls: np.ndarray, pt: Sequence[float], clear_px: float,
                      radius_px: float) -> tuple[tuple[float, float], str]:
    """The printed room number is ink: a click ON it makes SAM segment the glyph (measured: 0.03 m² masks).
    Move the click to the nearest pixel at least `clear_px` from any ink, within `radius_px`, with no wall
    pixel on the straight line from the original click. Falls back to the clearest pixel in the radius."""
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    free = (gray >= 200).astype(np.uint8)
    dist = cv2.distanceTransform(free, cv2.DIST_L2, 5)
    h, w = gray.shape
    x0, y0 = float(pt[0]), float(pt[1])
    r = int(radius_px)
    ys, xs = np.mgrid[max(0, int(y0) - r):min(h, int(y0) + r + 1), max(0, int(x0) - r):min(w, int(x0) + r + 1)]
    d2 = (xs - x0) ** 2 + (ys - y0) ** 2
    inside = d2 <= r * r
    dd = dist[ys, xs]

    def sight(x, y):
        n = int(max(abs(x - x0), abs(y - y0))) + 1
        lx = np.linspace(x0, x, n).round().astype(int).clip(0, w - 1)
        ly = np.linspace(y0, y, n).round().astype(int).clip(0, h - 1)
        return not walls[ly, lx].any()

    ok = inside & (dd >= clear_px)
    if ok.any():
        order = np.argsort(d2[ok])
        cx, cy = xs[ok][order], ys[ok][order]
        for i in range(0, min(len(cx), 4000), 20):
            if sight(cx[i], cy[i]):
                return (float(cx[i]), float(cy[i])), "clear"
    best = np.argmax(np.where(inside, dd, -1))
    return (float(xs.flat[best]), float(ys.flat[best])), "clearest"


def negative_points_on_walls(walls: np.ndarray, pt: Sequence[float], n: int = 4, max_px: int | None = None,
                             inset_px: int = 3) -> list[tuple[float, float]]:
    """Cast 8 rays from the click; the first wall pixel on each (pushed `inset_px` into the wall) is a
    candidate; keep the `n` nearest. These are prompt variant B's negative points."""
    h, w = walls.shape
    x0, y0 = float(pt[0]), float(pt[1])
    max_px = max_px or max(h, w)
    hits: list[tuple[float, float, float]] = []
    for ang in np.arange(0, 360, 45):
        dx, dy = np.cos(np.radians(ang)), np.sin(np.radians(ang))
        for r in range(2, max_px):
            x, y = int(round(x0 + dx * r)), int(round(y0 + dy * r))
            if not (0 <= x < w and 0 <= y < h):
                break
            if walls[y, x]:
                xi, yi = x0 + dx * (r + inset_px), y0 + dy * (r + inset_px)
                if 0 <= xi < w and 0 <= yi < h:
                    hits.append((r, xi, yi))
                break
    hits.sort()
    return [(x, y) for _, x, y in hits[:n]]


def largest_component(mask: np.ndarray, seed: Sequence[float] | None = None) -> np.ndarray:
    """The 8-connected component containing `seed` when it is in the mask, else the largest one."""
    m = mask.astype(np.uint8)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
    if n <= 1:
        return mask.astype(bool)
    if seed is not None:
        sx, sy = int(round(seed[0])), int(round(seed[1]))
        if 0 <= sy < lab.shape[0] and 0 <= sx < lab.shape[1] and lab[sy, sx] > 0:
            return lab == lab[sy, sx]
    best = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    return lab == best


def mask_to_polygon(mask: np.ndarray, frame: PageFrame, eps_m: float, m_per_pt: float,
                    offset_px: tuple[float, float] = (0.0, 0.0), min_hole_m2: float = 0.05) -> dict | None:
    """Binary mask (pixels of a crop at `offset_px` in the page raster) -> GeoJSON Polygon in PDF points.
    cv2.findContours RETR_CCOMP keeps holes; approxPolyDP with ε = `eps_m` metres on the page."""
    m = mask.astype(np.uint8)
    contours, hier = cv2.findContours(m, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    if not contours or hier is None:
        return None
    eps_px = eps_m / m_per_pt * frame.px_per_pt
    hier = hier[0]
    outers = [i for i in range(len(contours)) if hier[i][3] < 0]
    if not outers:
        return None
    outer = max(outers, key=lambda i: cv2.contourArea(contours[i]))
    ox, oy = offset_px

    def ring(c):
        a = cv2.approxPolyDP(c, eps_px, True).reshape(-1, 2).astype(float)
        if len(a) < 3:
            return None
        return [frame.px_to_pt(x + ox, y + oy) for x, y in a]

    shell = ring(contours[outer])
    if shell is None:
        return None
    holes = []
    child = hier[outer][2]
    while child >= 0:
        r = ring(contours[child])
        if r is not None and Polygon(r).area * m_per_pt ** 2 >= min_hole_m2:
            holes.append(r)
        child = hier[child][0]
    poly = Polygon(shell, holes)
    if not poly.is_valid:
        poly = poly.buffer(0)
        if poly.geom_type == "MultiPolygon":
            poly = max(poly.geoms, key=lambda g: g.area)
    return mapping(poly)


def polygon_metrics(geojson: dict, m_per_pt: float) -> dict:
    p = shape(geojson)
    return {"area_m2": round(p.area * m_per_pt ** 2, 3), "perimeter_m": round(p.exterior.length * m_per_pt, 3)}
