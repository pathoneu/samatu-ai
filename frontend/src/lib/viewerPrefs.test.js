import { test } from 'node:test';
import assert from 'node:assert/strict';
import { shouldCollapseThumbnails } from './viewerPrefs.js';

test('shouldCollapseThumbnails: respects saved collapsed preference', () => {
  assert.equal(shouldCollapseThumbnails({ savedValue: '1', totalPages: 3 }), true);
  assert.equal(shouldCollapseThumbnails({ savedValue: '0', totalPages: 80 }), false);
});

test('shouldCollapseThumbnails: collapses large PDFs by default', () => {
  assert.equal(shouldCollapseThumbnails({ savedValue: null, totalPages: 21 }), true);
  assert.equal(shouldCollapseThumbnails({ savedValue: null, totalPages: 20 }), false);
});
