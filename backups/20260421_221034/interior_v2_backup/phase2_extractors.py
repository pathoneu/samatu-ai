"""
V2.1 Phase 2 — Specialized extractors.
Parallel Vision calls per page type, 10 tool schemas.
"""
import asyncio
import time
from typing import Any

from anthropic import Anthropic

from .tools import TOOL_FOR_PAGE_TYPE
from .prompts import (
    PHASE2_PARTITION_PROMPT,
    PHASE2_WALL_ELEVATIONS_PROMPT,
    PHASE2_CEILING_PROMPT,
    PHASE2_FLOOR_PROMPT,
    PHASE2_PLUMBING_PROMPT,
    PHASE2_ELECTRICAL_PROMPT,
    PHASE2_TILES_PROMPT,
    PHASE2_VENTILATION_PROMPT,
)

VISION_MODEL = "claude-opus-4-7"

_PROMPT_FOR_PAGE_TYPE: dict[str, str] = {
    "partition_plan": PHASE2_PARTITION_PROMPT,
    "wall_elevations": PHASE2_WALL_ELEVATIONS_PROMPT,
    "ceiling_plan": PHASE2_CEILING_PROMPT,
    "floor_plan": PHASE2_FLOOR_PROMPT,
    "plumbing_plan": PHASE2_PLUMBING_PROMPT,
    "electrical_plan": PHASE2_ELECTRICAL_PROMPT,
    "tiles_layout": PHASE2_TILES_PROMPT,
    "ventilation_plan": PHASE2_VENTILATION_PROMPT,
}

_client: Anthropic | None = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic()
    return _client


def _build_phase1_context(phase1: dict) -> str:
    rooms = phase1.get("patalpos", [])
    rooms_str = ", ".join(
        f"{r['nr']}: {r['pavadinimas']} ({r['plotas_m2']}m²)" for r in rooms[:15]
    )
    features = phase1.get("features", {})
    features_str = ", ".join(k for k, v in features.items() if v is True)
    return (
        "PROJECT CONTEXT:\n"
        f"- Complexity: {phase1.get('sudetingumo_klase', 'unknown')}\n"
        f"- Scope: {phase1.get('scope_type', 'full_project')}\n"
        f"- Total area: {phase1.get('bendras_plotas_m2', '?')} m² (excl. garage)\n"
        f"- Rooms ({len(rooms)}): {rooms_str}\n"
        f"- Ceiling height: {phase1.get('lubu_aukstis_m', 2.8)}m\n"
        f"- Special features: {features_str or 'none'}\n"
    )


def _call_extractor_sync(
    page: dict,
    page_type: str,
    phase1_context: str,
) -> dict | None:
    """Synchronous single-page extractor call."""
    tool = TOOL_FOR_PAGE_TYPE.get(page_type)
    prompt_template = _PROMPT_FOR_PAGE_TYPE.get(page_type)
    if not tool or not prompt_template:
        return None

    prompt = prompt_template.format(context=phase1_context)
    b64 = page.get("image_b64", "")
    if not b64:
        return None

    content = [
        {"type": "text", "text": prompt},
        {
            "type": "image",
            "source": {"type": "base64", "media_type": "image/jpeg", "data": b64},
        },
        {
            "type": "text",
            "text": f"[File: '{page['filename']}', page {page['page_idx']+1}]",
        },
    ]

    client = _get_client()
    for attempt in range(3):
        try:
            response = client.messages.create(
                model=VISION_MODEL,
                max_tokens=4096,
                tools=[tool],
                tool_choice={"type": "tool", "name": tool["name"]},
                messages=[{"role": "user", "content": content}],
            )
            for block in response.content:
                if block.type == "tool_use":
                    result = dict(block.input)
                    result["_page_type"] = page_type
                    result["_source"] = f"{page['filename']}:{page['page_idx']+1}"
                    return result
            return None
        except Exception:
            if attempt == 2:
                return None
            time.sleep(2 ** attempt)
    return None


async def phase2_extract_page(
    page: dict,
    page_type: str,
    phase1_context: str,
) -> dict | None:
    """Async wrapper for single page extraction."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, _call_extractor_sync, page, page_type, phase1_context
    )


async def phase2_extract_all(
    classified_pages: list[dict],
    phase1: dict,
) -> list[dict]:
    """
    Extract from all classified pages in parallel.
    Returns list of raw extractor results.
    """
    phase1_context = _build_phase1_context(phase1)

    tasks = []
    for page in classified_pages:
        page_type = page.get("page_type", "unknown")
        if page_type in TOOL_FOR_PAGE_TYPE:
            tasks.append(phase2_extract_page(page, page_type, phase1_context))

    results = await asyncio.gather(*tasks)
    return [r for r in results if r is not None]


def merge_phase2_results(results: list[dict]) -> dict:
    """
    Merge multiple Phase 2 results into a single dict.

    Strategy:
    - paint_items, gkp_items, items arrays: concatenate, deduplicate by (kategorija, room_nr)
    - Numeric top-level fields: sum
    - boolean flags: OR
    - Last-wins for non-array/non-numeric fields
    """
    merged: dict[str, Any] = {
        "paint_items": [],
        "gkp_items": [],
        "floor_items": [],
        "plumbing_items": [],
        "electrical_items": [],
        "tiles_items": [],
        "ventilation_items": [],
        "special_works_items": [],
        "site_overhead_items": [],
        "partition_data": None,
        "wall_sections": [],
    }

    partition_results = []

    for r in results:
        ptype = r.get("_page_type", "")

        if ptype == "wall_elevations":
            merged["paint_items"].extend(r.get("paint_items", []))
            merged["gkp_items"].extend(r.get("gkp_items", []))

        elif ptype == "partition_plan":
            partition_results.append(r)
            if r.get("wall_sections"):
                merged["wall_sections"].extend(r["wall_sections"])

        elif ptype == "ceiling_plan":
            merged["gkp_items"].extend(r.get("items", []))

        elif ptype == "floor_plan":
            merged["floor_items"].extend(r.get("items", []))

        elif ptype == "plumbing_plan":
            merged["plumbing_items"].extend(r.get("items", []))

        elif ptype == "electrical_plan":
            merged["electrical_items"].extend(r.get("items", []))

        elif ptype == "tiles_layout":
            merged["tiles_items"].extend(r.get("items", []))

        elif ptype == "ventilation_plan":
            merged["ventilation_items"].extend(r.get("items", []))
            if r.get("has_detailed_hvac_plan"):
                merged["has_detailed_hvac_plan"] = True

    # Use best partition result (highest corner count = most detail)
    if partition_results:
        best = max(partition_results, key=lambda x: x.get("visu_kampu_vnt", 0))
        merged["partition_data"] = best

    # Deduplicate item arrays
    for key in ["paint_items", "gkp_items", "floor_items", "plumbing_items",
                "electrical_items", "tiles_items", "ventilation_items"]:
        merged[key] = _dedup_items(merged[key])

    return merged


def _dedup_items(items: list[dict]) -> list[dict]:
    """
    Deduplicate by (kategorija, room_nr).
    When duplicates found, keep the one with higher kiekis.
    """
    seen: dict[tuple, dict] = {}
    for item in items:
        key = (item.get("kategorija", ""), item.get("room_nr", None))
        if key not in seen:
            seen[key] = item
        else:
            existing = seen[key]
            if item.get("kiekis", 0) > existing.get("kiekis", 0):
                seen[key] = item
    return list(seen.values())
