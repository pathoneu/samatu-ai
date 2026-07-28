"""Niches-only Vision pass — targeted recovery of LED / partition niches
that the main floor-plan + ceiling-plan extractor missed.

The main vision_call pipeline reads niches as part of the elementai list,
but Beržų showed Vision missing niches in several rooms (Tambūras,
Koridorius, Darbo, Garažas per gap-analysis.md). This pass uses a single,
narrow prompt against the ceiling-plan page (luburiu planas) so the model
isn't distracted by walls / doors / windows / furniture.

The output is meant to be folded into ``elementai`` so the existing
deterministic engine recomputes nisu_metrai correctly.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from ._cache import VisionCache, cache_key
from .dimension_extractor import _detect_image_media_type

from models_config import model_for

REPO_ROOT = Path(__file__).resolve().parents[3]
PROMPT_PATH = REPO_ROOT / "prompts" / "niche_locator.txt"


@dataclass
class NicheRecord:
    room_nr: str
    room_name: str
    type: str            # "ceiling_led" | "wall_led" | "partition_niche"
    length_mm: float
    count: int = 1
    confidence: str = "high"
    evidence: str = ""

    @property
    def length_m(self) -> float:
        return self.length_mm / 1000.0

    # Map Vision-detected niche types → elementai.tipas. Only ceiling_led
    # and wall_led are billed as LED (`_calc_nisu_metrai_m` filters by
    # tipas == 'nisa_LED'). partition_niche and similar wall recesses are
    # tracked as nisa_partition so they're visible downstream but excluded
    # from the LED metric. This was the source of Beržų's +10m over-count
    # before the 2026-06-05 audit — every niche the locator returned was
    # being billed as LED regardless of type. See audit/niche_locator_rerun.json.
    _TYPE_TO_TIPAS = {
        "ceiling_led":     "nisa_LED",
        "wall_led":        "nisa_LED",
        "partition_niche": "nisa_partition",
        "shelf_niche":     "nisa_partition",
        "curtain_niche":   "nisa_partition",
    }

    def to_elementai_row(self) -> dict[str, Any]:
        """Format compatible with vision_call._elementai_to_counts.

        Conservative fallback: unknown niche types map to nisa_partition
        (NOT billed as LED). Only explicit ceiling_led / wall_led count.
        """
        tipas = self._TYPE_TO_TIPAS.get(self.type, "nisa_partition")
        return {
            "tipas": tipas,
            "kiekis": self.count,
            "ilgis_m": round(self.length_m, 3),
            "_niche_type": self.type,
            "_source": "niche_locator",
            "_confidence": self.confidence,
        }


@dataclass
class NicheList:
    niches: list[NicheRecord] = field(default_factory=list)
    _meta: dict[str, Any] = field(default_factory=dict)

    def per_room(self) -> dict[str, list[NicheRecord]]:
        """Group niches by room_nr (primary key). Niches that have no
        room_nr but DO have a room_name land under the special key
        "__name__:<name>" so the fold can match by name when the
        ceiling plan doesn't show room numbers (e.g., Ciurliu's
        Apšvietimo planas only shows room labels, not nrs).
        """
        out: dict[str, list[NicheRecord]] = {}
        for n in self.niches:
            nr = str(n.room_nr or "").strip()
            if nr:
                out.setdefault(nr, []).append(n)
            elif (n.room_name or "").strip():
                out.setdefault(f"__name__:{n.room_name.strip()}", []).append(n)
            # niches with neither nr nor name are unassignable — dropped
        return out

    def to_dict(self) -> dict[str, Any]:
        return {
            "niches": [asdict(n) for n in self.niches],
            "_meta": self._meta,
        }


def parse_niche_payload(raw: dict[str, Any]) -> NicheList:
    if not isinstance(raw, dict):
        raise ValueError("expected dict at top level")
    out = NicheList()
    for row in raw.get("niches") or []:
        out.niches.append(NicheRecord(
            room_nr=str(row.get("room_nr") or ""),
            room_name=str(row.get("room_name") or ""),
            type=str(row.get("type") or "ceiling_led"),
            length_mm=float(row.get("length_mm") or 0),
            count=int(row.get("count") or 1),
            confidence=str(row.get("confidence") or "high"),
            evidence=str(row.get("evidence") or "")[:120],
        ))
    return out


def _load_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def extract_niches(
    *,
    image_b64: str,
    model: str | None = None,
    max_tokens: int = 16384,
    cache: VisionCache | None = None,
    no_cache: bool = False,
    client: Any | None = None,
) -> NicheList:
    """Run the niche-only Vision pass on a single page image."""
    prompt = _load_prompt()
    img_bytes = base64.b64decode(image_b64)
    model = model or model_for("vision_pass1")
    key = cache_key(img_bytes, prompt, model, str(max_tokens))

    if cache is None:
        cache = VisionCache(namespace="niche_locator")

    if not no_cache:
        hit = cache.get(key)
        if hit is not None:
            out = parse_niche_payload(hit)
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
                {"type": "text", "text": "Return the niche list as JSON."},
            ],
        }],
    ) as stream:
        resp = stream.get_final_message()

    text = "".join(
        b.text for b in resp.content if getattr(b, "type", None) == "text"
    )
    payload = json.loads(text)
    cache.put(key, payload)

    out = parse_niche_payload(payload)
    out._meta = {
        "cache": "miss",
        "key": key,
        "model": model,
        "input_tokens": getattr(resp.usage, "input_tokens", None),
        "output_tokens": getattr(resp.usage, "output_tokens", None),
    }
    return out


def fold_niches_into_rooms(
    rooms: list[dict[str, Any]],
    niches: NicheList,
) -> dict[str, list[NicheRecord]]:
    """For each room nr the niche pass identified, REPLACE the existing
    nisa_LED entries in elementai with the niche-pass entries.

    Matching is by ``room_nr`` (string compare). Returns the
    per_room dict for diagnostics.

    Why replace instead of append: the main extractor might have under-
    counted (the whole reason for this pass). Appending would double-count
    niches the main pass caught correctly. The targeted pass is treated as
    the source of truth for niches when it returns a record for that room.

    Rooms not mentioned in the niche pass are left untouched (the main
    extractor's record stands).

    2026-06-05 audit note: a confidence-weighted variant was tried but
    didn't help because the locator's current prompt over-extracts on
    Beržų (52m vs 42m truth) and under-extracts on Objektas B (23m
    vs 55m truth). The locator finds real niches the main pass misses
    but also catches curtain/non-LED niches the contractor doesn't
    bill. The root fix is at the prompt level (precision/recall tuning)
    not at the fold level. Keeping the original REPLACE policy here
    so the fold's behavior is well-understood; do NOT wire into prod
    until the locator prompt is improved. See audit/niche_locator_rerun.json.
    """
    by_room = niches.per_room()
    for room in rooms:
        nr = str(room.get("nr") or "")
        name = str(room.get("pavadinimas") or "").strip()
        # Try nr first, then by-name fallback (helps when ceiling plan
        # doesn't show room numbers and the locator can only provide names).
        room_niches = by_room.get(nr) or by_room.get(f"__name__:{name}")
        if not room_niches:
            continue
        # Strip existing nisa_LED entries (preserve other tipai incl.
        # nisa_partition from a previous fold)
        elementai = [
            e for e in (room.get("elementai") or [])
            if (e.get("tipas") or "").lower() != "nisa_led"
        ]
        for n in room_niches:
            elementai.append(n.to_elementai_row())
        room["elementai"] = elementai
    return by_room
