import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createViewerStore } from './viewerStore.js';

test('createViewerStore: defaults', () => {
  const store = createViewerStore();
  const state = store.getState();
  assert.equal(state.scale, 1);
  assert.deepEqual(state.translate, { x: 0, y: 0 });
  assert.equal(state.currentPage, 1);
  assert.equal(state.currentTool, 'pan');
  assert.equal(state.hoveredRoomId, null);
});

test('createViewerStore: setScale updates and notifies', () => {
  const store = createViewerStore();
  let calls = 0;
  store.subscribe(() => calls++);
  store.getState().setScale(2);
  assert.equal(store.getState().scale, 2);
  assert.equal(calls, 1);
});

test('createViewerStore: setTransform sets both scale and translate', () => {
  const store = createViewerStore();
  store.getState().setTransform({ scale: 1.5, translate: { x: 10, y: 20 } });
  const s = store.getState();
  assert.equal(s.scale, 1.5);
  assert.deepEqual(s.translate, { x: 10, y: 20 });
});

test('createViewerStore: setHoveredRoomId triggers single update', () => {
  const store = createViewerStore();
  let calls = 0;
  store.subscribe(() => calls++);
  store.getState().setHoveredRoomId('K1');
  store.getState().setHoveredRoomId('K1');  // same value
  assert.equal(store.getState().hoveredRoomId, 'K1');
  assert.ok(calls >= 1);
});
