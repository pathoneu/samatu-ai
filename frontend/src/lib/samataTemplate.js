/**
 * samataTemplate.js — the contractor's own sąmata layout, on the client.
 *
 * Pure helpers over the rows `POST /api/projects/{id}/samata-render` returns
 * (backend `extractor/samata_template.render_samata`): HIS sections, HIS row
 * labels, and per row a fill state —
 *
 *   `_pildymas`  'uzpildyta'  a verified / ledgered number went in (`kiekis`)
 *                'pasiulymas' we have a number nobody checked (`_siulomas_kiekis`,
 *                             greyed — never the value)
 *                'tuscia'     the drawing cannot answer this row
 *   `_saltinio_id` the darbu_sarasas row ids that fed the cell
 *   `_sablono_eile` the template family key
 *
 * The rendered sheet is a VIEW: it is never stored. Everything the contractor
 * does on it is written back into `darbu_sarasas`, the one list every total,
 * export and recompute already reads:
 *
 *   • typing into a blank cell   → a hand-added `rnk-` row that CARRIES the
 *                                  family key (`_sablono_eile`), so the next
 *                                  render puts it back into his cell instead of
 *                                  „Kita (iš brėžinio)" (backend honours it);
 *   • „Teisinga ✓" on a suggestion → `user_verified_at` on the source rows —
 *                                  the same stamp Patikra writes, so it counts
 *                                  for the scorecard and the ground truth too;
 *   • a price                    → on the single source row, as in the table.
 *
 * Nothing here talks to the network (see samataTemplateApi.js) or to React.
 */

import { insertRowInSection, manualRowId, nextEilNr } from './darbuRows.js';
import { manualPricePatch } from './applyPriceList.js';

export const FILL = Object.freeze({
  DONE: 'uzpildyta',
  SUGGESTED: 'pasiulymas',
  EMPTY: 'tuscia',
});

/** Backend `EXTRA_SECTION` — rows of ours no family of his consumed. */
export const EXTRA_SECTION = 'Kita (iš brėžinio)';

const LAYOUT_KEY = 'samatu_samata_layout';
export const LAYOUT_PATHON = 'pathon';
export const LAYOUT_TEMPLATE = 'sablonas';

/** Which layout the Sąmata step shows. Per browser; falls back to Pathon. */
export function loadLayoutChoice() {
  try {
    const v = globalThis.localStorage?.getItem(LAYOUT_KEY);
    return v === LAYOUT_TEMPLATE ? LAYOUT_TEMPLATE : LAYOUT_PATHON;
  } catch {
    return LAYOUT_PATHON;
  }
}

/** True once he has picked a layout himself; until then the uploaded template is the default. */
export function hasLayoutChoice() {
  try {
    const v = globalThis.localStorage?.getItem(LAYOUT_KEY);
    return v === LAYOUT_TEMPLATE || v === LAYOUT_PATHON;
  } catch {
    return false;
  }
}

export function saveLayoutChoice(layout) {
  try {
    globalThis.localStorage?.setItem(
      LAYOUT_KEY, layout === LAYOUT_TEMPLATE ? LAYOUT_TEMPLATE : LAYOUT_PATHON);
  } catch { /* private window, quota — the choice just does not stick */ }
}

/** Rendered rows grouped in HIS order: [{ label, rows }], first-seen order. */
export function groupBySection(rows) {
  const out = [];
  const byLabel = new Map();
  for (const r of rows || []) {
    if (!r || typeof r !== 'object') continue;
    const label = String(r.skyrius || EXTRA_SECTION);
    let g = byLabel.get(label);
    if (!g) {
      g = { label, rows: [] };
      byLabel.set(label, g);
      out.push(g);
    }
    g.rows.push(r);
  }
  return out;
}

/** Mirrors backend `render_summary`, recomputed after local edits. */
export function summarize(rows) {
  const all = (rows || []).filter((r) => r && typeof r === 'object');
  const his = all.filter((r) => r._sablonas);
  const count = (state) => his.filter((r) => r._pildymas === state).length;
  return {
    eilutes: all.length,
    sablonoEilutes: his.length,
    kitosEilutes: all.length - his.length,
    uzpildyta: count(FILL.DONE),
    pasiulyta: count(FILL.SUGGESTED),
    tuscia: count(FILL.EMPTY),
  };
}

