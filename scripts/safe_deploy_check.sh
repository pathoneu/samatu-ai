#!/bin/zsh
# Is a prod extraction in flight? Pushing to main triggers a Railway redeploy,
# and a container restart KILLS a running extraction — including the detached
# drain thread that would otherwise have saved it.
#
# Learned the hard way 2026-07-29: a push at 18:44 destroyed a user's 26-minute
# run that was still making Claude calls at 18:36. The client polled for a
# project id that could never be written. ALWAYS run this before pushing to main.
LAST_START=$(railway logs 2>/dev/null | grep "extract-interior-stream: ip=" | tail -1)
LAST_CALL=$(railway logs 2>/dev/null | grep -c "anthropic.com")
LAST_SAVE=$(railway logs 2>/dev/null | grep -cE "orphan drain: saved project|record_usage")
echo "last extraction start : ${LAST_START:-none in window}"
echo "anthropic calls seen  : $LAST_CALL"
echo "saves/metering seen   : $LAST_SAVE"
if [ -n "$LAST_START" ] && [ "$LAST_SAVE" -eq 0 ]; then
  echo ""
  echo "⛔ AN EXTRACTION MAY BE IN FLIGHT — do NOT push to main."
  echo "   A redeploy restarts the container and kills it mid-run."
  exit 1
fi
echo "✅ no extraction in flight — safe to push"
