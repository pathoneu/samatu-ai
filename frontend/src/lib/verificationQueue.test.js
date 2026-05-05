// frontend/src/lib/verificationQueue.test.js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  buildQueue, advanceQueue, isQueueComplete, classifyDispute,
} from './verificationQueue.js';

test('buildQueue: empty inputs return empty queue', () => {
  assert.deepEqual(buildQueue({ rooms: [], pozicijos: [] }), []);
});

test('buildQueue: skips 🟢 (high confidence) items', () => {
  const queue = buildQueue({
    rooms: [],
    pozicijos: [
      { id: 'p1', kiekis: 10, confidence: 'high', skyrius_label: 'Apdaila', aprasymas: 'Sienų dažymas' },
    ],
  });
  assert.equal(queue.length, 0);
});

test('buildQueue: includes 🟡 + 🔴, orders 🔴 first', () => {
  const queue = buildQueue({
    rooms: [],
    pozicijos: [
      { id: 'p1', kiekis: 10, confidence: 'med', skyrius_label: 'Apdaila', aprasymas: 'A' },
      { id: 'p2', kiekis: 20, confidence: 'low', skyrius_label: 'Apdaila', aprasymas: 'B' },
      { id: 'p3', kiekis: 30, confidence: 'med', skyrius_label: 'Plytelės', aprasymas: 'C' },
    ],
  });
  assert.equal(queue.length, 3);
  assert.equal(queue[0].id, 'p2'); // 🔴 first
  assert.equal(queue[1].confidence, 'med');
  assert.equal(queue[2].confidence, 'med');
});

test('buildQueue: skips locked pozicijos (already user-confirmed)', () => {
  const queue = buildQueue({
    rooms: [],
    pozicijos: [
      { id: 'p1', kiekis: 10, confidence: 'med', override_locked: true, skyrius_label: 'X', aprasymas: 'X' },
      { id: 'p2', kiekis: 20, confidence: 'med', skyrius_label: 'Y', aprasymas: 'Y' },
    ],
  });
  assert.equal(queue.length, 1);
  assert.equal(queue[0].id, 'p2');
});

test('buildQueue: skipped items stay in queue but are flagged', () => {
  // Skipped state lives outside buildQueue; this test verifies that
  // buildQueue accepts a `skipped` Set and propagates it.
  const queue = buildQueue({
    rooms: [],
    pozicijos: [
      { id: 'p1', confidence: 'med', kiekis: 5, skyrius_label: 'X', aprasymas: 'X' },
      { id: 'p2', confidence: 'med', kiekis: 6, skyrius_label: 'Y', aprasymas: 'Y' },
    ],
    skipped: new Set(['p1']),
  });
  assert.equal(queue.length, 2);
  assert.equal(queue.find(q => q.id === 'p1').skipped, true);
  assert.equal(queue.find(q => q.id === 'p2').skipped, false);
});

test('buildQueue: includes room polygon for auto-zoom (when room_id present)', () => {
  const queue = buildQueue({
    rooms: [
      { id: 'r1', polygon_pct: [[0.1, 0.1], [0.5, 0.1], [0.5, 0.5], [0.1, 0.5]] },
    ],
    pozicijos: [
      { id: 'p1', confidence: 'med', kiekis: 5, room_id: 'r1', skyrius_label: 'X', aprasymas: 'X' },
    ],
  });
  assert.equal(queue.length, 1);
  assert.deepEqual(queue[0].polygon, [[0.1, 0.1], [0.5, 0.1], [0.5, 0.5], [0.1, 0.5]]);
});

test('classifyDispute: pozicijos in m²/m³/m → number', () => {
  assert.equal(classifyDispute({ vnt: 'm2' }), 'number');
  assert.equal(classifyDispute({ vnt: 'm3' }), 'number');
  assert.equal(classifyDispute({ vnt: 'm' }), 'number');
  assert.equal(classifyDispute({ vnt: 'kg' }), 'number');
  assert.equal(classifyDispute({ vnt: 'l' }), 'number');
});

test('classifyDispute: pozicijos in vnt with skyrius=elektra/santechnika → count', () => {
  assert.equal(classifyDispute({ vnt: 'vnt', skyrius: 'elektra' }), 'count');
  assert.equal(classifyDispute({ vnt: 'vnt', skyrius: 'santechnika' }), 'count');
});

test('classifyDispute: vnt with no recognized skyrius → number (safe default)', () => {
  assert.equal(classifyDispute({ vnt: 'vnt', skyrius: 'apdaila' }), 'number');
});

test('advanceQueue: increments index', () => {
  assert.equal(advanceQueue(0, 3), 1);
  assert.equal(advanceQueue(1, 3), 2);
});

test('advanceQueue: caps at length (does not overflow)', () => {
  assert.equal(advanceQueue(2, 3), 3);
  assert.equal(advanceQueue(3, 3), 3); // already at end
});

test('isQueueComplete: true when index >= length', () => {
  assert.equal(isQueueComplete(2, 3), false);
  assert.equal(isQueueComplete(3, 3), true);
  assert.equal(isQueueComplete(4, 3), true);
});
