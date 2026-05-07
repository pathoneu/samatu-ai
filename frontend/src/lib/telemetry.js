/**
 * Sprint 0 Fix 6 (frontend): track session timing + gestures, POST at end.
 *
 * Backend persists to JSONL; Sprint 4 reads to compare against manual baseline.
 */

import { API_BASE } from './apiBase';

export function createSession({ projectId, now = () => Date.now() }) {
  const startedAt = now();
  const gestures = [];
  let finished = false;

  return {
    recordGesture(g, gestureNow = now()) {
      if (finished) return;
      gestures.push({
        type: g.type,
        target: g.target,
        outcome: g.outcome,
        duration_ms: g.duration_ms ?? 0,
        timestamp_ms_from_start: gestureNow - startedAt,
      });
    },

    async finish({ exported = false, now: finishNow = now } = {}) {
      if (finished) return;
      finished = true;
      const finishedAt = finishNow();
      const payload = {
        project_id: projectId,
        started_at: Math.floor(startedAt / 1000),
        finished_at: Math.floor(finishedAt / 1000),
        total_seconds: Math.floor((finishedAt - startedAt) / 1000),
        gestures,
        exported,
      };
      try {
        await fetch(`${API_BASE}/api/telemetry/session`, {
          method: 'POST',
          credentials: 'include',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
      } catch (err) {
        // Don't fail the user's flow on telemetry error
        console.warn('telemetry post failed:', err);
      }
    },
  };
}
