"""extractor.wall_elevation — specialized Vision extractor for sienų išklotinės pages.

Why this exists:
    Main `extract_interior` Vision call sees the whole PDF (~50-65 pages) at
    200 DPI and produces room primitives + symbol counts. It under-extracts
    sienų išklotinė data (15-25 pages of detailed wall sections) because:
      - One big prompt can't deeply analyze each wall elevation
      - Plytelių zonos with mm boundaries get rounded or skipped
      - Niches, furniture zones, panel boundaries lost in noise

    This module runs a SECOND Vision pass per wall_elevation page at higher
    DPI (300) with a tightly focused prompt: "you are reading ONE wall
    elevation, give me precise mm boundaries for tile / paint / niche /
    furniture zones".

    Result: instead of approximating `plyteles_sienos_m2 = perim × 2.0` for
    vonia (paskirtis-based default), we get exact mm boundaries from the
    actual drawing.

When to use:
    Opt-in via `WALL_ELEVATION_EXTRACT=1` env var on backend OR per-project
    setting. Cost: ~$0.10-0.20/page × 10-25 pages = $1-5/project. Defer for
    raster-only PDFs (Vision can't read mm dimensions reliably below 300 DPI).

Output shape:
    {
        "wall_elevations": [
            {
                "page": int,
                "room_name": str,         # matches eksplikacija/floor plan
                "wall_id": str,            # "A", "B", "1", "2" — labelled in drawing
                "tile_zones": [
                    {"from_floor_mm": int, "to_floor_mm": int,
                     "wall_segment_label": str | None}
                ],
                "paint_zones": [
                    {"from_floor_mm": int, "to_floor_mm": int}
                ],
                "niches": [
                    {"width_mm": int, "height_mm": int, "depth_mm": int,
                     "purpose": str | None}
                ],
                "furniture_zones": [
                    {"from_floor_mm": int, "to_floor_mm": int,
                     "width_mm": int, "label": str | None}
                ],
                "wall_total_width_mm": int | None,
                "wall_total_height_mm": int | None,
                "confidence": "high" | "medium" | "low",
            }
        ],
        "_meta": {"pages_processed": int, "elapsed_s": float, ...}
    }

This module never raises — soft-fails per page so one bad page doesn't kill
the batch.
"""
from __future__ import annotations

import json
import re as _re
import time
from typing import Any

import anthropic

from models_config import model_for  # call-time model resolution
from .vision_call import pdf_to_b64_images

__all__ = ["extract_wall_elevations"]


# =============================================================================
# JSON SCHEMA — locked output for ONE wall elevation page
# =============================================================================
PAGE_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["page", "wall_elevations"],
    "properties": {
        "page": {"type": "integer"},
        "wall_elevations": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["wall_id", "tile_zones", "paint_zones", "niches", "furniture_zones"],
                "properties": {
                    "nr": {"type": ["string", "null"],
                           "description": "Room number from eksplikacija (e.g. '107', '111'). REQUIRED when readable."},
                    "room_name": {"type": ["string", "null"],
                                  "description": "Room name as labelled in drawing title block. Match eksplikacija."},
                    "wall_id": {"type": "string",
                                "description": "Wall label (A/B/1/2/N/S/E/W). Use literal label from drawing."},
                    "wall_total_width_mm": {"type": ["integer", "null"]},
                    "wall_total_height_mm": {"type": ["integer", "null"]},
                    "tile_zones": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["from_floor_mm", "to_floor_mm"],
                            "properties": {
                                "from_floor_mm": {"type": "integer"},
                                "to_floor_mm": {"type": "integer"},
                                "wall_segment_label": {"type": ["string", "null"]},
                            },
                        },
                    },
                    "paint_zones": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["from_floor_mm", "to_floor_mm"],
                            "properties": {
                                "from_floor_mm": {"type": "integer"},
                                "to_floor_mm": {"type": "integer"},
                            },
                        },
                    },
                    "niches": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["width_mm", "height_mm"],
                            "properties": {
                                "width_mm": {"type": "integer"},
                                "height_mm": {"type": "integer"},
                                "depth_mm": {"type": ["integer", "null"]},
                                "purpose": {"type": ["string", "null"]},
                            },
                        },
                    },
                    "furniture_zones": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["from_floor_mm", "to_floor_mm", "width_mm"],
                            "properties": {
                                "from_floor_mm": {"type": "integer"},
                                "to_floor_mm": {"type": "integer"},
                                "width_mm": {"type": "integer"},
                                "label": {"type": ["string", "null"]},
                            },
                        },
                    },
                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                },
            },
        },
    },
}


