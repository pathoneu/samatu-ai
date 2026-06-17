"""Vision pass — door/window schedule (Durų ir langų lentelė) extractor.

When a schedule page is present, this gives exact per-opening dimensions and
exterior/interior flags that override the per-element guesses Vision makes
in the floor-plan pass. Downstream:

  - ``plan_assembler._resolve_opening`` looks up ``schedule_ref`` in the
    parsed schedule and uses the table values (already supported as of
    Phase 2).
  - ``vision_call._elementai_to_counts`` will trust the schedule's
    ``is_exterior`` flag in preference to ``_exterior`` on elementai.

The output of ``extract_schedule`` is the same shape the plan_assembler
already expects: ``{"durys": [{id, width_mm, height_mm, ...}], "langai":
[...]}``.
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
PROMPT_PATH = REPO_ROOT / "prompts" / "schedule.txt"


@dataclass
class ScheduleEntry:
    id: str
    width_mm: float
    height_mm: float
    count: int = 1
    is_exterior: bool = False
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Schedule:
    durys: list[ScheduleEntry] = field(default_factory=list)
    langai: list[ScheduleEntry] = field(default_factory=list)
    _meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "durys": [e.to_dict() for e in self.durys],
            "langai": [e.to_dict() for e in self.langai],
            "_meta": self._meta,
        }


def parse_schedule_payload(raw: dict[str, Any]) -> Schedule:
    if not isinstance(raw, dict):
        raise ValueError("expected dict at top level")
    s = Schedule()
    for row in raw.get("durys") or []:
        s.durys.append(_parse_row(row))
    for row in raw.get("langai") or []:
        s.langai.append(_parse_row(row))
    return s


def _parse_row(row: dict[str, Any]) -> ScheduleEntry:
    return ScheduleEntry(
        id=str(row["id"]),
        width_mm=float(row.get("width_mm") or 0),
        height_mm=float(row.get("height_mm") or 0),
        count=int(row.get("count") or 1),
        is_exterior=bool(row.get("is_exterior", False)),
        notes=(str(row["notes"]) if row.get("notes") else None),
    )


def _load_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def extract_schedule(
    *,
    image_b64: str,
    model: str = "claude-opus-4-8",
    max_tokens: int = 32768,
    cache: VisionCache | None = None,
    no_cache: bool = False,
    client: Any | None = None,
) -> Schedule:
    """Run the schedule extractor on a single page image.

    The caller is responsible for finding the schedule page (page_classifier
    or manual selection).
    """
    prompt = _load_prompt()
    img_bytes = base64.b64decode(image_b64)
    key = cache_key(img_bytes, prompt, model, str(max_tokens))

    if cache is None:
        cache = VisionCache(namespace="schedule")

    if not no_cache:
        hit = cache.get(key)
        if hit is not None:
            out = parse_schedule_payload(hit)
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
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": image_b64,
                    },
                },
                {"type": "text", "text": "Return the schedule as JSON."},
            ],
        }],
    ) as stream:
        resp = stream.get_final_message()

    text = "".join(
        b.text for b in resp.content if getattr(b, "type", None) == "text"
    )
    payload = json.loads(text)
    cache.put(key, payload)
    out = parse_schedule_payload(payload)
    out._meta = {
        "cache": "miss",
        "key": key,
        "model": model,
        "input_tokens": getattr(resp.usage, "input_tokens", None),
        "output_tokens": getattr(resp.usage, "output_tokens", None),
    }
    return out


def apply_schedule_to_elementai(
    rooms: list[dict[str, Any]],
    schedule: Schedule,
) -> list[dict[str, Any]]:
    """Walk each room's elementai and update _exterior + dimensions when an
    opening's ``schedule_ref`` matches a schedule entry.

    The match is by literal ID (D1, L1, etc.). Lookup happens in O(1) via
    pre-built maps. Rooms whose openings have no schedule_ref are left
    untouched.

    Returns the mutated rooms list (same identity) for chaining.
    """
    doors_by_id = {e.id: e for e in schedule.durys}
    windows_by_id = {e.id: e for e in schedule.langai}
    for room in rooms:
        for el in room.get("elementai") or []:
            ref = el.get("schedule_ref")
            if not ref:
                continue
            entry = doors_by_id.get(ref) or windows_by_id.get(ref)
            if entry is None:
                continue
            el["plotis_mm"] = int(entry.width_mm)
            el["aukstis_mm"] = int(entry.height_mm)
            el["_exterior"] = entry.is_exterior
            el["_schedule_ref"] = ref
    return rooms