/** Sections for the export filter — every row counts, blank ones included. */
export function sectionsOf(rows) {
  return groupBySection(rows).map((g) => ({ name: g.label, count: g.rows.length }));
}

/** A darbu_sarasas row the contractor typed into one of his template cells. */
export function isTypedRow(row) {
  return Boolean(row && String(row.id || '').startsWith('rnk-') && row._sablono_eile);
}

/**
 * The typed row behind a rendered row, if that is what fills it: exactly one
 * source, and that source is a hand-typed template row. Otherwise null.
 */
export function typedSourceRow(templateRow, darbai) {
  const ids = Array.isArray(templateRow?._saltinio_id) ? templateRow._saltinio_id : [];
  if (ids.length !== 1) return null;
  const src = (darbai || []).find((r) => String(r?.id) === String(ids[0]));
  return isTypedRow(src) ? src : null;
}

/** May the contractor type a quantity straight into this cell? */
export function canTypeQuantity(templateRow, darbai) {
  if (!templateRow || !templateRow._sablonas) return false;
  if (templateRow._pildymas === FILL.EMPTY) return true;
  return typedSourceRow(templateRow, darbai) != null;
}

/** The single darbu_sarasas row a rendered row reads its price from, or null. */
export function singleSourceRow(templateRow, darbai) {
  const ids = Array.isArray(templateRow?._saltinio_id) ? templateRow._saltinio_id : [];
  if (ids.length !== 1) return null;
  return (darbai || []).find((r) => String(r?.id) === String(ids[0])) || null;
}

/**
 * Write a typed quantity into HIS cell. Returns the new darbu_sarasas.
 *
 * Blank cell → a new hand-added row inside his section, carrying the family
 * key; a cell he already typed → that row updated. A cell filled from OUR
 * computed rows is not typable here (fix the input in Patikra, or the row in
 * the Pathon layout) — throws, so a caller cannot silently overwrite a ledger.
 */
export function typeQuantity(darbai, templateRow, kiekis, { kaina, now, otherLabel } = {}) {
  const qty = Number(kiekis);
  if (!Number.isFinite(qty) || qty < 0) throw new Error('Invalid quantity');
  const stamp = now || new Date().toISOString();
  const existing = typedSourceRow(templateRow, darbai);
  if (existing) {
    const price = kaina != null ? Number(kaina) : Number(existing.kaina || 0);
    return (darbai || []).map((r) => (r === existing
      ? {
        ...r,
        kiekis: qty,
        kaina: price,
        suma: qty * price,
        manual_override: true,
        quantity_source: 'manual_override',
        manual_override_at: stamp,
        ...(kaina != null ? manualPricePatch(r, price) : {}),
      }
      : r));
  }
  if (templateRow?._pildymas !== FILL.EMPTY) {
    throw new Error('Cell is filled from computed rows');
  }
  const price = kaina != null ? Number(kaina) : Number(templateRow.kaina || 0);
  const row = {
    eil_nr: nextEilNr(darbai),
    id: manualRowId(),
    aprasymas: String(templateRow.aprasymas || ''),
    mato_vnt: templateRow.mato_vnt || templateRow.vnt || '',
    kiekis: qty,
    kaina: price,
    suma: qty * price,
    skyrius: String(templateRow.skyrius || otherLabel || EXTRA_SECTION),
    _sablono_eile: templateRow._sablono_eile,
    manual_override: true,
    quantity_source: 'manual_override',
    manual_override_at: stamp,
    confidence: 'high',
    ...(price > 0 ? { kaina_source: 'manual' } : {}),
  };
  return insertRowInSection(darbai, row.skyrius, row, otherLabel || EXTRA_SECTION);
}

/**
 * „Teisinga ✓" on a suggested cell: the contractor stands behind OUR number.
 * Stamps the source rows exactly as Patikra does; the next render fills the
 * cell because the rows are now verified.
 */
export function acceptSuggestion(darbai, templateRow, now) {
  const ids = new Set((templateRow?._saltinio_id || []).map(String));
  if (!ids.size) return darbai || [];
  const stamp = now || new Date().toISOString();
  return (darbai || []).map((r) => (ids.has(String(r?.id))
    ? {
      ...r,
      confidence: 'high',
      quantity_source: r.quantity_source || 'user_verified_ai',
      user_verified_at: stamp,
    }
    : r));
}

