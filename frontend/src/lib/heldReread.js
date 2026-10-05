/**
 * heldReread — a paid re-read that outlives the page it was started on
 * (2026-10-03 review of the extraction-jobs round).
 *
 * When a re-read's connection goes, the server finishes the reading and HOLDS
 * it on the run's job row for HELD_RESULT_DAYS (backend/db.py). The waiting
 * re-read card takes it from there — but only while the page lives: a reload
 * during the wait threw the paid read away, because the card sits inside the
 * Prielaidos drawer and nothing else knew the run existed. So:
 *
 *   • the card REMEMBERS the run id per project (localStorage) the moment the
 *     server announces it — earlier than the hand-off, because a reload in the
 *     middle of the stream drops the connection just the same and the server
 *     holds that read too;
 *   • the project page (hooks/useHeldReread.js) asks for that run on open and
 *     merges a held read through the SAME path the card uses
 *     (lib/rereadApply.js), once: the merged project carries the run id as
 *     `_reread_run_id`, and a run the project already carries is never merged
 *     again;
 *   • the id is FORGOTTEN once the run's ending has been handled — merged,
 *     told (interrupted / failed / lost), or cancelled by the user (his cancel
 *     promises the reading will not be written into the project). The endings
 *     that keep it: "still running when the wait gave up", and an ending the
 *     project page found after he had left it — the next open picks the read
 *     up, or tells how it ended. A run done with nothing held is told only
 *     after a grace (`lostRunUnhandled`): another tab may be merging it.
 *
 * Also the in-flight registry the card used to keep to itself: one re-read
 * per project per page load, whether the card started it or the page resumed
 * it, so the card shows the running one instead of offering a second paid one.
 *
 * Pure apart from storage, which is injectable. Relative imports only: this
 * module runs under `node --test`.
 */

const KEY_PREFIX = 'samatu_reread_run:';

function defaultStore() {
  try {
    return globalThis.localStorage || null;
  } catch {
    return null;   // access itself can throw (blocked site data)
  }
}

/** Remember the run reading `projectId` again. Never throws. */
export function rememberRereadRun(projectId, runId, store = defaultStore()) {
  if (!projectId || !runId || !store) return;
  try { store.setItem(KEY_PREFIX + projectId, String(runId)); } catch { /* best-effort */ }
}

/** The remembered run id for `projectId`, or null. Never throws. */
export function recallRereadRun(projectId, store = defaultStore()) {
  if (!projectId || !store) return null;
  try { return store.getItem(KEY_PREFIX + projectId) || null; } catch { return null; }
}

/**
 * Forget the remembered run. With `runId`, only when it is still that run —
 * the ending of an older run must not forget a newer one. Never throws.
 */
export function forgetRereadRun(projectId, runId = null, store = defaultStore()) {
  if (!projectId || !store) return;
  try {
    const key = KEY_PREFIX + projectId;
    if (runId && store.getItem(key) !== String(runId)) return;
    store.removeItem(key);
  } catch { /* best-effort */ }
}

// ── one re-read per project per page load ───────────────────────────────────

const inflight = new Map();   // projectId → Promise<{error: string|null}>

/** The re-read running for `projectId` on this page load, or undefined. */
export function rereadInFlight(projectId) {
  return inflight.get(projectId);
}

/**
 * Register a running re-read (`promise` resolves to `{error}`); it leaves the
 * registry when it settles. Returns the same promise.
 */
export function trackReread(projectId, promise) {
  inflight.set(projectId, promise);
  const clear = () => { if (inflight.get(projectId) === promise) inflight.delete(projectId); };
  promise.then(clear, clear);
  return promise;
}

// ── what to do with a remembered run on project open ────────────────────────

/**
 * The first look at a remembered run when its project opens.
 *
 * @param {string|null} runId    the remembered id
 * @param {object|null} project  the stored project
 * @param {{job: object}|{missing: true}|null} answer  lib/extractionRun.fetchExtractionJob
 * @returns {{do: 'nothing'} | {do: 'forget'} | {do: 'wait'}
 *   | {do: 'apply', result: object}
 *   | {do: 'tell', why: 'interrupted'|'failed'|'lost', afterGrace?: true}}
 *   'forget' = silently (already merged, or not this user's / this project's run);
 *   'tell'   = forget AND say how it ended (lib/extractionRun.runEndText);
 *   `afterGrace` = only if, after LOST_GRACE_MS, `lostRunUnhandled` still holds.
 */
export function heldRereadAction(runId, project, answer) {
  if (!runId) return { do: 'nothing' };
  if (project && project._reread_run_id === runId) return { do: 'forget' };
  if (!answer) return { do: 'wait' };               // no answer this time
  if (answer.missing) return { do: 'forget' };      // not this user's run (or none)
  const job = answer.job || {};
  if ((job.kind && job.kind !== 'reread')
      || (job.project_id && project?.id && job.project_id !== project.id)) {
    return { do: 'forget' };
  }
  switch (job.status) {
    case 'done':
      // Nothing held: delivered over a stream (maybe to another tab that is
      // merging it right now — see heldRereadOutcomeAction), or the hold expired.
      return job.result && typeof job.result === 'object'
        ? { do: 'apply', result: job.result }
        : { do: 'tell', why: 'lost', afterGrace: true };
    case 'interrupted':
    case 'failed':
      return { do: 'tell', why: job.status };
    default:
      return { do: 'wait' };                       // running
  }
}

