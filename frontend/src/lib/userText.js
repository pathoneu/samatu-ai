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
 * Generic jargon lives here. Customer identifiers are NEVER in the repo — they
 * come from `VITE_CONFIDENTIAL_TERMS` (comma-separated, set in the hosting env
 * and in a gitignored .env.local).
 */
const JARGON = new RegExp([
  'rangovo samat', '\\brangovą\\b', 'Rangovas [A-D]\\b', '\\(\\d+ projekt', 'projektai\\)',
  '\\bvs\\b', '%/', '\\brecall\\b', 'etalon', 'kalibruot', 'ginčytin', 'Ekstrakcij',
  'Gretimyb', 'pradinis pass', 'archetip', 'low confidence', '\\bVision\\b', 'žinomai',
  'Sprint\\s*\\d', '\\bTODO\\b', '\\bFIXME\\b', 'shared-walls', '\\bMAE\\b', 'benchmark',
].join('|'), 'i');

function escapeRe(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }

let _confidential = null;
function confidentialPattern() {
  if (_confidential !== null) return _confidential;
  let raw = '';
  try { raw = import.meta.env?.VITE_CONFIDENTIAL_TERMS || ''; } catch { raw = ''; }
  try { raw = raw || globalThis.process?.env?.VITE_CONFIDENTIAL_TERMS || ''; } catch { /* node:test */ }
  const terms = raw.split(',').map(t => t.trim()).filter(Boolean);
  _confidential = terms.length ? new RegExp(terms.map(escapeRe).join('|'), 'i') : false;
  return _confidential;
}

/** Test hook — reset the cached pattern after changing the env. */
export function _resetConfidentialCache() { _confidential = null; }

export function isBannedText(text) {
  if (typeof text !== 'string' || !text) return false;
  if (JARGON.test(text)) return true;
  const c = confidentialPattern();
  return Boolean(c && c.test(text));
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
