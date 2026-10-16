// „Rasti panašius" (Togal's AI Image Search → count), the pure part: the box the
// person drags, filtering the backend's candidates by the slider, grouping per
// sheet, the honesty rules and turning what is left into count marks.
//
// Geometry is in TOP-LEFT mediabox PDF points, the measurement space
// (viewerEngine/embedPdfAdapter). The backend (POST /api/cv/find-symbol) answers
// in the same points. Scores are a SHAPE agreement (chamfer), not a probability.
// Measured 2026-10-16 on objektas_h page 1, the entrance door swing boxed: the
// real twins scored 0.87–0.90, the first wrong hits 0.850–0.856, and below 0.80
// almost everything is text, dimension ticks and wall corners. So the slider
// starts at 0.87, cannot go below 0.80, and the person moves it — one box on one
// sheet, not a calibration: another symbol will sit elsewhere.

import { makeMeasurement } from './measurements.js';

export const SYMBOL_SOURCE = 'symbol_search';
// Same vocabulary as the hand-placed count marks ('green'); lib/confidence maps it to geltona.
export const AI_CONFIDENCE = 'yellow';
export const DEFAULT_THRESHOLD = 0.87;
// The backend returns everything above this; the slider cannot go lower.
export const MIN_THRESHOLD = 0.80;
// Honesty rules: a sheet with more hits than this, or more than RATIO × the
// median of the other sheets, gets a warning instead of a silent add.
export const UNUSUAL_COUNT = 60;
export const UNUSUAL_RATIO = 3;
// „Ieškoti visuose lapuose": at most this many sheets and this long, then stop and say so.
export const MAX_PAGES_PER_RUN = 12;
export const MAX_RUN_MS = 90_000;

/** Two drag corners → [x0, y0, x1, y1]; null when the box is too small to be a symbol. */
export function boxFromDrag(a, b, minSidePt = 4) {
  if (!a || !b) return null;
  const x0 = Math.min(a.x, b.x);
  const y0 = Math.min(a.y, b.y);
  const x1 = Math.max(a.x, b.x);
  const y1 = Math.max(a.y, b.y);
  if (x1 - x0 < minSidePt || y1 - y0 < minSidePt) return null;
  return [x0, y0, x1, y1].map((v) => Math.round(v * 100) / 100);
}

/** Backend candidates for one sheet → stable ids, page numbers (1-based). */
export function normalizeCandidates(pageNr, candidates = []) {
  return candidates.map((c, i) => ({
    id: `${pageNr}:${i}`,
    page: pageNr,
    x: c.x,
    y: c.y,
    box: c.box_pt,
    score: Number(c.score) || 0,
    isSource: !!c.is_source,
  }));
}

/** The candidates the person sees: above the slider and not removed. Best first. */
export function visibleCandidates(all, threshold, removed = new Set()) {
  return all
    .filter((c) => c.score >= threshold && !removed.has(c.id))
    .sort((a, b) => b.score - a.score);
}

/** Lithuanian decimal comma, two places. */
export function formatScore(s) {
  return (Math.round(s * 100) / 100).toFixed(2).replace('.', ',');
}

/** „rasta 14, rodoma 9 nuo 0,72" — found = above the backend floor, minus removed. */
export function countLabel({ found, shown, threshold }) {
  return `rasta ${found}, rodoma ${shown} nuo ${formatScore(threshold)}`;
}

/** Visible candidates grouped per sheet, sheets in order: [{page, items}]. */
export function groupByPage(items) {
  const by = new Map();
  for (const c of items) {
    if (!by.has(c.page)) by.set(c.page, []);
    by.get(c.page).push(c);
  }
  return [...by.entries()].sort((a, b) => a[0] - b[0]).map(([page, list]) => ({ page, items: list }));
}

function median(values) {
  if (!values.length) return 0;
  const s = [...values].sort((a, b) => a - b);
  const m = Math.floor(s.length / 2);
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}

/**
 * Sheets whose hit count is suspicious: above UNUSUAL_COUNT, or above
 * UNUSUAL_RATIO × the median of the sheets that have any hits (the ratio rule
 * needs at least three such sheets — with one or two there is no "usual").
 * Sheets with no hits are left out of the median: a set where most sheets are
 * sections would otherwise make every real hit look unusual.
 * `counts` = {[page]: n}. Returns {[page]: reason}.
 */
