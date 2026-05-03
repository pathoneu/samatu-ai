import { test, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { createSession } from './telemetry.js';

let posted = null;
beforeEach(() => {
  posted = null;
  globalThis.fetch = async (url, opts) => {
    posted = { url, body: JSON.parse(opts.body) };
    return { ok: true, json: async () => ({ ok: true }) };
  };
});

test('createSession tracks gestures and POSTs on finish', async () => {
  const session = createSession({ projectId: 'p1', now: () => 1000 });
  session.recordGesture({
    type: 'G1', target: { kind: 'room', id: 'K1' },
    outcome: 'success', duration_ms: 3000,
  }, /* now= */ 2500);
  await session.finish({ exported: true, now: () => 5000 });

  assert.equal(posted.url, '/api/telemetry/session');
  assert.equal(posted.body.project_id, 'p1');
  assert.equal(posted.body.total_seconds, 4);  // (5000-1000)/1000
  assert.equal(posted.body.gestures.length, 1);
  assert.equal(posted.body.gestures[0].timestamp_ms_from_start, 1500);
  assert.equal(posted.body.exported, true);
});
