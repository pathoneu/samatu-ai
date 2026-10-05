/**
 * lib/heldReread — a paid re-read that outlives its page: what is remembered,
 * what the project page does with it on open, and when it is forgotten.
 *
 * What matters most (2026-10-03 review): a read the server HOLDS for a page
 * that was reloaded is merged once — never zero times (the paid read thrown
 * away), never twice (the merged project already carries the run).
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import {
  rememberRereadRun, recallRereadRun, forgetRereadRun,
  rereadInFlight, trackReread,
  heldRereadAction, heldRereadOutcomeAction, keepRunAfterCardEnding,
  lostRunUnhandled, LOST_GRACE_MS, settleHeldReread,
} from './heldReread.js';
import { waitForExtraction } from './extractionRun.js';

/** A Storage-like store; `broken` makes every call throw (blocked site data). */
function memStore({ broken = false } = {}) {
  const m = new Map();
  const guard = () => { if (broken) throw new Error('SecurityError'); };
  return {
    getItem: (k) => { guard(); return m.has(k) ? m.get(k) : null; },
    setItem: (k, v) => { guard(); m.set(k, String(v)); },
    removeItem: (k) => { guard(); m.delete(k); },
    size: () => m.size,
  };
}

const P = { id: 'proj-1' };
const job = (status, extra = {}) => ({
  job: { id: 'run-1', status, kind: 'reread', project_id: 'proj-1', result: null, ...extra },
});
const READ = { patalpos: [{ nr: '1' }] };

// ── remembering ─────────────────────────────────────────────────────────────

test('the run id is remembered per project and recalled', () => {
  const s = memStore();
  rememberRereadRun('proj-1', 'run-1', s);
  rememberRereadRun('proj-2', 'run-9', s);
  assert.equal(recallRereadRun('proj-1', s), 'run-1');
  assert.equal(recallRereadRun('proj-2', s), 'run-9');
  assert.equal(recallRereadRun('proj-3', s), null);
});

test('forgetting an older run never forgets the newer one', () => {
  const s = memStore();
  rememberRereadRun('proj-1', 'run-2', s);
  forgetRereadRun('proj-1', 'run-1', s);          // the old run's ending
  assert.equal(recallRereadRun('proj-1', s), 'run-2');
  forgetRereadRun('proj-1', 'run-2', s);
  assert.equal(recallRereadRun('proj-1', s), null);
  rememberRereadRun('proj-1', 'run-3', s);
  forgetRereadRun('proj-1', null, s);              // unconditional
  assert.equal(recallRereadRun('proj-1', s), null);
});

test('storage that throws (private window, blocked data) never throws here', () => {
  const s = memStore({ broken: true });
  assert.doesNotThrow(() => rememberRereadRun('proj-1', 'run-1', s));
  assert.equal(recallRereadRun('proj-1', s), null);
  assert.doesNotThrow(() => forgetRereadRun('proj-1', 'run-1', s));
  // No storage at all (node has no localStorage): the default is a no-op.
  assert.doesNotThrow(() => rememberRereadRun('proj-1', 'run-1'));
  assert.equal(recallRereadRun('proj-1'), null);
});

test('nothing is remembered without both ids', () => {
  const s = memStore();
  rememberRereadRun('', 'run-1', s);
  rememberRereadRun('proj-1', null, s);
  assert.equal(s.size(), 0);
});

// ── on project open ─────────────────────────────────────────────────────────

test('nothing remembered → nothing to do (and no question asked)', () => {
  assert.deepEqual(heldRereadAction(null, P, null), { do: 'nothing' });
});

test('a held read for this project is applied', () => {
  assert.deepEqual(heldRereadAction('run-1', P, job('done', { result: READ })),
    { do: 'apply', result: READ });
});

test('applied once: a project that already carries the run forgets it, whatever the server says', () => {
  const merged = { ...P, _reread_run_id: 'run-1' };
  assert.deepEqual(heldRereadAction('run-1', merged, job('done', { result: READ })), { do: 'forget' });
  // A DIFFERENT earlier run on the project does not block this one.
  const older = { ...P, _reread_run_id: 'run-0' };
  assert.equal(heldRereadAction('run-1', older, job('done', { result: READ })).do, 'apply');
});

