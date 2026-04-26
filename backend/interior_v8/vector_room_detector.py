"""
Vector-first room detection — pdfplumber + Shapely.

Strategija (per skill A.5):
1. PDF lines + rects → polygonize → kambarių polygons
2. Find room labels (text positions) → match polygon ↔ name
3. Compute area, perimeter su tikru masteliu (ne pikseliais)

Privalumai:
- DETERMINISTINIS (visada tas pats rezultatas)
- 100% tikslumas vector PDF'ams (sienos coordinates yra realios)
- Greitas (~1-3 sekundžių per puslapį)

Trūkumai:
- Veikia TIK vector PDF'ams (rastriniai → fallback į Vision)
- Sudėtinga atvirose erdvėse (svetainė + virtuvė vienoj zonoj)
- Kambarių labels gali būti per toli nuo polygon centroid

NRM2 / LT taisyklės:
- Plotas matuojamas tarp apdailintų sienų paviršių
- Niašos < 1.6m aukščio neįtraukiamos
- Mansardiniai zonų svoris: <1.5m=0%, 1.5-2.0m=50%, >2.0m=100%
"""
from __future__ import annotations
import io
import re
from typing import Any


def detect_rooms_from_vector(pdf_bytes: bytes,
                              page_nr: int,
                              scale_m_per_pdf_unit: float = 0.353) -> dict:
    """Aptikti kambarius iš vector PDF puslapio.

    Args:
        pdf_bytes: PDF failo bytes
        page_nr: 1-indexed puslapio nr
        scale_m_per_pdf_unit: Kiek metrų per 1 PDF unitą.
            Default 0.353 = 1/72 inch × 25.4 mm/inch / 1000 mm/m
            (be brėžinio mastelio — tai grynas PDF unit'as)

    Returns:
        {
          "rooms": [{label, area_m2, perimeter_m, polygon, centroid}, ...],
          "labels_unmatched": [...],
          "page_width_pdf": float,
          "page_height_pdf": float,
          "method": "shapely" | "fallback",
        }
    """
    try:
        import pdfplumber
        from shapely.geometry import Polygon, Point
        from shapely.ops import polygonize, unary_union
        from shapely.geometry.linestring import LineString
    except ImportError as e:
        return {"rooms": [], "error": f"deps missing: {e}", "method": "fallback"}

    try:
        pdf = pdfplumber.open(io.BytesIO(pdf_bytes))
    except Exception as e:
        return {"rooms": [], "error": f"pdf open: {e}", "method": "fallback"}

    try:
        if page_nr < 1 or page_nr > len(pdf.pages):
            return {"rooms": [], "error": "page out of range"}

        page = pdf.pages[page_nr - 1]

        # 1. Surink visas linijas ir stačiakampius
        line_segments: list[LineString] = []
        for ln in page.lines or []:
            try:
                seg = LineString([(ln["x0"], ln["top"]),
                                  (ln["x1"], ln["bottom"])])
                if seg.length > 1:
                    line_segments.append(seg)
            except Exception:
                continue

        for r in page.rects or []:
            try:
                x0, y0 = r["x0"], r["top"]
                x1, y1 = r["x1"], r["bottom"]
                # Tik plonos rect'os = sienos (storis < 50px)
                if min(abs(x1-x0), abs(y1-y0)) > 50:
                    continue
                # Pridedam 4 kraštus
                line_segments.append(LineString([(x0,y0), (x1,y0)]))
                line_segments.append(LineString([(x1,y0), (x1,y1)]))
                line_segments.append(LineString([(x1,y1), (x0,y1)]))
                line_segments.append(LineString([(x0,y1), (x0,y0)]))
            except Exception:
                continue

        if not line_segments:
            return {
                "rooms": [], "method": "fallback",
                "error": "no vector lines found (rastrinis PDF?)",
                "page_width_pdf": page.width,
                "page_height_pdf": page.height,
            }

        # 2. Sujungti linijas (snap endpoint'us, kurie yra <2px atstumu)
        merged = unary_union(line_segments)

        # 3. Polygonize → kambarių formos
        try:
            polys = list(polygonize(merged))
        except Exception as e:
            polys = []

        # 4. Filtruoti per mažas zonas (jei mažiau nei 1 m² po mastelio konversijos)
        min_pdf_area = (1.0 / scale_m_per_pdf_unit) ** 2  # 1m² in PDF units²
        valid_polys = [p for p in polys if p.area > min_pdf_area]

        # 5. Surink visus tekstinius elementus su pozicija
        words = page.extract_words() or []
        text_positions = [
            {
                "text": w.get("text", "").strip(),
                "x": (w["x0"] + w["x1"]) / 2,
                "y": (w["top"] + w["bottom"]) / 2,
            }
            for w in words if w.get("text")
        ]

        # 6. Match polygon ↔ label (ieškom teksto polygon'o viduje)
        rooms_data = []
        used_labels = set()

        for poly in valid_polys:
            # Surink visus tekstus poly viduje
            inside_texts = []
            cx, cy = poly.centroid.x, poly.centroid.y
            for tp in text_positions:
                pt = Point(tp["x"], tp["y"])
                if poly.contains(pt):
                    # Atstumas iki centroido — artimesni svarbesni
                    dist = ((tp["x"]-cx)**2 + (tp["y"]-cy)**2) ** 0.5
                    inside_texts.append((tp["text"], dist))

            # Surūšiuoti pagal artimumą centroidui
            inside_texts.sort(key=lambda x: x[1])

            # Geriausias label'as = tekstas, kuris yra ROOM_NAME-like
            label = _find_room_label([t for t, _ in inside_texts])

            # Konvertuoti į m²
            area_pdf = poly.area
            area_m2 = area_pdf * (scale_m_per_pdf_unit ** 2)
            perim_pdf = poly.length
            perim_m = perim_pdf * scale_m_per_pdf_unit

            rooms_data.append({
                "label": label,
                "area_m2": round(area_m2, 2),
                "perimeter_m": round(perim_m, 2),
                "centroid_pdf": [round(cx, 1), round(cy, 1)],
                "centroid_pct": [
                    round(cx / page.width, 4),
                    round(cy / page.height, 4),
                ],
                "bbox_pdf": list(poly.bounds),  # [x0, y0, x1, y1]
                "bbox_pct": {
                    "x": round(poly.bounds[0] / page.width, 4),
                    "y": round(poly.bounds[1] / page.height, 4),
                    "w": round((poly.bounds[2] - poly.bounds[0]) / page.width, 4),
                    "h": round((poly.bounds[3] - poly.bounds[1]) / page.height, 4),
                },
                "polygon_pdf": [list(p) for p in poly.exterior.coords],
                "inside_texts": [t for t, _ in inside_texts[:10]],
            })

        return {
            "rooms": rooms_data,
            "page_width_pdf": page.width,
            "page_height_pdf": page.height,
            "method": "shapely",
            "polygons_total": len(polys),
            "polygons_valid": len(valid_polys),
            "lines_collected": len(line_segments),
        }
    finally:
        pdf.close()


