/**
 * scaleOverview — one row per sheet for the „Masteliai" panel (Togal-v2 W6, 2026-10-16; Togal research §2).
 *
 * Togal predicts a scale per sheet, asks a person to confirm it and refuses to apply one scale to a set
 * blindly. The panel lists every sheet with the scale in force, where it comes from in his words, the scale
 * the sheet writes when that differs, how many of the drawing's dimension strings the lane read on it, and a
 * state: nenustatytas · spėjamas · nuskaitytas · patvirtintas (lib/scaleProvenance). Pure — the panel stays dumb and
 * puts `desc` into words with i18n.
 *
 * Inputs are what the viewer already holds: the project (for the lane and the rooms) and the live durable map
 * (the viewer owns it between saves).
 */
import { laneScalesOf, staleConfirmation } from './durableScale.js';
import { effectivePageScales, pageScaleIn } from './pageScales.js';
import { blankReasonOf, describeScale } from './scaleProvenance.js';

const roomsOf = (project) => project?.v8_rooms || project?.patalpos || [];

/**
 * `{page: [{text, value_m, line_pct, ilgis_pt?}]}` — the dimension strings the geometry lane added into the rooms' walls
 * (`room._sienos[].eilutes[]`, each with its own sheet and its drawn dimension line in display-space page
 * fractions; `ilgis_pt` = the drawn line's length less its stroke, stored since 2026-10-16). Deduplicated: two rooms sharing a wall carry the same string. The pair lane's
 * `_perimetras_matmenys` keeps only text boxes, not lines, so it is not used here.
 */
export function dimensionStringsOf(project) {
  const out = {};
  const seen = new Set();
  for (const r of roomsOf(project)) {
    for (const wall of r?._sienos || []) {
      for (const e of wall?.eilutes || []) {
        const page = Number(e?.page);
        const value = Number(e?.value_m);
        const line = e?.line_pct;
        if (!(page > 0) || !(value > 0) || !Array.isArray(line) || line.length !== 2) continue;
        const key = `${page}|${e.text}|${line.flat().map((n) => Number(n).toFixed(4)).join(',')}`;
        if (seen.has(key)) continue;
        seen.add(key);
        const ilgis = Number(e?.ilgis_pt);
        (out[page] ||= []).push({ text: String(e.text ?? ''), value_m: value, line_pct: line, ...(ilgis > 0 ? { ilgis_pt: ilgis } : {}) });
      }
    }
  }
  return out;
}

const ratioOf = (scale) => {
  const mpp = Number(scale?.metersPerPointX) || 0;
  return mpp > 0 ? Math.round((mpp * 72) / 0.0254) : 0;
};
const labelOf = (scale) => scale?.label || (ratioOf(scale) ? `1:${ratioOf(scale)}` : '');
const prefixOf = (scale) => (scale?.source === 'auto' ? '~' : '');

/** The pages to list: every sheet of the PDF when known, else every page any source mentions. */
function pagesOf(project, pageCount, scales) {
  const n = Number(pageCount);
  if (n > 0) return Array.from({ length: n }, (_, i) => i + 1);
  const set = new Set(Object.keys(scales).map(Number));
  for (const p of project?.puslapiai || []) {
    const nr = Number(p?.puslapio_nr ?? p?.nr ?? p?.page);
    if (nr > 0) set.add(nr);
  }
  return [...set].filter((p) => p > 0).sort((a, b) => a - b);
}

/**
 * `{rows, groups}`.
 *   rows[i]  = {page, state, desc, label, ratio, written, strings, sample, canConfirm, stale}
 *     label    '1:115' / '~1:50' / '' — the scale in force;
 *     desc     lib/scaleProvenance.describeScale — where it comes from, as data (the panel words it);
 *     written  the scale the sheet writes when the strings measure another ('1:100'), else '';
 *     strings  how many dimension strings the lane read on this sheet; sample = the first few, as written;
 *     canConfirm  a lane scale he has not confirmed yet (read from the drawing or a proposal);
 *     stale    {confirmed, now} when he confirmed a ratio the lane no longer measures there.
 *   groups   = [{ratio, label, pages}] — two or more unconfirmed sheets sharing one lane ratio, for
 *              „Patvirtinti visus su tuo pačiu masteliu".
 */
export function buildScaleOverview(project, { pageCount = null, durable = project?.pageScalesDurable, sampleSize = 4 } = {}) {
  const scales = effectivePageScales(project, durable || {});
  const lane = laneScalesOf(project);
  const strings = dimensionStringsOf(project);
  const rows = pagesOf(project, pageCount, scales).map((page) => {
    const scale = pageScaleIn(scales, page);
    const laneScale = pageScaleIn(lane, page);
    const desc = describeScale(scale, { blankReason: blankReasonOf(project, page) });
    const { state } = desc;
    const own = strings[page] || [];
    const stale = staleConfirmation(pageScaleIn(durable || {}, page), laneScale);
    return {
      page,
      state,
      label: state === 'nenustatytas' ? '' : `${prefixOf(scale)}${labelOf(scale)}`,
      ratio: ratioOf(scale),
      desc,
      written: (scale?.uzrasyta || []).filter((n) => Number(n) > 0).map((n) => `1:${n}`).join(', '),
      strings: own.length,
      sample: own.slice(0, sampleSize).map((s) => s.text),
      canConfirm: (state === 'spejamas' || state === 'nuskaitytas') && scale?.source === 'plan',
      stale,
    };
  });
  const byRatio = new Map();
  for (const r of rows) {
    if (!r.canConfirm) continue;
    if (!byRatio.has(r.ratio)) byRatio.set(r.ratio, []);
    byRatio.get(r.ratio).push(r.page);
  }
  const groups = [...byRatio.entries()]
    .filter(([, pages]) => pages.length >= 2)
    .map(([ratio, pages]) => ({ ratio, label: `1:${ratio}`, pages }));
  return { rows, groups };
}

/** Counts per state, for the panel's header line. */
export function overviewCounts(rows) {
  const out = { nenustatytas: 0, spejamas: 0, nuskaitytas: 0, patvirtintas: 0 };
  for (const r of rows || []) out[r.state] = (out[r.state] || 0) + 1;
  return out;
}

/** Lithuanian count agreement: 1 matmuo · 2–9 matmenys · 10–20 and …0 matmenų (21 matmuo, 22 matmenys). */
export function plural(n, one, few, many) {
  const d = n % 10;
  const t = n % 100;
  if (d === 1 && t !== 11) return one;
  if (d >= 2 && (t < 10 || t > 20)) return few;
  return many;
}