test('still running, or no answer this time → wait', () => {
  assert.deepEqual(heldRereadAction('run-1', P, job('running')), { do: 'wait' });
  assert.deepEqual(heldRereadAction('run-1', P, null), { do: 'wait' });
});

test('interrupted and failed are told and forgotten; done with nothing held is lost', () => {
  assert.deepEqual(heldRereadAction('run-1', P, job('interrupted')), { do: 'tell', why: 'interrupted' });
  assert.deepEqual(heldRereadAction('run-1', P, job('failed')), { do: 'tell', why: 'failed' });
  // Delivered over a stream (maybe to another tab, merging it right now), the
  // 3-day hold pruned, or the server hides it (the project was deleted):
  // nothing to merge — told only if, after the grace, nobody handled it.
  assert.deepEqual(heldRereadAction('run-1', P, job('done')),
    { do: 'tell', why: 'lost', afterGrace: true });
});

test('not this user\'s run (404), not a re-read, or another project\'s → forgotten silently', () => {
  assert.deepEqual(heldRereadAction('run-1', P, { missing: true }), { do: 'forget' });
  assert.deepEqual(heldRereadAction('run-1', P, job('done', { kind: 'new', result: READ })), { do: 'forget' });
  assert.deepEqual(heldRereadAction('run-1', P, job('done', { project_id: 'proj-2', result: READ })),
    { do: 'forget' });
});

// ── after waiting ───────────────────────────────────────────────────────────

test('how the wait ended → what the page does', () => {
  assert.deepEqual(heldRereadOutcomeAction({ status: 'recovered', result: READ }), { do: 'apply', result: READ });
  for (const why of ['interrupted', 'failed']) {
    assert.deepEqual(heldRereadOutcomeAction({ status: why }), { do: 'tell', why });
  }
  // Ended with nothing held while this page waited: the stream it went down
  // was another tab's — told only after the grace, if nobody handled it.
  assert.deepEqual(heldRereadOutcomeAction({ status: 'lost' }),
    { do: 'tell', why: 'lost', afterGrace: true });
  assert.deepEqual(heldRereadOutcomeAction({ status: 'recovered' }),
    { do: 'tell', why: 'lost', afterGrace: true });
  // Still running when the wait gave up, or the page went away: the run stays
  // remembered for the next open.
  assert.deepEqual(heldRereadOutcomeAction({ status: 'waiting' }), { do: 'keep' });
  assert.deepEqual(heldRereadOutcomeAction({ status: 'cancelled' }), { do: 'keep' });
  assert.deepEqual(heldRereadOutcomeAction(null), { do: 'keep' });
});

test('a lost run is told only when nobody handled it during the grace', () => {
  assert.ok(LOST_GRACE_MS >= 5_000, 'long enough for another tab to rebuild the rows');
  // Still remembered and not on the project: nobody merged it → tell.
  assert.equal(lostRunUnhandled('run-1', { remembered: 'run-1', project: P }), true);
  assert.equal(lostRunUnhandled('run-1', { remembered: 'run-1', project: null }), true);
  // The tab that had the stream merged it (stamped the project)…
  assert.equal(lostRunUnhandled('run-1',
    { remembered: 'run-1', project: { ...P, _reread_run_id: 'run-1' } }), false);
  // …or ended it and forgot the run (it told its own ending there).
  assert.equal(lostRunUnhandled('run-1', { remembered: null, project: P }), false);
  // A newer run remembered since: this one is not ours to tell any more.
  assert.equal(lostRunUnhandled('run-1', { remembered: 'run-2', project: P }), false);
  assert.equal(lostRunUnhandled(null, { remembered: null, project: P }), false);
});

test('the card keeps the run only when the server still read as its wait gave up', () => {
  assert.equal(keepRunAfterCardEnding('waiting'), true);
  for (const s of ['done', 'recovered', 'interrupted', 'failed', 'lost', 'cancelled']) {
    assert.equal(keepRunAfterCardEnding(s), false, s);
  }
});

