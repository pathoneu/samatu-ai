/**
 * lib/extractionRun — the stream, the hand-off and the wait, against a mocked
 * fetch. The server side is played by scripts: an SSE body that emits, hangs,
 * drops or ends, and job/project answers the poller reads in order.
 *
 * What matters most (2026-10-03): a run the server reports INTERRUPTED (a
 * redeploy killed it), failed or lost ends the wait at once and is never
 * described as still running; only a run still running after the wait may be.
 */

import test, { afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import {
  runExtraction, waitForExtraction, fetchExtractionJob, runEndText, RUN_END_KEYS,
  ExtractionStopped, isUsableProject, reduceStreamProgress, progressLine,
} from './extractionRun.js';

const HERE = dirname(fileURLToPath(import.meta.url));
const LT = JSON.parse(readFileSync(join(HERE, '../i18n/lt.json'), 'utf8'));
const EN = JSON.parse(readFileSync(join(HERE, '../i18n/en.json'), 'utf8'));
/** The value at a dotted key, or undefined. */
const at = (dict, key) => key.split('.').reduce((n, k) => (n == null ? n : n[k]), dict);
const lt = (key) => at(LT, key);

const realFetch = globalThis.fetch;
afterEach(() => { globalThis.fetch = realFetch; });

const delay = (ms) => new Promise((r) => setTimeout(r, ms));
const noSleep = async () => {};

/** An SSE body. Steps: {data}, {heartbeat}, {wait}, {drop}, {hang}. */
function sseBody(steps, signal) {
  const enc = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      let closed = false;
      const abort = () => {
        if (closed) return;
        closed = true;
        try { controller.error(new DOMException('The operation was aborted.', 'AbortError')); } catch { /* done */ }
      };
      signal?.addEventListener('abort', abort);
      (async () => {
        for (const s of steps) {
          if (closed) return;
          if (s.wait) await delay(s.wait);
          else if (s.data) controller.enqueue(enc.encode(`data: ${JSON.stringify(s.data)}\n\n`));
          else if (s.heartbeat) controller.enqueue(enc.encode(': heartbeat\n\n'));
          else if (s.drop) {
            // A real connection delivers what it already sent before it dies;
            // error() would discard chunks still queued, so let the reader drain.
            await delay(10);
            closed = true;
            controller.error(new TypeError('network error'));
            return;
          }
          else if (s.hang) return;              // open until aborted
        }
        if (!closed) { closed = true; controller.close(); }
      })();
    },
  });
}

const json = (body, status = 200) => new Response(JSON.stringify(body), {
  status, headers: { 'Content-Type': 'application/json' },
});

/**
 * Install a fetch that serves the stream from `stream` steps and answers
 * job / project GETs from the given queues (the last answer repeats).
 */
function serve({ stream = [], streamStatus = 200, streamBody = null, jobs = [], projects = {} } = {}) {
  const calls = [];
  let jobIdx = 0;
  globalThis.fetch = async (url, init = {}) => {
    calls.push({ url: String(url), method: init.method || 'GET' });
    if (init.signal?.aborted) throw new DOMException('aborted', 'AbortError');
    if (String(url).endsWith('/extract-interior-stream')) {
      if (streamStatus !== 200) return json(streamBody || {}, streamStatus);
      return new Response(sseBody(stream, init.signal), {
        status: 200, headers: { 'Content-Type': 'text/event-stream' },
      });
    }
    const jobMatch = String(url).match(/\/api\/extraction-jobs\/(.+)$/);
    if (jobMatch) {
      const answer = jobs[Math.min(jobIdx, jobs.length - 1)];
      jobIdx += 1;
      if (answer === undefined || answer === 404) return json({ detail: 'Skaitymas nerastas' }, 404);
      if (answer === 'offline') throw new TypeError('Failed to fetch');
      return json(answer);
    }
    const projMatch = String(url).match(/\/api\/projects\/(.+)$/);
    if (projMatch) {
      const p = projects[decodeURIComponent(projMatch[1])];
      return p ? json(p) : json({ detail: 'not found' }, 404);
    }
    throw new Error(`unexpected fetch ${url}`);
  };
  return calls;
}

const RID = 'run-1';
const started = [{ data: { event: 'recovery_id', project_id: RID } }, { data: { event: 'started', page_count: 3 } }];
const job = (status, extra = {}) => ({ id: RID, status, kind: 'new', project_id: null, result: null, ...extra });

