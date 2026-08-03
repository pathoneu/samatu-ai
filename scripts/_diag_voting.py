"""Throwaway: replay the SAVED per-round voting values (`room["_vote"]`) under
different VOTING_N / arbitration rules and rescore. Zero API calls — the
per-round numbers are already on disk inside ai_extract.json.

Modes:
  n3            consensus as shipped (median of all stored values)
  n2:<i>,<j>    median over the i-th and j-th stored value (2-round vote)
  run:<i>       take the i-th stored value verbatim (single run, no vote)
"""
import sys, json, copy, pathlib, io, contextlib, itertools
from statistics import median

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))
import eval_harness as EH  # noqa: E402

FIELDS = tuple((__import__("os").environ.get("VFIELDS")
                or "perimetras_m,lubu_aukstis_m,plotas_m2,n_partition_walls"
                ).split(","))


def rebuild(raw, picker):
    p = copy.deepcopy(raw)
    changed = []
    for r in p.get("patalpos") or []:
        v = r.get("_vote") or {}
        for f in FIELDS:
            info = v.get(f)
            if not info:
                continue
            vals = [x for x in (info.get("values") or []) if x is not None]
            if not vals:
                continue
            new = picker(vals)
            if new is None:
                continue
            new = int(round(new)) if f == "n_partition_walls" else round(float(new), 3)
            if abs(float(r.get(f) or 0) - new) > 1e-6:
                changed.append((r.get("nr"), f, r.get(f), new))
                r[f] = new
    return p, changed


def score(slug, p):
    with contextlib.redirect_stdout(io.StringIO()):
        p = EH._rerun_deterministic_tail(p, slug)
    res = EH.evaluate(p, EH._load_truth(slug))
    scored, _, _ = EH._partition_headline_metrics(res, "ai_extract")
    mae = sum(abs(r.pct_error) for r in scored) / len(scored)
    return mae, {r.label: (r.truth_value, r.actual_value, r.pct_error) for r in scored}


def main():
    slug = sys.argv[1]
    raw = json.loads((ROOT / f"ground_truth/{slug}/ai_extract.json")
                     .read_text(encoding="utf-8"))
    nvals = max(len((r.get("_vote") or {}).get("perimetras_m", {}).get("values") or [])
                for r in raw["patalpos"])
    print(f"{slug}: stored per-round values per field = {nvals}")

    modes = [("n%d (as shipped)" % nvals, lambda v: median(v))]
    if nvals >= 3:
        for combo in itertools.combinations(range(nvals), 2):
            modes.append((f"n2 rounds{combo}",
                          lambda v, c=combo: median([v[c[0]], v[c[1]]])
                          if len(v) > max(c) else median(v)))
    for i in range(nvals):
        modes.append((f"single run #{i}",
                      lambda v, i=i: v[i] if len(v) > i else median(v)))

    for label, picker in modes:
        p, changed = rebuild(raw, picker)
        mae, mets = score(slug, p)
        print(f"\n--- {label}   MAE={mae:.3f}%   ({len(changed)} field(s) changed)")
        for lab, (t, a, pe) in mets.items():
            print(f"      {lab[:46]:<46}{t:>9.2f}{a:>9.2f}{pe:>+8.2f}")
        for c in changed[:8]:
            print(f"      ~ room {c[0]} {c[1]}: {c[2]} -> {c[3]}")


if __name__ == "__main__":
    main()