/** A price typed on a rendered row lands on its single source row. */
export function setPrice(darbai, templateRow, kaina) {
  const price = Number(kaina);
  if (!Number.isFinite(price) || price < 0) throw new Error('Invalid price');
  const src = singleSourceRow(templateRow, darbai);
  if (!src) throw new Error('No single source row');
  return (darbai || []).map((r) => (r === src
    ? { ...r, kaina: price, suma: (Number(r.kiekis) || 0) * price, ...manualPricePatch(r, price) }
    : r));
}

/**
 * A merged line of HIS whose source rows carry different prices, or only some
 * carry one: no single unit price, and the backend's `suma` is
 * Σ(quantity × that row's own price) (audit 2026-09-29, exports-money-1).
 */
function hasOwnAmount(r) {
  return Boolean(r?._suma_be_vieneto_kainos) && r.suma != null && Number.isFinite(Number(r.suma));
}

/**
 * The money on a rendered line: quantity × unit price (as the view always
 * computed it), or a merged line's own amount. null without a quantity or any
 * price.
 */
export function lineAmount(r) {
  if (!r || r.kiekis == null || r.kiekis === '') return null;
  if (hasOwnAmount(r)) return Number(r.suma);
  return r.kaina == null ? null : Number(r.kiekis) * Number(r.kaina);
}

/**
 * The rows `POST /generate-excel?layout=template` prints. Blank stays blank —
 * `kiekis: null`, no `suma` — the backend leaves that cell empty rather than
 * printing „0,00 €" to his client. A greyed suggestion is NOT exported. A
 * merged line without one unit price goes as `kaina: null` + its amount; the
 * backend prints Kaina blank and Suma as a value.
 */
export function exportRows(rows, allowedSkyriai = null) {
  const keep = (s) => !allowedSkyriai || allowedSkyriai.has(s);
  return (rows || [])
    .filter((r) => r && typeof r === 'object')
    .map((r, i) => {
      const skyrius = String(r.skyrius || EXTRA_SECTION);
      const kiekis = (r.kiekis == null || r.kiekis === '') ? null : Number(r.kiekis);
      const kaina = r.kaina == null ? null : Number(r.kaina);
      const own = kiekis != null && hasOwnAmount(r);
      return {
        nr: String(r.nr || r.eil_nr || i + 1),
        aprasymas: r.aprasymas || '',
        mato_vnt: r.mato_vnt || r.vnt || '',
        kiekis,
        kaina: own ? null : (kaina ?? 0),
        suma: kiekis == null ? null : (own ? Number(r.suma) : kiekis * (kaina ?? 0)),
        skyrius,
        confidence: r.confidence || 'medium',
        ...(own && r._dalis_be_kainos ? { _dalis_be_kainos: true } : {}),
      };
    })
    .filter((r) => keep(r.skyrius));
}

/**
 * Does an exported line still need a price? A merged line counts when part of
 * its quantity is unpriced, not when it is fully priced at several prices.
 */
export function lacksPrice(r) {
  if (r?._dalis_be_kainos) return true;
  if (r?.kaina == null && Number(r?.suma) > 0) return false;
  return !(Number(r?.kaina) > 0);
}

/** An exported line × the floor count (SM02). Blank stays blank. */
export function scaleExportRow(r, factor) {
  if (r?.kiekis == null) return r;
  return {
    ...r,
    kiekis: r.kiekis * factor,
    suma: r.kaina == null ? (r.suma == null ? null : r.suma * factor)
      : r.kiekis * factor * (r.kaina || 0),
  };
}

/**
 * A cheap key for „did anything that changes the render move?" — ids,
 * quantities, prices and verification stamps. The render is a pure function
 * of these, so re-fetch only when this string changes.
 */
export function darbaiFingerprint(darbai) {
  return (darbai || [])
    .map((r) => [
      r?.id ?? '', r?.kiekis ?? '', r?.kaina ?? '', r?.user_verified_at ?? '',
      r?._review_status ?? '', r?.manual_override ? 1 : 0, r?._sablono_eile ?? '',
    ].join(':'))
    .join('|');
}
