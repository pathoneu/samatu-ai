/**
 * applyPriceList — match a price list against a project's positions and fill
 * the `kaina` column where confidence is high enough.
 *
 * Matching strategy (no external deps):
 *   1. Normalize aprašymas — lowercase, DIACRITICS FOLDED, punctuation dropped,
 *      whitespace collapsed
 *   2. Score = max( exact_match_after_normalize, substring, token_jaccard )
 *   3. If both project pozicija and price item have `vnt`, vnt MUST match
 *      (m² ≠ m ≠ vnt) — different units = no match no matter the text. A
 *      price item with NO unit prices a unit-bearing row only when the whole
 *      list quotes no units (2026-09-30)
 *   3b. SIBLING GUARD (2026-09-30): a label that adds a height tier (virš 3 m),
 *      a Q-level, a coat count or a surface (sienų / lubų) is a different
 *      priced line — never filled from the base line, whatever the text score
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
    // „virš 3 m" and „virš 3m" are the same height: glue a number to its
    // length unit so both sides of a match spell it alike.
    .replace(/(\d) (m|mm|cm)(?= |$)/g, '$1$2')
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

/**
 * A token's stem: LT inflects at the end („montavimas / montavimo",
 * „sienų / sienos", „plytelių / plytelės"), so two labels naming the same
 * work in different cases share their first letters. Six letters keep
 * „glaistymas" and „glaistas" apart; short tokens are compared whole.
 */
function stem(t) {
  return t.length > 6 ? t.slice(0, 6) : t;
}

function stemmed(setA) {
  return new Set([...setA].map(stem));
}

/**
 * Coverage: 1 when EVERY word of the shorter label is in the longer one, else 0.
 * A contractor's sąmata line is wordier than ours („Nišų iš GKP paslėptam led
 * apšvietimui glaistymas dažymas" vs „LED nišų glaistymas/dažymas", „Sienų,
 * lubų glaistymas/dažymas" vs „Sienų glaistymas/dažymas"); Jaccard punishes
 * every extra word, this does not. Anything less than full coverage is NOT the
 * same work: siblings differ by exactly one word — „iki 3m" / „virš 3m",
 * „Q2" / „Q4", „lubų" / „sienų" — and a partial overlap priced the premium
 * tier from the plain one (2026-09-15 review). Asked only of labels with at
 * least three real tokens; two-token labels coincide too easily.
 */
function covered(setA, setB) {
  if (setA.size < 3 || setB.size < 3) return 0;
  const [small, big] = setA.size <= setB.size ? [setA, setB] : [setB, setA];
  for (const t of small) if (!big.has(t)) return 0;
  return 1;
}

// ── Sibling qualifiers (exports-money-6, 2026-09-30) ────────────────────────
// The substring and coverage tiers asked only „are all the words of one label
// in the other?". A label that ADDS a height tier, a Q-level, a coat count or
// a surface is a sibling line at a different price, and it scored 0.92 anyway:
// „Sienų glaistymas/dažymas" priced both „(iki 3m aukščio)" and „(virš 3m
// aukščio)", „GKP lubų montavimas" priced its above-3m row. These are the
// words that make two otherwise-equal labels different work.
const LAYER_WORDS = {
  vienu: '1', vieno: '1', vienas: '1', viena: '1',
  du: '2', dvi: '2', dviem: '2', dvieju: '2',
  trys: '3', trim: '3', triju: '3',
};
const SURFACE_WORDS = {
  lubu: 'lubos', lubos: 'lubos', lubas: 'lubos', luboms: 'lubos', lubose: 'lubos',
  sienu: 'sienos', sienos: 'sienos', sienas: 'sienos', sienoms: 'sienos', sienose: 'sienos', siena: 'sienos',
};

