/**
 * scaleLabel — what the viewer's status bar, its tooltip and the scale toast say about a sheet's scale.
 *
 * A PageScale stores metres of reality per PDF point; 1 pt = 1/72 inch of paper, so the 1:N ratio is
 * mpp / (0.0254 / 72). Sources (`source`): 'plan' (the drawing — lib/durableScale.laneScalesOf, with the
 * backend's `provenance` when the geometry lane stored one), 'auto' (the rooms' areas), 'user' (his two clicks
 * or a typed ratio), 'lane-confirmed' (a lane scale he confirmed).
 *
 * v4 (2026-10-24): the words are no longer built here from `kilme` — lib/scaleProvenance is the one place that
 * puts a scale into words, from the backend's own provenance; every text function takes i18n's `t`. „Spėjamas"
 * is said only when the backend says low confidence or there is no backend source. Pure: no React.
 */
import {
  describeScale, provenanceExplanation, provenancePhrase, scaleProvenanceLine, scaleStateWord,
} from './scaleProvenance.js';

/**
 * The scale's state:
 *   'nenustatytas'  no scale in force;
 *   'spejamas'      a proposal — the backend said low confidence, no backend source (old blobs), or the areas;
 *   'nuskaitytas'   read from the drawing (backend source with high / medium confidence), not yet confirmed;
 *   'patvirtintas'  his: two clicks on a known length, or a lane scale he confirmed (source 'lane-confirmed').
 */
export function scaleState(pageScale) {
  return describeScale(pageScale).state;
}

/** The state in a word, for chips and the overview. */
export function scaleStateText(state, t) {
  return scaleStateWord(state, t);
}

/** The scale's source in one short phrase — the overview's „Šaltinis" column, capitalised. */
export function scaleSourceText(pageScale, t) {
  const desc = describeScale(pageScale);
  if (desc.state === 'nenustatytas') return t('project.scaleProvenance.overview.sourceNone');
  const p = provenancePhrase(desc, t);
  return p.charAt(0).toUpperCase() + p.slice(1);
}

/** The status bar's one line: „Mastelis 1:75 — iš plano matmenų (139 skaičiai)". */
export function scaleStatusText(pageScale, t, { blankReason = '', clickable = true } = {}) {
  if (!pageScale?.calibrated && !blankReason && clickable) return t('project.scaleProvenance.status.noneClick');
  return scaleProvenanceLine(pageScale, t, { blankReason });
}

/** Where the scale comes from and what that means — the chip card's text (its own buttons say what to do). */
export function scaleExplanation(pageScale, t, { blankReason = '' } = {}) {
  return provenanceExplanation(describeScale(pageScale, { blankReason }), t);
}

/** The status bar's tooltip: the explanation, plus how to set another scale. */
export function scaleStatusTitle(pageScale, t, opts = {}) {
  return `${scaleExplanation(pageScale, t, opts)} ${t('project.scaleProvenance.explain.clickToSet')}`;
}
