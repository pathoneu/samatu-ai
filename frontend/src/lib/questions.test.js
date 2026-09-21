/**
 * Patikra as a short list of questions (2026-09-21) — the pure half: which question is open next, and what
 * an answer turns into on the project. „Programa siūlo — jūs patvirtinate": with nothing typed, an answer is
 * the program's own proposal for every item.
 */
import test from 'node:test';
import assert from 'node:assert/strict';

import {
  answerSummary, floorAnswer, heightAnswer, nextOpenQuestion, numbersAnswer, openingsAnswer, progressOf, wallsAnswer,
} from './questions.js';

const Q = (id, extra = {}) => ({ id, kind: id.split(':')[0], items: [], manual: [], ...extra });

test('the next open question is the first one not skipped — after the current one first, then from the top', () => {
  const qs = [Q('aukstis'), Q('konturas'), Q('perimetras'), Q('angos')];
  assert.equal(nextOpenQuestion(qs, new Set()).id, 'aukstis');
  assert.equal(nextOpenQuestion(qs, new Set(), 'konturas').id, 'perimetras');
  assert.equal(nextOpenQuestion(qs, new Set(['perimetras']), 'konturas').id, 'angos');
  assert.equal(nextOpenQuestion(qs, new Set(['aukstis']), 'angos').id, 'konturas', 'wraps round to what is still open');
  assert.equal(nextOpenQuestion(qs, new Set(['aukstis', 'konturas', 'perimetras', 'angos'])), null);
  assert.equal(nextOpenQuestion([], new Set()), null);
  assert.equal(nextOpenQuestion(qs, new Set(), 'gone-after-the-answer').id, 'aukstis');
});

test('progress counts what is open, what was skipped and what was answered in this sitting', () => {
  const qs = [Q('aukstis'), Q('perimetras'), Q('angos')];
  assert.deepEqual(progressOf(qs, new Set(['angos']), 2), { open: 2, skipped: 1, answered: 2, total: 5 });
  assert.deepEqual(progressOf([], new Set(['angos']), 0), { open: 0, skipped: 0, answered: 0, total: 0 },
    'a skipped question that is gone from the list is not counted');
});

const heightItems = [
  { room_nr: '01', proposed: 2.82, field: 'lubu_auksciai' },
  { room_nr: '02', proposed: 2.82, field: 'lubu_auksciai' },
  { room_nr: '03', proposed: 2.7, field: 'lubu_auksciai' },
];

test('one height goes to every room that asked, a room typed separately keeps its own, nobody else is touched', () => {
  const project = { _overrides: { lubu_auksciai: { '09': 3.1 } }, patalpos: [{ nr: '01', lubu_aukstis_m: 2.82 }] };
  const all = heightAnswer(project, heightItems, 2.75);
  assert.deepEqual(all.table, { '09': 3.1, '01': 2.75, '02': 2.75, '03': 2.75 });
  assert.deepEqual(all.rooms, ['01', '02', '03']);
  const some = heightAnswer(project, heightItems, 2.75, { '03': 2.5 });
  assert.deepEqual(some.table, { '09': 3.1, '01': 2.75, '02': 2.75, '03': 2.5 });
  assert.equal(project._overrides.lubu_auksciai['01'], undefined, 'the project is not mutated');
  assert.equal(heightAnswer(project, heightItems, 0), null, 'no number — nothing to send');
  assert.equal(heightAnswer(project, heightItems, NaN), null);
  assert.equal(heightAnswer(project, [], 2.7), null);
});

test('a height equal to the one every asked room is computed with is known to change nothing', () => {
  const project = { patalpos: [{ nr: '01', lubu_aukstis_m: 2.82 }, { nr: '02', lubu_aukstis_m: 2.82 }, { nr: '03', lubu_aukstis_m: 2.7 }] };
  assert.equal(heightAnswer(project, heightItems.slice(0, 2), 2.82).sameValue, true);
  assert.equal(heightAnswer(project, heightItems, 2.82).sameValue, false, 'room 03 was computed with 2,70');
  assert.equal(heightAnswer(project, heightItems, 2.82, { '03': 2.7 }).sameValue, true);
});

const perimeterItems = [
  { room_nr: '03', proposed: 21.23, field: 'perimetras_m' },
  { room_nr: '07', proposed: 8.6, field: 'perimetras_m' },
];

test('numbers: the proposals are taken as they stand, a typed one replaces its own, each is marked as his', () => {
  const project = {
    patalpos: [{ nr: '03', perimetras_m: 21.23, pavadinimas: 'Koridorius' }, { nr: '07', perimetras_m: 8.6 }, { nr: '09', perimetras_m: 16.01 }],
  };
  const out = numbersAnswer(project, perimeterItems, { '07': 9.1 });
  assert.deepEqual(out.touched, ['03', '07']);
  assert.deepEqual(out.rooms.map((r) => [r.nr, r.perimetras_m, r.perimetras_saltinis]), [
    ['03', 21.23, 'user_override'], ['07', 9.1, 'user_override'], ['09', 16.01, undefined]]);
  assert.equal(out.rooms[0].pavadinimas, 'Koridorius', 'nothing else of the room moves');
  assert.equal(out.sameValue, false);
  assert.equal(project.patalpos[0].perimetras_saltinis, undefined, 'the project is not mutated');
  assert.equal(numbersAnswer(project, perimeterItems, {}).sameValue, true, 'every proposal is the number already in use');
});

