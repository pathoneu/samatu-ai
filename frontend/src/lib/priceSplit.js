/**
 * priceSplit — the few facts the kainynas matcher and the rinkiniai share
 * (togal-v2 W9): which row is a material, cent rounding, and the keys a price
 * from elsewhere must clear so a darbo + medžiagų split never describes a
 * price it no longer adds up to. Its own module so applyPriceList.js and
 * assemblyPricing.js do not import each other.
 */

export const SK_MEDZIAGOS = 'Medžiagos';

export function isMaterialRow(row) {
  return !!row?._medziaga || row?.skyrius === SK_MEDZIAGOS;
}

export function round2(v) {
  const n = Number(v);
  return Number.isFinite(n) ? Math.round((n + Number.EPSILON) * 100) / 100 : 0;
}

export const SPLIT_CLEARED = Object.freeze({
  kaina_darbo: undefined,
  kaina_medziagu: undefined,
  medziagos_kainoje: undefined,
});

export function hasSplit(row) {
  return !!row && (row.kaina_darbo !== undefined || row.kaina_medziagu !== undefined
    || row.medziagos_kainoje !== undefined);
}
