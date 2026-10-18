/**
 * Shared per-line confidence vocabulary (P0 fix 2026-08-03).
 *
 * The backend stamps LT tiers (extractor/confidence.py: zalia/geltona/raudona)
 * onto darbu_sarasas rows; older blobs and a few frontend writers still carry
 * the legacy EN scheme (high/medium/low). Every consumer must normalize through
 * here — a raw `confidence === 'low'` comparison silently renders engine-flagged
 * rows as confident green.
 *
 * Canonical tiers are the LT values, because that is what production emits.
 */

export const CONF_ZALIA = 'zalia';
export const CONF_GELTONA = 'geltona';
export const CONF_RAUDONA = 'raudona';

const TIER_BY_VALUE = {
  zalia: CONF_ZALIA,
  'žalia': CONF_ZALIA,
  high: CONF_ZALIA,
  geltona: CONF_GELTONA,
  medium: CONF_GELTONA,
  raudona: CONF_RAUDONA,
  low: CONF_RAUDONA,
};

const RANK = { [CONF_ZALIA]: 0, [CONF_GELTONA]: 1, [CONF_RAUDONA]: 2 };

// Lifted from the retired PositionsPanel map — the one place that already spoke
// both vocabularies.
export const CONFIDENCE_LABELS = {
  [CONF_ZALIA]: 'Skaityta tiesiogiai',
  [CONF_GELTONA]: 'Patikrinti',
  [CONF_RAUDONA]: 'Būtina patikrinti',
};

// index.css ships .dot-high/.dot-med/.dot-low on the --conf-* tokens.
export const CONFIDENCE_DOT_CLASS = {
  [CONF_ZALIA]: 'dot-high',
  [CONF_GELTONA]: 'dot-med',
  [CONF_RAUDONA]: 'dot-low',
};

/**
 * Map any confidence value (LT, legacy EN, junk) to a canonical tier.
 * Unstamped rows (null/'') stay zalia — legacy KŽ rows carry no confidence and
 * must not be flagged retroactively. Unknown non-empty values normalize to
 * geltona: vocabulary drift must never render as trusted green again.
 */
export function normalizeConfidence(value) {
  const raw = String(value ?? '').trim().toLowerCase();
  if (!raw) return CONF_ZALIA;
  return TIER_BY_VALUE[raw] || CONF_GELTONA;
}

export function confidenceRank(value) {
  return RANK[normalizeConfidence(value)];
}

export function confidenceNeedsReview(value) {
  return normalizeConfidence(value) !== CONF_ZALIA;
}

export function confidenceLabel(value) {
  return CONFIDENCE_LABELS[normalizeConfidence(value)];
}

// A room's area in one sentence, in the labels' words — the drawing's room chip (2026-10-18 audit §6 item 10:
// it said „Ploto pasitikėjimas: high"). Takes any vocabulary, including areaConfidence's 'unknown' (a guess).
const AREA_SENTENCES = {
  [CONF_ZALIA]: 'Plotas skaitytas tiesiogiai — tikrinti nereikia.',
  [CONF_GELTONA]: 'Plotą verta patikrinti.',
  [CONF_RAUDONA]: 'Plotą būtina patikrinti.',
};

export function areaConfidenceSentence(value) {
  return AREA_SENTENCES[normalizeConfidence(value)];
}
