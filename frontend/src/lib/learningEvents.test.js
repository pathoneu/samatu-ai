/**
 * The learning loop's browser half (togal-v2 W11): which saves are a person's decision about an AI result,
 * and what each becomes in the journal.
 */
import test from 'node:test';
import assert from 'node:assert/strict';

import {
  chatFeedbackCorrection, learningEventsFromChange, questionCorrection, questionVerdict, rowIdOf, textHash,
} from './learningEvents.js';

const row = (extra = {}) => ({ id: 'abc123', aprasymas: 'Sienų dažymas', kiekis: 143.2, ...extra });

test('„Teisinga" on a row is one eilute_teisinga event named by the row id', () => {
  const prev = { darbu_sarasas: [row()] };
  const next = { darbu_sarasas: [row({ user_verified_at: '2026-10-16T10:00:00Z', quantity_source: 'user_verified_ai' })] };
  assert.deepEqual(learningEventsFromChange(prev, next), [{
    field_path: 'eilute.abc123.kiekis', source: 'eilute_teisinga', old_value: 143.2, new_value: 143.2,
    room_nr: null, note: null,
  }]);
});

test('a typed quantity is one eilute_kiekis event: from what the drawing gave to what he typed', () => {
  const prev = { darbu_sarasas: [row()] };
  const next = { darbu_sarasas: [row({ kiekis: 150, manual_override: true, ai_kiekis_original: 143.2, manual_override_at: 't1' })] };
  const [ev] = learningEventsFromChange(prev, next);
  assert.equal(ev.source, 'eilute_kiekis');
  assert.equal(ev.old_value, 143.2);
  assert.equal(ev.new_value, 150);
  // a second edit compares with the drawing's number again, never with his first edit
  const again = learningEventsFromChange(next, { darbu_sarasas: [{ ...next.darbu_sarasas[0], kiekis: 151, manual_override_at: 't2' }] });
  assert.equal(again[0].old_value, 143.2);
  assert.equal(again[0].new_value, 151);
});

test('a save that only carries old stamps over (a recompute, a price) records nothing', () => {
  const verified = row({ user_verified_at: 't0', manual_override: true, manual_override_at: 't0', ai_kiekis_original: 1 });
  const prev = { darbu_sarasas: [verified], patalpos: [{ nr: '03', user_verified_at: 't0' }] };
  const next = { darbu_sarasas: [{ ...verified, kaina: 4.5, suma: 644.4 }], patalpos: [{ nr: '03', user_verified_at: 't0', plotas_m2: 10 }] };
  assert.deepEqual(learningEventsFromChange(prev, next), []);
  assert.deepEqual(learningEventsFromChange(prev, { name: 'x' }), []);
  assert.deepEqual(learningEventsFromChange(prev, null), []);
});

test('a room confirmed in either room array is one patalpa_patvirtinta event', () => {
  const prev = { patalpos: [{ nr: '03', plotas_m2: 10.12 }], v8_rooms: [{ nr: '03', plotas_m2: 10.12 }] };
  const next = {
    patalpos: [{ nr: '03', plotas_m2: 10.12, user_verified_at: 't1' }],
    v8_rooms: [{ nr: '03', plotas_m2: 10.12, user_verified_at: 't1' }],
  };
  assert.deepEqual(learningEventsFromChange(prev, next), [{
    field_path: 'patalpa.03.patvirtinta', source: 'patalpa_patvirtinta', old_value: null, new_value: 10.12,
    room_nr: '03', note: null,
  }]);
});

test('a hand-added row is named by its own id', () => {
  assert.equal(rowIdOf({ id: 'rnk-1' }), 'rnk-1');
  assert.equal(rowIdOf({ _id: 'x' }), 'x');
  assert.equal(rowIdOf({ eil_nr: 3, aprasymas: 'A' }), '3-A');
  const [ev] = learningEventsFromChange({ darbu_sarasas: [] }, { darbu_sarasas: [{ id: 'rnk-1', kiekis: 2, user_verified_at: 't' }] });
  assert.equal(ev.field_path, 'eilute.rnk-1.kiekis');
});

