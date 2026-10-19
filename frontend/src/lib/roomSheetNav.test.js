import test from 'node:test';
import assert from 'node:assert/strict';
import { pickerCounts, roomPickerItems, typedDigit } from './roomSheetNav.js';

const rooms = [
  { nr: '01', pavadinimas: 'Tambūras', user_verified_at: '2026-10-06' },
  { nr: '02', pavadinimas: 'Katilinė' },
  { nr: '05', pavadinimas: 'Svetainė', _sujungta_i: '04' },
  { nr: '06', pavadinimas: 'Vaiko kambarys' },
  { nr: '', pavadinimas: 'be numerio' },
];

test('every room with its state in words: checked, open, merged, left out', () => {
  const items = roomPickerItems(rooms, (nr) => nr !== '06', '02');
  assert.deepEqual(items.map((i) => [i.nr, i.state]), [['01', 'checked'], ['02', 'open'], ['05', 'merged'], ['06', 'excluded']]);
  assert.equal(items.find((i) => i.nr === '05').mergedInto, '04');
  assert.deepEqual(items.filter((i) => i.current).map((i) => i.nr), ['02']);
  assert.deepEqual(pickerCounts(items), { open: 1, checked: 1, merged: 1, excluded: 1 });
});

test('no rooms, no list', () => {
  assert.deepEqual(roomPickerItems(null), []);
  assert.deepEqual(pickerCounts([]), { open: 0, checked: 0, merged: 0, excluded: 0 });
});

test('a digit opens the focused number fact', () => {
  assert.equal(typedDigit({ key: '7' }, { targetTag: 'BUTTON', factKind: 'number' }), '7');
  assert.equal(typedDigit({ key: '0' }, { targetTag: 'DIV', factKind: 'number' }), '0');
});

test('not while typing, for a non-number fact, with modifiers, under a dialog or while saving', () => {
  assert.equal(typedDigit({ key: '7' }, { targetTag: 'INPUT', factKind: 'number' }), null);
  assert.equal(typedDigit({ key: '7' }, { targetEditable: true, factKind: 'number' }), null);
  assert.equal(typedDigit({ key: '7' }, { targetTag: 'DIV', factKind: 'choice' }), null);
  assert.equal(typedDigit({ key: '7' }, { targetTag: 'DIV' }), null);
  assert.equal(typedDigit({ key: '7', ctrlKey: true }, { factKind: 'number' }), null);
  assert.equal(typedDigit({ key: '7', metaKey: true }, { factKind: 'number' }), null);
  assert.equal(typedDigit({ key: '7' }, { factKind: 'number', layerOpen: true }), null);
  assert.equal(typedDigit({ key: '7' }, { factKind: 'number', busy: true }), null);
  assert.equal(typedDigit({ key: 'a' }, { factKind: 'number' }), null);
  assert.equal(typedDigit({ key: 'Enter' }, { factKind: 'number' }), null);
  assert.equal(typedDigit({ key: '7', defaultPrevented: true }, { factKind: 'number' }), null);
});
