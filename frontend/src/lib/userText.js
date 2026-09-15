/**
 * cleanUserText — the frontend twin of backend `extractor/user_text.py`.
 *
 * Every prose field a component renders (a stored `_confidence_reason`, an
 * `_assumption`, a ledger `note`/`included_because`, a sanity message) may have
 * been written by an older engine and can carry methodology confession or —
 * worse — another customer's project name (2026-09-02, seen on production).
 * The backend scrubs on read and rewrites blobs at startup; this is the last
 * line: a component never prints a stored sentence that trips the guard.
 *
 * Generic jargon lives here. Customer identifiers are NEVER in the repo AND
 * never in this bundle: a `VITE_*` denylist would be inlined into the public
 * JS for anyone to read (2026-09-15 review). The customer-name scrub is the
 * backend's (`scrub_prose` on read, `.confidential-terms` outside the repo);
 * every prose field reaches a component already scrubbed of names.
 */
const JARGON = new RegExp([
  'rangovo samat', '\\brangovą\\b', 'Rangovas [A-D]\\b', '\\(\\d+ projekt', 'projektai\\)',
  '\\bvs\\b', '%/', '\\brecall\\b', 'etalon', 'kalibruot', 'ginčytin', 'Ekstrakcij',
  'Gretimyb', 'pradinis pass', 'archetip', 'low confidence', '\\bVision\\b', 'žinomai',
  'Sprint\\s*\\d', '\\bTODO\\b', '\\bFIXME\\b', 'shared-walls', '\\bMAE\\b', 'benchmark',
].join('|'), 'i');

/** Test hook kept for callers; there is no cached pattern any more. */
export function _resetConfidentialCache() { /* no-op since 2026-09-15 */ }

export function isBannedText(text) {
  if (typeof text !== 'string' || !text) return false;
  return JARGON.test(text);
}

export const FALLBACK_TEXT = 'Patikrinkite šį kiekį pagal brėžinį.';

/**
 * Drop every clause carrying jargon/a confidential term, keep the rest; nothing
 * left → generic guidance. Clean text is returned as-is (identity).
 */
export function cleanUserText(text, fallback = FALLBACK_TEXT) {
  if (typeof text !== 'string' || !text.trim()) return text;
  if (!isBannedText(text)) return text;
  const kept = text.split(/(?<=[.;])\s+|\s+—\s+/).filter(c => c && !isBannedText(c));
  const cleaned = kept.map(c => c.trim()).join(' ').trim();
  return cleaned || fallback;
}