test('numbers: an item with no proposal and nothing typed is left alone; nothing at all → null', () => {
  const project = { patalpos: [{ nr: '03' }, { nr: '07' }] };
  const items = [{ room_nr: '03', proposed: null, field: 'plotas_m2' }, { room_nr: '07', proposed: 5.64, field: 'plotas_m2' }];
  const out = numbersAnswer(project, items, {});
  assert.deepEqual(out.touched, ['07']);
  assert.deepEqual(out.rooms.map((r) => [r.nr, r.plotas_m2, r.plotas_saltinis]), [['03', undefined, undefined], ['07', 5.64, 'user_override']]);
  assert.equal(numbersAnswer(project, [items[0]], {}), null);
  assert.equal(numbersAnswer(project, [items[0]], { '03': -1 }), null);
});

test('numbers: the rebuilt rooms are the ones patched, as everywhere on the sheet', () => {
  const project = { patalpos: [{ nr: '03', perimetras_m: 1 }], v8_rooms: [{ nr: '03', perimetras_m: 21.23, walls_paintable_m2: 50 }] };
  const out = numbersAnswer(project, [perimeterItems[0]], {});
  assert.equal(out.rooms[0].walls_paintable_m2, 50);
});

test('floor coverings: the proposal or his own choice, written as his', () => {
  const project = { patalpos: [{ nr: '01' }, { nr: '07' }] };
  const items = [{ room_nr: '01', proposed: 'minksta', field: 'grindu_danga' }, { room_nr: '07', proposed: 'plyteles', field: 'grindu_danga' }];
  const out = floorAnswer(project, items, { '01': 'plyteles' });
  assert.deepEqual(out.rooms.map((r) => [r.nr, r.grindu_danga, r.grindu_danga_saltinis]),
    [['01', 'plyteles', 'user_override'], ['07', 'plyteles', 'user_override']]);
  assert.deepEqual(out.touched, ['01', '07']);
  assert.equal(floorAnswer(project, [{ room_nr: '01', proposed: null }], {}), null);
});

test('wall finishes go into the per-room table the assumptions use', () => {
  const project = { _overrides: { walls_paint_override: { '05': 0 } } };
  const items = [{ room_nr: '01', proposed: 1 }, { room_nr: '02', proposed: 0 }];
  const out = wallsAnswer(project, items, { '02': 1 });
  assert.deepEqual(out.table, { '05': 0, '01': 1, '02': 1 });
  assert.deepEqual(out.touched, ['01', '02']);
  assert.equal(wallsAnswer(project, [], {}), null);
});

const door = (room_nr, plotis_mm, i) => ({ room_nr, tipas: 'duris', plotis_mm, aukstis_mm: 2100, i });

test('openings: the ticked ones are added to their rooms — two in one room both land, an unticked one does not', () => {
  const project = {
    patalpos: [
      { nr: '02', elementai: [] },
      { nr: '07', elementai: [{ tipas: 'langas', kiekis: 1, plotis_mm: 1200, aukstis_mm: 1500 }] },
      { nr: '09', elementai: [] },
    ],
  };
  const items = [door('02', 800, '03'), door('07', 800, '03'), door('07', 700, '08'), door('09', 900, '03')];
  const out = openingsAnswer(project, items, [true, true, true, false]);
  assert.deepEqual(out.touched, ['02', '07']);
  assert.equal(out.added, 3);
  const r07 = out.rooms.find((r) => r.nr === '07');
  assert.equal(r07.elementai.length, 3);
  assert.ok(r07._angos_user_at, 'marked as his, like every opening he adds on the room sheet');
  assert.deepEqual(out.rooms.find((r) => r.nr === '09').elementai, []);
  assert.equal(project.patalpos[0].elementai.length, 0, 'the project is not mutated');
  assert.equal(openingsAnswer(project, items, [false, false, false, false]), null);
  assert.equal(openingsAnswer(project, items, undefined).added, 4, 'nothing unticked → every proposal');
});

test('what was answered is said in one plain sentence', () => {
  const t = (key, params) => `${key}|${JSON.stringify(params || {})}`;
  assert.match(answerSummary({ kind: 'aukstis' }, { rooms: ['01', '02'], value: 2.82 }, t), /answeredHeight/);
  assert.match(answerSummary({ kind: 'aukstis' }, { rooms: ['01', '02'], value: 2.82 }, t), /"count":2/);
  assert.match(answerSummary({ kind: 'perimetras' }, { touched: ['03'] }, t), /answeredNumbers/);
  assert.match(answerSummary({ kind: 'angos' }, { added: 3, touched: ['02', '07'] }, t), /answeredOpenings.*"count":3/);
  assert.match(answerSummary({ kind: 'erdve' }, { touched: ['04', '05'] }, t), /answeredSplit/);
  assert.match(answerSummary({ kind: 'konturas' }, { touched: ['01'] }, t), /answeredOutline/);
});