/** Tier qualifiers and surfaces a NORMALIZED label names. */
function qualifiersOf(n) {
  const tiers = new Set();
  for (const m of n.matchAll(/\b(iki|virs) ((?:\d+ )*\d+m)\b/g)) tiers.add(`h:${m[1]}:${m[2]}`);
  for (const m of n.matchAll(/\bq([1-4])\b/g)) tiers.add(`q:${m[1]}`);
  for (const m of n.matchAll(/\b(\d+|[a-z]+) sluoksn[a-z]*/g)) {
    const count = /^\d+$/.test(m[1]) ? m[1] : LAYER_WORDS[m[1]];
    if (count) tiers.add(`l:${count}`);
  }
  if (/\bsluoksn/.test(n) && ![...tiers].some(t => t.startsWith('l:'))) tiers.add('l:?');
  const surfaces = new Set();
  for (const w of n.split(' ')) if (SURFACE_WORDS[w]) surfaces.add(SURFACE_WORDS[w]);
  return { tiers, surfaces };
}

/**
 * Do two labels that share their words differ by a sibling qualifier?
 *   'none' — same work as far as tiers and surfaces go
 *   'row'  — the ROW names a tier or surface the price line does not quote
 *            (the line is a different sibling, or the plain base rate): never
 *            a candidate
 *   'item' — the PRICE LINE is the more specific one (the row does not say
 *            which height / Q / coats): never filled from it, but two such
 *            lines at different prices make the row ambiguous, so it is named
 * „iki 3 m" is the ordinary height: it only counts when the other label names
 * a height too, so a plain line still prices our „(iki 3m aukščio)" row.
 * A line naming MORE surfaces than the row („Sienų, lubų …") covers it.
 */
function siblingConflict(na, nb) {
  const a = qualifiersOf(na);
  const b = qualifiersOf(nb);
  const hasHeight = (q) => [...q.tiers].some(t => t.startsWith('h:'));
  const dropUpTo = (q) => { for (const t of [...q.tiers]) if (t.startsWith('h:iki:')) q.tiers.delete(t); };
  if (!hasHeight(b)) dropUpTo(a);
  if (!hasHeight(a)) dropUpTo(b);
  if ([...a.tiers].some(t => !b.tiers.has(t))) return 'row';
  if ([...a.surfaces].some(sf => !b.surfaces.has(sf))) return 'row';
  if ([...b.tiers].some(t => !a.tiers.has(t))) return 'item';
  if (a.surfaces.size === 0 && b.surfaces.size > 0) return 'item';
  return 'none';
}

// A sibling's score is held under MIN_SCORE so it can never fill a row.
const SIBLING_CAP = 0.5;

function jaccard(setA, setB) {
  if (setA.size === 0 || setB.size === 0) return 0;
  let intersect = 0;
  for (const t of setA) if (setB.has(t)) intersect += 1;
  const union = setA.size + setB.size - intersect;
  return intersect / union;
}

function unitsCompatible(a, b, listHasUnits = false) {
  // Map superscripts to their ASCII token so area / volume / length stay DISTINCT:
  // 'm²'→'m2', 'm³'→'m3', 'm'→'m'. (2026-06-19 hunt: the old code stripped ²³
  // FIRST, collapsing 'm²' and 'm³' to 'm', so a €/m linear price could be matched
  // onto an m² area line — silently mis-pricing the sąmata.)
  const norm = (u) => String(u || '').toLowerCase()
    .replace(/²/g, '2').replace(/³/g, '3').replace(/[\s.]/g, '');
  const ua = norm(a);
  const ub = norm(b);
  if (!ua && !ub) return true;
  // A price line with no unit, in a list that quotes units elsewhere, is a
  // rate whose unit nobody knows — „Dažymas 5 €" priced m rows (skirting,
  // LED niches, reveals) with what was an m² rate (exports-money-6). Only a
  // list with no units at all keeps the benefit of the doubt.
  if (!ub) return !listHasUnits;
  if (!ua) return true;          // the row states no unit: as before
  return ua === ub;
}

