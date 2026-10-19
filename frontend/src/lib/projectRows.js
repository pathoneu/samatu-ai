// projectRows — „Projektai" as status rows (Pathon v3 W5-C, C6 / coverage #216): per project its name, its
// state in plain words, the last change, the totals, and the ONE next step with where it goes. Rimas reads
// „Liko patikrinti 3 kambarius → Tęsti patikrą" instead of a pill saying „PARUOŠTA" on every card.
//
// Pure: Dashboard / ProjectRow render the keys. Counts come off the stored blob (rooms' `user_verified_at`,
// rows with a quantity and no price — lib/exportLines.rowNeedsPrice, the Siųsti step's own rule).

import { rowNeedsPrice } from './exportLines.js';

const READY = new Set(['ready', 'ok', undefined, null, '']);

function roomsToCheck(project) {
  const rooms = Array.isArray(project?.patalpos) ? project.patalpos : [];
  // a room merged into another is checked with it
  return rooms.filter((r) => r && r.nr != null && !r._sujungta_i && !r.user_verified_at).length;
}

function lastChangeOf(project) {
  const raw = project?.updated_at || project?.updated_date || project?.created_date || project?.created_at || null;
  if (!raw) return null;
  const d = new Date(raw);
  return Number.isNaN(d.getTime()) ? null : d;
}

/**
 * → {
 *   id, name, company,
 *   state: 'processing' | 'error' | 'check' | 'prices' | 'ready',
 *   stateParams: { count },          // rooms to check / rows without a price
 *   lastChange: Date | null,
 *   totals: { net, gross, rooms, rows },
 *   next: { key, href } | null,      // the one next step (null while it is still being read)
 *   openable: boolean,
 * }
 */
export function projectRow(project, vatRate = 21) {
  const id = project?.id;
  const rows = Array.isArray(project?.darbu_sarasas) ? project.darbu_sarasas : [];
  const rooms = Array.isArray(project?.patalpos) ? project.patalpos.filter((r) => r && !r._sujungta_i).length : 0;
  const net = Number(project?.total_value) || rows.reduce((s, it) => s + (Number(it?.kiekis) || 0) * (Number(it?.kaina) || 0), 0);
  const totals = {
    net,
    gross: net ? net * (1 + (Number(vatRate) || 0) / 100) : 0,
    rooms,
    rows: rows.length || Number(project?.total_rows) || 0,
  };
  const base = { id, name: project?.name || '', company: project?.company_name || '', lastChange: lastChangeOf(project), totals };

  if (project?.status === 'processing') {
    return { ...base, state: 'processing', stateParams: {}, next: null, openable: false };
  }
  if (!READY.has(project?.status)) {
    return { ...base, state: 'error', stateParams: {}, next: { key: 'newUpload', href: '/new-project' }, openable: false };
  }
  const toCheck = roomsToCheck(project);
  if (toCheck > 0) {
    return { ...base, state: 'check', stateParams: { count: toCheck }, next: { key: 'check', href: `/project/${id}/patikra` }, openable: true };
  }
  const noPrice = rows.filter((r) => rowNeedsPrice(r)).length;
  if (noPrice > 0) {
    return { ...base, state: 'prices', stateParams: { count: noPrice }, next: { key: 'prices', href: `/project/${id}?step=samata` }, openable: true };
  }
  return { ...base, state: 'ready', stateParams: {}, next: { key: 'send', href: `/project/${id}?step=siusti` }, openable: true };
}

/**
 * A euro amount for a row of text: grouped with a THIN space (U+2009) — the locale's narrow no-break space
 * renders a full cell wide in the mono font (the „gap inside numbers"), and the row uses tabular figures of
 * the interface font instead. Whole euros; the comma decimal for cents when asked.
 */
export function rowEuro(value, { cents = false } = {}) {
  const n = Number(value) || 0;
  const s = n.toLocaleString('lt-LT', { minimumFractionDigits: cents ? 2 : 0, maximumFractionDigits: cents ? 2 : 0 });
  return s.replace(/[  \s]/g, ' ');
}
