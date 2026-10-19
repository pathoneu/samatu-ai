// runTeaching — what the „Kol skaitoma" panel says while the paid read runs (Pathon v3 W5-C, C1 / coverage
// #34), and whether the „Ką programa perskaito" card is still due before the first run (C2 / #33).
//
// Everything comes from the stages the stream already sends (lib/extractionRun → NewProject's streamPhase):
// no new call, nothing paid. Pure — the panel (components/upload/RunTeaching.jsx) turns the keys into words.

// the stream's phases, in order; „finishing" is the same last step after the socket was handed off
const STAGES = ['rendering', 'pass1', 'zoom', 'post'];
const STAGE_OF = { rendering: 'rendering', pass1: 'pass1', zoom: 'zoom', post: 'post', finishing: 'post' };

// the usual length of a full read (founder brief: 25–28 min); the preflight's own estimate wins when it has one
export const USUAL_MINUTES = '25–28';

/**
 * phase    NewProject's streamPhase ('rendering' | 'pass1' | 'zoom' | 'post' | 'finishing' | null)
 * progress { zoomDone, zoomTotal, pageCount, rooms }
 * elapsed  seconds since the start
 * started  the server announced the run (its id came) — from then on the window may be closed safely
 * estMinutes the preflight's range („15–25"), or ''
 * → { stage, stageKey, stageParams, step, steps, minutes, estimate, canLeave }
 */
export function runTeachingFor({ phase = null, progress = {}, elapsed = 0, started = false, estMinutes = '' } = {}) {
  const stage = STAGE_OF[phase] || 'rendering';
  const params = {};
  if (stage === 'rendering' && progress?.pageCount) params.count = progress.pageCount;
  if (stage === 'pass1' && progress?.rooms?.length) params.count = progress.rooms.length;
  if (stage === 'zoom' && progress?.zoomTotal) { params.done = progress.zoomDone || 0; params.total = progress.zoomTotal; }
  let stageKey = `stage.${stage}`;
  if (stage === 'rendering' && params.count) stageKey = 'stage.renderingPages';
  if (stage === 'pass1' && params.count) stageKey = 'stage.pass1Rooms';
  if (stage === 'zoom' && params.total) stageKey = 'stage.zoomProgress';
  if (phase === 'finishing') stageKey = 'stage.finishing';
  return {
    stage,                                  // the stage's name key (runTeaching.name.<stage>)
    stageKey,
    stageParams: params,
    step: STAGES.indexOf(stage) + 1,
    steps: STAGES.length,
    minutes: Math.max(0, Math.floor((Number(elapsed) || 0) / 60)),
    // the preflight says „iki 30 min" — the panel adds the unit itself
    estimate: String(estMinutes || '').replace(/\s*min\.?\s*$/i, '').trim() || USUAL_MINUTES,
    canLeave: Boolean(started),
  };
}

// ── C2: the card before the first run ─────────────────────────────────────────────────────────────────
export const READ_SCOPE_KEY = 'samatu_read_scope_seen';

/** The card is due until he closes it or his first read starts. Storage may be missing or throw. */
export function readScopeDue(storage) {
  try {
    return storage?.getItem?.(READ_SCOPE_KEY) !== '1';
  } catch {
    return true;
  }
}

export function markReadScopeSeen(storage) {
  try {
    storage?.setItem?.(READ_SCOPE_KEY, '1');
  } catch {
    // a private window: the card simply shows again next time
  }
}
