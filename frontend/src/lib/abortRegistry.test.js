// frontend/src/lib/abortRegistry.test.js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createAbortRegistry } from './abortRegistry.js';

test('takeSignal aborts previous controller for same kind', () => {
  const reg = createAbortRegistry();
  const sig1 = reg.takeSignal('g1');
  assert.equal(sig1.aborted, false);
  const sig2 = reg.takeSignal('g1');
  assert.equal(sig1.aborted, true, 'old g1 signal should be aborted');
  assert.equal(sig2.aborted, false);
});

test('different kinds do not interfere', () => {
  const reg = createAbortRegistry();
  const sig1 = reg.takeSignal('g1');
  const sig2 = reg.takeSignal('g5');
  assert.equal(sig1.aborted, false);
  assert.equal(sig2.aborted, false);
  reg.takeSignal('g5');
  assert.equal(sig1.aborted, false);
  assert.equal(sig2.aborted, true);
});

test('cancelAll aborts every kind', () => {
  const reg = createAbortRegistry();
  const sig1 = reg.takeSignal('g1');
  const sig2 = reg.takeSignal('g5');
  reg.cancelAll();
  assert.equal(sig1.aborted, true);
  assert.equal(sig2.aborted, true);
});
