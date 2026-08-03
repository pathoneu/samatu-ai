"""Throwaway simulator: patch a saved ai_extract in memory, re-run the
deterministic tail, and score against truth. Zero API calls.

Usage:
  python scripts/_diag_sim.py <slug> <patchspec> [<patchspec> ...]

patchspec forms:
  room:<name-substr>:<field>=<value>     set a per-room primitive
  root:<field>=<value>                   set a top-level field
  baseline                               no patch (baseline rerun)
"""
import sys, json, copy, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))
import eval_harness as EH  # noqa: E402


def apply_patch(parsed, spec):
    if spec == "baseline":
        return
    kind, rest = spec.split(":", 1)
    if kind == "room":
        sub, assign = rest.split(":", 1)
        field, val = assign.split("=", 1)
        hits = 0
        for r in parsed.get("patalpos") or []:
            if sub.lower() in str(r.get("pavadinimas", "")).lower():
                r[field] = json.loads(val)
                hits += 1
        if not hits:
            raise SystemExit(f"patch matched no room: {spec}")
    elif kind == "dropwarn":
        parsed["warnings"] = [
            w for w in (parsed.get("warnings") or [])
            if rest.lower() not in json.dumps(w, ensure_ascii=False).lower()]
    elif kind == "root":
        field, val = rest.split("=", 1)
        parsed[field] = json.loads(val)
    else:
        raise SystemExit(f"unknown patch kind {kind}")


def score(slug, parsed):
    truth = EH._load_truth(slug)
    res = EH.evaluate(parsed, truth)
    rows = []
    for r in res:
        if getattr(r, "status", None) in ("scored", "ok") or r.pct_error is not None:
            rows.append(r)
    return rows


def main():
    slug = sys.argv[1]
    specs = sys.argv[2:] or ["baseline"]
    raw = json.loads((ROOT / f"ground_truth/{slug}/ai_extract.json")
                     .read_text(encoding="utf-8"))
    p = copy.deepcopy(raw)
    for s in specs:
        apply_patch(p, s)
    p = EH._rerun_deterministic_tail(p, slug)
    truth = EH._load_truth(slug)
    res = EH.evaluate(p, truth)
    scored, _ne, _col = EH._partition_headline_metrics(res, "ai_extract")
    errs = []
    print(f"\n{slug}  patches={specs}")
    print(f"  {'metric (HEADLINE = corpus MAE)':<50}{'truth':>10}{'actual':>10}{'pct':>9}")
    for r in scored:
        errs.append(abs(r.pct_error))
        print(f"  {r.label[:50]:<50}{r.truth_value:>10.2f}"
              f"{r.actual_value:>10.2f}{r.pct_error:>+9.2f}")
    print(f"  {'--- category tier (not in MAE) ---':<50}")
    for r in res:
        if r.tier == "headline" or r.pct_error is None or r.actual_value is None:
            continue
        print(f"  {r.label[:50]:<50}{r.truth_value:>10.2f}"
              f"{r.actual_value:>10.2f}{r.pct_error:>+9.2f}")
    if errs:
        print(f"  --> project MAE over {len(errs)} headline metrics: "
              f"{sum(errs)/len(errs):.3f}%")
    s = p.get("santrauka") or {}
    print("  santrauka:", json.dumps(
        {k: v for k, v in s.items() if isinstance(v, (int, float))},
        ensure_ascii=False))


if __name__ == "__main__":
    main()
