import test from 'node:test';
import assert from 'node:assert/strict';
import { closesOnEscape, isTypingTarget } from './escapeToClose.js';

const key = (k, target = { tagName: 'BUTTON' }, extra = {}) => ({ key: k, target, defaultPrevented: false, ...extra });

test('Escape closes the drawer from a button, the drawer itself or the page', () => {
  assert.equal(closesOnEscape(key('Escape')), true);
  assert.equal(closesOnEscape(key('Escape', { tagName: 'DIV' })), true);
  assert.equal(closesOnEscape(key('Escape', { tagName: 'BODY' })), true);
});

test('Escape typed in a field stays with the field — the drawer does not close under it', () => {
  for (const tagName of ['INPUT', 'TEXTAREA', 'SELECT', 'input']) {
    assert.equal(closesOnEscape(key('Escape', { tagName })), false, tagName);
  }
  assert.equal(closesOnEscape(key('Escape', { tagName: 'DIV', isContentEditable: true })), false);
});

test('an Escape something inside already handled does not close it too', () => {
  assert.equal(closesOnEscape(key('Escape', { tagName: 'BUTTON' }, { defaultPrevented: true })), false);
});

test('other keys, and no event at all, close nothing', () => {
  for (const k of ['Enter', 'Esc', 'q', ' ']) assert.equal(closesOnEscape(key(k)), false, k);
  assert.equal(closesOnEscape(null), false);
  assert.equal(closesOnEscape(key('Escape', null)), true, 'no target (the window) is not a field');
});

test('what counts as a field being typed in', () => {
  assert.equal(isTypingTarget({ tagName: 'INPUT' }), true);
  assert.equal(isTypingTarget({ tagName: 'BUTTON' }), false);
  assert.equal(isTypingTarget({ tagName: 'P', isContentEditable: true }), true);
  assert.equal(isTypingTarget(null), false);
  assert.equal(isTypingTarget(undefined), false);
});
