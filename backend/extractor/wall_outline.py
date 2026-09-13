"""Room outlines traced from the drawing's WALL geometry.

The founder's review note, 2026-09-13: the room frame on the check sheet —
Vision's `bbox_pct` — sits a wall thickness off, and a frame that is off makes
every number on the sheet look unread. Research the same day
(docs/superpowers/research/2026-09-13-room-geometry-precision.md): nobody gets
1–2 % room geometry from a learned model or a vision LLM; the systems that do
read the wall vectors, or flood-fill a CLEAN raster and check the result. On
objektas_g the old raster flood-fill solved 0 of 9 rooms (interior dimension
lines and furniture cut the rooms, grey wall fills vanish under an adaptive
threshold); this lane solved 7 of 9 within ±5 % of the printed area, and its
perimeters agreed with the dimension strings within 1 % wherever both exist.

How: render the page WITHOUT text and without stroke-only hairlines (dimension
lines, furniture, symbols) — what is left is the walls, filled or hatched;
bridge door gaps along the wall direction and window gaps in THICK walls only
(a 1-D closing, so a narrow corridor between two parallel walls is not
swallowed); flood-fill from the room's own area label; keep the fill only when
its area matches the printed m² (±AREA_TOL) and exactly one room label lies
inside it (an open plan that swallows the next room fails that test). Door
widths are swept and the best fit per room wins — one kernel does not fit
every drawing. A room the walls do not close stays as it was, and says so.

What the lane writes: `polygon_pct` (display-frame fractions, `[[x, y], …]`)
with `polygon_source = "sienu_konturas"`, `_konturas` {page, plotas_m2,
perimetras_m, plotas_uzrasas_m2, paklaida, durys_m, dpi}; and, when nobody
STATED the perimeter (plan dimensions, table, user), `perimetras_m` becomes the
outline's with `perimetras_saltinis = "sienu_konturas"` and the read figure kept
as `_perimetras_pries_kontura`. Areas are never touched — the printed label is
the area, the outline is checked against it.
"""

from __future__ import annotations

import ctypes
import math
from typing import Any, Sequence

import numpy as np

from .plan_area_annotations import _f, _rel
from .plan_dimensions import _PT_M, _label_position, frame_groups

DPI = 200
WALL_GREY = 245            # darker than this on the walls-only render = wall (fills are grey)
HAIRLINE_PT = 1.0          # stroke-only paths thinner than this are dimension lines, furniture, symbols
THICK_WALL_MM = 3.5        # paper mm — a band at least this thick is an exterior / bearing wall
RUN_M = 0.3                # a wall band is at least this long in its own direction; shorter ink is a stub or a symbol
DOOR_M = (0.95, 0.80, 1.10)   # gap widths bridged along any wall, tried in this order
WINDOW_M = 3.2             # gap widths bridged in thick walls only
SEED_MM = ((0, 0), (-2.5, 0), (2.5, 0), (0, -2.5), (0, 2.5), (-5, -5), (5, 5), (-5, 5), (5, -5), (-9, 0), (9, 0), (0, -9), (0, 9))
AREA_TOL = 0.05            # the fill's area against the printed m²
CONFIRM_TOL = 0.02         # the read perimeter already agreed with the outline
MIN_ROOM_M2 = 0.5
SIMPLIFY_PCT = 0.4         # Douglas–Peucker tolerance, % of the contour's bounding diagonal
SOURCE = "sienu_konturas"
_STATED_PERIMETERS = ("plano_matmenys", "eksplikacija", "user_override", "manual")
_KEPT_POLYGONS = ("corrected", "manual")


# ── the walls-only raster ────────────────────────────────────────────────────

