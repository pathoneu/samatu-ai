"""ONE source of truth for a sheet's scale (plan 2026-10-24 §3.1 `scale.py`, §9 Phase 1 cause 5).

`scale_for_page(ctx, page) -> Scale` tries, in order, and every answer carries its provenance
(`geometry.provenance.Scale`: m_per_pt, source, source_text, confidence, page_from):

1. USER_LINE — a person drew a line over a dimension string („Mastelis" tool,
   `POST /api/projects/{id}/geometry/scale-line`, stored in `page_scales`). Always wins.
2. DIMENSION_LINES — dimension strings sitting on their own hairline. This is
   `extractor.plan_dimensions` unchanged (its stated-scale snap, its refusals): this module
   only reads the `scale_m_per_pt` it put on the strings.
3. DIMENSION_WALLS — strings with NO hairline (objektas_c, r1, j1 and objektas_i sheets 6, 8–10
   had none line-backed), matched to the wall faces they measure: a horizontal string is paired
   with two vertical wall faces on either side of it, roughly centred on it, near it across;
   each pair proposes a scale = value / distance. A scale is accepted when ≥ WALL_MIN_AGREE
   different strings propose it within WALL_TOL (1 %), it beats every other proposal by
   WALL_PEAK_RATIO (a chance agreement does not), and it is a plan's scale (1:20…1:500).
4. STATED — „M 1:50" written on the sheet (`plan_dimensions.stated_scales_on_page`, the same
   rule the line reader uses). Validated against 2/3 when they exist (snapped to the stated one
   when they agree within STATED_SNAP, noted when they do not, and the measurement wins) and
   against the strings' refused reading when that reading is the stated scale in other units
   (objektas_j1: strings in centimetres, measured 1:10 against „M 1:100" → 1:100, HIGH).
   A stated scale nothing measured confirms is LOW — and when a SIBLING sheet measured another
   scale, the sibling wins: a set printed reduced states 1:40 and measures 1:45 (objektas_j2).
5. SIBLING — a sheet of the same set with a measured scale (1–3) that overlays this sheet:
   same frame size, and either its wall fills coincide (`sheet_alignment`, ≥ 0,85 overlap; the
   scale follows the fit's factor k) or — for sheets drawn without wall fills (objektas_d draws
   walls as black strokes) — its stroked drawing coincides after one translation at k = 1
   (≥ STROKE_SAME of the smaller sheet's vertices). `page_from` names the sheet.
6. BLANK — with a reason sentence. Never a default.

Deterministic only — no `vision*` import (guard test). The lane (`extractor/geometry_lane.py`)
asks this module for every sheet its own dimension lines leave without a scale.
"""
from __future__ import annotations

import bisect
import logging
import math
import statistics
from dataclasses import dataclass, field, replace
from typing import Iterable, Sequence

from .provenance import HIGH, LOW, MEDIUM, PT_M, Scale, ScaleSource, blank

log = logging.getLogger("samatu.geometry.scale")

# ── constants (each one a stated rule, not a tuned share) ────────────────────
MIN_DENOM, MAX_DENOM = 20, 500          # a plan's scale (plan_dimensions.MIN/MAX_SCALE_DENOM)
RANGE_TOL = 0.03
STANDARD = (20, 25, 30, 40, 50, 75, 100, 125, 150, 200, 250, 500)
STATED_SNAP = 0.02          # a measured scale this close to the stated one IS the stated one (exact)
UNIT_RATIOS = (10.0, 100.0)  # strings in cm or dm read as mm measure 10× / 100× too large a scale
UNIT_TOL = 0.015            # …and the product must land this close on the stated (or a standard) scale

WALL_TOL = 0.01             # strings agreeing within 1 % propose one scale
WALL_MIN_AGREE = 5          # ≥ 5 different strings must agree (one room's four sides are not a sheet)
WALL_MIN_VALUES = 4         # …written with ≥ 4 different values (a module repeated five times proves one ratio, not a scale)
WALL_PEAK_RATIO = 2.0       # …and the scale must have twice the support of any other proposal
WALL_RIVAL_APART = 0.04     # a rival proposal is one at least 4 % away
# Measured 2026-10-24 against the 48 sheets of a, b, d, g, h, i, j2 whose strings sit on hairlines (source 2 known),
# with their hairlines hidden: 7 right (≤ 0,9 %), 0 wrong, 41 silent. Letting a string also pair with the far face of a
# wall, counting a rival only by strings of its own, or a centre tolerance of 30 % each produced wrong scales there
# (half the scale on electrical sheets, +5 % on elevations) — so: nearest faces only, every string counts for a rival,
# 15 % centre tolerance, and a scale no drawing is made at needs twice the evidence.
WALL_CENTRE_TOL = 0.15     # the string sits at its span's middle (within 15 % of the span) — a string at a quarter point measures half a room (an outlet's offset), never the room
WALL_NEAR_PT = 120.0        # a face counts for a string when its extent comes this close across
WALL_MIN_FACE_PT = 6.0      # wall faces shorter than this are corners and caps
AXIS_TOL_PT = 0.6           # an edge this close to vertical / horizontal is one
FACE_MERGE_PT = 0.5         # faces this close along the axis are one line
MAX_FILL_SHARE = 0.2        # a fill covering more of the page is a background (vector_rooms.MAX_FILL_SHARE)

SIZE_TOL_PT = 2.0           # two sheets share a frame when their sizes agree this closely
STROKE_SAME = 0.8           # share of the smaller sheet's stroke vertices that must coincide after one shift
STROKE_NEAR_PT = 1.5
STROKE_MIN_W = 0.2          # hairlines (text-leaders, hatching) are not the drawing's body
STROKE_MIN_PTS = 40          # ≥ 10 drawn rectangles: fewer vertices coincide by chance
STROKE_SAMPLE = 700


def _in_plan_range(m_per_pt: float) -> bool:
    d = m_per_pt / PT_M
    return MIN_DENOM * (1 - RANGE_TOL) <= d <= MAX_DENOM * (1 + RANGE_TOL)


def _ratio(n: float) -> str:
    return f"1:{int(round(n))}"


# ── the context: one drawing, read once ─────────────────────────────────────

