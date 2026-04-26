"""
Vector polygon detection iš PDF lines/rects.

Skirtumai nuo V8 PoC:
1. Endpoint SNAP — sienos kampai su ±3px tolerancija
2. Filtravimas pagal MIN PLOTĄ (su mastelio konversija)
3. Sienų aptikimas iš storesnių rects (ne tik lines)
4. Hole filling — vidiniai polygons (kambariai) atskiriami nuo išorinių
5. Label matching su NEAREST search (artimiausias text iki centroidui),
   ne tik viduje polygon'o
"""
from __future__ import annotations
import io
import re
from typing import Any


# Mastelio default'as: 1 PDF unit = 0.353mm (1/72 inch)
# Su brėžinio masteliu 1:50 — 1 PDF unit = 17.6mm = 0.0176m
DEFAULT_PDF_UNIT_TO_M = 0.353 / 1000  # tik PDF unit'as, be brėžinio mastelio


def build_room_polygons(
    pdf_bytes: bytes,
    page_nr: int,
    drawing_scale: int = 50,        # 1:50 default (tipinis LT)
    snap_tolerance_px: float = 3.0,
    min_room_area_m2: float = 1.5,  # mažiausia leistina patalpa
    max_segments: int = 3000,       # skip page jei daugiau (per lėta polygonize)
) -> dict:
    """Iš PDF puslapio gauname kambarių polygons su realiom dimensijom.

    Args:
        pdf_bytes: PDF bytes
        page_nr: 1-indexed
        drawing_scale: brėžinio mastelis (1:N) — default 50 (LT typical)
        snap_tolerance_px: kampų snap tolerance (3px = ~1mm at 1:50)
        min_room_area_m2: filtras per minimumą (1.5 m² = WC dydis)

    Returns:
        {
          "rooms": [
            {
              "polygon_id": 0,
              "area_m2": 24.5,
              "perimeter_m": 21.2,
              "centroid_pdf": [x, y],
              "centroid_pct": [x_pct, y_pct],
              "bbox_pct": {x, y, w, h},
              "polygon_pdf": [[x1,y1], [x2,y2], ...],
              "nearby_texts": [...]   # tekstai ARTIMI centroidui (iki 100px)
            }
          ],
          "page_width_pdf": float,
          "page_height_pdf": float,
          "scale_used": int,
          "method": "shapely_v9",
          "stats": {lines, rects, polygons_total, polygons_valid}
        }
    """
    try:
        import pdfplumber
        from shapely.geometry import Polygon, Point, LineString
        from shapely.ops import polygonize, unary_union, snap
    except ImportError as e:
        return {"rooms": [], "error": f"deps missing: {e}"}

    # Mastelio konversija
    m_per_pdf_unit = (0.353 / 1000) * drawing_scale  # 0.353mm × scale / 1000
    min_pdf_area = min_room_area_m2 / (m_per_pdf_unit ** 2)

    try:
        pdf = pdfplumber.open(io.BytesIO(pdf_bytes))
    except Exception as e:
        return {"rooms": [], "error": f"pdf open: {e}"}

    try:
        if page_nr < 1 or page_nr > len(pdf.pages):
            return {"rooms": [], "error": "page out of range"}
        page = pdf.pages[page_nr - 1]

        # 1. Surink VISAS linijas (lines + rect kraštai)
        # Filtravimas: tik wall-like segmentai. Praleidžiam:
        #  - per trumpas linijas (<5 PDF units = ~1mm at 1:50 → triukšmas, hatching)
        #  - rect'as kurios per mažos (text/dimension boxes)
        #  - rect'as kurios non-orthogonal (rotated text/labels)
        segments: list[LineString] = []
        # Wall-like minimum: bent 30 PDF units = ~50cm at 1:50 (mažiausia siena)
        # Tai filtruoja DAUG triukšmo (text, dimension lines, hatching)
        min_seg_length = 15  # PDF units (= ~25cm at 1:50)

        for ln in page.lines or []:
            try:
                seg = LineString([(ln["x0"], ln["top"]),
                                  (ln["x1"], ln["bottom"])])
                # Filtras: per trumpas → praleisti
                if seg.length < min_seg_length:
                    continue
                # Wall-like: turi būti orthogonal (horiz arba vert, ±2°)
                dx = abs(ln["x1"] - ln["x0"])
                dy = abs(ln["bottom"] - ln["top"])
                # Orthogonal jei vienas iš dx/dy yra <5% kito
                if dx > 0 and dy > 0:
                    ratio = min(dx, dy) / max(dx, dy)
                    if ratio > 0.05:  # not orthogonal — diagonal line, skip
                        continue
                segments.append(seg)
            except Exception:
                pass

        for r in page.rects or []:
            try:
                x0, y0 = r["x0"], r["top"]
                x1, y1 = r["x1"], r["bottom"]
                w, h = abs(x1-x0), abs(y1-y0)
                # Storesnės rect'os = sienos. Plonos (<3px) = grafikos elementai (skip).
                # Per platūs (>50px) — baldai/kolonėlės (skip).
                thickness = min(w, h)
                length = max(w, h)
                if thickness < 0.5 or thickness > 50:
                    continue
                # Per trumpas rect (text bbox) — skip
                if length < min_seg_length:
                    continue
                # 4 rect kraštai
                segments.append(LineString([(x0,y0), (x1,y0)]))
                segments.append(LineString([(x1,y0), (x1,y1)]))
                segments.append(LineString([(x1,y1), (x0,y1)]))
                segments.append(LineString([(x0,y1), (x0,y0)]))
            except Exception:
                pass

        if not segments:
            return {
                "rooms": [], "method": "fallback",
                "error": "no vector geometry (rastrinis PDF?)",
                "page_width_pdf": page.width,
                "page_height_pdf": page.height,
            }

        # OPTIMIZATION: jei per daug segmentų — dalijam puslapį į ROI tiles
        # (4 kvadrantai → 16 jei vis dar didelis). Polygonize per kiekvieną tile,
        # tada apjungiam rezultatus. Tai sumažina O(n²) → O(n × tiles).
        polys: list = []
        if len(segments) > max_segments:
            # ROI-based polygonize
            from shapely.geometry import box as shp_box
            from shapely.affinity import translate

            page_w, page_h = page.width, page.height
            # 4-tile grid (2×2). Jei vis tiek per daug — 16 tiles (4×4).
            tile_grid = 2 if len(segments) <= max_segments * 4 else 4
            tile_w = page_w / tile_grid
            tile_h = page_h / tile_grid
            tile_overlap = max(snap_tolerance_px * 4, 10)  # overlap tarp tiles

            print(f"[V9 ROI] {len(segments)} seg → {tile_grid}×{tile_grid} tiles")

            seen_polys = []
            for ti in range(tile_grid):
                for tj in range(tile_grid):
                    tile_xmin = max(0, ti * tile_w - tile_overlap)
                    tile_ymin = max(0, tj * tile_h - tile_overlap)
                    tile_xmax = min(page_w, (ti+1) * tile_w + tile_overlap)
                    tile_ymax = min(page_h, (tj+1) * tile_h + tile_overlap)
                    tile_box = shp_box(tile_xmin, tile_ymin, tile_xmax, tile_ymax)

                    # Intersect segments su tile (clip)
                    tile_segs = []
                    for seg in segments:
                        if seg.intersects(tile_box):
                            clipped = seg.intersection(tile_box)
                            if clipped.is_empty or clipped.length < 1:
                                continue
                            # Pastaba: intersection gali grąžinti MultiLineString
                            if hasattr(clipped, 'geoms'):
                                for g in clipped.geoms:
                                    if hasattr(g, 'length') and g.length > 1:
                                        tile_segs.append(g)
                            else:
                                tile_segs.append(clipped)

                    if not tile_segs:
                        continue
                    # Skip if tile has too many segments still
                    if len(tile_segs) > max_segments * 2:
                        continue

                    try:
                        tile_merged = unary_union(tile_segs)
                        tile_snapped = snap(tile_merged, tile_merged, snap_tolerance_px)
                        tile_polys = list(polygonize(tile_snapped))
                    except Exception as e:
                        print(f"[V9 ROI] tile {ti},{tj} polygonize failed: {e}")
                        continue

                    # Filter: tik tile vidus (ne dubliuoti su gretimų tile'ų)
                    tile_inner_box = shp_box(
                        ti * tile_w, tj * tile_h,
                        (ti+1) * tile_w, (tj+1) * tile_h,
                    )
                    for tp in tile_polys:
                        # Centroidas turi būti šio tile vidaus zone
                        c = tp.centroid
                        if tile_inner_box.contains(c):
                            polys.append(tp)
            print(f"[V9 ROI] Surasta {len(polys)} polygons per {tile_grid*tile_grid} tiles")
        else:
            # 2. Endpoint SNAP — apjungiam linijas, kurių endpoint'ai per 3px
            merged = unary_union(segments)
            snapped = snap(merged, merged, snap_tolerance_px)

            # 3. Polygonize → uždari kambariai
            try:
                polys = list(polygonize(snapped))
            except Exception:
                polys = []

        # 4. Filtravimas — per maži = ne kambariai (pertvaros, dėžutės)
        # Adaptyvus: jei mažai polygons, leidžiam mažesnius (gali būti closet'as).
        # Pastaba: P2-stiliaus brėžiniai su sienomis kaip storais rect'ais turi
        # nedidelius polygons (sienos vidus). Filtras turi būti minkštas.
        adaptive_min = min_pdf_area
        if len(polys) <= 20:
            adaptive_min = min_pdf_area * 0.5  # leistina iki 0.75m² (mažas WC)
        valid_polys = [p for p in polys if p.area >= adaptive_min]

        # FALLBACK: jei VISI polygons filtruojami, mastelis greičiausiai blogas
        # (1:100 vs 1:50). Grąžinam didžiausius polygons kaip low-confidence,
        # kad vartotojas pamatytų ką sistema rado, o ne tylų failure.
        scale_warning = None
        if not valid_polys and polys:
            sorted_polys = sorted(polys, key=lambda p: p.area, reverse=True)
            valid_polys = sorted_polys[:12]

        # SCALE_WARNING: jei rasti rooms, bet didžiausias <3m², mastelis greičiausiai blogas
        if valid_polys:
            largest_pdf = max(p.area for p in valid_polys)
            largest_m2 = largest_pdf * (m_per_pdf_unit ** 2)
            if largest_m2 < 3.0:  # 3m² yra MAŽIAUSIAS realus kambarys (mažas WC)
                # Suggest 2x ar 4x didesnį mastelį
                if largest_m2 < 0.5:
                    suggested_scale = drawing_scale * 4
                else:
                    suggested_scale = drawing_scale * 2
                scale_warning = (
                    f"Didžiausias rastas room: {largest_m2:.2f}m². Mastelis greičiausiai "
                    f"NETEISINGAS (1:{drawing_scale}) — pabandyk drawing_scale={suggested_scale} (1:{suggested_scale})."
                )

        # 4a. Pašalinti POLYGONS, kurie yra polygon viduje kito (hole'ai)
        # Naudojam outer-only logic: jei polygon A pilnai įeina į polygon B,
        # tada A yra B vidaus dalis (pvz. spinta kambario viduje) — drop A.
        outer_only = []
        for i, p_a in enumerate(valid_polys):
            is_hole = False
            for j, p_b in enumerate(valid_polys):
                if i == j:
                    continue
                if p_b.area > p_a.area * 1.5 and p_b.contains(p_a.buffer(-1)):
                    is_hole = True
                    break
            if not is_hole:
                outer_only.append(p_a)

        # 5. Surink visus tekstinius elementus
        words = page.extract_words() or []
        text_positions = [
            {
                "text": w.get("text", "").strip(),
                "x": (w["x0"] + w["x1"]) / 2,
                "y": (w["top"] + w["bottom"]) / 2,
                "size": w.get("bottom", 0) - w.get("top", 0),
            }
            for w in words if w.get("text")
        ]

        # 6. Per kambarį surink artimus textus
        rooms_data = []
        for idx, poly in enumerate(outer_only):
            cx, cy = poly.centroid.x, poly.centroid.y

            # Tekstai polygon viduje (top priority)
            inside_texts = []
            # Tekstai šalia centroido (artimiausia 100px)
            nearby_texts = []
            for tp in text_positions:
                pt = Point(tp["x"], tp["y"])
                dist_to_centroid = ((tp["x"]-cx)**2 + (tp["y"]-cy)**2) ** 0.5
                if poly.contains(pt):
                    inside_texts.append((tp["text"], dist_to_centroid, tp["size"]))
                elif dist_to_centroid < 100:
                    nearby_texts.append((tp["text"], dist_to_centroid, tp["size"]))

            inside_texts.sort(key=lambda x: x[1])  # arčiausias centroidui pirma
            nearby_texts.sort(key=lambda x: x[1])

            # Konvertuoti į m²
            area_m2 = poly.area * (m_per_pdf_unit ** 2)
            perim_m = poly.length * m_per_pdf_unit

            rooms_data.append({
                "polygon_id": idx,
                "area_m2": round(area_m2, 2),
                "perimeter_m": round(perim_m, 2),
                "centroid_pdf": [round(cx, 1), round(cy, 1)],
                "centroid_pct": [round(cx / page.width, 4),
                                 round(cy / page.height, 4)],
                "bbox_pdf": list(poly.bounds),
                "bbox_pct": {
                    "x": round(poly.bounds[0] / page.width, 4),
                    "y": round(poly.bounds[1] / page.height, 4),
                    "w": round((poly.bounds[2] - poly.bounds[0]) / page.width, 4),
                    "h": round((poly.bounds[3] - poly.bounds[1]) / page.height, 4),
                },
                "polygon_pdf": [[round(p[0],1), round(p[1],1)] for p in poly.exterior.coords],
                "inside_texts": [t for t,_,_ in inside_texts[:8]],
                "nearby_texts": [t for t,_,_ in nearby_texts[:5]],
            })

        return {
            "rooms": rooms_data,
            "page_width_pdf": page.width,
            "page_height_pdf": page.height,
            "scale_used": drawing_scale,
            "method": "shapely_v9",
            "scale_warning": scale_warning,
            "stats": {
                "lines": len(segments),
                "polygons_total": len(polys),
                "polygons_valid": len(valid_polys),
                "polygons_outer": len(outer_only),
                "min_room_area_m2": min_room_area_m2,
            },
        }
    finally:
        pdf.close()
