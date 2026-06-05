"""Offline niche-locator pass: runs niche_locator on each project's
ceiling_plan page, folds results into the cached ai_extract.json,
re-computes santrauka via the same python-math step the production
pipeline uses, and prints LED accuracy before/after.

Goal: validate the niche_locator wiring is correct + measures real
accuracy improvement BEFORE modifying backend/extractor/vision_call.py.

Vision budget: ~$0.30-0.50 per ceiling_plan page (only on cache miss).
"""
from __future__ import annotations

import base64
import io
import json
import sys
from pathlib import Path

import yaml
from pdf2image import convert_from_bytes

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "backend"))

from extractor.vision.niche_locator import (  # noqa: E402
    extract_niches, fold_niches_into_rooms,
)
from extractor.vision_call import _recompute_per_room_via_python, _recompute_santrauka  # noqa: E402


def get_truth_led(truth: dict) -> float | None:
    v = (truth.get("gt_totals") or {}).get("led_nisos_m")
    if isinstance(v, dict):
        return v.get("value")
    return v


def render_page(pdf_bytes: bytes, page_nr: int, *, dpi: int = 200) -> str:
    """Render one page (1-indexed) to JPEG base64."""
    images = convert_from_bytes(
        pdf_bytes, dpi=dpi, first_page=page_nr, last_page=page_nr,
    )
    if not images:
        raise RuntimeError(f"no image rendered for page {page_nr}")
    buf = io.BytesIO()
    images[0].save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def sum_led_m(rooms: list[dict]) -> float:
    """Sum of niche lengths across all rooms, in metres."""
    total_m = 0.0
    for r in rooms:
        for el in (r.get("elementai") or []):
            tipas = (el.get("tipas") or "").lower()
            if tipas in ("nisa_led", "nisa_ceiling_led", "ceiling_led"):
                length_mm = el.get("ilgis_mm") or el.get("length_mm") or 0
                kiekis = el.get("kiekis") or 1
                total_m += (length_mm / 1000.0) * kiekis
    return total_m


def process(slug: str, entry: dict) -> dict:
    """Returns {slug, truth, before, after, delta_pct, n_niches_found, cost_est}."""
    truth_path = REPO / entry["truth_path"]
    pdf_path   = REPO / entry["project_pdf"]
    extract_path = REPO / "ground_truth" / slug / "ai_extract.json"
    out_path = REPO / "ground_truth" / slug / "ai_extract_with_niches.json"

    truth = json.loads(truth_path.read_text(encoding="utf-8"))
    led_truth = get_truth_led(truth)
    extract = json.loads(extract_path.read_text(encoding="utf-8"))

    # Find ceiling_plan page
    ceiling = [
        p for p in (extract.get("puslapiai") or [])
        if (p.get("tipas") or "").lower() == "ceiling_plan"
    ]
    if not ceiling:
        return {
            "slug": slug, "status": "no_ceiling_plan_page",
            "truth": led_truth, "before": sum_led_m(extract.get("patalpos") or []),
        }
    page_nr = ceiling[0]["nr"]

    # Render that page
    pdf_bytes = pdf_path.read_bytes()
    image_b64 = render_page(pdf_bytes, page_nr)

    # Run niche_locator (signature is keyword-only)
    nl = extract_niches(image_b64=image_b64)
    cache_state = (nl._meta or {}).get("cache")
    cost = 0.0 if cache_state == "hit" else 0.40   # rough estimate

    rooms = extract.get("patalpos") or []
    before_led = float((extract.get("santrauka") or {}).get("nisu_metrai_total") or 0)

    # Fold + recompute per-room + recompute santrauka totals
    fold_niches_into_rooms(rooms, nl)
    extract["patalpos"] = rooms
    extract = _recompute_per_room_via_python(extract, None)
    extract = _recompute_santrauka(extract)
    after_led = float((extract.get("santrauka") or {}).get("nisu_metrai_total") or 0)

    out_path.write_text(json.dumps(extract, ensure_ascii=False, indent=2), encoding="utf-8")

    delta_pct_before = (before_led - led_truth) / led_truth * 100 if led_truth else 0
    delta_pct_after  = (after_led  - led_truth) / led_truth * 100 if led_truth else 0

    return {
        "slug": slug,
        "status": "ok",
        "page": page_nr,
        "cache": cache_state,
        "cost_est_usd": cost,
        "n_niches_found": len(nl.niches),
        "truth": led_truth,
        "before": round(before_led, 2),
        "after":  round(after_led, 2),
        "before_pct": round(delta_pct_before, 2),
        "after_pct":  round(delta_pct_after, 2),
        "improvement_pp": round(abs(delta_pct_before) - abs(delta_pct_after), 2),
        "rerolled_to": str(out_path.relative_to(REPO)),
    }


def main() -> int:
    reg = yaml.safe_load((REPO / "ground_truth/registry.yaml").read_text(encoding="utf-8"))
    results = []
    total_cost = 0.0
    for entry in reg.get("projects", []):
        if (entry.get("scope_mismatch") or
            entry.get("blocked_for_vision_extraction") or
            entry.get("blocked_partial_input")):
            continue
        slug = entry["slug"]
        try:
            r = process(slug, entry)
        except Exception as exc:
            r = {"slug": slug, "status": "error", "error": str(exc)}
        results.append(r)
        total_cost += r.get("cost_est_usd", 0.0)
        print(f"  {slug}: {json.dumps(r, ensure_ascii=False)}")

    print(f"\n  Estimated Vision cost: ${total_cost:.2f}")

    summary = REPO / "audit/niche_locator_rerun.json"
    summary.parent.mkdir(parents=True, exist_ok=True)
    summary.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  saved → {summary.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
