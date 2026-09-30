"""Vision pass #1 — extract every dimension annotation on a floor plan page.

Returns a list of ``Dimension`` records. Pure I/O wrapper around the prompt at
``prompts/dimension_list.txt`` plus JSON parsing & validation. The Vision call
is cached on disk; identical (image, prompt, model) triples are free after the
first run.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Iterable

from ._cache import VisionCache, cache_key
from ..response_text import ModelStopped, read_answer, usage_meta

from models_config import model_for

REPO_ROOT = Path(__file__).resolve().parents[3]
PROMPT_PATH = REPO_ROOT / "prompts" / "dimension_list.txt"


@dataclass
class Dimension:
    id: str
    text: str
    value_mm: float | None
    x_pct: float
    y_pct: float
    orientation: str
    pixel_start_pct: list[float] | None = None
    pixel_end_pct: list[float] | None = None
    confidence: str = "high"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Dimension":
        return cls(
            id=str(raw["id"]),
            text=str(raw.get("text", "")),
            value_mm=(None if raw.get("value_mm") is None else float(raw["value_mm"])),
            x_pct=float(raw.get("x_pct") or 0.0),
            y_pct=float(raw.get("y_pct") or 0.0),
            orientation=str(raw.get("orientation") or "horizontal"),
            pixel_start_pct=raw.get("pixel_start_pct"),
            pixel_end_pct=raw.get("pixel_end_pct"),
            confidence=str(raw.get("confidence") or "high"),
        )


@dataclass
class DimensionList:
    dimensions: list[Dimension] = field(default_factory=list)
    _meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "dimensions": [d.to_dict() for d in self.dimensions],
            "_meta": self._meta,
        }


def _load_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def _decode_response_json(text: str) -> dict[str, Any]:
    """Robust JSON decode for model output.

    Tolerates: code-fenced output (```json…```), leading/trailing prose,
    UTF-8 BOMs. Falls back to extracting the first top-level JSON object
    via brace-matching when straight ``json.loads`` fails.
    """
    if not text:
        raise ValueError("empty model response")
    s = text.strip().lstrip("﻿")
    # Strip code fences
    if s.startswith("```"):
        # ```json or ``` + newline at start, ``` at end
        s = s.split("\n", 1)[-1] if "\n" in s else s
        if s.endswith("```"):
            s = s[: -3]
        s = s.strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    # Brace-balance fallback — find the first '{' then walk to the matching '}'
    start = s.find("{")
    if start == -1:
        raise ValueError("no JSON object in response")
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(s)):
        ch = s[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                candidate = s[start: i + 1]
                return json.loads(candidate)
    raise ValueError("unbalanced JSON object in response")


def _detect_image_media_type(img_bytes: bytes) -> str:
    """Sniff a base64-decoded image's media type from the first few bytes.
    Anthropic accepts image/png, image/jpeg, image/webp, image/gif."""
    if img_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if img_bytes[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if img_bytes[:4] == b"RIFF" and img_bytes[8:12] == b"WEBP":
        return "image/webp"
    if img_bytes[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    return "image/png"  # default


def parse_dimension_payload(raw_json: dict[str, Any]) -> DimensionList:
    """Convert Vision JSON → typed DimensionList, raising on malformed input.

    Filters out implausible entries that slipped through despite the prompt:
      - value_mm <= 0 (room numbers parsed as length, or genuine zero-lengths)
      - x_pct / y_pct outside [0, 1] (mis-positioned text)
      - duplicate IDs (model retry with same numbering — first wins)
    Filtered entries are recorded in _meta.filtered so they're auditable.
    """
    if not isinstance(raw_json, dict):
        raise ValueError("expected dict at top level")
    items = raw_json.get("dimensions")
    if items is None:
        # Some models wrap responses; tolerate raw lists too.
        if isinstance(raw_json, list):
            items = raw_json
        else:
            raise ValueError("missing 'dimensions' array")
    out = DimensionList()
    seen_ids: set[str] = set()
    filtered: list[dict[str, Any]] = []
    for raw in items:
        d = Dimension.from_dict(raw)
        if d.id in seen_ids:
            filtered.append({"id": d.id, "reason": "duplicate_id"})
            continue
        # Drop value_mm that's a level marker (orientation="level") OR zero/negative
        # length on a horizontal/vertical/diagonal dimension.
        if d.orientation in ("horizontal", "vertical", "diagonal"):
            if d.value_mm is None or d.value_mm <= 0:
                filtered.append({"id": d.id, "reason": "non_positive_value_mm"})
                continue
            # Sanity: a real LT dimension is between 50 mm (door jamb) and
            # 100 000 mm (a 100 m building edge). Outside that → almost
            # certainly a room number or area label.
            if not (50 <= d.value_mm <= 100_000):
                filtered.append({"id": d.id, "reason": f"value_mm_out_of_range({d.value_mm})"})
                continue
        # Coordinate sanity. Allow a small overhang (model occasionally clamps
        # at 1.01) but reject hard out-of-page coords.
        if not (-0.05 <= d.x_pct <= 1.05 and -0.05 <= d.y_pct <= 1.05):
            filtered.append({"id": d.id, "reason": "coords_out_of_range"})
            continue
        seen_ids.add(d.id)
        out.dimensions.append(d)
    if filtered:
        out._meta = {**out._meta, "filtered": filtered}
    return out


def extract_dimensions(
    *,
    image_b64: str,
    model: str | None = None,
    max_tokens: int = 32768,
    cache: VisionCache | None = None,
    no_cache: bool = False,
    client: Any | None = None,
) -> DimensionList:
    """Vision pass 1: dimension list.

    Parameters
    ----------
    image_b64 : str
        PNG base64 string for the floor plan page. The caller is responsible
        for rasterising the right page at a useful DPI (≥200).
    model : str
        Anthropic model id. None resolves model_for("vision_pass1") at call time.
    cache, no_cache : VisionCache | bool
        File cache controls. ``no_cache=True`` forces a fresh API call (used by
        determinism tests).
    client : anthropic.Anthropic | None
        Optional pre-constructed Anthropic client (so tests/notebooks can pass
        a stub). When None, the function constructs ``anthropic.Anthropic()``.

    Returns
    -------
    DimensionList
        Typed list. ``_meta`` carries usage and cache stats.
    """
    prompt = _load_prompt()
    img_bytes = base64.b64decode(image_b64)
    model = model or model_for("vision_pass1")
    key = cache_key(img_bytes, prompt, model, str(max_tokens))

    if cache is None:
        cache = VisionCache(namespace="dimension_list")

    if not no_cache:
        hit = cache.get(key)
        if hit is not None:
            out = parse_dimension_payload(hit)
            out._meta = {**out._meta, "cache": "hit", "key": key, "model": model}
            return out

    # Live API call ────────────────────────────────────────────────────────────
    if client is None:
        import anthropic  # local import: tests don't need anthropic installed
        client = anthropic.Anthropic(max_retries=1)

    # pdf_to_b64_images emits JPEG; auto-detect to stay flexible.
    media_type = _detect_image_media_type(img_bytes)
    # Anthropic SDK requires streaming when max_tokens may take >10min.
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
                {"type": "text", "text": "Return the dimension list as JSON."},
            ],
        }],
    ) as stream:
        resp = stream.get_final_message()

    _, stopped = read_answer(resp, reader="dimension_extractor")
    if stopped:  # refused / cut off: named, usage kept, never cached (2026-09-30)
        raise ModelStopped(stopped, {"cache": "miss", "key": key, **usage_meta(resp, model)})

    text = "".join(
        b.text for b in resp.content if getattr(b, "type", None) == "text"
    )
    payload = _decode_response_json(text)
    cache.put(key, payload)
    out = parse_dimension_payload(payload)
    out._meta = {
        "cache": "miss",
        "key": key,
        "model": model,
        "input_tokens": getattr(resp.usage, "input_tokens", None),
        "output_tokens": getattr(resp.usage, "output_tokens", None),
    }
    return out


# ── Calibration helper ────────────────────────────────────────────────────────
def compute_scale_mm_per_pct(
    dimensions: Iterable[Dimension],
    image_pixel_width: int,
    image_pixel_height: int,
) -> float | None:
    """Median mm/pct ratio from dimensions with usable line endpoints.

    Returns the page-scale factor (mm per fractional unit of image width).
    Use this when the room_graph reports vertex positions in pct: the
    distance between two vertices times this factor gives mm.

    None if there are not enough usable dimensions (< 3).
    """
    ratios: list[float] = []
    for d in dimensions:
        if d.value_mm is None or d.value_mm <= 0:
            continue
        s = d.pixel_start_pct
        e = d.pixel_end_pct
        if not (s and e and len(s) == 2 and len(e) == 2):
            continue
        # Convert pct deltas to pixel-equivalent magnitude using the image's
        # actual pixel dimensions, then normalise back to a single unit per
        # image-width fraction so room-graph vertex pct deltas are directly
        # usable.
        dx_px = (e[0] - s[0]) * image_pixel_width
        dy_px = (e[1] - s[1]) * image_pixel_height
        pixel_len = (dx_px * dx_px + dy_px * dy_px) ** 0.5
        if pixel_len < 10:
            continue
        # mm per pixel
        ratios.append(d.value_mm / pixel_len)
    if len(ratios) < 3:
        return None
    ratios.sort()
    mid = len(ratios) // 2
    if len(ratios) % 2:
        return ratios[mid]
    return 0.5 * (ratios[mid - 1] + ratios[mid])
