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

/**
 * A durable id for a HAND-ADDED row (2026-09-02, Patikra P0).
 *
 * Every computed row carries a hash of its section + label (backend
 * `extractor/position_id.py`), which is what the recompute merge now matches on
 * first. A hand-added row is never produced by that builder, so it needs no
 * agreement with the hash — it needs to be unique and to survive every rebuild
 * in the row object the merge carries forward. Hence a random id under its own
 * `rnk-` (rankinė) prefix: two rows both called „Nauja eilutė" in one section
 * stay distinguishable, and a hand-typed label that happens to equal a computed
 * one cannot silently inherit that row's identity — it falls through to the
 * label passes exactly as it does today.
 */
export function manualRowId() {
  const rnd = globalThis.crypto?.randomUUID
    ? globalThis.crypto.randomUUID().replace(/-/g, '').slice(0, 12)
    : Math.random().toString(16).slice(2, 10) + Date.now().toString(16).slice(-4);
  return `rnk-${rnd}`;
}
