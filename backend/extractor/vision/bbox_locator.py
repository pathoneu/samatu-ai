"""Vision pass — emit a tight axis-aligned bbox per labeled room.

Cheap single call ($~0.13) that fills the gap left by the existing
eksplikacija reader: that pass returns room areas and names but rarely
returns per-room polygons / bboxes. Without bboxes, the per-room zoom
pipeline can only process the one room (102) that happens to have a
bbox in the to-the-dot extract. This pass produces bboxes for all
rooms so per-room zoom scales.

The output integrates directly into existing ``patalpos`` records by
setting ``room.bbox_pct = {x, y, w, h}`` to match what
``_crop_room_image`` consumes.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ._cache import VisionCache, cache_key
from .dimension_extractor import _detect_image_media_type, _decode_response_json

REPO_ROOT = Path(__file__).resolve().parents[3]
PROMPT_PATH = REPO_ROOT / "prompts" / "room_bbox.txt"


@dataclass
class RoomBBox:
    nr: str
    name: str
    bbox_pct: dict[str, float]   # {x_min, y_min, x_max, y_max}
    confidence: str = "high"

    def to_crop_bbox(self) -> dict[str, float]:
        """Convert to the {x, y, w, h} shape the cropper expects."""
        return {
            "x": float(self.bbox_pct["x_min"]),
            "y": float(self.bbox_pct["y_min"]),
            "w": float(self.bbox_pct["x_max"] - self.bbox_pct["x_min"]),
            "h": float(self.bbox_pct["y_max"] - self.bbox_pct["y_min"]),
        }


@dataclass
class RoomBBoxList:
    rooms: list[RoomBBox] = field(default_factory=list)
    _meta: dict[str, Any] = field(default_factory=dict)

    def by_nr(self) -> dict[str, RoomBBox]:
        return {r.nr: r for r in self.rooms}


def parse_bbox_payload(raw: dict[str, Any]) -> RoomBBoxList:
    if not isinstance(raw, dict):
        raise ValueError("expected dict at top level")
    out = RoomBBoxList()
    for row in raw.get("rooms") or []:
        bb = row.get("bbox_pct") or row.get("bbox") or {}
        try:
            normalised = {
                "x_min": float(bb["x_min"]),
                "y_min": float(bb["y_min"]),
                "x_max": float(bb["x_max"]),
                "y_max": float(bb["y_max"]),
            }
        except (KeyError, TypeError, ValueError):
            continue
        # Order + range guard
        if not (0 <= normalised["x_min"] < normalised["x_max"] <= 1 and
                0 <= normalised["y_min"] < normalised["y_max"] <= 1):
            continue
        out.rooms.append(RoomBBox(
            nr=str(row["nr"]),
            name=str(row.get("name") or ""),
            bbox_pct=normalised,
            confidence=str(row.get("confidence") or "high"),
        ))
    return out


def _load_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def extract_room_bboxes(
    *,
    image_b64: str,
    model: str = "claude-opus-4-8",
    max_tokens: int = 8192,
    cache: VisionCache | None = None,
    no_cache: bool = False,
    client: Any | None = None,
) -> RoomBBoxList:
    """Run the bbox-locator Vision pass on a single floor-plan page."""
    prompt = _load_prompt()
    img_bytes = base64.b64decode(image_b64)
    key = cache_key(img_bytes, prompt, model, str(max_tokens))

    if cache is None:
        cache = VisionCache(namespace="room_bbox")

    if not no_cache:
        hit = cache.get(key)
        if hit is not None:
            out = parse_bbox_payload(hit)
            out._meta = {**out._meta, "cache": "hit", "key": key, "model": model}
            return out

    if client is None:
        import anthropic
        client = anthropic.Anthropic()

    media_type = _detect_image_media_type(img_bytes)
    with client.messages.stream(
        model=model,
        max_tokens=max_tokens,
        system=prompt,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image",
                 "source": {"type": "base64", "media_type": media_type, "data": image_b64}},
                {"type": "text", "text": "Return the per-room bbox list as JSON."},
            ],
        }],
    ) as stream:
        resp = stream.get_final_message()

    text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
    payload = _decode_response_json(text)
    cache.put(key, payload)

    out = parse_bbox_payload(payload)
    out._meta = {
        "cache": "miss",
        "key": key,
        "model": model,
        "input_tokens": getattr(resp.usage, "input_tokens", None),
        "output_tokens": getattr(resp.usage, "output_tokens", None),
    }
    return out


def merge_into_patalpos(
    parsed: dict[str, Any],
    bboxes: RoomBBoxList,
) -> int:
    """Set ``room.bbox_pct`` on each patalpa that the bbox-locator found.
    Existing bbox_pct (with non-null value) is preserved (don't overwrite
    known-good data). Returns number of rooms newly populated."""
    by_nr = bboxes.by_nr()
    n = 0
    for room in parsed.get("patalpos") or []:
        nr = str(room.get("nr") or "")
        if room.get("bbox_pct"):
            continue
        bb = by_nr.get(nr)
        if not bb:
            continue
        room["bbox_pct"] = bb.to_crop_bbox()
        n += 1
    return n
