#!/usr/bin/env bash
# pass1_narrow_gate.sh -- v4 (2026-10-28). Reads a fresh extract with SAMATU_PASS1_NARROW=1 for
# every corpus project and scores it against the samata (eval_harness --totals-only --recompute
# and --rows --recompute) and the reading scorecard. The script DOES NOT overwrite
# ground_truth/<slug>/ai_extract.json -- it writes ai_extract_narrow.json alongside, swaps it in
# for scoring, and restores BOTH ai_extract.json and ai_extract_meta.json with `git checkout --`
# afterwards.
#
# NOT run from this task (no credit for paid runs). The founder funds the reads from this script.
#
# Expected cost: ~0,3-0,5 USD per project per round at Opus 4.7 rates (narrow prompt ~3 000
# output tokens vs today's ~10 000 and the image prefix is cached across voting rounds). The
# default compares the one-round narrow against the stored baseline:
#
#     bash scripts/pass1_narrow_gate.sh                  # votes = 1, every corpus project
#     bash scripts/pass1_narrow_gate.sh objektas_h       # votes = 1, one project
#     VOTES=3 bash scripts/pass1_narrow_gate.sh          # votes = 3 (compare 1 vs 3 rounds)
#     DRY_RUN=1 bash scripts/pass1_narrow_gate.sh        # prints the plan + estimated cost, no API
#
# Baseline runtimes stored in each project's ai_extract.json._meta.elapsed_s (full Pass-1):
#   objektas_a 208,3 s - objektas_b 468,3 s - objektas_c 308,7 s - objektas_d 212,4 s
#   objektas_g 1510,6 s - objektas_h 735,4 s
# Narrow estimate (one round, zoom skipped): ~100-200 s per project. ~0,3-0,5 USD/round.
#
# Gate -- the narrow run passes when all of these hold vs the baseline:
#   - totals +/-1 pp of 57,50 %         (eval_harness --totals-only --recompute)
#   - rows +/-10 % within 1 pp of 9,0 % (eval_harness --rows --recompute)
#   - euro +/-10 % within 1 pp of 18,0 % (eval_harness --rows --recompute, euro columns)
#   - scorecard tiers unchanged         (scripts/reading_scorecard.py)

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PY="${PY:-$ROOT/venv/bin/python}"
VOTES="${VOTES:-1}"
BUDGET_USD="${BUDGET_USD:-10.0}"
DRY_RUN="${DRY_RUN:-0}"
PROJECTS="${@:-objektas_a objektas_b objektas_c objektas_d objektas_g objektas_h}"

echo "pass1_narrow gate -- $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "  python  : $PY"
echo "  votes   : $VOTES"
echo "  projects: $PROJECTS"
echo "  budget  : \$$BUDGET_USD"
echo

OUT_DIR="docs/superpowers/fixtures/pass1_narrow_$(date -u +%Y-%m-%d)"
mkdir -p "$OUT_DIR"

# ---- Phase 1: read every project -----------------------------------------------
# Uses pass1_fast_measure.py with --tag narrow and SAMATU_PASS1_NARROW=1 exported.
# That runner writes ground_truth/<slug>/ai_extract_narrow.json and NEVER overwrites
# ai_extract.json or ai_extract_meta.json, so no mv/restore is needed here.
#
# defect (a) fixed (2026-10-28): the old code called run_vision_on_truth_set.py --only,
# which reads registry projects with has_cached_extract: false and skips a/g/h silently.
# Those three have has_cached_extract: true and were "0 project(s) to process" on
# every gate run, so their narrow files were baseline copies. The runner handles ALL
# corpus slugs regardless of that registry flag.

SWAPPED_SLUGS=""

if [[ "$DRY_RUN" == "1" ]]; then
  echo "(dry run -- would call pass1_fast_measure.py with SAMATU_PASS1_NARROW=1"
  echo " SAMATU_PASS1_NARROW_VOTES=$VOTES for each of: $PROJECTS)"
  SAMATU_PASS1_NARROW=1 SAMATU_PASS1_NARROW_VOTES=$VOTES \
    "$PY" scripts/pass1_fast_measure.py $PROJECTS --tag narrow --dry-run
  echo "(dry run complete -- no API calls made)"
  exit 0
fi

SAMATU_PASS1_NARROW=1 SAMATU_PASS1_NARROW_VOTES=$VOTES \
  "$PY" scripts/pass1_fast_measure.py $PROJECTS --tag narrow || {
    echo "pass1_fast_measure.py exited non-zero -- aborting gate"
    exit 1
  }

