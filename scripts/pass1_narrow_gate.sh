#!/usr/bin/env bash
# pass1_narrow_gate.sh — v4 (2026-10-27). Reads a fresh extract with SAMATU_PASS1_NARROW=1 for
# every corpus project and scores it against the sąmata (eval_harness --totals-only --recompute
# and --rows --recompute) and the reading scorecard. The script DOES NOT overwrite
# ground_truth/<slug>/ai_extract.json — it writes ai_extract_narrow.json alongside, swaps it in
# for scoring, and restores the file with `git checkout --` afterwards.
#
# NOT run from this task (no credit for paid runs). The founder funds the reads from this script.
#
# Expected cost: ~0,3–0,5 USD per project per round at Opus 4.7 rates (narrow prompt ~3 000
# output tokens vs today's ~10 000 and the image prefix is cached across voting rounds). The
# default compares the one-round narrow against the stored baseline:
#
#     bash scripts/pass1_narrow_gate.sh                  # votes = 1, every corpus project
#     bash scripts/pass1_narrow_gate.sh objektas_h       # votes = 1, one project
#     VOTES=3 bash scripts/pass1_narrow_gate.sh          # votes = 3 (compare 1 vs 3 rounds)
#     DRY_RUN=1 bash scripts/pass1_narrow_gate.sh        # prints the plan + estimated cost, no API
#
# Baseline runtimes stored in each project's ai_extract.json._meta.elapsed_s (full Pass-1):
#   objektas_a 208,3 s · objektas_b 468,3 s · objektas_c 308,7 s · objektas_d 212,4 s
#   objektas_g 1510,6 s · objektas_h 735,4 s
# Narrow estimate (one round, zoom skipped): ~100–200 s per project. ~0,3–0,5 USD/round.
#
# Gate — the narrow run passes when all of these hold vs the baseline:
#   · totals ±1 pp of 57,50 %         (eval_harness --totals-only --recompute)
#   · rows ±10 % within 1 pp of 9,0 % (eval_harness --rows --recompute)
#   · € ±10 % within 1 pp of 18,0 %   (eval_harness --rows --recompute, € columns)
#   · scorecard tiers unchanged       (scripts/reading_scorecard.py per project)

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PY="${PY:-$ROOT/venv/bin/python}"
VOTES="${VOTES:-1}"
BUDGET_USD="${BUDGET_USD:-10.0}"
DRY_RUN="${DRY_RUN:-0}"
PROJECTS="${@:-objektas_a objektas_b objektas_c objektas_d objektas_g objektas_h}"

echo "pass1_narrow gate — $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "  python  : $PY"
echo "  votes   : $VOTES"
echo "  projects: $PROJECTS"
echo "  budget  : \$$BUDGET_USD"
echo

OUT_DIR="docs/superpowers/fixtures/pass1_narrow_$(date -u +%Y-%m-%d)"
mkdir -p "$OUT_DIR"
SUMMARY="$OUT_DIR/summary.tsv"
printf "slug\truntime_baseline_s\truntime_narrow_s\tnarrow_rounds\toutput_tokens\tcost_usd\ttotals_pct\trows_pm10_pct\teur_pm10_pct\tscorecard\n" > "$SUMMARY"

for SLUG in $PROJECTS; do
  BASE="ground_truth/$SLUG/ai_extract.json"
  if [[ ! -f "$BASE" ]]; then
    echo "  $SLUG — SKIP: no baseline ai_extract.json"
    continue
  fi
  NARROW="ground_truth/$SLUG/ai_extract_narrow.json"
  BASELINE_ELAPSED=$("$PY" -c "import json; d=json.load(open('$BASE')); print((d.get('_meta') or {}).get('elapsed_s',''))")
  echo "─── $SLUG (baseline ${BASELINE_ELAPSED}s) ───"

  if [[ "$DRY_RUN" == "1" ]]; then
    echo "  (dry run — would call extract_interior with SAMATU_PASS1_NARROW=1 and VOTES=$VOTES)"
    continue
  fi

  # 1) Fresh read with narrow enabled. The run_vision_on_truth_set.py helper is single-slug via
  #    --only; it writes ai_extract.json AND an ai_extract_meta.json sidecar. We redirect its
  #    output to the _narrow filename by moving the file after it writes.
  SAMATU_PASS1_NARROW=1 SAMATU_PASS1_NARROW_VOTES=$VOTES \
    "$PY" scripts/run_vision_on_truth_set.py --only "$SLUG" --budget "$BUDGET_USD" || {
      echo "  $SLUG — FAIL (vision run exited non-zero)"
      continue
    }
  mv "$BASE" "$NARROW"
  # restore the baseline so the scoring reads it when we are not scoring the narrow one
  git checkout -- "$BASE"

  # 2) Swap the narrow extract in for scoring; restore afterwards.
  cp "$BASE" "$BASE.bak"
  cp "$NARROW" "$BASE"
  trap 'mv "$BASE.bak" "$BASE" 2>/dev/null || true' EXIT

  TOTALS=$("$PY" eval_harness.py --project "$SLUG" --totals-only --recompute 2>&1 | tee "$OUT_DIR/${SLUG}_totals.log" | grep -oE 'totals [0-9]+,[0-9]+ %' | head -1 || echo "N/A")
  ROWS=$("$PY" eval_harness.py --project "$SLUG" --rows --recompute 2>&1 | tee "$OUT_DIR/${SLUG}_rows.log" | grep -oE 'rows ±10 % [0-9]+,[0-9]+ %' | head -1 || echo "N/A")
  EUR=$(grep -oE '€ ±10 % [0-9]+,[0-9]+ %' "$OUT_DIR/${SLUG}_rows.log" | head -1 || echo "N/A")
  SCORECARD=$("$PY" scripts/reading_scorecard.py --project "$SLUG" 2>&1 | tee "$OUT_DIR/${SLUG}_scorecard.log" | tail -1 || echo "N/A")

  # 3) Pull the narrow run's own meta for the row.
  META=$("$PY" -c "
import json
d = json.load(open('$NARROW'))
m = d.get('_meta') or {}
pn = m.get('pass1_narrow') or {}
elapsed = m.get('elapsed_s', 0)
rounds = pn.get('votes_effective', pn.get('votes', 1))
out_tok = pn.get('output_tokens', 0)
in_tok = pn.get('input_tokens', 0)
cost = round(in_tok*15/1e6 + out_tok*75/1e6, 4)
print(f'{elapsed}\t{rounds}\t{out_tok}\t{cost}')
")
  printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" \
    "$SLUG" "$BASELINE_ELAPSED" "$META" "$TOTALS" "$ROWS" "$EUR" "$SCORECARD" \
    >> "$SUMMARY"

  mv "$BASE.bak" "$BASE"
  trap - EXIT
done

echo
echo "Summary → $SUMMARY"
column -t -s $'\t' "$SUMMARY"
