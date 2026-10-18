/**
 * measuredRows — measurements on sąmata rows (Pathon v3 W4-A M1; design §4 track F).
 *
 * A measurement (a length, a perimeter, an area) or a whole count type is attached to ONE row of
 * `darbu_sarasas` by the row's `id`, and says how (`kaip`):
 *   'kiekis'  — the measured number is the row's quantity, instead of the program's;
 *   'pridėti' — added to the program's quantity;
 *   'atimti'  — taken away from it.
 * The row's `kiekis` = the program's number ± the measurements, never below 0. Each measurement is a ledger
 * line on the row — „matavimas 4,20 m (lapas 1)" — in `row.matavimai` (the „iš matavimų" chip lists them) and,
 * when the row has a chain, a `roll_up` step with op `matavimas`, so the chain still ends on `kiekis`
 * (extractor/ledger.py's rule). `kiekis_programos` keeps the program's own number beside it. A quantity he typed
 * (`manual_override`, lib/quantityOverride.js) wins: the measurements are listed, not counted.
 *
 * WHERE THE LINK LIVES. `project.measurementRows = {'m:<measurement id>' | 'type:<count type id>': {eilute_id,
 * kaip}}` — beside the measurements, not on them, because the viewer owns `measurements`/`countTypes` in its own
 * history and writes its whole list back on every save (InteriorWorkspace.handleMeasureDataChange): a field the
 * panel put on a measurement object would be gone at the viewer's next save. A link written on the object itself
 * (`eilute_id`/`kaip` on a measurement or a count type — the viewer's or a legend row's own) is honoured too; the
 * map wins, and `{eilute_id: null}` in it takes such a link off.
 *
 * WHO COUNTS. The browser turns each linked measurement into a contribution `{key, eilute_id, kaip, value, unit,
 * pages, pavadinimas?, tekstas?}` (only the browser knows the sheets' scales, lib/pageScales). The rows follow on
 * every save (projectStore.updateProject → syncMeasuredRows), and /recompute-interior applies the same
 * contributions (sent in the recompute context) to the rows it rebuilds — `backend/api/measured_rows.py`, the
 * twin of applyMeasuredRows below; `measuredRows.cases.json` holds the cases both run. Measurements are what he
 * measured, never a default: nothing here invents a number.
 *
 * Pure: no React, no I/O.
 */

import { measurementValue } from './measurements.js';
import { effectivePageScales, pageScaleIn } from './pageScales.js';

export const KAIP = Object.freeze(['kiekis', 'pridėti', 'atimti']);
export const KAIP_LABELS = Object.freeze({
  kiekis: 'Vietoj programos kiekio',
  'pridėti': 'Pridėti prie kiekio',
  atimti: 'Atimti iš kiekio',
});
export const LINKS_KEY = 'measurementRows';
const ROLL_UP_OP = 'matavimas';
const GEOMETRY_UNITS = { distance: 'm', perimeter: 'm', area: 'm²' };
const KIND_ORDER = { kiekis: 0, 'pridėti': 1, atimti: 2 };

const isObj = (v) => !!v && typeof v === 'object' && !Array.isArray(v);
const num = (v) => (v != null && v !== '' && Number.isFinite(Number(v)) ? Number(v) : null);
/** Half-up to the cent — `math.floor(v * 100 + 0.5) / 100` on the server, so both sides agree. */
export const round2 = (v) => Math.round(v * 100) / 100;

// ── Units ───────────────────────────────────────────────────────────────────────────────────────────

const UNIT_FOLD = { m2: 'm²', 'm²': 'm²', m3: 'm³', 'm³': 'm³', m: 'm', vnt: 'vnt.', 'vnt.': 'vnt.' };

/** One spelling per unit: „m2" → „m²", „vnt" → „vnt."; anything else as written. */
export function foldUnit(unit) {
  const raw = String(unit ?? '').trim();
  return UNIT_FOLD[raw.toLowerCase()] || raw;
}

export function unitOfRow(row) {
  return foldUnit(row?.mato_vnt || row?.vnt);
}

export function unitsMatch(a, b) {
  return foldUnit(a) === foldUnit(b);
}

// ── Words ───────────────────────────────────────────────────────────────────────────────────────────

