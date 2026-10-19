import test from 'node:test';
import assert from 'node:assert/strict';
import { CURSORS, CURSOR_MODES, cursorForMode, cursorOf } from './cursors.js';
import { RAIL_TOOLS } from './toolRail.js';
import { CURSOR_HINT_MODES } from './cursorHints.js';

const CSS_CURSORS = new Set(['default', 'grab', 'grabbing', 'crosshair', 'move', 'copy', 'pointer', 'progress', 'not-allowed']);

test('every cursor in the table is a valid CSS cursor', () => {
  for (const [role, css] of Object.entries(CURSORS)) assert.ok(CSS_CURSORS.has(css), `${role}: ${css}`);
});

test('every tool on the rail and every hint mode has a cursor of its own', () => {
  for (const t of RAIL_TOOLS.filter((x) => !x.toggle)) assert.ok(CURSOR_MODES.includes(t.id), t.id);
  for (const m of CURSOR_HINT_MODES) assert.ok(CURSOR_MODES.includes(m), m);
});

test('placing a point is a crosshair, a drag a grabbing hand, rest the arrow', () => {
  for (const m of ['distance', 'area', 'perimeter', 'count', 'calibrate']) assert.equal(cursorForMode(m), 'crosshair', m);
  assert.equal(cursorOf('dragging'), 'grabbing');
  assert.equal(cursorForMode(null), 'default');
  assert.equal(cursorOf('nonsense'), 'default');
});