@dataclass
class ScaleContext:
    """What every source reads from. `dims`: `plan_dimensions.read_dimension_strings` output (read
    lazily when None). `user_scales`: {page: {m_per_pt, source_text, …}} from `page_scales`.
    `alignment`: the lane's `sheet_alignment.align_sheets` answer when it has one (saves a re-read)."""
    pdf_bytes: bytes
    dims: list[dict] | None = None
    user_scales: dict[int, dict] | None = None
    alignment: dict | None = None
    _stated: dict[int, set[int]] = field(default_factory=dict)
    _sizes: dict[int, tuple[float, float]] = field(default_factory=dict)
    _measured: dict[int, Scale] = field(default_factory=dict)
    _faces: dict[int, tuple[list, list]] = field(default_factory=dict)
    _strokes: dict[int, list] = field(default_factory=dict)
    _sigs: dict[int, object] = field(default_factory=dict)
    _ocr: dict[int, bool] = field(default_factory=dict)        # v4 ocr hook: page → OCR added strings / a scale
    _ocr_scale: dict[int, Scale] = field(default_factory=dict)  # v4 ocr wiring: page → scale its OCR'd strings measure on their lines

    def strings(self) -> list[dict]:
        if self.dims is None:
            from extractor.plan_dimensions import read_dimension_strings
            self.dims = read_dimension_strings(self.pdf_bytes)
        return self.dims

    def strings_on(self, page: int) -> list[dict]:
        on = [d for d in self.strings() if int(d.get("page") or 0) == int(page)]
        if len(on) < WALL_MIN_AGREE and self._ocr_fill(page):          # v4 ocr hook
            on = [d for d in self.strings() if int(d.get("page") or 0) == int(page)]
        return on

    def _ocr_fill(self, page: int) -> bool:
        """v4 ocr hook (plan §9 Phase 1 cause 7). With `SAMATU_OCR` on, a sheet whose TEXT LAYER gives no written
        scale and fewer dimension strings than any source can use (< WALL_MIN_AGREE, none on a hairline) is read by
        local OCR (`text.ocr.dimension_strings`). objektas_c sheet 3: four „760" in the layer, its other strings
        drawn as outlines. The OCR strings REPLACE the layer's on that sheet (the render shows those too, so
        nothing is lost and nothing is counted twice) — marked `source: "ocr"`, no hairline, so only source 3 can
        use them — and its written scale joins `_stated` (source 4). Once per page; True when OCR added
        something. Flag off: returns False before importing anything."""
        page = int(page)
        if page in self._ocr:
            return self._ocr[page]
        from text.ocr import ocr_enabled
        if not ocr_enabled():
            return False
        self._ocr[page] = False
        layer = [d for d in self.strings() if int(d.get("page") or 0) == page]
        if len(layer) >= WALL_MIN_AGREE or any(d.get("scale_m_per_pt") for d in layer):
            return False
        self.load_stated([page])
        if self._stated.get(page):
            return False
        try:
            from text.ocr import dimension_strings
            dims, stated = dimension_strings(self.pdf_bytes, page)
        except Exception:  # noqa: BLE001 — OCR missing or failing leaves the sheet as the text layer left it
            log.exception("OCR unavailable on page %s", page)
            return False
        if dims:
            self.dims = [d for d in self.strings() if int(d.get("page") or 0) != page] + dims
        self._stated.setdefault(page, set()).update(stated)
        try:                                                        # v4 ocr wiring: the OCR'd strings on their lines
            sc = _ocr_line_match(self, page, dims, stated)
        except Exception:  # noqa: BLE001 — never at the cost of what OCR already gave
            log.exception("OCR line match failed on page %s", page)
            sc = None
        if sc is not None:
            self._ocr_scale[page] = sc
        self._ocr[page] = bool(dims or stated)
        return self._ocr[page]

    def page_count(self) -> int:
        from extractor.pdfium_guard import PDFIUM_LOCK
        import pypdfium2 as pdfium
        with PDFIUM_LOCK:
            doc = pdfium.PdfDocument(self.pdf_bytes)
            try:
                return len(doc)
            finally:
                doc.close()

    def size(self, page: int) -> tuple[float, float]:
        if page not in self._sizes:
            for d in (d for d in self.strings() if int(d.get("page") or 0) == int(page)):
                if d.get("page_width") and d.get("page_height"):
                    self._sizes[page] = (float(d["page_width"]), float(d["page_height"]))
                    break
            else:
                from extractor.pdf_vectors import page_geometry
                W, H, _ = page_geometry(self.pdf_bytes, page)
                self._sizes[page] = (float(W), float(H))
        return self._sizes[page]

    def stated(self, page: int) -> set[int]:
        """The plan scales the sheet writes („M 1:50") — the line reader's own rule."""
        if page not in self._stated:
            self.load_stated([page])
        if not self._stated.get(page):
            self._ocr_fill(page)                                     # v4 ocr hook
        return self._stated.get(page, set())

    def load_stated(self, pages: Iterable[int]) -> None:
        todo = sorted({int(p) for p in pages} - set(self._stated))
        if not todo:
            return
        from extractor.plan_dimensions import _iter_pages, stated_scales_on_page
        for p in todo:
            self._stated[p] = set()
        try:
            for pn, _W, _H, chars, _ in _iter_pages(self.pdf_bytes, todo):
                self._stated.setdefault(pn, set()).update(stated_scales_on_page(chars))
        except Exception:  # noqa: BLE001 — an unreadable text layer states nothing
            log.exception("stated scales unreadable")


# ── 1. the person's line ────────────────────────────────────────────────────

def _user(ctx: ScaleContext, page: int) -> Scale | None:
    u = (ctx.user_scales or {}).get(int(page))
    if not u or not u.get("m_per_pt"):
        return None
    return Scale(m_per_pt=float(u["m_per_pt"]), source=ScaleSource.USER_LINE,
                 source_text=u.get("source_text"), confidence=HIGH,
                 details={k: u[k] for k in ("user_id", "created_at", "length_pt", "value_m") if u.get(k) is not None})


# ── 2. strings on their hairlines (plan_dimensions, unchanged) ──────────────

def _lines(ctx: ScaleContext, page: int) -> Scale | None:
    on = ctx.strings_on(page)
    backed = [d for d in on if d.get("span_source") == "line"]
    s = next((float(d["scale_m_per_pt"]) for d in on if d.get("scale_m_per_pt")), None)
    if not s:
        return None
    other = next((d.get("mastelis_kitas") for d in on if d.get("mastelis_kitas")), None)
    sc = Scale(m_per_pt=s, source=ScaleSource.DIMENSION_LINES,
               source_text=f"{len(backed)} matmenų eilutės ant matmenų linijų",
               confidence=HIGH if len(backed) >= 10 else MEDIUM,
               details={"strings": len(on), "line_backed": len(backed)})
    if other:
        sc.reason = (f"Lape užrašytas mastelis {', '.join(_ratio(n) for n in other.get('uzrasyta') or [])}, "
                     f"bet matmenys atitinka {_ratio(other.get('ismatuota') or s / PT_M)} — lapas tikriausiai spausdintas kitu dydžiu.")
        sc.details["stated_other"] = other
    return sc


