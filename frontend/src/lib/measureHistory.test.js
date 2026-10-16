import test from 'node:test';
import assert from 'node:assert/strict';
import {
  initHistory, historyReducer, canUndo, canRedo, describeChange, HISTORY_LIMIT,
} from './measureHistory.js';

const m = (id, extra = {}) => ({ id, kind: 'distance', page: 1, points: [], ...extra });
const add = (item) => ({ type: 'apply', update: (cur) => [...cur, item], label: `+${item.id}` });

test('apply records an entry; undo and redo walk it', () => {
  let s = initHistory([]);
  s = historyReducer(s, add(m('a')));
  s = historyReducer(s, add(m('b')));
  assert.deepEqual(s.present.map((x) => x.id), ['a', 'b']);
  assert.equal(s.past.length, 2);
  assert.ok(canUndo(s) && !canRedo(s));
  s = historyReducer(s, { type: 'undo' });
  assert.deepEqual(s.present.map((x) => x.id), ['a']);
  assert.ok(canRedo(s));
  s = historyReducer(s, { type: 'redo' });
  assert.deepEqual(s.present.map((x) => x.id), ['a', 'b']);
  assert.equal(s.future.length, 0);
});

test('a new action after undo drops the redo branch', () => {
  let s = historyReducer(initHistory([]), add(m('a')));
  s = historyReducer(s, add(m('b')));
  s = historyReducer(s, { type: 'undo' });
  s = historyReducer(s, add(m('c')));
  assert.deepEqual(s.present.map((x) => x.id), ['a', 'c']);
  assert.equal(s.future.length, 0);
});

test('a no-op update records nothing', () => {
  const s0 = historyReducer(initHistory([]), add(m('a')));
  const s1 = historyReducer(s0, { type: 'apply', update: (cur) => cur.filter(() => true) });
  assert.equal(s1, s0);
});

test('undo / redo on an empty stack keep the state', () => {
  const s = initHistory([m('a')]);
  assert.equal(historyReducer(s, { type: 'undo' }), s);
  assert.equal(historyReducer(s, { type: 'redo' }), s);
});

test('revertTo restores the state right after that entry, later entries redo in order', () => {
  let s = initHistory([]);
  for (const id of ['a', 'b', 'c', 'd']) s = historyReducer(s, add(m(id)));
  const target = s.past[1];                      // after 'b'
  s = historyReducer(s, { type: 'revertTo', entryId: target.id });
  assert.deepEqual(s.present.map((x) => x.id), ['a', 'b']);
  assert.equal(s.past.length, 2);
  s = historyReducer(s, { type: 'redo' });
  assert.deepEqual(s.present.map((x) => x.id), ['a', 'b', 'c']);
  s = historyReducer(s, { type: 'redo' });
  assert.deepEqual(s.present.map((x) => x.id), ['a', 'b', 'c', 'd']);
});

test('revertTo the latest entry or an unknown id changes nothing', () => {
  let s = historyReducer(initHistory([]), add(m('a')));
  assert.equal(historyReducer(s, { type: 'revertTo', entryId: s.past[0].id }), s);
  assert.equal(historyReducer(s, { type: 'revertTo', entryId: 'nope' }), s);
});

test(`history keeps the last ${HISTORY_LIMIT} actions`, () => {
  let s = initHistory([]);
  for (let i = 0; i < HISTORY_LIMIT + 7; i++) s = historyReducer(s, add(m(`m${i}`)));
  assert.equal(s.past.length, HISTORY_LIMIT);
  assert.equal(s.past[0].label, '+m7');
  assert.equal(s.present.length, HISTORY_LIMIT + 7);
});

test('reset hydrates and clears the stacks', () => {
  let s = historyReducer(initHistory([]), add(m('a')));
  s = historyReducer(s, { type: 'reset', present: [m('x')] });
  assert.deepEqual(s.present.map((x) => x.id), ['x']);
  assert.equal(s.past.length + s.future.length, 0);
});

test('apply takes a describe(before, after) when no label is given', () => {
  const s = historyReducer(initHistory([]), {
    type: 'apply', update: [m('a')], describe: (b, a) => `${b.length}→${a.length}`,
  });
  assert.equal(s.past[0].label, '0→1');
});

// ---- labels

const ctx = {
  countTypeLabel: (id) => ({ rozetes: 'Rozetės', jungikliai: 'Jungikliai' })[id] || null,
  formatValue: (x) => (x.kind === 'distance' ? '6,65 m' : x.kind === 'area' ? '12,40 m²' : null),
};

test('label: one added distance carries its value and page', () => {
  assert.equal(describeChange([], [m('a')], ctx), 'Pridėtas atstumas 6,65 m · psl. 1');
});

test('label: a removed count mark is feminine and names its type', () => {
  const c = m('c', { kind: 'count', typeId: 'rozetes', page: 2 });
  assert.equal(describeChange([c], [], ctx), 'Pašalinta žymė · Rozetės · psl. 2');
});

test('label: many removed marks of one type', () => {
  const list = [1, 2, 3, 4, 5].map((i) => m(`c${i}`, { kind: 'count', typeId: 'rozetes' }));
  assert.equal(describeChange(list, [], ctx), 'Pašalintos 5 žymės · Rozetės');
});

test('label: rename and type change', () => {
  const a = m('a', { kind: 'area' });
  assert.equal(describeChange([a], [{ ...a, name: 'Virtuvė' }], ctx), 'Pervadintas plotas → „Virtuvė"');
  const c = m('c', { kind: 'count', typeId: 'rozetes' });
  assert.equal(describeChange([c], [{ ...c, typeId: 'jungikliai' }], ctx), 'Pakeistas žymės tipas · Rozetės → Jungikliai');
});

test('label: a named measurement shows its name', () => {
  assert.equal(describeChange([], [m('a', { name: 'Koridorius' })], ctx), 'Pridėtas atstumas 6,65 m · „Koridorius" · psl. 1');
});

test('label: no value without a calibrated scale', () => {
  assert.equal(describeChange([], [m('a', { kind: 'perimeter' })], ctx), 'Pridėtas perimetras · psl. 1');
});
