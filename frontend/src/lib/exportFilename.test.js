import test from 'node:test';
import assert from 'node:assert/strict';
import { sanitizeExportFilename } from './exportFilename.js';

test('sanitizeExportFilename: keeps Lithuanian diacritics', () => {
  assert.equal(sanitizeExportFilename('Ąžuolų g. 24'), 'Ąžuolų g. 24');
  assert.equal(
    sanitizeExportFilename('Ąžuolų alėja 5 — Šiaulių įstaiga'),
    'Ąžuolų alėja 5 Šiaulių įstaiga',
  );
});

test('sanitizeExportFilename: strips filesystem-hostile characters', () => {
  assert.equal(sanitizeExportFilename('a/b\\c:d*e?f"g<h>i|j'), 'abcdefghij');
  assert.equal(sanitizeExportFilename('projektas\n\t2'), 'projektas 2');
});

test('sanitizeExportFilename: keeps dots, dashes and underscores', () => {
  assert.equal(sanitizeExportFilename('v1.2_final-b'), 'v1.2_final-b');
});

test('sanitizeExportFilename: no leading dot / trailing dot or space', () => {
  assert.equal(sanitizeExportFilename('  .slaptas.  '), 'slaptas');
});

test('sanitizeExportFilename: falls back when nothing survives', () => {
  assert.equal(sanitizeExportFilename('///'), 'projektas');
  assert.equal(sanitizeExportFilename(''), 'projektas');
  assert.equal(sanitizeExportFilename(null), 'projektas');
  assert.equal(sanitizeExportFilename('***', 'atsarginis'), 'atsarginis');
});