// ── the stream delivers ─────────────────────────────────────────────────────

test('a healthy stream returns its result and every event, heartbeats included', async () => {
  serve({ stream: [...started, { heartbeat: true },
    { data: { event: 'done', result: { status: 'ok', patalpos: [{ nr: '1' }] } } }] });
  const seen = [];
  const out = await runExtraction(new FormData(), { onEvent: (ev) => seen.push(ev.event) });
  assert.equal(out.status, 'done');
  assert.equal(out.recoveryId, RID);
  assert.deepEqual(out.result.patalpos, [{ nr: '1' }]);
  assert.deepEqual(seen, ['recovery_id', 'started', 'heartbeat', 'done']);
});

test('an error result is still "done": the caller reads result.status as before', async () => {
  serve({ stream: [...started, { data: { event: 'done', result: { status: 'error', _error: 'x' } } }] });
  const out = await runExtraction(new FormData());
  assert.equal(out.status, 'done');
  assert.equal(out.result.status, 'error');
});

// ── the hand-off and the wait ───────────────────────────────────────────────

test('edge deadline: we let go, wait, and land the project the server saved', async () => {
  const calls = serve({
    stream: [...started, { hang: true }],
    jobs: [job('running'), job('done', { project_id: RID })],
    projects: { [RID]: { id: RID, patalpos: [{ nr: '1' }] } },
  });
  const handoffs = [];
  const ticks = [];
  const out = await runExtraction(new FormData(), {
    edgeDeadlineMs: 30, sleep: noSleep,
    onHandoff: (why, id) => handoffs.push([why, id]),
    onPollTick: (s) => ticks.push(s),
  });
  assert.equal(out.status, 'recovered');
  assert.equal(out.project.id, RID);
  assert.equal(out.handoff, 'edge_deadline');
  assert.deepEqual(handoffs, [['edge_deadline', RID]]);
  assert.equal(ticks.length, 1, 'one tick for the one "running" answer');
  assert.ok(calls.some((c) => c.url.endsWith(`/api/extraction-jobs/${RID}`)));
});

test('a redeploy killed the run: the wait ends at once with "interrupted"', async () => {
  const calls = serve({ stream: [...started, { drop: true }], jobs: [job('interrupted', { error: 'restart' })] });
  const out = await runExtraction(new FormData(), { sleep: noSleep });
  assert.equal(out.status, 'interrupted');
  assert.equal(out.handoff, 'dropped');
  assert.equal(out.job.error, 'restart');
  // One question, no 40-minute wait, and no project fetch for a run that died.
  assert.equal(calls.filter((c) => c.url.includes('/api/extraction-jobs/')).length, 1);
  assert.equal(calls.filter((c) => c.url.includes('/api/projects/')).length, 0);
});

test('failed and lost end the wait too', async () => {
  serve({ stream: [...started, { drop: true }], jobs: [job('running'), job('failed', { error: 'no_result' })] });
  assert.equal((await runExtraction(new FormData(), { sleep: noSleep })).status, 'failed');

  // done, but no project saved server-side: the result went to a stream that
  // never reached this window.
  serve({ stream: [...started, { drop: true }], jobs: [job('done')] });
  assert.equal((await runExtraction(new FormData(), { sleep: noSleep })).status, 'lost');
});

test('a stream that ends without a result hands off like a drop', async () => {
  serve({ stream: [...started], jobs: [job('done', { project_id: RID })],
    projects: { [RID]: { id: RID, status: 'empty', patalpos: [] } } });
  const out = await runExtraction(new FormData(), { sleep: noSleep });
  assert.equal(out.handoff, 'dropped');
  assert.equal(out.status, 'recovered');
  assert.equal(out.project.status, 'empty', 'a saved zero-room read is a real project');
});

test('seven silent minutes with the id known: hand off, the record decides', async () => {
  serve({ stream: [...started, { hang: true }], jobs: [job('interrupted')] });
  const out = await runExtraction(new FormData(), { idleAbortMs: 30, sleep: noSleep });
  assert.equal(out.handoff, 'stalled');
  assert.equal(out.status, 'interrupted');
});