# ── 2b. OCR'd strings on their lines (v4 ocr wiring, SAMATU_OCR) ────────────
# A sheet with no text layer (objektas_c: strings drawn as outlines; j4: all text as outlines; j3: a scan) gets its
# strings from OCR (`_ocr_fill`). They have no hairline from plan_dimensions — that reader needs a text-layer string
# to look under — so here each OCR'd string is matched to the lines it could be written on: the vector hairlines
# PDFium finds (`plan_dimensions._page_lines_pdfium`) and the lines read off the RENDER under each string
# (`text.raster_lines`; the only lines a scan has). Every (string, line) pair proposes value / length, and the scale
# is the densest proposal by the source-3 rules (WALL_MIN_AGREE different strings, WALL_MIN_VALUES values, twice any
# rival; a scale no drawing is made at needs twice that) — `plan_dimensions`' own 40 %-of-the-strings rule cannot be
# used, because OCR also returns every room number, height and furniture size as a „string".
# Readings: millimetres first; centimetres only when the millimetre reading is no plan's scale at all (j4: 1:8,5 as
# mm → 1:87 as cm) and the sheet writes no detail scale (a 1:10 detail in mm looks exactly like 1:100 in cm).
# A written scale (OCR'd „M 1:50") that the measurement contradicts by more than STATED_MISMATCH is MARKED and the
# measurement wins — c writes 1:50 and measures ≈ 1:60 (a reduced print); j3, a scan of a reduced print, writes 1:40
# and measures ≈ 1:64. When a written scale is contradicted, a measurement that is the densest but short of twice its
# rival is still taken (LOW): j3's numbers are the contractor's tape readings, which scatter by a few per cent.
OCR_LINES_NOTE = "skaičiai perskaityti iš lapo vaizdo"
OCR_CM_NOTE = "matmenys centimetrais"
STATED_MISMATCH = 0.05      # a written scale further than this from the measured one is contradicted
OCR_LINE_SNAP_PT = 0.5      # a string's candidate lines this close in length are one line (vector + raster twins)


def _ocr_props(dims: Sequence[dict], lines: dict) -> list[tuple[float, int]]:
    from extractor.plan_dimensions import _line_candidates
    props: list[tuple[float, int]] = []
    for i, d in enumerate(dims):
        try:
            lengths = sorted({round(float(L) / OCR_LINE_SNAP_PT) * OCR_LINE_SNAP_PT
                              for *_, L in _line_candidates(d, lines)})
            v = float(d["value_m"])
        except (KeyError, TypeError, ValueError):
            continue
        props += [(v / L, i) for L in lengths if L > 0]
    return props


def _ocr_candidates(dims: Sequence[dict], line_sets: Sequence[tuple[str, dict]]) -> list[dict]:
    """The densest proposal per line source: {scale, support, rival, values, lines, idx, props}."""
    out = []
    for src, lines in line_sets:
        props = _ocr_props(dims, lines)
        pk = _peak(props)
        if pk is None:
            continue
        sc_, support, rival, idx = pk
        out.append({"scale": sc_, "support": support, "rival": rival, "lines": src, "idx": idx, "props": props,
                    "values": len({float(dims[i]["value_m"]) for i in idx}), "in_range": _in_plan_range(sc_)})
    return out


def _ocr_strong(c: dict) -> bool:
    if not c["in_range"] or c["support"] < WALL_MIN_AGREE or c["values"] < WALL_MIN_VALUES:
        return False
    if c["support"] < WALL_PEAK_RATIO * c["rival"]:
        return False
    n = c["scale"] / PT_M
    if not any(abs(n - st) / st <= STATED_SNAP for st in STANDARD) and (
            c["support"] < 2 * WALL_MIN_AGREE or c["support"] < 1.5 * WALL_PEAK_RATIO * c["rival"]):
        return False        # a scale no drawing is made at (a reduced print) needs twice the evidence (source 3's rule)
    return True


def _ocr_contradicts(c: dict, stated: Sequence[int]) -> bool:
    """Rule for a written scale the strings contradict: the measurement is the densest proposal (more strings than
    any rival), WALL_MIN_AGREE strings with WALL_MIN_VALUES values, more than STATED_MISMATCH from the written
    scale, and at least twice as many strings as propose the written one."""
    if len(stated) != 1 or not c["in_range"] or c["support"] < WALL_MIN_AGREE or c["values"] < WALL_MIN_VALUES:
        return False
    if c["support"] <= c["rival"]:
        return False
    w = stated[0]
    if abs(c["scale"] / PT_M / w - 1) <= STATED_MISMATCH:
        return False
    lw = math.log(w * PT_M)
    backing = {i for s, i in c["props"] if abs(math.log(s) - lw) <= math.log(1 + WALL_TOL)}
    return c["support"] >= WALL_PEAK_RATIO * len(backing)


def _ocr_scale(c: dict, dims: Sequence[dict], units: str, stated: Sequence[int], weak: bool) -> Scale:
    n = c["scale"] / PT_M
    m_per_pt = c["scale"]
    sample = ", ".join(sorted({str(dims[i]["text"]) for i in c["idx"]})[:6])
    text = f"{c['support']} matmenų eilutės ant matmenų linijų ({sample}); {OCR_LINES_NOTE}"
    if units == "cm":
        text += f"; {OCR_CM_NOTE}"
    details = {"ocr": True, "units": units, "lines": c["lines"], "agree": c["support"], "rival": c["rival"],
               "values": c["values"], "strings": len(dims)}
    reason = None
    if stated:
        near = min(stated, key=lambda s: abs(n - s) / s)
        details["stated"] = list(stated)
        dev = n / near - 1
        if abs(dev) <= STATED_SNAP:
            m_per_pt = near * PT_M
            text += f"; sutampa su užrašytu M {_ratio(near)}"
        elif abs(dev) > STATED_MISMATCH:
            text += f"; užrašytas mastelis neatitinka matmenų (≈ {_ratio(n)})"
            reason = (f"Lape užrašytas M {_ratio(near)}, bet matmenys atitinka ≈ {_ratio(n)} — lapas tikriausiai "
                      f"spausdintas kitu dydžiu. Patikrinkite mastelį, nubrėžę liniją ant žinomo matmens.")
        else:
            reason = (f"Lape užrašytas M {_ratio(near)}, matmenys atitinka {_ratio(n)} — patikrinkite mastelį, "
                      f"nubrėžę liniją ant žinomo matmens.")
    if weak and reason is None:
        reason = "Matmenys tarpusavyje sutampa tik apytiksliai — patikrinkite mastelį, nubrėžę liniją ant žinomo matmens."
    sc = Scale(m_per_pt=m_per_pt, source=ScaleSource.DIMENSION_LINES, source_text=text,
               confidence=LOW if weak else MEDIUM, details=details)
    sc.reason = reason
    return sc


