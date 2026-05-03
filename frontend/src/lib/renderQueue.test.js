import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createRenderQueue } from './renderQueue.js';

test('renderQueue runs at most 2 jobs concurrently', async () => {
  const queue = createRenderQueue(2);
  let inFlight = 0;
  let maxObserved = 0;
  const job = async () => {
    inFlight++;
    maxObserved = Math.max(maxObserved, inFlight);
    await new Promise(r => setTimeout(r, 20));
    inFlight--;
    return 'ok';
  };
  const results = await Promise.all(Array(8).fill(0).map(() => queue(job)));
  assert.equal(results.length, 8);
  assert.ok(results.every(r => r === 'ok'));
  assert.equal(maxObserved, 2);
});

test('renderQueue propagates errors', async () => {
  const queue = createRenderQueue(2);
  await assert.rejects(
    () => queue(async () => { throw new Error('boom'); }),
    /boom/
  );
});
