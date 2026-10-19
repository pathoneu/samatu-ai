import test from 'node:test';
import assert from 'node:assert/strict';
import { projectRow, rowEuro } from './projectRows.js';

const rooms = (n, verified = 0) => Array.from({ length: n }, (_, i) => ({ nr: String(i + 1), user_verified_at: i < verified ? 'x' : undefined }));

test('rooms left to check come first, with the way to Patikra', () => {
  const r = projectRow({ id: 'p1', name: 'Butas', patalpos: rooms(11, 8), darbu_sarasas: [{ kiekis: 2, kaina: 0 }] });
  assert.equal(r.state, 'check');
  assert.deepEqual(r.stateParams, { count: 3 });
  assert.deepEqual(r.next, { key: 'check', href: '/project/p1/patikra' });
  assert.equal(r.openable, true);
});

test('a merged room is not a room left to check, nor a room in the totals', () => {
  const r = projectRow({ id: 'p1', patalpos: [{ nr: '1', user_verified_at: 'x' }, { nr: '2', _sujungta_i: '1' }], darbu_sarasas: [] });
  assert.equal(r.state, 'ready');
  assert.equal(r.totals.rooms, 1);
});

test('all rooms checked: rows without a price next; then the estimate is ready to send', () => {
  const rows = [{ kiekis: 2, kaina: 10 }, { kiekis: 3, kaina: 0 }, { kiekis: 0, kaina: 0 }];
  const prices = projectRow({ id: 'p1', patalpos: rooms(2, 2), darbu_sarasas: rows });
  assert.equal(prices.state, 'prices');
  assert.deepEqual(prices.stateParams, { count: 1 });
  assert.equal(prices.next.href, '/project/p1?step=samata');
  const ready = projectRow({ id: 'p1', patalpos: rooms(2, 2), darbu_sarasas: [{ kiekis: 2, kaina: 10 }] });
  assert.equal(ready.state, 'ready');
  assert.equal(ready.next.href, '/project/p1?step=siusti');
});

test('still being read: no next step, not openable; a failed read offers a new upload', () => {
  const p = projectRow({ id: 'p1', status: 'processing' });
  assert.equal(p.state, 'processing');
  assert.equal(p.next, null);
  assert.equal(p.openable, false);
  const e = projectRow({ id: 'p1', status: 'error' });
  assert.equal(e.state, 'error');
  assert.equal(e.next.href, '/new-project');
});

test('legacy statuses ok / undefined count as read', () => {
  assert.notEqual(projectRow({ id: 'a', status: 'ok' }).state, 'error');
  assert.notEqual(projectRow({ id: 'a' }).state, 'error');
});

test('totals: net from the rows, gross with the project VAT, rows and rooms counted; last change parsed', () => {
  const r = projectRow({ id: 'p', patalpos: rooms(3, 3), darbu_sarasas: [{ kiekis: 10, kaina: 10 }], updated_at: '2026-10-19T07:00:00Z' }, 21);
  assert.equal(r.totals.net, 100);
  assert.ok(Math.abs(r.totals.gross - 121) < 1e-9);
  assert.equal(r.totals.rows, 1);
  assert.equal(r.totals.rooms, 3);
  assert.equal(r.lastChange.toISOString(), '2026-10-19T07:00:00.000Z');
  assert.equal(projectRow({ id: 'p', updated_at: 'nonsense' }).lastChange, null);
});

test('euro amounts group with a thin space, never the wide no-break space', () => {
  const s = rowEuro(14472.66);
  assert.ok(!/[   ]/.test(s), s);
  assert.equal(s, '14 473');
  assert.equal(rowEuro(14472.66, { cents: true }), '14 472,66');
  assert.equal(rowEuro(0), '0');
});