# Collect which slugs produced a narrow file.
for SLUG in $PROJECTS; do
  NARROW="ground_truth/$SLUG/ai_extract_narrow.json"
  if [[ -f "$NARROW" ]]; then
    SWAPPED_SLUGS="$SWAPPED_SLUGS $SLUG"
  else
    echo "  $SLUG -- no ai_extract_narrow.json produced; skipping scoring for this slug"
  fi
done

if [[ -z "$SWAPPED_SLUGS" ]]; then
  echo "No narrow extracts produced -- nothing to score."
  exit 1
fi

# ---- Phase 2: corpus-wide scoring (one pass after all projects are read) -------
# Swap every narrow extract in for scoring, score once across the whole corpus,
# then restore with git checkout.

echo
echo "=== Scoring corpus: $SWAPPED_SLUGS ==="
for SLUG in $SWAPPED_SLUGS; do
  NARROW="ground_truth/$SLUG/ai_extract_narrow.json"
  if [[ -f "$NARROW" ]]; then
    cp "$NARROW" "ground_truth/$SLUG/ai_extract.json"
  fi
done

"$PY" eval_harness.py --totals-only --recompute 2>&1 | tee "$OUT_DIR/narrow_totals.log"
"$PY" eval_harness.py --rows --recompute        2>&1 | tee "$OUT_DIR/narrow_rows.log"
"$PY" scripts/reading_scorecard.py              2>&1 | tee "$OUT_DIR/narrow_scorecard.log"

# defect (b) fixed (2026-10-28): restore BOTH ai_extract.json AND ai_extract_meta.json
# for every swapped slug explicitly, then check git status for any remaining tracked
# modifications and fail loudly.

echo
echo "=== Restoring baseline files ==="
for SLUG in $SWAPPED_SLUGS; do
  git checkout -- "ground_truth/$SLUG/ai_extract.json" 2>/dev/null || true
  git checkout -- "ground_truth/$SLUG/ai_extract_meta.json" 2>/dev/null || true
  echo "  $SLUG: restored ai_extract.json + ai_extract_meta.json"
done

echo
echo "=== git status check (nothing tracked should stay modified) ==="
DIRTY="$(git status --short ground_truth)"
if [[ -n "$DIRTY" ]]; then
  echo "ERROR: tracked ground_truth files are still modified after restore:" >&2
  echo "$DIRTY" >&2
  exit 1
fi
echo "(clean)"

# ---- Phase 3: print gate-decision headlines ------------------------------------
echo
echo "=== Totals headline ==="
grep -n "Billed lines\|Corpus mean" "$OUT_DIR/narrow_totals.log" || echo "(no match)"

echo
echo "=== Rows headline ==="
grep -n "Billed lines\|Corpus mean" "$OUT_DIR/narrow_rows.log" || echo "(no match)"

echo
echo "=== Scorecard (last 4 lines) ==="
tail -4 "$OUT_DIR/narrow_scorecard.log"

echo
echo "=== Per-project rows table ==="
awk '/Project.*rows.*within10/{p=1} p{print} /Corpus mean/{p=0}' "$OUT_DIR/narrow_rows.log" \
  || echo "(rows table not found)"

# ---- Phase 4: runtime comparison TSV ------------------------------------------
RUNTIME_TSV="$OUT_DIR/narrow_runtime.tsv"
printf "slug\tbaseline_elapsed_s\tnarrow_elapsed_s\tnarrow_rounds\toutput_tokens\tcost_usd\n" \
  > "$RUNTIME_TSV"

for SLUG in $SWAPPED_SLUGS; do
  BASE="ground_truth/$SLUG/ai_extract.json"
  NARROW="ground_truth/$SLUG/ai_extract_narrow.json"
  if [[ ! -f "$NARROW" ]]; then
    continue
  fi
  "$PY" -c "
import json, sys
base_elapsed = (json.load(open('$BASE')).get('_meta') or {}).get('elapsed_s', '')
d = json.load(open('$NARROW'))
m = d.get('_meta') or {}
pn = m.get('pass1_narrow') or {}
narrow_elapsed = m.get('elapsed_s', 0)
rounds = pn.get('votes_effective', pn.get('votes', 1))
out_tok = pn.get('output_tokens', 0)
in_tok = pn.get('input_tokens', 0)
cost = round(in_tok*15/1e6 + out_tok*75/1e6, 4)
print(f'$SLUG\t{base_elapsed}\t{narrow_elapsed}\t{rounds}\t{out_tok}\t{cost}')
" >> "$RUNTIME_TSV" || echo "$SLUG -- could not read narrow meta"
done

echo
echo "=== Runtime comparison ==="
column -t -s $'\t' "$RUNTIME_TSV"

echo
echo "Summary logs -> $OUT_DIR/"
