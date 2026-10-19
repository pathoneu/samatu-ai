"""POST /api/projects/{project_id}/export-overlay-pdf — the drawing's sheets with Pathon's marks on them and a
legend per sheet, as one PDF (togal-v2 W8; Togal's „export with overlays and legend",
docs/superpowers/research/2026-10-16-togal-pipeline-analysis.md §8).

Each requested sheet is rendered with PDFium (the /Rotate-applied page, as the viewer shows it) and laid into a
reportlab page of the same displayed size; the marks are drawn over it as vectors, so labels stay sharp and
searchable:
  * room outlines (`polygon_pct`, display-frame page fractions — plotted raw, as PageOverlayHost does) with the
    room number and its area; an outline a person drew or fixed is solid, one the program proposed is dashed
    and the legend says so;
  * measurements (`project.measurements`, kind distance / perimeter / area) with their length or area at the
    sheet's scale in force, mapped to the display exactly like lib/viewerEngine/embedPdfAdapter.js
    (`display_fraction`, the backend twin of pageRotation.rotatePctPoint). The viewer stores a point as
    toPdf(): an unrotated-frame fraction × EmbedPDF's `page.size`, and that size is the UNROTATED page —
    measured 2026-10-16 in the browser on this build: 842 × 1191 at rotation 3 on a /Rotate 270 A3 sheet,
    400 × 200 at rotation 1 on a 400 × 200 /Rotate 90 sheet, equal to `page.boxes.media`. pypdfium2's
    `page.get_size()` is the DISPLAYED size (swapped on /Rotate 90/270), so the divisor here is that size
    swapped back (`Wu`, `Hu`); dividing by `get_size()` as reported placed every mark on a rotated sheet
    stretched along one axis (lengths were right — they come from the points and the scale);
  * count marks (kind count) in their type's colour and shape, tallied in the legend;
  * optionally the wall solid the program read (api/page_geometry.wall_solid_rings).

Nothing is computed that the viewer does not compute: a measurement's value is its points × the sheet's scale,
the scale is the one the browser sends (the viewer's effective scale) or else the stored calibration / the
lane's reading. No AI call, nothing saved. `dry_run` returns the first sheet as a PNG for the export dialog.
"""
from __future__ import annotations

import io
import logging
import math
from datetime import date
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from api.free_reread import NO_PDF, _project_for

log = logging.getLogger("samatu.export_overlay_pdf")

router = APIRouter(prefix="/api/projects", tags=["export-overlay-pdf"])

METERS_PER_POINT_AT_1_TO_1 = 0.0254 / 72
MAX_PAGES = 60
MAX_SIDE_PX = 4200              # an A0 sheet at 110 dpi is ~5100 px — cap the raster, not the vectors
PREVIEW_SIDE_PX = 1400

INK = (0.10, 0.11, 0.11)        # --foreground #191C1B
MUTED = (0.45, 0.47, 0.48)      # --muted-foreground #73787B
CONFIRMED = (0.25, 0.40, 0.36)  # --accent-2 #3F665C evergreen: an outline a person drew or fixed
PROPOSED = (0.61, 0.42, 0.03)   # --conf-med amber: an outline the program proposed
WALLS = (0.85, 0.47, 0.13)      # the viewer's walls layer (orange)
USER_SOURCES = {"corrected", "manual"}

FONT = "PathonSans"
FONT_BOLD = "PathonSansBold"
_FONT_DIR = Path(__file__).resolve().parents[1] / "assets" / "fonts"


# ── body ────────────────────────────────────────────────────────────────────────────────────────────────

class Layers(BaseModel):
    measurements: bool = True
    counts: bool = True
    outlines: bool = True
    walls: bool = False
    # „Užrašai" (W5-B B4): room numbers with areas, measurement values — the viewer's „Rodinys" label switch
    labels: bool = True


class PageScale(BaseModel):
    metersPerPointX: float = Field(gt=0)
    metersPerPointY: float | None = Field(default=None, gt=0)
    source: str | None = Field(default=None, max_length=32)


