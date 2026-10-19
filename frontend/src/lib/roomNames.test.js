import test from 'node:test';
import assert from 'node:assert/strict';
import { namePatch, namesAreAsked, openHints, ROOM_NAME_CHOICES } from './roomNames.js';

const outline = [[0.1, 0.1], [0.2, 0.1], [0.2, 0.2]];

test('asked only for an outlined room that is not a row of the room table', () => {
  assert.equal(namesAreAsked({ nr: '12', polygon_pct: outline, plotas_saltinis: 'konturas' }), true);
  assert.equal(namesAreAsked({ nr: '12', polygon_pct: outline }), true);
  assert.equal(namesAreAsked({ nr: '03', polygon_pct: outline, plotas_saltinis: 'eksplikacija' }), false);
  assert.equal(namesAreAsked({ nr: '04', polygon_pct: outline, plotas_saltinis: 'eksplikacija_sujungta' }), false);
  assert.equal(namesAreAsked({ nr: '03', polygon_pct: outline, plotas_source: 'eksplikacija' }), false);
  assert.equal(namesAreAsked({ nr: '03', polygon_pct: outline, eksplikacija_row_idx: 200 }), false);
  assert.equal(namesAreAsked({ nr: '12', polygon_pct: [] }), false);
  assert.equal(namesAreAsked({ nr: '12' }), false);
  assert.equal(namesAreAsked(null), false);
});

test('a room he already named is not asked again', () => {
  assert.equal(namesAreAsked({ nr: '12', polygon_pct: outline, _pavadinimas_user_at: '2026-10-19' }), false);
});

test('a proposal the room already carries is not asked (diacritics and case aside)', () => {
  const hints = [{ pavadinimas: 'Virtuvė', paskirtis: 'virtuve', zodis: 'VIRTUVE' }, { pavadinimas: 'WC', paskirtis: 'wc' }];
  assert.deepEqual(openHints({ pavadinimas: 'virtuve' }, hints).map((h) => h.pavadinimas), ['WC']);
  assert.deepEqual(openHints({ pavadinimas: 'Patalpa 12' }, hints).map((h) => h.pavadinimas), ['Virtuvė', 'WC']);
  assert.deepEqual(openHints({}, null), []);
});

test('the answer saves the name and the kind, both marked as his', () => {
  const p = namePatch({ pavadinimas: ' Virtuvė ', paskirtis: 'virtuve' }, 'T');
  assert.deepEqual(p, { pavadinimas: 'Virtuvė', _pavadinimas_user_at: 'T', paskirtis: 'virtuve', _paskirtis_user_at: 'T' });
  assert.deepEqual(namePatch({ pavadinimas: 'Sandėlis' }, 'T'), { pavadinimas: 'Sandėlis', _pavadinimas_user_at: 'T' });
});

test('„Kita…" offers known room kinds, each with its paskirtis', () => {
  assert.ok(ROOM_NAME_CHOICES.length >= 8);
  for (const c of ROOM_NAME_CHOICES) assert.ok(c.pavadinimas && c.paskirtis);
});
