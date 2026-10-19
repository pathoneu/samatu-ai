import test from 'node:test';
import assert from 'node:assert/strict';
import { storableMessages } from './chatHistory.js';

test('only the known keys of real messages are stored', () => {
  const out = storableMessages([
    { role: 'user', text: 'Kiek dažymo?', extra: 1 },
    { role: 'assistant', text: 'Atsakymas', vote: 'up', given: { patalpos: ['04'] }, isError: undefined, question: 'Kiek dažymo?' },
    { role: 'assistant', text: '   ' },
    { role: 'system', text: 'x' },
    null,
  ]);
  assert.deepEqual(out, [
    { role: 'user', text: 'Kiek dažymo?' },
    { role: 'assistant', text: 'Atsakymas', vote: 'up', question: 'Kiek dažymo?', given: { patalpos: ['04'] } },
  ]);
});

test('the newest hundred', () => {
  const many = Array.from({ length: 130 }, (_, i) => ({ role: 'user', text: `k${i}` }));
  const out = storableMessages(many);
  assert.equal(out.length, 100);
  assert.equal(out[0].text, 'k30');
  assert.deepEqual(storableMessages(null), []);
});