/** „1 234,50" — LT decimal comma, a no-break space between thousands; `digits` decimals. */
export function ltFixed(value, digits = 2) {
  const n = Number(value);
  const [int, frac] = Math.abs(n).toFixed(digits).split('.');
  const grouped = int.replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
  return `${n < 0 ? '−' : ''}${grouped}${frac ? `,${frac}` : ''}`;
}

const digitsFor = (unit) => (foldUnit(unit) === 'vnt.' ? 0 : 2);
const quantityText = (value, unit) => `${ltFixed(value, digitsFor(unit))} ${foldUnit(unit)}`;

function pagesText(pages) {
  const list = (Array.isArray(pages) ? pages : []).filter((p) => num(p) != null);
  if (!list.length) return '';
  return list.length === 1 ? ` (lapas ${list[0]})` : ` (lapai ${list.join(', ')})`;
}

const SIGN = { kiekis: '', 'pridėti': '+ ', atimti: '− ' };

/** The ledger line: „+ matavimas „Siena“ 4,20 m (lapas 1)". A producer's own `tekstas` is used as given. */
export function lineText(c) {
  const sign = SIGN[c?.kaip] ?? '';
  if (typeof c?.tekstas === 'string' && c.tekstas.trim()) return `${sign}${c.tekstas.trim()}`;
  const name = typeof c?.pavadinimas === 'string' && c.pavadinimas.trim() ? ` „${c.pavadinimas.trim()}“` : '';
  const value = num(c?.value) == null ? 'be mastelio' : quantityText(num(c.value), c.unit);
  return `${sign}matavimas${name} ${value}${pagesText(c?.pages)}`;
}

/** Why a line is shown but not counted — in his words, saying what to do. */
function notCountedBecause(c, rowUnit, typed) {
  if (typed) return 'Kiekį įrašėte ranka — matavimas į jį neįtrauktas.';
  if (num(c.value) == null) {
    const page = (Array.isArray(c.pages) ? c.pages : [])[0];
    return page != null
      ? `${page} lape nenustatytas mastelis — nustatykite jį, ir matavimas bus įtrauktas.`
      : 'Lape nenustatytas mastelis — nustatykite jį, ir matavimas bus įtrauktas.';
  }
  if (rowUnit && !unitsMatch(c.unit, rowUnit)) {
    return `Eilutė skaičiuojama ${rowUnit}, o matavimas — ${foldUnit(c.unit)}: į kiekį neįtrauktas.`;
  }
  return null;
}

// ── Applying contributions to rows (the server's twin: backend/api/measured_rows.py) ────────────────

const isTyped = (row) => row?.manual_override === true || row?.quantity_source === 'manual_override';

/** The number a stored list of lines makes of `base` — the same arithmetic as the apply below. */
function combine(base, lines) {
  const counted = (lines || []).filter((l) => l?.taikoma && num(l.value) != null);
  const instead = counted.filter((l) => l.kaip === 'kiekis');
  let v = instead.length ? instead.reduce((s, l) => s + num(l.value), 0) : (num(base) ?? 0);
  for (const l of counted) {
    if (l.kaip === 'pridėti') v += num(l.value);
    else if (l.kaip === 'atimti') v -= num(l.value);
  }
  return round2(Math.max(0, v));
}

/**
 * The program's own number under a row. A row that already carries measurements stores it in
 * `kiekis_programos`, but only while `kiekis` is still what those measurements made of it — a rebuild that
 * wrote a new number over a carried row is the program's new number, and the measurements ride on that.
 */
function programNumber(row) {
  if (Array.isArray(row.matavimai) && 'kiekis_programos' in row) {
    const expected = combine(row.kiekis_programos, row.matavimai);
    if (Math.abs((num(row.kiekis) ?? 0) - expected) <= 0.005) return num(row.kiekis_programos);
  }
  return num(row.kiekis);
}

function stripped(rollUp) {
  return Array.isArray(rollUp) ? rollUp.filter((s) => s?.op !== ROLL_UP_OP) : rollUp;
}

function sumFlag(row, kiekis) {
  const cs = Array.isArray(row.contributions) ? row.contributions : [];
  if (!cs.length || kiekis == null) return false;
  return Math.abs(round2(cs.reduce((s, c) => s + (num(c?.value) ?? 0), 0)) - kiekis) <= 0.01;
}

