import test from 'node:test';
import assert from 'node:assert/strict';
import { patikraKeyAction } from './patikraKeys.js';

const inQueue = { insideQueue: true, targetTag: 'DIV', canAccept: true };

test('Enter in the queue takes the proposal; Esc goes back to the list', () => {
  assert.equal(patikraKeyAction({ key: 'Enter' }, inQueue), 'accept');
  assert.equal(patikraKeyAction({ key: 'Escape' }, inQueue), 'list');
});

test('Enter on the page body (nothing focused) also answers', () => {
  assert.equal(patikraKeyAction({ key: 'Enter' }, { onBody: true, targetTag: 'BODY', canAccept: true }), 'accept');
});

test('a field keeps its own Enter; Esc in a field still goes back to the list', () => {
  for (const tag of ['INPUT', 'TEXTAREA', 'SELECT']) {
    assert.equal(patikraKeyAction({ key: 'Enter' }, { ...inQueue, targetTag: tag }), null);
  }
  assert.equal(patikraKeyAction({ key: 'Enter' }, { ...inQueue, targetEditable: true }), null);
  assert.equal(patikraKeyAction({ key: 'Escape' }, { ...inQueue, targetTag: 'INPUT' }), 'list');
});

test('Enter on a focused button is that button — no second answer', () => {
  assert.equal(patikraKeyAction({ key: 'Enter' }, { ...inQueue, targetIsButton: true }), null);
});

test('nothing while a save runs, with nothing to accept, under a dialog, or with a modifier', () => {
  assert.equal(patikraKeyAction({ key: 'Enter' }, { ...inQueue, busy: true }), null);
  assert.equal(patikraKeyAction({ key: 'Enter' }, { ...inQueue, canAccept: false }), null);
  assert.equal(patikraKeyAction({ key: 'Enter' }, { ...inQueue, layerOpen: true }), null);
  assert.equal(patikraKeyAction({ key: 'Escape' }, { ...inQueue, layerOpen: true }), null);
  for (const mod of ['ctrlKey', 'metaKey', 'altKey', 'shiftKey']) {
    assert.equal(patikraKeyAction({ key: 'Enter', [mod]: true }, inQueue), null);
  }
});

test('a key another surface already handled (the drawing finishing a line) is not taken again', () => {
  assert.equal(patikraKeyAction({ key: 'Enter', defaultPrevented: true }, inQueue), null);
  assert.equal(patikraKeyAction({ key: 'Enter', isComposing: true }, inQueue), null);
});

test('keys pressed elsewhere (the drawing has the focus) are not the queue\'s', () => {
  assert.equal(patikraKeyAction({ key: 'Enter' }, { targetTag: 'CANVAS', canAccept: true }), null);
  assert.equal(patikraKeyAction({ key: 'Escape' }, { targetTag: 'CANVAS' }), null);
});
