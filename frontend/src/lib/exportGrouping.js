/**
 * exportGrouping.js — what the export dialog sends for „Grupuoti pagal" and „PDF su žymėjimais"
 * (togal-v2 W8; Togal's Screen View / Full Export and PDF with overlays, research note §8).
 *
 * The grouping itself runs on the server (backend/api/export_grouping.py) — once, for both the preview and
 * the file, so the dialog shows exactly what the workbook holds. This module only prepares the lines:
 * the very lines `exportLines` prints (same filter, same floor multiplier), each with the rooms that
 * produced it (`dalys`, the server's `contributions[]` × the floor count) and where its number came from
 * (`kilme`: the program, or his own). Nothing is recomputed here.
 *
 * Pure: no React, no network, no storage.
 */

import { exportLines } from './exportLines.js';
import { getFloorCount } from './floorMultiplier.js';
import { contributionsOf, isManualRow } from './ledger.js';
import { autoPageScalesFromRooms, laneScalesOf } from './durableScale.js';

export const DEFAULT_GROUPING = 'skyriai';

/** The choices, in the dialog's order. `value` is what /generate-excel's `grupavimas` takes. */
export const GROUPINGS = Object.freeze([
  { value: 'skyriai', label: 'Skyrius', desc: 'Kaip iki šiol: skyriai ir jų eilutės' },
  { value: 'patalpos', label: 'Patalpas', desc: 'Kiekviena patalpa su savo kiekių dalimi' },
  { value: 'seimos', label: 'Darbų šeimas', desc: 'Kaip „Kiekiai" skiltyje: eilutė ir patalpos po ja' },
  { value: 'lapai', label: 'Lapus', desc: 'Pagal brėžinio lapą, kuriame patalpa nubraižyta' },
  { value: 'be_grupavimo', label: 'Be grupavimo', desc: 'Viena eilutė kiekvienai patalpos daliai, su filtru' },
]);

export function isGrouping(value) {
  return GROUPINGS.some((g) => g.value === value);
}

/** Where a sąmata row's number came from: 'jusu' (a row he added), 'pataisyta' (he typed over it), 'programa'. */
export function rowOrigin(row) {
  if (isManualRow(row)) return 'jusu';
  if (row?.manual_override === true) return 'pataisyta';
  return 'programa';
}

/**
 * `exportLines(project, allowedSkyriai)` with each line's room parts and origin attached — same lines, same
 * order (both walk the darbu_sarasas rows that carry a quantity). A KŽ project (no darbu_sarasas) has no
 * room parts: its lines come back as they are.
 */
export function exportLinesWithParts(project, allowedSkyriai = null) {
  const rows = Array.isArray(project?.darbu_sarasas) ? project.darbu_sarasas : [];
  if (rows.length === 0) return exportLines(project, allowedSkyriai);
  const source = rows.filter((it) => (it?.kiekis || 0) > 0);
  const lines = exportLines(project, null);
  const floors = getFloorCount(project);
  const keep = (skyrius) => !allowedSkyriai || allowedSkyriai.has(skyrius);
  const out = [];
  lines.forEach((line, i) => {
    if (!keep(line.skyrius)) return;
    const row = source[i] || {};
    const dalys = contributionsOf(row)
      .filter((c) => c && Number.isFinite(Number(c.value)))
      .map((c) => ({
        room_nr: c.room_nr != null ? String(c.room_nr) : '',
        room_name: c.room_name || '',
        page: c.page ?? null,
        value: Number(c.value) * floors,
      }));
    out.push({
      ...line,
      dalys,
      kilme: rowOrigin(row),
      prielaida: row._assumption || row._confidence_reason || '',
    });
  });
  return out;
}

/** `[{nr, pavadinimas}]` — the sheet names the grouped workbook heads its groups with. */
export function exportSheets(project) {
  return (project?.puslapiai || [])
    .filter((s) => s && Number.isInteger(Number(s.nr)))
    .map((s) => ({ nr: Number(s.nr), pavadinimas: String(s.pavadinimas || '').trim() }));
}

/** The sheets the overlay PDF can print: one entry per drawing page, named when the project knows its name. */
export function overlayPageChoices(project, pageCount) {
  const names = new Map(exportSheets(project).map((s) => [s.nr, s.pavadinimas]));
  const n = Number(pageCount) || Math.max(0, ...names.keys());
  return Array.from({ length: n }, (_, i) => ({ nr: i + 1, name: names.get(i + 1) || '' }));
}

export const OVERLAY_LAYERS = Object.freeze([
  { key: 'outlines', label: 'Patalpų kontūrai', desc: 'su numeriu ir plotu; programos pasiūlyti — brūkšniniai', on: true },
  { key: 'measurements', label: 'Matavimai', desc: 'ilgiai ir plotai pagal lapo mastelį', on: true },
  { key: 'counts', label: 'Skaičiavimai', desc: 'pažymėti simboliai jų tipo spalva', on: true },
  { key: 'walls', label: 'Sienos', desc: 'kurias programa perskaitė iš brėžinio linijų', on: false },
]);

/**
 * The scale each sheet's measurements are labelled with — the viewer's own merge (TakeoffViewer
 * effectiveScales): areas of the outlined rooms ← the drawing's ratio ← his calibration. Sent with the
 * overlay request so the PDF says the same metres as the screen.
 */
export function overlayScales(project) {
  const rooms = project?.v8_rooms || project?.patalpos || [];
  const merged = {
    ...autoPageScalesFromRooms(rooms),
    ...laneScalesOf(project),
    ...Object.fromEntries(Object.entries(project?.pageScalesDurable || {})
      .filter(([, s]) => s && s.calibrated !== false && Number(s.metersPerPointX) > 0)),
  };
  const out = {};
  for (const [page, s] of Object.entries(merged)) {
    const mx = Number(s?.metersPerPointX);
    if (!(mx > 0)) continue;
    const my = Number(s?.metersPerPointY);
    out[String(page)] = { metersPerPointX: mx, ...(my > 0 ? { metersPerPointY: my } : {}), source: s.source || 'user' };
  }
  return out;
}

/** The overlay route's body. `pages`: 'all' or page numbers; `layers`: {key: bool}. */
export function overlayRequestBody(project, { pages = 'all', layers = {}, dryRun = false } = {}) {
  const chosen = {};
  for (const l of OVERLAY_LAYERS) chosen[l.key] = layers[l.key] ?? l.on;
  return {
    pages: pages === 'all' ? 'all' : [...pages].map(Number).filter((n) => n > 0).sort((a, b) => a - b),
    layers: chosen,
    scales: overlayScales(project),
    dry_run: dryRun,
  };
}