function withQuantity(row, kiekis) {
  const out = { ...row, kiekis };
  if (num(row.kaina) != null) out.suma = round2(kiekis * num(row.kaina));
  if (typeof row.contributions_sum_to_total === 'boolean') out.contributions_sum_to_total = sumFlag(row, kiekis);
  return out;
}

/** A row that carried measurements and has none now: the program's number back, the lines gone. */
function released(row) {
  const { matavimai: _m, kiekis_programos: _k, ...rest } = row;
  const base = { ...rest, roll_up: stripped(row.roll_up) };
  if (!('roll_up' in row)) delete base.roll_up;
  if (isTyped(row)) return base;
  return withQuantity(base, programNumber(row) ?? 0);
}

function applied(row, contributions) {
  const rowUnit = unitOfRow(row);
  const typed = isTyped(row);
  const ordered = contributions
    .map((c, i) => ({ c, i }))
    .sort((a, b) => ((KIND_ORDER[a.c.kaip] ?? 9) - (KIND_ORDER[b.c.kaip] ?? 9)) || (a.i - b.i))
    .map(({ c }) => c);
  const lines = ordered.map((c) => {
    const why = notCountedBecause(c, rowUnit, typed);
    const line = {
      key: c.key, kaip: c.kaip, value: num(c.value), unit: foldUnit(c.unit),
      pages: Array.isArray(c.pages) ? c.pages : [], tekstas: lineText(c), taikoma: !why,
    };
    if (why) line.priezastis = why;
    return line;
  });
  const chain = stripped(row.roll_up);
  if (typed) {
    // His number stands; the lines are only listed. The program's own number is `ai_kiekis_original`.
    const { kiekis_programos: _k, ...rest } = row;
    const out = { ...rest, matavimai: lines };
    if ('roll_up' in row) out.roll_up = chain;
    return out;
  }
  const base = programNumber(row);
  const kiekis = combine(base, lines);
  const out = withQuantity({ ...row, kiekis_programos: base, matavimai: lines }, kiekis);
  if (Array.isArray(chain) && chain.length) {
    const steps = [...chain];
    let running = num(base) ?? 0;
    let insteadStarted = false;
    const unit = rowUnit || '';
    lines.filter((l) => l.taikoma).forEach((l) => {
      let note;
      if (l.kaip === 'kiekis') {
        running = insteadStarted ? running + l.value : l.value;
        note = insteadStarted ? `+${ltFixed(l.value, digitsFor(unit))} ${unit}`.trim()
          : `vietoj programos kiekio ${quantityText(num(base) ?? 0, unit)}`.trim();
        insteadStarted = true;
      } else if (l.kaip === 'pridėti') {
        running += l.value;
        note = `+${ltFixed(l.value, digitsFor(l.unit))} ${l.unit}`;
      } else {
        running -= l.value;
        note = `−${ltFixed(l.value, digitsFor(l.unit))} ${l.unit}`;
      }
      steps.push({ op: ROLL_UP_OP, label: l.tekstas, value: round2(running), note });
    });
    if (steps.length > chain.length) steps[steps.length - 1] = { ...steps[steps.length - 1], value: kiekis };
    out.roll_up = steps;
  } else if ('roll_up' in row) {
    out.roll_up = chain;
  }
  return out;
}

const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);

/**
 * Rows with the measurements applied. Pure and idempotent; a row nothing touches keeps its identity, and a list
 * nothing touches is returned as it came — so a save can tell „nothing to do" by `===`.
 */
export function applyMeasuredRows(rows, contributions) {
  if (!Array.isArray(rows)) return rows;
  const byRow = new Map();
  for (const c of Array.isArray(contributions) ? contributions : []) {
    if (!isObj(c) || !c.eilute_id || !KAIP.includes(c.kaip)) continue;
    const id = String(c.eilute_id);
    if (!byRow.has(id)) byRow.set(id, []);
    byRow.get(id).push(c);
  }
  let changed = false;
  const out = rows.map((row) => {
    if (!isObj(row)) return row;
    const mine = row.id != null ? byRow.get(String(row.id)) : null;
    let next = row;
    if (mine?.length) next = applied(row, mine);
    else if (Array.isArray(row.matavimai)) next = released(row);
    if (next !== row && same(next, row)) next = row;
    if (next !== row) changed = true;
    return next;
  });
  return changed ? out : rows;
}

// ── Links ───────────────────────────────────────────────────────────────────────────────────────────

