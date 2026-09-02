/**
 * stretchCeiling — the per-room "įtempiamos lubos" assumption (2026-09-02, F1).
 *
 * A stretch ceiling is a separate trade: a membrane stretched under a raw slab.
 * None of the ceiling glaistymas / gruntavimas / dažymas / šlifavimas happens
 * under it, so the backend drops those m² from the sąmata (both the iki-3m and
 * virš-3m tiers). Lubų karnizas, LED nišos, GKP lubos and grindjuostės are
 * deliberately NOT affected — the founder scoped this to the paint only.
 *
 * Shape: `assumptions.stretch_ceiling_override = { [roomNr]: 1 | 0 }`.
 * 1 = įtempiamos, 0 = dažomos, ABSENT = dažomos. The absent case is what makes
 * this safe to ship: a project nobody toggles produces the same numbers it did
 * before the feature existed.
 *
 * Mirrors `extractor/vision_call._stretch_ceiling_nrs` — keep the two readers
 * agreeing on what counts as "on" (>= 0.5, tolerant of "1"/true/1.0).
 */

/** Read the map off an assumptions blob, tolerating null/undefined/garbage. */
export function stretchCeilingMap(assumptions) {
  const raw = assumptions && assumptions.stretch_ceiling_override;
  return (raw && typeof raw === 'object' && !Array.isArray(raw)) ? raw : {};
}

/** Is THIS room's ceiling a stretch ceiling? Absent key → no (dažomos). */
export function isStretchCeiling(assumptions, roomNr) {
  const v = stretchCeilingMap(assumptions)[roomNr];
  if (v == null || v === '') return false;
  const n = typeof v === 'boolean' ? (v ? 1 : 0) : Number(v);
  return Number.isFinite(n) && n >= 0.5;
}

/**
 * Next assumptions blob with `roomNr` flipped. Returns a NEW object (React
 * state), never mutates, and always writes an explicit 0 rather than deleting
 * the key — an explicit "dažomos" is a decision the user made and the backend
 * treats it identically to absence.
 */
export function withStretchCeiling(assumptions, roomNr, stretch) {
  const safe = assumptions || {};
  return {
    ...safe,
    stretch_ceiling_override: {
      ...stretchCeilingMap(safe),
      [roomNr]: stretch ? 1 : 0,
    },
  };
}
