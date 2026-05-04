// frontend/src/lib/scaleStore.test.js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createScaleStore } from './scaleStore.js';

test('createScaleStore: defaults', () => {
  const store = createScaleStore();
  assert.equal(store.getState().ratio, 50);
  assert.equal(store.getState().locked, true);
});

test('createScaleStore: setRatio updates', () => {
  const store = createScaleStore();
  store.getState().setRatio(100);
  assert.equal(store.getState().ratio, 100);
});

test('createScaleStore: toggleLock flips', () => {
  const store = createScaleStore();
  assert.equal(store.getState().locked, true);
  store.getState().toggleLock();
  assert.equal(store.getState().locked, false);
  store.getState().toggleLock();
  assert.equal(store.getState().locked, true);
});

test('createScaleStore: setRatio coerces strings to numbers', () => {
  const store = createScaleStore();
  store.getState().setRatio('200');
  assert.equal(store.getState().ratio, 200);
});

test('createScaleStore: setRatio rejects non-positive values silently', () => {
  const store = createScaleStore();
  store.getState().setRatio(0);
  assert.equal(store.getState().ratio, 50); // unchanged
  store.getState().setRatio(-50);
  assert.equal(store.getState().ratio, 50); // unchanged
});