test('end to end with the real wait: running, then held → apply', async () => {
  const realFetch = globalThis.fetch;
  const answers = [job('running').job, job('done', { result: READ }).job];
  let i = 0;
  globalThis.fetch = async (url) => {
    assert.match(String(url), /\/api\/extraction-jobs\/run-1$/);
    const a = answers[Math.min(i, answers.length - 1)];
    i += 1;
    return new Response(JSON.stringify(a), { status: 200 });
  };
  try {
    const outcome = await waitForExtraction('run-1', { kind: 'reread', sleep: async () => {} });
    assert.deepEqual(heldRereadOutcomeAction(outcome), { do: 'apply', result: READ });
  } finally {
    globalThis.fetch = realFetch;
  }
});

// ── the project page's whole flow (hooks/useHeldReread.js) ──────────────────

/**
 * The page's effects, stubbed: a project store of one project, a job answer,
 * a wait outcome, and a merge that stamps the run like applyRereadResult.
 */
function pageFlow({ project = { ...P }, answer, outcome, applyThrows = false, gone = false } = {}) {
  const store = memStore();
  rememberRereadRun('proj-1', 'run-1', store);
  const calls = { fetch: 0, wait: 0, apply: [], applied: [], waiting: 0, slept: [] };
  const box = { project, gone };
  const deps = {
    store,
    getProject: (id) => (id === 'proj-1' ? box.project : null),
    fetchJob: async (id) => { calls.fetch += 1; assert.equal(id, 'run-1'); return answer; },
    wait: async (id, { isCancelled }) => {
      calls.wait += 1;
      assert.equal(typeof isCancelled, 'function');
      return outcome;
    },
    apply: async (pid, result, { runId }) => {
      calls.apply.push({ pid, result, runId });
      if (applyThrows) throw new Error('rebuild failed');
      box.project = { ...box.project, patalpos: result.patalpos, _reread_run_id: runId };
      return box.project;
    },
    isGone: () => box.gone,
    onWaiting: () => { calls.waiting += 1; },
    onApplied: (p, info) => { calls.applied.push({ p, info }); },
    sleep: async (ms) => { calls.slept.push(ms); },
  };
  return { deps, calls, box, store };
}

test('page: a held read is merged once on open — the next open asks nothing', async () => {
  const f = pageFlow({ answer: job('done', { result: READ }) });
  assert.deepEqual(await settleHeldReread('proj-1', 'run-1', f.deps), { told: null });
  assert.equal(f.calls.apply.length, 1);
  assert.deepEqual(f.calls.apply[0], { pid: 'proj-1', result: READ, runId: 'run-1' });
  assert.equal(f.calls.applied.length, 1);
  assert.deepEqual(f.calls.applied[0].info, { merged: true });
  assert.equal(recallRereadRun('proj-1', f.store), null, 'forgotten once merged');

  // The same run remembered again (another tab, an old copy): the project
  // carries it, so the server is not even asked and nothing merges twice.
  rememberRereadRun('proj-1', 'run-1', f.store);
  assert.deepEqual(await settleHeldReread('proj-1', 'run-1', f.deps), { told: null });
  assert.equal(f.calls.fetch, 1);
  assert.equal(f.calls.apply.length, 1);
  assert.equal(recallRereadRun('proj-1', f.store), null);
});

test('page: still running → it says so, waits, then merges what the server held', async () => {
  const f = pageFlow({ answer: job('running'), outcome: { status: 'recovered', result: READ } });
  assert.deepEqual(await settleHeldReread('proj-1', 'run-1', f.deps), { told: null });
  assert.equal(f.calls.waiting, 1);
  assert.equal(f.calls.wait, 1);
  assert.equal(f.calls.apply.length, 1);
  assert.equal(recallRereadRun('proj-1', f.store), null);
});

test('page: interrupted → told and forgotten; the project is not touched', async () => {
  const f = pageFlow({ answer: job('interrupted') });
  assert.deepEqual(await settleHeldReread('proj-1', 'run-1', f.deps), { told: 'interrupted' });
  assert.equal(f.calls.apply.length, 0);
  assert.equal(recallRereadRun('proj-1', f.store), null);
});

