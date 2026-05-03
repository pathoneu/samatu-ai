"""Auto-extract symbol legends from a PDF.

Given a PDF + the page numbers where SUTARTINIAI ŽENKLAI appears, ask Claude
Sonnet 4.6 (vision-capable) to read the legend block and return structured:

    [
      {
        "symbol_code": "iš.1",
        "description_lt": "išviršinis lubinis šviestuvas",
        "category": "lighting",
        "glyph_bbox_pct": [x, y, w, h],   # location of the GLYPH inside the page
        "color_hint": "#RRGGBB" | null,
      },
      ...
    ]

Then crops each glyph_bbox_pct out of the rendered page and saves as PNG
under legends/<pdf_name>/<symbol_code>.png — these become templates for
Pipeline 3 (cv2.matchTemplate) and Pipeline 4 (hybrid).
"""

from __future__ import annotations
import json
import os
import base64
from pathlib import Path
from io import BytesIO

from PIL import Image
import anthropic

from detector_bench.core.pdf_loader import render_page

CLAUDE_MODEL = "claude-sonnet-4-6"

LEGEND_PROMPT = """You are reading a Lithuanian construction-drawing legend block.

Identify every distinct symbol shown in the SUTARTINIAI ŽENKLAI / SUTARTINIAI ŽYMĖJIMAI section
of this page. For each symbol, return:

- symbol_code: the short code (e.g. "iš.1", "pš.1", "led.1", "rozete", "jungtukas").
  Lowercase, replace spaces with underscores. If the legend uses a Lithuanian word
  (e.g. "rozetė", "jungtukas") with no code, use the word itself.
- description_lt: the Lithuanian description shown next to the symbol.
- category: one of "lighting" | "electrical" | "plumbing" | "hvac" | "finish" | "other"
- glyph_bbox_pct: [x, y, w, h] normalized 0-1 fractions of THIS PAGE indicating
  where the symbol GLYPH (not the description text) is drawn. Tight crop.
- color_hint: dominant glyph color as #RRGGBB hex if obviously colored, else null.

Return ONLY valid JSON — a list of objects, no prose, no markdown fence.
If you cannot find a legend on this page, return [].
"""


def _img_to_base64_png(img: Image.Image) -> str:
    buf = BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def extract_legend_from_page(pdf_path: Path, page_nr: int) -> list[dict]:
    """Returns list of symbol dicts (see module docstring). Empty if no legend."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    arr = render_page(Path(pdf_path), page_nr, dpi=200)
    img = Image.fromarray(arr)
    b64 = _img_to_base64_png(img)
    client = anthropic.Anthropic()
    resp = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4000,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64}},
                    {"type": "text", "text": LEGEND_PROMPT},
                ],
            }
        ],
    )
    text = resp.content[0].text.strip()
    # Tolerate accidental code fences
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json\n"):
            text = text[5:]
        text = text.rstrip("`").strip()
    try:
        items = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Claude returned non-JSON: {e}\n--- raw ---\n{text[:500]}")
    if not isinstance(items, list):
        raise ValueError(f"expected list, got {type(items).__name__}")
    return items


def crop_glyph_templates(
    pdf_path: Path, page_nr: int, items: list[dict], out_dir: Path,
) -> dict[str, Path]:
    """Crop each glyph_bbox_pct out of the rendered page; save as PNG.

    Returns mapping {symbol_code: png_path}.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    arr = render_page(Path(pdf_path), page_nr, dpi=200)
    h, w = arr.shape
    img = Image.fromarray(arr)
    out: dict[str, Path] = {}
    for item in items:
        bbox = item.get("glyph_bbox_pct")
        code = item.get("symbol_code")
        if not bbox or not code or len(bbox) != 4:
            continue
        x, y, ww, hh = bbox
        left = max(0, int(x * w))
        top = max(0, int(y * h))
        right = min(w, int((x + ww) * w))
        bottom = min(h, int((y + hh) * h))
        if right <= left or bottom <= top:
            continue
        crop = img.crop((left, top, right, bottom))
        # Sanitize filename
        safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in code)
        out_path = out_dir / f"{safe}.png"
        crop.save(out_path, "PNG")
        out[code] = out_path
    return out