def render_walls_only(pdf_bytes: bytes, page_nr: int, dpi: int = DPI) -> np.ndarray | None:
    """Grayscale raster of one page (1-based) in the DISPLAY frame, with text
    objects and stroke-only hairlines removed — walls, filled or hatched,
    stay. None when pypdfium2 or the page is unavailable."""
    try:
        import pypdfium2 as pdfium
        import pypdfium2.raw as C
    except Exception:  # noqa: BLE001
        return None
    doc = pdfium.PdfDocument(pdf_bytes)
    if page_nr < 1 or page_nr > len(doc):
        return None
    page = doc[page_nr - 1]
    # No explicit close: the object wrappers created below are finalised by
    # Python in reverse order of creation, after which the page and the
    # document go — closing the page first makes every wrapper's finaliser
    # assert at interpreter exit (pypdfium2 5.x).
    objs = list(page.get_objects(max_depth=1))
    for obj in objs:
        if obj.type == C.FPDF_PAGEOBJ_TEXT:
            page.remove_obj(obj)
            continue
        if obj.type == C.FPDF_PAGEOBJ_PATH:
            sw = ctypes.c_float()
            C.FPDFPageObj_GetStrokeWidth(obj, ctypes.byref(sw))
            fill = ctypes.c_int()
            stroke = ctypes.c_int()
            C.FPDFPath_GetDrawMode(obj, ctypes.byref(fill), ctypes.byref(stroke))
            if not fill.value and stroke.value and sw.value < HAIRLINE_PT:
                page.remove_obj(obj)
    page.gen_content()
    img = page.render(scale=dpi / 72).to_pil().convert("L")
    raster = np.array(img)
    del objs, page, doc
    return raster


def wall_mask(raster: np.ndarray) -> np.ndarray:
    """255 where the walls-only render has ink, 0 elsewhere."""
    return (raster < WALL_GREY).astype(np.uint8) * 255


def _kernel(w: int, h: int):
    import cv2
    return cv2.getStructuringElement(cv2.MORPH_RECT, (max(1, int(w)), max(1, int(h))))


def thick_walls(wall: np.ndarray, thick_px: int) -> np.ndarray:
    """Only the bands at least `thick_px` wide — the exterior and bearing walls."""
    import cv2
    return cv2.morphologyEx(wall, cv2.MORPH_OPEN, _kernel(thick_px, thick_px))


def _oriented(mask: np.ndarray, run_px: int) -> tuple[np.ndarray, np.ndarray]:
    """The horizontal and the vertical wall bands of a mask — what survives an
    opening with a long thin kernel in ONE direction only. A band thicker than
    `run_px` survives both openings and is neither: it must not be bridged
    along a direction it does not have (a 0,30 m exterior wall read as a
    vertical band let the window closing span from it to the wall opposite
    and swallow a 3 m room — the 2026-09-13 synthetic test). A gap is then
    bridged only along a band's own direction, between its two ends."""
    import cv2
    h = cv2.morphologyEx(mask, cv2.MORPH_OPEN, _kernel(run_px, 1))
    v = cv2.morphologyEx(mask, cv2.MORPH_OPEN, _kernel(1, run_px))
    both = cv2.bitwise_and(h, v)
    return cv2.bitwise_and(h, cv2.bitwise_not(both)), cv2.bitwise_and(v, cv2.bitwise_not(both))


def _bridge_doors(wall: np.ndarray, band: np.ndarray, kernel) -> np.ndarray:
    """Gap pixels a 1-D closing of the whole mask adds, kept only where they
    continue a band of that direction — so a door beside a corner (band on
    one side, the perpendicular wall on the other) is bridged, while the
    closing's other product, a phantom fill from one wall to the parallel
    wall opposite, is not (it continues no band)."""
    import cv2
    added = cv2.bitwise_and(cv2.morphologyEx(wall, cv2.MORPH_CLOSE, kernel), cv2.bitwise_not(wall))
    # the closing bridges a gap up to the kernel's length, so the band must be
    # extended by that much on each side — a dilation reaches only half a kernel
    kw, kh = kernel.shape[1], kernel.shape[0]
    reach = _kernel(2 * kw - 1, 1) if kw > kh else _kernel(1, 2 * kh - 1)
    return cv2.bitwise_and(added, cv2.dilate(band, reach))


