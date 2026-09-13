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

// ── the shared pilot session (2026-09-13) ─────────────────────────────────────

import {
  _resetPilotSessions, flushPilotSessions, markExported, pilotSession, postSessionRecord, recordPilot,
  releasePilotSession,
} from './telemetry.js';

test('one pilot session per project, events with offsets, export marks it, flush posts and clears', () => {
  _resetPilotSessions();
  let t = 10_000;
  const now = () => t;
  const a = pilotSession('p1', now);
  t = 12_500;
  recordPilot('p1', 'fact_accept', { kind: 'fact', id: 'plotas', room: '01' }, 'success', now);
  t = 20_000;
  recordPilot('p1', 'row_delete', { kind: 'row', id: 'Slenksniai' }, 'success', now);
  assert.equal(pilotSession('p1', now), a, 'the same session comes back');
  t = 65_000;
  markExported('p1', 'excel', now);
  const posted = [];
  const out = flushPilotSessions({ now: () => 70_000, post: (p) => posted.push(p) });
  assert.equal(out.length, 1);
  const p = posted[0];
  assert.equal(p.project_id, 'p1');
  assert.equal(p.started_at, 10);
  assert.equal(p.total_seconds, 60);
  assert.equal(p.exported, true);
  assert.deepEqual(p.gestures.map((g) => [g.type, g.timestamp_ms_from_start]),
    [['fact_accept', 2500], ['row_delete', 10000], ['export', 55000]]);
  assert.deepEqual(p.gestures[0].target, { kind: 'fact', id: 'plotas', room: '01' });
  assert.deepEqual(p.gestures[2].target, { kind: 'export', id: 'excel' });
  assert.equal(flushPilotSessions({ post: () => { throw new Error('must not post'); } }).length, 0, 'flushed sessions are gone');
});

test('an empty blink of a session is dropped; a bare project id is ignored', () => {
  _resetPilotSessions();
  pilotSession('p2', () => 1000);
  assert.equal(flushPilotSessions({ now: () => 2000, post: () => { throw new Error('noise'); } }).length, 0);
  assert.equal(pilotSession(null), null);
  recordPilot(undefined, 'fact_accept');   // never throws
});

test('postSessionRecord prefers a beacon and falls back to a keepalive fetch', () => {
  const beacons = [];
  const ok = postSessionRecord({ project_id: 'p3' }, { beacon: (url, body) => { beacons.push({ url, body }); return true; } });
  assert.equal(ok, true);
  assert.equal(beacons.length, 1);
  assert.match(beacons[0].url, /\/api\/telemetry\/session$/);
  const fetched = [];
  const ok2 = postSessionRecord({ project_id: 'p3' }, {
    beacon: () => false,
    fetchFn: (url, opts) => { fetched.push({ url, opts }); return Promise.resolve({ ok: true }); },
  });
  assert.equal(ok2, true);
  assert.equal(fetched[0].opts.keepalive, true);
  assert.equal(JSON.parse(fetched[0].opts.body).project_id, 'p3');
});

test('a remount within the release delay keeps one session; a real leave flushes it', () => {
  _resetPilotSessions();
  const timers = new Map();
  let nextId = 1;
  const setTimeoutFn = (fn, ms) => { const h = nextId++; timers.set(h, { fn, ms }); return h; };
  const clearTimeoutFn = (h) => timers.delete(h);
  const fire = () => { for (const [h, tmr] of [...timers]) { timers.delete(h); tmr.fn(); } };
  const posted = [];
  const post = (p) => posted.push(p);
  let t = 1000;
  const now = () => t;

  const first = pilotSession('p9', now);
  recordPilot('p9', 'fact_accept', { kind: 'fact', id: 'plotas' }, 'success', now);
  releasePilotSession('p9', { setTimeoutFn, clearTimeoutFn, now, post });       // the sheet unmounts…
  t = 1400;
  assert.equal(pilotSession('p9', now, { clearTimeoutFn }), first, '…and remounts: same session');
  assert.equal(timers.size, 0, 'the scheduled release was cancelled');
  fire();
  assert.equal(posted.length, 0);

  t = 9000;
  releasePilotSession('p9', { setTimeoutFn, clearTimeoutFn, now, post });       // he leaves for good
  assert.equal(timers.size, 1);
  t = 11000;
  fire();
  assert.equal(posted.length, 1);
  assert.equal(posted[0].total_seconds, 10);
  assert.equal(posted[0].gestures.length, 1);
  assert.equal(pilotSession('p9', now) === first, false, 'a later visit starts a new session');
  _resetPilotSessions();
});
