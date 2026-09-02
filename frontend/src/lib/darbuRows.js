/**
 * Pure helpers for darbu_sarasas row manipulation (contractor ask 2026-09-02:
 * "pridėti eilutę į bet kurį skyrių"). Kept out of ProjectMainView.jsx per the
 * repo convention — testable logic lives in lib/, the page keeps a thin call.
 */

/** Section label for a row — mirrors groupByCategory in ProjectMainView. */
export function rowSection(item, otherLabel) {
  return item.skyrius || item.kategorija || otherLabel;
}

/**
 * Insert `newRow` as the LAST row of section `cat` (right after the section's
 * current last row, so it renders inside the group). Unknown/empty section →
 * append at the end. Returns a new array; input is not mutated.
 */
export function insertRowInSection(darbai, cat, newRow, otherLabel) {
  const lastIdx = (darbai || []).reduce(
    (acc, item, i) => (rowSection(item, otherLabel) === cat ? i : acc),
    -1,
  );
  const at = lastIdx >= 0 ? lastIdx + 1 : (darbai || []).length;
  return [...(darbai || []).slice(0, at), newRow, ...(darbai || []).slice(at)];
}

/**
 * Next eil_nr for a manually added row: max existing + 1. Deletions leave
 * numbering gaps, so `length + 1` could collide with a live number.
 */
export function nextEilNr(darbai) {
  return (darbai || []).reduce((m, d) => Math.max(m, Number(d.eil_nr) || 0), 0) + 1;
}
