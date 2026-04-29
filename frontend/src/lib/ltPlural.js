/**
 * ltPlural.js — Lithuanian noun pluralisation per LT grammar rules
 * (Sprint §AUDIT, 2026-04-29).
 *
 * LT has 3 number forms (vienaskaita / dauginis / nulinis), each with
 * different endings. The rule:
 *
 *   1, 21, 31, 41, 91, 101, ... → vienaskaita (singular)   "1 siena"
 *   2-9, 22-29, 32-39, ...      → dauginis    (paucal)     "2 sienos"
 *   0, 10-19, 20, 30, 40, ...   → nulinis     (genitive plural) "10 sienų"
 *
 * Wrong: "12 sienos" — 12 ends in 2 BUT 11..19 are exceptions.
 * Wrong: "22 sienų" — 22 ends in 2 and 22%100 != 12, so it's dauginis.
 *
 * Usage: ltPlural(n, 'siena', 'sienos', 'sienų')
 *        ltPlural(2, 'eilutė', 'eilutės', 'eilučių') → "eilutės"
 */

export function ltPlural(n, singular, paucal, plural) {
  const num = Math.abs(Math.floor(Number(n) || 0));
  const last = num % 10;
  const lastTwo = num % 100;

  // Teens (10-19) and 0 → genitive plural
  if (lastTwo >= 10 && lastTwo <= 19) return plural;
  if (last === 0) return plural;

  // Single units (1, 21, 31, ...)
  if (last === 1) return singular;

  // 2-9 (excl. teens)
  return paucal;
}

/**
 * Format n with appropriate pluralisation: "1 siena", "5 sienų", "22 sienos".
 */
export function ltCount(n, singular, paucal, plural) {
  return `${n} ${ltPlural(n, singular, paucal, plural)}`;
}
