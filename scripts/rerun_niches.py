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
    extract_niches, fold_niches_into_rooms, NicheList,
)
from extractor.vision_call import _recompute_per_room_via_python, _recompute_santrauka  # noqa: E402


def _is_niche_candidate(page: dict) -> bool:
    """Pages worth scanning for LED/niche annotations:
       1. classifier marked as ceiling_plan
       2. title contains 'lub' (Lubų planas, lubų mazgai) or 'apšviet'
          (Apšvietimo planas — often shows LED strip routing)
    Catches detail-section pages and lighting plans the page
    classifier doesn't tag as ceiling_plan but which carry niche data.
    """
    tipas = (page.get("tipas") or "").lower()
    if tipas == "ceiling_plan":
        return True
    title = (page.get("pavadinimas") or "").lower()
    return ("lub" in title) or ("apšviet" in title) or ("apsviet" in title)


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

    # Find ALL niche-candidate pages. Primary = first ceiling_plan;
    # secondary = other candidates (lighting plans, section pages).
    candidate_pages = [
        p for p in (extract.get("puslapiai") or [])
        if _is_niche_candidate(p)
    ]
    if not candidate_pages:
        return {
            "slug": slug, "status": "no_niche_candidate_page",
            "truth": led_truth, "before": sum_led_m(extract.get("patalpos") or []),
        }
    # Sort: ceiling_plan first, then by page number
    candidate_pages.sort(key=lambda p: (
        0 if (p.get("tipas") or "").lower() == "ceiling_plan" else 1,
        int(p.get("nr", 999)),
    ))
    page_nrs = [int(p["nr"]) for p in candidate_pages]

    pdf_bytes = pdf_path.read_bytes()
    rooms = extract.get("patalpos") or []
    before_led = float((extract.get("santrauka") or {}).get("nisu_metrai_total") or 0)

    # CONDITIONAL BACKFILL (2026-06-05): primary page is canonical.
    # Run secondary pages ONLY if primary's LED coverage is sparse
    # (< COVERAGE_GATE rooms with non-zero LED). On projects where
    # the ceiling_plan already covers most rooms (berzas pg6: 10
    # rooms), additional pages just re-detect the same LEDs as new
    # niches → false positives.
    COVERAGE_GATE = 5
    combined = NicheList()
    rooms_covered_by_primary: set[str] = set()
    page_results: list[dict] = []
    cost = 0.0

    # First pass: primary page only
    primary_pg = page_nrs[0]
    image_b64 = render_page(pdf_bytes, primary_pg)
    nl = extract_niches(image_b64=image_b64)
    c = (nl._meta or {}).get("cache")
    if c != "hit":
        cost += 0.40
    for n in nl.niches:
        is_led_billable = n.type in ("ceiling_led", "wall_led")
        if is_led_billable and (n.length_mm or 0) > 0:
            rooms_covered_by_primary.add(str(n.room_nr))
        combined.niches.append(n)
    page_results.append({
        "page": primary_pg, "n": len(nl.niches),
        "kept": len(nl.niches), "cache": c, "role": "primary",
    })

    # Conditional backfill: only run secondaries if coverage is sparse
    if len(rooms_covered_by_primary) < COVERAGE_GATE:
        for page_nr in page_nrs[1:]:
            image_b64 = render_page(pdf_bytes, page_nr)
            nl = extract_niches(image_b64=image_b64)
            c = (nl._meta or {}).get("cache")
            if c != "hit":
                cost += 0.40
            kept = 0
            for n in nl.niches:
                is_led_billable = n.type in ("ceiling_led", "wall_led")
                if (not is_led_billable
                    or str(n.room_nr) not in rooms_covered_by_primary):
                    combined.niches.append(n)
                    kept += 1
            page_results.append({
                "page": page_nr, "n": len(nl.niches),
                "kept": kept, "cache": c, "role": "backfill",
            })
    else:
        for page_nr in page_nrs[1:]:
            page_results.append({
                "page": page_nr, "n": None, "kept": 0,
                "cache": "skipped", "role": "skipped_coverage_ok",
            })

    fold_niches_into_rooms(rooms, combined)
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
        "pages_scanned": page_nrs,
        "per_page": page_results,
        "cost_est_usd": cost,
        "n_niches_found": len(combined.niches),
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
