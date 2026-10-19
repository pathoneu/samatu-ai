/**
 * freeRereadApi — the network half of the free re-read (see lib/freeReread.js
 * for what it may change). GET asks whether the stored project can and should
 * be read again for free; `runFreeReread` reads, merges, and rebuilds the rows
 * on the merged rooms through the same /recompute-interior path a room edit
 * takes. If the rebuild fails NOTHING is returned to save — half a re-read
 * (new rooms under old rows) is worse than none.
 */

import { API_BASE } from '@/lib/apiBase';
import { saveRoomEdit } from '@/lib/roomSheetApi';
import { mergeDarbuSarasasEdits } from '@/lib/mergeDarbuSarasas';
import { mergeFreeReread } from '@/lib/freeReread';
import { withChanges } from '@/lib/changeSummary';

const url = (projectId) => `${API_BASE}/api/projects/${encodeURIComponent(projectId)}/free-reread`;

async function readJson(res) {
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(body.detail || `HTTP ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return body;
}

/** `{available, needed, versija, projekto_versija, reason}` */
export async function fetchFreeRereadStatus(projectId, { signal } = {}) {
  return readJson(await fetch(url(projectId), { credentials: 'include', signal }));
}

/** `{ project, diff, santrauka }` — the project to save, what changed, and the lane's counts. */
export async function runFreeReread(base) {
  const result = await readJson(await fetch(url(base.id), {
    method: 'POST', credentials: 'include', signal: AbortSignal.timeout(180_000),
  }));
  return landFreeRereadResult(base, result);
}

/**
 * A free re-read's answer (POST /free-reread, or a finished /detect-run job — the same shape) landed on the
 * stored project: merged by the re-read's rules, the rows rebuilt on the merged rooms. Nothing to save on failure.
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
