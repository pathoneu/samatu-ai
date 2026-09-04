"""CoT perimeter pilot — Svetainė + Miegamasis + Berniuko (1 of 2).

Spend budget: 3 rooms × 3 no_cache runs × ~$0.10 ≈ $0.90.

Honest scope: we do NOT have per-room contractor perimeter truth. The
purpose of this pilot is to detect whether the model's chain-of-thought
self-verification produces NOTICEABLY different perimeters from the
single-pass extraction. If CoT yields ≈ same values across 3 runs and
≈ same value as the existing extract, the input is at the model's
ceiling. If it yields a CONSISTENT but DIFFERENT value, the existing
extract has a real bias the model has now corrected.

The 3-room report includes:
  • per-room CoT median perim across 3 runs
  • CoT-vs-existing delta
  • CoT internal-self-check rates (axis_x_ok, axis_y_ok)
  • Vision cost summary
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import statistics
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


PROMPT_PATH = REPO_ROOT / "prompts" / "perimeter_cot.txt"

# Objektas A rooms to test, with cached bboxes from earlier bbox_locator run.
TARGET_ROOMS = ["102", "110", "108"]  # Svetainė, Miegamasis, Berniuko-1


def main() -> int:
    _load_dotenv(REPO_ROOT / "backend" / ".env")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERR: ANTHROPIC_API_KEY not in env"); return 2

    from extractor.vision_call import pdf_to_b64_images, _crop_room_image
    from extractor.vision.bbox_locator import extract_room_bboxes
    from extractor.vision.dimension_extractor import _decode_response_json
    import anthropic

    pdf_path = REPO_ROOT / "docs/superpowers/fixtures/2026-05-26-objektas-a/project.pdf"
    pdf_bytes = pdf_path.read_bytes()
    pages = pdf_to_b64_images(pdf_bytes, max_pages=2)
    floor_b64 = pages[1]['image_b64']

    bb = extract_room_bboxes(image_b64=floor_b64)
    by_nr = {r.nr: r for r in bb.rooms}

    # Existing per-room perim from the gt_dimensions
    truth = json.loads((REPO_ROOT / "ground_truth/objektas_a/truth.json").read_text())
    existing_perim = {str(r["nr"]): float(r.get("perimetras_m") or 0)
                      for r in truth["gt_dimensions"]}

    prompt = PROMPT_PATH.read_text(encoding="utf-8")
    client = anthropic.Anthropic()

    cost_in = 0
    cost_out = 0
    results = {}
    for nr in TARGET_ROOMS:
        bb_obj = by_nr.get(nr)
        if not bb_obj:
            print(f"  [{nr}] no bbox; skipping"); continue
        bbox = bb_obj.to_crop_bbox()
        crop_b64 = _crop_room_image(pdf_bytes, 2, bbox, target_dpi=300,
                                     max_dim=2576, padding=0.20)
        if not crop_b64:
            print(f"  [{nr}] crop failed; skipping"); continue
        img_bytes = base64.b64decode(crop_b64)
        media = "image/jpeg"

        print(f"\n=== Room {nr} {bb_obj.name} — 3 CoT runs ===")
        runs = []
        for trial in range(1, 4):
            with client.messages.stream(
                model="claude-opus-4-7",
                max_tokens=8192,
                system=prompt,
                messages=[{"role": "user", "content": [
                    {"type": "image", "source": {"type": "base64",
                                                  "media_type": media, "data": crop_b64}},
                    {"type": "text", "text":
                        f"Cropped room — best guess label '{bb_obj.name}' (room nr {nr})."},
                ]}],
            ) as stream:
                resp = stream.get_final_message()
            text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
            in_t = getattr(resp.usage, "input_tokens", 0) or 0
            out_t = getattr(resp.usage, "output_tokens", 0) or 0
            cost_in += in_t
            cost_out += out_t

            # Pull the JSON sentinel block out of the CoT response
            idx = text.find("FINAL_JSON:")
            payload = None
            if idx >= 0:
                tail = text[idx + len("FINAL_JSON:"):].strip()
                try:
                    payload = _decode_response_json(tail)
                except Exception as e:
                    print(f"  Trial {trial}: JSON parse failed: {e}")
            perim = None
            if payload:
                perim = (payload.get("perimeter_mm") or
                         sum(float(w.get("length_mm") or 0) for w in payload.get("walls") or []))
            runs.append({"perim_mm": perim, "in_t": in_t, "out_t": out_t,
                         "self_check": (payload or {}).get("self_check") if payload else None})
            print(f"  Trial {trial}: perim_mm={perim}  in_t={in_t}  out_t={out_t}  "
                  f"self_check={runs[-1]['self_check']}")

        # Median across runs
        perims = [r["perim_mm"] for r in runs if r["perim_mm"] is not None and r["perim_mm"] > 0]
        median = statistics.median(perims) if perims else None
        existing = existing_perim.get(nr, 0) * 1000  # in mm
        delta_mm = (median - existing) if (median and existing) else None
        delta_pct = (delta_mm / existing * 100) if (delta_mm is not None and existing) else None
        results[nr] = {
            "name": bb_obj.name,
            "runs": runs,
            "median_perim_mm": median,
            "existing_perim_mm": existing,
            "delta_mm": delta_mm,
            "delta_pct": delta_pct,
        }

    print()
    print("=== CoT Pilot Summary ===")
    print(f"{'nr':>4} {'name':<22} {'existing':>10} {'CoT median':>11} {'Δ_mm':>8} {'Δ%':>7}")
    print("─" * 70)
    for nr, r in results.items():
        existing_s = f"{r['existing_perim_mm']:.0f}" if r['existing_perim_mm'] else "—"
        med_s = f"{r['median_perim_mm']:.0f}" if r['median_perim_mm'] else "—"
        d_mm_s = f"{r['delta_mm']:+.0f}" if r['delta_mm'] is not None else "—"
        d_pct_s = f"{r['delta_pct']:+.2f}%" if r['delta_pct'] is not None else "—"
        print(f"{nr:>4} {r['name'][:22]:<22} {existing_s:>10} {med_s:>11} {d_mm_s:>8} {d_pct_s:>7}")

    # Cost (Opus 4.7 pricing: $15/M input + $75/M output)
    cost_usd = (cost_in / 1_000_000) * 15 + (cost_out / 1_000_000) * 75
    print(f"\nTotal Vision: in_tokens={cost_in}, out_tokens={cost_out}, est_cost=${cost_usd:.2f}")

    out_path = REPO_ROOT / "eval_runs" / "objektas_a_cot_pilot.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"Saved: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
