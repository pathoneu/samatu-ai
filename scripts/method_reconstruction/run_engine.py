"""Run the live engine (zero API) on every cached extract and dump what the
analysis needs: per-room facts, our sąmata rows (pozicijos) and the row
scorecard against his sąmata — once per mode and rule variant.

    venv/bin/python scripts/method_reconstruction/run_engine.py \
        [--modes plain,replay] [--variants today,open05,open30,open_inf]

Modes:  plain  = `eval_harness.py --rows --recompute`
        replay = `eval_harness.py --rows --recompute --replay-geometry`
Variants patch ONE engine constant in-process (nothing on disk changes):
        today     — engine as committed
        open05    — UNIVERSAL_RULES["openings_threshold_m2"] = 0.5 (NRM2 threshold under the LT standard)
        open30    — … = 3.0 (founder's aperture rule: ≤ 3.0 m² not deducted)
        open_inf  — … = 1e9 (no opening ever deducted)

Writes  <out>/engine_<mode>_<variant>.json  keyed by codename. Must be run
with the main checkout's venv (see common.REPO).
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

VARIANTS = {"today": None, "open05": 0.5, "open30": 3.0, "open_inf": 1e9}
DROP_ROOM_KEYS = {"polygon_pct", "bbox_pct", "calculation_trace", "_angos_sienose", "eksplikacija_row_bbox",
                  "shared_edges_provenance", "_atvira_erdve"}


def _room(r: dict) -> dict:
    out = {k: v for k, v in r.items() if k not in DROP_ROOM_KEYS}
    k = r.get("_konturas")
    if isinstance(k, dict):
        out["_konturas"] = {x: k.get(x) for x in ("page", "plotas_m2", "perimetras_m", "plotas_uzrasas_m2",
                                                  "paklaida", "plotas_nesutampa", "saltinis", "durys_m")}
    return out


def run(mode: str, variant: str) -> dict:
    eh = common.harness()
    from extractor import universal_rules as ur
    saved = ur.UNIVERSAL_RULES["openings_threshold_m2"]
    eh.REPLAY_GEOMETRY = (mode == "replay")
    eh.GEOMETRY_LANE = False
    if VARIANTS[variant] is not None:
        ur.UNIVERSAL_RULES["openings_threshold_m2"] = VARIANTS[variant]
    result: dict = {"mode": mode, "variant": variant, "threshold_m2": ur.UNIVERSAL_RULES["openings_threshold_m2"],
                    "projects": {}}
    try:
        for code, folder in common.projects():
            extract = common.GT / folder / "ai_extract.json"
            entry: dict = {"his_rows": common.his_rows(folder)}
            if not extract.exists():
                entry["status"] = "no extract"
                result["projects"][code] = entry
                continue
            log = io.StringIO()
            t0 = time.time()
            with contextlib.redirect_stdout(log):
                parsed = eh.run_pipeline_replay(extract)
                parsed = eh._rerun_deterministic_tail(parsed, folder)
                sc = eh._score_rows_of(parsed, folder)
            entry["seconds"] = round(time.time() - t0, 1)
            entry["log"] = common.scrub(log.getvalue())[-6000:]
            entry["rooms"] = [_room(r) for r in parsed.get("patalpos") or [] if isinstance(r, dict)]
            entry["pozicijos"] = parsed.get("pozicijos") or parsed.get("darbu_sarasas") or []
            entry["santrauka"] = parsed.get("santrauka")
            entry["meta_geometrija"] = {k: v for k, v in ((parsed.get("_meta") or {}).get("geometrija") or {}).items()
                                        if k in ("versija", "konturai", "perimetrai_sudeti", "perimetrai_tusti",
                                                 "atviros_erdves", "masteliai")}
            if sc is not None:
                entry["scorecard"] = {
                    "n_rows": sc.n_rows, "n_scored": sc.n_scored, "buckets": sc.buckets,
                    "within_10_share": sc.within_10_share,
                    "families_within_10": sc.families_within_10, "families_scored": sc.families_scored,
                    "rows": [{k: v for k, v in asdict(r).items() if k != "eur"} for r in sc.rows],
                    "concepts": [asdict(c) for c in sc.concepts],
                    "app_extra": sc.app_extra,
                }
            result["projects"][code] = entry
            print(f"  {mode}/{variant} {code}: "
                  + (f"{sc.within_10_share:.1f}% of {sc.n_scored}" if sc is not None else "no scorecard")
                  + f" ({entry['seconds']} s)", flush=True)
    finally:
        ur.UNIVERSAL_RULES["openings_threshold_m2"] = saved
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--modes", default="plain,replay")
    ap.add_argument("--variants", default="today")
    a = ap.parse_args()
    out = common.out_dir()
    for mode in a.modes.split(","):
        for variant in a.variants.split(","):
            res = run(mode, variant)
            p = out / f"engine_{mode}_{variant}.json"
            p.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
            print(f"→ {p}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
