"""Throwaway: split the recomputed rooms into the contractor's iki-3m /
virs-3m paint tiers and compare against the samata's item 16 / item 17.

Two conventions exist in the SAME contractor's quotes:
  · objektas_a item 17  = "Sienų, lubų glaistymas/dažymas (virš 3m)"  → walls INCLUDED
  · objektas_b it17 = "Lubų glaistymas/dažymas (virš 3m aukščio)" → ceilings ONLY
"""
import sys, json, copy, pathlib, io, contextlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))
import eval_harness as EH  # noqa: E402

slug = sys.argv[1]
exclude = [s.lower() for s in (sys.argv[2].split(",") if len(sys.argv) > 2 else [])]

raw = json.loads((ROOT / f"ground_truth/{slug}/ai_extract.json")
                 .read_text(encoding="utf-8"))
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    p = EH._rerun_deterministic_tail(copy.deepcopy(raw), slug)

low_w = low_c = high_w = high_c = 0.0
print(f"{'room':<34}{'H':>6}{'walls':>9}{'w<=3':>9}{'w>3':>9}{'ceil':>9}")
for r in p.get("patalpos") or []:
    name = str(r.get("pavadinimas"))
    if any(x in name.lower() for x in exclude):
        print(f"{name[:34]:<34}   (excluded)")
        continue
    H = float(r.get("lubu_aukstis_m") or 0)
    w = float(r.get("walls_paintable_m2") or 0)
    c = float(r.get("ceiling_paintable_m2") or 0)
    if H > 3.0:
        w_lo = w * 3.0 / H
        w_hi = w - w_lo
        high_c += c
    else:
        w_lo, w_hi = w, 0.0
        low_c += c
    low_w += w_lo
    high_w += w_hi
    print(f"{name[:34]:<34}{H:>6.2f}{w:>9.2f}{w_lo:>9.2f}{w_hi:>9.2f}{c:>9.2f}")

print()
print(f"  iki-3m walls      {low_w:9.2f}")
print(f"  iki-3m ceilings   {low_c:9.2f}   -> item16-equivalent (walls<=3 + ceil<=3) = {low_w+low_c:.2f}")
print(f"  virs-3m walls     {high_w:9.2f}")
print(f"  virs-3m ceilings  {high_c:9.2f}")
print(f"  item17 as CEILINGS ONLY (objektas_b wording) = {high_c:.2f}")
print(f"  item17 as WALLS+CEILINGS (objektas_a wording)    = {high_w+high_c:.2f}")
print(f"  full combined (all walls + all ceilings)     = {low_w+high_w+low_c+high_c:.2f}")
