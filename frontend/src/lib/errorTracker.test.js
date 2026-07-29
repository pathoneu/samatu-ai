import test from 'node:test';
import assert from 'node:assert/strict';
import { isBenignError } from './errorTracker.js';

test('isBenignError: ResizeObserver noise is filtered', () => {
  assert.equal(isBenignError('ResizeObserver loop completed with undelivered notifications.'), true);
  assert.equal(isBenignError('ResizeObserver loop limit exceeded'), true);
  // Chrome prefixes window.onerror messages with "Uncaught " only for thrown
  // Errors; the RO warning arrives bare, so anchoring at ^ is correct.
  assert.equal(isBenignError('resizeobserver loop completed'), true);
});

test('isBenignError: real errors are NOT filtered', () => {
  assert.equal(isBenignError("Cannot read properties of undefined (reading 'patalpos')"), false);
  assert.equal(isBenignError('TypeError: network error'), false);
  assert.equal(isBenignError('Upload pipeline failed'), false);
  // A ResizeObserver mention inside a real stack trace must still report.
  assert.equal(isBenignError('TypeError: x is not a function at ResizeObserver loop'), false);
});

test('isBenignError: empty / non-string input', () => {
  assert.equal(isBenignError(''), false);
  assert.equal(isBenignError(null), false);
  assert.equal(isBenignError(undefined), false);
});
