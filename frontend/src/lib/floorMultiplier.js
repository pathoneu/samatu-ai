// floorMultiplier — SM02 daugiabučių aukštų pakartojimas.
//
// Vartotojas įkelia 1 tipinio aukšto brėžinį ir nurodo "tai kartojasi × N aukštų".
// Kiekiai, plotai ir pozicijos parodomi/eksportuojami pagaugintame režime, bet
// originalūs duomenys nemutuojami — tai per-display multiplier'is.
//
// Default: 1 aukštas, t.y. multiplier = 1, jokio pokyčio.

export const MIN_FLOORS = 1;
export const MAX_FLOORS = 9;

export function getFloorCount(project) {
  const n = parseInt(project?.prielaidos?.aukstu_skaicius, 10);
  if (!Number.isFinite(n) || n < MIN_FLOORS) return 1;
  return Math.min(MAX_FLOORS, n);
}

export function isMultiFloor(project) {
  return getFloorCount(project) > 1;
}

// Multiply numeric kiekis on each row. Returns new array; preserves per-row
// fields (kaina/suma is left as-is — caller decides whether to recompute suma).
export function multiplyDarbai(darbai, floorCount) {
  if (!Array.isArray(darbai)) return [];
  if (!floorCount || floorCount <= 1) return darbai;
  return darbai.map(d => {
    const k = (d.kiekis || 0) * floorCount;
    return { ...d, kiekis: k, suma: k * (d.kaina || 0) };
  });
}

// Multiply santrauka totals (m², m, vnt.).
const _MULT_KEYS_SANTRAUKA = [
  'dazymo_plotas_total_m2', 'kampai_m_total', 'angokrasciu_gkp_m_total',
  'pasleptu_duru_staktu_m_total', 'nisu_metrai_total',
  'gkp_lubu_m2_total', 'gkp_lubu_virs_3m_m2_total',
  'pvc_grindys_m2_total', 'plyteles_grindys_m2_total',
  'plyteles_sienos_m2_total', 'isliginamasis_m2_total',
  'grindjuosciu_m_total', 'hidroizoliacijos_vnt',
];

export function multiplySantrauka(santrauka, floorCount) {
  if (!santrauka || !floorCount || floorCount <= 1) return santrauka;
  const out = { ...santrauka };
  for (const k of _MULT_KEYS_SANTRAUKA) {
    if (typeof out[k] === 'number') out[k] = out[k] * floorCount;
  }
  return out;
}

export function multiplyArea(m2, floorCount) {
  if (typeof m2 !== 'number' || !floorCount || floorCount <= 1) return m2;
  return m2 * floorCount;
}
