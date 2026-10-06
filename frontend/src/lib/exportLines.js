/**
 * exportLines.js — the lines a document sends to the client, and what is still
 * missing on them.
 *
 * One source for two things that must never disagree (2026-10-06, contractor
 * walkthrough): what the Excel / PDF pasiūlymas / client link actually print,
 * and the sentence that warns him before he sends it. After „Užpildyti iš mano
 * kainyno" priced 12 of 116 rows, the Siųsti step said only „10 eilučių be
 * kiekio bus praleista" — nothing about the 94 rows that would reach the
 * client at 0,00 €.
 *
 * THE PRICE RULE, checked against the data model rather than assumed: a row
 * has a price only when `kaina > 0`. The model does not tell a typed 0 from no
 * price at all — `applyPriceList.manualPricePatch` turns a price cleared to 0
 * back into „not priced" (fillable by the kainynas again), the Sąmata table
 * shows „įveskite" for it, and every document prints it as 0,00 €. So null,
 * undefined, '' and 0 all count as „no price". (Negative prices cannot be
 * typed: parseLtNumber.isValidAmount rejects them.)
 *
 * Pure: no React, no network, no storage.
 */

import { getFloorCount } from './floorMultiplier.js';
import { exportRows as templateExportRows, lacksPrice } from './samataTemplate.js';

/**
 * The section a sąmata row is printed under when it names none — the name the
 * Sąmata step shows it under (ProjectMainView `otherWorks`, darbuRows.rowSection).
 *
 * 2026-10-06: the export dialog listed such a row as „Kiti darbai" while the
 * export filed it under „Apdaila", so with every listed section ticked the row
 * was still left out of the Excel / PDF without a word. One name now, and the
 * dialog lists the very names the export filters on (`exportSections`).
 */
export const EXPORT_FALLBACK_SECTION = 'Kiti darbai';

/** The section a darbu_sarasas row is printed (and filtered) under. */
export function exportSectionOf(row) {
  return row?.skyrius || row?.kategorija || EXPORT_FALLBACK_SECTION;
}

/**
 * The lines `/generate-excel` and `/generate-pdf` print in the Pathon layout.
 *
 * Moved here verbatim from ExportDropdown.buildPayload (which now calls it),
 * so the export and the warnings before it read the same rows: a row without
 * a quantity is dropped, the floor multiplier (SM02) scales the quantities,
 * an unpriced row goes out as `kaina: 0` (0,00 € on paper), and with
 * `allowedSkyriai` (a Set) only the sections he left ticked are kept. A
 * project with no darbu_sarasas falls back to `project.rows` (KŽ), as before.
 */
export function exportLines(project, allowedSkyriai = null) {
  const keep = (skyrius) => !allowedSkyriai || allowedSkyriai.has(skyrius);
  const floorCount = getFloorCount(project);
  const mult = (n) => (n || 0) * floorCount;

  // V8 darbu_sarasas — primary source
  if (Array.isArray(project?.darbu_sarasas) && project.darbu_sarasas.length > 0) {
    return project.darbu_sarasas
      .filter(it => (it.kiekis || 0) > 0)
      .map((it, i) => {
        const kiekis = mult(it.kiekis);
        return {
          nr: String(it.eil_nr || i + 1),
          aprasymas: it.aprasymas || '',
          mato_vnt: it.mato_vnt || it.vnt || '',
          kiekis,
          kaina: it.kaina || 0,
          suma: kiekis * (it.kaina || 0),
          skyrius: exportSectionOf(it),
          confidence: it.confidence || 'medium',
        };
      })
      .filter(it => keep(it.skyrius));
  }
  // Fallback (KŽ projektai)
  return (project?.rows || [])
    .map(r => {
      const kiekis = mult(r.kiekis);
      return {
        nr: r.nr || '', aprasymas: r.aprasymas || '',
        mato_vnt: r.mato_vnt || '',
        kiekis,
        kaina: r.kaina || 0,
        suma: kiekis * (r.kaina || 0),
        skyrius: r.skyrius || '',
      };
    })
    .filter(it => keep(it.skyrius || ''));
}

/**
 * The lines one export dialog prints: his own layout's rendered rows
 * ('excel-template', lib/samataTemplate.exportRows) or the Pathon layout's.
 */
