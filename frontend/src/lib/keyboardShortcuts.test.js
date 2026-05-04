// frontend/src/lib/keyboardShortcuts.test.js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { keyToTool, attachShortcuts } from './keyboardShortcuts.js';

test('keyToTool maps single keys to gesture tools', () => {
  assert.equal(keyToTool('v'), 'pan');
  assert.equal(keyToTool('V'), 'pan');
  assert.equal(keyToTool('1'), 'g1');
  assert.equal(keyToTool('5'), 'g5');
  assert.equal(keyToTool('Escape'), 'pan');
  assert.equal(keyToTool('q'), null);
});

test('keyToTool ignores when typing in input', () => {
  assert.equal(keyToTool('1', { tagName: 'INPUT' }), null);
  assert.equal(keyToTool('1', { tagName: 'TEXTAREA' }), null);
  assert.equal(keyToTool('1', { isContentEditable: true }), null);
});

test('attachShortcuts wires keydown listener and unsubscribes', () => {
  const calls = [];
  const fakeWindow = {
    listeners: {},
    addEventListener(ev, fn) { this.listeners[ev] = fn; },
    removeEventListener(ev) { delete this.listeners[ev]; },
  };
  const detach = attachShortcuts({
    setCurrentTool: (tool) => calls.push(tool),
    win: fakeWindow,
  });
  fakeWindow.listeners.keydown({ key: '3', target: { tagName: 'BODY' } });
  fakeWindow.listeners.keydown({ key: 'Escape', target: { tagName: 'BODY' } });
  detach();
  assert.deepEqual(calls, ['g3', 'pan']);
  assert.equal(fakeWindow.listeners.keydown, undefined);
});
