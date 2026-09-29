// Company details + logo kept on the server per user (audit 2026-09-29,
// frontend-architecture-3). authContext purges `samatu_settings` at every login
// and logout on purpose; before this the purge deleted the ONLY copy, so each
// re-login silently took the logo, IBAN and codes out of his exports.
import test from 'node:test';
import assert from 'node:assert/strict';
import {
  getSettings, saveSettings, flushSettingsWrites, pullSettingsFromBackend,
  ensureSettingsPulled, resetPullCache,
} from './projectStore.js';

function installLocalStorage(initial = {}) {
  const map = new Map(Object.entries(initial));
  globalThis.localStorage = {
    getItem: (k) => (map.has(k) ? map.get(k) : null),
    setItem: (k, v) => { map.set(k, String(v)); },
    removeItem: (k) => { map.delete(k); },
  };
  return map;
}

/**
 * A fake backend: one settings object per account, answering as whichever
 * account the session cookie belongs to right now (`srv.current`). `srv.hold`
 * parks the GET for one account until the test releases it.
 */
function installServer(data = {}) {
  const srv = { data: { ...data }, current: 'A', calls: [], failPut: false, hold: {} };
  globalThis.fetch = async (url, opts = {}) => {
    const method = opts.method || 'GET';
    const who = srv.current;
    srv.calls.push({ url, method, who, body: opts.body });
    if (!String(url).endsWith('/api/settings')) {
      return { ok: true, status: 200, json: async () => ({}) };
    }
    if (method === 'PUT') {
      if (srv.failPut) return { ok: false, status: 500, json: async () => ({}) };
      srv.data[who] = JSON.parse(opts.body);
      return { ok: true, status: 200, json: async () => ({ ok: true }) };
    }
    const answer = JSON.parse(JSON.stringify(srv.data[who] || {}));
    if (srv.hold[who]) await srv.hold[who];
    return { ok: true, status: 200, json: async () => answer };
  };
  return srv;
}

const puts = (srv) => srv.calls.filter((c) => c.method === 'PUT');

/** What authContext does on login, register and logout — unchanged by this fix. */
function purgeLikeAuthContext(ls) {
  for (const k of ['samatu_projects', 'samatu_settings', 'samatu_price_lists']) ls.delete(k);
  resetPullCache();
}

const A = { company_name: 'UAB Pirmoji', iban: 'LT000000000000000001',
  imones_kodas: '300000001', company_logo: 'data:image/png;base64,AAAA' };

test('save writes the cache at once and sends the PUT', async () => {
  installLocalStorage();
  resetPullCache();
  const srv = installServer();
  const next = { company_name: 'UAB Pirmoji', iban: 'LT01' };
  const ret = saveSettings(next);
  assert.deepEqual(ret, next);
  assert.deepEqual(getSettings(), next, 'the cache is written before the server answers');
  assert.equal(await flushSettingsWrites(), 'ok');
  assert.equal(puts(srv).length, 1);
  assert.deepEqual(JSON.parse(puts(srv)[0].body), next);
  assert.deepEqual(srv.data.A, next);
});

test('pull fills the cache from the server (after a login purge)', async () => {
  installLocalStorage();
  resetPullCache();
  const srv = installServer({ A });
  assert.deepEqual(getSettings(), {});
  const got = await pullSettingsFromBackend('u-a');
  assert.deepEqual(got, A);
  assert.deepEqual(getSettings(), A);
  assert.equal(puts(srv).length, 0, 'a pull never writes back');
  // Every later caller shares the same pull: no second GET.
  await ensureSettingsPulled();
  assert.equal(srv.calls.filter((c) => c.method === 'GET').length, 1);
});

test('exports awaiting ensureSettingsPulled see the pulled values', async () => {
  installLocalStorage();
  resetPullCache();
  const srv = installServer({ A });
  let release;
  srv.hold.A = new Promise((r) => { release = r; });
  pullSettingsFromBackend('u-a');               // login fires it, does not await
  const exportRead = ensureSettingsPulled();    // the export starts right away
  release();
  assert.deepEqual(await exportRead, A);
});

test('empty server + details only in this browser: uploaded once', async () => {
  const ls = installLocalStorage({ samatu_settings: JSON.stringify(A) });
  resetPullCache();
  const srv = installServer();
  await pullSettingsFromBackend('u-a');
  await pullSettingsFromBackend('u-a');
  await ensureSettingsPulled();
  assert.equal(await flushSettingsWrites(), 'ok');
  assert.equal(puts(srv).length, 1, 'sent up exactly once');
  assert.deepEqual(srv.data.A, A);
  assert.deepEqual(getSettings(), A, 'the local copy stays');
  assert.equal(ls.get('samatu_settings_owner'), 'u-a');

  // Next session (page reload): the server has them now, nothing goes up again.
  resetPullCache();
  await pullSettingsFromBackend('u-a');
  assert.equal(puts(srv).length, 1);
  assert.deepEqual(getSettings(), A);
});

