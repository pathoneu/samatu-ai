/**
 * priceListCsv — the browser-side kainynas importer for .csv files.
 *
 * Moved out of pages/PriceLists.jsx (2026-09-30) so it can be tested; the page
 * imports it. The .xlsx twin lives server-side in backend/api/price_lists.py
 * (`_read_price_cell`, `parse_xlsx_items`) — the two must read a cell the same
 * way, and one made-up list (backend/tests/fixtures_price_list/) checks both.
 *
 * Price cells (exports-money-3): the old reader kept every digit in the cell,
 * so "15 €/m2" became 152, "8 €/m3" 83 and "1.234,56" 1.234. Now the LEADING
 * number is read on its own — LT decimal comma, a plain/thin/no-break space or
 * a dot as the thousands separator — and whatever follows must be a currency
 * and/or a unit. Anything else is not a price: the row is skipped and named.
 */

const SPACES = '    ';
const NUMBER_RE = /^[+-]?\d[\d.,    ]*/;
const TAIL_RE = /^(?:(?:€|eur(?:ų|u|ai)?)\.?)?\s*(?:(?:\/\s*|už\s+)?(m²|m³|m2|m3|m|vnt|kompl|kg|t|l|val|h|d\.d)(\.?))?$/iu;

function readNumber(text) {
  let s = text.trim();
  while (s && (SPACES.includes(s.at(-1)) || s.at(-1) === '.' || s.at(-1) === ',')) s = s.slice(0, -1);
  s = s.replace(/[   ]/g, ' ');
  if (s.includes(' ')) {
    // A space is only ever a thousands separator: "1 234,56", never "15 2".
    if (!/^[+-]?\d{1,3}(?: \d{3})+(?:[.,]\d+)?$/.test(s)) return null;
    s = s.replace(/ /g, '');
  }
  if (s.includes(',') && s.includes('.')) {
    // Both present: the LAST one is the decimal separator.
    s = s.lastIndexOf(',') > s.lastIndexOf('.') ? s.replace(/\./g, '') : s.replace(/,/g, '');
  }
  s = s.replace(',', '.');
  if (!/^[+-]?\d+(?:\.\d+)?$/.test(s)) return null;
  const f = Number(s);
  return Number.isFinite(f) ? f : null;
}

/**
 * Read one price cell → { price, unit, status }.
 * status: 'ok' | 'empty' (nothing typed) | 'unreadable' (typed, but not a price).
 * `unit` is the unit written inside the cell („12,5 Eur/m²" → 'm²'), else null.
 */
export function parseLtPrice(raw) {
  if (typeof raw === 'number') {
    return Number.isFinite(raw)
      ? { price: raw, unit: null, status: 'ok' }
      : { price: null, unit: null, status: 'unreadable' };
  }
  const s = String(raw ?? '').trim();
  if (!s) return { price: null, unit: null, status: 'empty' };
  const m = NUMBER_RE.exec(s);
  if (!m) return { price: null, unit: null, status: 'unreadable' };
  const tail = TAIL_RE.exec(s.slice(m[0].length).trim());
  const price = readNumber(m[0]);
  if (!tail || price === null) return { price: null, unit: null, status: 'unreadable' };
  return { price, unit: tail[1] ? tail[1] + tail[2] : null, status: 'ok' };
}

/** A header cell's comparison key — the backend's `_norm_header`. */
function normHeader(h) {
  return String(h || '').normalize('NFKD').replace(/[̀-ͯ]/g, '')
    .toLowerCase().replace(/[^\p{L}\p{N}]/gu, '');
}

// Same vocabulary as the backend's `_HEADER_MAP`, keyed the same way, so
// „Darbas", „Mato vnt." and „Aprašymas" work in a CSV as they do in .xlsx.
const HEADER_MAP = {
  skyrius: 'skyrius', kategorija: 'skyrius',
  aprasymas: 'aprasymas', pavadinimas: 'aprasymas', darbas: 'aprasymas',
  vnt: 'mato_vnt', matovnt: 'mato_vnt', matas: 'mato_vnt', matovienetas: 'mato_vnt', unit: 'mato_vnt',
  kaina: 'kaina', kainaeur: 'kaina', kainaeurvnt: 'kaina', ikaina: 'kaina', price: 'kaina',
};

