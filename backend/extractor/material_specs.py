"""extractor.material_specs — on-demand designer material spec extraction
for a single room. Triggered by user click in RoomCard, not auto.

Pages targeted:
- "VIRTUVĖS SPALVOS", "VAIKŲ VONIOS SPALVOS", etc. (per-room paint+tile spec)
- "VIRTUVĖS SIENŲ IŠKLOTINĖS", room wall elevations (tile spec inline)

We use Vision because text layout is mixed with paint sample images and
tile photos — pdfplumber alone can't disambiguate which spec belongs to
which page section. ONE focused Vision call per room (~$0.20).

Returns structured: {paint, sienos_plyteles, grindys_plyteles, grindys_medines}
each with brand/model/dims/color/notes/raw_text.

Cached at project level — second click for same room is free.
"""
from __future__ import annotations

import json
import re
import time
from typing import Any

import anthropic

from models_config import model_for  # call-time model resolution
from .vision_call import pdf_to_b64_images

__all__ = ["extract_room_material_specs"]


SYSTEM_TEXT = """Tu esi LT interjero projektų medžiagų spec'ų skaitytojas.

Iš pateiktų puslapių susijusių su konkrečia patalpa, ištrauk medžiagų
specifikacijas (dažai, plytelės, grindys). Grąžink TIK strukturuotą JSON.

GRIEŽTOS TAISYKLĖS:
- TIK kas matoma puslapiuose. Niekada neinferink.
- Jei lauko reikšmės nematote, palik `null`.
- Lietuviški simboliai (ąčęėįšųūž) PRIVALO būti tikslūs.
- Plytelių dydžiai mm (jei brėžinyje cm, konvertuok).
- Brand'ai (Benjamin Moore, Materia Pesca, Limo Cedit, Esta Parket) — palik kaip yra.

Output schema (TypeScript):
```typescript
type RoomSpecs = {
  paint?: {
    brand: string;       // "Benjamin Moore"
    code: string | null; // "HC-98"
    name: string | null; // "Providence Olive"
    where: "sienos" | "lubos" | "sienos_lubos" | null;
    raw_text: string;    // exact label as on page
  } | null;
  sienos_plyteles?: {
    brand: string | null;       // "Materia Pesca"
    model: string | null;       // "Trama Rett"
    size_mm: string | null;     // "60x120"
    storis_mm: number | null;   // 9
    spalva: string | null;      // "07" or color name
    klijavimo_kampas: string | null;  // "45°" or "tiesiai"
    tarpas_mm: number | null;   // 0.5
    raw_text: string;
  } | null;
  grindys_plyteles?: {  // same shape
    brand: string | null;
    model: string | null;
    size_mm: string | null;
    storis_mm: number | null;
    spalva: string | null;
    raw_text: string;
  } | null;
  grindys_medines?: {
    brand: string | null;     // "Esta Parket"
    model: string | null;     // "1 Strip Oak BC Kose Grey"
    finish: string | null;    // "Pores Extra Matt Lac 5% 2B Brushed"
    supplier: string | null;  // "Vielaris" / "Woodlife"
    raw_text: string;
  } | null;
};
```
"""