class OverlayBody(BaseModel):
    pages: list[int] | Literal["all"] = "all"
    layers: Layers = Field(default_factory=Layers)
    # The viewer's effective per-page scale (TakeoffViewer: auto ← lane ← his calibration). Optional: without
    # it the stored calibration and the lane's reading are used.
    scales: dict[str, PageScale] = Field(default_factory=dict)
    dpi: int = Field(default=110, ge=50, le=200)
    dry_run: bool = False


def _owned_project(request: Request, project_id: str) -> dict:
    """Ownership before the body is validated (tests/test_route_ownership_policy.py)."""
    return _project_for(request, project_id)


# ── geometry: the frontend's frames, mirrored ───────────────────────────────────────────────────────────

def normalize_rotation(value: Any) -> int:
    """lib/viewerEngine/pageRotation.normalizeRotation: degrees or the /Rotate enum (1, 2, 3) → 0/90/180/270."""
    try:
        n = int(value or 0)
    except (TypeError, ValueError):
        return 0
    return {1: 90, 2: 180, 3: 270}.get(n, n % 360 if n % 90 == 0 else 0)


def rotate_pct_point(x: float, y: float, rot: int) -> tuple[float, float]:
    """lib/viewerEngine/pageRotation.rotatePctPoint: rotate the image clockwise by /Rotate degrees."""
    r = normalize_rotation(rot)
    if r == 90:
        return 1 - y, x
    if r == 180:
        return 1 - x, 1 - y
    if r == 270:
        return y, 1 - x
    return x, y


def display_fraction(pt: dict, size_w: float, size_h: float, rot: int) -> tuple[float, float] | None:
    """A stored measurement point → display-frame page fraction — embedPdfAdapter.toViewport divided by the
    rendered size. `size_w/h`: the page size the viewer divided by (PDFium's page size, see the docstring)."""
    mediabox_w, mediabox_h = size_w, size_h
    try:
        x, y = float(pt["x"]), float(pt["y"])
    except (KeyError, TypeError, ValueError):
        return None
    if mediabox_w <= 0 or mediabox_h <= 0:
        return None
    return rotate_pct_point(x / mediabox_w, y / mediabox_h, rot)


def _pct_pair(p: Any) -> tuple[float, float] | None:
    try:
        if isinstance(p, dict):
            return float(p.get("x_pct", p.get("x"))), float(p.get("y_pct", p.get("y")))
        return float(p[0]), float(p[1])
    except (TypeError, ValueError, IndexError, KeyError):
        return None


# ── scale and values (lib/measureGeometry.js) ───────────────────────────────────────────────────────────

def _ratio_label(mpp: float) -> int:
    return int(round(mpp / METERS_PER_POINT_AT_1_TO_1))


