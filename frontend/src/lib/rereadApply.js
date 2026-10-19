/**
 * rereadApply — the ONE path a fresh read of the drawing takes into a stored
 * project: merged (lib/mergeReextract.js: verified rooms and the facts he set
 * himself stay, prices ride on the rebuilt rows, the diff is recorded), its
 * rows rebuilt on the merged rooms through the same /recompute-interior path a
 * room edit uses, then saved.
 *
 * Used by the re-read card (components/project/ReextractButton.jsx) for a read
 * that arrives while it waits, and by the project page
 * (hooks/useHeldReread.js) for a read the server held while no page waited —
 * moved here from the card on 2026-10-03 so both take the same path.
 */

import { getProject, updateProject } from '@/lib/projectStore';
import { mergeReextract } from '@/lib/mergeReextract';
import { mergeDarbuSarasasEdits } from '@/lib/mergeDarbuSarasas';
import { saveRoomEdit } from '@/lib/roomSheetApi';
import { recordPilot } from '@/lib/telemetry';
import { withChanges } from '@/lib/changeSummary';
import { forgetRereadRun } from '@/lib/heldReread';

/**
 * The stored project after a fresh read: merged, then its rows rebuilt on the
 * merged rooms (the fresh read built them on its own rooms — without the facts
 * he set, without the project's scope). If the rebuild fails, the merged
 * project is still a complete, honest state: fresh rows with his prices.
 */
export async function projectAfterReread(base, result) {
  const { project: merged } = mergeReextract(base, result);
  try {
    const re = await saveRoomEdit(merged, merged.patalpos);
    const notes = [];
    const out = {
      ...merged,
      ...re,
      name: base.name,
      company_name: base.company_name,
      vat_rate: base.vat_rate,
      _overrides: merged._overrides,
      _apimtis: merged._apimtis,
      _per_room_overrides: merged._per_room_overrides,
      _reextracted_at: merged._reextracted_at,
      _reread_diff: merged._reread_diff,
      darbu_sarasas: mergeDarbuSarasasEdits(re.darbu_sarasas, base.darbu_sarasas, notes),
    };
    // „Kas pasikeitė" (Pathon v3 W4-A): the rows and the reads this read moved, beside its rooms
    return { ...out, _reread_diff: withChanges(merged._reread_diff, base, out) };
  } catch (e) {
    console.warn('[reextract] rebuilding rows on the merged rooms failed — keeping the merged read:', e);
    return { ...merged, _reread_diff: withChanges(merged._reread_diff, base, merged) };
  }
}

// Runs being merged right now on this page load — the card and the page never
// merge the same run twice, even while the first merge is still rebuilding.
const applying = new Set();

/**
 * Merge a finished re-read into the stored project and save it — once per run.
 *
 * The base is the CURRENT stored project, read at merge time (2026-07-28
 * audit: a render-time snapshot rolled back everything he changed while the
 * read ran). The merged project carries `_reread_run_id`, so a run it already
 * carries is never merged again.
 *
 * @param {string} projectId
 * @param {object} result   the fresh read (stream `done` result or the held one)
 * @param {{runId?: string|null, fallback?: object|null}} opts
 *   `fallback` — the project to merge into when the store has none.
 * @returns {Promise<object|null>} the saved project, or null when this run was
 *   already merged (or is being merged) or there is no project to merge into
 */
export async function applyRereadResult(projectId, result, { runId = null, fallback = null } = {}) {
  if (runId && applying.has(runId)) return null;
  const base = getProject(projectId) || fallback;
  if (!base) return null;
  if (runId && base._reread_run_id === runId) {
    forgetRereadRun(projectId, runId);
    return null;
  }
  if (runId) applying.add(runId);
  try {
    const merged = await projectAfterReread(base, result);
    const saved = runId ? { ...merged, _reread_run_id: runId } : merged;
    recordPilot(projectId, 'reread', { kind: 'reread', id: String((saved._reread_diff?.changed || []).length) });
    updateProject(projectId, saved, { versionSource: 'perskaityta' });
    if (runId) forgetRereadRun(projectId, runId);
    return saved;
  } finally {
    if (runId) applying.delete(runId);
  }
}
