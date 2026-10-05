import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { CONTINUING_RUN_KEYS, newRunEnding } from './runEndNotice.js';

const HERE = dirname(fileURLToPath(import.meta.url));
const LT = JSON.parse(readFileSync(join(HERE, '../i18n/lt.json'), 'utf8'));
const at = (dict, key) => key.split('.').reduce((n, k) => (n == null ? n : n[k]), dict);

test('a run the server still reads is a notice: the dropped connection, and his cancel after the start', () => {
  assert.deepEqual(newRunEnding('waiting'), { key: 'newProject.errStreamLostButRunning', tone: 'notice' });
  assert.deepEqual(newRunEnding('user', { started: true }), { key: 'newProject.cancelledRunContinues', tone: 'notice' });
  assert.deepEqual(newRunEnding('cancelled'), { key: 'newProject.cancelledRunContinues', tone: 'notice' });
});

test('every ending that leaves no project stays an error', () => {
  // a cancel before the server started: nothing is read, nothing will appear
  assert.deepEqual(newRunEnding('user', { started: false }), { key: 'newProject.abortedByUser', tone: 'error' });
  for (const why of ['interrupted', 'failed', 'lost', 'stalled', 'timeout', 'network', 'kazkas']) {
    assert.equal(newRunEnding(why).tone, 'error', why);
    assert.ok(!CONTINUING_RUN_KEYS.includes(newRunEnding(why).key), why);
  }
});

test('the notice texts say the project will appear in „Projektai" — that is what makes them news', () => {
  for (const key of CONTINUING_RUN_KEYS) {
    assert.match(at(LT, key), /Projektai/, key);
  }
});