def _ocr_line_match(ctx: "ScaleContext", page: int, dims_mm: Sequence[dict], stated: Iterable[int]) -> Scale | None:
    """The scale a sheet's OCR'd strings measure on their lines (section doc above), or None."""
    from extractor.plan_dimensions import _page_lines_pdfium
    from text.ocr import detail_scales, dimension_strings
    from text.raster_lines import sheet_dimension_lines
    stated = sorted(set(stated))
    dims_cm, _ = dimension_strings(ctx.pdf_bytes, page, units="cm")
    if len(dims_mm) + len(dims_cm) < WALL_MIN_AGREE:
        return None
    try:
        vector = _page_lines_pdfium(ctx.pdf_bytes, {page}).get(page) or {"h": [], "v": []}
    except Exception:  # noqa: BLE001 — a raster sheet has no vector lines
        vector = {"h": [], "v": []}
    raster = sheet_dimension_lines(ctx.pdf_bytes, page, list(dims_mm) + list(dims_cm))
    line_sets = [("raster", raster), ("vector", vector),
                 ("union", {"h": raster["h"] + vector["h"], "v": raster["v"] + vector["v"]})]

    def best(cands: list[dict], ok) -> dict | None:
        good = [c for c in cands if ok(c)]
        return max(good, key=lambda c: (c["support"], -c["rival"])) if good else None

    mm = _ocr_candidates(dims_mm, line_sets)
    c = best(mm, _ocr_strong)
    if c is not None:
        return _ocr_scale(c, dims_mm, "mm", stated, weak=False)
    c = best(mm, lambda c: _ocr_contradicts(c, stated))
    if c is not None:
        return _ocr_scale(c, dims_mm, "mm", stated, weak=True)
    # centimetres: only when the millimetre reading is no plan's scale at all, and no detail scale is written
    if any(c["in_range"] and c["support"] >= WALL_MIN_AGREE for c in mm):
        return None
    cm = _ocr_candidates(dims_cm, line_sets)
    c, weak = best(cm, _ocr_strong), False
    if c is None:
        c, weak = best(cm, lambda c: _ocr_contradicts(c, stated)), True
    if c is None or detail_scales(ctx.pdf_bytes, page):
        return None
    return _ocr_scale(c, dims_cm, "cm", stated, weak=weak)


def _ocr_lines(ctx: ScaleContext, page: int) -> Scale | None:
    ctx.strings_on(page)                   # OCRs the sheet when it qualifies (flag on; `_ocr_fill`)
    sc = ctx._ocr_scale.get(int(page))
    return replace(sc, details=dict(sc.details)) if sc else None


# ── 3. strings matched to the wall faces they measure ───────────────────────

def _wall_faces(ctx: ScaleContext, page: int) -> tuple[list, list]:
    """(vertical faces [(x, y0, y1)], horizontal faces [(y, x0, x1)]) of the page's wall solid —
    the union of EVERY non-black wall-shaped fill (not one dominant colour: objektas_i draws
    outer walls dark grey and partitions mid grey), display frame."""
    if page in ctx._faces:
        return ctx._faces[page]
    vs: list[tuple[float, float, float]] = []
    hs: list[tuple[float, float, float]] = []
    try:
        from shapely.ops import unary_union
        from extractor.pdf_vectors import _is_wall_shape, filled_shapes
        W, H = ctx.size(page)
        fills = [p for _c, p in filled_shapes(ctx.pdf_bytes, page)
                 if _is_wall_shape(p) and p.area < MAX_FILL_SHARE * W * H]
        if fills:
            solid = unary_union(fills).buffer(0.25, join_style=2).buffer(-0.25, join_style=2).simplify(0.2)
            polys = solid.geoms if hasattr(solid, "geoms") else [solid]
            for poly in polys:
                if poly.geom_type != "Polygon":
                    continue
                for ring in [poly.exterior, *poly.interiors]:
                    pts = list(ring.coords)
                    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
                        if abs(x1 - x0) <= AXIS_TOL_PT and abs(y1 - y0) >= WALL_MIN_FACE_PT:
                            vs.append(((x0 + x1) / 2, min(y0, y1), max(y0, y1)))
                        elif abs(y1 - y0) <= AXIS_TOL_PT and abs(x1 - x0) >= WALL_MIN_FACE_PT:
                            hs.append(((y0 + y1) / 2, min(x0, x1), max(x0, x1)))
    except Exception:  # noqa: BLE001 — a page without a vector layer has no faces
        log.exception("wall faces unreadable on page %s", page)
    ctx._faces[page] = (vs, hs)
    return vs, hs


def _bracket(positions: list[float], c: float, half: float) -> tuple[float, float] | None:
    """The face pair that BRACKETS a string: the nearest face left of it and the nearest right of it."""
    k0 = bisect.bisect_left(positions, c - half)
    k1 = bisect.bisect_right(positions, c + half)
    return (positions[k0 - 1], positions[k1]) if k0 >= 1 and k1 < len(positions) else None


