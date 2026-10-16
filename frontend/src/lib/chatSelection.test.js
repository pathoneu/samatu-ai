/**
 * The „Pokalbis" selection (togal-v2 W11): pills = exactly what the request carries.
 */
import test from 'node:test';
import assert from 'node:assert/strict';

import {
  EMPTY_SELECTION, MAX_ROOMS, MAX_TURNS, addRoom, addRow, chatRequest, givenPills, removePill, selectionPayload,
  selectionPills, toggleRoom,
} from './chatSelection.js';

const project = {
  id: 'p1',
  patalpos: [{ nr: '03', pavadinimas: 'Miegamasis' }, { nr: '04', pavadinimas: 'Svetainė' }, { nr: '07' }],
  darbu_sarasas: [{ id: 'r1', aprasymas: 'Sienų dažymas' }, { _id: 'legacy', aprasymas: 'Grindjuostės' }],
};

test('the focused room is the first pill; more rooms and lines follow, each named for him', () => {
  let sel = addRoom(EMPTY_SELECTION, '04');
  sel = addRow(sel, project.darbu_sarasas[0]);
  sel = addRow(sel, project.darbu_sarasas[1]);
  const pills = selectionPills(sel, project, '03');
  assert.deepEqual(pills.map((p) => p.label), [
    'Patalpa 03 · Miegamasis', 'Patalpa 04 · Svetainė', 'Eilutė: Sienų dažymas', 'Eilutė: Grindjuostės',
  ]);
  assert.equal(pills[0].focus, true);
  assert.deepEqual(selectionPayload(sel, '03'), { rooms: ['03', '04'], rows: ['r1', 'legacy'] });
  // a room without a name is still a pill
  assert.equal(selectionPills(addRoom(EMPTY_SELECTION, '07'), project)[0].label, 'Patalpa 07');
});

test('nothing is added twice — not even the focused room clicked again', () => {
  let sel = addRoom(EMPTY_SELECTION, '03');
  sel = addRoom(sel, '03');
  sel = addRow(addRow(sel, 'r1'), 'r1');
  assert.deepEqual(selectionPayload(sel, '03'), { rooms: ['03'], rows: ['r1'] });
});

test('every pill is removable — the focused room stays out until another room is focused', () => {
  let sel = addRow(addRoom(EMPTY_SELECTION, '04'), 'r1');
  sel = removePill(sel, { kind: 'room', nr: '03' }, '03');
  assert.deepEqual(selectionPayload(sel, '03'), { rooms: ['04'], rows: ['r1'] });
  assert.deepEqual(selectionPayload(sel, '07'), { rooms: ['07', '04'], rows: ['r1'] });
  sel = removePill(sel, { kind: 'row', id: 'r1' }, '03');
  sel = removePill(sel, { kind: 'room', nr: '04' }, '03');
  assert.deepEqual(selectionPayload(sel, '03'), { rooms: [], rows: [] });
  // clicking the chip of the dropped focused room brings it back
  assert.deepEqual(selectionPayload(toggleRoom(sel, '03', '03'), '03'), { rooms: ['03'], rows: [] });
});

test('room chips toggle', () => {
  let sel = toggleRoom(EMPTY_SELECTION, '04', '03');
  assert.deepEqual(selectionPayload(sel, '03').rooms, ['03', '04']);
  sel = toggleRoom(sel, '04', '03');
  assert.deepEqual(selectionPayload(sel, '03').rooms, ['03']);
  sel = toggleRoom(sel, '03', '03');
  assert.deepEqual(selectionPayload(sel, '03').rooms, []);
});

test('the payload is capped like the server', () => {
  let sel = EMPTY_SELECTION;
  for (let i = 1; i <= 15; i += 1) sel = addRoom(sel, String(i));
  assert.equal(selectionPayload(sel).rooms.length, MAX_ROOMS);
});

test('the request carries history without errors, the new question last, and the selection', () => {
  const history = [
    { role: 'user', text: 'Kiek patalpų?' },
    { role: 'assistant', text: 'Vienuolika.' },
    { role: 'assistant', text: 'Tinklo klaida', isError: true },
  ];
  const body = chatRequest('p1', history, '  Kiek dažomo ploto?  ', { rooms: ['03'], rows: [] });
  assert.deepEqual(body, {
    project_id: 'p1',
    messages: [
      { role: 'user', content: 'Kiek patalpų?' },
      { role: 'assistant', content: 'Vienuolika.' },
      { role: 'user', content: 'Kiek dažomo ploto?' },
    ],
    selection: { rooms: ['03'], rows: [] },
  });
  const long = Array.from({ length: 30 }, (_, i) => ({ role: i % 2 ? 'assistant' : 'user', text: `t${i}` }));
  const capped = chatRequest('p1', long, 'q', { rooms: [], rows: [] }).messages;
  assert.equal(capped.length, MAX_TURNS);
  assert.equal(capped.at(-1).content, 'q');
});

test('what the model was given is shown as its own pills, and what it was not given is said', () => {
  const { pills, notes } = givenPills({
    rooms: [{ nr: '03', name: 'Miegamasis' }], rows: [{ id: 'r1', aprasymas: 'Sienų dažymas' }],
    left_out: { rooms: ['13'], rows: [] }, not_found: { rooms: ['99'], rows: [] },
  });
  assert.deepEqual(pills.map((p) => p.label), ['Patalpa 03 · Miegamasis', 'Eilutė: Sienų dažymas']);
  assert.deepEqual(notes, ['Neperduota (daugiau nei 12 patalpų): 13', 'Projekte nerasta: 99']);
  assert.deepEqual(givenPills(null), { pills: [], notes: [] });
});

test('bold markers in an answer become bold parts, never asterisks', async () => {
  const { answerParts } = await import('./chatSelection.js');
  assert.deepEqual(answerParts('Iš viso: **114,23 m²** (sienos).'), [
    { text: 'Iš viso: ', bold: false }, { text: '114,23 m²', bold: true }, { text: ' (sienos).', bold: false },
  ]);
  assert.deepEqual(answerParts('be žymių'), [{ text: 'be žymių', bold: false }]);
  // an unpaired marker is left as it is
  assert.deepEqual(answerParts('a **b** c **d'), [
    { text: 'a ', bold: false }, { text: 'b', bold: true }, { text: ' c ', bold: false }, { text: '**d', bold: false },
  ]);
});
