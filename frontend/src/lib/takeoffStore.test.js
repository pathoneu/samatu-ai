import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  loadTakeoff,
  saveTakeoff,
  subscribeTakeoff,
  TAKEOFF_CHANGE_EVENT,
} from './takeoffStore.js';

function installBrowserMocks() {
  const data = new Map();
  globalThis.localStorage = {
    getItem: (key) => data.get(key) ?? null,
    setItem: (key, value) => { data.set(key, String(value)); },
    removeItem: (key) => { data.delete(key); },
    clear: () => { data.clear(); },
  };

  class TestCustomEvent extends Event {
    constructor(type, init = {}) {
      super(type);
      this.detail = init.detail;
    }
  }

  globalThis.CustomEvent = TestCustomEvent;
  globalThis.window = new EventTarget();
}

test('saveTakeoff: persists and notifies same-tab subscribers for matching project', () => {
  installBrowserMocks();

  const calls = [];
  const unsubscribe = subscribeTakeoff('p1', (event) => calls.push(event.detail));

  saveTakeoff('p1', { polygons: [{ id: 'a' }], meta: {} });
  saveTakeoff('p2', { polygons: [{ id: 'b' }], meta: {} });

  unsubscribe();

  assert.equal(calls.length, 1);
  assert.equal(calls[0].projectId, 'p1');
  assert.equal(calls[0].storageKey, 'samatu_takeoff_p1');
  assert.equal(loadTakeoff('p1').polygons[0].id, 'a');
});

test('subscribeTakeoff: unsubscribe stops future notifications', () => {
  installBrowserMocks();

  let count = 0;
  const unsubscribe = subscribeTakeoff('p1', () => { count += 1; });
  saveTakeoff('p1', { polygons: [], meta: {} });
  unsubscribe();
  window.dispatchEvent(new CustomEvent(TAKEOFF_CHANGE_EVENT, {
    detail: { projectId: 'p1', storageKey: 'samatu_takeoff_p1' },
  }));

  assert.equal(count, 1);
});
