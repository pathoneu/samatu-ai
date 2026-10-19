// sheetRail — what the viewer's sheet rail shows (Togal-v2 W7, research §1 „Sheets").
//
// Every sheet gets a number, a name, a type and a discipline group. The automatic values come from
// the stored classification (`project.puslapiai[]`: tipas, pavadinimas — an AI reading of the title
// block, optionally `dalis` from the title-block code); the user's corrections live in
// `project.sheet_overrides = { [page]: { name?, type?, dalis? } }` and always win. „Atkurti
// automatinį" removes the override. Pure: no React, no storage — SheetRail.jsx renders it,
// InteriorWorkspace persists the overrides through updateProject.
//
// The backend's callout matcher (api/sheet_links.rail_sheets) applies the same overrides, so a
// renamed sheet is what a link's hover names.

import { PAGE_TYPE_LABELS } from './pageTypes.js';

// Discipline groups, in rail order. `dalis` codes are the LT project parts (page_classifier.Dalis);
// `types` are the classification's page types that belong to the group when no dalis was read.
export const DISCIPLINES = [
  { key: 'architektura', label: 'Architektūra ir interjeras', dalis: ['SA'],
    types: ['floor_plan', 'ceiling_plan', 'wall_elevation', 'section', 'eksplikacija', 'finish_schedule', 'door_window_schedule', 'facade', 'legend'] },
  { key: 'elektra', label: 'Elektra', dalis: ['E'], types: ['electrical'] },
  { key: 'santechnika', label: 'Vandentiekis ir nuotekos', dalis: ['VVN'], types: ['plumbing'] },
  { key: 'svok', label: 'Šildymas ir vėdinimas', dalis: ['ŠVOK', 'SVOK'], types: [] },
  { key: 'konstrukcijos', label: 'Konstrukcijos', dalis: ['SK'], types: ['structural', 'stogo_planas'] },
  { key: 'bendra', label: 'Bendroji dalis ir sklypas', dalis: ['BD', 'SP'], types: ['title_page', 'site_plan'] },
  { key: 'kita', label: 'Specifikacijos ir kita', dalis: [], types: [] },
];
const DISCIPLINE_BY_KEY = Object.fromEntries(DISCIPLINES.map((d) => [d.key, d]));

// The two rails' widths — SheetRail.jsx (`w-[232px]`) and TakeoffViewer's ThumbnailRail (`w-[148px]`); keep
// them in step with those classes.
export const SHEET_RAIL_WIDTH = 232;
export const THUMBNAIL_RAIL_WIDTH = 148;
// SheetRail mode="strip" (`w-14`)
export const SHEET_STRIP_WIDTH = 56;
const PANEL_GAP = 8;

/**
 * Where a panel floating at the drawing's top-left starts („Rasti panašius", the count types): right of the
 * open rail, never over it (2026-10-18 audit §4.6 item 4 — the review panel covered ~76 px of the sheet list).
 */
export function floatingPanelLeft({ railOpen, sheetRail, strip = false, toolRail = 0 }) {
  // Pathon v3 click model (W1-B): the tool cards float at the drawing's left edge — panels start right of them too
  const tools = toolRail > 0 ? toolRail + PANEL_GAP : 0;
  return sheetRailWidth({ railOpen, sheetRail, strip }) + PANEL_GAP + tools;
}

/** How wide the sheet list on the drawing's left is: the full rail, the 56 px strip, the thumbnails, or 0. */
export function sheetRailWidth({ railOpen, sheetRail, strip = false }) {
  // Pathon v3 frame (A4): with the full rail shut a sheet set still shows its 56 px strip
  if (!railOpen) return sheetRail && strip ? SHEET_STRIP_WIDTH : 0;
  return sheetRail ? SHEET_RAIL_WIDTH : THUMBNAIL_RAIL_WIDTH;
}

/** The type choices the rename editor offers: the classification's enum with its LT labels. */
export const SHEET_TYPE_OPTIONS = Object.entries(PAGE_TYPE_LABELS).map(([value, label]) => ({ value, label }));

export const DISCIPLINE_OPTIONS = DISCIPLINES.map(({ key, label }) => ({ value: key, label }));

export function disciplineLabel(key) {
  return DISCIPLINE_BY_KEY[key]?.label || DISCIPLINE_BY_KEY.kita.label;
}

