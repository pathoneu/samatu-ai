import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createTileCache } from './tileCache.js';

class StubBitmap {
  constructor(id) { this.id = id; this.closed = false; }
  close() { this.closed = true; }
}

test('tileCache: get returns set value', () => {
  const cache = createTileCache({ max: 5 });
  const b = new StubBitmap('a');
  cache.set('a', b);
  assert.equal(cache.get('a'), b);
});

test('tileCache: evicts oldest and calls close() on evicted', () => {
  const cache = createTileCache({ max: 2 });
  const a = new StubBitmap('a');
  const b = new StubBitmap('b');
  const c = new StubBitmap('c');
  cache.set('a', a);
  cache.set('b', b);
  cache.set('c', c);
  assert.equal(cache.get('a'), undefined);
  assert.equal(a.closed, true, 'evicted bitmap.close() should have been called');
  assert.equal(b.closed, false);
  assert.equal(c.closed, false);
});

test('tileCache: clear() closes all and empties', () => {
  const cache = createTileCache({ max: 5 });
  const a = new StubBitmap('a');
  const b = new StubBitmap('b');
  cache.set('a', a);
  cache.set('b', b);
  cache.clear();
  assert.equal(cache.get('a'), undefined);
  assert.equal(cache.get('b'), undefined);
  assert.equal(a.closed, true);
  assert.equal(b.closed, true);
});