/**
 * How a wait for a remembered run ended (lib/extractionRun.waitForExtraction
 * with kind 'reread'). 'keep' = still running when the wait gave up, or the
 * page went away: the id stays for the next open.
 *
 * A run that ended 'lost' WHILE this page waited is told only `afterGrace`.
 * The server held nothing because it delivered the read over a stream that
 * was still open — usually another tab of this browser, whose card merges it
 * (stamping the project) and forgets the run, then tells him how it went.
 * Saying „rezultatas neatėjo, pabandykite dar kartą" here at once would send
 * him to buy a second read of something being merged; after LOST_GRACE_MS,
 * `lostRunUnhandled` says whether anyone handled it.
 */
export function heldRereadOutcomeAction(outcome) {
  switch (outcome?.status) {
    case 'recovered':
      return outcome.result && typeof outcome.result === 'object'
        ? { do: 'apply', result: outcome.result }
        : { do: 'tell', why: 'lost', afterGrace: true };
    case 'lost':
      return { do: 'tell', why: 'lost', afterGrace: true };
    case 'interrupted':
    case 'failed':
      return { do: 'tell', why: outcome.status };
    default:
      return { do: 'keep' };
  }
}

/** How long a 'lost' run waits for the tab that had its stream (a merge's rebuild is a few seconds). */
export const LOST_GRACE_MS = 15_000;

/**
 * After the grace: was the 'lost' run left unhandled? Handled = the card that
 * had the stream forgot the remembered id (it merged, or told its own ending),
 * or the stored project already carries the run (merged).
 */
export function lostRunUnhandled(runId, { remembered, project } = {}) {
  return !!runId && remembered === runId && project?._reread_run_id !== runId;
}

/**
 * Should the card keep the remembered run after its own read ended?
 * Only when the server still reported it running when the wait gave up
 * ('waiting') — every other ending was handled (merged or told) on the card.
 */
export function keepRunAfterCardEnding(status) {
  return status === 'waiting';
}

const realSleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

/**
 * The project page's handling of one remembered run, start to end — the body
 * of hooks/useHeldReread.js with every effect injected, so node:test drives
 * the real flow (the hook only wires the store, the network, toasts and t()).
 *
 * @param {string} projectId
 * @param {string} runId  the remembered id
 * @param {{getProject: Function, fetchJob: Function, wait: Function, apply: Function,
 *          isGone?: Function, onWaiting?: Function, onApplied?: Function,
 *          sleep?: Function, store?: object}} deps
 *   `getProject(id)` — lib/projectStore.getProject;
 *   `fetchJob(runId)` — lib/extractionRun.fetchExtractionJob;
 *   `wait(runId, {isCancelled})` — lib/extractionRun.waitForExtraction, kind 'reread';
 *   `apply(projectId, result, {runId})` — lib/rereadApply.applyRereadResult;
 *   `isGone()` — the page was left; `onWaiting()` — the server still reads;
 *   `onApplied(project, {merged})` — show `project`, merged here or by another tab;
 *   `store` — Storage-like (default: localStorage).
 * @returns {Promise<{told: null|'interrupted'|'failed'|'lost'|'merge', cause?: Error}>}
 *   what the page must say: how the run ended (lib/extractionRun.runEndText),
 *   'merge' when merging the held read threw. null = nothing to say.
 */
export async function settleHeldReread(projectId, runId, {
  getProject, fetchJob, wait, apply,
  isGone = () => false, onWaiting, onApplied, sleep = realSleep, store = defaultStore(),
}) {
  const stored = getProject(projectId);
  let action = stored?._reread_run_id === runId
    ? { do: 'forget' }                              // merged already: no question asked
    : heldRereadAction(runId, stored, await fetchJob(runId));
  if (action.do === 'wait') {
    if (!isGone()) onWaiting?.();
    action = heldRereadOutcomeAction(await wait(runId, { isCancelled: isGone }));
  }
  if (action.do === 'apply') {
    let merged;
    try {
      merged = await apply(projectId, action.result, { runId });
    } catch (cause) {
      // Not retried on the next open: a held read that cannot be merged
      // would fail the same way every time.
      forgetRereadRun(projectId, runId, store);
      return { told: 'merge', cause };
    }
    // null: merged already, or being merged by the card right now (both
    // forget the run themselves), or no project to merge into (kept: the
    // next open tries again).
    if (merged) {
      forgetRereadRun(projectId, runId, store);
      if (!isGone()) onApplied?.(merged, { merged: true });
    }
    return { told: null };
  }
  if (action.do === 'tell' && action.afterGrace) {
    await sleep(LOST_GRACE_MS);
    const latest = getProject(projectId);
    if (!lostRunUnhandled(runId, { remembered: recallRereadRun(projectId, store), project: latest })) {
      forgetRereadRun(projectId, runId, store);
      // Another tab merged it: show that instead of this page's older copy.
      if (!isGone() && latest?._reread_run_id === runId) onApplied?.(latest, { merged: false });
      return { told: null };
    }
  }
  if (action.do === 'tell') {
    // Nobody on the page to read it: keep the run — the next open tells it.
    if (isGone()) return { told: null };
    forgetRereadRun(projectId, runId, store);
    return { told: action.why };
  }
  if (action.do === 'forget') forgetRereadRun(projectId, runId, store);
  return { told: null };                            // 'keep' / 'nothing'
}