export function sheetTypeLabel(tipas) {
  return PAGE_TYPE_LABELS[tipas] || PAGE_TYPE_LABELS.unknown;
}

/** The group a sheet falls in: a dalis code first (it is read from the title block), then its type. */
export function disciplineOf(tipas, dalis = null) {
  const code = String(dalis || '').toUpperCase();
  if (code && code !== 'UNKNOWN') {
    const byDalis = DISCIPLINES.find((d) => d.dalis.includes(code));
    if (byDalis) return byDalis.key;
  }
  const byType = DISCIPLINES.find((d) => d.types.includes(tipas));
  return byType ? byType.key : 'kita';
}

// A name that starts with its sheet number: „IN.1A.-B.01 1A. BALDŲ PLANAS M 1:50". Same rule as
// api/sheet_refs.split_code: letters, then a . or - and digits.
const LEADING_CODE = /^\s*([A-ZĄČĘĖĮŠŲŪŽ]{1,4}(?:[.-]{1,2}[0-9A-ZĄČĘĖĮŠŲŪŽ]{1,4})*[.-]\d{1,3})\s+(.+)$/u;

/** { number, shortNumber, title } of a sheet name; number is null when the name carries none. */
export function splitSheetName(name) {
  const s = String(name || '').trim();
  const m = LEADING_CODE.exec(s);
  if (!m) return { number: null, shortNumber: null, title: s };
  const number = m[1];
  // „IN.1A.-B.01" is read as „B.01" on the sheet; the full code stays in the tooltip.
  const tail = number.split('-').pop();
  const shortNumber = /\d/.test(tail) && /[A-Za-zĄ-ž]/u.test(tail) && tail.length >= 3 ? tail : number;
  return { number, shortNumber, title: m[2].trim() };
}

function pageKey(page) { return String(Number(page)); }

/** The override for a page, or null. Keys are strings in the stored blob („3"), numbers in memory. */
export function overrideFor(overrides, page) {
  if (!overrides || typeof overrides !== 'object') return null;
  const o = overrides[pageKey(page)] ?? overrides[Number(page)];
  return o && typeof o === 'object' ? o : null;
}

/**
 * The rail model.
 * @param {{ puslapiai?: object[], overrides?: object, pageCount?: number }} input
 * @returns {{ sheets: Sheet[], groups: { key, label, sheets: Sheet[] }[] }}
 * Sheet = { page, number, shortNumber, name, autoName, tipas, autoTipas, discipline, autoDiscipline,
 *           overridden: boolean, classified: boolean }
 */
export function buildSheetRail({ puslapiai = [], overrides = null, pageCount = null } = {}) {
  const byPage = new Map();
  for (const p of Array.isArray(puslapiai) ? puslapiai : []) {
    const nr = Number(p?.nr ?? p?.page);
    if (Number.isInteger(nr) && nr >= 1 && !byPage.has(nr)) byPage.set(nr, p);
  }
  const last = Math.max(Number(pageCount) || 0, ...byPage.keys(), 0);
  const sheets = [];
  for (let page = 1; page <= last; page++) {
    const auto = byPage.get(page) || null;
    const o = overrideFor(overrides, page);
    // `puslapiai[]` {nr, tipas, pavadinimas}; legacy blobs carry `v8_pages[]` {page, type, label}.
    const autoName = String(auto?.pavadinimas || auto?.label || '').trim() || `Lapas ${page}`;
    const autoTipas = auto?.tipas || auto?.type || 'unknown';
    const autoDiscipline = disciplineOf(autoTipas, auto?.dalis);
    const name = String(o?.name || '').trim() || autoName;
    const tipas = o?.type || autoTipas;
    // A user's type moves the sheet with it unless the user also chose a group.
    const discipline = (o?.dalis && DISCIPLINE_BY_KEY[o.dalis]) ? o.dalis
      : (o?.type ? disciplineOf(o.type, auto?.dalis) : autoDiscipline);
    const { number, shortNumber, title } = splitSheetName(name);
    sheets.push({
      page, number, shortNumber, name: title || name, fullName: name, autoName, tipas, autoTipas,
      discipline, autoDiscipline, overridden: !!o, classified: !!auto,
    });
  }
  const groups = DISCIPLINES
    .map((d) => ({ key: d.key, label: d.label, sheets: sheets.filter((s) => s.discipline === d.key) }))
    .filter((g) => g.sheets.length > 0);
  return { sheets, groups };
}

