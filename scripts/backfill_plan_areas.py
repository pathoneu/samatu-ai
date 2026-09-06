"""Backfill the plan-area lane into cached extracts frozen before it existed.

2026-09-06. `extractor/plan_area_annotations.py` runs inside a fresh
extraction when no room table merged. The frozen `ground_truth/<slug>/
ai_extract.json` files were made before that, so `eval_harness.py --recompute`
would never see its effect. Zero cost: the labels are read from the fixture
PDF's text layer with the same module, the same reconciliation is applied to
the cached rooms, and the same warnings and ceiling anchor are written.
Idempotent: an extract that already carries `_meta.plan_area_lane` is skipped;
one with a merged room table is skipped (the lane does not run there either).

    venv/bin/python scripts/backfill_plan_areas.py              # all
    venv/bin/python scripts/backfill_plan_areas.py objektas_g   # one
    venv/bin/python scripts/backfill_plan_areas.py --refresh-author   # re-read the designer's figures
    venv/bin/python scripts/backfill_plan_areas.py --refresh-lane     # undo + re-run the room lane (reader changed)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))

from extractor.plan_area_annotations import (  # noqa: E402
    SOURCE_LABEL, lane_warnings, most_common_page, plan_pages_from_classification,
    reconcile_rooms_with_annotations, scan_text_layer, text_pages_from_classification,
)

LANE_WARNING_CODES = ("room_area_unconfirmed", "plan_area_unclaimed")


def _undo_lane(parsed: dict) -> None:
    """Put the rooms back to what Vision read, so the lane can run again with
    the current reader (a re-read after a reader change)."""
    for r in parsed.get("patalpos") or []:
        if not isinstance(r, dict):
            continue
        if r.get("plotas_saltinis") == SOURCE_LABEL:
            prior = r.pop("_plotas_pries_uzrasa_m2", None)
            if prior is not None:
                r["plotas_m2"] = prior
                r["plotas_saltinis"] = "wall_dim_calc"
            else:
                r["plotas_saltinis"] = "inline_label"
            r.pop("_plotas_uzrasas", None)
        r.pop("_area_unconfirmed", None)
        r.pop("_area_unconfirmed_reason", None)
    anchor = parsed.get("_ceiling_anchor") or {}
    if str(anchor.get("label") or "").startswith("plano užrašų"):
        parsed.pop("_ceiling_anchor", None)
    parsed["warnings"] = [w for w in (parsed.get("warnings") or [])
                          if not (isinstance(w, dict) and w.get("code") in LANE_WARNING_CODES)]
    parsed.get("_meta", {}).pop("plan_area_lane", None)


def _lt(v: float) -> str:
    return f"{float(v):.2f}".replace(".", ",")


def backfill(slug: str, entry: dict) -> str:
    path = REPO / "ground_truth" / slug / "ai_extract.json"
    if not path.exists():
        return "no cached extract"
    parsed = json.loads(path.read_text(encoding="utf-8"))
    meta = parsed.setdefault("_meta", {})
    pdf = REPO / (entry.get("project_pdf") or "")
    if not entry.get("project_pdf") or not pdf.exists():
        return "no project PDF on disk"
    notes: list[str] = []
    text_pages = text_pages_from_classification(parsed.get("puslapiai") or [])
    scan = scan_text_layer(pdf.read_bytes(), pages=text_pages or None)   # one pass, same as Step 2.44
    if "_autoriaus_kiekiai" not in parsed or REFRESH_AUTHOR:
        # 3c — the designer's own legend totals, on every project (tables or not)
        parsed["_autoriaus_kiekiai"] = scan["figures"]
        path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        notes.append(f"author figures: {len(parsed['_autoriaus_kiekiai'])}")
    if meta.get("plan_area_lane") and REFRESH_LANE:
        _undo_lane(parsed)
        notes.append("lane re-read")
    if meta.get("plan_area_lane"):
        return "; ".join(notes + [f"lane already applied ({meta['plan_area_lane'].get('status')})"])
    if int(meta.get("eksplikacija_merged_rooms") or 0) > 0:
        return "; ".join(notes + ["room table merged — lane does not run"])
    pages = set(plan_pages_from_classification(parsed.get("puslapiai") or []))
    ann = [a for a in scan["annotations"] if not pages or a["page"] in pages]
    lane = reconcile_rooms_with_annotations(parsed.get("patalpos") or [], ann)
    meta["plan_area_lane"] = lane
    if lane["status"] == "applied":
        parsed.setdefault("warnings", []).extend(lane_warnings(lane, parsed.get("patalpos") or []))
        if not parsed.get("_ceiling_anchor") and float(lane.get("sum_m2") or 0) > 0:
            parsed["_ceiling_anchor"] = {"total_area_m2": float(lane["sum_m2"]),
                                         "label": "plano užrašų suma", "page": most_common_page(ann)}
    parsed.setdefault("_backfill", {})["plan_areas"] = (
        "2026-09-06: plan-area lane applied from the fixture PDF's text layer; "
        "a fresh run does the same in Step 2.44")
    path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return "; ".join(notes + [
        f"{lane['status']} ({lane.get('geometry')}): {lane['candidates']} labels on pages {lane['pages']}, "
        f"confirmed {lane['confirmed']}, adopted {lane['adopted']}, unconfirmed {lane['unconfirmed']}, "
        f"duplicates {lane.get('duplicates')}, unclaimed {lane['unclaimed']}, Σ {lane['sum_m2']}"])


REFRESH_AUTHOR = False
REFRESH_LANE = False


def main(argv: list[str]) -> int:
    global REFRESH_AUTHOR, REFRESH_LANE
    REFRESH_AUTHOR = "--refresh-author" in argv          # re-read the designer's figures with the current reader
    REFRESH_LANE = "--refresh-lane" in argv              # undo + re-run the room lane with the current reader
    argv = [a for a in argv if a not in ("--refresh-author", "--refresh-lane")]
    reg = yaml.safe_load((REPO / "ground_truth/registry.yaml").read_text(encoding="utf-8"))
    only = set(argv[1:])
    for entry in reg.get("projects") or []:
        slug = entry["slug"]
        if only and slug not in only:
            continue
        if entry.get("ablation_of"):
            continue
        print(f"  {slug:<14} {backfill(slug, entry)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
