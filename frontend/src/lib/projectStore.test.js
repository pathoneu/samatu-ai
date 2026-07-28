import test from 'node:test';
import assert from 'node:assert/strict';
import {
  _handleSyncResponse, _hasStorageNotice, _resetSaveState, _getServerVersion,
  updateProject, getProject, getProjects, createProject, flushProjectSaves,
  resetPullCache,
} from './projectStore.js';

// Minimal localStorage double — the store only needs get/set/removeItem.
function installLocalStorage(initial = {}) {
  const map = new Map(Object.entries(initial));
  const ls = {
    getItem: (k) => (map.has(k) ? map.get(k) : null),
    setItem: (k, v) => { map.set(k, String(v)); },
    removeItem: (k) => { map.delete(k); },
    _writes: 0,
  };
  globalThis.localStorage = ls;
  return ls;
}

// Backend write-through is fire-and-forget; keep it from hitting the network.
globalThis.fetch = async () => ({ ok: true, status: 200, json: async () => ({}) });

/** Record every PUT the store makes, so the debounce can be counted. */
function installFetchRecorder(response) {
  const calls = [];
  globalThis.fetch = async (url, opts = {}) => {
    calls.push({ url, method: opts.method, body: opts.body });
    return response
      || { ok: true, status: 200, json: async () => ({ updated_at: '2026-07-28T10:00:00Z' }) };
  };
  return calls;
}

const tick = (ms) => new Promise((r) => setTimeout(r, ms));

test('_handleSyncResponse: 2xx is a silent success', () => {
  assert.equal(_handleSyncResponse({ ok: true, status: 200 }), 'ok');
});

test('_handleSyncResponse: 401 reports an expired session', () => {
  assert.equal(_handleSyncResponse({ ok: false, status: 401 }), 'unauthorized');
});

test('_handleSyncResponse: 409 reports a lost-update conflict', () => {
  assert.equal(_handleSyncResponse({ ok: false, status: 409 }), 'conflict');
});

test('_handleSyncResponse: 5xx reports a failed save', () => {
  assert.equal(_handleSyncResponse({ ok: false, status: 500 }), 'failed');
  assert.equal(_handleSyncResponse({ ok: false, status: 403 }), 'failed');
  assert.equal(_handleSyncResponse(undefined), 'failed');
});

test('updateProject survives a QuotaExceededError and warns once', () => {
  _resetSaveState();
  const ls = installLocalStorage({
    samatu_projects: JSON.stringify([{ id: 'p1', name: 'Testas', darbu_sarasas: [] }]),
  });
  assert.equal(_hasStorageNotice(), false);

  ls.setItem = () => {
    const err = new Error('quota');
    err.name = 'QuotaExceededError';
    throw err;
  };

  // Must NOT throw — the caller is a React click handler.
  const updated = updateProject('p1', { name: 'Perrašyta' });
  assert.equal(updated.name, 'Perrašyta');

  // The localStorage write is now debounced, so the quota notice appears when
  // the save actually flushes, not on the mutating call.
  flushProjectSaves();
  assert.equal(_hasStorageNotice(), true);

  // The edit is NOT lost when localStorage refuses it: the in-memory snapshot
  // keeps it and the backend PUT (the real source of truth) still carries it.
  assert.equal(getProject('p1').name, 'Perrašyta');
});

// ── Debounced save layer (2026-07-28 perf sweep) ──────────────────────────────

test('updateProject coalesces a burst into ONE localStorage write and ONE PUT', async () => {
  _resetSaveState();
  const ls = installLocalStorage({
    samatu_projects: JSON.stringify([{ id: 'p1', name: 'A', darbu_sarasas: [] }]),
  });
  let writes = 0;
  const realSet = ls.setItem;
  ls.setItem = (k, v) => { if (k === 'samatu_projects') writes += 1; realSet(k, v); };
  const puts = installFetchRecorder();

  for (const name of ['A1', 'A12', 'A123', 'A1234', 'A12345']) {
    updateProject('p1', { name });
  }
  // Nothing has hit storage or the network yet — that is the whole point.
  assert.equal(writes, 0, 'no localStorage write during the burst');
  assert.equal(puts.length, 0, 'no PUT during the burst');

  await tick(600);
  assert.equal(writes, 1, 'exactly one localStorage write after the debounce');
  assert.equal(puts.length, 1, 'exactly one PUT after the debounce');
  // Last write wins.
  assert.equal(JSON.parse(puts[0].body).name, 'A12345');
  assert.equal(getProject('p1').name, 'A12345');
});