// Sprint §30 (2026-04-29): CSV parser. Supports both `,` and `;` separators
// (LT Excel uses `;` by default). Quoted fields with embedded commas. UTF-8 BOM
// stripped. First row treated as headers.
//
// Returns { items, skippedRows, problemRows } — the same shape the .xlsx
// endpoint returns ({items, skipped_rows, problem_rows}). problemRows names
// each row skipped for an unreadable price: { row (file line), aprasymas, kaina }.
export function parseCsv(text) {
  // Detect separator from first non-empty line
  const cleaned = text.replace(/^﻿/, '');
  const firstLine = cleaned.split(/\r?\n/).find(l => l.trim()) || '';
  const sep = firstLine.includes(';') && !firstLine.includes(',') ? ';'
            : firstLine.split(',').length >= firstLine.split(';').length ? ','
            : ';';

  const rows = [];
  let cur = [];
  let field = '';
  let inQuotes = false;
  for (let i = 0; i < cleaned.length; i++) {
    const ch = cleaned[i];
    if (inQuotes) {
      if (ch === '"' && cleaned[i + 1] === '"') { field += '"'; i++; }
      else if (ch === '"') { inQuotes = false; }
      else { field += ch; }
    } else {
      if (ch === '"') inQuotes = true;
      else if (ch === sep) { cur.push(field); field = ''; }
      else if (ch === '\n' || ch === '\r') {
        // An empty line still pushes an (empty) row, so a row's index + 1
        // stays its line number in the file.
        cur.push(field); rows.push(cur); cur = []; field = '';
        if (ch === '\r' && cleaned[i + 1] === '\n') i++;
      }
      else { field += ch; }
    }
  }
  if (field || cur.length) { cur.push(field); rows.push(cur); }
  const headerAt = rows.findIndex(r => r.some(c => c.trim()));
  if (headerAt < 0 || !rows.slice(headerAt + 1).some(r => r.some(c => c.trim()))) {
    throw new Error('CSV neturi duomenų eilučių');
  }

  const colIdx = {};
  rows[headerAt].forEach((h, i) => {
    const m = HEADER_MAP[normHeader(h)];
    if (m && colIdx[m] == null) colIdx[m] = i;
  });
  if (colIdx.aprasymas == null || colIdx.kaina == null) {
    throw new Error('Reikalingi stulpeliai: skyrius, aprasymas, vnt, kaina (suderinama su „Excel“ ar atsisiųstu CSV)');
  }

  const items = [];
  const problemRows = [];
  let skippedRows = 0;
  // A section heading on its own row („Dažymo darbai" with no price) names
  // the rows below it — the same rule as the .xlsx reader.
  let currentSection = '';
  for (let r = headerAt + 1; r < rows.length; r++) {
    const row = rows[r];
    if (!row || row.every(c => !c.trim())) continue;
    const cell = (i) => (i != null ? (row[i] || '').trim() : '');
    const aprasymas = cell(colIdx.aprasymas);
    const rawPrice = cell(colIdx.kaina);
    const { price, unit, status } = parseLtPrice(rawPrice);
    if (price === null) {
      const texts = row.map(c => c.trim()).filter(Boolean);
      if (aprasymas && texts.length === 1) currentSection = aprasymas.slice(0, 200);
      if (status === 'unreadable' && aprasymas) {
        problemRows.push({ row: r + 1, aprasymas: aprasymas.slice(0, 120), kaina: rawPrice.slice(0, 40) });
      }
      skippedRows += 1;
      continue;
    }
    if (!aprasymas) { skippedRows += 1; continue; }
    items.push({
      skyrius: cell(colIdx.skyrius) || currentSection || 'Kiti darbai',
      aprasymas,
      // The unit column first; a unit written in the price cell fills it
      // only when the column is empty.
      mato_vnt: cell(colIdx.mato_vnt) || unit || '',
      kaina: price,
    });
  }
  return { items, skippedRows, problemRows };
}

/**
 * The toast text naming the rows skipped for an unreadable price, or undefined
 * when there are none (what a toast's `description` expects). Takes `t` so it
 * stays translatable without importing i18n into lib/.
 */
export const UNREADABLE_ROWS_SHOWN = 5;

export function describeUnreadablePrices(problemRows, t) {
  const rows = (problemRows || []).filter(p => p && p.aprasymas);
  if (!rows.length) return undefined;
  const shown = rows.slice(0, UNREADABLE_ROWS_SHOWN)
    .map(p => t('priceLists.unreadableRow', { row: p.row, name: p.aprasymas, value: p.kaina }));
  if (rows.length > UNREADABLE_ROWS_SHOWN) {
    shown.push(t('priceLists.unreadableMore', { count: rows.length - UNREADABLE_ROWS_SHOWN }));
  }
  return t('priceLists.unreadableDescription', { rows: shown.join(' · ') });
}
