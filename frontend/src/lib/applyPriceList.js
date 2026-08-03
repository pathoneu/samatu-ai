/**
 * applyPriceList — match a price list against a project's positions and fill
 * the `kaina` column where confidence is high enough.
 *
 * Matching strategy (no external deps):
 *   1. Normalize aprašymas — lowercase, strip punctuation, collapse whitespace
 *   2. Score = max( exact_match_after_normalize, token_jaccard )
 *   3. If both project pozicija and price item have `vnt`, vnt MUST match
 *      (m² ≠ m ≠ vnt) — different units = no match no matter the text
 *   4. Apply only when score >= MIN_SCORE
 *   5. Mark applied positions with `kaina_source: 'kainynas'` so the UI can
 *      show provenance and the user can revert
 *
 * Returns { applied: number, skipped: number, items: PozicijaWithMaybeKaina[] }.
 * Pure function — does not mutate input.
 */

const MIN_SCORE = 0.78;       // tuned for LT construction terminology
const TOKEN_MIN_LEN = 3;       // ignore Lithuanian articles / 1-2 char noise

function normalize(s) {
  return String(s || '')
    .toLowerCase()
    .replace(/[.,;:()/]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function tokens(s) {
  return new Set(
    normalize(s)
      .split(' ')
      .filter(t => t.length >= TOKEN_MIN_LEN),
  );
}

function jaccard(setA, setB) {
  if (setA.size === 0 || setB.size === 0) return 0;
  let intersect = 0;
  for (const t of setA) if (setB.has(t)) intersect += 1;
  const union = setA.size + setB.size - intersect;
  return intersect / union;
}

function unitsCompatible(a, b) {
  // Map superscripts to their ASCII token so area / volume / length stay DISTINCT:
  // 'm²'→'m2', 'm³'→'m3', 'm'→'m'. (2026-06-19 hunt: the old code stripped ²³
  // FIRST, collapsing 'm²' and 'm³' to 'm', so a €/m linear price could be matched
  // onto an m² area line — silently mis-pricing the sąmata.)
  const norm = (u) => String(u || '').toLowerCase()
    .replace(/²/g, '2').replace(/³/g, '3').replace(/[\s.]/g, '');
  const ua = norm(a);
  const ub = norm(b);
  if (!ua || !ub) return true;  // benefit-of-the-doubt when unspecified
  return ua === ub;
}

export function scorePair(pozAprasymas, itemAprasymas) {
  const a = normalize(pozAprasymas);
  const b = normalize(itemAprasymas);
  if (!a || !b) return 0;
  if (a === b) return 1.0;
  if (a.includes(b) || b.includes(a)) return 0.92;
  return jaccard(tokens(a), tokens(b));
}

/**
 * Find the best price-list item for a single pozicija.
 * Returns { item, score } or null if nothing crosses the threshold.
 */
export function bestMatchForPozicija(poz, priceItems) {
  let best = null;
  let bestScore = MIN_SCORE - 0.001;
  for (const item of priceItems) {
    if (!unitsCompatible(poz.vnt || poz.mato_vnt, item.vnt || item.mato_vnt)) continue;
    const score = scorePair(poz.aprasymas, item.aprasymas);
    if (score > bestScore) {
      bestScore = score;
      best = item;
    }
  }
  return best ? { item: best, score: bestScore } : null;
}

/**
 * Provenance patch for a price the USER just committed in an editor.
 * Every manual price-commit site must spread this into its row update:
 *   onChange({ ...item, kaina, suma, ...manualPricePatch(item, kaina) })
 * — otherwise the 'manual' guard above never fires and "Taikyti kainyną"
 * overwrites hand-typed prices, breaking the UI promise
 * "Rankomis įvestos kainos lieka nepakeistos".
 *
 * Rules:
 *   - unchanged value → {}: saving a row without touching the price (e.g. a
 *     description fix, or a blur that re-commits the same number) must not
 *     convert a kainynas price into a protected manual one.
 *   - cleared to 0 → source reset: 0 renders as "no price" (—) everywhere,
 *     so a cleared row goes back to fillable-by-kainynas.
 *   - any other value → 'manual'. kaina_match_score describes the kainynas
 *     match, so it dies whenever the source changes.
 */
export function manualPricePatch(prevItem, nextKaina) {
  const prev = Number(prevItem?.kaina) || 0;
  const next = Number(nextKaina) || 0;
  if (next === prev) return {};
  if (next === 0) return { kaina_source: undefined, kaina_match_score: undefined };
  return { kaina_source: 'manual', kaina_match_score: undefined };
}

/**
 * Apply a price list across a project's positions. Returns a new array;
 * input is not mutated. Each row gains `kaina` (eur per unit) and
 * `kaina_source: 'kainynas'` when matched. Existing user-overridden prices
 * (kaina_source==='manual') are left alone.
 */
export function applyPriceListToPositions(positions, priceItems, options = {}) {
  const overwriteManual = !!options.overwriteManual;
  const items = Array.isArray(priceItems) ? priceItems : [];
  let applied = 0;
  let skipped = 0;
  const next = (positions || []).map((poz) => {
    if (poz.kaina_source === 'manual' && !overwriteManual) {
      skipped += 1;
      return poz;
    }
    const m = bestMatchForPozicija(poz, items);
    if (!m) {
      skipped += 1;
      return poz;
    }
    applied += 1;
    return {
      ...poz,
      kaina: Number(m.item.kaina) || 0,
      kaina_source: 'kainynas',
      kaina_match_score: Math.round(m.score * 100) / 100,
    };
  });
  return { items: next, applied, skipped };
}
