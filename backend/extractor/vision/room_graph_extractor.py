"""Vision pass #2 — extract the room graph keyed against a dimension list.

The model is shown the same floor-plan image plus the JSON dimension list
from pass 1, and must emit a graph of {vertices, walls, rooms, openings}

from models_config import model_for
where every numeric length is a *reference* to a dimension id (never a new
number). The deterministic plan_assembler then uses the IDs to assemble
perimeters/areas, and the geometry_solver enforces closure/orthogonality.

# EXPERIMENTAL — NOT IN PRODUCTION PATH (as of 2026-06-01)
#
# This is the Phase 2 deterministic room-graph extractor. Production
# `extract_interior()` does NOT call this module; the lightweight
# `adjacency_extractor` Vision pass (2026-06-01) covers the room-
# adjacency need with far less infrastructure. Imports outside this
# file are limited to tests + plan_assembler (also EXPERIMENTAL).
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from ._cache import VisionCache, cache_key
from ..response_text import ModelStopped, read_answer, usage_meta

REPO_ROOT = Path(__file__).resolve().parents[3]
PROMPT_PATH = REPO_ROOT / "prompts" / "room_graph.txt"


@dataclass
class Vertex:
    id: str
    x_pct: float
    y_pct: float


@dataclass
class Wall:
    id: str
    start_vertex: str
    end_vertex: str
    dimension_id: str | None = None
    angle_deg: float | None = None
    thickness_mm: float | None = None
    is_exterior: bool = False
    room_ids: list[str] = field(default_factory=list)
    # 2026-05-31: wall classification — used by adjacency detection
    # (load-bearing walls are usually shared between rooms; partition walls
    # often aren't) and by kampai categorisation.
    wall_type: str = "partition"   # load_bearing | partition | exterior_envelope
    curved: bool = False


@dataclass
class Room:
    id: str
    nr: str
    name: str
    paskirtis: str
    polygon_walls: list[str]
    lubu_aukstis_m: float = 2.82
    lubu_aukstis_source: str = "default"
    lubu_tipas: str = "gkp"
    plyteles_sienos_aukstis_m: float = 0.0
    sienu_apdailos_breakdown: dict[str, float] = field(default_factory=dict)
    confidence: str = "high"


@dataclass
class Opening:
    id: str
    wall_id: str
    type: str           # "door" | "hidden_door" | "window" | "led_niche"
    width_dimension_id: str | None = None
    height_dimension_id: str | None = None
    schedule_ref: str | None = None
    is_exterior: bool = False
    hidden: bool = False


@dataclass
class RoomGraph:
    vertices: list[Vertex] = field(default_factory=list)
    walls: list[Wall] = field(default_factory=list)
    rooms: list[Room] = field(default_factory=list)
    openings: list[Opening] = field(default_factory=list)
    _meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "vertices": [asdict(v) for v in self.vertices],
            "walls":    [asdict(w) for w in self.walls],
            "rooms":    [asdict(r) for r in self.rooms],
            "openings": [asdict(o) for o in self.openings],
            "_meta": self._meta,
        }


def _load_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def parse_room_graph_payload(raw_json: dict[str, Any]) -> RoomGraph:
    """Convert a Vision JSON payload into a typed RoomGraph."""
    if not isinstance(raw_json, dict):
        raise ValueError("expected dict at top level")

    rg = RoomGraph()
    for v in raw_json.get("vertices", []):
        rg.vertices.append(Vertex(
            id=str(v["id"]),
            x_pct=float(v["x_pct"]),
            y_pct=float(v["y_pct"]),
        ))
    def _safe_float(v: Any) -> float | None:
        """Coerce model output to a float. Vision occasionally emits a
        reference id ('d32') where a number was expected — return None
        rather than crash the entire parse."""
        if v is None:
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    for w in raw_json.get("walls", []):
        wall_type = str(w.get("wall_type") or "partition").lower()
        if wall_type not in ("load_bearing", "partition", "exterior_envelope"):
            wall_type = "partition"
        rg.walls.append(Wall(
            id=str(w["id"]),
            start_vertex=str(w["start_vertex"]),
            end_vertex=str(w["end_vertex"]),
            dimension_id=(str(w["dimension_id"]) if w.get("dimension_id") else None),
            angle_deg=_safe_float(w.get("angle_deg")),
            thickness_mm=_safe_float(w.get("thickness_mm")),
            is_exterior=bool(w.get("is_exterior", False)),
            room_ids=[str(x) for x in (w.get("room_ids") or [])],
            wall_type=wall_type,
            curved=bool(w.get("curved", False)),
        ))
    for r in raw_json.get("rooms", []):
        rg.rooms.append(Room(
            id=str(r["id"]),
            nr=str(r.get("nr") or r["id"]),
            name=str(r.get("name") or ""),
            paskirtis=str(r.get("paskirtis") or "gyvenamoji"),
            polygon_walls=[str(x) for x in (r.get("polygon_walls") or [])],
            lubu_aukstis_m=float(r.get("lubu_aukstis_m") or 2.82),
            lubu_aukstis_source=str(r.get("lubu_aukstis_source") or "default"),
            lubu_tipas=str(r.get("lubu_tipas") or "gkp"),
            plyteles_sienos_aukstis_m=float(r.get("plyteles_sienos_aukstis_m") or 0.0),
            sienu_apdailos_breakdown=dict(r.get("sienu_apdailos_breakdown") or {}),
            confidence=str(r.get("confidence") or "high"),
        ))
    for o in raw_json.get("openings", []):
        rg.openings.append(Opening(
            id=str(o["id"]),
            wall_id=str(o["wall_id"]),
            type=str(o.get("type") or "door"),
            width_dimension_id=(str(o["width_dimension_id"]) if o.get("width_dimension_id") else None),
            height_dimension_id=(str(o["height_dimension_id"]) if o.get("height_dimension_id") else None),
            schedule_ref=(str(o["schedule_ref"]) if o.get("schedule_ref") else None),
            is_exterior=bool(o.get("is_exterior", False)),
            hidden=bool(o.get("hidden", False)),
        ))

    _validate_referential_integrity(rg)
    degenerate = _filter_degenerate_rooms(rg)
    if degenerate:
        rg._meta = {**(rg._meta or {}),
                    "degenerate_rooms_dropped": degenerate}
    return rg


def _filter_degenerate_rooms(rg: RoomGraph) -> list[str]:
    """Drop rooms whose polygons are degenerate.

    A polygon is degenerate when:
      - it has fewer than 3 walls (cannot close), OR
      - any interior angle is > 175° (the polygon is essentially a line with
        a tiny tip — almost certainly a Vision read error)

    Returns the list of dropped room ids for the warnings buffer.
    """
    import math

    wmap = {w.id: w for w in rg.walls}
    kept: list[Room] = []
    dropped: list[str] = []
    for r in rg.rooms:
        wids = r.polygon_walls
        if len(wids) < 3:
            dropped.append(f"{r.id} ({r.nr}): only {len(wids)} walls")
            continue
        # Build the sequence of (angle_deg) for each wall in order
        angles: list[float | None] = []
        for wid in wids:
            w = wmap.get(wid)
            angles.append(w.angle_deg if w else None)
        if any(a is None for a in angles):
            # Can't verify angles → leave the room in, the geometry_solver
            # will infer or fail gracefully.
            kept.append(r)
            continue
        # Interior angle at vertex k = 180° − exterior_turn(k), where the
        # exterior turn is the change in direction from wall k to wall k+1.
        bad = False
        n = len(angles)
        for k in range(n):
            a1 = float(angles[k])
            a2 = float(angles[(k + 1) % n])
            turn = ((a2 - a1) + 180) % 360 - 180          # signed [-180, 180)
            interior = 180.0 - abs(turn)
            if interior > 175.0:
                bad = True
                break
        if bad:
            dropped.append(f"{r.id} ({r.nr}): degenerate interior angle")
            continue
        kept.append(r)
    rg.rooms = kept
    return dropped


def _validate_referential_integrity(rg: RoomGraph) -> None:
    """Drop unresolvable rooms/walls/openings rather than crash the whole pipeline.

    The downstream assembler is robust to missing rooms (just emits fewer
    patalpos); crashing on a partially-bad Vision response throws away the
    salvageable subset. Anomalies are pushed into rg._meta['warnings'] so
    callers can surface them.
    """
    vids = {v.id for v in rg.vertices}
    wids = {w.id for w in rg.walls}
    rids = {r.id for r in rg.rooms}
    warnings: list[str] = []

    # Walls with unknown endpoints → drop
    rg.walls = [
        w for w in rg.walls
        if (w.start_vertex in vids and w.end_vertex in vids)
        or (warnings.append(f"wall {w.id} references unknown vertices; dropped") or False)
    ]
    wids = {w.id for w in rg.walls}

    # Rooms with empty polygon or unknown walls → drop
    kept_rooms: list[Room] = []
    for r in rg.rooms:
        if not r.polygon_walls:
            warnings.append(f"room {r.id} ({r.nr}) has empty polygon_walls; dropped")
            continue
        if any(wid not in wids for wid in r.polygon_walls):
            warnings.append(f"room {r.id} ({r.nr}) references unknown walls; dropped")
            continue
        kept_rooms.append(r)
    rg.rooms = kept_rooms

    # Openings with unknown wall → drop
    rg.openings = [
        o for o in rg.openings
        if o.wall_id in wids
        or (warnings.append(f"opening {o.id} references unknown wall; dropped") or False)
    ]

    if warnings:
        rg._meta = {**(rg._meta or {}), "warnings": warnings}


def extract_room_graph(
    *,
    image_b64: str,
    dimensions_payload: dict[str, Any],
    model: str | None = None,
    max_tokens: int = 32768,
    cache: VisionCache | None = None,
    no_cache: bool = False,
    client: Any | None = None,
) -> RoomGraph:
    """Vision pass 2: room graph keyed against the dimension list."""
    prompt = _load_prompt()
    img_bytes = base64.b64decode(image_b64)
    dim_json = json.dumps(dimensions_payload, sort_keys=True)
    model = model or model_for("vision_pass1")
    key = cache_key(img_bytes, prompt, model, str(max_tokens), dim_json)

    if cache is None:
        cache = VisionCache(namespace="room_graph")

    if not no_cache:
        hit = cache.get(key)
        if hit is not None:
            out = parse_room_graph_payload(hit)
            out._meta = {**out._meta, "cache": "hit", "key": key, "model": model}
            return out

    if client is None:
        import anthropic
        client = anthropic.Anthropic(max_retries=1)

    from .dimension_extractor import _detect_image_media_type
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
                {
                    "type": "text",
                    "text": (
                        "Dimension list (use these IDs ONLY for length references):\n"
                        + dim_json
                    ),
                },
            ],
        }],
    ) as stream:
        resp = stream.get_final_message()

    _, stopped = read_answer(resp, reader="room_graph_extractor")
    if stopped:  # refused / cut off: named, usage kept, never cached (2026-09-30)
        raise ModelStopped(stopped, {"cache": "miss", "key": key, **usage_meta(resp, model)})
    text = "".join(
        b.text for b in resp.content if getattr(b, "type", None) == "text"
    )
    payload = json.loads(text)
    cache.put(key, payload)

    out = parse_room_graph_payload(payload)
    out._meta = {
        "cache": "miss",
        "key": key,
        "model": model,
        "input_tokens": getattr(resp.usage, "input_tokens", None),
        "output_tokens": getattr(resp.usage, "output_tokens", None),
    }
    return out