test('a question answer is „Tinka" only when it is the program\'s own proposal', () => {
  const h = { id: 'aukstis', answer: 'number_all', proposed: 2.7, items: [{ room_nr: '01' }] };
  assert.equal(questionVerdict(h, { value: 2.7, perRoom: {} }), 'tinka');
  assert.equal(questionVerdict(h, { value: 2.8 }), 'netinka');
  assert.equal(questionVerdict(h, { value: 2.7, perRoom: { '01': 3.1 } }), 'netinka');

  const n = { id: 'perimetras', answer: 'numbers', items: [{ room_nr: '01', proposed: 14 }, { room_nr: '02', proposed: 9 }] };
  assert.equal(questionVerdict(n, { values: {} }), 'tinka');
  assert.equal(questionVerdict(n, { values: { '01': 14 } }), 'tinka');
  assert.equal(questionVerdict(n, { values: { '02': 9.5 } }), 'netinka');

  const c = { id: 'grindys', answer: 'choices', items: [{ room_nr: '01', proposed: 'parketas' }] };
  assert.equal(questionVerdict(c, { values: { '01': 'parketas' } }), 'tinka');
  assert.equal(questionVerdict(c, { values: { '01': 'plytelės' } }), 'netinka');

  const o = { id: 'angos', answer: 'openings', items: [{}, {}] };
  assert.equal(questionVerdict(o, { picked: [true, true], edits: {} }), 'tinka');
  assert.equal(questionVerdict(o, { picked: [true, false], edits: {} }), 'netinka');
  assert.equal(questionVerdict(o, { picked: [true, true], edits: { 0: { plotis_mm: 900 } } }), 'netinka');

  const k = { id: 'konturas', answer: 'outline', items: [] };
  assert.equal(questionVerdict(k, {}, 'accepted'), 'tinka');
  assert.equal(questionVerdict(k, {}, 'own'), 'netinka');
});

test('a question answer carries its id in note and the rooms it touched', () => {
  assert.deepEqual(questionCorrection({ id: 'erdve:03-04' }, 'tinka', ['04', '03']), {
    field_path: 'klausimas.erdve:03-04', source: 'klausimas_tinka', old_value: null,
    new_value: { atsakymas: 'tinka', patalpos: ['03', '04'] }, room_nr: null, note: 'erdve:03-04',
  });
  assert.equal(questionCorrection({ id: 'aukstis' }, 'netinka', ['01']).source, 'klausimas_netinka');
  assert.equal(questionCorrection({ id: 'aukstis' }, 'netinka', ['01']).room_nr, '01');
  assert.equal(questionCorrection(null, 'tinka'), null);
});

test('chat thumbs: one field per answer, his question kept, the selection named', () => {
  const ev = chatFeedbackCorrection({
    question: 'Kiek dažomo ploto?', answer: 'Patalpose 03 ir 04 — 92,1 m².', up: false,
    selection: { rooms: ['03', '04'], rows: ['abc'] },
  });
  assert.equal(ev.source, 'pokalbis_ne');
  assert.equal(ev.field_path, `pokalbis.${textHash('Patalpose 03 ir 04 — 92,1 m².')}`);
  assert.deepEqual(ev.new_value, { ivertinimas: 'ne', patalpos: ['03', '04'], eilutes: ['abc'] });
  assert.equal(ev.note, 'Kiek dažomo ploto?');
  assert.equal(chatFeedbackCorrection({ answer: 'x', up: true }).source, 'pokalbis_taip');
  assert.equal(chatFeedbackCorrection({ question: 'q'.repeat(300), answer: 'x', up: true }).note.length, 200);
  assert.equal(chatFeedbackCorrection({ answer: '' }), null);
  assert.notEqual(textHash('a'), textHash('b'));
});

test('„Pertvarų sienos atviroje erdvėje" he typed on the room sheet is one patalpa_pertvaros row', async () => {
  const { userEditPatch } = await import('./roomSheet.js');
  const { LEARNING_SOURCES } = await import('./learningEvents.js');
  const patch = userEditPatch('n_partition_walls', 3.4, '2026-10-17T10:00:00Z');
  assert.deepEqual(patch, { n_partition_walls: 3, n_partition_walls_saltinis: 'user_override',
    _n_partition_walls_user_at: '2026-10-17T10:00:00Z' });
  const prev = { patalpos: [{ nr: '04', n_partition_walls: 5 }] };
  const next = { patalpos: [{ nr: '04', ...patch }] };
  assert.deepEqual(learningEventsFromChange(prev, next), [{
    field_path: 'patalpa.04.pertvaros', source: 'patalpa_pertvaros', old_value: 5, new_value: 3, room_nr: '04', note: null,
  }]);
  // a recompute carrying the same stamp over is not a decision
  assert.deepEqual(learningEventsFromChange(next, { patalpos: [{ ...next.patalpos[0] }] }), []);
  assert.ok(LEARNING_SOURCES.includes('patalpa_pertvaros'));
});