test('a re-read: the held read comes back as `result`, never a project', async () => {
  const calls = serve({
    stream: [...started, { drop: true }],
    jobs: [job('running', { kind: 'reread', project_id: 'p-old' }),
      job('done', { kind: 'reread', project_id: 'p-old', result: { patalpos: [{ nr: '7' }] } })],
  });
  const out = await runExtraction(new FormData(), { kind: 'reread', sleep: noSleep });
  assert.equal(out.status, 'recovered');
  assert.deepEqual(out.result, { patalpos: [{ nr: '7' }] });
  assert.equal(out.project, undefined);
  assert.equal(calls.filter((c) => c.url.includes('/api/projects/')).length, 0);
});

test('a re-read done with nothing held is lost', async () => {
  serve({ stream: [...started, { drop: true }], jobs: [job('done', { kind: 'reread', project_id: 'p' })] });
  assert.equal((await runExtraction(new FormData(), { kind: 'reread', sleep: noSleep })).status, 'lost');
});

test('no job record (an older server): a new project falls back to the project itself', async () => {
  serve({ stream: [...started, { drop: true }], jobs: [404],
    projects: { [RID]: { id: RID, darbu_sarasas: [{ aprasymas: 'x' }] } } });
  const out = await runExtraction(new FormData(), { sleep: noSleep });
  assert.equal(out.status, 'recovered');
  assert.equal(out.project.id, RID);
});

test('offline blips do not end the wait', async () => {
  serve({ stream: [...started, { drop: true }],
    jobs: ['offline', 'offline', job('done', { project_id: RID })],
    projects: { [RID]: { id: RID, patalpos: [{ nr: '1' }] } } });
  assert.equal((await runExtraction(new FormData(), { sleep: noSleep })).status, 'recovered');
});

// ── waitForExtraction on its own ────────────────────────────────────────────

function fakeClock(stepMs) {
  let t = 0;
  return { now: () => t, sleep: async (ms) => { t += ms || stepMs; } };
}

test('still running when the limit passes → "waiting" (the only honest "it continues")', async () => {
  serve({ jobs: [job('running')] });
  const clock = fakeClock(10_000);
  const out = await waitForExtraction(RID, { limitMs: 60_000, ...clock });
  assert.equal(out.status, 'waiting');
});

test('a re-read with no record keeps waiting (no project fallback)', async () => {
  const calls = serve({ jobs: [404] });
  const clock = fakeClock(10_000);
  const out = await waitForExtraction(RID, { kind: 'reread', limitMs: 30_000, ...clock });
  assert.equal(out.status, 'waiting');
  assert.equal(calls.filter((c) => c.url.includes('/api/projects/')).length, 0);
});

test('isCancelled stops the wait', async () => {
  serve({ jobs: [job('running')] });
  let n = 0;
  const out = await waitForExtraction(RID, { sleep: noSleep, isCancelled: () => (n += 1) > 2 });
  assert.equal(out.status, 'cancelled');
});

test('fetchExtractionJob: 404 is "missing", a network error is no answer', async () => {
  serve({ jobs: [404] });
  assert.deepEqual(await fetchExtractionJob(RID), { missing: true });
  serve({ jobs: ['offline'] });
  assert.equal(await fetchExtractionJob(RID), null);
  serve({ jobs: [job('running')] });
  assert.equal((await fetchExtractionJob(RID)).job.status, 'running');
});

// ── the run stops on this side ──────────────────────────────────────────────

test('a drop before the id arrived is a connection problem: nothing started', async () => {
  serve({ stream: [{ drop: true }] });
  await assert.rejects(runExtraction(new FormData(), { sleep: noSleep }),
    (e) => e instanceof ExtractionStopped && e.reason === 'network');
});

test('silence before the id arrived is a stall, not a wait', async () => {
  serve({ stream: [{ hang: true }] });
  await assert.rejects(runExtraction(new FormData(), { idleAbortMs: 30 }),
    (e) => e instanceof ExtractionStopped && e.reason === 'stalled');
});

test('the cancel button aborts the caller\'s controller → "user"', async () => {
  serve({ stream: [...started, { hang: true }] });
  const controller = new AbortController();
  setTimeout(() => controller.abort(), 20);
  await assert.rejects(runExtraction(new FormData(), { controller }),
    (e) => e instanceof ExtractionStopped && e.reason === 'user'
      // The server had announced the run: it keeps reading after this cancel.
      && e.recoveryId === RID);
});

test('a cancel before the id arrived carries no run id: nothing started', async () => {
  serve({ stream: [{ hang: true }] });
  const controller = new AbortController();
  setTimeout(() => controller.abort(), 20);
  await assert.rejects(runExtraction(new FormData(), { controller }),
    (e) => e instanceof ExtractionStopped && e.reason === 'user' && e.recoveryId === null);
});