test('a reader that runs before the login pull does not throw the local copy away', async () => {
  installLocalStorage({ samatu_settings: JSON.stringify(A) });
  resetPullCache();
  const srv = installServer();
  assert.deepEqual(await ensureSettingsPulled(), A, 'account unknown: local copy kept');
  assert.equal(puts(srv).length, 0, 'nothing uploaded without knowing the account');
  await pullSettingsFromBackend('u-a');
  assert.equal(await flushSettingsWrites(), 'ok');
  assert.equal(puts(srv).length, 1);
  assert.deepEqual(srv.data.A, A);
});

test('a cache written for ANOTHER account is never uploaded', async () => {
  const ls = installLocalStorage({
    samatu_settings: JSON.stringify(A),
    samatu_settings_owner: 'u-a',
  });
  resetPullCache();
  const srv = installServer();
  srv.current = 'B';
  const got = await pullSettingsFromBackend('u-b');
  assert.deepEqual(got, {});
  assert.equal(puts(srv).length, 0);
  assert.deepEqual(getSettings(), {}, 'B never sees A\'s details');
  assert.equal(ls.get('samatu_settings_owner'), 'u-b');
});

test('a failed save keeps the local copy and reports it', async () => {
  installLocalStorage();
  resetPullCache();
  const srv = installServer();
  srv.failPut = true;
  const next = { company_name: 'UAB Pirmoji', iban: 'LT01' };
  saveSettings(next);
  assert.equal(await flushSettingsWrites(), 'failed');
  assert.deepEqual(getSettings(), next);

  // Network down entirely: same answer, same local copy.
  globalThis.fetch = async () => { throw new Error('offline'); };
  saveSettings({ ...next, adresas: 'Pirmoji g. 1' });
  assert.equal(await flushSettingsWrites(), 'failed');
  assert.equal(getSettings().adresas, 'Pirmoji g. 1');
});

test('a failed pull leaves the cache alone and the next caller retries', async () => {
  installLocalStorage();
  resetPullCache();
  const srv = installServer({ A });
  const real = globalThis.fetch;
  globalThis.fetch = async () => ({ ok: false, status: 500, json: async () => ({}) });
  assert.equal(await pullSettingsFromBackend('u-a'), null);
  assert.deepEqual(getSettings(), {});
  globalThis.fetch = real;
  assert.deepEqual(await ensureSettingsPulled(), A);
  assert.equal(puts(srv).length, 0);
});

test('account switch: B never sees A\'s details and B\'s first save carries none of them', async () => {
  const ls = installLocalStorage();
  resetPullCache();
  const srv = installServer({ A });
  const seen = [];
  const noA = (s) => !JSON.stringify(s).includes('Pirmoji')
    && !JSON.stringify(s).includes('300000001');

  // A signed in; his session-restore pull is slow and still on the wire.
  let releaseA;
  srv.hold.A = new Promise((r) => { releaseA = r; });
  const lateA = pullSettingsFromBackend('u-a');

  // A logs out, B logs in on the same browser.
  purgeLikeAuthContext(ls);
  seen.push(getSettings());
  srv.current = 'B';
  const pullB = pullSettingsFromBackend('u-b');
  seen.push(getSettings());
  await pullB;
  seen.push(getSettings());

  // A's answer arrives after B is in — it must change nothing.
  releaseA();
  assert.equal(await lateA, null);
  seen.push(getSettings());
  seen.push(await ensureSettingsPulled());
  assert.ok(seen.every(noA), `B saw A's details: ${JSON.stringify(seen)}`);

  // B's first save: only his own values reach the server.
  saveSettings({ ...getSettings(), company_name: 'UAB Antroji' });
  assert.equal(await flushSettingsWrites(), 'ok');
  const bPuts = puts(srv).filter((c) => c.who === 'B');
  assert.equal(bPuts.length, 1);
  assert.deepEqual(JSON.parse(bPuts[0].body), { company_name: 'UAB Antroji' });
  assert.deepEqual(srv.data.A, A, 'A\'s server copy untouched');
  assert.equal(ls.get('samatu_settings_owner'), 'u-b');
});

test('the same account signing in again gets his details back after the purge', async () => {
  const ls = installLocalStorage();
  resetPullCache();
  const srv = installServer({ A });
  await pullSettingsFromBackend('u-a');
  assert.deepEqual(getSettings(), A);
  purgeLikeAuthContext(ls);                    // logout → purge (unchanged)
  assert.deepEqual(getSettings(), {});
  await pullSettingsFromBackend('u-a');        // login → pull
  assert.deepEqual(getSettings(), A, 'logo, IBAN and codes are back for the export');
  assert.equal(puts(srv).length, 0);
});
