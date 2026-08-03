"""Throwaway diagnostic: per-room before/after the deterministic tail.

Usage: python scripts/_diag_rooms.py <slug> [path/to/ai_extract.json]
"""
import sys, json, copy, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))
import eval_harness as EH  # noqa: E402

slug = sys.argv[1]
src = sys.argv[2] if len(sys.argv) > 2 else f"ground_truth/{slug}/ai_extract.json"
raw = json.loads((ROOT / src).read_text(encoding="utf-8"))
before = copy.deepcopy(raw)
after = EH._rerun_deterministic_tail(copy.deepcopy(raw), slug)

def idx(p):
    return {f"{i:02d} {r.get('nr') or ''} {r.get('pavadinimas')}": r
            for i, r in enumerate(p.get("patalpos") or [])}

B, A = idx(before), idx(after)
cols = ["plotas_m2", "perimetras_m", "lubu_aukstis_m",
        "walls_paintable_m2", "ceiling_paintable_m2"]
hdr = f"{'room':<32}" + "".join(f"{c.split('_')[0][:9]:>12}" for c in cols)
print(hdr)
print("-" * len(hdr))
tot = {c: [0.0, 0.0] for c in cols}
for name in A:
    b, a = B.get(name, {}), A[name]
    row = f"{str(name)[:32]:<32}"
    for c in cols:
        bv = float(b.get(c) or 0)
        av = float(a.get(c) or 0)
        tot[c][0] += bv
        tot[c][1] += av
        row += f"{av:>12.2f}" if abs(av - bv) < 0.005 else f"{bv:.1f}>{av:.1f}".rjust(12)
    print(row, "|", a.get("lubu_aukstis_saltinis") or "-",
          "|", a.get("paskirtis") or a.get("tipas") or "-")
print("-" * len(hdr))
print(f"{'TOTAL(after)':<32}" + "".join(f"{tot[c][1]:>12.2f}" for c in cols))
print(f"{'TOTAL(frozen)':<32}" + "".join(f"{tot[c][0]:>12.2f}" for c in cols))
print()
s = after.get("santrauka") or {}
print("santrauka after:", json.dumps(
    {k: v for k, v in s.items() if isinstance(v, (int, float))},
    ensure_ascii=False, indent=1))
