import test from 'node:test';
import assert from 'node:assert/strict';
import { _handleSyncResponse, _hasStorageNotice, updateProject, getProject } from './projectStore.js';

// Minimal localStorage double — the store only needs get/set/removeItem.
function installLocalStorage(initial = {}) {
  const map = new Map(Object.entries(initial));
  const ls = {
    getItem: (k) => (map.has(k) ? map.get(k) : null),
    setItem: (k, v) => { map.set(k, String(v)); },
    removeItem: (k) => { map.delete(k); },
  };
  globalThis.localStorage = ls;
  return ls;
}

// Backend write-through is fire-and-forget; keep it from hitting the network.
globalThis.fetch = async () => ({ ok: true, status: 200 });

test('_handleSyncResponse: 2xx is a silent success', () => {
  assert.equal(_handleSyncResponse({ ok: true, status: 200 }), 'ok');
});

test('_handleSyncResponse: 401 reports an expired session', () => {
  assert.equal(_handleSyncResponse({ ok: false, status: 401 }), 'unauthorized');
});

test('_handleSyncResponse: 5xx reports a failed save', () => {
  assert.equal(_handleSyncResponse({ ok: false, status: 500 }), 'failed');
  assert.equal(_handleSyncResponse({ ok: false, status: 403 }), 'failed');
  assert.equal(_handleSyncResponse(undefined), 'failed');
});

test('updateProject survives a QuotaExceededError and warns once', () => {
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
  assert.equal(_hasStorageNotice(), true);

  // Nothing was written, so the cache still holds the old value.
  assert.equal(getProject('p1').name, 'Testas');
});
