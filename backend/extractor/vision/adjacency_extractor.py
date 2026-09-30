"""Lightweight room-adjacency Vision pass.

Per the 2026-06-01 multi-project Vision sprint, the production extract
does NOT produce polygon-level wall geometry (plan_assembler never wired
in). The systematic +43% angokraščiai over-extraction + −18% kampai
under-extraction both need wall-adjacency data to fix.

This module asks Opus 4.7 to reason about room adjacency directly from
the floor plan image — no polygon coordinates needed. The output gives
us, per room:

  • n_partition_walls — sum of shared_wall_count across all neighbours
  • exterior_wall_count — needed for the window heuristic

Downstream, ``scripts/apply_adjacency.py`` merges this into each
project's existing ai_extract.json (no re-extraction of dimensions or
room enumeration).
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from ._cache import VisionCache, cache_key
from ..response_text import ModelStopped, read_answer, usage_meta
from .dimension_extractor import _detect_image_media_type, _decode_response_json

from models_config import model_for

REPO_ROOT = Path(__file__).resolve().parents[3]
PROMPT_PATH = REPO_ROOT / "prompts" / "room_adjacency.txt"


@dataclass
class Adjacency:
    to_room: str
    to_room_nr: str | None
    shared_wall_count: int
    wall_types: list[str] = field(default_factory=list)


@dataclass
class RoomAdjacency:
    room_name: str
    room_nr: str | None
    adjacent_rooms: list[Adjacency]
    exterior_wall_count: int
    confidence: str = "medium"
    evidence: str = ""

    @property
    def n_partition_walls(self) -> int:
        return sum(a.shared_wall_count for a in self.adjacent_rooms)


@dataclass
class AdjacencyPayload:
    rooms: list[RoomAdjacency] = field(default_factory=list)
    _meta: dict[str, Any] = field(default_factory=dict)

    def by_room_nr(self) -> dict[str, RoomAdjacency]:
        return {r.room_nr: r for r in self.rooms if r.room_nr}

    def by_room_name(self) -> dict[str, RoomAdjacency]:
        return {r.room_name.strip().lower(): r for r in self.rooms if r.room_name}

    def to_dict(self) -> dict[str, Any]:
        return {
            "rooms": [
                {**asdict(r), "n_partition_walls": r.n_partition_walls}
                for r in self.rooms
            ],
            "_meta": self._meta,
        }


def parse_adjacency_payload(raw: dict[str, Any]) -> AdjacencyPayload:
    if not isinstance(raw, dict):
        raise ValueError("expected dict at top level")
    out = AdjacencyPayload()
    for row in raw.get("rooms") or []:
        if not isinstance(row, dict):
            continue
        adjacents = []
        for a in row.get("adjacent_rooms") or []:
            if not isinstance(a, dict):
                continue
            adjacents.append(Adjacency(
                to_room=str(a.get("to_room") or ""),
                to_room_nr=(str(a["to_room_nr"]) if a.get("to_room_nr") else None),
                shared_wall_count=int(a.get("shared_wall_count") or 1),
                wall_types=list(a.get("wall_types") or []),
            ))
        out.rooms.append(RoomAdjacency(
            room_name=str(row.get("room_name") or ""),
            room_nr=(str(row["room_nr"]) if row.get("room_nr") else None),
            adjacent_rooms=adjacents,
            exterior_wall_count=int(row.get("exterior_wall_count") or 0),
            confidence=str(row.get("confidence") or "medium"),
            evidence=str(row.get("evidence") or "")[:200],
        ))
    return out


def _load_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def extract_adjacency(
    *,
    image_b64: str,
    model: str | None = None,
    max_tokens: int = 8192,
    cache: VisionCache | None = None,
    no_cache: bool = False,
    client: Any | None = None,
) -> AdjacencyPayload:
    """Run the adjacency Vision pass on a single floor-plan page."""
    prompt = _load_prompt()
    img_bytes = base64.b64decode(image_b64)
    model = model or model_for("vision_pass1")
    key = cache_key(img_bytes, prompt, model, str(max_tokens))

    if cache is None:
        cache = VisionCache(namespace="room_adjacency")

    if not no_cache:
        hit = cache.get(key)
        if hit is not None:
            out = parse_adjacency_payload(hit)
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
                {"type": "text", "text": "Return the room adjacency JSON."},
            ],
        }],
    ) as stream:
        resp = stream.get_final_message()

    _, stopped = read_answer(resp, reader="adjacency_extractor")
    if stopped:  # refused / cut off: named, usage kept, never cached (2026-09-30)
        raise ModelStopped(stopped, {"cache": "miss", "key": key, **usage_meta(resp, model)})

    text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
    payload = _decode_response_json(text)
    cache.put(key, payload)

    out = parse_adjacency_payload(payload)
    out._meta = {
        "cache": "miss",
        "key": key,
        "model": model,
        "input_tokens": getattr(resp.usage, "input_tokens", None),
        "output_tokens": getattr(resp.usage, "output_tokens", None),
    }
    return out


def _normalize_name(s: str) -> str:
    """Normalize a Lithuanian room name for fuzzy matching:
      • lowercase
      • strip parenthesized notes ("Kambarys (prie sofos)" → "Kambarys")
      • strip trailing digits/separators after the head noun
      • collapse whitespace
    """
    import re
    s = s.strip().lower()
    s = re.sub(r"\([^)]*\)", "", s)               # drop parentheses
    s = re.sub(r"[/_,;-]", " ", s)                # separator → space
    s = re.sub(r"\b\d+\b", "", s)                 # drop standalone numbers
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _fuzzy_match_adjacency(
    nr: str, name: str,
    by_nr: dict[str, "RoomAdjacency"],
    by_name: dict[str, "RoomAdjacency"],
) -> "RoomAdjacency | None":
    """Best-effort match by nr, exact-name, then first-token name."""
    if nr and nr in by_nr:
        return by_nr[nr]
    norm = _normalize_name(name)
    if norm in by_name:
        return by_name[norm]
    # First-word match (e.g. "Miegamasis" matches "miegamasis xxx")
    head = norm.split(" ")[0] if norm else ""
    if head:
        for key, val in by_name.items():
            if key.startswith(head):
                return val
    # Substring containment either direction
    if norm:
        for key, val in by_name.items():
            if norm in key or key in norm:
                return val
    return None


def apply_adjacency_to_rooms(
    rooms: list[dict[str, Any]],
    adjacency: AdjacencyPayload,
) -> dict[str, Any]:
    """Mutate each room dict in place:
      • set ``n_partition_walls`` = sum of shared_wall_count from adjacency
      • set ``_exterior_wall_count`` for reference (used by window heuristic)
      • flag windows in rooms with ≥1 exterior wall as ``_exterior=True``
        (heuristic: in residential drawings, windows are placed on
        exterior walls in the vast majority of cases)

    Returns a summary dict ``{n_rooms_matched, n_partition_walls_total,
    n_windows_flagged_exterior, n_unmatched}`` for logging.
    """
    # Build lookup tables using normalized keys
    by_nr = {r.room_nr: r for r in adjacency.rooms if r.room_nr}
    by_name = {_normalize_name(r.room_name): r for r in adjacency.rooms if r.room_name}
    summary = {
        "n_rooms_matched": 0,
        "n_partition_walls_total": 0,
        "n_windows_flagged_exterior": 0,
        "n_unmatched_rooms": 0,
        "n_rooms_with_exterior_walls": 0,
        "unmatched_names": [],
    }
    for room in rooms:
        nr = str(room.get("nr") or "")
        name = str(room.get("pavadinimas") or "")

        adj = _fuzzy_match_adjacency(nr, name, by_nr, by_name)
        if not adj:
            summary["n_unmatched_rooms"] += 1
            summary["unmatched_names"].append(f"{nr}:{name}")
            continue
        summary["n_rooms_matched"] += 1
        room["n_partition_walls"] = adj.n_partition_walls
        room["_exterior_wall_count"] = adj.exterior_wall_count
        room["_adjacency_confidence"] = adj.confidence
        # KEEP the payload, not just the three scalars it reduces to
        # (2026-09-02). `n_partition_walls` is one of the four addends behind
        # every room's corner metres, and until now the only answer to "why 4?"
        # was the number itself — the neighbour list, the wall types and the
        # model's own one-line evidence were computed on a paid pass and thrown
        # away at the call site. Persisted per room, they are the term's
        # explanation, one dict deep.
        room["_adjacency"] = {
            "neighbours": [
                {"room": a.to_room, "room_nr": a.to_room_nr,
                 "shared_walls": a.shared_wall_count,
                 "wall_types": list(a.wall_types or [])}
                for a in adj.adjacent_rooms
            ],
            "wall_types": sorted({t for a in adj.adjacent_rooms
                                  for t in (a.wall_types or [])}),
            "exterior_walls": adj.exterior_wall_count,
            "confidence": adj.confidence,
            "evidence": adj.evidence,
        }
        summary["n_partition_walls_total"] += adj.n_partition_walls
        has_exterior = adj.exterior_wall_count > 0
        if has_exterior:
            summary["n_rooms_with_exterior_walls"] += 1
        # Window heuristic: if the room has ≥1 exterior wall, windows
        # in this room are EXTERIOR (face outside). If exterior_wall_count
        # is 0 and the room has windows, those windows are interior (rare
        # case — usually a transom into a corridor or a sunroom).
        for el in (room.get("elementai") or []):
            tipas = (el.get("tipas") or "").lower()
            if tipas not in ("langas", "stoglangis"):
                continue
            # Don't overwrite an explicit False (interior) flag from a
            # higher-confidence source. Only fill None.
            if el.get("_exterior") is not None:
                continue
            el["_exterior"] = has_exterior
            if has_exterior:
                kiekis = int(el.get("kiekis") or 1)
                summary["n_windows_flagged_exterior"] += kiekis
    return summary