/** The link key of a measurement or a count type. */
export function linkKey(source) {
  if (!source?.id) return null;
  return source.kind === 'countType' ? `type:${source.id}` : `m:${source.id}`;
}

function cleanLink(l) {
  if (!isObj(l) || !l.eilute_id) return null;
  return { eilute_id: String(l.eilute_id), kaip: KAIP.includes(l.kaip) ? l.kaip : 'pridėti' };
}

/** Every link in force: Map key → {eilute_id, kaip}. The panel's map wins over a link on the object. */
export function linksOf(project) {
  const out = new Map();
  for (const m of project?.measurements || []) {
    const l = cleanLink(m);
    if (l && m.id) out.set(`m:${m.id}`, l);
  }
  for (const t of project?.countTypes || []) {
    const l = cleanLink(t);
    if (l && t.id) out.set(`type:${t.id}`, l);
  }
  const map = isObj(project?.[LINKS_KEY]) ? project[LINKS_KEY] : {};
  for (const [key, l] of Object.entries(map)) {
    const clean = cleanLink(l);
    if (clean) out.set(key, clean);
    else out.delete(key);
  }
  return out;
}

function geometrySource(m, scales) {
  const scale = pageScaleIn(scales, m.page);
  const value = scale?.calibrated ? round2(measurementValue(m, scale).value) : null;
  return {
    key: `m:${m.id}`, value: Number.isFinite(value) ? value : null, unit: GEOMETRY_UNITS[m.kind],
    pages: m.page != null ? [m.page] : [],
    ...(m.name ? { pavadinimas: String(m.name) } : {}),
  };
}

function countTypeSource(id, measurements, types) {
  const marks = measurements.filter((m) => m?.kind === 'count' && m.typeId === id);
  const pages = [...new Set(marks.map((m) => m.page).filter((p) => num(p) != null))].sort((a, b) => a - b);
  const type = types.find((t) => t?.id === id);
  return { key: `type:${id}`, value: marks.length, unit: 'vnt.', pages, pavadinimas: String(type?.label || id) };
}

/**
 * One measurement or count type as he would read it — `{key, value, unit, pages, pavadinimas?}` — linked or
 * not (the picker and the toasts name what is being put on a row). Null for an unknown key.
 */
export function measureSource(project, key) {
  const measurements = Array.isArray(project?.measurements) ? project.measurements : [];
  const k = String(key || '');
  if (k.startsWith('m:')) {
    const m = measurements.find((x) => x?.id != null && `m:${x.id}` === k);
    return m && GEOMETRY_UNITS[m.kind] ? geometrySource(m, effectivePageScales(project)) : null;
  }
  if (k.startsWith('type:')) {
    const id = k.slice(5);
    const types = Array.isArray(project?.countTypes) ? project.countTypes : [];
    if (!types.some((t) => t?.id === id) && !measurements.some((m) => m?.typeId === id)) return null;
    return countTypeSource(id, measurements, types);
  }
  return null;
}

/** „Atstumas 4,20 m (lapas 1)" — a source in words, without the sign a row line carries. */
export function sourceText(source) {
  if (!source) return '';
  return lineText({ ...source, kaip: 'kiekis' });
}

/**
 * The linked measurements as contributions — the measured value with its unit and pages. A length on a sheet
 * with no scale has `value: null` (listed, never counted). A count type is all of its marks.
 */
export function measuredContributions(project) {
  const links = linksOf(project);
  if (!links.size) return [];
  const measurements = Array.isArray(project?.measurements) ? project.measurements : [];
  let scales = null;
  const out = [];
  for (const m of measurements) {
    const link = m?.id ? links.get(`m:${m.id}`) : null;
    if (!link || !GEOMETRY_UNITS[m?.kind]) continue;
    if (!scales) scales = effectivePageScales(project);
    const { key, ...src } = geometrySource(m, scales);
    out.push({ key, ...link, ...src });
  }
  const types = Array.isArray(project?.countTypes) ? project.countTypes : [];
  const typeIds = new Set([...types.map((t) => t?.id), ...measurements.map((m) => m?.typeId)].filter(Boolean));
  for (const id of typeIds) {
    const link = links.get(`type:${id}`);
    if (!link) continue;
    const { key, ...src } = countTypeSource(id, measurements, types);
    out.push({ key, ...link, ...src });
  }
  return out;
}

// ── Drag and drop ───────────────────────────────────────────────────────────────────────────────────