def free_space(wall: np.ndarray, thick: np.ndarray, door_px: int, window_px: int, run_px: int,
               thick_px: int = 1) -> np.ndarray:
    """255 = room interior, 0 = wall — after bridging door gaps in partitions
    (a gap continuing a band, whatever closes its far side) and window / door
    gaps in thick walls (a gap BETWEEN two segments of one thick band), each
    along the band's own direction. Thick bands are oriented with a run of
    three thicknesses, so a 0,4 m wall is never taken for a vertical one."""
    import cv2
    wall_h, wall_v = _oriented(wall, run_px)
    thick_h, thick_v = _oriented(thick, max(run_px, 3 * thick_px + 1))
    doors = cv2.bitwise_or(_bridge_doors(wall, wall_h, _kernel(door_px, 1)),
                           _bridge_doors(wall, wall_v, _kernel(1, door_px)))
    windows = cv2.bitwise_or(cv2.morphologyEx(thick_h, cv2.MORPH_CLOSE, _kernel(window_px, 1)),
                             cv2.morphologyEx(thick_v, cv2.MORPH_CLOSE, _kernel(1, window_px)))
    return (255 - cv2.bitwise_or(wall, cv2.bitwise_or(doors, windows))).astype(np.uint8)


def _fill(free: np.ndarray, x: int, y: int) -> np.ndarray | None:
    """0/1 mask of the free region containing (x, y); None on a wall pixel."""
    import cv2
    h, w = free.shape
    if not (0 <= x < w and 0 <= y < h) or free[y, x] == 0:
        return None
    src = free.copy()
    mask = np.zeros((h + 2, w + 2), dtype=np.uint8)
    cv2.floodFill(src, mask, seedPoint=(x, y), newVal=128, loDiff=0, upDiff=0, flags=4)
    return (src == 128).astype(np.uint8)


def _polygon(mask: np.ndarray) -> np.ndarray | None:
    import cv2
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not contours:
        return None
    contour = max(contours, key=cv2.contourArea)
    x, y, w, h = cv2.boundingRect(contour)
    eps = float(np.hypot(w, h)) * SIMPLIFY_PCT / 100.0
    poly = cv2.approxPolyDP(contour, eps, closed=True).reshape(-1, 2)
    return poly if len(poly) >= 3 else None


def _inside(poly: np.ndarray, x: float, y: float) -> bool:
    import cv2
    return cv2.pointPolygonTest(poly.reshape(-1, 1, 2).astype(np.int32), (float(x), float(y)), False) >= 0


def trace_room(free: np.ndarray, seed_px: tuple[int, int], area_m2: float, m_per_px: float,
               seed_offsets_px: Sequence[tuple[int, int]]) -> dict | None:
    """The best fill around the seed for a room of `area_m2`: its polygon (px),
    area and perimeter in metres, and the relative area error. None when no
    fill comes within AREA_TOL."""
    import cv2
    best = None
    page_px = free.shape[0] * free.shape[1]
    for dx, dy in seed_offsets_px:
        mask = _fill(free, seed_px[0] + dx, seed_px[1] + dy)
        if mask is None:
            continue
        n = int(mask.sum())
        est = n * m_per_px ** 2
        if n > 0.25 * page_px or est < MIN_ROOM_M2 or est > 3 * area_m2:
            continue                                   # leaked into the flat, or a pocket
        poly = _polygon(mask)
        if poly is None:
            continue
        cnt = poly.reshape(-1, 1, 2).astype(np.int32)
        perim = cv2.arcLength(cnt, True) * m_per_px
        # A rasterised boundary sits half a pixel outside the wall face on every
        # side, so a fill runs about one pixel × its perimeter large (objektas_g
        # room 09: 6,88 m² for a 2,31 × 2,935 = 6,78 m² room at 200 dpi). Take
        # that strip off before the check — it is geometry, not calibration.
        pa = cv2.contourArea(cnt) * m_per_px ** 2 - perim * m_per_px
        err = _rel(pa, area_m2)
        if err > AREA_TOL:
            continue
        cand = {"poly": poly, "plotas_m2": pa, "perimetras_m": perim, "paklaida": err}
        # Among fills within tolerance the TIGHTEST outline wins: a fill that
        # leaked a little and lost a little can land on the right area with a
        # ragged, far longer boundary (06 at a 1,1 m door: −1 %, 17,4 m against
        # 12,8 m). A shorter perimeter cannot come from a leak.
        if best is None or (perim, err) < (best["perimetras_m"], best["paklaida"]):
            best = cand
        if err <= 0.01:
            break
    return best


