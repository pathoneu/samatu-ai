/**
 * roomKampai — the corner length (kampai, m) a room grid may show: the
 * backend's own per-room value and nothing else (2026-10-03 review).
 *
 * RoomsGrid used to compute its own „perimetras + 4 × aukštis" next to the
 * backend's universal_rules.calc_room_quantities (which also counts the
 * openings' edges, partition junctions and his „Dažymo kampai" choice), so the
 * same room showed two different corner figures. The backend writes its value
 * onto the room as `kampai_m` (and the Vision-schema alias `kampu_metrai`). A
 * room without one — a legacy blob, a room added by hand, a room whose inputs
 * he just changed and the backend has not recomputed — shows nothing.
 *
 * Relative imports only: this module runs under `node --test`.
 */

function finite(v) {
  if (typeof v === 'number') return Number.isFinite(v) ? v : null;
  if (typeof v === 'string' && v.trim() !== '') {
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

/** The backend's corner length for `room` (m), or null when it carries none. */
export function backendKampaiM(room) {
  if (!room || typeof room !== 'object') return null;
  const own = finite(room.kampai_m);
  return own != null ? own : finite(room.kampu_metrai);
}

// What the backend computed the corner length from that the room grid can edit.
const KAMPAI_INPUTS = ['perimetras_m', 'lubu_aukstis_m', 'paskirtis', 'plotas_m2'];

/** Did an edit change an input the backend's corner length was computed from? */
export function kampaiInputsChanged(before, after) {
  return KAMPAI_INPUTS.some((k) => {
    const a = before?.[k];
    const b = after?.[k];
    const na = finite(a);
    const nb = finite(b);
    if (na != null || nb != null) return na !== nb;
    return (a ?? null) !== (b ?? null);
  });
}

/** `room` without the backend's corner length (it no longer describes the room). */
export function withoutBackendKampai(room) {
  const { kampai_m: _k, kampu_metrai: _m, ...rest } = room || {};
  return rest;
}

/**
 * The grid's total: the sum when EVERY room carries the backend's value, else
 * null — a sum over some of the rooms is a different number, not a total.
 */
export function kampaiTotalM(rooms) {
  if (!Array.isArray(rooms) || rooms.length === 0) return null;
  let sum = 0;
  for (const r of rooms) {
    const v = backendKampaiM(r);
    if (v == null) return null;
    sum += v;
  }
  return sum;
}
