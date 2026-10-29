/**
 * freeRereadApi — the landing path for a geometry-lane result (€0, no Vision).
 *
 * The product no longer offers a project-wide free re-read (2026-10-29 founder decision: a sąmata is a dated
 * document; the drawing is read once at upload). What remains is per-sheet reading from the viewer
 * (api/detect_run.py) and other viewer features that call the lane for one sheet. Their results arrive in
 * the same shape and land through `landFreeRereadResult`: merged by the re-read's rules, the rows rebuilt on
 * the merged rooms through the same /recompute-interior path a room edit takes. If the rebuild fails NOTHING
 * is returned to save — half a re-read (new rooms under old rows) is worse than none.
 */

import { saveRoomEdit } from '@/lib/roomSheetApi';
import { mergeDarbuSarasasEdits } from '@/lib/mergeDarbuSarasas';
import { mergeFreeReread } from '@/lib/freeReread';
import { withChanges } from '@/lib/changeSummary';

/**
 * A geometry-lane result (a finished /detect-run job) landed on the stored project: merged by the re-read's
 * rules, the rows rebuilt on the merged rooms. Nothing to save on failure.
 */
export async function landFreeRereadResult(base, result) {
  const { project: merged, diff } = mergeFreeReread(base, result);
  if (!merged) {
    const err = new Error('lane_failed');
    err.code = 'lane_failed';
    throw err;
  }
  const re = await saveRoomEdit(merged, merged.patalpos);
  const notes = [];
  const project = {
    ...merged,
    ...re,
    name: base.name,
    company_name: base.company_name,
    vat_rate: base.vat_rate,
    _overrides: merged._overrides,
    _apimtis: merged._apimtis,
    _per_room_overrides: merged._per_room_overrides,
    // the lane's records as the re-read merged them — a recompute answer carrying an older copy never wins
    _meta: {
      ...(merged._meta || {}),
      ...(re._meta || {}),
      geometrija: merged._meta?.geometrija,
      ...(merged._meta?.lenteles !== undefined ? { lenteles: merged._meta.lenteles } : {}),
      ...(merged._meta?.zonos !== undefined ? { zonos: merged._meta.zonos } : {}),
    },
    _reread_diff: diff,
    _geometrija_perskaityta_at: merged._geometrija_perskaityta_at,
    darbu_sarasas: mergeDarbuSarasasEdits(re.darbu_sarasas, base.darbu_sarasas, notes),
  };
  // „Kas pasikeitė" (Pathon v3 W4-A): the rows and the reads this read moved, beside its rooms
  project._reread_diff = withChanges(diff, base, project);
  return { project, diff: project._reread_diff, santrauka: result.santrauka || null };
}