def scale_in_force(project: dict, page: int, client: dict[str, PageScale]) -> dict | None:
    """{mx, my, label} — metres per mediabox point on the sheet and how the legend names it; None when the
    sheet has no scale (measurements are then drawn without numbers and the legend says so)."""
    sources = {"user": "kalibruota jūsų", "standard": "pasirinkta jūsų", "auto": "apytiksliai, iš patalpų plotų",
               "lane": "iš brėžinio", "plan": "iš brėžinio", "none": ""}
    s = client.get(str(page))
    if s is not None:
        mx = float(s.metersPerPointX)
        my = float(s.metersPerPointY or mx)
        src = sources.get(str(s.source or "user"), "iš peržiūros")
        return {"mx": mx, "my": my, "label": f"1:{_ratio_label(mx)} ({src})" if src else f"1:{_ratio_label(mx)}"}
    stored = (project.get("pageScalesDurable") or {}).get(str(page)) or {}
    try:
        mx = float(stored.get("metersPerPointX") or 0)
    except (TypeError, ValueError):
        mx = 0.0
    if mx > 0 and stored.get("calibrated", True):
        my = float(stored.get("metersPerPointY") or mx)
        src = sources.get(str(stored.get("source") or "user"), "kalibruota jūsų")
        return {"mx": mx, "my": my, "label": f"1:{_ratio_label(mx)} ({src})"}
    meta = project.get("_meta") if isinstance(project.get("_meta"), dict) else {}
    geo = ((meta.get("geometrija") or {}).get("masteliai") or {}).get(str(page)) or {}
    pairs = (meta.get("plan_dimension_lane") or {}).get("mastelis") or {}
    ratio = None
    try:
        if pairs.get(str(page)):
            ratio = float(pairs[str(page)])
        elif geo.get("m_per_pt"):
            mpp = float(geo["m_per_pt"])
            return {"mx": mpp, "my": mpp, "label": f"1:{int(geo.get('mastelis') or _ratio_label(mpp))} (iš brėžinio)"}
        elif geo.get("mastelis"):
            ratio = float(geo["mastelis"])
    except (TypeError, ValueError):
        ratio = None
    if ratio and ratio > 0:
        mpp = ratio * METERS_PER_POINT_AT_1_TO_1
        return {"mx": mpp, "my": mpp, "label": f"1:{int(round(ratio))} (iš brėžinio)"}
    return None


def path_length_m(points: list[dict], scale: dict, closed: bool = False) -> float:
    pts = [(float(p["x"]), float(p["y"])) for p in points if isinstance(p, dict) and "x" in p and "y" in p]
    n = len(pts)
    if n < 2:
        return 0.0
    total = 0.0
    last = n if closed else n - 1
    for i in range(last):
        (ax, ay), (bx, by) = pts[i], pts[(i + 1) % n]
        total += math.hypot((bx - ax) * scale["mx"], (by - ay) * scale["my"])
    return total


def area_m2(points: list[dict], holes: list[list[dict]] | None, scale: dict) -> float:
    def shoelace(ring):
        pts = [(float(p["x"]) * scale["mx"], float(p["y"]) * scale["my"]) for p in ring
               if isinstance(p, dict) and "x" in p and "y" in p]
        if len(pts) < 3:
            return 0.0
        return abs(sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1]
                       for i in range(len(pts)))) / 2
    return max(0.0, shoelace(points) - sum(shoelace(h) for h in (holes or []) if isinstance(h, list)))


def lt_number(value: float, decimals: int = 2) -> str:
    """„1 234,50" — LT decimal comma, thin-free thousands (lib/measureGeometry.formatNumberLT)."""
    s = f"{value:,.{decimals}f}"
    return s.replace(",", " ").replace(".", ",")


# ── rendering ───────────────────────────────────────────────────────────────────────────────────────────

