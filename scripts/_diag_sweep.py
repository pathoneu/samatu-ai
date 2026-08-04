"""Throwaway: sweep the double-height room's ceiling height and report the
headline metrics at each value. Zero API calls."""
import sys, json, copy, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))
import eval_harness as EH  # noqa: E402

slug = sys.argv[1]
sub = sys.argv[2]
heights = [float(x) for x in sys.argv[3].split(",")]
raw = json.loads((ROOT / f"ground_truth/{slug}/ai_extract.json")
                 .read_text(encoding="utf-8"))
truth = EH._load_truth(slug)

# The PDF-reading lanes (positioned height markers, symbol legend) do not
# influence the paint metrics on this project (marker lane reports
# "no_positioned_markers"; the legend only gates symbol COUNTS). Skip the
# 65-page PDF re-read on every sweep point so the sweep finishes.
EH.REGISTRY[slug] = dict(EH.REGISTRY[slug], pdf_path="__skip__/none.pdf")

print(f"{'H':>6} {'combined':>10} {'walls':>10} {'ceil':>10} "
      f"{'cmb%':>8} {'w%':>8} {'c%':>8} {'MAE':>8}")
for h in heights:
    p = copy.deepcopy(raw)
    p["warnings"] = [w for w in (p.get("warnings") or [])
                     if "dvigub" not in json.dumps(w, ensure_ascii=False).lower()]
    for r in p.get("patalpos") or []:
        if sub.lower() in str(r.get("pavadinimas", "")).lower():
            r["lubu_aukstis_m"] = h
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        p = EH._rerun_deterministic_tail(p, slug)
    res = EH.evaluate(p, truth)
    scored, _, _ = EH._partition_headline_metrics(res, "ai_extract")
    m = {r.label: r for r in res}
    cmb = m["Dažymo plotas (samata items 16+17, excl garažas)"]
    w = m["Sienų dažomas plotas"]
    c = m["Lubų dažomas plotas"]
    mae = sum(abs(r.pct_error) for r in scored) / len(scored)
    print(f"{h:>6.2f} {cmb.actual_value:>10.2f} {w.actual_value:>10.2f} "
          f"{c.actual_value:>10.2f} {cmb.pct_error:>+8.2f} {w.pct_error:>+8.2f} "
          f"{c.pct_error:>+8.2f} {mae:>8.3f}")
