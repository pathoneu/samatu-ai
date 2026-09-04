/**
 * workFamilies — „Ką skaičiuoti?" (design „Rimo kelionė" §E1).
 *
 * Five families a contractor recognises, mapped onto the section names the
 * builder actually emits. Everything is on by default; unticking one means
 * „tų eilučių sąmatoje nebus", and this module is what makes that sentence
 * true instead of decorative.
 *
 * TWO RULES, both about not surprising him:
 *
 * 1. **An unmatched section is always KEPT.** A family removes only sections it
 *    recognises. „Ventiliacijos darbai", „Pridėtiniai elementai" and anything a
 *    future builder invents belong to no family, so no checkbox can silently
 *    delete them. Removing rows nobody asked about is far worse than leaving a
 *    section he has to delete by hand.
 * 2. **Materials follow their work.** A „Medžiagos" row carries
 *    `susijes_darbas` — the work line it was bought for. Dropping „Santechnika"
 *    while leaving its silicone and pipe fittings in the shopping list would
 *    bill materials for work that is not in the sąmata.
 *
 * Pure and total: no i18n, no DOM, no project blob — section strings in,
 * decisions out. Covered by workFamilies.test.js.
 */

/** The five families, in the order the upload screen lists them. */
export const WORK_FAMILIES = ['apdaila', 'grindys', 'plyteles', 'santechnika', 'elektra'];

// Matched case-insensitively against the row's `skyrius` (or `kategorija`).
// Deliberately narrow: a pattern that is not certain about its family is not
// here, and its section survives every choice.
const FAMILY_SECTION_PATTERNS = {
  apdaila: [/sien/i, /lub/i, /glaist/i, /dažym/i, /dazym/i, /gkp/i, /gipso/i, /tapet/i],
  grindys: [/grind/i, /parket/i, /laminat/i],
  plyteles: [/plytel/i],
  santechnika: [/santechnik/i],
  elektra: [/elektr/i],
};

/** The family a section belongs to, or null when it belongs to none. */
export function sectionFamily(section) {
  const s = String(section || '');
  if (!s) return null;
  for (const family of WORK_FAMILIES) {
    if (FAMILY_SECTION_PATTERNS[family].some((re) => re.test(s))) return family;
  }
  return null;
}

const rowSectionOf = (row) => row?.skyrius || row?.kategorija || '';

/**
 * Drop the rows belonging to families the contractor unticked.
 *
 * @param {Array<object>} rows      darbu_sarasas
 * @param {Array<string>} selected  the families still ticked
 * @returns {Array<object>} a new array; the input is never mutated
 */
export function filterRowsByFamilies(rows, selected) {
  const keep = new Set(Array.isArray(selected) ? selected : WORK_FAMILIES);
  // Nothing unticked → hand back exactly what came in, including a non-array.
  // The call site spreads the result onto the project, so returning [] for an
  // absent list would replace "no list yet" with "an empty sąmata".
  if (WORK_FAMILIES.every((f) => keep.has(f))) return rows;
  const list = Array.isArray(rows) ? rows.filter(Boolean) : [];

  const dropped = [];
  const survivors = list.filter((row) => {
    const family = sectionFamily(rowSectionOf(row));
    if (family && !keep.has(family)) { dropped.push(row); return false; }
    return true;
  });

  // Rule 2: a material bought for a dropped work line goes with it.
  const droppedWork = new Set(
    dropped.map((r) => String(r.aprasymas || '').trim().toLowerCase()).filter(Boolean));
  if (droppedWork.size === 0) return survivors;
  return survivors.filter((row) => {
    const parent = String(row?.susijes_darbas || '').trim().toLowerCase();
    return !(parent && droppedWork.has(parent));
  });
}

/** How many rows unticking these families would remove — for the live hint. */
export function countRowsRemoved(rows, selected) {
  const before = Array.isArray(rows) ? rows.filter(Boolean).length : 0;
  return before - filterRowsByFamilies(rows, selected).length;
}