def _proposals(strings: Sequence[dict], faces_v: list, faces_h: list, factor: float) -> list[tuple[float, int]]:
    """(scale, string index) for the face pairs a string could measure (module doc, source 3): the faces that
    bracket it on its own line across (a string written inside a room, between the walls it measures), and the
    faces of the nearest walls within WALL_NEAR_PT across (a chain written outside the walls it measures).
    Only the nearest face on each side — never every pair on the sheet: with every pair, any scale finds support
    by chance (measured, see WALL_CENTRE_TOL).
    `factor`: the strings' values are multiplied by it (10 = they were written in centimetres)."""
    out: list[tuple[float, int]] = []
    lo_m, hi_m = MIN_DENOM * (1 - RANGE_TOL) * PT_M, MAX_DENOM * (1 + RANGE_TOL) * PT_M
    for i, d in enumerate(strings):
        try:
            v = float(d["value_m"]) * factor
            x0, top, x1, bottom = (float(t) for t in d["bbox"])
        except (KeyError, TypeError, ValueError):
            continue
        if d.get("orientation") == "h":
            c, across, half, faces = (x0 + x1) / 2, (top + bottom) / 2, (x1 - x0) / 2, faces_v
        elif d.get("orientation") == "v":
            c, across, half, faces = (top + bottom) / 2, (x0 + x1) / 2, (bottom - top) / 2, faces_h
        else:
            continue
        on_line = sorted({round(pos / FACE_MERGE_PT) * FACE_MERGE_PT for pos, a0, a1 in faces if a0 <= across <= a1})
        near = sorted({round(pos / FACE_MERGE_PT) * FACE_MERGE_PT for pos, a0, a1 in faces
                       if a0 - WALL_NEAR_PT <= across <= a1 + WALL_NEAR_PT})
        pairs = {pr for pr in (_bracket(on_line, c, half), _bracket(near, c, half)) if pr}
        seen: set[float] = set()
        for a, b in pairs:
            L = b - a
            if L <= 0:
                continue
            s = v / L
            if not (lo_m <= s <= hi_m):
                continue
            if abs(c - (a + b) / 2) > WALL_CENTRE_TOL * L:
                continue
            key = round(math.log(s), 4)
            if key not in seen:
                seen.add(key)
                out.append((s, i))
    return out


def _peak(props: list[tuple[float, int]]) -> tuple[float, int, int, list[int]] | None:
    """(scale, support, best rival support, supporting strings) — support = distinct strings within ±WALL_TOL."""
    if not props:
        return None
    props = sorted(props)
    logs = [math.log(s) for s, _ in props]
    w = math.log(1 + WALL_TOL)
    windows: list[tuple[int, float, list[int]]] = []
    j0 = 0
    for i, li in enumerate(logs):
        while logs[j0] < li - w:
            j0 += 1
        j1 = bisect.bisect_right(logs, li + w)
        idx = sorted({props[j][1] for j in range(j0, j1)})
        windows.append((len(idx), props[i][0], idx))
    best = max(windows, key=lambda t: t[0])
    count, centre, idx = best
    # one proposal per supporting string: the one closest to the centre
    per: dict[int, float] = {}
    for s, i in props:
        if i in idx and abs(math.log(s / centre)) <= w:
            if i not in per or abs(math.log(s / centre)) < abs(math.log(per[i] / centre)):
                per[i] = s
    scale = statistics.median(per.values())
    rival = max((n for n, s, _ in windows if abs(math.log(s / scale)) > math.log(1 + WALL_RIVAL_APART)), default=0)
    return scale, count, rival, sorted(per)


def _unbacked(ctx: ScaleContext, page: int) -> list[dict]:
    return [d for d in ctx.strings_on(page) if d.get("orientation") in ("h", "v") and d.get("span_source") != "line"]


def _match(ctx: ScaleContext, pages: Sequence[int]) -> Scale | None:
    """Source 3 over the strings of `pages` (one sheet, or sheets of one plan pooled)."""
    strings: list[dict] = []
    props: dict[float, list[tuple[float, int]]] = {1.0: [], 10.0: []}
    for p in pages:
        on = _unbacked(ctx, p)
        fv, fh = _wall_faces(ctx, p)
        if not on or len(fv) + len(fh) < 4:
            continue
        for factor in props:
            props[factor] += [(sc, i + len(strings)) for sc, i in _proposals(on, fv, fh, factor)]
        strings += on
    if len(strings) < WALL_MIN_AGREE:
        return None
    for factor in (1.0, 10.0):
        pk = _peak(props[factor])
        if pk is None:
            continue
        sc_, support, rival, idx = pk
        if support < WALL_MIN_AGREE or support < WALL_PEAK_RATIO * rival or not _in_plan_range(sc_):
            continue
        if len({float(strings[i]["value_m"]) for i in idx}) < WALL_MIN_VALUES:
            continue
        n = sc_ / PT_M
        if not any(abs(n - st) / st <= STATED_SNAP for st in STANDARD) and (
                support < 2 * WALL_MIN_AGREE or support < 1.5 * WALL_PEAK_RATIO * rival):
            continue        # a scale no drawing is made at (a reduced print) needs twice the evidence
        if factor != 1.0:
            # strings in centimetres: only when the scale they then give IS a drawing scale (no free correction)
            n = sc_ / PT_M
            if not any(abs(n - st) / st <= UNIT_TOL for st in STANDARD):
                continue
        sample = ", ".join(sorted({str(strings[i]["text"]) for i in idx})[:6])
        out = Scale(m_per_pt=sc_, source=ScaleSource.DIMENSION_WALLS,
                    source_text=f"{support} matmenų eilutės atitinka sienas ({sample})",
                    confidence=MEDIUM,
                    details={"strings": len(strings), "agree": support, "rival": rival,
                             "units": "cm" if factor == 10.0 else "mm"})
        if len(pages) > 1:
            out.details["pooled_pages"] = list(pages)
            out.source_text += f"; to paties plano lapai {', '.join(str(p) for p in pages)}"
        if factor != 1.0:
            out.reason = "Matmenys užrašyti centimetrais."
        return out
    return None


def _plan_siblings(ctx: ScaleContext, page: int) -> list[int]:
    """Sheets of the SAME plan at the same print scale (frame size, wall fills coinciding at k ≈ 1) that also carry
    strings with no hairline — their strings measure the same walls, so they may be pooled."""
    sp = _sig(ctx, page)
    if sp is None:
        return []
    from extractor.sheet_alignment import SAME_WALLS, _best_fit
    out = []
    for q in _candidate_pages(ctx):
        if q == page or not _same_frame(ctx, page, q) or len(_unbacked(ctx, q)) < 2:
            continue
        if any(d.get("scale_m_per_pt") for d in ctx.strings_on(q)):
            continue                       # a sheet with its own line scale lends it as a sibling instead
        sq = _sig(ctx, q)
        if sq is None:
            continue
        fit = _best_fit(sq, sp)
        if fit and fit[0] >= SAME_WALLS and abs(float(fit[1]) - 1.0) <= 0.005:
            out.append(q)
    return out


def _walls(ctx: ScaleContext, page: int) -> Scale | None:
    if len(_unbacked(ctx, page)) < 2:
        return None
    own = _match(ctx, [page])
    if own is not None:
        return own
    sibs = _plan_siblings(ctx, page)
    return _match(ctx, [page, *sibs]) if sibs else None