/**
 * A new overrides map with `patch` stored for `page`. A field equal to the automatic value is not
 * stored (renaming back to the automatic name is not an override), an empty patch removes the entry.
 */
export function setSheetOverride(overrides, page, patch, auto = {}) {
  const next = { ...(overrides && typeof overrides === 'object' ? overrides : {}) };
  delete next[Number(page)];
  const entry = {};
  const name = String(patch?.name ?? '').trim();
  if (name && name !== String(auto.name || '').trim()) entry.name = name.slice(0, 200);
  if (patch?.type && patch.type !== auto.tipas && PAGE_TYPE_LABELS[patch.type]) entry.type = patch.type;
  if (patch?.dalis && patch.dalis !== auto.discipline && DISCIPLINE_BY_KEY[patch.dalis]) entry.dalis = patch.dalis;
  if (Object.keys(entry).length) next[pageKey(page)] = entry;
  else delete next[pageKey(page)];
  return next;
}

/** A new overrides map without the page's entry („Atkurti automatinį"). */
export function clearSheetOverride(overrides, page) {
  const next = { ...(overrides && typeof overrides === 'object' ? overrides : {}) };
  delete next[pageKey(page)];
  delete next[Number(page)];
  return next;
}

/** {page: hits} from the search plugin's results (pageIndex is 0-based). */
export function searchHitsByPage(results) {
  const out = {};
  for (const r of Array.isArray(results) ? results : []) {
    const idx = Number(r?.pageIndex);
    if (!Number.isInteger(idx) || idx < 0) continue;
    out[idx + 1] = (out[idx + 1] || 0) + 1;
  }
  return out;
}

/** The hover line of a link: „→ lapas 5: Lubų planas" (+ „ir dar N lapai" when several are meant). */
export function calloutHoverText(callout, sheets = []) {
  const page = Number(callout?.target_page);
  const s = sheets.find((x) => x.page === page);
  const name = s?.fullName || callout?.target_name || '';
  let text = `→ lapas ${page}${name ? `: ${name}` : ''}`;
  const more = Array.isArray(callout?.other_pages) ? callout.other_pages.length : 0;
  if (more) text += ` (ir dar ${more} ${lapuForma(more)}: ${callout.other_pages.join(', ')})`;
  return text;
}

/** 1 lapas, 2 lapai, 10 lapų, 21 lapas. */
export function lapuForma(n) {
  const d = n % 10;
  const t = n % 100;
  if (d === 1 && t !== 11) return 'lapas';
  if (d >= 2 && d <= 9 && (t < 12 || t > 19)) return 'lapai';
  return 'lapų';
}

// ── The 56 px strip (Pathon v3 workspace frame) ───────────────────────────────────────────────────
// The rail opens on a strip of thumbnails so the drawing gets the room; the full rail is one click
// („Lapai") or T away. Remembered per browser: 'full' | anything else = the strip.
export const SHEET_RAIL_KEY = 'samatu_viewer_sheet_rail';

export function readSheetRailFull(storage) {
  try { return storage?.getItem?.(SHEET_RAIL_KEY) === 'full'; } catch { return false; }
}

export function writeSheetRailFull(storage, full) {
  try { storage?.setItem?.(SHEET_RAIL_KEY, full ? 'full' : 'strip'); } catch { /* private mode */ }
}

/** The tag under a strip thumbnail: the sheet's short number („B.01"), else its page number. */
export function stripTag(sheet) {
  const tag = String(sheet?.shortNumber || '').trim();
  if (tag && tag.length <= 6) return tag;
  return String(sheet?.page ?? '');
}

/**
 * What the strip says about a sheet when it is focused or clicked (never on hover alone):
 * „B.01 · Išdėstymo planas — Architektūra ir interjeras, lapas 1".
 */
export function stripLabel(sheet, groupLabel = '') {
  if (!sheet) return '';
  const tag = stripTag(sheet);
  const name = String(sheet.name || sheet.fullName || '').trim();
  const head = name && name !== tag ? `${tag} · ${name}` : tag;
  const where = [String(groupLabel || '').trim(), `lapas ${sheet.page}`].filter(Boolean).join(', ');
  return `${head} — ${where}`;
}
