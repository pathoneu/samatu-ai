import test from 'node:test';
import assert from 'node:assert/strict';
import { createDebouncedRun, createRequestOrder } from './debouncedRun.js';

// A hand-driven clock: a timer fires only when the test moves time past it.
function clock() {
  let now = 0;
  let seq = 0;
  const timers = new Map();
  return {
    setTimer: (fn, ms) => { seq += 1; timers.set(seq, { fn, at: now + ms }); return seq; },
    clearTimer: (id) => { timers.delete(id); },
    advance(ms) {
      now += ms;
      for (const [id, t] of [...timers]) {
        if (t.at <= now) { timers.delete(id); t.fn(); }
      }
    },
    get armed() { return timers.size; },
  };
}

function setup() {
  const c = clock();
  const ran = [];
  const debounced = createDebouncedRun(400, c);
  const run = (name) => () => ran.push(name);
  return { c, ran, debounced, run };
}

test('a burst of edits makes one run — the last one — once the wait is over', () => {
  const { c, ran, debounced, run } = setup();
  debounced.schedule(run('a'));
  c.advance(200);
  debounced.schedule(run('b'));
  c.advance(399);
  assert.deepEqual(ran, []);
  c.advance(1);
  assert.deepEqual(ran, ['b']);
  assert.equal(c.armed, 0);
});

test('closing the drawer flushes the waiting run at once — it is not dropped, and it does not run twice', () => {
  // 2026-10-06: toggling a setting and closing within 400 ms saved the setting and never recomputed the rows
  const { c, ran, debounced, run } = setup();
  debounced.schedule(run('a'));
  debounced.schedule(run('b'));
  assert.equal(debounced.flush(), true);
  assert.deepEqual(ran, ['b']);
  assert.equal(c.armed, 0, 'the timer is gone');
  c.advance(1000);
  assert.deepEqual(ran, ['b']);
});

test('nothing waiting — closing runs nothing', () => {
  const { c, ran, debounced, run } = setup();
  assert.equal(debounced.flush(), false);
  debounced.schedule(run('a'));
  c.advance(400);
  assert.equal(debounced.flush(), false, 'the run already happened');
  assert.deepEqual(ran, ['a']);
});

test('the newest request per project wins — also when it comes from the drawer opened again', () => {
  const order = createRequestOrder();
  const flushedOnClose = order.next('p1');          // the run the closed drawer flushed, still answering
  assert.equal(order.isLatest('p1', flushedOnClose), true);
  const afterReopen = order.next('p1');             // an edit after the drawer was opened again
  assert.equal(order.isLatest('p1', flushedOnClose), false);
  assert.equal(order.isLatest('p1', afterReopen), true);
  // another project's requests never supersede this one's
  const other = order.next('p2');
  assert.equal(order.isLatest('p1', afterReopen), true);
  assert.equal(order.isLatest('p2', other), true);
});