# ── 4. the scale written on the sheet ───────────────────────────────────────

def _refused_in_units(ctx: ScaleContext, page: int, stated: int) -> bool:
    """The line reader refused the page (`mastelis_atmestas`) at a scale that is the stated one in other units —
    strings in centimetres on a 1:100 sheet measure 1:10 (objektas_j1). Then the stated scale is CONFIRMED."""
    rec = next((d.get("mastelis_atmestas") for d in ctx.strings_on(page) if d.get("mastelis_atmestas")), None)
    if not rec or not rec.get("ismatuota"):
        return False
    measured = float(rec["ismatuota"])
    return any(abs(measured * u - stated) / stated <= 0.05 for u in UNIT_RATIOS)


def _stated_scale(n: int, confidence: str, text: str, **details) -> Scale:
    return Scale(m_per_pt=n * PT_M, source=ScaleSource.STATED, source_text=text, confidence=confidence, details=dict(details))


# ── 5. a sibling sheet that overlays this one ───────────────────────────────

def _same_frame(ctx: ScaleContext, a: int, b: int) -> bool:
    (wa, ha), (wb, hb) = ctx.size(a), ctx.size(b)
    return wa > 0 and abs(wa - wb) <= SIZE_TOL_PT and abs(ha - hb) <= SIZE_TOL_PT


def _sig(ctx: ScaleContext, page: int):
    if page not in ctx._sigs:
        try:
            from extractor.sheet_alignment import _signature
            ctx._sigs[page] = _signature(ctx.pdf_bytes, page)
        except Exception:  # noqa: BLE001
            ctx._sigs[page] = None
    return ctx._sigs[page]


def _stroke_points(ctx: ScaleContext, page: int) -> list[tuple[float, float]]:
    if page not in ctx._strokes:
        pts: list[tuple[float, float]] = []
        try:
            from extractor.pdf_vectors import page_paths
            W, H = ctx.size(page)
            for p in page_paths(ctx.pdf_bytes, page, strokes=True):
                if p.get("stroke") is None or float(p.get("width") or 0) < STROKE_MIN_W:
                    continue
                for sub in p["subpaths"]:
                    xs = [q[0] for q in sub]
                    ys = [q[1] for q in sub]
                    if max(xs) - min(xs) > 0.5 * W or max(ys) - min(ys) > 0.5 * H:
                        continue                  # the sheet's frame and title-block rules are every sheet's
                    pts.extend(sub)
        except Exception:  # noqa: BLE001
            log.exception("stroke points unreadable on page %s", page)
        ctx._strokes[page] = sorted(set((round(x, 1), round(y, 1)) for x, y in pts))
    return ctx._strokes[page]


