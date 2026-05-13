#!/usr/bin/env bash
# Week 1 Task 1.2 (D2 bridge): forbid arithmetic patterns that have produced
# `NaN` in the live UI. Run as a pre-commit hook or in CI.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

failed=0

scan() {
  local pattern="$1"
  local description="$2"
  if grep -RInE "$pattern" frontend/src 2>/dev/null; then
    echo "ERROR: $description"
    failed=1
  fi
}

scan 'null\s*\+\s*null' \
  "Forbidden 'null + null' arithmetic — use safeNumber() or backend recompute."

# When the full D2 cutover lands (Week 3), uncomment:
# scan 'calculateInteriorQuantities' \
#   "Frontend interiorCalc.js is forbidden — use POST /api/recompute-quantities."

if [[ $failed -eq 0 ]]; then
  echo "OK: no forbidden frontend math patterns in frontend/src"
fi
exit $failed