def _register_fonts() -> None:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    if FONT in pdfmetrics.getRegisteredFontNames():
        return
    pdfmetrics.registerFont(TTFont(FONT, str(_FONT_DIR / "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont(FONT_BOLD, str(_FONT_DIR / "DejaVuSans-Bold.ttf")))


def _hex_rgb(value: Any, fallback=(0.16, 0.44, 0.71)) -> tuple[float, float, float]:
    s = str(value or "").strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    try:
        return tuple(int(s[i:i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]
    except ValueError:
        return fallback


def render_sheets(pdf_bytes: bytes, pages: list[int], dpi: int, side_cap: int) -> list[dict]:
    """[{page, image (PIL), Wd, Hd, Wm, Hm, Ws, Hs, Wu, Hu, rotation}] — the displayed page size in points,
    the unrotated (cropbox) size, pypdfium2's page size (displayed), that size unrotated (the viewer's
    `page.size`, the measurements' divisor) and the raster. Under the process-wide PDFium lock."""
    import pypdfium2 as pdfium

    from extractor.pdfium_guard import PDFIUM_LOCK
    out = []
    with PDFIUM_LOCK:
        doc = pdfium.PdfDocument(pdf_bytes)
        try:
            n = len(doc)
            for nr in pages:
                if not (1 <= nr <= n):
                    continue
                page = doc[nr - 1]
                try:
                    rot = normalize_rotation(page.get_rotation())
                    x0, y0, x1, y1 = (float(v) for v in page.get_cropbox())
                    Wm, Hm = abs(x1 - x0), abs(y1 - y0)
                    Wd, Hd = (Hm, Wm) if rot in (90, 270) else (Wm, Hm)
                    Ws, Hs = (float(v) for v in page.get_size())
                    Wu, Hu = (Hs, Ws) if rot in (90, 270) else (Ws, Hs)
                    scale = min(dpi / 72.0, side_cap / max(Wd, Hd))
                    image = page.render(scale=scale, may_draw_forms=True).to_pil().convert("RGB")
                    out.append({"page": nr, "image": image, "Wd": Wd, "Hd": Hd, "Wm": Wm, "Hm": Hm, "Ws": Ws, "Hs": Hs,
                                "Wu": Wu, "Hu": Hu, "rotation": rot})
                finally:
                    page.close()
        finally:
            doc.close()
    return out


def _rooms_on(project: dict, page: int) -> list[dict]:
    rooms = project.get("v8_rooms") or project.get("patalpos") or []
    out = []
    for r in rooms:
        if not isinstance(r, dict):
            continue
        try:
            if int(r.get("puslapio_nr") or 0) != page:
                continue
        except (TypeError, ValueError):
            continue
        ring = [p for p in (_pct_pair(q) for q in (r.get("polygon_pct") or [])) if p]
        if len(ring) >= 3:
            out.append({**r, "_ring": ring})
    return out


def _measurements_on(project: dict, page: int) -> list[dict]:
    out = []
    for m in project.get("measurements") or []:
        if not isinstance(m, dict):
            continue
        try:
            if int(m.get("page") or 0) != page:
                continue
        except (TypeError, ValueError):
            continue
        out.append(m)
    return out


def _count_types(project: dict) -> dict[str, dict]:
    types = {}
    for t in project.get("countTypes") or []:
        if isinstance(t, dict) and t.get("id"):
            types[str(t["id"])] = t
    return types


def _sheet_name(project: dict, page: int) -> str:
    for s in project.get("puslapiai") or []:
        try:
            if isinstance(s, dict) and int(s.get("nr")) == page:
                return str(s.get("pavadinimas") or "").strip()
        except (TypeError, ValueError):
            continue
    return ""


def draw_sheet(c, sheet: dict, project: dict, layers: Layers, scale: dict | None, walls: list | None,
               today: str) -> None:
    """One reportlab page: the raster, the marks, the legend."""
    from reportlab.lib.utils import ImageReader

    Wd, Hd, rot = sheet["Wd"], sheet["Hd"], sheet["rotation"]
    page = sheet["page"]
    c.setPageSize((Wd, Hd))
    buf = io.BytesIO()
    sheet["image"].save(buf, format="JPEG", quality=82, optimize=True)
    buf.seek(0)
    c.drawImage(ImageReader(buf), 0, 0, width=Wd, height=Hd)

    def P(fx: float, fy: float) -> tuple[float, float]:     # display fraction (top-left) → reportlab (bottom-left)
        return fx * Wd, Hd - fy * Hd

    unit = max(Wd, Hd) / 1190.0                              # 1 at A3 landscape: line widths and type follow the sheet
    legend: list[tuple[str, tuple, str, str]] = []           # (kind, colour, text, style)

    def polygon(ring, stroke, fill=None, width=1.0, dash=None, fill_alpha=0.12):
        path = c.beginPath()
        x, y = P(*ring[0])
        path.moveTo(x, y)
        for fx, fy in ring[1:]:
            path.lineTo(*P(fx, fy))
        path.close()
        c.saveState()
        c.setStrokeColorRGB(*stroke)
        c.setLineWidth(width * unit)
        if dash:
            c.setDash([d * unit for d in dash])
        if fill:
            c.setFillColorRGB(*fill)
            c.setFillAlpha(fill_alpha)
        c.drawPath(path, stroke=1, fill=1 if fill else 0)
        c.restoreState()

    def label(text, x, y, size=7.0, colour=INK, bold=False, anchor="middle"):
        size *= unit
        font = FONT_BOLD if bold else FONT
        from reportlab.pdfbase.pdfmetrics import stringWidth
        w = stringWidth(text, font, size)
        lx = x - w / 2 if anchor == "middle" else x
        c.saveState()
        c.setFillColorRGB(1, 1, 1)
        c.setFillAlpha(0.85)
        c.rect(lx - 1.5 * unit, y - 1.8 * unit, w + 3 * unit, size + 2.6 * unit, stroke=0, fill=1)
        c.setFillAlpha(1)
        c.setFillColorRGB(*colour)
        c.setFont(font, size)
        c.drawString(lx, y, text)
        c.restoreState()

    # walls
    if layers.walls and walls:
        c.saveState()
        c.setFillColorRGB(*WALLS)
        c.setFillAlpha(0.35)
        path = c.beginPath()
        for ring in walls:
            pts = [p for p in (_pct_pair(q) for q in ring) if p]
            if len(pts) < 3:
                continue
            path.moveTo(*P(*pts[0]))
            for q in pts[1:]:
                path.lineTo(*P(*q))
            path.close()
        c.drawPath(path, stroke=0, fill=1, fillMode=0)       # even-odd: holes stay holes
        c.restoreState()
        legend.append(("fill", WALLS, "Sienos, kurias programa perskaitė iš brėžinio linijų", ""))

    # room outlines
    if layers.outlines:
        rooms = _rooms_on(project, page)
        n_user = n_ai = 0
        for r in rooms:
            mine = str(r.get("polygon_source") or "") in USER_SOURCES
            n_user += mine
            n_ai += not mine
            colour = CONFIRMED if mine else PROPOSED
            polygon(r["_ring"], colour, fill=colour, width=1.4, dash=None if mine else (4, 2.5))
            cx = sum(p[0] for p in r["_ring"]) / len(r["_ring"])
            cy = sum(p[1] for p in r["_ring"]) / len(r["_ring"])
            x, y = P(cx, cy)
            area = r.get("plotas_m2")
            text = str(r.get("nr") or "")
            try:
                if area not in (None, ""):
                    text += f" · {lt_number(float(area))} m²"
            except (TypeError, ValueError):
                pass
            if layers.labels:
                label(text, x, y, size=7.5, colour=colour, bold=True)
        if n_user:
            legend.append(("line", CONFIRMED, f"Patalpos kontūras — nubrėžtas ar pataisytas jūsų ({n_user})", "solid"))
        if n_ai:
            legend.append(("line", PROPOSED, f"Patalpos kontūras — pasiūlytas programos, patikrinkite ({n_ai})", "dash"))

    measurements = _measurements_on(project, page)
    Ws, Hs = sheet["Wu"], sheet["Hu"]

    def disp(points):
        return [q for q in (display_fraction(p, Ws, Hs, rot) for p in points or []) if q]

    if layers.measurements:
        shown = 0
        for m in measurements:
            kind = m.get("kind")
            if kind not in ("distance", "perimeter", "area"):
                continue
            pts = disp(m.get("points"))
            if len(pts) < 2:
                continue
            colour = _hex_rgb(m.get("color"))
            shown += 1
            if kind == "area" and len(pts) >= 3:
                polygon(pts, colour, fill=colour, width=1.2, fill_alpha=0.16)
                value = f"{lt_number(area_m2(m['points'], m.get('holes'), scale))} m²" if scale else "nekalibruota"
                anchor = (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
            else:
                c.saveState()
                c.setStrokeColorRGB(*colour)
                c.setLineWidth(1.4 * unit)
                path = c.beginPath()
                path.moveTo(*P(*pts[0]))
                for q in pts[1:]:
                    path.lineTo(*P(*q))
                c.drawPath(path, stroke=1, fill=0)
                for q in (pts[0], pts[-1]):
                    x, y = P(*q)
                    c.setFillColorRGB(*colour)
                    c.circle(x, y, 1.6 * unit, stroke=0, fill=1)
                c.restoreState()
                value = (f"{lt_number(path_length_m(m['points'], scale))} m"
                         if scale else "nekalibruota")
                anchor = pts[len(pts) // 2] if len(pts) > 2 else ((pts[0][0] + pts[1][0]) / 2, (pts[0][1] + pts[1][1]) / 2)
            name = str(m.get("classification") or "").strip()
            if layers.labels:
                label(f"{name}: {value}" if name else value, *P(*anchor), size=6.5, colour=colour)
        if shown:
            legend.append(("line", (0.16, 0.44, 0.71), f"Jūsų matavimai — ilgis arba plotas pagal lapo mastelį ({shown})",
                           "solid"))
        # „Pastaba" pins (Pathon v3 W5-C, C11): a small square with the note's number and its text beside it —
        # P1, P2 … per sheet, the numbers the viewer and the Matavimai list show
        notes = 0
        for m in measurements:
            if m.get("kind") != "note":
                continue
            pts = disp(m.get("points"))
            text = " ".join(str(m.get("text") or "").split())
            if not pts or not text:
                continue
            notes += 1
            x, y = P(*pts[0])
            rr = 3.0 * unit
            c.saveState()
            c.setFillColorRGB(1, 1, 1)
            c.setStrokeColorRGB(*INK)
            c.setLineWidth(0.8 * unit)
            c.rect(x - rr, y - rr, 2 * rr, 2 * rr, stroke=1, fill=1)
            c.restoreState()
            short = text if len(text) <= 70 else text[:69] + "…"
            label(f"P{notes} {short}", x + rr + 2 * unit, y - 2 * unit, size=6.5, colour=INK, anchor="start")
        if notes:
            legend.append(("dot", INK, f"Pastabos — jūsų užrašai brėžinyje ({notes})", ""))

    if layers.counts:
        types = _count_types(project)
        tally: dict[str, int] = {}
        for m in measurements:
            if m.get("kind") != "count":
                continue
            pts = disp(m.get("points"))
            if not pts:
                continue
            tid = str(m.get("typeId") or "")
            t = types.get(tid) or {}
            colour = _hex_rgb(t.get("color") or m.get("color"))
            shape = str(t.get("shape") or "circle")
            x, y = P(*pts[0])
            rr = 3.2 * unit
            c.saveState()
            c.setFillColorRGB(*colour)
            c.setStrokeColorRGB(1, 1, 1)
            c.setLineWidth(0.6 * unit)
            if shape == "square":
                c.rect(x - rr, y - rr, 2 * rr, 2 * rr, stroke=1, fill=1)
            elif shape == "diamond":
                path = c.beginPath()
                path.moveTo(x, y + rr * 1.2)
                path.lineTo(x + rr * 1.2, y)
                path.lineTo(x, y - rr * 1.2)
                path.lineTo(x - rr * 1.2, y)
                path.close()
                c.drawPath(path, stroke=1, fill=1)
            else:
                c.circle(x, y, rr, stroke=1, fill=1)
            c.restoreState()
            tally[tid] = tally.get(tid, 0) + 1
        for tid, n in tally.items():
            t = types.get(tid) or {}
            src = " (rasta programos)" if any(m.get("typeId") == tid and str(m.get("source") or "user") != "user"
                                              for m in measurements if m.get("kind") == "count") else ""
            legend.append(("dot", _hex_rgb(t.get("color")), f"{t.get('label') or tid}: {n} vnt.{src}", ""))

    _draw_legend(c, Wd, Hd, unit, project, page, scale, legend, today)


def _draw_legend(c, Wd, Hd, unit, project, page, scale, items, today) -> None:
    from reportlab.pdfbase.pdfmetrics import stringWidth

    name = str(project.get("name") or project.get("pavadinimas") or "Projektas").strip()
    sheet = _sheet_name(project, page)
    head = [
        (FONT_BOLD, 8.5, f"Pathon · {name}"),
        (FONT, 7.0, f"Lapas {page}" + (f" — {sheet}" if sheet else "") + f" · {today}"),
        (FONT, 7.0, f"Mastelis: {scale['label']}" if scale else "Mastelis nenustatytas — matavimai be skaičių"),
    ]
    foot = (FONT, 6.2, "Brūkšniniai kontūrai pasiūlyti programos (AI) — žmogus jų dar netikrino.")
    if not items:
        items = [("none", MUTED, "Šiame lape žymėjimų nėra", "")]
    pad, swatch, line_h = 6 * unit, 14 * unit, 10.5 * unit
    rows = [(f, s * unit, t) for f, s, t in head]
    text_w = max([stringWidth(t, f, s) for f, s, t in rows]
                 + [stringWidth(t, FONT, 7.0 * unit) + swatch + 4 * unit for _, _, t, _ in items]
                 + [stringWidth(foot[2], foot[0], foot[1] * unit)])
    box_w = text_w + 2 * pad
    box_h = pad * 2 + line_h * (len(rows) + len(items) + 1) + 3 * unit
    # top-right: drawings keep their title block bottom-right, and the legend must not cover it
    x0, y0 = Wd - box_w - 10 * unit, Hd - box_h - 10 * unit
    c.saveState()
    c.setFillColorRGB(1, 1, 1)
    c.setStrokeColorRGB(*INK)
    c.setLineWidth(0.6 * unit)
    c.rect(x0, y0, box_w, box_h, stroke=1, fill=1)
    y = y0 + box_h - pad - 8 * unit
    for f, s, t in rows:
        c.setFillColorRGB(*INK)
        c.setFont(f, s)
        c.drawString(x0 + pad, y, t)
        y -= line_h
    y -= 3 * unit
    for kind, colour, text, style in items:
        sx, sy = x0 + pad, y + 2.4 * unit
        c.setStrokeColorRGB(*colour)
        c.setFillColorRGB(*colour)
        if kind == "line":
            c.setLineWidth(1.4 * unit)
            c.setDash([4 * unit, 2.5 * unit] if style == "dash" else [])
            c.line(sx, sy, sx + swatch - 3 * unit, sy)
            c.setDash([])
        elif kind == "fill":
            c.setFillAlpha(0.45)
            c.rect(sx, sy - 3 * unit, swatch - 3 * unit, 6 * unit, stroke=0, fill=1)
            c.setFillAlpha(1)
        elif kind == "dot":
            c.circle(sx + 4 * unit, sy, 3 * unit, stroke=0, fill=1)
        c.setFillColorRGB(*INK)
        c.setFont(FONT, 7.0 * unit)
        c.drawString(sx + swatch + 1 * unit, y, text)
        y -= line_h
    c.setFillColorRGB(*MUTED)
    c.setFont(foot[0], foot[1] * unit)
    c.drawString(x0 + pad, y, foot[2])
    c.restoreState()


def build_overlay_pdf(pdf_bytes: bytes, project: dict, body: OverlayBody, *, side_cap: int = MAX_SIDE_PX,
                      walls_for=None) -> bytes:
    from reportlab.pdfgen import canvas as rl_canvas

    _register_fonts()
    pages = _requested_pages(pdf_bytes, body)
    if body.dry_run:
        pages = pages[:1]
    sheets = render_sheets(pdf_bytes, pages, body.dpi, side_cap)
    if not sheets:
        raise HTTPException(status_code=400, detail="Tokių lapų brėžinyje nėra")
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pageCompression=1)
    c.setTitle(f"Pathon — {project.get('name') or 'brėžiniai su žymėjimais'}")
    c.setAuthor("Pathon")
    today = date.today().strftime("%Y-%m-%d")
    for sheet in sheets:
        scale = scale_in_force(project, sheet["page"], body.scales)
        walls = None
        if body.layers.walls:
            walls = (walls_for or _walls)(pdf_bytes, sheet["page"])
        draw_sheet(c, sheet, project, body.layers, scale, walls, today)
        c.showPage()
    c.save()
    return buf.getvalue()


def _walls(pdf_bytes: bytes, page: int) -> list:
    from api.page_geometry import wall_solid_rings
    try:
        _W, _H, rings, _trunc = wall_solid_rings(pdf_bytes, page)
    except HTTPException:
        return []
    return rings


def _page_count(pdf_bytes: bytes) -> int:
    import pypdfium2 as pdfium

    from extractor.pdfium_guard import PDFIUM_LOCK
    with PDFIUM_LOCK:
        doc = pdfium.PdfDocument(pdf_bytes)
        try:
            return len(doc)
        finally:
            doc.close()


def _requested_pages(pdf_bytes: bytes, body: OverlayBody) -> list[int]:
    n = _page_count(pdf_bytes)
    if body.pages == "all":
        return list(range(1, min(n, MAX_PAGES) + 1))
    wanted = sorted({int(p) for p in body.pages if 1 <= int(p) <= n})
    if not wanted:
        raise HTTPException(status_code=400, detail="Pasirinkite bent vieną brėžinio lapą")
    return wanted[:MAX_PAGES]


def first_page_png(pdf_out: bytes, side_px: int = PREVIEW_SIDE_PX) -> bytes:
    """The overlay PDF's first page as a PNG — the export dialog's preview is the file itself."""
    import pypdfium2 as pdfium

    from extractor.pdfium_guard import PDFIUM_LOCK
    with PDFIUM_LOCK:
        doc = pdfium.PdfDocument(pdf_out)
        try:
            page = doc[0]
            try:
                w, h = (float(v) for v in page.get_size())
                image = page.render(scale=side_px / max(w, h)).to_pil().convert("RGB")
            finally:
                page.close()
        finally:
            doc.close()
    buf = io.BytesIO()
    image.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


# Plain `def`: PDFium + reportlab are blocking CPU — FastAPI runs it in the threadpool.
@router.post("/{project_id}/export-overlay-pdf")
def api_export_overlay_pdf(request: Request, project_id: str, body: OverlayBody,
                           project: dict = Depends(_owned_project)):
    from main import _check_rate_limit, _client_key
    _check_rate_limit(_client_key(request), "export_overlay_pdf")

    from storage import get_storage, pdf_key
    try:
        pdf_bytes = get_storage().get(pdf_key(project_id))
    except Exception as exc:  # noqa: BLE001 — an R2 hiccup is a 502, not a 500
        log.warning("overlay-pdf fetch failed for %s: %r", project_id, exc)
        raise HTTPException(status_code=502, detail="Nepavyko pasiekti brėžinio saugyklos")
    if not pdf_bytes:
        raise HTTPException(status_code=404, detail=NO_PDF)
    try:
        out = build_overlay_pdf(pdf_bytes, project, body,
                                side_cap=PREVIEW_SIDE_PX if body.dry_run else MAX_SIDE_PX)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 — a broken sheet must not be a bare 500
        log.exception("overlay-pdf build failed for %s", project_id)
        raise HTTPException(status_code=500, detail="Nepavyko sudaryti PDF su žymėjimais") from exc
    if body.dry_run:
        return Response(first_page_png(out), media_type="image/png",
                        headers={"Cache-Control": "no-store"})
    return Response(out, media_type="application/pdf",
                    headers={"Content-Disposition": 'attachment; filename="brezinys-su-zymejimais.pdf"',
                             "Cache-Control": "no-store"})