test('an HTTP refusal is rethrown with its status and body (paywall detection)', async () => {
  serve({ streamStatus: 402, streamBody: { reason: 'quota_exceeded', message: 'Limitas' } });
  await assert.rejects(runExtraction(new FormData()), (e) => {
    assert.equal(e.status, 402);
    assert.equal(e.body.reason, 'quota_exceeded');
    assert.equal(e.message, 'Limitas');
    return true;
  });
});

// ── what the user is told ───────────────────────────────────────────────────

const BANNED = /(?<![A-Za-zĄČĘĖĮŠŲŪŽąčęėįšųūž])AI(?![A-Za-zĄČĘĖĮŠŲŪŽąčęėįšųūž])|analiz|ekstrakc|vision|\bmodel/i;

test('every ending\'s key exists in lt.json and en.json (lt.json is the one source)', () => {
  assert.ok(RUN_END_KEYS.length >= 13);
  for (const key of RUN_END_KEYS) {
    assert.equal(typeof lt(key), 'string', `lt.json lacks ${key}`);
    assert.ok(lt(key).trim(), `lt.json ${key} is empty`);
    assert.equal(typeof at(EN, key), 'string', `en.json lacks ${key}`);
    // Inside the namespaces the vocabulary guard (ltVocabulary.test.js) walks.
    assert.ok(['newProject', 'project'].includes(key.split('.')[0]), key);
  }
  // The keys the components used to reach only through a defaultValue.
  for (const key of ['newProject.errRunInterrupted', 'newProject.errRunFailed',
    'newProject.errRunLost', 'project.reextract.errInterrupted', 'project.reextract.errFailed',
    'project.reextract.errLost', 'project.reextract.errStillRunning']) {
    assert.ok(RUN_END_KEYS.includes(key), key);
  }
});

test('an ending the server reported never says the work continues, nor promises money', () => {
  for (const kind of ['new', 'reread']) {
    for (const why of ['interrupted', 'failed', 'lost']) {
      const key = runEndText(kind, why);
      const text = lt(key);
      assert.ok(text, `${kind}/${why} needs text`);
      assert.doesNotMatch(text, /tęsiasi|tęsis|nekartokite|atsiras|vyksta/i, `${kind}/${why}`);
      assert.match(text, /dar kartą/i, `${kind}/${why} must say it can be started again`);
      assert.doesNotMatch(text, /€|\$|kain|mokė|mokės|nuskait|sąskait/i, `${kind}/${why}`);
      assert.doesNotMatch(text, BANNED, `${kind}/${why}`);
    }
  }
  // A re-read that stopped leaves his project as it was — and says so.
  for (const why of ['interrupted', 'failed', 'lost', 'waiting', 'user', 'cancelled']) {
    assert.match(lt(runEndText('reread', why)), /Projektas (kol kas )?nepakeistas/, why);
  }
});

test('a re-read still running when the wait gave up does not send him to start another', () => {
  const text = lt(runEndText('reread', 'waiting'));
  assert.match(text, /vyksta/);
  assert.match(text, /Naujo skaitymo pradėti nereikia/);
  assert.doesNotMatch(text, /pabandykite dar kartą/i);
});

test('a cancel is not a stop on the server — the texts say what really happens', () => {
  // A re-read: its own text, not „Skaitymas nepavyko", and no claim that the
  // server stopped — only that the result will not be written into the project.
  assert.equal(runEndText('reread', 'user'), 'project.reextract.cancelled');
  assert.equal(runEndText('reread', 'cancelled'), 'project.reextract.cancelled');
  const reread = lt('project.reextract.cancelled');
  assert.doesNotMatch(reread, /nepavyko/i);
  assert.match(reread, /atšaukėte/i);
  assert.match(reread, /nebus įrašytas/);
  assert.doesNotMatch(reread, /sustabdytas|sustojo|nutrauktas serveryje/i);

  // A new project cancelled AFTER the server started: it will still appear.
  assert.equal(runEndText('new', 'user', { started: true }), 'newProject.cancelledRunContinues');
  assert.equal(runEndText('new', 'cancelled'), 'newProject.cancelledRunContinues');
  const continues = lt('newProject.cancelledRunContinues');
  assert.match(continues, /atsiras sąraše „Projektai“/);
  assert.match(continues, /įkelti iš naujo nereikia/);
  // …and BEFORE: nothing was created, he may upload again.
  assert.equal(runEndText('new', 'user'), 'newProject.abortedByUser');
  assert.match(lt('newProject.abortedByUser'), /Projektas nesukurtas/);
  assert.doesNotMatch(lt('newProject.abortedByUser'), /vartotojo/);

  // The button's tooltip no longer promises he has to upload again.
  assert.doesNotMatch(lt('newProject.cancelTitle'), /teks įkelti iš naujo/);
  assert.match(lt('newProject.cancelTitle'), /atsiras sąraše „Projektai“/);
  for (const key of ['project.reextract.cancelled', 'newProject.cancelledRunContinues',
    'newProject.abortedByUser', 'newProject.cancelTitle', 'newProject.cancelTitleNoStream']) {
    assert.doesNotMatch(lt(key), /€|\$|kainuos|mokės/i, key);
    assert.equal(typeof at(EN, key), 'string', `en.json lacks ${key}`);
  }
});

