import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import {
  VIEWER_SHORTCUTS, SHORTCUT_GROUPS, matchViewerHotkey, formatCombo, keyText, withKey,
  hintText, shortcutGuideRows, isMacPlatform, isPanHoldKey,
} from './viewerShortcuts.js';

const ev = (key, mods = {}) => ({ key, metaKey: false, ctrlKey: false, altKey: false, shiftKey: false, ...mods });

// The handler table ViewerHotkeys dispatches on, read from its source between the markers.
function viewerHotkeyHandlerIds() {
  const src = readFileSync(fileURLToPath(new URL('../components/viewer/TakeoffViewer.jsx', import.meta.url)), 'utf8');
  const start = src.indexOf('// HOTKEY-HANDLERS:start');
  const end = src.indexOf('// HOTKEY-HANDLERS:end');
  assert.ok(start > 0 && end > start, 'ViewerHotkeys handler markers not found');
  return [...src.slice(start, end).matchAll(/^\s*(\w+):\s*\(/gm)].map((x) => x[1]);
}

test('every hotkey ViewerHotkeys handles is in the shortcut table, and every table hotkey has a handler', () => {
  const handled = viewerHotkeyHandlerIds();
  assert.ok(handled.length >= 15, `only ${handled.length} handlers parsed`);
  const table = VIEWER_SHORTCUTS.filter((s) => s.bound === 'hotkeys').map((s) => s.id);
  for (const id of handled) assert.ok(table.includes(id), `handler „${id}" missing from viewerShortcuts`);
  for (const id of table) assert.ok(handled.includes(id), `table entry „${id}" has no ViewerHotkeys handler`);
});

test('ViewerHotkeys matches keys only through matchViewerHotkey (no stray e.key switch)', () => {
  const src = readFileSync(fileURLToPath(new URL('../components/viewer/TakeoffViewer.jsx', import.meta.url)), 'utf8');
  const from = src.indexOf('function ViewerHotkeys(');
  const body = src.slice(from, src.indexOf('\n}\n', from));
  assert.ok(body.includes('matchViewerHotkey(e)'));
  assert.ok(!/switch \(e\.key\)/.test(body), 'ViewerHotkeys must not switch on e.key');
});

test('ids are unique and every entry belongs to a group and has keys to show', () => {
  const ids = VIEWER_SHORTCUTS.map((s) => s.id);
  assert.equal(new Set(ids).size, ids.length);
  const groups = new Set(SHORTCUT_GROUPS.map((g) => g.id));
  for (const s of VIEWER_SHORTCUTS) {
    assert.ok(groups.has(s.group), s.id);
    assert.ok(s.display || s.combos?.length, s.id);
  }
});

test('no two hotkey entries claim the same key combo', () => {
  const seen = new Map();
  for (const s of VIEWER_SHORTCUTS.filter((x) => x.bound === 'hotkeys')) {
    for (const c of s.combos) {
      for (const k of c.keys) {
        const sig = `${c.mod || ''}|${c.shift ?? '*'}|${k}`;
        assert.ok(!seen.has(sig), `${s.id} and ${seen.get(sig)} both bind ${sig}`);
        seen.set(sig, s.id);
      }
    }
  }
});

test('matchViewerHotkey: plain keys, modifiers and shift', () => {
  assert.equal(matchViewerHotkey(ev('2')), 'toolDistance');
  assert.equal(matchViewerHotkey(ev('=')), 'zoomIn');
  assert.equal(matchViewerHotkey(ev('?', { shiftKey: true })), 'openGuide');
  assert.equal(matchViewerHotkey(ev('PageDown')), 'nextPage');
  assert.equal(matchViewerHotkey(ev('z', { ctrlKey: true })), 'undo');
  assert.equal(matchViewerHotkey(ev('z', { metaKey: true })), 'undo');
  assert.equal(matchViewerHotkey(ev('Z', { metaKey: true, shiftKey: true })), 'redo');
  assert.equal(matchViewerHotkey(ev('y', { ctrlKey: true })), 'redo');
  assert.equal(matchViewerHotkey(ev('f', { ctrlKey: true })), 'openSearch');
  assert.equal(matchViewerHotkey(ev('p', { metaKey: true })), 'print');
  assert.equal(matchViewerHotkey(ev('l')), 'toolLasso');
  assert.equal(matchViewerHotkey(ev('L', { shiftKey: true })), 'toolLasso');
  // v3 click model: every rail tool has a key; 1 / V is „Žymėti", fit-to-width moved to W
  assert.equal(matchViewerHotkey(ev('1')), 'toolSelect');
  assert.equal(matchViewerHotkey(ev('v')), 'toolSelect');
  assert.equal(matchViewerHotkey(ev('w')), 'fitWidth');
  assert.equal(matchViewerHotkey(ev('h')), 'toolPan');
  assert.equal(matchViewerHotkey(ev('k')), 'toolCalibrate');
  assert.equal(matchViewerHotkey(ev('r')), 'toolRoom');
  // plain F is „Rasti panašius"; text search keeps Ctrl+F and /
  assert.equal(matchViewerHotkey(ev('f')), 'toolFindSimilar');
  assert.equal(matchViewerHotkey(ev('/')), 'openSearch');
  // frame the selection: Shift+F or „."; room actions E / M / X
  assert.equal(matchViewerHotkey(ev('F', { shiftKey: true })), 'frameSelection');
  assert.equal(matchViewerHotkey(ev('.')), 'frameSelection');
  assert.equal(matchViewerHotkey(ev('e')), 'roomEditOutline');
  assert.equal(matchViewerHotkey(ev('m')), 'roomMerge');
  assert.equal(matchViewerHotkey(ev('x')), 'roomSubtract');
  // Space is the held pan, not a hotkey
  assert.equal(matchViewerHotkey(ev(' ')), null);
  // plain Z is the draft / outline undo, not the global one
  assert.equal(matchViewerHotkey(ev('z')), null);
  // browser combos stay with the browser
  assert.equal(matchViewerHotkey(ev('c', { ctrlKey: true })), null);
  assert.equal(matchViewerHotkey(ev('2', { ctrlKey: true })), null);
  assert.equal(matchViewerHotkey(ev('z', { ctrlKey: true, altKey: true })), null);
});

test('modifier wording: ⌘ on Mac, Ctrl elsewhere', () => {
  const redo = { keys: ['z'], mod: 'primary', shift: true };
  assert.equal(formatCombo(redo, { mac: true }), '⌘ ⇧ Z');
  assert.equal(formatCombo(redo, { mac: false }), 'Ctrl + Shift + Z');
  assert.equal(keyText('undo', { mac: false }), 'Ctrl + Z');
  assert.equal(keyText('wheelZoom', { mac: false }), 'Ctrl + pelės ratukas');
  assert.match(keyText('wheelZoom', { mac: true }), /^⌘/);
  assert.equal(isMacPlatform({ platform: 'MacIntel' }), true);
  assert.equal(isMacPlatform({ platform: 'Win32' }), false);
});

test('titles and hints read the table', () => {
  assert.equal(withKey('Tolinti', 'zoomOut', { mac: false }), 'Tolinti (−)');
  assert.equal(withKey('Kitas puslapis', 'nextPage', { mac: false }), 'Kitas puslapis (PgDn)');
  assert.equal(hintText(['outlineUndo', 'outlineSave', 'outlineCancel'], { mac: false }), 'Z — atgal · Enter — išsaugoti · Esc — atšaukti');
  assert.equal(hintText(['draftUndoPoint'], { mac: false }), 'Z / Backspace — atgal');
});

test('guide rows cover every entry exactly once, in group order', () => {
  const rows = shortcutGuideRows({ mac: false });
  assert.deepEqual(rows.map((r) => r.group), SHORTCUT_GROUPS.map((g) => g.id));
  assert.equal(rows.reduce((n, r) => n + r.items.length, 0), VIEWER_SHORTCUTS.length);
  for (const r of rows) for (const it of r.items) assert.ok(it.keys.length > 0, it.id);
});

test('Space held pans from any tool; with a modifier it stays the browser\'s', () => {
  assert.equal(isPanHoldKey(ev(' ')), true);
  assert.equal(isPanHoldKey(ev(' ', { ctrlKey: true })), false);
  assert.equal(isPanHoldKey(ev('a')), false);
  assert.equal(isPanHoldKey(null), false);
});

test('Esc is one key with one meaning: a step back (lib/escOrder), listed where it acts', () => {
  const esc = VIEWER_SHORTCUTS.filter((s) => (s.combos || []).some((c) => c.keys.includes('Escape')));
  assert.deepEqual(esc.filter((s) => s.bound === 'hotkeys').map((s) => s.id), ['escape']);
  for (const s of esc.filter((x) => x.bound !== 'hotkeys')) assert.equal(s.bound, 'esc', s.id);
  assert.equal(hintText(['draftStepBack'], { mac: false }), 'Esc — atgal');
});
