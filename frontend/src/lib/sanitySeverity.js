/**
 * Sanity-check severity vocabulary + merge rules for `project.lt_sanity`.
 *
 * These checks (CLAUDE.md §6 — dažomas plotas 2,5–4× grindų ploto, lubos ≈
 * grindys, grindjuostė ≈ perimetras − 0,8 m/durys …) are the app's only
 * generalisation safety net on a project nobody has seen before. A 2026-08
 * audit found them muted on four counts; three of them lived here:
 *
 *   · the backend mirror dropped `severity`, so a `severity:"high"` violation
 *     arrived as a blue INFO row (fixed in extractor/sanity_mirror.py — this
 *     module keeps the SAME tier contract for older, already-saved blobs);
 *   · INFO was collapsed by default and left out of the counter, so a demoted
 *     high-severity check was invisible in both places at once;
 *   · "Atnaujinti AI patikrinimus" replaced the whole list, so any stream the
 *     rebuild did not produce was deleted from the UI.
 *
 * Tier contract (mirrors backend `extractor/sanity_mirror.resolve_tier`):
 *   severity  level     UI
 *   high      WARNING   red,   expanded by default, counted as "įspėjimas"
 *   med       WARNING   amber, expanded by default, counted as "įspėjimas"
 *   low       INFO      muted, collapsed by default, counted as "pastaba"
 *   (any)     ERROR     red — an authored ERROR always outranks its severity
 *
 * Pure module: no React, no DOM, no i18n. Unit-tested in sanitySeverity.test.js.
 */

export const SEV_HIGH = 'high';
export const SEV_MED = 'med';
export const SEV_LOW = 'low';

/** Loudest first — used to order the banner groups. */
export const SEVERITY_ORDER = [SEV_HIGH, SEV_MED, SEV_LOW];

const SEVERITY_ALIASES = {
  high: SEV_HIGH, critical: SEV_HIGH, error: SEV_HIGH, fail: SEV_HIGH,
  regression: SEV_HIGH,
  med: SEV_MED, medium: SEV_MED, warn: SEV_MED, warning: SEV_MED,
  low: SEV_LOW, info: SEV_LOW, note: SEV_LOW,
};

const LEVEL_ALIASES = {
  ERROR: 'ERROR', FAIL: 'ERROR', CRITICAL: 'ERROR', CRIT: 'ERROR',
  WARN: 'WARNING', WARNING: 'WARNING',
  INFO: 'INFO', NOTE: 'INFO', OK: 'INFO', PASS: 'INFO', DEBUG: 'INFO',
};

const SEVERITY_FROM_LEVEL = { ERROR: SEV_HIGH, WARNING: SEV_MED, INFO: SEV_LOW };

export function normalizeLevel(raw) {
  if (typeof raw !== 'string' || !raw.trim()) return null;
  return LEVEL_ALIASES[raw.trim().toUpperCase()] || null;
}

export function normalizeSeverity(raw) {
  if (typeof raw !== 'string' || !raw.trim()) return null;
  return SEVERITY_ALIASES[raw.trim().toLowerCase()] || null;
}

/**
 * Resolve one warning to its UI tier.
 *
 * An authored ERROR wins outright; otherwise `severity` decides, so a
 * high-severity §6 check can never land in the collapsed info bucket again.
 * Blobs saved before the backend carried `severity` fall back to `level`.
 */
export function warningSeverity(w) {
  if (!w || typeof w !== 'object') return SEV_LOW;
  const level = normalizeLevel(w.level);
  if (level === 'ERROR') return SEV_HIGH;
  const sev = normalizeSeverity(w.severity);
  if (sev) return sev;
  return SEVERITY_FROM_LEVEL[level || 'INFO'] || SEV_LOW;
}

/** High and medium are actionable ("įspėjimai"); low is a note ("pastaba"). */
export function isActionable(w) {
  return warningSeverity(w) !== SEV_LOW;
}

/**
 * Stable identity for dismissal tracking AND for the revalidate merge.
 * Deliberately excludes `level`/`severity`: re-running a check may change how
 * loud it is without making it a different finding, and a user who dismissed
 * it should not see it come back as a new row.
 */
export function warningKey(w) {
  if (!w || typeof w !== 'object') return String(w);
  const code = w.code || '';
  const source = w.source || '';
  return [source, code, w.room || '', w.field || '',
    String(w.message || '').slice(0, 120)].join('|');
}

/**
 * Counts the severity pill and the banner header read.
 * `warnings` = high + med (actionable), `notes` = low.
 */
export function summarizeSanity(sanity) {
  const list = Array.isArray(sanity?.warnings) ? sanity.warnings : [];
  let high = 0, med = 0, low = 0;
  for (const w of list) {
    const sev = warningSeverity(w);
    if (sev === SEV_HIGH) high += 1;
    else if (sev === SEV_MED) med += 1;
    else low += 1;
  }
  return { high, med, low, warnings: high + med, notes: low, total: list.length };
}

