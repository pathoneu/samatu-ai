"""Vision pass #2 — extract the room graph keyed against a dimension list.

The model is shown the same floor-plan image plus the JSON dimension list
from pass 1, and must emit a graph of {vertices, walls, rooms, openings}
where every numeric length is a *reference* to a dimension id (never a new
number). The deterministic plan_assembler then uses the IDs to assemble
perimeters/areas, and the geometry_solver enforces closure/orthogonality.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from ._cache import VisionCache, cache_key

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
    for w in raw_json.get("walls", []):
        rg.walls.append(Wall(
            id=str(w["id"]),
            start_vertex=str(w["start_vertex"]),
            end_vertex=str(w["end_vertex"]),
            dimension_id=(str(w["dimension_id"]) if w.get("dimension_id") else None),
            angle_deg=(float(w["angle_deg"]) if w.get("angle_deg") is not None else None),
            thickness_mm=(float(w["thickness_mm"]) if w.get("thickness_mm") is not None else None),
            is_exterior=bool(w.get("is_exterior", False)),
            room_ids=[str(x) for x in (w.get("room_ids") or [])],
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
    return rg


def _validate_referential_integrity(rg: RoomGraph) -> None:
    vids = {v.id for v in rg.vertices}
    wids = {w.id for w in rg.walls}
    rids = {r.id for r in rg.rooms}

    for w in rg.walls:
        if w.start_vertex not in vids:
            raise ValueError(f"wall {w.id} references unknown start_vertex {w.start_vertex}")
        if w.end_vertex not in vids:
            raise ValueError(f"wall {w.id} references unknown end_vertex {w.end_vertex}")
        for rid in w.room_ids:
            if rid not in rids:
                raise ValueError(f"wall {w.id} references unknown room {rid}")

    for r in rg.rooms:
        if not r.polygon_walls:
            raise ValueError(f"room {r.id} has empty polygon_walls")
        for wid in r.polygon_walls:
            if wid not in wids:
                raise ValueError(f"room {r.id} references unknown wall {wid}")

    for o in rg.openings:
        if o.wall_id not in wids:
            raise ValueError(f"opening {o.id} references unknown wall {o.wall_id}")


def extract_room_graph(
    *,
    image_b64: str,
    dimensions_payload: dict[str, Any],
    model: str = "claude-opus-4-7",
    max_tokens: int = 32768,
    cache: VisionCache | None = None,
    no_cache: bool = False,
    client: Any | None = None,
) -> RoomGraph:
    """Vision pass 2: room graph keyed against the dimension list."""
    prompt = _load_prompt()
    img_bytes = base64.b64decode(image_b64)
    dim_json = json.dumps(dimensions_payload, sort_keys=True)
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
        client = anthropic.Anthropic()

    resp = client.messages.create(
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
                        "media_type": "image/png",
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
    )
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
