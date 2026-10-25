import test from 'node:test';
import assert from 'node:assert/strict';
import { RAIL_GROUPS, RAIL_TOOLS, railShortcut, railKey, railTooltip, railTool } from './toolRail.js';
import { VIEWER_SHORTCUTS, matchViewerHotkey } from './viewerShortcuts.js';

const ev = (key, mods = {}) => ({ key, metaKey: false, ctrlKey: false, altKey: false, shiftKey: false, ...mods });

test('the rail holds the planned cards in order', () => {
  assert.deepEqual(RAIL_GROUPS.map((g) => g.id), ['navigate', 'measure', 'read', 'layers']);
  assert.deepEqual(RAIL_TOOLS.map((t) => t.id), [
    'select', 'lasso', 'pan', 'distance', 'area', 'perimeter', 'count', 'room', 'legend', 'findSimilar', 'scaleLine', 'calibrate', 'zones', 'walls',
  ]);
});

test('every rail item has a key, and no two items share one', () => {
  const seen = new Map();
  for (const t of RAIL_TOOLS) {
    const entry = railShortcut(t.id);
    assert.ok(entry, `${t.id} has no shortcut entry`);
    assert.equal(entry.bound, 'hotkeys', `${t.id} must be a hotkey`);
    assert.ok(railKey(t.id), `${t.id} has no key text`);
    for (const c of entry.combos) {
      for (const k of c.keys) {
        const sig = `${c.mod || ''}|${c.shift ?? '*'}|${k.toLowerCase()}`;
        assert.ok(!seen.has(sig) || seen.get(sig) === t.id, `${t.id} and ${seen.get(sig)} share ${sig}`);
        seen.set(sig, t.id);
      }
    }
  }
});

test('the keys the rail shows are the keys that arm it', () => {
  const expect = { select: '1', lasso: 'L', pan: 'H', distance: '2', area: '3', perimeter: '4', count: '6', room: 'R', findSimilar: 'F', scaleLine: 'N', calibrate: 'K', zones: 'U', walls: 'S' };
  for (const [id, key] of Object.entries(expect)) {
    assert.equal(railKey(id, { mac: false }), key, id);
    assert.equal(matchViewerHotkey(ev(key.toLowerCase())), railShortcut(id).id, `${key} arms ${id}`);
  }
  assert.equal(railKey('select', { mac: false, all: true }), '1 / V');
});

test('the room tool R is registered for W1-D (the combo exists even before the tool is wired)', () => {
  const room = VIEWER_SHORTCUTS.find((s) => s.id === 'toolRoom');
  assert.ok(room);
  assert.equal(room.tool, 'room');
  assert.match(room.label, /^Patalpa/);
  assert.equal(matchViewerHotkey(ev('R', { shiftKey: true })), 'toolRoom');
});

test('labels fit the 64 px card; tooltips say name, key and one sentence', () => {
  for (const t of RAIL_TOOLS) {
    assert.ok(t.label.length <= 10, `${t.id}: „${t.label}" is too long for the card`);
    assert.ok(t.sentence.endsWith('.'), t.id);
  }
  assert.equal(railTooltip('distance', { mac: false }).startsWith('Atstumas (2) — '), true);
  assert.equal(railTooltip('findSimilar', { mac: false }).startsWith('Rasti panašius (F) — '), true);
  assert.equal(railTool('nope'), null);
  assert.equal(railTooltip('nope'), '');
});
