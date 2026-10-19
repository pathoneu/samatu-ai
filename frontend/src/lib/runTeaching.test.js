import test from 'node:test';
import assert from 'node:assert/strict';
import { markReadScopeSeen, readScopeDue, runTeachingFor, USUAL_MINUTES } from './runTeaching.js';

test('each stream phase names its stage, with the counts the stream gave', () => {
  assert.equal(runTeachingFor({ phase: 'rendering' }).stageKey, 'stage.rendering');
  assert.deepEqual(runTeachingFor({ phase: 'rendering', progress: { pageCount: 8 } }).stageParams, { count: 8 });
  assert.equal(runTeachingFor({ phase: 'rendering', progress: { pageCount: 8 } }).stageKey, 'stage.renderingPages');
  assert.equal(runTeachingFor({ phase: 'pass1', progress: { rooms: [{}, {}] } }).stageKey, 'stage.pass1Rooms');
  const zoom = runTeachingFor({ phase: 'zoom', progress: { zoomDone: 3, zoomTotal: 11 } });
  assert.equal(zoom.stageKey, 'stage.zoomProgress');
  assert.deepEqual(zoom.stageParams, { done: 3, total: 11 });
  assert.equal(zoom.step, 3);
  assert.equal(zoom.steps, 4);
});

test('the hand-off is the same last step, said as finishing on the server', () => {
  const r = runTeachingFor({ phase: 'finishing' });
  assert.equal(r.step, 4);
  assert.equal(r.stageKey, 'stage.finishing');
});

test('time: whole minutes gone, the usual 25–28 min unless the preflight measured its own', () => {
  assert.equal(runTeachingFor({ elapsed: 125 }).minutes, 2);
  assert.equal(runTeachingFor({}).estimate, USUAL_MINUTES);
  assert.equal(runTeachingFor({ estMinutes: '15–20' }).estimate, '15–20');
  assert.equal(runTeachingFor({ estMinutes: 'iki 30 min' }).estimate, 'iki 30');
});

test('the window may be closed only once the server has the run', () => {
  assert.equal(runTeachingFor({ started: false }).canLeave, false);
  assert.equal(runTeachingFor({ started: true }).canLeave, true);
});

test('the card before the first run: due until seen; storage that throws never hides or breaks it', () => {
  const mem = new Map();
  const storage = { getItem: (k) => (mem.has(k) ? mem.get(k) : null), setItem: (k, v) => mem.set(k, v) };
  assert.equal(readScopeDue(storage), true);
  markReadScopeSeen(storage);
  assert.equal(readScopeDue(storage), false);
  const broken = { getItem: () => { throw new Error('blocked'); }, setItem: () => { throw new Error('blocked'); } };
  assert.equal(readScopeDue(broken), true);
  assert.doesNotThrow(() => markReadScopeSeen(broken));
  assert.equal(readScopeDue(null), true);
});
