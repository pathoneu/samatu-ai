"""Second-pass elevation extraction targeted at bathroom rooms whose
first-pass wall_elevation extraction returned ZERO tile_zones.

For each affected (project, room) pair:
  1. Find the wall_elevation page whose title mentions the room
  2. Run the focused tile prompt (prompts/elevation_tile_focus.txt)
  3. Merge any new tile_zones into the existing _wall_elevations
  4. Re-apply _apply_wall_elevation_tile_override and recompute

Budget: $0.20 per affected room. Cap with --max-cost.
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import sys
import time
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

OPUS_INPUT_PER_M = 15.0
OPUS_OUTPUT_PER_M = 75.0


def _find_bathroom_rooms_without_tile(ai: dict) -> list[dict]:
    """Return rooms whose paskirtis is bathroom-family AND have no
    elevation tile area."""
    out = []
    for r in ai.get("patalpos") or []:
        paskirtis = (r.get("paskirtis") or "").lower()
        pavadinimas = (r.get("pavadinimas") or "").lower()
        is_bath = (
            paskirtis in {"vonia", "wc", "tualetas", "san_mazgas", "san"}
            or "vonia" in pavadinimas
            or "san.mazgas" in pavadinimas
            or "tualetas" in pavadinimas
        )
        if not is_bath:
            continue
        if (r.get("_tile_area_from_elevation_m2") or 0) > 0:
            continue
        out.append(r)
    return out


def _find_elevation_page_for_room(ai: dict, room_name: str, room_nr: str) -> int | None:
    """Heuristic: scan puslapiai for a wall_elevation page whose title
    mentions the room name or nr."""
    name_low = (room_name or "").lower()
    nr_str = str(room_nr or "")
    for p in (ai.get("puslapiai") or []):
        if (p.get("tipas") or "").lower() != "wall_elevation":
            continue
        title = (p.get("pavadinimas") or "").lower()
        if name_low and any(token in title for token in name_low.split() if len(token) > 3):
            return int(p.get("nr") or 0)
        if nr_str and nr_str in title:
            return int(p.get("nr") or 0)
    return None


def _resolve_pdf(slug: str, entry: dict) -> Path:
    if slug == "objektas_a":
        return REPO_ROOT / "docs/superpowers/fixtures/2026-05-26-objektas-a/project.pdf"
    return REPO_ROOT / entry["project_pdf"]


def _call_tile_focus_vision(image_b64: str, room_nr: str, room_name: str,
                            client) -> dict:
    from extractor.vision.dimension_extractor import (
        _detect_image_media_type, _decode_response_json,
    )
    prompt = (REPO_ROOT / "prompts/elevation_tile_focus.txt").read_text(encoding="utf-8")
    img_bytes = base64.b64decode(image_b64)
    media_type = _detect_image_media_type(img_bytes)
    user_text = (
        f"This wall elevation page belongs to room nr={room_nr!r}, "
        f"room_name={room_name!r}. Find every tile zone on every wall shown.\n\n"
        "Emphasis: there ARE tile zones — the previous pass missed them. "
        "Re-examine for cyan/blue hatching, diagonal lines labelled PT, "
        "or any annotated tile band."
    )
    with client.messages.stream(
        model="claude-opus-4-7",
        max_tokens=4096,
        system=prompt,
        messages=[{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64",
                                          "media_type": media_type, "data": image_b64}},
            {"type": "text", "text": user_text},
        ]}],
    ) as stream:
        resp = stream.get_final_message()
    text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
    payload = _decode_response_json(text)
    in_t = getattr(resp.usage, "input_tokens", 0) or 0
    out_t = getattr(resp.usage, "output_tokens", 0) or 0
    cost = round((in_t / 1e6) * OPUS_INPUT_PER_M + (out_t / 1e6) * OPUS_OUTPUT_PER_M, 4)
    payload["_cost"] = cost
    payload["_room_nr"] = room_nr
    payload["_room_name"] = room_name
    return payload


def process_project(slug: str, max_cost: float = 1.5) -> dict:
    reg = yaml.safe_load((REPO_ROOT / "ground_truth/registry.yaml").read_text())
    entry = next((p for p in (reg.get("projects") or []) if p["slug"] == slug), None)
    if not entry:
        return {"slug": slug, "status": "unknown"}
    ai_path = REPO_ROOT / "ground_truth" / slug / "ai_extract.json"
    if not ai_path.exists():
        return {"slug": slug, "status": "no_ai_extract"}
    ai = json.loads(ai_path.read_text(encoding="utf-8"))

    missing_rooms = _find_bathroom_rooms_without_tile(ai)
    print(f"\n══ {slug} ══")
    print(f"  Bathrooms with 0 tile_zones from first pass: {len(missing_rooms)}")
    if not missing_rooms:
        return {"slug": slug, "status": "no_rooms_to_repair"}

    pdf_path = _resolve_pdf(slug, entry)
    if not pdf_path.exists():
        return {"slug": slug, "status": "no_pdf"}
    from extractor.vision_call import pdf_to_b64_images
    pdf_bytes = pdf_path.read_bytes()
    pages = pdf_to_b64_images(pdf_bytes)
    by_idx = {p["page_index"]: p["image_b64"] for p in pages}

    import anthropic
    client = anthropic.Anthropic()
    total_cost = 0.0
    repaired = 0
    elevations_added: list[dict] = []
    for r in missing_rooms:
        if total_cost >= max_cost:
            print(f"  budget cap; skipping remaining")
            break
        nr = str(r.get("nr") or "")
        name = str(r.get("pavadinimas") or "")
        page_idx = _find_elevation_page_for_room(ai, name, nr)
        print(f"  room {nr} '{name[:25]}': elevation page = {page_idx}")
        if not page_idx or page_idx not in by_idx:
            continue
        try:
            payload = _call_tile_focus_vision(by_idx[page_idx], nr, name, client)
        except Exception as exc:
            print(f"    error: {exc}")
            continue
        cost = payload.get("_cost", 0)
        total_cost += cost
        new_elevs = payload.get("wall_elevations") or []
        n_tile_zones = sum(len(e.get("tile_zones") or []) for e in new_elevs)
        print(f"    Vision: ${cost}  walls={len(new_elevs)}  total_tile_zones={n_tile_zones}")
        if n_tile_zones == 0:
            continue
        # Stamp the room nr on every elevation entry (for the override)
        for e in new_elevs:
            e["nr"] = nr
            e["room_name"] = name
            e["_source_pass"] = "second_pass_tile_focus"
        elevations_added.extend(new_elevs)
        repaired += 1

    if not elevations_added:
        print(f"  No new tile zones recovered")
        ai["_elevation_second_pass"] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "rooms_attempted": [r.get("nr") for r in missing_rooms],
            "rooms_repaired": 0, "cost_usd": total_cost,
        }
        ai_path.write_text(json.dumps(ai, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"slug": slug, "status": "no_tile_zones_found", "cost_usd": total_cost}

    # Merge into _wall_elevations
    existing = ai.get("_wall_elevations") or []
    existing.extend(elevations_added)
    ai["_wall_elevations"] = existing

    # Re-apply the override + recompute
    from extractor.vision_call import (
        _apply_wall_elevation_tile_override,
        _recompute_per_room_via_python, _recompute_santrauka,
    )
    n_updated = _apply_wall_elevation_tile_override(ai)
    ai = _recompute_per_room_via_python(ai, rules_override=None)
    ai = _recompute_santrauka(ai)

    ai["_elevation_second_pass"] = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "rooms_attempted": [r.get("nr") for r in missing_rooms],
        "rooms_repaired": repaired,
        "elevations_added": len(elevations_added),
        "rooms_recomputed": n_updated,
        "cost_usd": total_cost,
    }
    ai_path.write_text(json.dumps(ai, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  Recompute: tile override applied to {n_updated} rooms")
    return {"slug": slug, "status": "ok", "repaired": repaired,
            "cost_usd": total_cost}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None)
    ap.add_argument("--max-cost-per-project", type=float, default=1.0)
    args = ap.parse_args(argv)
    reg = yaml.safe_load((REPO_ROOT / "ground_truth/registry.yaml").read_text())
    targets = ([args.only] if args.only
               else [p["slug"] for p in (reg.get("projects") or [])
                     if not p.get("blocked_for_vision_extraction")])
    total = 0.0
    for slug in targets:
        r = process_project(slug, max_cost=args.max_cost_per_project)
        if r.get("cost_usd"):
            total += r["cost_usd"]
    print(f"\nSecond-pass total: ${total:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
