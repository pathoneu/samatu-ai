/**
 * applyPriceList — match a price list against a project's positions and fill
 * the `kaina` column where confidence is high enough.
 *
 * Matching strategy (no external deps):
 *   1. Normalize aprašymas — lowercase, DIACRITICS FOLDED, punctuation dropped,
 *      whitespace collapsed
 *   2. Score = max( exact_match_after_normalize, substring, token_jaccard )
 *   3. If both project pozicija and price item have `vnt`, vnt MUST match
 *      (m² ≠ m ≠ vnt) — different units = no match no matter the text
 *   4. Apply only when score >= MIN_SCORE
 *   5. AMBIGUITY GUARD: when the two best candidates are within
 *      AMBIGUITY_MARGIN of each other AND quote different prices, fill nothing
 *      and report the row — guessing between two prices is the one failure the
 *      user cannot see in a finished sąmata
 *   6. Mark applied positions with `kaina_source: 'kainynas'` so the UI can
 *      show provenance and the user can revert
 *
 * Returns { applied, skipped, exact, similar, ambiguous[], items[] }.
 * Pure function — does not mutate input.
 *
 * NORMALIZATION AUDIT (2026-09-02). `mergeDarbuSarasas.normLabel` is the
 * strongest normalizer in the codebase, but only ONE of its three moves belongs
 * here:
 *   - diacritics folding  → ADOPTED. A kainynas typed on a keyboard without LT
 *     letters ("Sienu dazymas") must price "Sienų dažymas"; before this it
 *     scored 0 and the row stayed empty.
 *   - Q-level stripping   → REJECTED. Q2 and Q4 glaistymas are different work at
 *     different prices; folding them would either mis-price a row or (with the
 *     guard above) make every Q line ambiguous.
 *   - '(N sluoksnis)' strip → REJECTED, same reason: a price list that quotes
 *     one and two coats separately means it.
 * The merge has to fold those because a rebuild RE-TIERS a row it already owns;
 * pricing has no such excuse.
 */

const MIN_SCORE = 0.78;        // tuned for LT construction terminology
const TOKEN_MIN_LEN = 3;       // ignore Lithuanian articles / 1-2 char noise
// Two candidates this close are indistinguishable to the matcher. 0.05 keeps
// the ordinary "one clear winner" case (typically a >0.2 gap) filling.
const AMBIGUITY_MARGIN = 0.05;

