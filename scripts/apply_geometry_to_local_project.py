#!/usr/bin/env python3
"""DEV ONLY: run the geometry lane (no Vision, €0) over a project that is
already in the LOCAL database, recompute its quantities through the running
local backend exactly the way a room edit on the check sheet does, and save.

    SAMATU_AUTH_DISABLED=1 venv/bin/python scripts/apply_geometry_to_local_project.py demo-objektas_h
    … --dry-run      print what the lane reads, change nothing
    … --forget-floor-choices   drop a test choice of floor covering first (demo projects)
    … --api URL      the local backend (default http://localhost:8000)

A real extraction gets the lane as Step 2.44d of vision_call; this script is
for looking at a change on a stored project without paying for a re-run. It
refuses any API that is not localhost.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

CONTEXT_KEYS = ("_door_types", "detected_symbols_summary", "_plyteliu_specs", "_symbol_legend", "_duru_ziniarastis",
                "_vector_symbols",
                "bendras_plotas_m2", "v9_meta", "_overrides", "_ceiling_anchor", "_walls_anchor", "_floor_anchors", "_meta",
                "_autoriaus_kiekiai")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("project_id")
    ap.add_argument("--api", default="http://localhost:8000")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--forget-floor-choices", action="store_true",
                    help="take a TEST choice of floor covering back off the rooms first (a demo project only)")
    args = ap.parse_args()
    if urlparse(args.api).hostname not in ("localhost", "127.0.0.1"):
        print("refusing: --api must be the local backend")
        return 2

    import db
    from extractor.geometry_lane import apply_geometry
    from storage import get_storage, pdf_key

    row = db.get_project(args.project_id)
    if not row:
        print(f"no such project in the local database: {args.project_id}")
        return 1
    project = row.get("data") if isinstance(row.get("data"), dict) else row
    pdf = get_storage().get(pdf_key(args.project_id))
    if not pdf:
        print("the project's PDF is not in storage")
        return 1

    if args.forget_floor_choices:
        for key in ("patalpos", "v8_rooms"):
            for r in project.get(key) or []:
                if isinstance(r, dict) and r.get("grindu_danga_saltinis") == "user_override":
                    r.pop("grindu_danga", None)
                    r.pop("grindu_danga_saltinis", None)

    out = apply_geometry(project, pdf)
    # the drawing's door schedule (deterministic, €0) — the same scan a full extraction and the free re-read run
    from extractor.door_schedule import scan_door_schedule
    project["_duru_ziniarastis"] = scan_door_schedule(pdf)
    print(f"durų žiniaraštis: {project['_duru_ziniarastis'].get('status')} — {project['_duru_ziniarastis'].get('sakinys')}")
    # the symbols counted from the drawing's paths (€0) — the diffuser rows take this count
    from extractor.vector_symbols import scan_vector_symbols
    project["_vector_symbols"] = scan_vector_symbols(pdf)
    _vs = project["_vector_symbols"].get("difuzoriai") or {}
    print(f"ženklai iš brėžinio: difuzoriai {_vs.get('count')} — {_vs.get('sakinys')}")
    print(f"status {out['status']} in {out['seconds']} s | vietos {out['vietos']} | plano lapai {out['grupes']}")
    print(f"kontūrai {out['konturai']} | atviros erdvės {out['atviros_erdves']}")
    print(f"perimetrai sudėti {out['perimetrai_sudeti']} | tušti {out['perimetrai_tusti']}")
    print(f"grindų dangos {out['grindu_dangos']}")
    for r in project.get("patalpos") or []:
        suma = r.get("_perimetras_suma") or {}
        print(f"  {r.get('nr')} {str(r.get('pavadinimas'))[:24]:24} P={r.get('perimetras_m')} ({r.get('perimetras_saltinis')}) "
              f"buvo={r.get('_perimetras_pries_geometrija')} įvertis={r.get('_perimetras_ivertis_m')} "
              f"{' + '.join(suma.get('eilutes') or [])} {r.get('_perimetras_priezastis') or r.get('_konturo_priezastis') or ''}")
    if args.dry_run:
        return 0

    rooms = project.get("patalpos") or []
    body = {"patalpos": rooms, "rules_override": project.get("_overrides") or {},
            "per_room_overrides": project.get("_per_room_overrides") or {}, "archetipas": project.get("archetipas"),
            "bendras_plotas_m2": sum(float(r.get("plotas_m2") or 0) for r in rooms),
            "_ceiling_anchor": project.get("_ceiling_anchor"), "_door_types": project.get("_door_types"),
            "_symbol_legend": project.get("_symbol_legend"), "_duru_ziniarastis": project.get("_duru_ziniarastis"),
            "context": {k: project.get(k) for k in CONTEXT_KEYS}}
    req = urllib.request.Request(f"{args.api}/recompute-interior", data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=120) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    if result.get("status") != "ok":
        print("recompute failed:", result.get("_error") or result.get("status"))
        return 1
    merged = {**project, **{k: v for k, v in result.items() if k != "status"}}
    merged["_meta"] = {**(project.get("_meta") or {}), **(result.get("_meta") or {})}
    db.upsert_project(args.project_id, merged, user_id=row.get("user_id") if isinstance(row.get("data"), dict) else None)
    print(f"saved {args.project_id}: {len(merged.get('patalpos') or [])} rooms, {len(merged.get('pozicijos') or [])} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
