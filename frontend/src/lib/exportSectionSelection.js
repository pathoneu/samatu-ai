/**
 * exportSectionSelection — persistence for the pre-export skyrius picker.
 *
 * 2026-07-27 audit: the old format stored the INCLUDED section names. A skyrius
 * that appeared later (re-extraction, recompute, a symbol-count line landing in
 * "Matavimai") was therefore absent from the stored list and shipped UNCHECKED —
 * the export quietly lost a whole section of the sąmata.
 *
 * v2 stores the EXCLUDED names instead, so "not mentioned" means "include it"
 * and any new skyrius defaults in. `selectedFor()` derives the checked set from
 * the sections that actually exist right now, which removes the reconciliation
 * effect the old component needed entirely.
 */

export const EXPORT_SELECTION_VERSION = 2;

export const exportSelectionKey = (projectId) => `samatu_export_skyriai_${projectId}`;

/**
 * Read the persisted exclusions. Accepts both formats and never throws.
 *
 * v1 (a bare array of INCLUDED names) is deliberately migrated to "nothing
 * excluded": we cannot tell an explicit uncheck apart from a section that did
 * not exist when it was saved, and a silently missing export line is far worse
 * than a re-checked one the user sees in the modal before confirming.
 */
export function parseExcludedSections(raw) {
  if (!raw) return new Set();
  let parsed;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return new Set();
  }
  if (Array.isArray(parsed)) return new Set();            // v1 — see comment above
  if (parsed && typeof parsed === 'object' && Array.isArray(parsed.excluded)) {
    return new Set(parsed.excluded.filter((n) => typeof n === 'string'));
  }
  return new Set();
}

/**
 * The exclusions stored for one project. Never throws: a private window, a
 * blocked storage or a corrupt value all read as „nothing excluded".
 * (Shared by the export dialog and the Siųsti step's count, 2026-10-06.)
 */
export function loadExcludedSections(projectId, storage = globalThis.localStorage) {
  try {
    return parseExcludedSections(storage?.getItem(exportSelectionKey(projectId)));
  } catch {
    return new Set();
  }
}

export function serializeExcludedSections(excluded) {
  return JSON.stringify({
    v: EXPORT_SELECTION_VERSION,
    excluded: [...(excluded || [])],
  });
}

/** The checked set: every section that exists now and is not explicitly excluded. */
export function selectedFor(sectionNames, excluded) {
  const ex = excluded || new Set();
  return new Set((sectionNames || []).filter((n) => !ex.has(n)));
}

/** Flip one section between included and excluded. Returns a NEW Set. */
export function toggleSection(excluded, name) {
  const next = new Set(excluded || []);
  if (next.has(name)) next.delete(name); else next.add(name);
  return next;
}