function normalize(s) {
  return String(s || '')
    .toLowerCase()
    // Fold diacritics: ą→a, č→c, ę→e, ė→e, į→i, š→s, ų→u, ū→u, ž→z.
    .normalize('NFKD').replace(/[\u0300-\u036f]/g, '')
    // Everything that is not a letter or digit is a separator. (Was a fixed
    // `.,;:()/` list, which left hyphens, quotes and „ “ glued to their words.)
    .replace(/[^\p{L}\p{N}]+/gu, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function tokens(s) {
  return new Set(
    normalize(s)
      .split(' ')
      // Short tokens are LT noise — except when they carry a digit. 'q2'/'q4',
      // '12,5', '9,5' are the whole difference between two priced lines, and
      // dropping them made 'Sienų glaistymas Q2' and '… Q4' score a perfect
      // 1.0 against each other: the matcher then filled the Q4 row from the Q2
      // price, silently, with no way for the user to see it. (2026-09-02 audit.)
      .filter(t => t.length >= TOKEN_MIN_LEN || /\d/.test(t)),
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

/** The unit a row/item quotes, wherever it happens to be stored. */
function unitOf(row) {
  return row?.vnt || row?.mato_vnt || '';
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
 *
 * Returns:
 *   { item, score, tier: 'exact' | 'similar' }  — a usable match
 *   { ambiguous: true, candidates: [{aprasymas, kaina}, …] } — two prices too
 *     close to choose between; the caller must NOT fill
 *   null — nothing crossed the threshold
 */
export function bestMatchForPozicija(poz, priceItems) {
  let best = null;
  let bestScore = 0;
  let runnerUp = null;
  let runnerUpScore = 0;
  for (const item of priceItems || []) {
    if (!unitsCompatible(unitOf(poz), unitOf(item))) continue;
    const score = scorePair(poz?.aprasymas, item?.aprasymas);
    if (score > bestScore) {
      runnerUp = best; runnerUpScore = bestScore;
      best = item; bestScore = score;
    } else if (score > runnerUpScore) {
      runnerUp = item; runnerUpScore = score;
    }
  }
  if (!best || bestScore < MIN_SCORE) return null;
  // Two candidates within a hair of each other quoting DIFFERENT prices: the
  // matcher has no basis to pick one. Identical prices are not ambiguous —
  // a duplicated line in the kainynas gives the same answer either way.
  if (runnerUp && bestScore - runnerUpScore < AMBIGUITY_MARGIN
      && (Number(runnerUp.kaina) || 0) !== (Number(best.kaina) || 0)) {
    return {
      ambiguous: true,
      candidates: [
        { aprasymas: best.aprasymas, kaina: Number(best.kaina) || 0 },
        { aprasymas: runnerUp.aprasymas, kaina: Number(runnerUp.kaina) || 0 },
      ],
    };
  }
  // 'exact' means the DESCRIPTIONS are the same once folded — not merely that
  // the score reached 1.0, which token overlap can also do.
  const tier = normalize(poz?.aprasymas) === normalize(best.aprasymas)
    ? 'exact' : 'similar';
  return { item: best, score: bestScore, tier };
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
 *
 * options:
 *   overwriteManual  — re-price hand-typed rows too (never used by the UI)
 *   onlyEmpty        — touch only rows that carry no price at all. This is what
 *                      the automatic fill after an extraction uses: it may add
 *                      prices, never replace one that is already on the books.
 */
export function applyPriceListToPositions(positions, priceItems, options = {}) {
  const overwriteManual = !!options.overwriteManual;
  const onlyEmpty = !!options.onlyEmpty;
  const items = Array.isArray(priceItems) ? priceItems : [];
  let applied = 0;
  let skipped = 0;
  let exact = 0;
  let similar = 0;
  const ambiguous = [];
  const next = (positions || []).map((poz) => {
    if (poz.kaina_source === 'manual' && !overwriteManual) {
      skipped += 1;
      return poz;
    }
    if (onlyEmpty && (Number(poz.kaina) || 0) !== 0) {
      skipped += 1;
      return poz;
    }
    const m = bestMatchForPozicija(poz, items);
    if (!m) {
      skipped += 1;
      return poz;
    }
    if (m.ambiguous) {
      // Reported, not filled — the user gets to see WHICH rows need a decision.
      skipped += 1;
      ambiguous.push({ aprasymas: poz.aprasymas, candidates: m.candidates });
      return poz;
    }
    applied += 1;
    if (m.tier === 'exact') exact += 1; else similar += 1;
    return {
      ...poz,
      kaina: Number(m.item.kaina) || 0,
      kaina_source: 'kainynas',
      kaina_match_score: Math.round(m.score * 100) / 100,
    };
  });
  return { items: next, applied, skipped, exact, similar, ambiguous };
}

/**
 * Name the rows the matcher refused to price, the way the recompute already
 * names its carried rows.
 *
 * `applyPriceListToPositions` has always returned `{aprasymas, candidates}` per
 * ambiguous row, and every one of the three call sites threw all but the count
 * away — so the user was told "3 rows need a price by hand" and had no way to
 * find WHICH three in an 80-row sąmata. Takes `t` so it stays translatable
 * without importing i18n into lib/. Returns undefined when there is nothing to
 * name, which is what a toast's `description` expects. (2026-09-02)
 */
export const AMBIGUOUS_ROWS_SHOWN = 5;

export function describeAmbiguous(ambiguous, t) {
  const rows = (ambiguous || [])
    .map((a) => (typeof a === 'string' ? a : a?.aprasymas))
    .filter(Boolean);
  if (!rows.length) return undefined;
  const shown = rows.slice(0, AMBIGUOUS_ROWS_SHOWN).join(' · ');
  return t('project.mainView.toastAmbiguousRows', {
    rows: rows.length > AMBIGUOUS_ROWS_SHOWN ? `${shown}…` : shown,
  });
}

/** The user's default kainynas, or null. One per user is enforced server-side. */
export function findDefaultPriceList(priceLists) {
  return (priceLists || []).find(pl => pl?.is_default && (pl.items || []).length) || null;
}

/**
 * Automatic fill right after an extraction lands (founder decision 2026-09-02:
 * "auto-apply from the default price list + keep the manual button").
 *
 * Deliberately conservative:
 *   - only runs when the user has marked a kainynas as default
 *   - only fills rows with NO price (onlyEmpty) — it can never move money
 *   - stamps `_kainynas_auto_applied` on the project so a reload, a recompute
 *     or a second visit cannot fire it again
 *
 * Pure: returns `{ project, summary }` or null when there is nothing to do.
 */
export function autoFillFromDefaultPriceList(project, priceLists) {
  if (!project || project._kainynas_auto_applied) return null;
  const list = findDefaultPriceList(priceLists);
  if (!list) return null;

  const next = { ...project };
  let primary = null;
  let touched = false;
  for (const key of ['darbu_sarasas', 'pozicijos', 'rows']) {
    const src = project[key];
    if (!Array.isArray(src) || src.length === 0) continue;
    const result = applyPriceListToPositions(src, list.items || [], { onlyEmpty: true });
    // Keep suma in step with the price we just wrote — the totals row and the
    // exports read `suma`, not kaina × kiekis.
    next[key] = result.items.map(r => (
      r.kaina_source === 'kainynas'
        ? { ...r, suma: (Number(r.kiekis) || 0) * (Number(r.kaina) || 0) }
        : r
    ));
    touched = true;
    if (!primary) primary = result;
  }
  if (!touched || !primary || primary.applied === 0) return null;

  next._kainynas_auto_applied = {
    id: list.id,
    name: list.name,
    applied_at: new Date().toISOString(),
    applied: primary.applied,
    exact: primary.exact,
    similar: primary.similar,
  };
  return {
    project: next,
    summary: {
      name: list.name,
      applied: primary.applied,
      exact: primary.exact,
      similar: primary.similar,
      skipped: primary.skipped,
      ambiguous: primary.ambiguous,
    },
  };
}
