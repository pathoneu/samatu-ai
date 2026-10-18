/**
 * The project's reminders (Pathon v3 W5-E, E8 + E9) — which a screen shows, in what order, and where
 * „Rodyti brėžinyje" goes. Every item is a sentence, never a quantity row.
 */
import test from 'node:test';
import assert from 'node:assert/strict';

import { WHERE_PATIKRA, WHERE_SAMATA, evidenceTarget, remindersFor, remindersWord } from './reminders.js';

const R = (id, extra = {}) => ({ id, kind: id, sentence: `${id}.`, vieta: [WHERE_PATIKRA, WHERE_SAMATA], ...extra });

test('a screen shows the reminders meant for it — warnings first, otherwise in the server order', () => {
  const list = [R('gruntas'), R('konturai_uzeina:01:02', { vieta: [WHERE_PATIKRA], tone: 'warning' }),
    R('hidroizoliacija', { tone: 'warning' }), R('dumu_davikliai')];
  assert.deepEqual(remindersFor(list, WHERE_SAMATA).map((r) => r.id), ['hidroizoliacija', 'gruntas', 'dumu_davikliai']);
  assert.deepEqual(remindersFor(list, WHERE_PATIKRA).map((r) => r.id),
    ['konturai_uzeina:01:02', 'hidroizoliacija', 'gruntas', 'dumu_davikliai']);
});

test('a malformed answer shows nothing, never throws', () => {
  assert.deepEqual(remindersFor(null, WHERE_SAMATA), []);
  assert.deepEqual(remindersFor([null, {}, { sentence: '' }, R('x', { vieta: 'samata' })], WHERE_SAMATA).map((r) => r.id), ['x']);
});

test('the head counts in Lithuanian', () => {
  assert.deepEqual([1, 2, 5, 10, 11, 12, 21, 22, 25].map(remindersWord),
    ['priminimas', 'priminimai', 'priminimai', 'priminimų', 'priminimų', 'priminimų', 'priminimas', 'priminimai',
      'priminimai']);
});

test('„Rodyti brėžinyje" goes to the page and the box the reminder carries — or nowhere', () => {
  assert.deepEqual(evidenceTarget(R('a', { evidence: { page: 2, rect_pct: [0.1, 0.2, 0.3, 0.4], text: 'EI30' } })),
    { page: 2, rect_pct: [0.1, 0.2, 0.3, 0.4] });
  assert.deepEqual(evidenceTarget(R('a', { evidence: { page: 3, rect_pct: null } })), { page: 3, rect_pct: null });
  assert.equal(evidenceTarget(R('a', { evidence: null })), null);
  assert.equal(evidenceTarget(R('a', { evidence: { page: 0 } })), null);
  assert.equal(evidenceTarget(R('a')), null);
});
