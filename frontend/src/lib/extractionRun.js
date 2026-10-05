/**
 * extractionRun — one long, paid reading of a drawing over
 * /extract-interior-stream, start to finish. Shared by the two places that
 * start one: a new project (pages/NewProject.jsx) and a re-read of a stored
 * project (components/project/ReextractButton.jsx), so the stream, its timers,
 * the hand-off and the wait exist exactly once. (2026-10-03, audit
 * frontend-architecture-4 + data-ops-infra-4.)
 *
 * A RUN OUTLIVES ITS CONNECTION. The server announces the run's id first
 * (`recovery_id`). When the socket dies — or when we let go ourselves at
 * 840 s, before Railway's edge cuts every request at 900 s — the server keeps
 * reading, and this module WAITS for how the run ended, asking
 * GET /api/extraction-jobs/{id} every 10 s:
 *   • new project done → the server saved it under that id → fetch it;
 *   • re-read done     → the server holds the read on the job row → take it
 *                        (the caller merges it into the project it belongs to);
 *   • interrupted      → the process running it was restarted (a deploy, a
 *                        crash). Nothing will ever arrive: stop waiting;
 *   • failed           → the run ended without a result;
 *   • lost             → the result went down a connection that never reached
 *                        this window (the server considers it delivered).
 * Only a run the server still reports as running is worth waiting for — the
 * old poller waited 40 minutes on runs a redeploy had already killed, telling
 * the user all along that the work continued and not to upload again.
 *
 * THE THREE TIMERS (moved here from NewProject.jsx, numbers unchanged):
 *   • idle 7 min with no event at all (heartbeats count) → the connection is
 *     dead: hand off to the wait like a drop (a stop only if no id came);
 *   • 45 min absolute ceiling on the stream itself;
 *   • 840 s edge deadline → hand off to the wait (armed only once the id is
 *     known; without an id there is nothing to wait for).
 *
 * No i18n here: `runEndText` maps an ending to an i18n key (lt.json is the one
 * source of the text) and the components call `t()`.
 * Relative imports with .js: this module runs under `node --test`, which
 * resolves no Vite aliases.
 */

import { API_BASE as API } from './apiBase.js';
import { postSse } from './sseFetch.js';

export const IDLE_ABORT_MS = 420_000;      // 7 min with no progress event → hung
export const HARD_ABORT_MS = 2_700_000;    // 45 min absolute ceiling
// EDGE DEADLINE (2026-07-29). Railway's edge terminates the HTTP request at
// exactly 900 s — measured three times on the same 17-page project, the last
// one failing at 899 s with a bare "TypeError: network error" while the SERVER
// kept extracting for another five minutes. Waiting for that cut means the user
// always eats a scary error on a healthy run, so we let go FIRST and wait for
// the run's ending instead — same result, no error, no lost work.
export const EDGE_DEADLINE_MS = 840_000;   // 14 min < the 900 s edge cut
export const POLL_EVERY_MS = 10_000;
// WINDOW SIZING (2026-07-29, measured on the first successful recovery): a real
// run took 26 min 53 s, 12 min 40 s of it AFTER the 840 s hand-off, and landed
// with 2 min to spare in the old 15 min window. 40 min is sized off what waiting
// costs — one indexed GET every 10 s, stopped the moment the run ends — not off
// the typical run. With the job record the wait now also stops the moment the
// server says the run is over, so a long window no longer means a long lie.
// Callers pass lib/preflight.pollLimitMs, which only ever raises it.
export const DEFAULT_WAIT_MS = 40 * 60 * 1000;

const realSleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

/**
 * The run stopped on THIS side before the server could finish it — or before
 * it ever started. `reason`: 'stalled' | 'timeout' | 'user' | 'network'.
 * `recoveryId` is the run's id when the server had announced it, i.e. when the
 * reading had STARTED there: the server then keeps reading after this side
 * lets go (a new project is saved, a re-read is held on its job row), which is
 * what a cancel message has to say. null = the server never started.
 * (An HTTP refusal is rethrown as postSse built it, status + body intact, so
 * the paywall detection keeps working.)
 */
export class ExtractionStopped extends Error {
  constructor(reason, cause, recoveryId = null) {
    super(cause?.message || reason);
    this.name = 'ExtractionStopped';
    this.reason = reason;
    this.cause = cause;
    this.recoveryId = recoveryId || null;
  }
}

