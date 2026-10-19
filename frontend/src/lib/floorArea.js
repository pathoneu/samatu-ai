/**
 * The project's floor area outside the billed lines — the room list's header, „Patalpų suvestinė",
 * the shared page, the room grid (Pathon v3 W1-F, 2026-10-18).
 *
 * After „Sujungti" (api/room_outline.py) the kept room bills both table rows (`plotas_m2 = a + b`) and the
 * absorbed room keeps its own row, marked `_sujungta_i: <kept nr>` (backend `scope.MERGED_INTO_KEY`). A plain
 * Σ plotas_m2 then counted the absorbed room twice — demo-objektas_h after 05 → 04 read 178,77 m² (35,50 twice)
 * while the billed ceiling stayed 143,27. The backend's own totals skip it the same way
 * (`scope.is_absorbed`, `sanity_checks._counted`).
 */

/** A room merged into another: its area and openings are counted in the room it joined. */
export function isMergedAway(room) {
  return !!(room && room._sujungta_i);
}

/** Σ plotas_m2 of the rooms a project total adds (a merged-away room is inside the room it joined). */
export function floorAreaTotal(rooms) {
  let sum = 0;
  for (const r of rooms || []) {
    if (!r || isMergedAway(r)) continue;
    const v = Number(r.plotas_m2);
    if (Number.isFinite(v)) sum += v;
  }
  return sum;
}