/** The drag payload's type: a measurement's link key travels as text under it. */
export const MEASURE_DRAG_TYPE = 'application/x-pathon-matavimas';

/** May this measurement go on this row? `{ok}` or `{ok: false, why}` in his words. */
export function canLinkTo(source, row) {
  if (!source) return { ok: false, why: 'Matavimo nebėra.' };
  if (!row?.id) return { ok: false, why: 'Šios eilutės priskirti negalima — perskaičiuokite sąmatą.' };
  const rowUnit = unitOfRow(row);
  if (rowUnit && !unitsMatch(source.unit, rowUnit)) {
    return { ok: false, why: `Eilutė skaičiuojama ${rowUnit}, o matavimas — ${foldUnit(source.unit)}. Pasirinkite eilutę, skaičiuojamą ${foldUnit(source.unit)}.` };
  }
  return { ok: true };
}

/** A row put back as it was (an Undo): the row in `rows` that is `row` takes `previous`'s fields. */
export function restoreRow(rows, row, previous) {
  const list = Array.isArray(rows) ? rows : [];
  const id = row?.id ?? row?._id;
  const at = id != null
    ? list.findIndex((r) => (r?.id ?? r?._id) === id)
    : list.findIndex((r) => r?.aprasymas === row?.aprasymas && (r?.skyrius || '') === (row?.skyrius || ''));
  if (at < 0) return list;
  const next = list.slice();
  next[at] = previous;
  return next;
}

/** Does anything on the project link a measurement to a row (or did, so a row must be released)? */
export function hasMeasuredRows(project) {
  if (!project) return false;
  const map = project[LINKS_KEY];
  if (isObj(map) && Object.keys(map).length) return true;
  if ((project.measurements || []).some((m) => m?.eilute_id)) return true;
  if ((project.countTypes || []).some((t) => t?.eilute_id)) return true;
  return (project.darbu_sarasas || []).some((r) => Array.isArray(r?.matavimai));
}

/** The project with its rows following its measurements; the same object when nothing changes. */
export function syncMeasuredRows(project) {
  if (!isObj(project) || !Array.isArray(project.darbu_sarasas) || !hasMeasuredRows(project)) return project;
  const rows = applyMeasuredRows(project.darbu_sarasas, measuredContributions(project));
  return rows === project.darbu_sarasas ? project : { ...project, darbu_sarasas: rows };
}

/**
 * The fields a link change writes: the link map, and the rows as they then stand. `link` = {eilute_id, kaip}, or
 * null to take the measurement off its row. Merge onto the stored project (updateProject) — field-scoped.
 */
export function linkPatch(project, key, link) {
  const map = { ...(isObj(project?.[LINKS_KEY]) ? project[LINKS_KEY] : {}) };
  const clean = cleanLink(link);
  if (clean) map[key] = { ...clean, at: new Date().toISOString() };
  else {
    delete map[key];
    // a link written on the object itself stays in force unless the map says otherwise
    const onObject = linksOf({ ...project, [LINKS_KEY]: {} }).has(key);
    if (onObject) map[key] = { eilute_id: null, at: new Date().toISOString() };
  }
  const next = { ...project, [LINKS_KEY]: map };
  const rows = applyMeasuredRows(next.darbu_sarasas || [], measuredContributions(next));
  return { [LINKS_KEY]: map, darbu_sarasas: rows };
}

/** What a drop proposes: instead of an empty line, added to one that already has a number. */
export function defaultKaip(row) {
  const k = num(row?.kiekis);
  return k == null || k === 0 ? 'kiekis' : 'pridėti';
}

/** The ledger lines a row carries now (the „iš matavimų" chip and its list). */
export function rowMeasurements(project, row) {
  const id = row?.id != null ? String(row.id) : null;
  if (!id) return [];
  const live = (project?.darbu_sarasas || []).find((r) => r?.id != null && String(r.id) === id) || row;
  return Array.isArray(live?.matavimai) ? live.matavimai : [];
}

/** Where a measurement is linked: {link, row|null} — row null when the line is no longer in the sąmata. */
export function linkStatus(project, key) {
  const link = key ? linksOf(project).get(key) : null;
  if (!link) return null;
  const row = (project?.darbu_sarasas || []).find((r) => r?.id != null && String(r.id) === link.eilute_id) || null;
  return { link, row };
}
