import { test } from 'node:test';
import assert from 'node:assert/strict';

import { getPdfBlob } from './pdfStore.js';

test('concurrent callers on one project share a single PDF load', async () => {
  let loads = 0;
  const load = async (id) => { loads += 1; await new Promise((r) => setTimeout(r, 5)); return { id, size: 3 }; };
  const [a, b, c] = await Promise.all([getPdfBlob('p1', { load }), getPdfBlob('p1', { load }), getPdfBlob('p1', { load })]);
  assert.equal(loads, 1, 'the viewer, the rail and the room list share one download');
  assert.equal(a, b);
  assert.equal(b, c);
  // Settled → the next open loads again (it will hit IndexedDB in the browser).
  await getPdfBlob('p1', { load });
  assert.equal(loads, 2);
});

test('different projects never share a load, and a failed load is not cached', async () => {
  let loads = 0;
  const load = async (id) => { loads += 1; if (id === 'bad') throw new Error('offline'); return { id }; };
  const [x, y] = await Promise.all([getPdfBlob('a', { load }), getPdfBlob('b', { load })]);
  assert.deepEqual([x.id, y.id], ['a', 'b']);
  assert.equal(loads, 2);
  await assert.rejects(getPdfBlob('bad', { load }), /offline/);
  await assert.rejects(getPdfBlob('bad', { load }), /offline/);
  assert.equal(loads, 4, 'a rejected load is retried by the next caller');
});
