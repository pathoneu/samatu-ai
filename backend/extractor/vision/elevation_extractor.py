"""Vision pass #3 — extract material zones (tile / paint / wood / mirror)
from wall-elevation pages (sienų išklotinės).

from models_config import model_for

Per CLAUDE.md §4 Section "Wall Development … MOST IMPORTANT FOR INTERIOR".
The output drives the tile_calculator, which produces exact per-room tile
area and paint area instead of the percentage-of-perimeter approximation
the current ``apdailos_breakdown`` path uses.

Status: scaffold + JSON parser. Live wiring lands when a Beržų-grade
fixture with elevation pages arrives (the Beržų PDF has elevation panels
on pages 11–16, but they're rendered in one of several formats and Phase 4
prompt-iteration is not yet done).
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from ._cache import VisionCache, cache_key
from .dimension_extractor import _detect_image_media_type

REPO_ROOT = Path(__file__).resolve().parents[3]
PROMPT_PATH = REPO_ROOT / "prompts" / "elevation_zones.txt"

# Allowed material tags. "opening" is a special pseudo-material that subtracts
# from both tile and paint area.
MATERIAL_TAGS = {
    "tile", "paint", "wood_panel", "wallpaper", "mirror", "stone",
    "opening", "other",
}


@dataclass
class ElevationZone:
    id: str
    material: str
    x_mm: float
    y_mm: float
    width_mm: float
    height_mm: float
    format_label: str | None = None
    confidence: str = "high"

    @property
    def area_m2(self) -> float:
        return (self.width_mm * self.height_mm) / 1_000_000.0


@dataclass
class ElevationPanel:
    panel_id: str
    room_nr: str
    wall_label: str
    wall_length_mm: float
    wall_height_mm: float
    zones: list[ElevationZone] = field(default_factory=list)

    @property
    def panel_area_m2(self) -> float:
        return (self.wall_length_mm * self.wall_height_mm) / 1_000_000.0


@dataclass
class ElevationPayload:
    page_role: str = "wall_elevation"
    panels: list[ElevationPanel] = field(default_factory=list)
    _meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "page_role": self.page_role,
            "panels": [{
                "panel_id": p.panel_id,
                "room_nr": p.room_nr,
                "wall_label": p.wall_label,
                "wall_length_mm": p.wall_length_mm,
                "wall_height_mm": p.wall_height_mm,
                "zones": [asdict(z) for z in p.zones],
            } for p in self.panels],
            "_meta": self._meta,
        }


def parse_elevation_payload(raw: dict[str, Any]) -> ElevationPayload:
    """Validate + coerce a Vision JSON response into typed records."""
    if not isinstance(raw, dict):
        raise ValueError("expected dict at top level")
    out = ElevationPayload(page_role=str(raw.get("page_role") or "wall_elevation"))
    for p in raw.get("panels") or []:
        panel = ElevationPanel(
            panel_id=str(p["panel_id"]),
            room_nr=str(p["room_nr"]),
            wall_label=str(p.get("wall_label") or ""),
            wall_length_mm=float(p.get("wall_length_mm") or 0),
            wall_height_mm=float(p.get("wall_height_mm") or 0),
        )
        for z in p.get("zones") or []:
            material = str(z.get("material") or "other").lower()
            if material not in MATERIAL_TAGS:
                material = "other"
            panel.zones.append(ElevationZone(
                id=str(z["id"]),
                material=material,
                x_mm=float(z.get("x_mm") or 0),
                y_mm=float(z.get("y_mm") or 0),
                width_mm=float(z.get("width_mm") or 0),
                height_mm=float(z.get("height_mm") or 0),
                format_label=(str(z["format_label"]) if z.get("format_label") else None),
                confidence=str(z.get("confidence") or "high"),
            ))
        _validate_panel_coverage(panel)
        out.panels.append(panel)
    return out


def _validate_panel_coverage(panel: ElevationPanel) -> None:
    """Soft check: zones (excl. opening) should approximately cover the panel.

    We allow a 2% slop because Vision's mm reads can drift by a few mm. If
    coverage is wildly off (<80% or >110%) we warn via _meta but don't raise
    — the tile_calculator still produces a useful number from whatever was
    extracted."""
    panel_area = panel.wall_length_mm * panel.wall_height_mm
    if panel_area <= 0:
        return
    covered = sum(
        z.width_mm * z.height_mm
        for z in panel.zones if z.material != "opening"
    )
    ratio = covered / panel_area
    if not (0.80 <= ratio <= 1.10):
        # Embed a warning into the panel; downstream can filter low-trust panels.
        panel.zones.append(ElevationZone(
            id=f"{panel.panel_id}-coverage_warning",
            material="other",
            x_mm=0, y_mm=0, width_mm=0, height_mm=0,
            confidence=f"coverage_ratio_{ratio:.2f}",
        ))


def _load_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def extract_elevation_zones(
    *,
    image_b64: str,
    model: str | None = None,
    max_tokens: int = 32768,
    cache: VisionCache | None = None,
    no_cache: bool = False,
    client: Any | None = None,
) -> ElevationPayload:
    """Vision pass 3: elevation material zones."""
    prompt = _load_prompt()
    img_bytes = base64.b64decode(image_b64)
    model = model or model_for("vision_pass1")
    key = cache_key(img_bytes, prompt, model, str(max_tokens))

    if cache is None:
        cache = VisionCache(namespace="elevation_zones")

    if not no_cache:
        hit = cache.get(key)
        if hit is not None:
            out = parse_elevation_payload(hit)
            out._meta = {**out._meta, "cache": "hit", "key": key, "model": model}
            return out

    if client is None:
        import anthropic
        client = anthropic.Anthropic(max_retries=1)

    media_type = _detect_image_media_type(img_bytes)
    with client.messages.stream(
        model=model,
        max_tokens=max_tokens,
        system=prompt,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": image_b64,
                    },
                },
                {"type": "text", "text": "Return the elevation zones as JSON."},
            ],
        }],
    ) as stream:
        resp = stream.get_final_message()

    text = "".join(
        b.text for b in resp.content if getattr(b, "type", None) == "text"
    )
    payload = json.loads(text)
    cache.put(key, payload)
    out = parse_elevation_payload(payload)
    out._meta = {
        "cache": "miss",
        "key": key,
        "model": model,
        "input_tokens": getattr(resp.usage, "input_tokens", None),
        "output_tokens": getattr(resp.usage, "output_tokens", None),
    }
    return out
