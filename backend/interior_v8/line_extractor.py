"""
Vector PDF lines extractor — atskirsto sienos ir kitos linijos iš vector PDF
sluoksnio, naudojama snap-to-lines įrankiui frontend'e.

Output formatas:
{
  "page": 1,
  "page_width_pdf": 595.2,    # PDF unitais
  "page_height_pdf": 841.8,
  "lines": [
    {"x1": 100.5, "y1": 200.3, "x2": 350.5, "y2": 200.3, "thickness": 1.0},
    ...
  ]
}

Snap radius default 8 px (Konva canvas'e). Frontend'as konvertuoja per
canvas_scale = canvas_width / page_width_pdf.
"""
from __future__ import annotations
import io
from typing import Any


def extract_lines_for_page(pdf_bytes: bytes, page_nr: int) -> dict:
    """Iš PDF puslapio (1-indexed) ekstrahuoja visas linijas.

    Args:
        pdf_bytes: PDF failo bytes
        page_nr: puslapio numeris (1-indexed)

    Returns:
        {page, page_width_pdf, page_height_pdf, lines, count}
    """
    try:
        import pdfplumber
    except ImportError:
        return {"page": page_nr, "lines": [], "error": "pdfplumber missing"}

    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            if page_nr < 1 or page_nr > len(pdf.pages):
                return {"page": page_nr, "lines": [], "error": "page out of range"}

            page = pdf.pages[page_nr - 1]
            lines_raw = page.lines or []
            rects_raw = page.rects or []
            curves_raw = page.curves or []

            lines = []
            # Tiesi linijos
            for ln in lines_raw:
                lines.append({
                    "x1": round(ln.get("x0", 0), 2),
                    "y1": round(ln.get("top", 0), 2),
                    "x2": round(ln.get("x1", 0), 2),
                    "y2": round(ln.get("bottom", 0), 2),
                    "thickness": round(ln.get("linewidth", 1.0) or 1.0, 2),
                    "type": "line",
                })

            # Stačiakampių sienos (4 linijos per rect)
            for r in rects_raw:
                x0, y0 = r.get("x0", 0), r.get("top", 0)
                x1, y1 = r.get("x1", 0), r.get("bottom", 0)
                # Tik aiškios "sienos" — jei rect storis didelis, tai blokas/baldas
                w = abs(x1 - x0)
                h = abs(y1 - y0)
                if min(w, h) > 50:  # ne sienos (per platus)
                    continue
                # 4 kraštai
                lines.append({"x1": x0, "y1": y0, "x2": x1, "y2": y0, "thickness": 1, "type": "rect_edge"})
                lines.append({"x1": x1, "y1": y0, "x2": x1, "y2": y1, "thickness": 1, "type": "rect_edge"})
                lines.append({"x1": x1, "y1": y1, "x2": x0, "y2": y1, "thickness": 1, "type": "rect_edge"})
                lines.append({"x1": x0, "y1": y1, "x2": x0, "y2": y0, "thickness": 1, "type": "rect_edge"})

            # Filtras: per trumpos linijos (mažiau 3 PDF unitų ≈ 1mm) — atmetam
            lines = [
                ln for ln in lines
                if ((ln["x2"] - ln["x1"]) ** 2 + (ln["y2"] - ln["y1"]) ** 2) ** 0.5 > 3
            ]

            return {
                "page": page_nr,
                "page_width_pdf": round(page.width, 2),
                "page_height_pdf": round(page.height, 2),
                "lines": lines,
                "count": len(lines),
                "has_curves": len(curves_raw) > 0,
            }
    except Exception as e:
        return {"page": page_nr, "lines": [], "error": str(e)}


def extract_lines_all_pages(pdf_bytes: bytes, max_pages: int = 30) -> dict:
    """Ekstrahuoja linijas visiems puslapiams (ribota).

    Args:
        pdf_bytes: PDF
        max_pages: maksimalus puslapių skaičius (default 30)
    """
    try:
        import pdfplumber
    except ImportError:
        return {"pages": {}, "error": "pdfplumber missing"}

    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            n = min(len(pdf.pages), max_pages)
            pages = {}
            for i in range(n):
                page_nr = i + 1
                page = pdf.pages[i]
                lines_raw = page.lines or []

                lines = []
                for ln in lines_raw:
                    lines.append({
                        "x1": round(ln.get("x0", 0), 2),
                        "y1": round(ln.get("top", 0), 2),
                        "x2": round(ln.get("x1", 0), 2),
                        "y2": round(ln.get("bottom", 0), 2),
                    })

                # Filter trumpas
                lines = [
                    ln for ln in lines
                    if ((ln["x2"] - ln["x1"]) ** 2 + (ln["y2"] - ln["y1"]) ** 2) ** 0.5 > 3
                ]

                pages[str(page_nr)] = {
                    "page_width_pdf": round(page.width, 2),
                    "page_height_pdf": round(page.height, 2),
                    "lines": lines,
                    "count": len(lines),
                }
            return {"pages": pages, "total_pages": len(pdf.pages)}
    except Exception as e:
        return {"pages": {}, "error": str(e)}
