/**
 * measureLimits.js — how many measurements one sheet holds before the viewer
 * slows down (v3 W7-A M7, measured 2026-10-18 on demo-objektas_h).
 *
 * Measured in headless Chromium, 1440×900, sheet 1, a mix of areas / lines /
 * perimeters / counts, then 40 pans and 16 Ctrl-wheel zooms (rAF frame gaps):
 *     N      open    slowest frame   long tasks (longest)
 *     0      1,1 s   17 ms           0
 *     1000   1,2 s   50 ms           0
 *     2000   1,3 s   117 ms          2 (74 ms)
 *     4000   1,8 s   250 ms          4 (142 ms)
 *     8000   2,7 s   533 ms (p95 67) 19 (317 ms)
 * The first stutter a person notices (a frame over 100 ms) appears between
 * 1000 and 2000 on that machine; slower laptops reach it sooner. The warning
 * fires at 1500, once per sheet, when the count crosses it — nothing is ever
 * blocked. Full numbers: docs/DEVELOPING.md › Limits.
 */

export const MEASUREMENTS_PER_SHEET_WARN = 1500;

function perSheet(measurements) {
  const out = new Map();
  for (const m of measurements || []) {
    if (!m || m.page == null) continue;
    out.set(m.page, (out.get(m.page) || 0) + 1);
  }
  return out;
}

/** Sheets whose measurement count went from below the limit to at or above it. */
export function sheetsCrossingLimit(prev, next, limit = MEASUREMENTS_PER_SHEET_WARN) {
  const before = perSheet(prev);
  const after = perSheet(next);
  const out = [];
  for (const [page, count] of after) {
    if (count >= limit && (before.get(page) || 0) < limit) out.push({ page, count });
  }
  return out.sort((a, b) => a.page - b.page);
}

/** The warning, in plain words: what happened, what it does, what to do. */
export function sheetLimitMessage({ page, count }) {
  return `${page} lape jau ${count} matavimų. Kai jų daugiau nei ${MEASUREMENTS_PER_SHEET_WARN}, `
    + 'brėžinys gali pradėti strigti traukiant ar didinant. Nereikalingus matavimus ištrinkite '
    + 'arba juos eksportuokite („Matavimai" → CSV) ir išvalykite.';
}
