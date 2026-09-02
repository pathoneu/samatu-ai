import test from 'node:test';
import assert from 'node:assert/strict';
import {
  _handleSyncResponse, _hasStorageNotice, _resetSaveState, _getServerVersion,
  updateProject, getProject, getProjects, createProject, flushProjectSaves,
  resetPullCache, exportProjectsBackup, importProjectsBackup, getPriceLists,
  pullProjectsFromBackend,
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

test('a failing _persist cannot make edit N+1 revert edit N (A5 regression)', async () => {
  // THE hazard this asserts against: with localStorage refusing writes (quota),
  // the store used to re-read the STALE array for the next mutation, so edit
  // N+1 was merged onto a blob that never had edit N — and the backend PUT
  // shipped that regression as the new truth. The in-memory snapshot is what
  // makes this safe; if someone removes it, this test fails.
  _resetSaveState();
  const ls = installLocalStorage({
    samatu_projects: JSON.stringify([{ id: 'p1', name: 'A', kaina: 0 }]),
  });
  ls.setItem = () => { const e = new Error('quota'); e.name = 'QuotaExceededError'; throw e; };
  const puts = installFetchRecorder();

  updateProject('p1', { kaina: 42 });        // edit N — localStorage refuses it
  flushProjectSaves();
  updateProject('p1', { name: 'B' });        // edit N+1 — must build on edit N
  flushProjectSaves();
  await tick(20);

  assert.equal(getProject('p1').kaina, 42, 'edit N survives in the read path');
  assert.equal(getProject('p1').name, 'B');
  const lastBody = JSON.parse(puts[puts.length - 1].body);
  assert.equal(lastBody.kaina, 42, 'the PUT still carries edit N');
  assert.equal(lastBody.name, 'B');
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

// ── C1 (2026-07-28 audit): backups must carry the localStorage-only data ─────
// OLD: exportProjectsBackup() wrote projects + settings only. Price lists live
// ONLY in localStorage (no backend mirror) and authContext purges them on
// logout — so "Atsarginė kopija", the one feature whose whole job is surviving
// a browser wipe, silently dropped the data with the most manual work in it.

test('exportProjectsBackup includes price lists and settings', () => {
  _resetSaveState();
  installLocalStorage({
    samatu_projects: JSON.stringify([{ id: 'p1', name: 'A' }]),
    samatu_price_lists: JSON.stringify([{ id: 'pl1', name: 'Mano kainos', items: [] }]),
    samatu_settings: JSON.stringify({ company_name: 'UAB Testas' }),
  });
  const payload = JSON.parse(exportProjectsBackup());
  assert.equal(payload.version, 2);
  assert.equal(payload.price_lists.length, 1);
  assert.equal(payload.price_lists[0].name, 'Mano kainos');
  assert.equal(payload.settings.company_name, 'UAB Testas');
});

test('importProjectsBackup restores price lists without deleting existing ones', () => {
  _resetSaveState();
  installLocalStorage({
    samatu_projects: JSON.stringify([]),
    samatu_price_lists: JSON.stringify([{ id: 'local', name: 'Vietinis' }]),
  });
  installFetchRecorder();
  const res = importProjectsBackup(JSON.stringify({
    version: 2,
    projects: [{ id: 'p1', name: 'Iš backupo' }],
    price_lists: [{ id: 'pl1', name: 'Iš backupo kainos' }],
  }));
  assert.equal(res.price_lists_imported, 1);
  const names = getPriceLists().map(p => p.name).sort();
  assert.deepEqual(names, ['Iš backupo kainos', 'Vietinis']);
});

test('a v1 backup (no price_lists) leaves the existing lists untouched', () => {
  _resetSaveState();
  installLocalStorage({
    samatu_projects: JSON.stringify([]),
    samatu_price_lists: JSON.stringify([{ id: 'local', name: 'Vietinis' }]),
  });
  installFetchRecorder();
  const res = importProjectsBackup(JSON.stringify({
    version: 1, projects: [{ id: 'p1', name: 'Senas backupas' }],
  }));
  assert.equal(res.price_lists_imported, 0);
  assert.equal(getPriceLists().length, 1, 'a v1 restore must not wipe price lists');
  assert.equal(getProject('p1').name, 'Senas backupas');
});

// ── A4 (2026-07-28 audit): a partial pull must not shrink the cache ──────────

test('pullProjectsFromBackend leaves the cache alone when one project fails', async () => {
  _resetSaveState();
  installLocalStorage({
    samatu_projects: JSON.stringify([
      { id: 'p1', name: 'Vietinis A' }, { id: 'p2', name: 'Vietinis B' },
    ]),
  });
  globalThis.fetch = async (url) => {
    if (url.endsWith('/api/projects')) {
      return { ok: true, status: 200,
               json: async () => ({ projects: [{ id: 'p1' }, { id: 'p2' }] }) };
    }
    if (url.endsWith('/p2')) return { ok: false, status: 500, json: async () => ({}) };
    return { ok: true, status: 200, json: async () => ({ id: 'p1', name: 'Serverio A' }) };
  };

  const out = await pullProjectsFromBackend({ force: true });
  assert.equal(out, null, 'a partial pull reports failure');
  // The cache still has BOTH projects — the old code replaced it with just p1.
  assert.equal(getProjects().length, 2);
  assert.equal(getProject('p2').name, 'Vietinis B');

  // …and the guard was released, so a later attempt can complete.
  globalThis.fetch = async (url) => {
    if (url.endsWith('/api/projects')) {
      return { ok: true, status: 200,
               json: async () => ({ projects: [{ id: 'p1' }, { id: 'p2' }] }) };
    }
    const id = url.slice(url.lastIndexOf('/') + 1);
    return { ok: true, status: 200, json: async () => ({ id, name: `Serverio ${id}` }) };
  };
  const out2 = await pullProjectsFromBackend();   // NOT forced
  assert.equal(out2.length, 2, 'the retry must not be blocked by _hasPulled');
});

test('a project deleted between the list and the detail fetch (404) is not a failure', async () => {
  _resetSaveState();
  installLocalStorage({ samatu_projects: JSON.stringify([]) });
  globalThis.fetch = async (url) => {
    if (url.endsWith('/api/projects')) {
      return { ok: true, status: 200,
               json: async () => ({ projects: [{ id: 'p1' }, { id: 'gone' }] }) };
    }
    if (url.endsWith('/gone')) return { ok: false, status: 404, json: async () => ({}) };
    return { ok: true, status: 200, json: async () => ({ id: 'p1', name: 'Liko' }) };
  };
  const out = await pullProjectsFromBackend({ force: true });
  assert.equal(out.length, 1, 'a 404 must not block the pull forever');
  assert.equal(out[0].name, 'Liko');
});

test('noteServerVersion re-bases the tab on a version produced outside the PUT path', async () => {
  const { noteServerVersion } = await import('./projectStore.js');
  noteServerVersion('p-reval', '2026-08-23T10:00:00Z');
  assert.equal(_getServerVersion('p-reval'), '2026-08-23T10:00:00Z');
  // Missing values must be ignored, never clobber a known version with undefined.
  noteServerVersion('p-reval', undefined);
  assert.equal(_getServerVersion('p-reval'), '2026-08-23T10:00:00Z');
});

// ── Price lists: write-through (2026-09-02) ─────────────────────────────────

test('createPriceList writes the cache AND pushes to the backend', async () => {
  const { createPriceList } = await import('./projectStore.js');
  _resetSaveState();
  installLocalStorage({ samatu_price_lists: JSON.stringify([]) });
  const calls = installFetchRecorder();
  const pl = createPriceList({ name: 'Mano kainynas', items: [{ aprasymas: 'x', kaina: 1 }] });
  assert.equal(getPriceLists().length, 1);
  await tick(0);
  const put = calls.find(c => c.method === 'PUT');
  assert.ok(put, 'expected a PUT to the backend');
  assert.ok(put.url.endsWith(`/api/price-lists/${pl.id}`));
  assert.equal(JSON.parse(put.body).items.length, 1);
});

test('deletePriceList drops it locally and on the backend; a 404 is not an error', async () => {
  const { deletePriceList } = await import('./projectStore.js');
  _resetSaveState();
  installLocalStorage({
    samatu_price_lists: JSON.stringify([{ id: 'pl1', name: 'A' }, { id: 'pl2', name: 'B' }]),
  });
  const calls = installFetchRecorder({ ok: false, status: 404, json: async () => ({}) });
  deletePriceList('pl1');
  assert.deepEqual(getPriceLists().map(p => p.id), ['pl2']);
  await tick(0);
  assert.ok(calls.some(c => c.method === 'DELETE' && c.url.endsWith('/pl1')));
});

test('setDefaultPriceList keeps exactly one default and syncs both rows', async () => {
  const { setDefaultPriceList, getDefaultPriceList } = await import('./projectStore.js');
  _resetSaveState();
  installLocalStorage({
    samatu_price_lists: JSON.stringify([
      { id: 'pl1', name: 'A', is_default: true },
      { id: 'pl2', name: 'B' },
    ]),
  });
  const calls = installFetchRecorder();
  setDefaultPriceList('pl2');
  assert.equal(getDefaultPriceList().id, 'pl2');
  assert.equal(getPriceLists().filter(p => p.is_default).length, 1);
  await tick(0);
  assert.equal(calls.filter(c => c.method === 'PUT').length, 2, 'both rows pushed');
  // Clicking the star again clears it — no default at all is a valid state.
  setDefaultPriceList('pl2');
  assert.equal(getDefaultPriceList(), null);
});

test('a failed price-list pull leaves the cache alone', async () => {
  const { pullPriceListsFromBackend } = await import('./projectStore.js');
  _resetSaveState();
  installLocalStorage({
    samatu_price_lists: JSON.stringify([{ id: 'pl1', name: 'Turimas' }]),
  });
  globalThis.fetch = async () => ({ ok: false, status: 500, json: async () => ({}) });
  assert.equal(await pullPriceListsFromBackend({ force: true }), null);
  assert.equal(getPriceLists().length, 1, 'a 500 must not read as "no kainynai"');

  globalThis.fetch = async () => ({
    ok: true, status: 200,
    json: async () => ({ price_lists: [{ id: 'srv', name: 'Iš serverio', items: [] }] }),
  });
  const pulled = await pullPriceListsFromBackend();   // guard released by the failure
  assert.equal(pulled.length, 1);
  assert.equal(getPriceLists()[0].name, 'Iš serverio');
});

test('restoring a backup pushes the recovered price lists to the backend', async () => {
  _resetSaveState();
  installLocalStorage({
    samatu_projects: JSON.stringify([]),
    samatu_price_lists: JSON.stringify([]),
  });
  const calls = installFetchRecorder();
  const res = importProjectsBackup(JSON.stringify({
    version: 2,
    projects: [],
    price_lists: [{ id: 'pl-restored', name: 'Atkurtas', items: [] }],
  }));
  assert.equal(res.price_lists_imported, 1);
  await tick(0);
  assert.ok(calls.some(c => c.method === 'PUT' && c.url.endsWith('/pl-restored')),
    'a restore that only refills localStorage loses the list on the next pull');
});
