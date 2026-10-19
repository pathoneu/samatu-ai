/**
 * Packaging beside a material quantity (Pathon v3 W5-E, E6; CLAUDE.md §1.10 „round up to full containers",
 * §1.11 `bags_25kg = CEILING(putty_kg / 25)`): „17 maišų po 25 kg" beside the putty kilograms, „7 kibirai po
 * 10 l" beside the paint and primer litres. A note only — the kilograms and litres on the row are unchanged,
 * nothing is priced by it. The container sizes are visible assumptions in Nustatymai (`_overrides`).
 */
export const DEFAULT_BAG_KG = 25;       // CLAUDE.md §1.11
export const DEFAULT_BUCKET_L = 10;     // a visible assumption in Nustatymai — he sets his own
export const BAG_KEY = 'pakuote_maiso_kg';
export const BUCKET_KEY = 'pakuote_kibiro_l';
export const BAG_RANGE = [1, 50];
export const BUCKET_RANGE = [0.5, 30];

const num = (v) => {
  const n = typeof v === 'string' ? Number(v.replace(',', '.')) : Number(v);
  return Number.isFinite(n) ? n : null;
};

const inRange = (v, [lo, hi]) => v != null && v >= lo && v <= hi;

/** The container sizes he set in Nustatymai, else the defaults. */
export function packagingSizes(overrides) {
  const o = overrides && typeof overrides === 'object' ? overrides : {};
  const bag = num(o[BAG_KEY]);
  const bucket = num(o[BUCKET_KEY]);
  return {
    bagKg: inRange(bag, BAG_RANGE) ? bag : DEFAULT_BAG_KG,
    bucketL: inRange(bucket, BUCKET_RANGE) ? bucket : DEFAULT_BUCKET_L,
  };
}

/** LT number agreement: 1 maišas · 2–9 maišai · 10–20, 30… maišų (the same for kibiras). */
function agree(n, one, few, many) {
  const a = n % 100;
  const b = n % 10;
  if (b === 1 && a !== 11) return one;
  if (b >= 2 && b <= 9 && !(a >= 12 && a <= 19)) return few;
  return many;
}

const ltSize = (v) => String(Math.round(v * 100) / 100).replace('.', ',');

function unitOf(row) {
  return String(row?.mato_vnt || row?.vnt || '').trim().toLowerCase().replace(/\.$/, '');
}

function labelOf(row) {
  return String(row?.aprasymas || row?.pavadinimas || '').toLowerCase();
}

/**
 * „17 maišų po 25 kg" / „7 kibirai po 10 l", or null for a row that is not bagged putty or tinned paint and
 * primer (or has no quantity).
 */
export function packagingNote(row, sizes = packagingSizes()) {
  const qty = num(row?.kiekis);
  if (qty == null || qty <= 0) return null;
  const unit = unitOf(row);
  const label = labelOf(row);
  if (unit === 'kg' && /glaist/.test(label)) {
    const n = Math.ceil(qty / sizes.bagKg - 1e-9);
    return `${n} ${agree(n, 'maišas', 'maišai', 'maišų')} po ${ltSize(sizes.bagKg)} kg`;
  }
  if ((unit === 'l' || unit === 'ltr') && /(dažai|dažų|gruntas|grunto)/.test(label)) {
    const n = Math.ceil(qty / sizes.bucketL - 1e-9);
    return `${n} ${agree(n, 'kibiras', 'kibirai', 'kibirų')} po ${ltSize(sizes.bucketL)} l`;
  }
  return null;
}