/** Group warnings by tier, loudest first. Returns [[severity, items], …]. */
export function groupBySeverity(warnings) {
  const buckets = { [SEV_HIGH]: [], [SEV_MED]: [], [SEV_LOW]: [] };
  for (const w of warnings || []) buckets[warningSeverity(w)].push(w);
  return SEVERITY_ORDER
    .filter((sev) => buckets[sev].length > 0)
    .map((sev) => [sev, buckets[sev]]);
}

// ── actionable jumps ────────────────────────────────────────────────────────
// A loud warning the user cannot act on is only half a fix. Where a control
// exists, the row offers a one-click jump to it. Keyed on the backend `code`
// (stable) with a `field` fallback for older blobs that predate the codes.

export const ACTION_PRIELAIDOS = 'prielaidos';

const ACTION_BY_CODE = {
  paintable_floor_ratio: ACTION_PRIELAIDOS,
  ceiling_floor_mismatch: ACTION_PRIELAIDOS,
  paint_consumption_rate: ACTION_PRIELAIDOS,
  window_reveals_zero: ACTION_PRIELAIDOS,
  window_reveal_avg_off: ACTION_PRIELAIDOS,
  lubu_aukstis_below_str: ACTION_PRIELAIDOS,
  lubu_aukstis_out_of_range: ACTION_PRIELAIDOS,
  consistency_wall_floor_ratio: ACTION_PRIELAIDOS,
  consistency_height_plausibility: ACTION_PRIELAIDOS,
  consistency_height_uniformity: ACTION_PRIELAIDOS,
};

const ACTION_BY_FIELD = {
  lubu_aukstis_m: ACTION_PRIELAIDOS,
  sienu_storis_m: ACTION_PRIELAIDOS,
};

export function warningAction(w) {
  if (!w || typeof w !== 'object') return null;
  return ACTION_BY_CODE[w.code] || ACTION_BY_FIELD[w.field] || null;
}

// Which Prielaidos control a warning is actually about. The warnings have
// carried `code` / `field` / `room` since lt_rules.py:172 and the banner threw
// all three away — `onOpenAssumptions()` with no arguments dropped the user at
// the top of a long panel. (2026-09-02, Patikra.)
const ASSUMPTION_FIELD_BY_CODE = {
  lubu_aukstis_below_str: 'lubu_auksciai',
  lubu_aukstis_out_of_range: 'lubu_auksciai',
  consistency_height_plausibility: 'lubu_auksciai',
  consistency_height_uniformity: 'lubu_auksciai',
  paintable_floor_ratio: 'lubu_auksciai',
  consistency_wall_floor_ratio: 'lubu_auksciai',
  ceiling_floor_mismatch: 'stretch_ceiling_override',
};

const ASSUMPTION_FIELD_BY_WARNING_FIELD = {
  lubu_aukstis_m: 'lubu_auksciai',
};

/**
 * The `{field, roomNr}` an „Atidaryti Prielaidas" jump should land on, or null
 * when the warning names no control we can scroll to (then the panel just
 * opens, exactly as before).
 */
export function assumptionFocus(w) {
  if (!w || typeof w !== 'object') return null;
  const field = ASSUMPTION_FIELD_BY_CODE[w.code]
    || ASSUMPTION_FIELD_BY_WARNING_FIELD[w.field]
    || null;
  if (!field) return null;
  // `room` is the room NUMBER on the per-room validators and absent on the
  // project-level ones; an absent room focuses the section, not a row.
  const roomNr = w.room != null && String(w.room).trim() !== ''
    ? String(w.room).trim()
    : null;
  return { field, roomNr };
}

// Validators disagree on where the expected range goes: some put it in the
// message ("…tikėtina ~41,4 m…", "…norma 2,2–4,5 m…"), some only in
// `expected`. Appending it unconditionally produced rows that said the same
// number twice — "Grindjuostės 56,0 m, tikėtina ~41,4 m (…) (tikėtina ~41,4 m)".
const EXPECTED_ALREADY_SAID = ['tikėtina', 'norma', 'turi būti', 'leistina'];

/** The expected range to append after the message, or null if it is redundant. */
export function expectedSuffix(w) {
  const expected = w && typeof w === 'object' ? w.expected : null;
  if (typeof expected !== 'string' || !expected.trim()) return null;
  const message = String(w.message || '').toLowerCase();
  if (message.includes(expected.trim().toLowerCase())) return null;
  if (EXPECTED_ALREADY_SAID.some((phrase) => message.includes(phrase))) return null;
  return expected.trim();
}

/**
 * A room's note as it reads in the list: „101 Tambūras: Sienos dažomos…" —
 * the room the way every other screen names it. The backend puts the room's
 * NAME at the head of the message (lt_rules `_who`) and its NUMBER in `room`;
 * the list printed them glued as „[101]Tambūras: …" (2026-10-07). Returns the
 * number to print in front (empty when there is none, or when the message
 * already starts with it) and the message — a stored message that carries the
 * old „[101]" in front loses it.
 */