test('the new-project endings reuse the existing keys where lt.json has them', () => {
  assert.equal(runEndText('new', 'waiting'), 'newProject.errStreamLostButRunning');
  assert.equal(runEndText('new', 'stalled'), 'newProject.errStalled');
  assert.equal(runEndText('new', 'network'), 'newProject.errNetwork');
  assert.equal(runEndText('new', 'something-new'), 'newProject.errRunFailed');
  assert.equal(runEndText('reread', 'something-new'), 'project.reextract.errFailed');
});

test('the re-read card states no price and the fixed-range line is gone', () => {
  const r = LT.project.reextract;
  assert.equal(r.bullet1, undefined, 'the „~1–2 $" line is gone');
  for (const gone of ['analyzing', 'pass1', 'pass2', 'complex']) {
    assert.equal(r[gone], undefined, `unused key ${gone} is gone from lt.json`);
    assert.equal(EN.project.reextract[gone], undefined, `unused key ${gone} is gone from en.json`);
  }
  for (const [key, text] of Object.entries(r)) {
    assert.doesNotMatch(text, /\$|€|kainuos|kainuoja/i, `project.reextract.${key}`);
  }
  assert.match(r.durationEstimate, /\{\{value\}\}/);
  // Without an estimate: no upper bound the preflight itself would break
  // (backend/extractor/preflight.estimate_minutes has a „virš valandos" tier).
  assert.match(r.durationPlain, /iki valandos ar ilgiau/);
  assert.match(EN.project.reextract.durationPlain, /an hour or more/);
});

test('isUsableProject accepts rooms, rows or a saved empty read', () => {
  assert.ok(isUsableProject({ patalpos: [{}] }));
  assert.ok(isUsableProject({ darbu_sarasas: [{}] }));
  assert.ok(isUsableProject({ status: 'empty', patalpos: [] }));
  assert.ok(!isUsableProject({ status: 'ready', patalpos: [] }));
  assert.ok(!isUsableProject(null));
});

test('the compact progress line follows the stream', () => {
  let s = null;
  assert.deepEqual(progressLine(s), ['upload.stream.reading', {}]);
  s = reduceStreamProgress(s, { event: 'started', page_count: 9 });
  assert.deepEqual(progressLine(s), ['upload.stream.readingPages', { count: 9 }]);
  s = reduceStreamProgress(s, { event: 'pass1_started' });
  assert.deepEqual(progressLine(s), ['upload.stream.recognizing', {}]);
  s = reduceStreamProgress(s, { event: 'pass1_completed', patalpos: [{}, {}, {}] });
  assert.deepEqual(progressLine(s), ['upload.stream.foundRooms', { count: 3 }]);
  s = reduceStreamProgress(s, { event: 'zoom_started', total: 3 });
  s = reduceStreamProgress(s, { event: 'zoom_room_completed', idx: 2 });
  assert.deepEqual(progressLine(s), ['upload.stream.refiningProgress', { done: 2, total: 3 }]);
  s = reduceStreamProgress(s, { event: 'heartbeat' });
  assert.deepEqual(progressLine(s), ['upload.stream.refiningProgress', { done: 2, total: 3 }]);
  s = reduceStreamProgress(s, { event: 'post_processing' });
  assert.deepEqual(progressLine(s), ['upload.stream.summing', {}]);
  assert.deepEqual(progressLine({ step: 'finishing' }), ['upload.stream.finishingOnServer', {}]);
});