def _repair_json(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        if text.endswith("```"):
            text = text[:-3]
    text = re.sub(r"([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:", r'\1"\2":', text)
    text = re.sub(r",(\s*[}\]])", r"\1", text)
    return text


def extract_room_material_specs(
    pdf_bytes: bytes,
    pages_to_inspect: list[int],
    room_pavadinimas: str,
    client: anthropic.Anthropic | None = None,
) -> dict:
    """Extract material specs from designer's spec pages for ONE room.

    Args:
        pdf_bytes: full PDF
        pages_to_inspect: 1-indexed page numbers (typically 1-3 pages —
            the room's wall elevation page + per-room spalvos page)
        room_pavadinimas: room name (used in user prompt for context)
        client: Anthropic client (created if None)

    Returns: RoomSpecs dict per schema, plus _meta with elapsed/tokens.
    """
    if not pages_to_inspect:
        return {"paint": None, "sienos_plyteles": None,
                "grindys_plyteles": None, "grindys_medines": None,
                "_meta": {"elapsed_s": 0, "pages_inspected": []}}

    if client is None:
        client = anthropic.Anthropic(max_retries=1)

    t0 = time.time()
    # Render only requested pages at high DPI (300) for clean OCR of small spec text
    try:
        from pdf2image import convert_from_bytes
        from PIL import Image
        import io
        import base64

        # Render only selected pages
        all_imgs = []
        for p in sorted(set(pages_to_inspect)):
            try:
                imgs = convert_from_bytes(
                    pdf_bytes, dpi=200, fmt="jpeg",
                    first_page=p, last_page=p,
                )
                if imgs:
                    img = imgs[0]
                    # Cap size like main pipeline
                    w, h = img.size
                    scale = min(1.0, 2000 / max(w, h))
                    if scale < 1.0:
                        img = img.resize((int(w * scale), int(h * scale)))
                    buf = io.BytesIO()
                    img.save(buf, format="JPEG", quality=85)
                    all_imgs.append({
                        "page_index": p,
                        "image_b64": base64.b64encode(buf.getvalue()).decode("ascii"),
                    })
            except Exception:
                continue
    except Exception as exc:
        return {"_error": f"render_failed: {exc}",
                "paint": None, "sienos_plyteles": None,
                "grindys_plyteles": None, "grindys_medines": None,
                "_meta": {"elapsed_s": round(time.time() - t0, 2)}}

    if not all_imgs:
        return {"paint": None, "sienos_plyteles": None,
                "grindys_plyteles": None, "grindys_medines": None,
                "_meta": {"elapsed_s": round(time.time() - t0, 2),
                          "_error": "no_pages_rendered"}}

    # Build user content: instruction + page images
    user_content: list[dict] = [{
        "type": "text",
        "text": (
            f"Patalpa, kuriai ieškome medžiagų: **{room_pavadinimas}**\n\n"
            f"Pateikti puslapiai: {[p['page_index'] for p in all_imgs]}\n\n"
            f"Iš šių puslapių ištrauk medžiagų spec'us TIK šiai patalpai. "
            f"Jei puslapis apima kitą patalpą — ignoruok. Jei spec'as universalus "
            f"(visiems gyvenamiems kambariams) — pateik. Grąžink JSON pagal schemą."
        ),
    }]
    for p in all_imgs:
        user_content.append({
            "type": "text",
            "text": f"Page {p['page_index']}:",
        })
        user_content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": p["image_b64"],
            },
        })

    system = [{"type": "text", "text": SYSTEM_TEXT,
               "cache_control": {"type": "ephemeral"}}]

    # Call with retry
    parsed_specs: dict | None = None
    last_err: Exception | None = None
    model = model_for("vision_pass1")  # resolved per-run (MODEL_OVERRIDE etc.)
    for attempt in range(2):
        try:
            with client.messages.stream(
                model=model,
                max_tokens=4096,  # raised at Opus 5 cutover: thinking counts against the cap
                system=system,
                messages=[{"role": "user", "content": user_content}],
                output_config={"effort": "medium"},
            ) as stream:
                resp = stream.get_final_message()
            text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
            try:
                parsed_specs = json.loads(text)
            except json.JSONDecodeError:
                parsed_specs = json.loads(_repair_json(text))
            usage = resp.usage
            input_tok = getattr(usage, "input_tokens", 0)
            output_tok = getattr(usage, "output_tokens", 0)
            break
        except Exception as exc:
            last_err = exc
            if attempt == 1:
                return {"_error": str(exc),
                        "paint": None, "sienos_plyteles": None,
                        "grindys_plyteles": None, "grindys_medines": None,
                        "_meta": {"elapsed_s": round(time.time() - t0, 2)}}
            time.sleep(1.0)

    out = parsed_specs or {}
    out.setdefault("paint", None)
    out.setdefault("sienos_plyteles", None)
    out.setdefault("grindys_plyteles", None)
    out.setdefault("grindys_medines", None)
    out["_meta"] = {
        "elapsed_s": round(time.time() - t0, 2),
        "pages_inspected": [p["page_index"] for p in all_imgs],
        "input_tokens": input_tok if "input_tok" in dir() else 0,
        "output_tokens": output_tok if "output_tok" in dir() else 0,
    }
    return out
