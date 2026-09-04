"""Ceiling-height Vision pass.

Per the 2026-06-01 user spec: the production pipeline often defaults
ceiling height to 2.82 m when the eksplikacija doesn't carry it. This
under-extracts walls_paintable when the real height differs (e.g.,
objektas_c where actual height appears to be ~3.0 m).

This module reads the title block / section / general notes / eksplikacija
of a project PDF and returns the canonical ceiling height(s).
"""

from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from ._cache import VisionCache, cache_key
from .dimension_extractor import _detect_image_media_type, _decode_response_json

from models_config import model_for

REPO_ROOT = Path(__file__).resolve().parents[3]
PROMPT_PATH = REPO_ROOT / "prompts" / "ceiling_height.txt"


@dataclass
class HeightPayload:
    ceiling_heights_m: list[float] = field(default_factory=list)
    primary_value_m: float | None = None
    source_quote: str = ""
    confidence: str = "low"
    per_room: dict[str, float] = field(default_factory=dict)
    _meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def parse_height_payload(raw: dict[str, Any]) -> HeightPayload:
    if not isinstance(raw, dict):
        raise ValueError("expected dict at top level")
    heights = []
    for v in raw.get("ceiling_heights_m") or []:
        try:
            heights.append(float(v))
        except (TypeError, ValueError):
            continue
    primary = raw.get("primary_value_m")
    try:
        primary = float(primary) if primary is not None else None
    except (TypeError, ValueError):
        primary = None
    per_room: dict[str, float] = {}
    for k, v in (raw.get("per_room") or {}).items():
        try:
            per_room[str(k)] = float(v)
        except (TypeError, ValueError):
            continue
    return HeightPayload(
        ceiling_heights_m=heights,
        primary_value_m=primary,
        source_quote=str(raw.get("source_quote") or "")[:200],
        confidence=str(raw.get("confidence") or "low"),
        per_room=per_room,
    )


def _load_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def extract_ceiling_height(
    *,
    image_b64: str,
    model: str | None = None,
    max_tokens: int = 2048,
    cache: VisionCache | None = None,
    no_cache: bool = False,
    client: Any | None = None,
) -> HeightPayload:
    prompt = _load_prompt()
    img_bytes = base64.b64decode(image_b64)
    model = model or model_for("vision_pass1")
    key = cache_key(img_bytes, prompt, model, str(max_tokens))

    if cache is None:
        cache = VisionCache(namespace="ceiling_height")

    if not no_cache:
        hit = cache.get(key)
        if hit is not None:
            out = parse_height_payload(hit)
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
                {"type": "text",
                 "text": "Return the ceiling-height JSON object."},
            ],
        }],
    ) as stream:
        resp = stream.get_final_message()

    text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
    payload = _decode_response_json(text)
    cache.put(key, payload)

    out = parse_height_payload(payload)
    out._meta = {
        "cache": "miss",
        "key": key,
        "model": model,
        "input_tokens": getattr(resp.usage, "input_tokens", None),
        "output_tokens": getattr(resp.usage, "output_tokens", None),
    }
    return out


# Plausibility bands. A PROJECT-WIDE primary above 4.0 m is a misread
# (no LT interior has every ceiling that tall). A NAMED per-room reading
# may legitimately reach a double-height interior (objektas_b svetainė
# ≈5.7 m) — same 6.5 m ceiling the warnings[] narration salvage accepts.
PRIMARY_PLAUSIBLE_M = (2.4, 4.0)
PER_ROOM_PLAUSIBLE_M = (2.4, 6.5)  # keep in sync with height_markers.MAX_NARRATED_CEILING_M

_COMPOUND_SPLIT_RE = re.compile(r"[/,+]")


def _norm_nr(raw: Any) -> str:
    s = str(raw or "").strip()
    if s.isdigit():
        return s.lstrip("0") or "0"
    return s.lower()


_NR_PREFIX_RE = re.compile(r"^(\d+)\s+(.+)$")


def _per_room_lookup(room: dict[str, Any],
                     per_room: dict[str, float]) -> float | None:
    """Match a room against per_room keys: by nr ('2' matches '02'), by
    full name (case-insensitive), by nr-prefixed key ('101 Tambūras' —
    the format Vision actually emits off eksplikacija tables), or by
    compound-name component — the eksplikacija says
    'Svetainė/valgomasis/virtuvė' while Vision names just 'Svetainė'
    (same aliasing the warnings salvage needs)."""
    nr = _norm_nr(room.get("nr"))
    name = str(room.get("pavadinimas") or "").strip().lower()
    name_parts = {p.strip() for p in _COMPOUND_SPLIT_RE.split(name)
                  if len(p.strip()) >= 5}
    for k, v in per_room.items():
        key = str(k).strip()
        key_lc = key.lower()
        # 'nr name' concatenated keys: match the nr part alone.
        m = _NR_PREFIX_RE.match(key)
        key_nr = _norm_nr(m.group(1)) if m else _norm_nr(key)
        if m:
            key_lc = m.group(2).strip().lower()
        if nr and key_nr == nr:
            return v
        if name and key_lc == name:
            return v
        key_parts = {p.strip() for p in _COMPOUND_SPLIT_RE.split(key_lc)
                     if len(p.strip()) >= 5}
        if name_parts & ({key_lc} | key_parts) or (name and name in key_parts):
            return v
    return None


def apply_height_to_rooms(rooms: list[dict[str, Any]],
                          height: HeightPayload) -> dict[str, Any]:
    """Apply the extracted ceiling height to rooms.

    Strategy:
      • If ``per_room`` map is populated, use it where it matches by nr,
        name, or compound-name component. Per-room values are plausible
        up to 6.5 m (double-height interiors are real).
      • Else if ``primary_value_m`` is set, replace every room's
        ``lubu_aukstis_m`` ONLY when it differs by >5cm AND the new
        value is within the project-wide plausible range (2.4–4.0 m).
      • Track which rooms were updated for the audit trail.
    """
    summary = {"n_rooms_updated": 0, "from_to": [], "skipped_implausible": []}
    if not height.primary_value_m and not height.per_room:
        return summary
    for r in rooms:
        nr = str(r.get("nr") or "")
        new_h: float | None = None
        per_room_hit = _per_room_lookup(r, height.per_room) if height.per_room else None
        if per_room_hit is not None:
            new_h = per_room_hit
            lo, hi = PER_ROOM_PLAUSIBLE_M
        elif height.primary_value_m is not None:
            new_h = height.primary_value_m
            lo, hi = PRIMARY_PLAUSIBLE_M
        if new_h is None:
            continue
        if not (lo <= new_h <= hi):
            summary["skipped_implausible"].append({"nr": nr, "value": new_h})
            continue
        old_h = float(r.get("lubu_aukstis_m") or 0)
        if abs(new_h - old_h) >= 0.05:
            r["lubu_aukstis_m"] = round(new_h, 2)
            r["_lubu_aukstis_source"] = "height_extractor"
            summary["from_to"].append({"nr": nr, "from": old_h, "to": new_h})
            summary["n_rooms_updated"] += 1
    return summary
