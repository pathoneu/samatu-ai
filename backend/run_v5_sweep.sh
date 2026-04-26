#!/usr/bin/env bash
# V5 prompt'ų sweep launcher (#33).
# Paleidžia visus 5 projektus VIENA užklausa (kad summary nebūtų pershov'inta)
# ir rodo before/after lyginimą su baseline.
#
# Naudojimas:
#   1) cd ~/samatu-ai/backend && ./start.sh     # vieną terminalą
#   2) cd ~/samatu-ai/backend && ./run_v5_sweep.sh   # kitą terminalą

set -euo pipefail

BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"
SWEEP_DIR="$(dirname "$(realpath "$0")")/logs/v4_runs/accuracy_sweep"

# 1) Patikrinti backend
if ! curl -sf -m 3 "$BACKEND_URL/" >/dev/null 2>&1; then
    echo "ERROR: backend nepasiekiamas $BACKEND_URL — pirmiausia paleisk ./start.sh"
    exit 1
fi
echo "✓ Backend pasiekiamas: $BACKEND_URL"
echo

# 2) Visi 5 projektai vienoje užklausoje (mažiausias → didžiausias).
#    Server'is pats sutvarkys iteraciją + summary failą.
echo "═══════════════════════════════════════════════════════════════════"
echo "  Vykdoma: P5 → P3 → P4 → P2 → P1 (V5 prompt'ai, holdout=true)"
echo "  Kiekvienas projektas užtruks 2-6 min (Opus Vision)"
echo "═══════════════════════════════════════════════════════════════════"

t_start=$(date +%s)
response=$(curl -sf -X POST "$BACKEND_URL/dev/accuracy-sweep-v4" \
    -H "Content-Type: application/json" \
    -d '{"projects": ["P5", "P3", "P4", "P2", "P1"], "holdout": true, "force": true}' \
    --max-time 3600)
t_end=$(date +%s)
elapsed=$((t_end - t_start))

echo
echo "Sweep done in ${elapsed}s ($(($elapsed/60))m $(($elapsed%60))s)"
echo

# 3) Lyginamoji lentelė
echo "═══════════════════════════════════════════════════════════════════"
echo "                BASELINE vs V5 (slim variant) LYGINIMAS"
echo "═══════════════════════════════════════════════════════════════════"
SWEEP_DIR="$SWEEP_DIR" python3 << 'PYEOF'
import json, os
from pathlib import Path

SWEEP_DIR = Path(os.environ["SWEEP_DIR"])

# Baseline iš senų prompt'ų run'o (Apr 24)
BASELINE = {
    "P1": {"PASS": 1, "TOTAL": 9, "scope": "full_project"},
    "P2": {"PASS": 2, "TOTAL": 6, "scope": "full_project"},
    "P3": {"PASS": 0, "TOTAL": 5, "scope": "partial_paint_only", "ERR": True},
    "P4": {"PASS": 2, "TOTAL": 6, "scope": "partial_paint_and_tiles"},
    "P5": {"PASS": 4, "TOTAL": 6, "scope": "full_project"},
}

print(f"\n{'PID':<5} {'BASELINE':<14} {'V5 NEW':<14} {'Δ %PASS':<10} {'V5 status':<10}")
print("-" * 65)

summary_path = SWEEP_DIR / "sweep_summary_holdout=True.json"
if not summary_path.exists():
    print(f"  ⚠ Naujo sweep'o nerasta: {summary_path}")
    raise SystemExit(0)

new = {r["pid"]: r for r in json.load(open(summary_path))}

total_baseline_pass = 0
total_baseline_n = 0
total_new_pass = 0
total_new_n = 0

for pid in ["P5", "P3", "P4", "P2", "P1"]:
    bl = BASELINE[pid]
    bl_pct = 100 * bl["PASS"] / bl["TOTAL"]
    bl_str = f"{bl['PASS']}/{bl['TOTAL']} ({bl_pct:.0f}%)" + (" ERR" if bl.get("ERR") else "")
    total_baseline_pass += bl["PASS"]
    total_baseline_n += bl["TOTAL"]

    n = new.get(pid, {})
    s = n.get("summary") or {}
    if not s:
        print(f"{pid:<5} {bl_str:<14} {'—':<14} {'—':<10} {'(nepaleista)':<10}")
        continue
    n_total = s.get("total", 0) or 1
    n_pct = 100 * s.get("PASS", 0) / n_total
    err = " ERR" if n.get("resp_status") == "error" else ""
    n_str = f"{s.get('PASS',0)}/{n_total} ({n_pct:.0f}%){err}"
    delta = n_pct - bl_pct
    delta_str = f"{'+' if delta >= 0 else ''}{delta:.0f}%"
    print(f"{pid:<5} {bl_str:<14} {n_str:<14} {delta_str:<10} {n.get('resp_status','?'):<10}")
    total_new_pass += s.get("PASS", 0)
    total_new_n += n_total

print('-' * 65)
bl_avg = 100 * total_baseline_pass / total_baseline_n if total_baseline_n else 0
n_avg = 100 * total_new_pass / total_new_n if total_new_n else 0
print(f"{'AVG':<5} {f'{total_baseline_pass}/{total_baseline_n} ({bl_avg:.0f}%)':<14} "
      f"{f'{total_new_pass}/{total_new_n} ({n_avg:.0f}%)':<14} "
      f"{'+' if n_avg >= bl_avg else ''}{n_avg - bl_avg:.0f}%")
print()

# Failed field detail per PID
print("\n=== Detalūs FAIL/MISSING laukai per PID ===")
for pid in ["P5", "P3", "P4", "P2", "P1"]:
    n = new.get(pid, {})
    rows = n.get("rows") or []
    fails = [r for r in rows if r.get("status") in ("FAIL", "MISSING")]
    if fails:
        print(f"\n  {pid}:")
        for r in fails:
            d = r.get("delta_pct")
            d_str = f"{d:+.1f}%" if d is not None else "-"
            print(f"    {r['status']:<8} {r['field']:<35} gt={r.get('gt')} pred={r.get('pred')} {d_str}")
PYEOF

echo
echo "Detalūs JSON: $SWEEP_DIR/"