/** The unit a row/item quotes, wherever it happens to be stored. */
function unitOf(row) {
  return row?.vnt || row?.mato_vnt || '';
}

/** Raw text score plus the sibling verdict (see siblingConflict). */
function pairScore(pozAprasymas, itemAprasymas) {
  const a = normalize(pozAprasymas);
  const b = normalize(itemAprasymas);
  if (!a || !b) return { score: 0, conflict: 'none' };
  if (a === b) return { score: 1.0, conflict: 'none' };
  const conflict = siblingConflict(a, b);
  if (a.includes(b) || b.includes(a)) return { score: 0.92, conflict };
  const ta = tokens(a);
  const tb = tokens(b);
  // Full stemmed coverage sits just under the substring tier: a wordier line
  // that carries every word of ours is „similar", never „exact".
  return { score: Math.max(jaccard(ta, tb), covered(stemmed(ta), stemmed(tb)) ? 0.9 : 0), conflict };
}

export function scorePair(pozAprasymas, itemAprasymas) {
  const { score, conflict } = pairScore(pozAprasymas, itemAprasymas);
  return conflict === 'none' ? score : Math.min(score, SIBLING_CAP);
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
  const list = priceItems || [];
  const listHasUnits = list.some(it => unitOf(it));
  let best = null;
  let bestScore = 0;
  let runnerUp = null;
  let runnerUpScore = 0;
  // More specific sibling lines (see siblingConflict 'item'): never a winner,
  // but a rival — the row does not say which of them it is.
  let sib = null;
  let sibScore = 0;
  let sib2 = null;
  let sib2Score = 0;
  for (const item of list) {
    if (!unitsCompatible(unitOf(poz), unitOf(item), listHasUnits)) continue;
    const { score, conflict } = pairScore(poz?.aprasymas, item?.aprasymas);
    if (conflict === 'row') continue;
    if (conflict === 'item') {
      if (score > sibScore) {
        sib2 = sib; sib2Score = sibScore;
        sib = item; sibScore = score;
      } else if (score > sib2Score) {
        sib2 = item; sib2Score = score;
      }
      continue;
    }
    if (score > bestScore) {
      runnerUp = best; runnerUpScore = bestScore;
      best = item; bestScore = score;
    } else if (score > runnerUpScore) {
      runnerUp = item; runnerUpScore = score;
    }
  }
  const differentPrice = (x, y) => (Number(x.kaina) || 0) !== (Number(y.kaina) || 0);
  const ambiguousPair = (x, y) => ({
    ambiguous: true,
    candidates: [
      { aprasymas: x.aprasymas, kaina: Number(x.kaina) || 0 },
      { aprasymas: y.aprasymas, kaina: Number(y.kaina) || 0 },
    ],
  });
  if (!best || bestScore < MIN_SCORE) {
    // Nothing quotes this row as it stands. Two more specific lines at
    // different prices that both fit it („… Q2" / „… Q4") are named, not
    // guessed between; a single one is simply not this row's price.
    if (sib && sib2 && sib2Score >= MIN_SCORE && sibScore - sib2Score < AMBIGUITY_MARGIN
        && differentPrice(sib, sib2)) {
      return ambiguousPair(sib, sib2);
    }
    return null;
  }
  // Two candidates within a hair of each other quoting DIFFERENT prices: the
  // matcher has no basis to pick one. Identical prices are not ambiguous —
  // a duplicated line in the kainynas gives the same answer either way.
  if (runnerUp && bestScore - runnerUpScore < AMBIGUITY_MARGIN && differentPrice(best, runnerUp)) {
    return ambiguousPair(best, runnerUp);
  }
  // A more specific sibling as close as the winner: the plain row may be
  // either one („Sienų dažymas" vs „… iki 3 m" / „… virš 3 m").
  if (sib && sibScore >= MIN_SCORE && Math.abs(bestScore - sibScore) < AMBIGUITY_MARGIN
      && differentPrice(best, sib)) {
    return ambiguousPair(best, sib);
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