export function unusualPages(counts) {
  const entries = Object.entries(counts).map(([p, n]) => [Number(p), Number(n) || 0]);
  const nonZero = entries.filter(([, n]) => n > 0).map(([, n]) => n);
  const med = nonZero.length >= 3 ? median(nonZero) : null;
  const out = {};
  for (const [page, n] of entries) {
    if (n > UNUSUAL_COUNT) out[page] = 'many';
    else if (med != null && n > UNUSUAL_RATIO * med) out[page] = 'ratio';
  }
  return out;
}

export const UNUSUAL_WARNING = 'Rasta neįprastai daug — patikrinkite, ar simbolis nėra legendoje ar rašte';

/** Hits per sheet among the visible candidates. */
export function countsByPage(items) {
  const out = {};
  for (const c of items) out[c.page] = (out[c.page] || 0) + 1;
  return out;
}

/**
 * Which sheets one „Ieškoti visuose lapuose" run searches: the template's sheet
 * first, then the others in order, at most `maxPages`. Returns {pages, skipped}.
 */
export function planAllPages(totalPages, templatePage, { maxPages = MAX_PAGES_PER_RUN, alreadyDone = [] } = {}) {
  const done = new Set(alreadyDone);
  const order = [templatePage, ...Array.from({ length: totalPages }, (_, i) => i + 1).filter((p) => p !== templatePage)]
    .filter((p) => p >= 1 && p <= totalPages && !done.has(p));
  return { pages: order.slice(0, maxPages), skipped: order.slice(maxPages) };
}

/** „13–16" style list of page numbers for the „praleista" sentence. */
export function pageRanges(pages) {
  const s = [...new Set(pages)].sort((a, b) => a - b);
  const out = [];
  for (let i = 0; i < s.length; i += 1) {
    let j = i;
    while (j + 1 < s.length && s[j + 1] === s[j] + 1) j += 1;
    out.push(i === j ? `${s[i]}` : `${s[i]}–${s[j]}`);
    i = j;
  }
  return out.join(', ');
}

/** The count marks the kept candidates become — same shape as hand-placed ones, flagged as AI-found. */
export function candidatesToMeasurements(items, type) {
  return items.map((c) => makeMeasurement('count', c.page, [{ x: c.x, y: c.y }], {
    typeId: type.id,
    color: type.color,
    confidence: AI_CONFIDENCE,
    source: SYMBOL_SOURCE,
    score: Math.round(c.score * 1000) / 1000,
    box: c.box,
  }));
}

/** Training-data class name from a count type (backend KLASS_PATTERN ^[a-z0-9_-]{1,40}$). */
export function klassFor(type) {
  const id = String(type?.id || '').toLowerCase().replace(/[^a-z0-9_-]+/g, '-').replace(/^-+|-+$/g, '');
  return (id || 'simbolis').slice(0, 40);
}

/**
 * What goes to /api/cv/record-decision when the person adds: every candidate
 * they kept is an accept, every one they removed by hand is a reject. Ones only
 * hidden by the slider are not judged and are not sent.
 */
export function decisionsToRecord(all, threshold, removed) {
  const out = [];
  for (const c of all) {
    if (removed.has(c.id)) out.push({ c, decision: 'reject' });
    else if (c.score >= threshold) out.push({ c, decision: 'accept' });
  }
  return out;
}

/** On cancel nothing is counted, but the hand-removed candidates are still a
 *  judgement („not this symbol") — the corpus keeps them as rejects. */
export function rejectionsToRecord(all, removed) {
  return all.filter((c) => removed.has(c.id)).map((c) => ({ c, decision: 'reject' }));
}

/** Whether a measurement is a „Rasti panašius" mark (drawn hollow, listed apart). */
export function isAiMark(m) {
  return m?.kind === 'count' && m.source === SYMBOL_SOURCE;
}

/** {typeId: n} of AI-found marks — the count legend shows them per type. */
export function aiTallies(measurements) {
  const out = {};
  for (const m of measurements || []) if (isAiMark(m) && m.typeId) out[m.typeId] = (out[m.typeId] || 0) + 1;
  return out;
}

/** AI-found marks of a count type that nobody has checked yet. */
export function aiMarkCount(measurements, typeId) {
  return (measurements || []).filter((m) => m.kind === 'count' && m.typeId === typeId && m.source === SYMBOL_SOURCE).length;
}