export function linesForExport(project, { format, templateRows = null, allowedSkyriai = null } = {}) {
  return format === 'excel-template'
    ? templateExportRows(templateRows || [], allowedSkyriai)
    : exportLines(project, allowedSkyriai);
}

/**
 * The sections the export dialog lists: the printed lines grouped by the very
 * name the section filter checks (`line.skyrius`), so ticking a section always
 * prints every line under it and no line is ever left out silently. Give it
 * the lines WITHOUT a section filter (`linesForExport(project, { format,
 * templateRows })`). `[{ name, count }]`, sorted the Lithuanian way.
 */
export function exportSections(lines) {
  const counts = new Map();
  for (const line of lines || []) {
    const name = String(line?.skyrius ?? '');
    counts.set(name, (counts.get(name) || 0) + 1);
  }
  return [...counts.entries()]
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => a.name.localeCompare(b.name, 'lt'));
}

/**
 * After the export dialog, is there still something to ask about prices?
 *
 * The dialog prints „N eilučių be kainos — klientas jas matys su 0,00 € suma"
 * over the very lines the export sends (same `lines`), so whenever a printed
 * line lacks a price he has already read it there — the confirm that followed
 * only repeated it, with „pozicijos" (2026-10-06 walkthrough). What the line
 * cannot say: a sąmata with no price at all whose document has no line with a
 * quantity to count (his own layout with every cell still blank). That case
 * alone still asks once.
 */
export function asksAboutPricesAfterDialog(project, lines) {
  if (linesWithoutPrice(lines).length > 0) return false;
  const rows = [project?.darbu_sarasas, project?.rows, project?.pozicijos].filter(Array.isArray).flat();
  return rows.length > 0 && !rows.some((r) => Number(r?.kaina) > 0);
}

/**
 * The lines the client link (/share/:token) lists — SharedProject.jsx's own
 * rule: every section (the link has no section filter), rows with a quantity,
 * each line's sum = kiekis × (kaina || 0).
 */
export function sharedLines(project) {
  return (project?.darbu_sarasas || [])
    .filter((d) => d && (d.kiekis || 0) > 0)
    .map((d) => ({ ...d, kaina: d.kaina || 0, suma: (d.kiekis || 0) * (d.kaina || 0) }));
}

/** Lines that carry a quantity — the ones the client actually reads. */
export function linesWithQuantity(lines) {
  return (lines || []).filter((r) => (r?.kiekis || 0) > 0);
}

/**
 * Lines that reach the client with a quantity but WITHOUT A PRICE: their sum
 * prints as 0,00 € in the Excel, the PDF and the client link alike. A merged
 * line of his own layout counts when part of its quantity is unpriced, not
 * when it carries several prices (samataTemplate.lacksPrice). A blank cell of
 * his layout has no quantity and is not counted — blank there is by design.
 */
export function linesWithoutPrice(lines) {
  return linesWithQuantity(lines).filter(lacksPrice);
}

/** Rows no export prints: no quantity (or a non-positive one). */
export function rowsWithoutQuantity(rows) {
  return (rows || []).filter((r) => !((r?.kiekis || 0) > 0));
}

/**
 * Does this sąmata row go to the client without a price? The rule of
 * linesWithoutPrice, asked of the row itself, so the Sąmata table can open the
 * first such row. `excludedSkyriai`: sections he unticked for the export
 * (lib/exportSectionSelection.js); null = every section, as the client link.
 */
export function rowNeedsPrice(row, excludedSkyriai = null) {
  if (!row || !((row.kiekis || 0) > 0)) return false;
  if (excludedSkyriai && excludedSkyriai.has(exportSectionOf(row))) return false;
  return !(Number(row.kaina) > 0);
}

/**
 * The Siųsti step's check, counted on what the Excel / PDF would print with
 * the sections he left unticked in the export dialog last time:
 *   rows     — every sąmata row
 *   noQty    — rows skipped for want of a quantity (all sections, as before)
 *   noPrice  — printed lines with a quantity and no price
 */
export function sendCheck(project, excludedSkyriai = null) {
  const rows = Array.isArray(project?.darbu_sarasas) ? project.darbu_sarasas : [];
  const ex = excludedSkyriai || new Set();
  const lines = exportLines(project).filter((l) => !ex.has(l.skyrius));
  return {
    rows: rows.length,
    noQty: rowsWithoutQuantity(rows).length,
    noPrice: linesWithoutPrice(lines).length,
  };
}