# =============================================================================
# SYSTEM PROMPT
# =============================================================================
SYSTEM_TEXT = """Tu skaitai LT statybinio brėžinio sienų išklotinę. Tavo VIENINTELĖ užduotis — iš pateiktų PDF puslapių su sienų išklotinėmis (wall elevations) iš VIENO puslapio ištraukti SIENŲ ZONŲ MATMENIS milimetrais.

Sienų išklotinė rodo kambario sienas „išklotines" — tai yra vertikalūs sienų piešiniai su matmenimis aukštyje (mm nuo grindų) ir pločiais. Tipiškai tame pačiame puslapyje pavaizduojama 2-4 sienos su raidiniais žymėjimais (A, B, C, D arba 1, 2, 3, 4).

KO IEŠKOTI KIEKVIENAI SIENAI:

1. **Plytelių zonos (`tile_zones`)** — kur sienoje plytelės. Hatching/brūkšniavimas + spalvinė užpildymas + žymėjimas „PLYTELĖS"/„PT". Matmenys nuo grindų: pvz., 0-2400mm (vonios) arba 600-1500mm (virtuvės backsplash).

2. **Dažomos zonos (`paint_zones`)** — kur sienoje dažoma. Tuščias arba be hatching'o, kartais su anotacija „DAŽYMAS"/„BALTAS"/„MATINIS". Tipiškai virš plytelių zonos iki lubų.

3. **Niches (`niches`)** — angos sienoje (palanges, dušo niches, knygų lentyna). Stačiakampis sienoje su anotuotais pločio × aukščio × gylio matmenimis.

4. **Baldų zonos (`furniture_zones`)** — vonios/virtuvės baldų / pakabintų spintelių vieta sienoje (NEDAŽOMA / NEPLYTELIUOJAMA, todėl atimama iš dažymo / plytelių). Žymima brūkšniuotu stačiakampiu su pavadinimu „SPINTELĖ"/„VONIA"/„DUŠO KABINA".

5. **Sienos bendri matmenys (`wall_total_width_mm`, `wall_total_height_mm`)** — sienos plotis ir aukštis (mm). Aukštis = patalpos aukštis (dažniausiai 2650 ar 2820 mm).

GRIEŽTOS TAISYKLĖS:
- Grąžink TIK strukturuotą JSON pagal pateiktą schemą. Jokio markdown'o.
- VISI matmenys MILIMETRAIS (jei brėžinyje cm/m — konvertuok).
- Jei matmuo neaiškus — palik `null`, NEMINTYJI.
- `nr` — KAMBARIO NUMERIS iš eksplikacijos (pvz., „107", „111"). Kiekviena išklotinė PRIKLAUSO konkrečiam kambariui. Ieškok numerio:
  • virš išklotinės grupės (pvz., „IŠKLOTINĖ 107", „107 — Vonia")
  • title block'e
  • šalia sienos žymėjimo (pvz., „107-A", „107-B" = kambario 107 sienos A ir B)
  • pateiktame kambarių sąraše (žiūrėk USER žinutę) — atitikink pavadinimą su numeriu
  Jei numeris MATOMAS bet kuriame šaltinyje — UŽPILDYK. `null` tik kai TIKRAI neradai.
- `room_name` — kambario pavadinimas (pvz., „Vonia 1", „Tėvų vonia", „Skalbykla"). Match'ink su sąrašu jei pateiktas.
- `wall_id` — vienetinis labelis kiekvienai sienai puslapyje. Naudok lygiai tokį, koks brėžinyje (A, B, C, D arba 1, 2, 3 arba "north"/"south"). Jei brėžinys grupuoja: „107-A, 107-B, 107-C, 107-D" — wall_id = "A"/"B"/"C"/"D", nr = "107".
- `confidence`:
  * `high` — visi matmenys aiškiai matomi su tiksliais skaičiais
  * `medium` — keli matmenys spėti iš proporcijos, ne visi anotuoti
  * `low` — brėžinys raster, neryškus, daug spėliojimo
"""


