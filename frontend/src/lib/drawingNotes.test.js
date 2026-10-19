import test from 'node:test';
import assert from 'node:assert/strict';
import {
  makeNote, NOTE_KIND, noteLabel, noteNumbers, notesOf, noteToolArmed, setNoteToolArmed, subscribeNoteTool,
} from './drawingNotes.js';

test('a note is a measurement of kind note: one point, his text, trimmed and bounded', () => {
  const n = makeNote({ page: 2, x: 100.5, y: 200, text: '  Patikrinti aukštį  ', id: 'a', now: 'T' });
  assert.deepEqual(n, { id: 'a', kind: NOTE_KIND, page: 2, points: [{ x: 100.5, y: 200 }], text: 'Patikrinti aukštį', source: 'user', created_at: 'T' });
  assert.equal(makeNote({ page: 1, x: 0, y: 0, text: 'x'.repeat(900) }).text.length, 500);
  assert.notEqual(makeNote({ page: 1, x: 0, y: 0, text: 'a' }).id, makeNote({ page: 1, x: 0, y: 0, text: 'a' }).id);
});

test('notes of a sheet, numbered per sheet in the order made; other measurements left out', () => {
  const ms = [
    makeNote({ page: 1, x: 1, y: 1, text: 'a', id: 'n1' }),
    { id: 'd1', kind: 'distance', page: 1, points: [{ x: 0, y: 0 }, { x: 1, y: 1 }] },
    makeNote({ page: 2, x: 1, y: 1, text: 'b', id: 'n2' }),
    makeNote({ page: 1, x: 2, y: 2, text: 'c', id: 'n3' }),
    { id: 'bad', kind: NOTE_KIND, page: 1, points: [] },
  ];
  assert.deepEqual(notesOf(ms, 1).map((n) => n.id), ['n1', 'n3']);
  assert.deepEqual(notesOf(ms).map((n) => n.id), ['n1', 'n2', 'n3']);
  const nums = noteNumbers(ms);
  assert.equal(nums.get('n1'), 'P1');
  assert.equal(nums.get('n3'), 'P2');
  assert.equal(nums.get('n2'), 'P1');
});

test('the label is short; the text stays whole elsewhere', () => {
  assert.equal(noteLabel('trumpa'), 'trumpa');
  const long = noteLabel('a'.repeat(60), 40);
  assert.equal(long.length, 40);
  assert.ok(long.endsWith('…'));
});

test('the arming store tells its listeners once per change', () => {
  const seen = [];
  const off = subscribeNoteTool((v) => seen.push(v));
  setNoteToolArmed(true);
  setNoteToolArmed(true);
  setNoteToolArmed(false);
  off();
  setNoteToolArmed(true);
  assert.deepEqual(seen, [true, false]);
  assert.equal(noteToolArmed(), true);
  setNoteToolArmed(false);
});
