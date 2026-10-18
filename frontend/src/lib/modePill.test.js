import test from 'node:test';
import assert from 'node:assert/strict';
import { modePillFor } from './modePill.js';
import { RAIL_TOOLS } from './toolRail.js';

const ids = (pill) => pill.actions.map((a) => a.id);

test('nothing at rest', () => {
  assert.equal(modePillFor({}), null);
  assert.equal(modePillFor({ tool: null }), null);
});

test('every tool mode on the rail has a pill with a way out', () => {
  for (const t of RAIL_TOOLS.filter((x) => !x.toggle && x.id !== 'room' && x.id !== 'findSimilar')) {
    const pill = modePillFor({ tool: t.id });
    assert.ok(pill, t.id);
    assert.equal(pill.name, t.name, t.id);
    assert.ok(pill.actions.length >= 1, `${t.id} has no button`);
  }
});

test('a measurement being drawn: Baigti (only when it can finish) and Atšaukti stay visible', () => {
  const empty = modePillFor({ tool: 'area', draftPoints: 0 });
  assert.deepEqual(ids(empty), ['toolExit']);
  const two = modePillFor({ tool: 'area', draftPoints: 2, finishable: false });
  assert.deepEqual(ids(two), ['draftFinish', 'draftCancel']);
  assert.equal(two.actions[0].disabled, true);
  const three = modePillFor({ tool: 'area', draftPoints: 3, finishable: true });
  assert.equal(three.actions[0].disabled, false);
  assert.equal(three.actions[0].primary, true);
  assert.match(three.keys, /Enter — baigti/);
});

test('the pill shows only the active mode — outline edit wins over an armed tool', () => {
  const pill = modePillFor({ tool: 'distance', draftPoints: 2, outlineEdit: { nr: '02', canUndo: false, invalid: false, saving: false } });
  assert.equal(pill.id, 'outlineEdit');
  assert.deepEqual(ids(pill), ['outlineUndo', 'outlineSave', 'outlineCancel']);
  assert.equal(pill.actions[0].disabled, true);
  const invalid = modePillFor({ outlineEdit: { nr: '02', canUndo: true, invalid: true } });
  assert.equal(invalid.actions[1].disabled, true);
  assert.match(invalid.detail, /kertasi/);
});

test('count shows its type and tally; calibration its points', () => {
  assert.equal(modePillFor({ tool: 'count', countType: { label: 'Rozetės', n: 12 } }).detail, 'Rozetės: 12 vnt.');
  assert.match(modePillFor({ tool: 'count' }).detail, /tipą/);
  assert.deepEqual(ids(modePillFor({ tool: 'calibrate', calibPoint: true })), ['calibCancel', 'toolExit']);
  assert.equal(modePillFor({ tool: 'scalecheck' }).name, 'Mastelio patikra');
});

test('selection: a count and the way to clear it', () => {
  const pill = modePillFor({ tool: 'lasso', selectionCount: 5 });
  assert.equal(pill.detail, 'Pažymėta: 5');
  assert.deepEqual(ids(pill), ['deselect', 'toolExit']);
});

test('fill and find-similar have their own pills', () => {
  assert.deepEqual(ids(modePillFor({ fill: { nr: '04', busy: false } })), ['fillCancel']);
  assert.equal(modePillFor({ fill: { nr: '04', busy: true } }).detail, 'Ieškoma kontūro…');
  assert.deepEqual(ids(modePillFor({ symbolActive: true })), ['symbolClose']);
});
