"""Vision pass — symbol detection on electrical / plumbing / ventilation pages.

Reads point-symbols (sockets, switches, lights, water points, vents, etc.)
as ``{type, subtype, room_nr, x_pct, y_pct, confidence}`` and emits them in
a shape the Annotator can render directly. Useful for:

  - Annotator overlay (place symbols as draggable icons over the PDF)
  - Quantity counts (rozetės/jungtukai/šviestuvai/difūzoriai per room)
  - Quality signal for the eval — Objektas A contractor truth has explicit
    counts (113 rozetės/jungtukai, 38 priglaistomi šviestuvai, etc.)
"""

from __future__ import annotations

import base64
import json
from collections import Counter
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from ._cache import VisionCache, cache_key
from ..response_text import ModelStopped, read_answer, usage_meta
from .dimension_extractor import _detect_image_media_type

from models_config import model_for

REPO_ROOT = Path(__file__).resolve().parents[3]
PROMPT_PATH = REPO_ROOT / "prompts" / "symbol_detection.txt"

CANONICAL_TYPES = {
    "socket", "switch",
    "light_ceiling", "light_wall", "light_track",
    "data_outlet",
    "vent_supply", "vent_return",
    "thermostat",
    "water_cold", "water_hot", "drain", "wc_outlet",
    "other",
}


@dataclass
class Symbol:
    id: str
    type: str
    subtype: str | None
    room_nr: str | None
    x_pct: float
    y_pct: float
    confidence: str = "high"
    evidence: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SymbolPayload:
    page_role: str = "mixed"
    symbols: list[Symbol] = field(default_factory=list)
    _meta: dict[str, Any] = field(default_factory=dict)

    def counts_by_type(self) -> dict[str, int]:
        return dict(Counter(s.type for s in self.symbols))

    def counts_by_room(self) -> dict[str, dict[str, int]]:
        out: dict[str, dict[str, int]] = {}
        for s in self.symbols:
            room = s.room_nr or "_unassigned"
            out.setdefault(room, {}).setdefault(s.type, 0)
            out[room][s.type] += 1
        return out

    def to_dict(self) -> dict[str, Any]:
        return {
            "page_role": self.page_role,
            "symbols": [s.to_dict() for s in self.symbols],
            "counts_by_type": self.counts_by_type(),
            "counts_by_room": self.counts_by_room(),
            "_meta": self._meta,
        }


def parse_symbol_payload(raw: dict[str, Any]) -> SymbolPayload:
    if not isinstance(raw, dict):
        raise ValueError("expected dict at top level")
    out = SymbolPayload(page_role=str(raw.get("page_role") or "mixed"))
    for row in raw.get("symbols") or []:
        tipe = str(row.get("type") or "other").lower()
        if tipe not in CANONICAL_TYPES:
            tipe = "other"
        out.symbols.append(Symbol(
            id=str(row.get("id") or f"s{len(out.symbols) + 1}"),
            type=tipe,
            subtype=(str(row["subtype"]) if row.get("subtype") else None),
            room_nr=(str(row["room_nr"]) if row.get("room_nr") else None),
            x_pct=float(row.get("x_pct") or 0.0),
            y_pct=float(row.get("y_pct") or 0.0),
            confidence=str(row.get("confidence") or "high"),
            evidence=str(row.get("evidence") or "")[:120],
        ))
    return out


def _load_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def detect_symbols(
    *,
    image_b64: str,
    model: str | None = None,
    max_tokens: int = 32768,
    cache: VisionCache | None = None,
    no_cache: bool = False,
    client: Any | None = None,
) -> SymbolPayload:
    """Run the symbol-detection Vision pass on a single page image."""
    prompt = _load_prompt()
    img_bytes = base64.b64decode(image_b64)
    model = model or model_for("symbols")
    key = cache_key(img_bytes, prompt, model, str(max_tokens))

    if cache is None:
        cache = VisionCache(namespace="symbol_detection")

    if not no_cache:
        hit = cache.get(key)
        if hit is not None:
            out = parse_symbol_payload(hit)
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
                {"type": "text", "text": "Return the symbol list as JSON."},
            ],
        }],
    ) as stream:
        resp = stream.get_final_message()

    _, stopped = read_answer(resp, reader="symbol_detector")
    if stopped:  # refused / cut off: named, usage kept, never cached (2026-09-30)
        raise ModelStopped(stopped, {"cache": "miss", "key": key, **usage_meta(resp, model)})

    text = "".join(
        b.text for b in resp.content if getattr(b, "type", None) == "text"
    )
    payload = json.loads(text)
    cache.put(key, payload)

    out = parse_symbol_payload(payload)
    out._meta = {
        "cache": "miss",
        "key": key,
        "model": model,
        "input_tokens": getattr(resp.usage, "input_tokens", None),
        "output_tokens": getattr(resp.usage, "output_tokens", None),
    }
    return out
