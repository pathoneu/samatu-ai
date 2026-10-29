/**
 * noticeFold — the words of the one „Pranešimai (N)" line that folds Patikra's notices (Pathon v3 W6-A).
 *
 * Measured 2026-10-19 on demo-objektas_h: three notices stood before the questions; at 1280×720 the first
 * question started below the panel. Two or more notices fold into one line that names each, so nothing is
 * hidden without a trace; one notice shows as it is.
 */

/** A notice's root `data-testid` → the name the fold line gives it. */
export const NOTICE_NAMES = {
  'read-rating': 'skaitymo įvertinimas',
  'reminders-patikra': 'priminimai',
  // above the right panel on Brėžinys / Sąmata and on Siųsti (B1-D)
  'server-refresh-notice': 'atnaujinta iš serverio',
  'reread-diff-banner': 'kas pasikeitė',
};

export const FOLD_MIN = 2;

/** True when the notices present should fold into one line. */
export function shouldFold(count) {
  return count >= FOLD_MIN;
}

// A notice that stays on screen while the rest are folded — as the fold's first line, one line + its button.
// No lead notice today (the free re-read offer, the one notice that always led, was removed 2026-10-29).
export const LEAD_NOTICES = [];

/** The notice that leads the fold (shown while it is closed), or null. */
export function leadNotice(testIds) {
  return LEAD_NOTICES.find((id) => (testIds || []).includes(id)) || null;
}

/**
 * { title, names } for the fold line, e.g. { title: 'Pranešimai (3)', names: 'nemokamas perskaitymas · …' }.
 * With a lead notice on screen the line counts only what it hides: { title: 'Dar pranešimai (2)', … }.
 */
export function foldLabel(testIds, lead = null) {
  const rest = lead ? testIds.filter((id) => id !== lead) : testIds;
  const names = rest.map((id) => NOTICE_NAMES[id] || null).filter(Boolean);
  return { title: `${lead ? 'Dar pranešimai' : 'Pranešimai'} (${rest.length})`, names: names.join(' · '), count: rest.length };
}

// A notice that answers what he just did (the re-read's „Kas pasikeitė" with its „Atšaukti") opens the fold
// when it ARRIVES or carries a NEW stamp (a later re-read: `data-notice-stamp`, the diff's time) — never on a page
// load where it was already there — so the Undo of his action is on screen.
export const OPENS_ON_ARRIVAL = new Set(['reread-diff-banner']);

/**
 * True when `next` holds an opens-on-arrival notice that `prev` did not. Entries are a notice's id, or
 * `id@stamp` when it carries a stamp. prev null = the first look: false.
 */
export function opensOnArrival(prev, next) {
  if (!Array.isArray(prev)) return false;
  return (next || []).some((key) => OPENS_ON_ARRIVAL.has(String(key).split('@')[0]) && !prev.includes(key));
}