# ── the lane ─────────────────────────────────────────────────────────────────

def _scales(dims: Sequence[dict] | None, override: dict[int, float] | None) -> dict[int, float]:
    out: dict[int, float] = {}
    for d in dims or []:
        s = _f(d.get("scale_m_per_pt"))
        if s:
            out.setdefault(int(d["page"]), s)
    if override:
        out.update({int(k): float(v) for k, v in override.items()})
    return out


def apply_wall_outlines(rooms: Sequence[dict], pdf_bytes: bytes, dims: Sequence[dict] | None = None,
                        annotations: Sequence[dict] | None = None, *,
                        scale_by_page: dict[int, float] | None = None, dpi: int = DPI) -> dict:
    """Trace every room's outline from the wall geometry (module doc).
    Mutates rooms in place; returns {status, pages, traced, confirmed,
    corrected, unmatched, skipped, dpi}."""
    summary: dict[str, Any] = {"status": "insufficient", "pages": [], "traced": [], "confirmed": [],
                               "corrected": [], "unmatched": [], "skipped": [], "dpi": dpi}
    scales = _scales(dims, scale_by_page)
    if not scales:
        return summary
    groups = frame_groups(dims) if dims else {}
    dims_per_page: dict[int, int] = {}
    for d in dims or []:
        dims_per_page[int(d["page"])] = dims_per_page.get(int(d["page"]), 0) + 1

    # where each room is labelled, and which pages to try for it
    todo: dict[int, list[tuple[dict, dict]]] = {}
    labels_on: dict[int, list[tuple[str, float, float]]] = {}
    for room in rooms:
        if not isinstance(room, dict):
            continue
        area = _f(room.get("plotas_m2"))
        pos = _label_position(room, annotations, dims_per_page) if area and area > 0 else None
        if pos is None:
            continue
        nr = str(room.get("nr") or "").strip()
        frame = sorted(groups.get(pos["page"], {pos["page"]}) | {pos["page"]},
                       key=lambda p: (p != pos["page"], -dims_per_page.get(p, 0)))
        for p in frame:
            labels_on.setdefault(p, []).append((nr, pos["cx"], pos["cy"]))
        if str(room.get("polygon_source") or "") in _KEPT_POLYGONS:
            summary["skipped"].append(nr)
            continue
        todo.setdefault(pos["page"], []).append((room, {**pos, "frame": frame}))

    solved: set[int] = set()
    rendered: dict[int, dict] = {}

    def page_data(pn: int) -> dict | None:
        if pn in rendered:
            return rendered[pn]
        scale_pt = scales.get(pn) or next((scales[q] for q in groups.get(pn, set()) if q in scales), None)
        if not scale_pt:
            rendered[pn] = None
            return None
        raster = render_walls_only(pdf_bytes, pn, dpi)
        if raster is None:
            rendered[pn] = None
            return None
        m_per_px = scale_pt * 72.0 / dpi
        px_per_mm = dpi / 25.4
        wall = wall_mask(raster)
        thick_px = int(round(THICK_WALL_MM * px_per_mm))
        thick = thick_walls(wall, thick_px)
        rendered[pn] = {"raster": raster, "wall": wall, "thick": thick, "thick_px": thick_px,
                        "m_per_px": m_per_px, "px_per_mm": px_per_mm, "free": {}}
        summary["pages"].append(pn)
        return rendered[pn]

    def free_for(pd: dict, door_m: float) -> np.ndarray:
        if door_m not in pd["free"]:
            pd["free"][door_m] = free_space(pd["wall"], pd["thick"], int(round(door_m / pd["m_per_px"])),
                                            int(round(WINDOW_M / pd["m_per_px"])), int(round(RUN_M / pd["m_per_px"])),
                                            pd["thick_px"])
        return pd["free"][door_m]

    for label_page, items in todo.items():
        for room, pos in items:
            nr = str(room.get("nr") or "").strip()
            area = float(room["plotas_m2"])
            found = None
            for pn in pos["frame"]:
                pd = page_data(pn)
                if pd is None:
                    continue
                h, w = pd["raster"].shape
                seed = (int(round(pos["cx"] * w)), int(round(pos["cy"] * h)))
                offsets = [(int(round(dx * pd["px_per_mm"])), int(round(dy * pd["px_per_mm"]))) for dx, dy in SEED_MM]
                others = [(o, ox * w, oy * h) for (o, ox, oy) in labels_on.get(pn, []) if o != nr]
                for door_m in DOOR_M:
                    cand = trace_room(free_for(pd, door_m), seed, area, pd["m_per_px"], offsets)
                    if cand is None:
                        continue
                    if any(_inside(cand["poly"], ox, oy) for _, ox, oy in others):
                        continue                       # the fill swallowed a neighbour — an open plan
                    cand.update({"page": pn, "durys_m": door_m, "w": w, "h": h})
                    if found is None or (cand["perimetras_m"], cand["paklaida"]) < (found["perimetras_m"], found["paklaida"]):
                        found = cand
                    if cand["paklaida"] <= 0.01:
                        break
                if found is not None and found["paklaida"] <= 0.01:
                    break
            if found is None:
                summary["unmatched"].append(nr)
                continue
            w, h = found["w"], found["h"]
            room["polygon_pct"] = [[round(float(x) / w, 5), round(float(y) / h, 5)] for x, y in found["poly"].tolist()]
            room["polygon_source"] = SOURCE
            room["_konturas"] = {
                "page": int(found["page"]), "plotas_m2": round(found["plotas_m2"], 2),
                "perimetras_m": round(found["perimetras_m"], 2), "plotas_uzrasas_m2": round(area, 2),
                "paklaida": round(found["paklaida"], 4), "durys_m": found["durys_m"], "dpi": dpi,
            }
            summary["traced"].append(nr)
            if str(room.get("perimetras_saltinis") or "").lower() in _STATED_PERIMETERS or room.get("manual_override"):
                continue
            old = _f(room.get("perimetras_m"))
            perim = round(found["perimetras_m"], 2)
            room["_perimetras_pries_kontura"] = round(old, 2) if old is not None else None
            room["perimetras_m"] = perim
            room["perimetras_saltinis"] = SOURCE
            (summary["confirmed"] if (old and _rel(old, perim) <= CONFIRM_TOL) else summary["corrected"]).append(nr)
    summary["pages"].sort()
    if summary["traced"]:
        summary["status"] = "applied"
    elif summary["unmatched"]:
        summary["status"] = "no_match"
    return summary


def outline_rect_pct(room: dict) -> list[float] | None:
    """The traced outline's bounding box as shares of the page — the check sheet's crop."""
    poly = room.get("polygon_pct")
    if str(room.get("polygon_source") or "") != SOURCE or not isinstance(poly, list) or len(poly) < 3:
        return None
    xs = [float(p[0]) for p in poly]
    ys = [float(p[1]) for p in poly]
    return [round(max(0.0, min(xs)), 4), round(max(0.0, min(ys)), 4), round(min(1.0, max(xs)), 4), round(min(1.0, max(ys)), 4)]


def outline_mastelis(m_per_pt: float | None) -> int | None:
    return int(round(m_per_pt / _PT_M)) if m_per_pt else None
