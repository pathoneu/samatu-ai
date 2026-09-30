// A stale second tab must not save one account's company details onto another
// (2026-09-30). Tab 1 signs A out and B in; tab 2 still shows A's Settings page.
// Its save goes out with B's cookie — so every save now says which account the
// page was loaded for, and the server answers 409 when that is not the session's.
import test from 'node:test';
import assert from 'node:assert/strict';
import {
  getSettings, saveSettings, flushSettingsWrites, pullSettingsFromBackend, resetPullCache,
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

const HEADER = 'X-Settings-For-User';

/** A fake server answering as the account whose cookie the browser holds now. */
function installServer(data = {}) {
  const srv = { data: { ...data }, current: 'A', calls: [] };
  globalThis.fetch = async (url, opts = {}) => {
    const method = opts.method || 'GET';
    const who = srv.current;
    const forUser = opts.headers?.[HEADER];
    srv.calls.push({ url, method, who, forUser, body: opts.body });
    if (method === 'PUT') {
      if (forUser !== undefined && forUser !== who) {
        return { ok: false, status: 409, json: async () => ({ detail: 'kita paskyra' }) };
      }
      srv.data[who] = JSON.parse(opts.body);
      return { ok: true, status: 200, json: async () => ({ ok: true }) };
    }
    return { ok: true, status: 200, json: async () => JSON.parse(JSON.stringify(srv.data[who] || {})) };
  };
  return srv;
}

const puts = (srv) => srv.calls.filter((c) => c.method === 'PUT');
const A = { company_name: 'UAB Pirmoji', iban: 'LT000000000000000001' };
const B = { company_name: 'UAB Antroji', iban: 'LT000000000000000002' };

test('a save says which account the page was loaded for', async () => {
  installLocalStorage({ samatu_cache_owner: 'A' });
  resetPullCache();
  const srv = installServer({ A });
  await pullSettingsFromBackend('A');
  saveSettings({ ...A, adresas: 'Pirmoji g. 1' });
  assert.equal(await flushSettingsWrites(), 'ok');
  assert.equal(puts(srv).length, 1);
  assert.equal(puts(srv)[0].forUser, 'A');
  assert.equal(srv.data.A.adresas, 'Pirmoji g. 1');
});

test('a 409 is reported as another account and keeps the local copy', async () => {
  const ls = installLocalStorage({ samatu_cache_owner: 'A' });
  resetPullCache();
  const srv = installServer({ A, B });
  await pullSettingsFromBackend('A');
  // The cookie now belongs to B (signed in elsewhere), the browser marker not yet.
  srv.current = 'B';
  const typed = { ...A, adresas: 'Pirmoji g. 2' };
  saveSettings(typed);
  assert.equal(await flushSettingsWrites(), 'other_account');
  assert.equal(puts(srv)[0].forUser, 'A');
  assert.deepEqual(srv.data.B, B, 'nothing landed on B');
  assert.deepEqual(getSettings(), typed, 'the local copy stays');
  assert.equal(ls.get('samatu_settings_owner'), 'A');
});

test('a stale tab does not write its account\'s details into the cache the new account reads', async () => {
  const ls = installLocalStorage({ samatu_cache_owner: 'A' });
  resetPullCache();
  const srv = installServer({ A, B });
  await pullSettingsFromBackend('A');     // tab 2 was loaded for A
  // Tab 1 signs A out and B in: the shared cache is now B's.
  srv.current = 'B';
  ls.set('samatu_cache_owner', 'B');
  ls.set('samatu_settings', JSON.stringify(B));
  ls.set('samatu_settings_owner', 'B');
  saveSettings({ ...A, adresas: 'Pirmoji g. 3' });
  assert.equal(await flushSettingsWrites(), 'other_account');
  assert.deepEqual(JSON.parse(ls.get('samatu_settings')), B, 'B\'s cache untouched');
  assert.equal(ls.get('samatu_settings_owner'), 'B');
  assert.deepEqual(srv.data.B, B, 'nothing landed on B');
});

test('before the account is known the save still goes out, without the header', async () => {
  installLocalStorage();
  resetPullCache();
  const srv = installServer();
  saveSettings(A);
  assert.equal(await flushSettingsWrites(), 'ok');
  assert.equal(puts(srv)[0].forUser, undefined);
});
