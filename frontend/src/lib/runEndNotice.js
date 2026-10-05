/**
 * Which endings of a NEW project's reading are news, not errors (2026-10-05).
 *
 * Two endings mean the server is still reading and saves the project itself
 * (backend `_drain_gen`): the connection dropped while it reads
 * (`errStreamLostButRunning`), and his cancel after the reading had started
 * (`cancelledRunContinues`). Both used to sit in the red error box above the
 * start form — „nekartokite įkėlimo" in red, over the very button that uploads
 * again. They are a neutral notice with the way to the projects list
 * (NewProject.jsx); every other ending is an error and stays red.
 */

import { runEndText } from './extractionRun.js';

/** The texts that say the reading goes on and the project will appear in „Projektai". */
export const CONTINUING_RUN_KEYS = Object.freeze([
  'newProject.errStreamLostButRunning',
  'newProject.cancelledRunContinues',
]);

/**
 * `{ key, tone }` for a new project's ending: the i18n key `runEndText` gives it,
 * and 'notice' when the reading continues on the server, else 'error'.
 */
export function newRunEnding(why, { started = false } = {}) {
  const key = runEndText('new', why, { started });
  return { key, tone: CONTINUING_RUN_KEYS.includes(key) ? 'notice' : 'error' };
}
