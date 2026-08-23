/**
 * preflight — the five-second read of an uploaded PDF, before the long spend.
 *
 * `POST /api/pdf-preflight` costs nothing (no Vision, text layer only) and
 * answers three questions the contractor otherwise pays 25 minutes to learn:
 * how many pages, roughly how long, and whether this file looks like the kind
 * of drawing the pipeline can measure at all.
 *
 * THE VERDICT IS A GUESS. It is read off sheet titles and vector density, not
 * off an analysis, so every string this module selects is phrased "atrodo,
 * kad…" and the user can always continue. The one exception is `hard_block`,
 * which is not a guess: past 100 pages the pipeline truncates the document,
 * and analysing the wrong 100 pages of a 139-page set is worse than being told
 * to upload the interior part on its own.
 *
 * The copy itself lives in i18n (newProject.preflight.*); this module only
 * decides WHICH string, so the mapping is unit-testable without a DOM.
 */

// Relative, not the '@/lib/...' alias: this module is covered by `node --test`,
// which resolves no Vite aliases (see recomputeApi.js for the same reason).
import { API_BASE as API } from './apiBase.js';

export const PREFLIGHT_VERDICTS = [
  'interior_plan',
  'table_only',
  'photo_or_scan',
  'facade_or_site',
  'mixed_bundle',
  'unknown',
];

/** Verdicts that mean "this probably will not find rooms". */
const CAUTION_VERDICTS = new Set([
  'table_only', 'photo_or_scan', 'facade_or_site', 'mixed_bundle',
]);

/**
 * The client's recovery poller ceiling when we know nothing about the file.
 * Kept at the historical 40 min so behaviour is unchanged for every upload
 * that never got a preflight (offline, endpoint down, older session).
 */
export const DEFAULT_POLL_MINUTES = 40;

/**
 * Poller ceiling in ms for a run, from its preflight.
 *
 * Why this matters: a 60-page project runs past 40 minutes, and the browser
 * used to give up and tell the user it failed while the server was still
 * working and about to save the project. The backend already told us the
 * expected tier — use it instead of a fixed number.
 *
 * @param {{est_minutes_max?: number}|null|undefined} pre
 * @returns {number} milliseconds
 */
export function pollLimitMs(pre) {
  const fromPre = Number(pre?.est_minutes_max) || 0;
  return Math.max(DEFAULT_POLL_MINUTES, fromPre) * 60 * 1000;
}

/**
 * Normalize the endpoint payload into what the card renders.
 *
 * Pure and total: any shape (null, an error object, a payload from a future
 * backend with a verdict we do not know) resolves to something renderable,
 * because a broken preflight must never stop an upload.
 *
 * @param {object|null} pre
 * @returns {{
 *   tone: 'ok'|'neutral'|'caution'|'blocked',
 *   verdict: string,
 *   blocked: boolean,
 *   needsDecision: boolean,
 *   pageCount: number,
 *   estMinutes: string,
 *   interiorPages: number,
 *   reason: string|null,
 *   warnings: string[],
 * }|null}
 */
export function preflightCard(pre) {
  if (!pre || typeof pre !== 'object') return null;
  const pageCount = Number(pre.page_count) || 0;
  if (!pageCount) return null;   // unreadable probe — say nothing rather than guess

  const verdict = PREFLIGHT_VERDICTS.includes(pre.verdict) ? pre.verdict : 'unknown';
  const blocked = pre.hard_block === true;

  let tone = 'neutral';
  if (blocked) tone = 'blocked';
  else if (CAUTION_VERDICTS.has(verdict)) tone = 'caution';
  else if (verdict === 'interior_plan') tone = 'ok';

  return {
    tone,
    verdict,
    blocked,
    // An 'ok' verdict is information, not a question — showing "Tęsti vis
    // tiek?" on a perfectly good interior project trains people to click
    // through the card without reading it.
    needsDecision: tone !== 'ok',
    pageCount,
    estMinutes: typeof pre.est_minutes === 'string' ? pre.est_minutes : '',
    interiorPages: Number(pre.interior_pages_estimate) || 0,
    reason: blocked ? (pre.hard_block_reason || null) : null,
    warnings: Array.isArray(pre.warnings) ? pre.warnings.filter(Boolean) : [],
  };
}

/** i18n key for a verdict's one-line plain-Lithuanian explanation. */
export function verdictKey(verdict) {
  const v = PREFLIGHT_VERDICTS.includes(verdict) ? verdict : 'unknown';
  return `newProject.preflight.verdict.${v}`;
}

/**
 * Run the preflight. Never throws and never rejects — a failed probe means the
 * card does not render, not that the user cannot upload.
 *
 * @param {File} file
 * @param {{signal?: AbortSignal}} [opts]
 * @returns {Promise<object|null>}
 */
export async function fetchPreflight(file, { signal } = {}) {
  if (!file) return null;
  const fd = new FormData();
  fd.append('file', file);
  try {
    const res = await fetch(`${API}/api/pdf-preflight`, {
      method: 'POST', credentials: 'include', body: fd, signal,
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}
