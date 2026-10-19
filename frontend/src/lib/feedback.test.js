import test from 'node:test';
import assert from 'node:assert/strict';
import { feedbackBody, markReadRated, readRatingDue, validBoxPct } from './feedback.js';

test('the read rating: the verdict and the optional line, trimmed and cut', () => {
  assert.deepEqual(feedbackBody({ kind: 'skaitymas', up: true }), { kind: 'skaitymas', up: true });
  assert.deepEqual(feedbackBody({ kind: 'skaitymas', up: false, line: '  aukščiai  ' }), { kind: 'skaitymas', up: false, line: 'aukščiai' });
  assert.equal(feedbackBody({ kind: 'skaitymas', line: 'x'.repeat(500) }).line.length, 200);
  assert.deepEqual(feedbackBody({ kind: 'skaitymas', undo: true }), { kind: 'skaitymas', up: false, undo: true });
});

test('a found symbol carries its sheet, box and kind', () => {
  assert.deepEqual(
    feedbackBody({ kind: 'simbolis', up: false, page: 2, boxPct: [0.1, 0.1, 0.2, 0.2], klass: 'Rozetė' }),
    { kind: 'simbolis', up: false, page: 2, box_pct: [0.1, 0.1, 0.2, 0.2], klass: 'Rozetė' },
  );
});

test('box validity', () => {
  assert.equal(validBoxPct([0.1, 0.1, 0.2, 0.2]), true);
  assert.equal(validBoxPct([0.2, 0.1, 0.1, 0.2]), false);
  assert.equal(validBoxPct([0.1, 0.1, 1.2, 0.2]), false);
  assert.equal(validBoxPct(null), false);
});

test('the read is offered once per project, only for a project the paid read made', () => {
  const mem = new Map();
  const storage = { getItem: (k) => mem.get(k) ?? null, setItem: (k, v) => mem.set(k, v) };
  const p = { id: 'p1', _meta: { model: 'm' } };
  assert.equal(readRatingDue(p, storage), true);
  markReadRated('p1', storage);
  assert.equal(readRatingDue(p, storage), false);
  assert.equal(readRatingDue({ id: 'p2' }, storage), false);
  const broken = { getItem: () => { throw new Error('x'); }, setItem: () => { throw new Error('x'); } };
  assert.equal(readRatingDue({ id: 'p3', _meta: { model: 'm' } }, broken), true);
  assert.doesNotThrow(() => markReadRated('p3', broken));
});