test('reads during a pending save see the pending value (no read-your-writes hazard)', () => {
  _resetSaveState();
  installLocalStorage({
    samatu_projects: JSON.stringify([{ id: 'p1', name: 'A' }, { id: 'p2', name: 'B' }]),
  });
  installFetchRecorder();
  updateProject('p1', { name: 'A-new' });
  // Second mutation reads the array back — it must contain the first edit.
  updateProject('p2', { name: 'B-new' });
  flushProjectSaves();
  assert.equal(getProject('p1').name, 'A-new');
  assert.equal(getProject('p2').name, 'B-new');
});

test('flushProjectSaves pushes a pending edit immediately (unmount / pagehide)', () => {
  _resetSaveState();
  installLocalStorage({ samatu_projects: JSON.stringify([{ id: 'p1', name: 'A' }]) });
  const puts = installFetchRecorder();
  updateProject('p1', { name: 'typed-then-navigated' });
  assert.equal(puts.length, 0);
  flushProjectSaves();
  assert.equal(puts.length, 1);
  assert.equal(JSON.parse(puts[0].body).name, 'typed-then-navigated');
});

test('createProject is NOT debounced — one-shot intents save immediately', () => {
  _resetSaveState();
  installLocalStorage({ samatu_projects: JSON.stringify([]) });
  const puts = installFetchRecorder();
  const p = createProject({ name: 'Naujas' });
  assert.equal(puts.length, 1, 'create PUTs in the same tick');
  assert.equal(getProject(p.id).name, 'Naujas');
});

// ── Optimistic concurrency (2026-07-28 improvement sweep, F8) ─────────────────

test('PUT carries base_updated_at only once the server has told us a version', async () => {
  _resetSaveState();
  installLocalStorage({ samatu_projects: JSON.stringify([{ id: 'p1', name: 'A' }]) });
  const puts = installFetchRecorder();

  // First save: we have never seen a server timestamp → legacy shape, no field.
  updateProject('p1', { name: 'A1' });
  flushProjectSaves();
  await tick(20);
  assert.equal('base_updated_at' in JSON.parse(puts[0].body), false);

  // The 200 response carried updated_at — the NEXT save must send it back.
  assert.equal(_getServerVersion('p1'), '2026-07-28T10:00:00Z');
  updateProject('p1', { name: 'A2' });
  flushProjectSaves();
  await tick(20);
  assert.equal(JSON.parse(puts[1].body).base_updated_at, '2026-07-28T10:00:00Z');
});

test('a user switch drops the in-memory snapshot (no cross-user leak)', () => {
  // SECURITY. authContext.purgeLocalUserData() clears localStorage and calls
  // resetPullCache(). The debounced save layer added an in-memory copy of the
  // projects array — if resetPullCache didn't drop it too, user B would keep
  // reading (and exporting) user A's projects in the same tab.
  _resetSaveState();
  const ls = installLocalStorage({
    samatu_projects: JSON.stringify([{ id: 'p1', name: 'Vartotojo A projektas' }]),
  });
  installFetchRecorder();
  updateProject('p1', { name: 'A slaptas' });
  assert.equal(getProject('p1').name, 'A slaptas');    // pending, in memory only

  // …user switch: localStorage purged, then resetPullCache().
  ls.removeItem('samatu_projects');
  resetPullCache();

  assert.deepEqual(getProjects(), [], 'previous user data must be gone');
  assert.equal(getProject('p1'), null);
});

test('a 409 does NOT advance the tracked server version', async () => {
  _resetSaveState();
  installLocalStorage({ samatu_projects: JSON.stringify([{ id: 'p1', name: 'A' }]) });
  installFetchRecorder({ ok: false, status: 409, json: async () => ({ error: 'conflict' }) });
  updateProject('p1', { name: 'A1' });
  flushProjectSaves();
  await tick(20);
  assert.equal(_getServerVersion('p1'), undefined);
});