export function roomNoteParts(w) {
  const message = typeof w?.message === 'string' ? w.message : String(w?.message ?? '');
  const room = w?.room != null ? String(w.room).trim() : '';
  if (!room) return { room: '', text: message };
  let text = message.trimStart();
  const bracketed = `[${room}]`;
  if (text.startsWith(bracketed)) text = text.slice(bracketed.length).trimStart();
  if (text === room || text.startsWith(`${room} `) || text.startsWith(`${room}:`)) {
    return { room: '', text };
  }
  return { room, text };
}

// ── revalidate merge ────────────────────────────────────────────────────────

/**
 * The streams „Atnaujinti patikrinimus" RE-RUNS on every press (backend
 * api/revalidate.py RECOMPUTED_SOURCES; a backend test pins the two lists).
 * For these the refreshed list is the whole truth, EMPTY INCLUDED: a check
 * that now passes leaves no row at all. Keeping the old row whenever the
 * refresh had none for its stream is how a fixed false note („GKP lapų
 * skaičius nesutampa", 2026-10-07) stayed on screen and was saved back.
 */
export const REFRESH_RECOMPUTES = ['sanity_checks', 'cross_page_validator', 'revalidate', 'lt_rules'];

/**
 * The CLAUDE.md §6 check codes (backend extractor/sanity_checks.py CODES,
 * pinned by the same test). Projects saved before 2026-08-23 carry these rows
 * with the code but WITHOUT a `source` — the code is what says the refresh
 * re-ran them.
 */
export const SANITY_CHECK_CODES = [
  'paintable_floor_ratio',
  'ceiling_floor_mismatch',
  'baseboard_perimeter_mismatch',
  'perimeter_below_geometric_minimum',
  'paint_consumption_rate',
  'gk_sheets_off',
  'window_reveals_zero',
  'window_reveal_avg_off',
  'sanity_check_error',
];

const REFRESH_SOURCES = new Set(REFRESH_RECOMPUTES);
const SANITY_CODES = new Set(SANITY_CHECK_CODES);

/** Did the refresh re-run the check behind this row? Then only its new list counts. */
function recomputedByRefresh(w) {
  if (!w || typeof w !== 'object') return false;
  if (w.source) return REFRESH_SOURCES.has(w.source);
  return SANITY_CODES.has(w.code);
}

/**
 * Merge a rebuilt `lt_sanity` onto the one already on screen.
 *
 * Rule, per row on screen:
 *
 *   · the refresh re-ran its check (REFRESH_RECOMPUTES / SANITY_CHECK_CODES)
 *     → the rebuilt list replaces it, even when the rebuilt list has nothing
 *     for that stream (the check now passes, the row goes);
 *   · otherwise, per stream (`source`): the rebuild produced entries for this
 *     source → its list is authoritative; it produced nothing → keep what we
 *     had. "Atnaujinti patikrinimus" must never make a note disappear that it
 *     cannot recompute (one written only during the reading of the drawing).
 *
 * Fresh entries win on identical keys so refreshed wording/severity lands.
 * The summary is recomputed from the merged list rather than trusted from
 * either side — otherwise the counter and the rows disagree.
 */
export function mergeSanity(prev, fresh) {
  const prevList = Array.isArray(prev?.warnings) ? prev.warnings : [];
  const freshList = Array.isArray(fresh?.warnings) ? fresh.warnings : [];
  if (!fresh || !Array.isArray(fresh.warnings)) return prev || null;
  if (!prevList.length) return withSummary(fresh, freshList);

  const refreshedSources = new Set(
    freshList.map((w) => w?.source || '').filter((s) => s !== '')
  );
  // An untagged fresh entry means we cannot tell which stream it replaced;
  // treat untagged as its own stream so tagged ones are unaffected.
  const freshHasUntagged = freshList.some((w) => !w?.source);

  const merged = [];
  const seen = new Set();
  for (const w of freshList) {
    merged.push(w);
    seen.add(warningKey(w));
  }
  for (const w of prevList) {
    if (recomputedByRefresh(w)) continue;  // re-run — the rebuilt list is the truth
    const source = w?.source || '';
    const wasRefreshed = source
      ? refreshedSources.has(source)
      : freshHasUntagged;
    if (wasRefreshed) continue;            // authoritative rebuild — drop
    const key = warningKey(w);
    if (seen.has(key)) continue;
    merged.push(w);
    seen.add(key);
  }
  return withSummary(fresh, merged);
}

function withSummary(fresh, warnings) {
  const counts = summarizeSanity({ warnings });
  let errors = 0;
  for (const w of warnings) if (normalizeLevel(w?.level) === 'ERROR') errors += 1;
  return {
    ...fresh,
    warnings,
    summary: {
      ...(fresh?.summary || {}),
      // Recomputed from the merged list — trusting either side's counter
      // after a merge is how the header ends up disagreeing with the rows.
      warnings_count: counts.warnings,
      errors,
      warnings: counts.warnings - errors,
      info: counts.low,
      high: counts.high,
      medium: counts.med,
      low: counts.low,
    },
  };
}
