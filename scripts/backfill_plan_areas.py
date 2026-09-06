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
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))

from extractor.plan_area_annotations import (  # noqa: E402
    most_common_page, plan_pages_from_classification, read_area_annotations,
    reconcile_rooms_with_annotations,
)


def _lt(v: float) -> str:
    return f"{float(v):.2f}".replace(".", ",")


def backfill(slug: str, entry: dict) -> str:
    path = REPO / "ground_truth" / slug / "ai_extract.json"
    if not path.exists():
        return "no cached extract"
    parsed = json.loads(path.read_text(encoding="utf-8"))
    meta = parsed.setdefault("_meta", {})
    if meta.get("plan_area_lane"):
        return f"already applied ({meta['plan_area_lane'].get('status')})"
    if int(meta.get("eksplikacija_merged_rooms") or 0) > 0:
        return "room table merged — lane does not run"
    pdf = REPO / (entry.get("project_pdf") or "")
    if not entry.get("project_pdf") or not pdf.exists():
        return "no project PDF on disk"
    pages = plan_pages_from_classification(parsed.get("puslapiai") or [])
    ann = read_area_annotations(pdf.read_bytes(), pages=pages or None)
    lane = reconcile_rooms_with_annotations(parsed.get("patalpos") or [], ann)
    meta["plan_area_lane"] = lane
    if lane["status"] == "applied":
        rooms_by_nr = {str(r.get("nr")): r for r in parsed.get("patalpos") or [] if isinstance(r, dict)}
        warns = parsed.setdefault("warnings", [])
        for nr in lane["unconfirmed"]:
            r = rooms_by_nr.get(str(nr)) or {}
            warns.append({"level": "WARN", "code": "room_area_unconfirmed", "room": nr, "severity": "high",
                          "message": (f"Patalpos „{r.get('pavadinimas') or nr}\" ({_lt(r.get('plotas_m2') or 0)} m²) "
                                      "ploto užrašo plane neradau, nors kitos patalpos jį turi – patikrinkite, "
                                      "ar tokia patalpa yra ir ar ji nesidubliuoja.")})
        for u in lane["unclaimed"]:
            warns.append({"level": "INFO", "code": "plan_area_unclaimed", "severity": "low",
                          "message": (f"Plane (psl. {u.get('page')}) užrašytas plotas {_lt(u.get('value_m2') or 0)} m², "
                                      "kurio nepriskyriau jokiai patalpai – galbūt trūksta patalpos.")})
        if not parsed.get("_ceiling_anchor") and float(lane.get("sum_m2") or 0) > 0:
            parsed["_ceiling_anchor"] = {"total_area_m2": float(lane["sum_m2"]),
                                         "label": "plano užrašų suma", "page": most_common_page(ann)}
    parsed.setdefault("_backfill", {})["plan_areas"] = (
        "2026-09-06: plan-area lane applied from the fixture PDF's text layer; "
        "a fresh run does the same in Step 2.44")
    path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return (f"{lane['status']}: {lane['candidates']} labels on pages {lane['pages']}, "
            f"confirmed {lane['confirmed']}, adopted {lane['adopted']}, "
            f"unconfirmed {lane['unconfirmed']}, unclaimed {lane['unclaimed']}, Σ {lane['sum_m2']}")


def main(argv: list[str]) -> int:
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
