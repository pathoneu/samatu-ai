// Whose cached projects, company details and price lists are in this browser
// (2026-09-30). Login and register purge the cache before the new account sees
// anything; a Google sign-in finishes through a server redirect, so the app only
// learns about the new session when it restores it on page load — and the purge
// never ran. The restore now compares the signed-in account with the owner
// recorded for the cache and purges a foreign cache before anything reads it.
import test from 'node:test';
import assert from 'node:assert/strict';
import {
  claimLocalCache, getProjects, getSettings, getPriceLists, resetPullCache,
} from './projectStore.js';
import { noteSignInStarted, takeSignInHint } from './signInHint.js';

function installStorage(name, initial = {}) {
  const map = new Map(Object.entries(initial));
  globalThis[name] = {
    getItem: (k) => (map.has(k) ? map.get(k) : null),
    setItem: (k, v) => { map.set(k, String(v)); },
    removeItem: (k) => { map.delete(k); },
  };
  return map;
}

// Invented values only.
const A_CACHE = {
  samatu_projects: JSON.stringify([{ id: 'p-a', name: 'Pirmosios projektas' }]),
  samatu_settings: JSON.stringify({ company_name: 'UAB Pirmoji', iban: 'LT000000000000000001' }),
  samatu_price_lists: JSON.stringify([{ id: 'pl-a', name: 'Pirmosios kainynas', items: [] }]),
};

function assertNothingOfA() {
  assert.deepEqual(getProjects(), []);
  assert.deepEqual(getSettings(), {});
  assert.deepEqual(getPriceLists(), []);
}

test('Google session for B restored over A\'s cache: A\'s data is gone before any read', () => {
  const ls = installStorage('localStorage', {
    ...A_CACHE, samatu_cache_owner: 'A', samatu_settings_owner: 'A',
  });
  installStorage('sessionStorage');
  resetPullCache();
  noteSignInStarted();                     // the Google button, before the redirect
  // …page reload after the server redirect: the restore learns the session is B's.
  const purged = claimLocalCache('B', { signIn: takeSignInHint() });
  assert.equal(purged, true);
  assertNothingOfA();
  assert.equal(ls.get('samatu_cache_owner'), 'B');
  assert.equal(ls.has('samatu_settings_owner'), false);
});

test('a marked foreign cache is purged on a plain reload too (no sign-in hint)', () => {
  installStorage('localStorage', { ...A_CACHE, samatu_cache_owner: 'A', samatu_settings_owner: 'A' });
  installStorage('sessionStorage');
  resetPullCache();
  assert.equal(claimLocalCache('B', { signIn: takeSignInHint() }), true);
  assertNothingOfA();
});

test('same user returns: nothing is purged (reload or Google sign-in)', () => {
  for (const signIn of [false, true]) {
    const ls = installStorage('localStorage', {
      ...A_CACHE, samatu_cache_owner: 'A', samatu_settings_owner: 'A',
    });
    resetPullCache();
    assert.equal(claimLocalCache('A', { signIn }), false);
    for (const [k, v] of Object.entries(A_CACHE)) assert.equal(ls.get(k), v, `${k} kept`);
    assert.equal(ls.get('samatu_cache_owner'), 'A');
    assert.equal(ls.get('samatu_settings_owner'), 'A');
    assert.equal(getProjects().length, 1);
    assert.equal(getSettings().company_name, 'UAB Pirmoji');
    assert.equal(getPriceLists().length, 1);
  }
});

test('a cache with no owner marker is foreign when someone signs in', () => {
  const ls = installStorage('localStorage', { ...A_CACHE });
  resetPullCache();
  assert.equal(claimLocalCache('B', { signIn: true }), true);
  assertNothingOfA();
  assert.equal(ls.get('samatu_cache_owner'), 'B');
});

test('company details written for another account are foreign even if the cache marker matches', () => {
  installStorage('localStorage', { ...A_CACHE, samatu_cache_owner: 'B', samatu_settings_owner: 'A' });
  resetPullCache();
  assert.equal(claimLocalCache('B', { signIn: false }), true);
  assertNothingOfA();
});

test('unmarked cache on a plain reload: projects and price lists dropped, company details kept', () => {
  // A cache written before the owner marker existed, found by a page reload of
  // the same session. Projects and price lists come back from the server; the
  // company details may exist only here (they went to the server only since
  // 2026-09-29), so they stay for the one-time carry-over.
  const ls = installStorage('localStorage', { ...A_CACHE });
  resetPullCache();
  assert.equal(claimLocalCache('A', { signIn: false }), false);
  assert.deepEqual(getProjects(), []);
  assert.deepEqual(getPriceLists(), []);
  assert.equal(getSettings().company_name, 'UAB Pirmoji');
  assert.equal(ls.get('samatu_cache_owner'), 'A');
});

test('an empty browser: nothing to purge, the owner is recorded', () => {
  const ls = installStorage('localStorage');
  resetPullCache();
  assert.equal(claimLocalCache('B', { signIn: true }), false);
  assert.equal(ls.get('samatu_cache_owner'), 'B');
});

test('no account, nothing done', () => {
  const ls = installStorage('localStorage', { ...A_CACHE, samatu_cache_owner: 'A' });
  assert.equal(claimLocalCache(null), false);
  assert.equal(ls.get('samatu_cache_owner'), 'A');
  assert.equal(ls.get('samatu_projects'), A_CACHE.samatu_projects);
});

test('the sign-in hint is used once', () => {
  installStorage('sessionStorage');
  assert.equal(takeSignInHint(), false);
  noteSignInStarted();
  assert.equal(takeSignInHint(), true);
  assert.equal(takeSignInHint(), false);
});

test('storage that throws never breaks the restore', () => {
  globalThis.sessionStorage = {
    getItem: () => { throw new Error('blocked'); },
    setItem: () => { throw new Error('blocked'); },
    removeItem: () => { throw new Error('blocked'); },
  };
  noteSignInStarted();
  assert.equal(takeSignInHint(), false);
});
