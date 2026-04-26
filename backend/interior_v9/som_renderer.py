"""
Set-of-Marks (SoM) PDF renderer.

Generuoja paveikslą iš PDF puslapio + perdengia raudonais skaičiais
per kiekvieno polygon centroidą. Vision'ui šitai labai padeda — pažymėti
regionai gerokai pagerina visual grounding (skill A.2, +20-30% accuracy).

Source: arXiv:2310.11441 (Microsoft SoM)
"""
from __future__ import annotations
import io
import base64


def render_pdf_with_som(
    pdf_bytes: bytes,
    page_nr: int,
    polygons: list[dict],
    dpi: int = 200,
) -> dict:
    """Render PDF page + overlay raudonais skaičiais per polygon centroidus.

    Args:
        pdf_bytes: PDF
        page_nr: 1-indexed
        polygons: list iš build_room_polygons (turi polygon_id, centroid_pdf, polygon_pdf)
        dpi: rendering DPI (200 = geras balansas)

    Returns:
        {
          "image_b64": str,    # base64 PNG perdengtas
          "image_size": [w, h],
          "scale_pdf_to_px": float,
        }
    """
    try:
        import pdfplumber
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as e:
        return {"error": f"deps missing: {e}"}

    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            if page_nr < 1 or page_nr > len(pdf.pages):
                return {"error": "page out of range"}
            page = pdf.pages[page_nr - 1]
            # Render to PIL Image
            pim = page.to_image(resolution=dpi)
            img = pim.original.convert("RGB")
            page_w_pdf = page.width
            page_h_pdf = page.height
    except Exception as e:
        return {"error": f"render: {e}"}

    img_w, img_h = img.size
    scale_x = img_w / page_w_pdf
    scale_y = img_h / page_h_pdf

    draw = ImageDraw.Draw(img, "RGBA")

    # Try to load font
    try:
        font_label = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 36)
    except Exception:
        try:
            font_label = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
        except Exception:
            font_label = ImageFont.load_default()

    for poly in polygons:
        # Polygon outline (light red)
        if poly.get("polygon_pdf"):
            pts = [(p[0] * scale_x, p[1] * scale_y) for p in poly["polygon_pdf"]]
            draw.polygon(pts, outline=(220, 30, 30, 200), width=3)
            # Soft fill
            draw.polygon(pts, fill=(220, 30, 30, 30))

        # Centroid label (red circle + number)
        cx_pdf, cy_pdf = poly.get("centroid_pdf", [0, 0])
        cx, cy = cx_pdf * scale_x, cy_pdf * scale_y
        radius = 28
        draw.ellipse(
            [(cx - radius, cy - radius), (cx + radius, cy + radius)],
            fill=(220, 30, 30, 230), outline=(255, 255, 255, 255), width=3
        )
        label = str(poly.get("polygon_id", "?"))
        # Centruoti tekstą
        try:
            bbox = draw.textbbox((cx, cy), label, font=font_label, anchor="mm")
            draw.text((cx, cy), label, font=font_label, fill="white", anchor="mm")
        except Exception:
            draw.text((cx - 10, cy - 18), label, font=font_label, fill="white")

    # Encode to base64
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")

    return {
        "image_b64": b64,
        "image_size": [img_w, img_h],
        "scale_pdf_to_px": (scale_x + scale_y) / 2,
    }