def _build_user_content(
    page_image_b64: str,
    page_idx: int,
    room_list: list[dict] | None = None,
) -> list[dict]:
    """Single-page user content: instruction + (optional) room list + image.

    When ``room_list`` is provided, the model is asked to ATTRIBUTE each
    elevation to a room by matching against this canonical list.
    """
    instructions = (
        f"Šitas yra puslapis {page_idx} su sienų išklotine(-ėmis). "
        f"Iš jo ištrauk visų matomų sienų zonų matmenis pagal pateiktą JSON schemą. "
        f"Grąžink VIENĄ JSON objektą su `wall_elevations[]` masyvu — po vieną įrašą per sieną."
    )
    if room_list:
        room_rows = "\n".join(
            f"  • nr={r.get('nr')!r}, name={(r.get('pavadinimas') or '')!r}, "
            f"paskirtis={r.get('paskirtis') or ''}"
            for r in room_list
        )
        instructions += (
            "\n\nKANONINIS KAMBARIŲ SĄRAŠAS — kiekviena išklotinė turi būti "
            "priskirta vienam iš šių kambarių:\n" + room_rows +
            "\n\nKai brėžinyje matai numerį arba pavadinimą, atitikink jį su "
            "šio sąrašo įrašu ir užpildyk `nr` lauką lygiai taip, kaip nurodyta "
            "viršuje (pvz., '107' o ne '107.', '02' o ne '2'). Vienai išklotinei "
            "PRIVALOMAI priskirk vieną nr arba palik null jei tikrai negali nustatyti."
        )
    return [
        {"type": "text", "text": instructions},
        {"type": "text", "text": json.dumps(PAGE_OUTPUT_SCHEMA, ensure_ascii=False, indent=2)},
        {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": page_image_b64}},
    ]


def _repair_json(text: str) -> str:
    """Same as eksplikacija_reader._repair_json — strip fences, quote bare keys."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        if text.endswith("```"):
            text = text[:-3]
    text = _re.sub(r'([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', text)
    text = _re.sub(r',(\s*[}\]])', r'\1', text)
    return text


def _extract_one_page(
    image_b64: str,
    page_idx: int,
    client: anthropic.Anthropic,
    room_list: list[dict] | None = None,
) -> dict | None:
    """Extract one wall_elevation page. Returns parsed dict or None on failure."""
    system = [
        {"type": "text", "text": SYSTEM_TEXT, "cache_control": {"type": "ephemeral"}}
    ]
    content = _build_user_content(image_b64, page_idx, room_list=room_list)

    last_err = None
    model = model_for("vision_pass1")  # resolved per-run (MODEL_OVERRIDE etc.)
    for attempt in range(3):
        try:
            with client.messages.stream(
                model=model,
                max_tokens=8192,  # one page = small output
                system=system,
                messages=[{"role": "user", "content": content}],
                output_config={"effort": "medium"},
            ) as stream:
                resp = stream.get_final_message()
            if resp.stop_reason in ("refusal", "max_tokens"):
                last_err = Exception(f"stop_reason={resp.stop_reason}")
                if attempt == 2:
                    break
                time.sleep(1.5 ** attempt)
                continue
            text = "".join(
                b.text for b in resp.content if getattr(b, "type", None) == "text"
            ).strip()
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                parsed = json.loads(_repair_json(text))
            # Attach token usage for cost tracking
            parsed["_usage"] = {
                "input_tokens": getattr(resp.usage, "input_tokens", 0) or 0,
                "output_tokens": getattr(resp.usage, "output_tokens", 0) or 0,
                "cache_read_tokens": getattr(resp.usage, "cache_read_input_tokens", 0) or 0,
            }
            return parsed
        except Exception as exc:
            last_err = exc
            if attempt == 2:
                break
            time.sleep(1.5 ** attempt)

    print(f"[wall_elevation] page {page_idx} extract failed after 3 attempts: {last_err}")
    return None


def extract_wall_elevations(
    pdf_bytes: bytes,
    client: anthropic.Anthropic,
    wall_elevation_pages: list[int],
    room_list: list[dict] | None = None,
) -> dict:
    """Per-page Vision extraction of sienų išklotinė data.

    Args:
        pdf_bytes: full PDF
        client: anthropic.Anthropic instance
        wall_elevation_pages: 1-indexed list of pages classified as wall_elevation
        room_list: optional canonical list of rooms (with nr + pavadinimas);
                   when provided, the model is asked to attribute each
                   elevation to a specific room nr from this list.

    Returns: dict per module docstring shape. Soft-fails per page.
    """
    t0 = time.time()
    out: dict[str, Any] = {
        "wall_elevations": [],
        "_meta": {
            "pages_processed": 0,
            "pages_failed": 0,
            "elapsed_s": 0.0,
            "input_tokens_total": 0,
            "output_tokens_total": 0,
            "cache_read_tokens_total": 0,
        },
    }

    if not wall_elevation_pages:
        out["_meta"]["elapsed_s"] = round(time.time() - t0, 2)
        return out

    # Render relevant pages at 300 DPI for legible mm dimensions
    try:
        all_pages = pdf_to_b64_images(pdf_bytes, dpi=300)
    except Exception as exc:
        out["_meta"]["error"] = f"pdf_to_images_failed: {exc}"
        out["_meta"]["elapsed_s"] = round(time.time() - t0, 2)
        return out

    # Map relevant page numbers to images (1-indexed)
    page_map = {p["page_index"]: p["image_b64"] for p in all_pages}

    for page_idx in wall_elevation_pages:
        image_b64 = page_map.get(page_idx)
        if not image_b64:
            out["_meta"]["pages_failed"] += 1
            continue
        result = _extract_one_page(image_b64, page_idx, client, room_list=room_list)
        if result is None:
            out["_meta"]["pages_failed"] += 1
            continue
        # Accumulate usage
        usage = result.pop("_usage", {})
        out["_meta"]["input_tokens_total"] += usage.get("input_tokens", 0)
        out["_meta"]["output_tokens_total"] += usage.get("output_tokens", 0)
        out["_meta"]["cache_read_tokens_total"] += usage.get("cache_read_tokens", 0)

        # Append wall elevation entries with page reference
        for we in (result.get("wall_elevations") or []):
            we["page"] = page_idx
            out["wall_elevations"].append(we)
        out["_meta"]["pages_processed"] += 1

    out["_meta"]["elapsed_s"] = round(time.time() - t0, 2)
    return out


# =============================================================================
# Smoke test (no Vision call)
# =============================================================================
if __name__ == "__main__":
    import inspect

    assert "extract_wall_elevations" in __all__
    assert callable(extract_wall_elevations)
    sig = inspect.signature(extract_wall_elevations)
    params = list(sig.parameters.keys())
    assert params == ["pdf_bytes", "client", "wall_elevation_pages"], (
        f"Unexpected signature: {params!r}"
    )

    # Schema sanity
    assert PAGE_OUTPUT_SCHEMA["properties"]["wall_elevations"]["items"]["required"] == [
        "wall_id", "tile_zones", "paint_zones", "niches", "furniture_zones",
    ]

    # _repair_json strips fences
    assert json.loads(_repair_json('```json\n{"a": 1,}\n```')) == {"a": 1}

    print("[wall_elevation] smoke test OK — module imports, signature, schema, json-repair verified.")