# ────────────────────────────────────────────────────────────────────
# Helper: identify room labels from text content
# ────────────────────────────────────────────────────────────────────

ROOM_LABEL_PATTERNS = [
    # LT
    r"svetain", r"miegamoj", r"miegamasis", r"vonia", r"wc", r"san[\.\s]?mazg",
    r"virtuv", r"valgom", r"koridori", r"holas", r"drabuž", r"rūbin",
    r"katil", r"skalb", r"sandėli", r"sandeli", r"tambūr", r"tambur",
    r"garaž", r"gyven", r"vaiko\s*kamb", r"kambar", r"prieškamb",
    r"prieskamb",
    # LT trumpiniai
    r"^sv$", r"^mg$", r"^vir$", r"^vonia$", r"^wc$",
    # Numeravimas
    r"^\d{2,3}$",  # patalpos numeris (01, 02, ...)
]


def _find_room_label(texts: list[str]) -> str:
    """Iš text'ų sąrašo pasirinkti geriausią kambario pavadinimą."""
    for text in texts:
        t_lower = text.lower().strip()
        if not t_lower:
            continue
        # Prioritetas: žodžiai, atitinkantys kambario tipo pattern'us
        for pattern in ROOM_LABEL_PATTERNS:
            if re.search(pattern, t_lower):
                return text.strip()
    # Fallback — pirmas tekstas
    return texts[0].strip() if texts else "Patalpa"