/** A project worth landing on: rooms, rows, or a saved zero-room read. */
export function isUsableProject(p) {
  return !!p && typeof p === 'object'
    && !!(p.patalpos?.length || p.darbu_sarasas?.length || p.status === 'empty');
}

/** Connection-level failures, as NewProject classified them before. */
function isConnectionLoss(e) {
  const msg = String(e?.message || '');
  return e?.name === 'TypeError' || /network|fetch/i.test(msg)
    || /stream ended without result/i.test(msg);
}

/**
 * Ask how a run is doing. Never throws.
 * @returns {Promise<{job: object}|{missing: true}|null>} null = no answer this time
 */
export async function fetchExtractionJob(jobId) {
  try {
    const res = await fetch(`${API}/api/extraction-jobs/${encodeURIComponent(jobId)}`,
      { credentials: 'include' });
    if (res.status === 404) return { missing: true };
    if (!res.ok) return null;
    return { job: await res.json() };
  } catch {
    return null;
  }
}

async function fetchProject(projectId) {
  try {
    const res = await fetch(`${API}/api/projects/${encodeURIComponent(projectId)}`,
      { credentials: 'include' });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

/**
 * Wait for a handed-off run to end.
 *
 * @param {string} recoveryId  the id the stream announced
 * @param {{kind?: 'new'|'reread', limitMs?: number, onTick?: Function,
 *          isCancelled?: Function, pollEveryMs?: number, sleep?: Function,
 *          now?: Function}} opts
 *   `limitMs` — see lib/preflight.pollLimitMs: a 60-page project outlives a
 *   fixed 40 min, and giving up first reads as a failure.
 * @returns {Promise<{status: 'recovered', project?: object, result?: object, job?: object}
 *   | {status: 'interrupted'|'failed'|'lost', job: object}
 *   | {status: 'waiting'} | {status: 'cancelled'}>}
 *   'waiting' = the limit passed while the server still reported the run as running.
 */
export async function waitForExtraction(recoveryId, {
  kind = 'new', limitMs, onTick, isCancelled,
  pollEveryMs = POLL_EVERY_MS, sleep = realSleep, now = () => Date.now(),
} = {}) {
  const started = now();
  const limit = limitMs || DEFAULT_WAIT_MS;
  while (now() - started < limit) {
    if (isCancelled?.()) return { status: 'cancelled' };
    const answer = await fetchExtractionJob(recoveryId);
    const job = answer?.job;
    if (job) {
      if (job.status === 'interrupted' || job.status === 'failed') {
        return { status: job.status, job };
      }
      if (job.status === 'done') {
        if ((job.kind || kind) === 'reread') {
          return job.result && typeof job.result === 'object'
            ? { status: 'recovered', result: job.result, job }
            : { status: 'lost', job };
        }
        // The server marks a new project done only AFTER saving it, and
        // records where; no project_id means the browser was meant to save it.
        if (!job.project_id) return { status: 'lost', job };
        const p = await fetchProject(job.project_id);
        if (isUsableProject(p)) return { status: 'recovered', project: p, job };
        // Not readable this time (a blip) — ask again next tick.
      }
    } else if (answer?.missing && kind !== 'reread') {
      // No job row: a backend from before the job table, or its insert failed
      // (it is best-effort). Fall back to the old signal — the project itself.
      const p = await fetchProject(recoveryId);
      if (isUsableProject(p)) return { status: 'recovered', project: p };
    }
    if (isCancelled?.()) return { status: 'cancelled' };
    onTick?.(Math.round((now() - started) / 1000));
    await sleep(pollEveryMs);
  }
  return { status: 'waiting' };
}

/**
 * Run one reading over the stream; if the connection goes, wait for its end.
 *
 * @param {FormData} body  `files` (+ `rules_override`, `interior_subtype`,
 *   and `reread_of` for a re-read — the server then holds the read instead of
 *   saving a second project)
 * @param {{controller?: AbortController, onEvent?: Function, onHandoff?: Function,
 *          onPollTick?: Function, isCancelled?: Function, kind?: 'new'|'reread',
 *          waitLimitMs?: number, url?: string, idleAbortMs?: number,
 *          hardAbortMs?: number, edgeDeadlineMs?: number, pollEveryMs?: number,
 *          sleep?: Function, now?: Function}} opts
 *   `controller` — the caller's cancel button aborts it (→ reason 'user').
 *   `onEvent` sees every event, heartbeats included.
 *   `onHandoff(reason)` — 'edge_deadline' (we let go), 'stalled' (seven silent
 *   minutes) or 'dropped' (the connection went).
 * @returns {Promise<{status: 'done', result: object, recoveryId: string|null}
 *   | ({recoveryId: string, handoff: string} & ReturnType<waitForExtraction>)>}
 *   'done' carries the result exactly as the stream delivered it — an error
 *   result included; the caller checks `result.status` as before.
 * @throws {ExtractionStopped} user / timeout / network — and stalled when the
 *   run's id never arrived
 * @throws the postSse HTTP error (status + body) when the server refused
 */
export async function runExtraction(body, {
  controller = new AbortController(),
  onEvent, onHandoff, onPollTick, isCancelled,
  kind = 'new', waitLimitMs,
  url = `${API}/extract-interior-stream`,
  idleAbortMs = IDLE_ABORT_MS, hardAbortMs = HARD_ABORT_MS,
  edgeDeadlineMs = EDGE_DEADLINE_MS,
  pollEveryMs, sleep, now,
} = {}) {
  let recoveryId = null;
  let result = null;
  let reason = null;     // why WE aborted: 'stalled' | 'timeout' | 'edge_deadline'
  let idleTimer = null;
  const bumpIdle = () => {
    if (idleTimer) clearTimeout(idleTimer);
    idleTimer = setTimeout(() => { reason = 'stalled'; controller.abort(); }, idleAbortMs);
  };
  const hardTimer = setTimeout(() => { reason = 'timeout'; controller.abort(); }, hardAbortMs);
  const edgeTimer = setTimeout(() => {
    if (recoveryId) { reason = 'edge_deadline'; controller.abort(); }
  }, edgeDeadlineMs);
  bumpIdle();   // armed before the first event arrives

  let handoff = null;
  try {
    await postSse(url, body, {
      signal: controller.signal,
      onEvent: (ev) => {
        bumpIdle();
        if (ev?.event === 'recovery_id' && ev.project_id) recoveryId = ev.project_id;
        if (ev?.event === 'done') result = ev.result;
        onEvent?.(ev);
      },
    });
    if (!result) throw new Error('Extraction stream ended without result');
  } catch (e) {
    if (e?.name === 'AbortError' || controller.signal.aborted) {
      // Our deliberate let-go, or seven silent minutes (not even a heartbeat,
      // which the server sends every 10 s): the CONNECTION is dead, the run
      // most likely is not — and the job record will say if it is. Telling
      // the user to start over here used to buy a second paid run of work
      // the server then finished anyway.
      if ((reason === 'edge_deadline' || reason === 'stalled') && recoveryId) handoff = reason;
      else throw new ExtractionStopped(reason || 'user', e, recoveryId);
    } else if (e?.status) {
      throw e;                       // HTTP refusal: nothing started
    } else if (isConnectionLoss(e)) {
      // Without the id the server never started (it announces the id before
      // any work), so there is nothing running to wait for.
      if (recoveryId) handoff = 'dropped';
      else throw new ExtractionStopped('network', e);
    } else {
      throw e;
    }
  } finally {
    if (idleTimer) clearTimeout(idleTimer);
    clearTimeout(hardTimer);
    clearTimeout(edgeTimer);
  }

  if (!handoff) return { status: 'done', result, recoveryId };
  onHandoff?.(handoff, recoveryId);
  const outcome = await waitForExtraction(recoveryId, {
    kind, limitMs: waitLimitMs, onTick: onPollTick, isCancelled, pollEveryMs, sleep, now,
  });
  return { ...outcome, recoveryId, handoff };
}

/**
 * What to tell the user when a run ends WITHOUT a result to show.
 * `why` is an outcome status ('interrupted' | 'failed' | 'lost' | 'waiting' |
 * 'cancelled') or an ExtractionStopped reason ('stalled' | 'timeout' | 'user' |
 * 'network'). `started` — the server had announced the run (the
 * ExtractionStopped's `recoveryId`), so it keeps reading after a cancel.
 * Returns the i18n key; the text lives in lt.json only.
 *
 * The honest split this module exists for: only 'waiting' — the server still
 * reports the run as running — may say the work continues. Every ending the
 * server reported says the reading stopped and can be started again, and none
 * of them promises anything about money: a run cut off by a restart is not
 * metered at all, and a failed one is metered as failed, so there is nothing
 * true and simple to promise.
 *
 * A CANCEL IS NOT A STOP ON THE SERVER (2026-10-03 review). Closing the stream
 * does not end a reading that has started — the server finishes it in the
 * background: a new project is saved and appears in „Projektai", a re-read is
 * held on its job row. So a new project's cancel after the start says the
 * project will still appear (and not to upload again), and a re-read's cancel
 * says the project is unchanged and the reading will not be written into it
 * (the caller forgets the run, so nothing later merges it).
 */
export function runEndText(kind, why, { started = false } = {}) {
  if (kind === 'reread') return REREAD_TEXT[why] || REREAD_TEXT.failed;
  if (why === 'user') return started ? NEW_TEXT.cancelled : NEW_TEXT.user;
  return NEW_TEXT[why] || NEW_TEXT.failed;
}

const NEW_TEXT = {
  interrupted: 'newProject.errRunInterrupted',
  failed: 'newProject.errRunFailed',
  lost: 'newProject.errRunLost',
  waiting: 'newProject.errStreamLostButRunning',
  // 'cancelled' only happens once the run was handed off — i.e. it had started.
  cancelled: 'newProject.cancelledRunContinues',
  user: 'newProject.abortedByUser',
  stalled: 'newProject.errStalled',
  timeout: 'newProject.errTimeout',
  network: 'newProject.errNetwork',
};

const REREAD_TEXT = {
  interrupted: 'project.reextract.errInterrupted',
  failed: 'project.reextract.errFailed',
  lost: 'project.reextract.errLost',
  // The server still reads; the run id stays remembered and the project page
  // merges the held read when it is next opened (hooks/useHeldReread.js).
  waiting: 'project.reextract.errStillRunning',
  cancelled: 'project.reextract.cancelled',
  user: 'project.reextract.cancelled',
  stalled: 'newProject.errStalled',
  timeout: 'newProject.errTimeout',
  network: 'newProject.errNetwork',
};

/** Every key `runEndText` can return — for the lt.json/en.json presence test. */
export const RUN_END_KEYS = [...new Set([...Object.values(NEW_TEXT), ...Object.values(REREAD_TEXT)])];

/**
 * The one-line progress of a stream, for the compact re-read card. A reducer
 * over the same events NewProject's full progress screen reads; the keys are
 * the existing `upload.stream.*` strings.
 *
 * @param {object|null} state  previous state (null to start)
 * @param {object} ev          one stream event
 */
export function reduceStreamProgress(state, ev) {
  const s = state || { step: 'reading', pageCount: 0, rooms: 0, done: 0, total: 0 };
  switch (ev?.event) {
    case 'started':
    case 'validation_warning':
      return { ...s, pageCount: Number(ev.page_count) || s.pageCount };
    case 'pass1_started':
      return { ...s, step: 'recognizing' };
    case 'pass1_completed':
      return { ...s, step: 'foundRooms', rooms: (ev.patalpos || []).length };
    case 'zoom_started':
      return { ...s, step: 'refining', total: Number(ev.total) || 0, done: 0 };
    case 'zoom_room_completed':
      return { ...s, step: 'refining', done: Number(ev.idx) || s.done + 1 };
    case 'post_processing':
      return { ...s, step: 'summing' };
    default:
      return s;
  }
}

/** `[i18nKey, params]` for a progress state from `reduceStreamProgress`. */
export function progressLine(state) {
  const s = state || { step: 'reading' };
  switch (s.step) {
    case 'recognizing': return ['upload.stream.recognizing', {}];
    case 'foundRooms': return ['upload.stream.foundRooms', { count: s.rooms }];
    case 'refining':
      return s.total
        ? ['upload.stream.refiningProgress', { done: s.done, total: s.total }]
        : ['upload.stream.refiningRooms', {}];
    case 'summing': return ['upload.stream.summing', {}];
    case 'finishing': return ['upload.stream.finishingOnServer', {}];
    default:
      return s.pageCount
        ? ['upload.stream.readingPages', { count: s.pageCount }]
        : ['upload.stream.reading', {}];
  }
}