test('page: an ending found after he left the page is kept — the next open tells it', async () => {
  const f = pageFlow({ answer: job('failed'), gone: true });
  assert.deepEqual(await settleHeldReread('proj-1', 'run-1', f.deps), { told: null });
  assert.equal(recallRereadRun('proj-1', f.store), 'run-1', 'nobody saw it: kept');
  // He opens the project again: now it is told, and forgotten.
  f.box.gone = false;
  assert.deepEqual(await settleHeldReread('proj-1', 'run-1', f.deps), { told: 'failed' });
  assert.equal(recallRereadRun('proj-1', f.store), null);
});

test('page: a wait the page left keeps the run, with no merge and nothing told', async () => {
  const f = pageFlow({ answer: job('running'), outcome: { status: 'cancelled' } });
  assert.deepEqual(await settleHeldReread('proj-1', 'run-1', f.deps), { told: null });
  assert.equal(f.calls.apply.length, 0);
  assert.equal(recallRereadRun('proj-1', f.store), 'run-1');
});

test('page: done with nothing held, merged by another tab during the grace → silent, shows it', async () => {
  const f = pageFlow({ answer: job('done') });
  // The other tab's card (it had the stream) merges and forgets while we wait.
  f.deps.sleep = async (ms) => {
    f.calls.slept.push(ms);
    f.box.project = { ...f.box.project, _reread_run_id: 'run-1' };
    forgetRereadRun('proj-1', 'run-1', f.store);
  };
  assert.deepEqual(await settleHeldReread('proj-1', 'run-1', f.deps), { told: null });
  assert.deepEqual(f.calls.slept, [LOST_GRACE_MS]);
  assert.equal(f.calls.applied.length, 1);
  assert.deepEqual(f.calls.applied[0].info, { merged: false }, 'shown, not merged again');
  assert.equal(f.calls.apply.length, 0);
});

test('page: lost while waiting and handled by nobody → told after the grace', async () => {
  const f = pageFlow({ answer: job('running'), outcome: { status: 'lost' } });
  assert.deepEqual(await settleHeldReread('proj-1', 'run-1', f.deps), { told: 'lost' });
  assert.deepEqual(f.calls.slept, [LOST_GRACE_MS]);
  assert.equal(recallRereadRun('proj-1', f.store), null);
});

test('page: a held read that cannot be merged is told and not retried', async () => {
  const f = pageFlow({ answer: job('done', { result: READ }), applyThrows: true });
  const out = await settleHeldReread('proj-1', 'run-1', f.deps);
  assert.equal(out.told, 'merge');
  assert.match(String(out.cause?.message), /rebuild failed/);
  assert.equal(recallRereadRun('proj-1', f.store), null);
  assert.equal(f.calls.applied.length, 0);
});

test('page: not his run (404) → forgotten silently, nothing merged', async () => {
  const f = pageFlow({ answer: { missing: true } });
  assert.deepEqual(await settleHeldReread('proj-1', 'run-1', f.deps), { told: null });
  assert.equal(f.calls.apply.length, 0);
  assert.equal(recallRereadRun('proj-1', f.store), null);
});

// ── one re-read per project per page load ───────────────────────────────────

test('a tracked re-read is in flight until it settles — resolved or rejected', async () => {
  let done;
  const p = new Promise((r) => { done = r; });
  trackReread('proj-x', p);
  assert.equal(rereadInFlight('proj-x'), p);
  assert.equal(rereadInFlight('proj-y'), undefined);
  done({ error: null });
  await p;
  await Promise.resolve();
  assert.equal(rereadInFlight('proj-x'), undefined);

  const failing = Promise.reject(new Error('x'));
  trackReread('proj-z', failing).catch(() => {});
  await failing.catch(() => {});
  await Promise.resolve();
  assert.equal(rereadInFlight('proj-z'), undefined);
});

test('a newer read is not cleared by an older one settling', async () => {
  let doneOld;
  const older = new Promise((r) => { doneOld = r; });
  trackReread('proj-n', older);
  const newer = new Promise(() => {});
  trackReread('proj-n', newer);
  doneOld({ error: null });
  await older;
  await Promise.resolve();
  assert.equal(rereadInFlight('proj-n'), newer);
});