def _stroke_overlay(ctx: ScaleContext, a: int, b: int) -> tuple[float, tuple[float, float]] | None:
    """(share of the smaller sheet's stroke vertices that land on the other's, the shift b→a) at k = 1."""
    pa, pb = _stroke_points(ctx, a), _stroke_points(ctx, b)
    if len(pa) < STROKE_MIN_PTS or len(pb) < STROKE_MIN_PTS:
        return None
    step_a = max(1, len(pa) // STROKE_SAMPLE)
    step_b = max(1, len(pb) // STROKE_SAMPLE)
    votes: dict[tuple[int, int], int] = {}
    for xa, ya in pa[::step_a]:
        for xb, yb in pb[::step_b]:
            key = (round(xa - xb), round(ya - yb))
            votes[key] = votes.get(key, 0) + 1
    (dx, dy), _n = max(votes.items(), key=lambda kv: kv[1])
    # the share is counted on the SMALLER sheet's vertices (one sheet may carry furniture the other does not)
    if len(pb) <= len(pa):
        src, dst, sign = pb, pa, 1.0
    else:
        src, dst, sign = pa, pb, -1.0
    grid: dict[tuple[int, int], list[tuple[float, float]]] = {}
    for x, y in dst:
        grid.setdefault((int(x // 4), int(y // 4)), []).append((x, y))

    def hits(points, sx, sy) -> float:
        n = 0
        for x, y in points:
            x, y = x + sx, y + sy
            gx, gy = int(x // 4), int(y // 4)
            n += any(abs(qx - x) <= STROKE_NEAR_PT and abs(qy - y) <= STROKE_NEAR_PT
                     for ix in (gx - 1, gx, gx + 1) for iy in (gy - 1, gy, gy + 1) for qx, qy in grid.get((ix, iy), ()))
        return n / max(1, len(points))

    # refine the integer shift to the best half-point one around it
    best = None
    for fx in (-0.5, 0.0, 0.5):
        for fy in (-0.5, 0.0, 0.5):
            share = hits(src, sign * (dx + fx), sign * (dy + fy))
            if best is None or share > best[0]:
                best = (share, (dx + fx, dy + fy))
    return best


def _sibling(ctx: ScaleContext, page: int, measured: dict[int, Scale]) -> Scale | None:
    """Borrow a measured scale (sources 1–3) from a sheet that overlays this one (module doc, source 5)."""
    donors = [q for q, s in sorted(measured.items()) if q != page and s.found and _same_frame(ctx, page, q)]
    if not donors:
        return None
    # the lane's alignment first: it already laid these sheets over each other
    al = ctx.alignment or {}
    tr = al.get("transform") or {}
    if page in tr:
        for g in al.get("groups") or []:
            if page in g:
                for q in donors:
                    if q in g and tr.get(q):
                        kq, kp = float(tr[q].get("k") or 1.0), float(tr[page].get("k") or 1.0)
                        return _borrowed(measured[q], q, measured[q].m_per_pt / kq * kp, "sienos sutampa", kp / kq)
    from extractor.sheet_alignment import SAME_WALLS, _best_fit
    sp = _sig(ctx, page)
    for q in donors:
        sq = _sig(ctx, q)
        if sp is None or sq is None:
            continue
        fit = _best_fit(sp, sq)
        if fit and fit[0] >= SAME_WALLS:
            k = float(fit[1]) or 1.0            # lengths on `page` × k = lengths on q
            return _borrowed(measured[q], q, measured[q].m_per_pt * k, "sienos sutampa", k, overlap=round(fit[0], 3))
    # sheets drawn without wall fills: the stroked drawing, one shift, k = 1
    for q in donors:
        if sp is not None and _sig(ctx, q) is not None:
            continue                            # both have walls and they did not coincide: another plan
        ov = _stroke_overlay(ctx, q, page)
        if ov and ov[0] >= STROKE_SAME:
            return _borrowed(measured[q], q, measured[q].m_per_pt, "brėžinio linijos sutampa", 1.0,
                             overlap=round(ov[0], 3), shift_pt=[round(ov[1][0], 1), round(ov[1][1], 1)])
    return None


def _borrowed(donor: Scale, q: int, m_per_pt: float, how: str, k: float, **details) -> Scale:
    return Scale(m_per_pt=m_per_pt, source=ScaleSource.SIBLING,
                 source_text=f"iš {q} lapo ({how}; {donor.source_text or donor.source.value})",
                 confidence=MEDIUM, page_from=q,
                 details={"donor_source": donor.source.value, "k": round(k, 5), **details})


# ── the cascade ─────────────────────────────────────────────────────────────

def measured_scale(ctx: ScaleContext, page: int) -> Scale | None:
    """Sources 1–3 only: a scale this sheet's own content measures (or a person set)."""
    page = int(page)
    if page not in ctx._measured:
        sc = _user(ctx, page) or _lines(ctx, page) or _ocr_lines(ctx, page) or _walls(ctx, page)
        ctx._measured[page] = sc if sc else blank("")
    sc = ctx._measured[page]
    return sc if sc.found else None


def _all_measured(ctx: ScaleContext, pages: Iterable[int]) -> dict[int, Scale]:
    out: dict[int, Scale] = {}
    for p in pages:
        s = measured_scale(ctx, p)
        if s:
            out[int(p)] = s
    return out


def _candidate_pages(ctx: ScaleContext) -> list[int]:
    pages = {int(d["page"]) for d in ctx.strings()}
    pages |= {int(p) for p in (ctx.user_scales or {})}
    return sorted(pages)


OCR_NOTE = "skaičiai perskaityti iš lapo vaizdo (lape nėra teksto sluoksnio) — patikrinkite mastelį"


def scale_for_page(ctx: ScaleContext, page: int, donors: Iterable[int] | None = None) -> Scale:
    """The sheet's scale with its provenance (module doc). `donors`: the sheets a sibling may lend from
    (default: every sheet that carries dimension strings or a person's line)."""
    sc = _scale_for_page(ctx, page, donors)
    if ctx._ocr.get(int(page)) and sc.found and sc.source in (ScaleSource.DIMENSION_WALLS, ScaleSource.STATED):
        sc.source_text = f"{sc.source_text}; {OCR_NOTE}" if sc.source_text else OCR_NOTE     # v4 ocr hook
        sc.details["ocr"] = True
    return sc


def _scale_for_page(ctx: ScaleContext, page: int, donors: Iterable[int] | None = None) -> Scale:
    page = int(page)
    own = measured_scale(ctx, page)
    stated = sorted(ctx.stated(page))
    if own is not None:
        if own.source == ScaleSource.DIMENSION_WALLS and stated:
            n = own.m_per_pt / PT_M
            near = min(stated, key=lambda s: abs(n - s) / s)
            if abs(n - near) / near <= STATED_SNAP:
                return Scale(m_per_pt=near * PT_M, source=ScaleSource.DIMENSION_WALLS,
                             source_text=f"{own.source_text}; sutampa su užrašytu M {_ratio(near)}",
                             confidence=HIGH, details={**own.details, "stated": stated})
            own.reason = (f"Lape užrašytas mastelis {', '.join(_ratio(s) for s in stated)}, bet matmenys atitinka "
                          f"{_ratio(n)} — lapas tikriausiai spausdintas kitu dydžiu.")
            own.details["stated"] = stated
        return own

    measured = _all_measured(ctx, donors if donors is not None else _candidate_pages(ctx))
    sib = _sibling(ctx, page, measured)
    if len(stated) == 1:
        n = stated[0]
        if _refused_in_units(ctx, page, n):
            return _stated_scale(n, HIGH, f"M {_ratio(n)} (matmenys užrašyti kitais vienetais — patvirtina mastelį)",
                                 stated=stated, units="cm")
        if sib is not None:
            m = sib.m_per_pt / PT_M
            if abs(m - n) / n <= STATED_SNAP:
                sc = _stated_scale(n, HIGH, f"M {_ratio(n)} (patvirtina {sib.page_from} lapo matmenys)",
                                   stated=stated, confirmed_by=sib.page_from, sibling=sib.details)
                sc.page_from = sib.page_from      # the measurement that confirms it was made on that sheet
                return sc
            sib.reason = (f"Lape užrašytas M {_ratio(n)}, bet to paties plano {sib.page_from} lapo matmenys atitinka "
                          f"{_ratio(m)} — rinkinys tikriausiai spausdintas kitu dydžiu.")
            sib.details["stated"] = stated
            return sib
        return _stated_scale(n, LOW, f"M {_ratio(n)} (užrašytas, nepatikrintas)", stated=stated, verified=False)
    if sib is not None:
        if stated:
            sib.details["stated"] = stated
        return sib
    if len(stated) > 1:
        return blank(f"Lape užrašyti keli masteliai ({', '.join(_ratio(s) for s in stated)}), o matmenų, "
                     f"pagal kuriuos būtų galima pasirinkti, nėra. Nubrėžkite liniją ant žinomo matmens.",
                     stated=stated)
    on = ctx.strings_on(page)
    if not on:
        return blank("Šiame lape nėra nei užrašyto mastelio, nei matmenų teksto. "
                     "Nubrėžkite liniją ant žinomo matmens, kad nustatytumėte mastelį.")
    return blank(f"Lape yra {len(on)} matmenų, bet jie nei ant matmenų linijų, nei atitinka sienas, o mastelis "
                 f"neužrašytas. Nubrėžkite liniją ant žinomo matmens, kad nustatytumėte mastelį.",
                 strings=len(on))


def scales_for_pages(ctx: ScaleContext, pages: Iterable[int], donors: Iterable[int] | None = None) -> dict[int, Scale]:
    pages = sorted({int(p) for p in pages})
    ctx.load_stated(pages)
    donor_pages = sorted(set(donors) if donors is not None else set(_candidate_pages(ctx)) | set(pages))
    return {p: scale_for_page(ctx, p, donor_pages) for p in pages}


# ── the person's line: read the string under it ─────────────────────────────

LINE_NEAR_PT = 18.0          # the string sits this close (perpendicular) to the line the person drew
LINE_MIN_PT = 10.0           # a line shorter than this is a click, not a measurement
LINE_ALONG_TOL = 0.15        # the string's centre projects inside the line, give or take this share


def string_under_line(dims_on_page: Sequence[dict], p1: Sequence[float], p2: Sequence[float]) -> dict | None:
    """The dimension string the person drew the line over: written along it (same orientation), its centre within
    LINE_NEAR_PT of the line and inside its length. Nearest wins. Display-frame points, as the strings."""
    (x1, y1), (x2, y2) = (float(p1[0]), float(p1[1])), (float(p2[0]), float(p2[1]))
    L = math.hypot(x2 - x1, y2 - y1)
    if L < LINE_MIN_PT:
        return None
    ux, uy = (x2 - x1) / L, (y2 - y1) / L
    horizontal = abs(ux) >= abs(uy)
    best = None
    for d in dims_on_page:
        try:
            bx0, btop, bx1, bbottom = (float(v) for v in d["bbox"])
        except (KeyError, TypeError, ValueError):
            continue
        o = d.get("orientation")
        slanted = 0.2 < abs(ux) < 0.98
        if o in ("h", "v") and not slanted and (o == "h") != horizontal:
            continue
        cx, cy = (bx0 + bx1) / 2, (btop + bbottom) / 2
        t = (cx - x1) * ux + (cy - y1) * uy
        if not (-LINE_ALONG_TOL * L <= t <= (1 + LINE_ALONG_TOL) * L):
            continue
        dist = abs((cx - x1) * uy - (cy - y1) * ux)
        if dist > LINE_NEAR_PT:
            continue
        key = (dist, abs(t - L / 2))
        if best is None or key < best[0]:
            best = (key, d)
    return best[1] if best else None


def scale_from_line(dims_on_page: Sequence[dict], p1: Sequence[float], p2: Sequence[float]) -> tuple[Scale | None, str | None]:
    """(Scale, None) or (None, reason) for a line a person drew over a dimension string."""
    L = math.hypot(float(p2[0]) - float(p1[0]), float(p2[1]) - float(p1[1]))
    if L < LINE_MIN_PT:
        return None, "Linija per trumpa — nubrėžkite ją per visą matmens ilgį."
    d = string_under_line(dims_on_page, p1, p2)
    if d is None:
        return None, ("Po linija neradau matmens teksto (pvz. „4280“). Nubrėžkite liniją išilgai užrašyto matmens, "
                      "tarp jo kraštinių brūkšnelių.")
    m = float(d["value_m"]) / L
    if not (5 * PT_M <= m <= 1000 * PT_M):
        return None, (f"Matmuo „{d['text']}“ ir linijos ilgis duoda mastelį {_ratio(m / PT_M)} — toks plane negalimas. "
                      f"Patikrinkite, ar linija nubrėžta per visą matmenį.")
    return Scale(m_per_pt=m, source=ScaleSource.USER_LINE, source_text=str(d["text"]), confidence=HIGH,
                 details={"value_m": float(d["value_m"]), "length_pt": round(L, 2),
                          "string_bbox": d.get("bbox")}), None


# ── what the geometry lane asks (extractor/geometry_lane.py, the „v4 scale hook") ──

def line_scales(dims: Iterable[dict] | None) -> dict[int, float]:
    """{page: m_per_pt} from the strings on their hairlines (source 2) — what plan_dimensions put on them, first per
    page. The lane and the raster outline lane (wall_outline) both start from this."""
    out: dict[int, float] = {}
    for d in dims or []:
        try:
            s = float(d.get("scale_m_per_pt") or 0)
        except (TypeError, ValueError):
            continue
        if s > 0:
            out.setdefault(int(d["page"]), s)
    return out


def user_scales_for_project(project_id: str | None) -> dict[int, dict]:
    """{page: row} of the person's „Mastelis" lines in force (db.page_scales). Reads the DB only when the web app has
    already opened it (`db` imported): the eval, the scripts and the tests never create a database by asking."""
    import sys
    if not project_id or "db" not in sys.modules:
        return {}
    try:
        return sys.modules["db"].get_page_scales(str(project_id))
    except Exception:  # noqa: BLE001 — a missing table or a locked file is „no person's scale", never a failure
        log.exception("page_scales unreadable for %s", project_id)
        return {}


def lane_fill(pdf_bytes: bytes, dims: Sequence[dict], scale: dict[int, float], pages: Iterable[int],
              alignment: dict | None = None, user_scales: dict[int, dict] | None = None) -> dict[int, Scale]:
    """The lane's sheets that its own dimension lines and wall alignment left without a scale get this module's
    (sources 3, 4, 5 — `scale` is filled IN PLACE for those only: a sheet the lane already scaled keeps its value).
    A person's line (source 1) is applied by the lane BEFORE its alignment, so siblings borrow it; here it is only
    recorded. Returns the provenance of every sheet in `scale` afterwards and of every asked sheet left blank."""
    ctx = ScaleContext(pdf_bytes, dims=list(dims), user_scales=user_scales or {}, alignment=alignment)
    wanted = sorted({int(p) for p in pages} | set(scale))
    ctx.load_stated(wanted)
    donors = sorted(set(_candidate_pages(ctx)) | set(wanted))
    out: dict[int, Scale] = {}
    for p in wanted:
        sc = scale_for_page(ctx, p, donors)
        if p in scale:
            if not (sc.found and abs(sc.m_per_pt / scale[p] - 1) <= 1e-6):
                # the lane's own reading stands; say where it came from (its lines, or a sheet laid over this one)
                sc = _user(ctx, p) or _lines(ctx, p) or _sibling(ctx, p, _all_measured(ctx, donors)) or Scale(
                    m_per_pt=scale[p], source=ScaleSource.SIBLING, source_text="iš to paties plano lapo", confidence=MEDIUM)
                sc.m_per_pt = scale[p]
            out[p] = sc
            continue
        if sc.found:
            scale[p] = sc.m_per_pt
        out[p] = sc
    return out


def lane_record(sc: Scale) -> dict:
    """The keys a sheet's scale adds to `_meta.geometrija.masteliai[page]` beside m_per_pt / mastelis (LT keys, as the
    rest of the lane's meta)."""
    rec = {"saltinis": sc.source.value, "patikimumas": sc.confidence}
    if sc.source_text:
        rec["tekstas"] = sc.source_text
    if sc.page_from:
        rec["is_lapo"] = int(sc.page_from)
    if sc.reason:
        rec["pastaba"] = sc.reason
    return rec
