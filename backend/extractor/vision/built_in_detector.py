"""Vision pass — detect built-in furniture that excludes wall paint area.

Per the council R3 verdict: the residual +4.15 m² wall overshoot on Objektas A
is most likely a built-in wardrobe / kitchen cabinet / shower cubicle
that the contractor excludes from paint area. This module reads a
furniture-layout page (BALDŲ PLANAS) and emits the per-wall built-in
list the calculator can subtract from walls_paintable.

Output shape is room-keyed; downstream consumer accumulates the per-
room sum and either:
  a) subtracts directly from walls_paintable (overlay correction), OR
  b) emits an ``extra_walls_m2`` negative override.

Initial integration uses (a) for simplicity.
"""

from __future__ import annotations

import base64
import json
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from ._cache import VisionCache, cache_key
from ..response_text import ModelStopped, read_answer, usage_meta
from .dimension_extractor import _detect_image_media_type, _decode_response_json

from models_config import model_for

REPO_ROOT = Path(__file__).resolve().parents[3]
PROMPT_PATH = REPO_ROOT / "prompts" / "built_in_furniture.txt"

CANONICAL_TYPES = {
    "wardrobe", "kitchen_cabinet_run", "shower_cubicle",
    "bathtub_apron", "bathroom_vanity", "fixed_shelving", "other",
}


@dataclass
class BuiltIn:
    id: str
    type: str
    room_nr: str | None
    wall_label: str | None
    width_mm: float
    height_mm: float
    confidence: str = "high"
    evidence: str = ""

    @property
    def excluded_area_m2(self) -> float:
        return (self.width_mm * self.height_mm) / 1_000_000.0


@dataclass
class BuiltInPayload:
    page_role: str = "furniture_layout"
    built_ins: list[BuiltIn] = field(default_factory=list)
    _meta: dict[str, Any] = field(default_factory=dict)

    def per_room_excluded_m2(self) -> dict[str, float]:
        out: dict[str, float] = defaultdict(float)
        for b in self.built_ins:
            if b.room_nr:
                out[b.room_nr] += b.excluded_area_m2
        return dict(out)

    def to_dict(self) -> dict[str, Any]:
        return {
            "page_role": self.page_role,
            "built_ins": [asdict(b) for b in self.built_ins],
            "per_room_excluded_m2": self.per_room_excluded_m2(),
            "_meta": self._meta,
        }


def parse_built_in_payload(raw: dict[str, Any]) -> BuiltInPayload:
    if not isinstance(raw, dict):
        raise ValueError("expected dict at top level")
    out = BuiltInPayload(page_role=str(raw.get("page_role") or "furniture_layout"))
    for row in raw.get("built_ins") or []:
        tipe = str(row.get("type") or "other").lower()
        if tipe not in CANONICAL_TYPES:
            tipe = "other"
        out.built_ins.append(BuiltIn(
            id=str(row.get("id") or f"f{len(out.built_ins) + 1}"),
            type=tipe,
            room_nr=(str(row["room_nr"]) if row.get("room_nr") else None),
            wall_label=(str(row["wall_label"]) if row.get("wall_label") else None),
            width_mm=float(row.get("width_mm") or 0),
            height_mm=float(row.get("height_mm") or 0),
            confidence=str(row.get("confidence") or "high"),
            evidence=str(row.get("evidence") or "")[:120],
        ))
    return out


def _load_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def detect_built_ins(
    *,
    image_b64: str,
    model: str | None = None,
    max_tokens: int = 8192,
    cache: VisionCache | None = None,
    no_cache: bool = False,
    client: Any | None = None,
) -> BuiltInPayload:
    """Run the built-in detector Vision pass on a single furniture-layout page."""
    prompt = _load_prompt()
    img_bytes = base64.b64decode(image_b64)
    model = model or model_for("vision_pass1")
    key = cache_key(img_bytes, prompt, model, str(max_tokens))

    if cache is None:
        cache = VisionCache(namespace="built_in_furniture")

    if not no_cache:
        hit = cache.get(key)
        if hit is not None:
            out = parse_built_in_payload(hit)
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
                {"type": "image",
                 "source": {"type": "base64", "media_type": media_type, "data": image_b64}},
                {"type": "text", "text": "Return the built-in fixtures list as JSON."},
            ],
        }],
    ) as stream:
        resp = stream.get_final_message()

    _, stopped = read_answer(resp, reader="built_in_detector")
    if stopped:  # refused / cut off: named, usage kept, never cached (2026-09-30)
        raise ModelStopped(stopped, {"cache": "miss", "key": key, **usage_meta(resp, model)})

    text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
    payload = _decode_response_json(text)
    cache.put(key, payload)

    out = parse_built_in_payload(payload)
    out._meta = {
        "cache": "miss",
        "key": key,
        "model": model,
        "input_tokens": getattr(resp.usage, "input_tokens", None),
        "output_tokens": getattr(resp.usage, "output_tokens", None),
    }
    return out


def apply_built_in_exclusions(
    parsed: dict[str, Any],
    built_ins: BuiltInPayload,
) -> dict[str, Any]:
    """Subtract built-in fixture wall area from each room's walls_paintable
    via the existing ``extra_walls_m2`` primitive (negative value)."""
    excl = built_ins.per_room_excluded_m2()
    by_nr = {str(r.get("nr")): r for r in (parsed.get("patalpos") or [])}
    for nr, m2 in excl.items():
        room = by_nr.get(str(nr))
        if not room:
            continue
        # Add negative extra to drop walls_paintable by the excluded area.
        # The existing engine adds extra_walls_m2 directly to walls_paintable;
        # a negative value subtracts (clipped at 0 elsewhere).
        prev = float(room.get("extra_walls_m2") or 0)
        room["extra_walls_m2"] = prev - m2
        room.setdefault("_built_in_exclusions_m2", 0.0)
        room["_built_in_exclusions_m2"] += m2
    return parsed
