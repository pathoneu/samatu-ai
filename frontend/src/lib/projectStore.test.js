import test from 'node:test';
import assert from 'node:assert/strict';
import {
  _handleSyncResponse, _hasStorageNotice, _resetStorageNotice, _resetSaveState, _getServerVersion,
  updateProject, getProject, getProjects, createProject, flushProjectSaves,
  resetPullCache, exportProjectsBackup, importProjectsBackup, getPriceLists,
  pullProjectsFromBackend, markPriceFillPending, peekPriceFillPending,
  consumePriceFillPending, refreshProjectFromBackend, noteServerVersion, adoptServerProject,
  hasServerRefreshNotice, dismissServerRefreshNotice,
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

test('importProjectsBackup restores price lists without deleting existing ones', async () => {
  _resetSaveState();
  installLocalStorage({
    samatu_projects: JSON.stringify([]),
    samatu_price_lists: JSON.stringify([{ id: 'local', name: 'Vietinis' }]),
  });
  installFetchRecorder();
  const res = await importProjectsBackup(JSON.stringify({
    version: 2,
    projects: [{ id: 'p1', name: 'Iš backupo' }],
    price_lists: [{ id: 'pl1', name: 'Iš backupo kainos' }],
  }));
  assert.equal(res.price_lists_imported, 1);
  const names = getPriceLists().map(p => p.name).sort();
  assert.deepEqual(names, ['Iš backupo kainos', 'Vietinis']);
});

test('a v1 backup (no price_lists) leaves the existing lists untouched', async () => {
  _resetSaveState();
  installLocalStorage({
    samatu_projects: JSON.stringify([]),
    samatu_price_lists: JSON.stringify([{ id: 'local', name: 'Vietinis' }]),
  });
  installFetchRecorder();
  const res = await importProjectsBackup(JSON.stringify({
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
  const res = await importProjectsBackup(JSON.stringify({
    version: 2,
    projects: [],
    price_lists: [{ id: 'pl-restored', name: 'Atkurtas', items: [] }],
  }));
  assert.equal(res.price_lists_imported, 1);
  await tick(0);
  assert.ok(calls.some(c => c.method === 'PUT' && c.url.endsWith('/pl-restored')),
    'a restore that only refills localStorage loses the list on the next pull');
});

// ── the flush reports its verdict (2026-09-02) ───────────────────────────────
//
// The automatic price fill on the disconnect-recovery path writes a SECOND PUT
// for a project the server already owns, so it meets the 409 lost-update guard.
// It used to fire-and-forget: on a refusal the prices lived only in this
// browser's cache, the next backend pull replaced that cache, and the
// sessionStorage marker had already been burned — nothing ever retried.

test('flushProjectSaves resolves with the server verdict per project', async () => {
  _resetSaveState();
  installLocalStorage({ samatu_projects: JSON.stringify([{ id: 'p1', name: 'A' }]) });
  installFetchRecorder();
  updateProject('p1', { name: 'A1' });
  const verdicts = await flushProjectSaves();
  assert.deepEqual(verdicts, [{ id: 'p1', verdict: 'ok' }]);
});

test('flushProjectSaves surfaces a refused write instead of swallowing it', async () => {
  _resetSaveState();
  installLocalStorage({ samatu_projects: JSON.stringify([{ id: 'p1', name: 'A' }]) });
  installFetchRecorder({ ok: false, status: 409, json: async () => ({}) });
  updateProject('p1', { name: 'kainos-iš-kainyno' });
  const verdicts = await flushProjectSaves();
  assert.equal(verdicts.length, 1);
  assert.equal(verdicts[0].verdict, 'conflict');
});

test('flushProjectSaves with nothing pending resolves empty', async () => {
  _resetSaveState();
  installLocalStorage({ samatu_projects: JSON.stringify([{ id: 'p1', name: 'A' }]) });
  installFetchRecorder();
  assert.deepEqual(await flushProjectSaves(), []);
});

// ── the "a fill is still owed" marker ────────────────────────────────────────

function installSessionStorage() {
  const map = new Map();
  globalThis.sessionStorage = {
    getItem: (k) => (map.has(k) ? map.get(k) : null),
    setItem: (k, v) => { map.set(k, String(v)); },
    removeItem: (k) => { map.delete(k); },
  };
}

test('peekPriceFillPending reads without burning the marker', () => {
  installSessionStorage();
  markPriceFillPending('p1');
  assert.equal(peekPriceFillPending('p1'), true);
  assert.equal(peekPriceFillPending('p1'), true, 'peek must not consume');
  assert.equal(consumePriceFillPending('p1'), true);
  assert.equal(peekPriceFillPending('p1'), false, 'consume clears it');
});

test('an unmarked project is never treated as owing a fill', () => {
  installSessionStorage();
  assert.equal(peekPriceFillPending('p-never-marked'), false);
  assert.equal(peekPriceFillPending(null), false);
});


test('refreshProjectFromBackend: a newer server copy replaces the cached one and sets the base version', async () => {
  _resetSaveState();
  installLocalStorage({
    samatu_projects: JSON.stringify([{ id: 'p9', name: 'Sena', updated_at: '2026-09-10T09:00:00Z',
                                      patalpos: [{ nr: '08', perimetras_m: 11.48 }] }]),
  });
  const fresh = { id: 'p9', name: 'Nauja', updated_at: '2026-09-10T09:50:10Z',
                  patalpos: [{ nr: '08', perimetras_m: 13.13, perimetras_saltinis: 'plano_matmenys' }] };
  const calls = [];
  globalThis.fetch = async (url, opts = {}) => {
    calls.push({ url, method: opts.method || 'GET' });
    return { ok: true, status: 200, json: async () => fresh };
  };
  const got = await refreshProjectFromBackend('p9');
  assert.equal(calls.length, 1);
  assert.match(calls[0].url, /\/api\/projects\/p9$/);
  assert.equal(got.patalpos[0].perimetras_m, 13.13);
  assert.equal(getProject('p9').patalpos[0].perimetras_saltinis, 'plano_matmenys');
  assert.equal(_getServerVersion('p9'), '2026-09-10T09:50:10Z');
});

test('refreshProjectFromBackend: an older server copy leaves the cache alone; a missing one is added', async () => {
  _resetSaveState();
  installLocalStorage({
    samatu_projects: JSON.stringify([{ id: 'p9', name: 'Vietinė', updated_at: '2026-09-10T10:00:00Z' }]),
  });
  globalThis.fetch = async () => ({ ok: true, status: 200,
    json: async () => ({ id: 'p9', name: 'Serverio', updated_at: '2026-09-10T09:00:00Z' }) });
  const got = await refreshProjectFromBackend('p9');
  assert.equal(got.name, 'Vietinė');
  // An older server copy is NOT adopted and does not become the base either:
  // the local copy keeps the version it was made on, so a stale-but-newer
  // cache can only 409, never silently overwrite (2026-09-15 review).
  assert.equal(_getServerVersion('p9'), undefined);

  globalThis.fetch = async () => ({ ok: true, status: 200,
    json: async () => ({ id: 'p10', name: 'Tiesioginis adresas', updated_at: '2026-09-10T09:30:00Z' }) });
  const added = await refreshProjectFromBackend('p10');
  assert.equal(added.name, 'Tiesioginis adresas');
  assert.equal(getProjects().length, 2);
  assert.equal(_getServerVersion('p10'), '2026-09-10T09:30:00Z', 'an adopted server copy is the base');
  assert.equal(JSON.parse(globalThis.localStorage.getItem('samatu_server_versions') || '{}').p10,
    '2026-09-10T09:30:00Z', 'and the base survives a reload');
});

test('refreshProjectFromBackend: an unsaved local edit is not swapped away, and a failed fetch is harmless', async () => {
  _resetSaveState();
  installLocalStorage({
    samatu_projects: JSON.stringify([{ id: 'p9', name: 'Sena', updated_at: '2026-09-10T09:00:00Z' }]),
  });
  installFetchRecorder();                       // the debounced PUT goes nowhere
  updateProject('p9', { name: 'Redaguota' });   // pending, not yet flushed
  globalThis.fetch = async () => ({ ok: true, status: 200,
    json: async () => ({ id: 'p9', name: 'Serverio', updated_at: '2026-09-10T12:00:00Z' }) });
  const got = await refreshProjectFromBackend('p9');
  assert.equal(got.name, 'Redaguota');
  await flushProjectSaves();

  globalThis.fetch = async () => { throw new Error('offline'); };
  const same = await refreshProjectFromBackend('p9');
  assert.equal(same.name, 'Redaguota');
  assert.equal(await refreshProjectFromBackend(null), null);
});

// ── The server moved on since this browser last saw it (Pathon v3 W1-F F4) ────
//
// The cached copy's `updated_at` is THIS BROWSER's clock (updateProject stamps it), the server's is the
// server's: comparing the two let a cache stamped „later" — a PC clock a few minutes fast, a database put
// back from a backup — stay on screen after a version was restored elsewhere. The like-for-like marker is
// the server's own stamp this browser last saw (samatu_server_versions).

const MERGED = [{ nr: '04', plotas_m2: 61.81 }, { nr: '05', plotas_m2: 35.5, _sujungta_i: '04' }];
const RESTORED = [{ nr: '04', plotas_m2: 26.31 }, { nr: '05', plotas_m2: 35.5 }];

function cacheAndSeen(cachedStamp, seen, patalpos = MERGED) {
  _resetSaveState();
  installLocalStorage({
    samatu_projects: JSON.stringify([{ id: 'p9', name: 'H', updated_at: cachedStamp, patalpos }]),
  });
  noteServerVersion('p9', seen);   // what samatu_server_versions holds after a reload
}

test('refreshProjectFromBackend: a server copy restored elsewhere wins over a cache stamped later, and says so once', async () => {
  // this browser merged at 20:20 by ITS clock (10 min fast); the server stored that save at 20:10:04 and a
  // version was restored elsewhere at 20:11
  cacheAndSeen('2026-10-18T20:20:03.120Z', '2026-10-18T20:10:04Z');
  globalThis.fetch = async () => ({ ok: true, status: 200,
    json: async () => ({ id: 'p9', name: 'H', updated_at: '2026-10-18T20:11:00Z', patalpos: RESTORED }) });
  const got = await refreshProjectFromBackend('p9');
  assert.deepEqual(got.patalpos, RESTORED);
  assert.deepEqual(getProject('p9').patalpos, RESTORED, 'the cache holds the server copy');
  assert.equal(_getServerVersion('p9'), '2026-10-18T20:11:00Z', 'and the next save is based on it');
  assert.equal(hasServerRefreshNotice('p9'), true);
  dismissServerRefreshNotice('p9');
  assert.equal(hasServerRefreshNotice('p9'), false);
});

test('refreshProjectFromBackend: a database put back with an OLDER stamp is still the server moving on', async () => {
  cacheAndSeen('2026-10-18T20:10:03.900Z', '2026-10-18T20:10:04Z');
  globalThis.fetch = async () => ({ ok: true, status: 200,
    json: async () => ({ id: 'p9', name: 'H', updated_at: '2026-10-18T17:54:51Z', patalpos: RESTORED }) });
  assert.deepEqual((await refreshProjectFromBackend('p9')).patalpos, RESTORED);
  assert.equal(hasServerRefreshNotice('p9'), true);
});

test('refreshProjectFromBackend: the server unchanged since this browser saw it — the cache stays, nothing said', async () => {
  cacheAndSeen('2026-10-18T20:20:03.120Z', '2026-10-18T20:10:04Z');
  globalThis.fetch = async () => ({ ok: true, status: 200,
    json: async () => ({ id: 'p9', name: 'H', updated_at: '2026-10-18T20:10:04Z', patalpos: RESTORED }) });
  assert.deepEqual((await refreshProjectFromBackend('p9')).patalpos, MERGED);
  assert.equal(hasServerRefreshNotice('p9'), false);
});

test('refreshProjectFromBackend: its own save whose answer never came back is taken silently (same content)', async () => {
  // the tab closed with a PUT on the wire: the server holds this browser's last edit under a stamp it never saw
  cacheAndSeen('2026-10-18T20:10:03.900Z', '2026-10-18T20:09:00Z');
  globalThis.fetch = async () => ({ ok: true, status: 200,
    json: async () => ({ id: 'p9', name: 'H', updated_at: '2026-10-18T20:10:04Z', patalpos: MERGED,
      user_id: 'u1', status: 'ready', vat_rate: 21, created_at: '2026-10-01T08:00:00Z' }) });
  assert.deepEqual((await refreshProjectFromBackend('p9')).patalpos, MERGED);
  assert.equal(_getServerVersion('p9'), '2026-10-18T20:10:04Z');
  assert.equal(hasServerRefreshNotice('p9'), false, 'nothing changed for him — nothing to say');
});

// ── One PUT in flight per project, never aborted (2026-09-29 audit) ──────────
//
// A new save used to ABORT the PUT still on the wire. The server had often
// stored that request already, so its version moved on while this tab kept the
// old base — the next PUT was a false 409, and so was every save after it.

/** fetch double whose responses the test releases by hand. */
function installDeferredFetch() {
  const calls = [];
  globalThis.fetch = (url, opts = {}) => new Promise((resolve, reject) => {
    calls.push({ url, method: opts.method, body: JSON.parse(opts.body || 'null'),
                 signal: opts.signal, resolve, reject });
  });
  return calls;
}
const okVersion = (v) => ({ ok: true, status: 200, json: async () => ({ updated_at: v }) });

test('three quick saves send two PUTs: the second on the first answer\'s version, with the newest content', async () => {
  _resetSaveState();
  installLocalStorage({ samatu_projects: JSON.stringify([{ id: 'p1', name: 'A' }]) });
  noteServerVersion('p1', 'v0');
  const calls = installDeferredFetch();

  updateProject('p1', { name: 'e1' }); const f1 = flushProjectSaves();
  updateProject('p1', { name: 'e2' }); const f2 = flushProjectSaves();
  updateProject('p1', { name: 'e3' }); const f3 = flushProjectSaves();
  assert.equal(calls.length, 1, 'only one PUT on the wire per project');
  assert.equal(calls[0].body.base_updated_at, 'v0');

  calls[0].resolve(okVersion('v1'));
  assert.deepEqual(await f1, [{ id: 'p1', verdict: 'ok' }]);
  assert.equal(calls.length, 2, 'the remembered snapshot goes out once the first is answered');
  assert.equal(calls[1].body.base_updated_at, 'v1', 'carries the version that just arrived');
  assert.equal(calls[1].body.name, 'e3', 'carries the LATEST snapshot, e2 is never sent');

  calls[1].resolve(okVersion('v2'));
  assert.deepEqual(await f2, [{ id: 'p1', verdict: 'ok' }]);
  assert.deepEqual(await f3, [{ id: 'p1', verdict: 'ok' }]);
  assert.equal(calls.length, 2);
  assert.ok(calls.every(c => !c.signal?.aborted), 'no PUT is ever aborted');
  assert.equal(_getServerVersion('p1'), 'v2');
});

/**
 * A tiny server with the backend's lost-update rule. `applyAt` says when it
 * stores a request: on receipt (the audit's case — the response is what is
 * slow) or only when it answers. The first answer is slow, later ones fast.
 */
function installVersionedServer(applyAt) {
  const srv = { stored: 'A', version: 'v0', n: 0, calls: [], conflicts: 0 };
  const apply = (body) => {
    if (body.base_updated_at && body.base_updated_at !== srv.version) {
      srv.conflicts += 1;
      return { ok: false, status: 409, json: async () => ({ current_updated_at: srv.version }) };
    }
    srv.stored = body.name;
    srv.version = `v${++srv.n}`;
    const v = srv.version;
    return { ok: true, status: 200, json: async () => ({ updated_at: v }) };
  };
  globalThis.fetch = (url, opts = {}) => {
    const body = JSON.parse(opts.body);
    srv.calls.push({ body, signal: opts.signal });
    const early = applyAt === 'receipt' ? apply(body) : null;
    const delay = srv.calls.length === 1 ? 40 : 2;
    return new Promise((resolve, reject) => {
      const t = setTimeout(() => resolve(early || apply(body)), delay);
      opts.signal?.addEventListener('abort', () => {
        clearTimeout(t);
        reject(Object.assign(new Error('aborted'), { name: 'AbortError' }));
      });
    });
  };
  return srv;
}

for (const applyAt of ['receipt', 'response']) {
  test(`a slow first answer and a fast second cannot leave the older content on the server (stored on ${applyAt})`, async () => {
    _resetSaveState();
    installLocalStorage({ samatu_projects: JSON.stringify([{ id: 'p1', name: 'A' }]) });
    noteServerVersion('p1', 'v0');
    const srv = installVersionedServer(applyAt);

    updateProject('p1', { name: 'e1' }); flushProjectSaves();
    await tick(10);                                   // e1 is on the wire, its answer is slow
    updateProject('p1', { name: 'e2' });
    const verdicts = await flushProjectSaves();
    await tick(60);

    assert.deepEqual(verdicts, [{ id: 'p1', verdict: 'ok' }]);
    assert.equal(srv.stored, 'e2', 'the last change the user made is the last one stored');
    assert.equal(srv.conflicts, 0, 'no false conflict');
    assert.ok(srv.calls.every(c => !c.signal?.aborted), 'nothing aborted');

    // …and the tab is not stuck: a later save goes through too.
    updateProject('p1', { name: 'e3' });
    assert.deepEqual(await flushProjectSaves(), [{ id: 'p1', verdict: 'ok' }]);
    assert.equal(srv.stored, 'e3');
  });
}

test('a real 409 still reports a conflict, and the waiting snapshot does not advance the version', async () => {
  _resetSaveState();
  installLocalStorage({ samatu_projects: JSON.stringify([{ id: 'p1', name: 'A' }]) });
  noteServerVersion('p1', 'v0');
  const calls = installDeferredFetch();
  const conflict = { ok: false, status: 409, json: async () => ({ current_updated_at: 'other-tab' }) };

  updateProject('p1', { name: 'e1' }); const f1 = flushProjectSaves();
  updateProject('p1', { name: 'e2' }); const f2 = flushProjectSaves();
  calls[0].resolve(conflict);
  assert.deepEqual(await f1, [{ id: 'p1', verdict: 'conflict' }]);
  assert.equal(calls.length, 2);
  assert.equal(calls[1].body.base_updated_at, 'v0', 'a conflict keeps the old base, as before');
  calls[1].resolve(conflict);
  assert.deepEqual(await f2, [{ id: 'p1', verdict: 'conflict' }]);
  assert.equal(_getServerVersion('p1'), 'v0');
});

test('a failed in-flight PUT does not lose the snapshot waiting behind it', async () => {
  _resetSaveState();
  installLocalStorage({ samatu_projects: JSON.stringify([{ id: 'p1', name: 'A' }]) });
  noteServerVersion('p1', 'v0');
  const calls = installDeferredFetch();

  updateProject('p1', { name: 'e1' }); const f1 = flushProjectSaves();
  updateProject('p1', { name: 'e2' }); const f2 = flushProjectSaves();
  calls[0].reject(new TypeError('Failed to fetch'));
  assert.deepEqual(await f1, [{ id: 'p1', verdict: 'failed' }]);
  assert.equal(calls.length, 2, 'the waiting snapshot is still sent');
  assert.equal(calls[1].body.name, 'e2');
  assert.equal(calls[1].body.base_updated_at, 'v0');
  calls[1].resolve(okVersion('v1'));
  assert.deepEqual(await f2, [{ id: 'p1', verdict: 'ok' }]);
  assert.equal(_getServerVersion('p1'), 'v1');
});

test('refreshProjectFromBackend does not swap away an edit waiting behind a PUT on the wire', async () => {
  _resetSaveState();
  installLocalStorage({ samatu_projects: JSON.stringify([{ id: 'p1', name: 'A', updated_at: '2026-09-29T09:00:00Z' }]) });
  noteServerVersion('p1', 'v0');
  const calls = installDeferredFetch();
  updateProject('p1', { name: 'e1' }); flushProjectSaves();
  updateProject('p1', { name: 'e2' }); const waiting = flushProjectSaves();   // waits behind e1

  const refreshed = refreshProjectFromBackend('p1');
  calls[1].resolve({ ok: true, status: 200,
    json: async () => ({ id: 'p1', name: 'e1', updated_at: '2999-01-01T00:00:00Z' }) });
  assert.equal((await refreshed).name, 'e2', 'the waiting edit stays in the cache');
  calls[0].resolve(okVersion('v1'));
  await tick(0);
  assert.equal(calls[2].body.name, 'e2');
  calls[2].resolve(okVersion('v2'));
  assert.deepEqual(await waiting, [{ id: 'p1', verdict: 'ok' }]);
});

// ── Backup import reaches the server (2026-09-29 audit) ──────────────────────
//
// The import merged into the local cache only. The next Dashboard pull replaces
// that cache with the server's list, so every restored project the server did
// not have was deleted without a word.

/** A backend double for /api/projects: list, detail and PUT with the 409 rule. */
function installProjectServer(initial = [], { failPut = () => false, failList = false } = {}) {
  const rows = new Map(initial.map(p => [p.id, { ...p }]));
  const calls = [];
  let n = 0;
  const json = (status, data) => ({ ok: status < 300, status, json: async () => data });
  globalThis.fetch = async (url, opts = {}) => {
    const method = opts.method || 'GET';
    const body = opts.body ? JSON.parse(opts.body) : null;
    calls.push({ url, method, body });
    const m = url.match(/\/api\/projects(?:\/([^/?]+))?$/);
    if (!m) return json(200, {});                       // price lists and the like
    const id = m[1];
    if (!id) {
      if (failList) return json(500, {});
      return json(200, { projects: [...rows.values()].map(r => ({ id: r.id, updated_at: r.updated_at })) });
    }
    if (method === 'GET') return rows.has(id) ? json(200, rows.get(id)) : json(404, {});
    if (failPut(id)) return json(500, {});
    const { base_updated_at, ...data } = body;
    const cur = rows.get(id);
    if (cur && base_updated_at && base_updated_at !== cur.updated_at) {
      return json(409, { current_updated_at: cur.updated_at });
    }
    const saved = { ...data, id, updated_at: `2026-09-29T12:00:0${++n}Z` };
    rows.set(id, saved);
    return json(200, saved);
  };
  return { rows, calls };
}

test('imported projects the server does not have are sent, and a later pull keeps them', async () => {
  _resetSaveState();
  installLocalStorage({ samatu_projects: JSON.stringify([]) });
  const srv = installProjectServer([{ id: 'srv1', name: 'Serverio', updated_at: '2026-09-20T10:00:00Z' }]);

  const res = await importProjectsBackup(JSON.stringify({
    version: 2,
    projects: [
      { id: 'r1', name: 'Atkurtas 1', updated_at: '2026-09-10T10:00:00Z' },
      { id: 'r2', name: 'Atkurtas 2', updated_at: '2026-09-11T10:00:00Z' },
      { id: 'demo-objektas-a', is_demo: true, name: 'Pavyzdys' },
    ],
  }));
  const puts = srv.calls.filter(c => c.method === 'PUT');
  assert.deepEqual(puts.map(c => c.url.split('/').pop()).sort(), ['r1', 'r2'],
    'every new project is sent; the local-only sample never is');
  assert.ok(puts.every(c => !('base_updated_at' in c.body)), 'no base for an id the server does not have');
  assert.equal(res.projects_saved, 2);
  assert.equal(res.projects_failed, 0);
  assert.equal(res.projects_kept_server, 0);

  // The Dashboard pull that used to delete them.
  await pullProjectsFromBackend({ force: true });
  const ids = getProjects().map(p => p.id).sort();
  assert.deepEqual(ids, ['r1', 'r2', 'srv1']);
  assert.equal(getProject('r1').name, 'Atkurtas 1');
});

test('a project that could not be sent is reported, not dropped silently', async () => {
  _resetSaveState();
  installLocalStorage({ samatu_projects: JSON.stringify([]) });
  let failing = true;
  const srv = installProjectServer([], { failPut: id => failing && id === 'bad' });
  const file = JSON.stringify({
    version: 2,
    projects: [{ id: 'good', name: 'Gerai' }, { id: 'bad', name: 'Nepavyko' }],
  });

  const res = await importProjectsBackup(file);
  assert.equal(res.projects_saved, 1);
  assert.equal(res.projects_failed, 1);

  // Importing the same file again retries the one that failed, even though
  // this browser's cache already holds it.
  failing = false;
  const again = await importProjectsBackup(file);
  assert.equal(again.projects_saved, 1);
  assert.equal(again.projects_failed, 0);
  assert.equal(srv.rows.get('bad').name, 'Nepavyko');
});

test('when the server cannot be asked, nothing is sent and every project is reported as not saved', async () => {
  _resetSaveState();
  installLocalStorage({ samatu_projects: JSON.stringify([]) });
  const srv = installProjectServer([], { failList: true });

  const res = await importProjectsBackup(JSON.stringify({
    version: 2, projects: [{ id: 'r1', name: 'Atkurtas' }],
  }));
  assert.equal(srv.calls.filter(c => c.method === 'PUT').length, 0);
  assert.equal(res.projects_saved, 0);
  assert.equal(res.projects_failed, 1);
  assert.equal(getProject('r1').name, 'Atkurtas', 'still in this browser, as before');
});

test('a newer server copy is kept; an imported copy newer than the server is sent on the server version', async () => {
  _resetSaveState();
  installLocalStorage({ samatu_projects: JSON.stringify([]) });
  const srv = installProjectServer([
    { id: 'kept', name: 'Serverio naujesnis', updated_at: '2026-09-20T10:00:00Z' },
    { id: 'older', name: 'Serverio senesnis', updated_at: '2026-09-20T10:00:00Z' },
  ]);

  const res = await importProjectsBackup(JSON.stringify({
    version: 2,
    projects: [
      { id: 'kept', name: 'Senas iš failo', updated_at: '2026-09-01T10:00:00Z' },
      { id: 'older', name: 'Naujas iš failo', updated_at: '2026-09-25T10:00:00Z' },
    ],
  }));
  const puts = srv.calls.filter(c => c.method === 'PUT');
  assert.deepEqual(puts.map(c => c.url.split('/').pop()), ['older']);
  assert.equal(puts[0].body.base_updated_at, '2026-09-20T10:00:00Z');
  assert.equal(res.projects_saved, 1);
  assert.equal(res.projects_kept_server, 1);
  assert.equal(srv.rows.get('kept').name, 'Serverio naujesnis');
  assert.notEqual(getProject('kept')?.name, 'Senas iš failo', 'the older file copy is not adopted');
});

test('a versionSource rides the PUT that carries the edit, and a plain save after it carries none', async () => {
  _resetSaveState();
  installLocalStorage({ samatu_projects: JSON.stringify([{ id: 'p1', name: 'A' }]) });
  const puts = installFetchRecorder();
  updateProject('p1', { name: 'A1' }, { versionSource: 'perskaityta' });
  updateProject('p1', { name: 'A2' });                 // same burst: still the re-read's PUT
  await flushProjectSaves();
  assert.equal(puts.length, 1);
  assert.equal(JSON.parse(puts[0].body)._versija_saltinis, 'perskaityta');
  assert.equal(JSON.parse(puts[0].body).name, 'A2');
  updateProject('p1', { name: 'A3' });
  await flushProjectSaves();
  assert.equal('_versija_saltinis' in JSON.parse(puts[1].body), false);
  assert.equal('_versija_saltinis' in getProject('p1'), false, 'never stored on the project');
});

test('adoptServerProject replaces the cached project and re-bases the next save, with no PUT', async () => {
  _resetSaveState();
  installLocalStorage({ samatu_projects: JSON.stringify([{ id: 'p1', name: 'Dabar' }, { id: 'p2', name: 'Kitas' }]) });
  const puts = installFetchRecorder();
  const got = adoptServerProject({ id: 'p1', name: 'Grąžinta', updated_at: '2026-10-16T11:00:00Z' });
  assert.equal(got.name, 'Grąžinta');
  assert.equal(getProject('p2').name, 'Kitas');
  assert.equal(_getServerVersion('p1'), '2026-10-16T11:00:00Z');
  await tick(20);
  assert.equal(puts.length, 0, 'adopting is not a save');
  updateProject('p1', { name: 'Po to' });
  await flushProjectSaves();
  assert.equal(JSON.parse(puts[0].body).base_updated_at, '2026-10-16T11:00:00Z');
});

test('every save keeps the rows on what he measured — a moved length moves its row, a project without links is left alone', async () => {
  _resetSaveState();
  installLocalStorage({ samatu_projects: JSON.stringify([
    {
      id: 'm1', name: 'Matavimai',
      pageScalesDurable: { 1: { calibrated: true, metersPerPointX: 0.01, metersPerPointY: 0.01 } },
      measurements: [{ id: 'd1', kind: 'distance', page: 1, points: [{ x: 0, y: 0 }, { x: 420, y: 0 }] }],
      darbu_sarasas: [{ id: 'a', aprasymas: 'Grindjuostės', mato_vnt: 'm', kiekis: 40 }],
    },
    { id: 'm2', name: 'Be matavimų', darbu_sarasas: [] },
  ]) });
  installFetchRecorder();
  // linking alone (the field the panel writes) is enough — the store brings the row along
  let saved = updateProject('m1', { measurementRows: { 'm:d1': { eilute_id: 'a', kaip: 'pridėti' } } });
  assert.equal(saved.darbu_sarasas[0].kiekis, 44.2);
  // the viewer saves its list with the line made longer: the row follows, no link on the objects needed
  saved = updateProject('m1', { measurements: [{ id: 'd1', kind: 'distance', page: 1, points: [{ x: 0, y: 0 }, { x: 500, y: 0 }] }] });
  assert.equal(saved.darbu_sarasas[0].kiekis, 45);
  assert.equal(getProject('m1').darbu_sarasas[0].kiekis, 45);
  // a project with no links: the rows a caller hands in are stored as they came
  const rows = [{ id: 'x', kiekis: 1 }];
  assert.equal(updateProject('m2', { darbu_sarasas: rows }).darbu_sarasas, rows);
  await flushProjectSaves();
});

// ── The cache under Safari's quota (2026-10-19) ───────────────────────────────

/** A localStorage double with WebKit's limit: ~2.5 M characters per origin, all keys together. */
function installQuotaStorage(initial = {}, limitChars = 2_500_000) {
  const ls = installLocalStorage(initial);
  const map = new Map(Object.entries(initial));
  const used = (except) => [...map].reduce((n, [k, v]) => (k === except ? n : n + k.length + v.length), 0);
  ls.getItem = (k) => (map.has(k) ? map.get(k) : null);
  ls.removeItem = (k) => { map.delete(k); };
  ls.setItem = (k, v) => {
    const s = String(v);
    if (used(k) + k.length + s.length > limitChars) {
      const e = new Error('The quota has been exceeded.'); e.name = 'QuotaExceededError'; throw e;
    }
    map.set(k, s);
  };
  return ls;
}

const bigProject = (id, day, chars = 750_000) => ({
  id, name: id, updated_at: `2026-10-${String(day).padStart(2, '0')}T10:00:00Z`, blob: 'x'.repeat(chars),
});

test('a 6 MB project set: the newest projects that fit are cached, nothing throws, no warning', () => {
  _resetSaveState();
  // 8 × 0,75 M ≈ 6 M characters — what a pull of a real account leaves in memory; the seed is not quota-checked
  const set = Array.from({ length: 8 }, (_, i) => bigProject(`p${i + 1}`, i + 1));
  const ls = installQuotaStorage({ samatu_projects: JSON.stringify(set) });
  installFetchRecorder();
  _resetStorageNotice();
  updateProject('p2', { name: 'Redaguota' });    // an old project with an unsent edit
  assert.doesNotThrow(() => flushProjectSaves());
  const cached = JSON.parse(ls.getItem('samatu_projects'));
  const ids = cached.map((p) => p.id);
  assert.ok(cached.length >= 2 && cached.length < 8, `cached ${cached.length}`);
  assert.ok(ids.includes('p2'), 'the project with the unsent edit is cached first');
  assert.ok(ids.includes('p8'), 'then the newest');
  assert.ok(!ids.includes('p1'), 'the oldest is the one left out');
  assert.equal(cached.find((p) => p.id === 'p2').name, 'Redaguota');
  assert.equal(_hasStorageNotice(), false, 'a partial cache is not an error');
  assert.equal(getProjects().length, 8, 'this session still sees every project');
});

test('a refused write never leaves the old copy behind to win after a reload', () => {
  _resetSaveState();
  const old = { id: 'p1', name: 'Senas', updated_at: '2026-10-01T10:00:00Z', blob: 'x'.repeat(100) };
  const ls = installQuotaStorage({ samatu_projects: JSON.stringify([old]) }, 2_000);
  installFetchRecorder();
  updateProject('p1', { name: 'Naujas', blob: 'y'.repeat(5_000) });   // the new copy cannot fit at all
  assert.doesNotThrow(() => flushProjectSaves());
  assert.equal(ls.getItem('samatu_projects'), null, 'the stale cached copy is gone');
  _resetSaveState();   // a reload: the cache is all there is
  assert.equal(getProject('p1'), null, 'nothing stale to read — the page loads it from the server');
});

test('storage blocked outright (Safari „Block all cookies"): a save neither throws nor loses the edit', () => {
  _resetSaveState();
  const ls = installLocalStorage({ samatu_projects: JSON.stringify([{ id: 'p1', name: 'A' }]) });
  const blocked = () => { const e = new Error('The operation is insecure.'); e.name = 'SecurityError'; throw e; };
  ls.setItem = blocked;
  ls.removeItem = blocked;
  const puts = installFetchRecorder();
  updateProject('p1', { name: 'B' });
  assert.doesNotThrow(() => flushProjectSaves());
  assert.equal(getProject('p1').name, 'B');
  assert.equal(JSON.parse(puts[puts.length - 1].body).name, 'B');
});
