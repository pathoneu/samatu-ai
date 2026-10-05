/**
 * The re-read diff in his words — the lines RereadDiffBanner and RereadRoomNote show.
 *
 * `_reread_diff` (lib/mergeReextract.js) keeps every value the way the engine
 * stores it: an outline as its `polygon_source` code, a floor covering and a
 * purpose as the engine's word. Printed as they are, a kept outline read
 * „kontūras corrected (naujas skaitymas: corrected)" (2026-10-05). So every
 * value goes through a label here — an outline's code never reaches the
 * screen — and a line whose old and new value read the same tells him nothing
 * and is left out. A room left with nothing to say is left out with it; a room
 * the new read did not find always stays (that is the news).
 */

import { ltNumber } from './ledger.js';

const UNIT = { plotas_m2: ' m²', perimetras_m: ' m', lubu_aukstis_m: ' m' };
const COUNTS = new Set(['durys', 'langai']);
// A floor covering is stored as the engine's word for it; he reads the sheet's words.
const FLOOR_LT = { plyteles: 'plytelės', minksta: 'parketas arba laminatas', be_dangos: 'be dangos' };

const code = (v) => String(v ?? '').trim().toLowerCase();

/** One value as he reads it: a number with its unit, a floor covering, a purpose, an outline. */
export function rereadValue(key, v, t) {
  if (v == null || v === '') return '—';
  if (key === 'grindu_danga') return FLOOR_LT[String(v)] || String(v);
  if (key === 'paskirtis') return t(`project.roomCard.paskirtis.${code(v)}`, { defaultValue: String(v) });
  if (key === 'polygon') {
    // an outline is stored as WHERE it came from — said in words, an unknown origin as „another outline"
    return t(`project.reread.outline.${code(v)}`, { defaultValue: t('project.reread.outline.other') });
  }
  const n = Number(v);
  if (!Number.isFinite(n)) return String(v);
  return `${ltNumber(n, COUNTS.has(key) ? 0 : 2)}${UNIT[key] || ''}`;
}

const fieldName = (key, t) => t(`project.reread.fields.${key}`, { defaultValue: key });

/** „plotas 12,00 m² → 12,40 m²" — null when the two read the same. */
export function changedLine(f, t) {
  const from = rereadValue(f?.key, f?.from, t);
  const to = rereadValue(f?.key, f?.to, t);
  return from === to ? null : `${fieldName(f?.key, t)} ${from} → ${to}`;
}

/** „kontūras jūsų pataisytas (naujas skaitymas: rastas pagal sienas)" — null when the new read says the same. */
export function keptLine(f, t) {
  const kept = rereadValue(f?.key, f?.kept, t);
  const read = rereadValue(f?.key, f?.read, t);
  return kept === read ? null : `${fieldName(f?.key, t)} ${kept} (${t('project.reread.read', { value: read })})`;
}

const linesOf = (fields, line, t) => (Array.isArray(fields) ? fields : []).map((f) => line(f, t)).filter(Boolean);

/**
 * The whole diff as finished lines: `{ changed: [{nr, pavadinimas, lines}], kept: [{nr, pavadinimas, why,
 * lines}], added, removed }` — only what reads differently.
 */
export function rereadDiffLines(diff, t) {
  const d = diff && typeof diff === 'object' ? diff : {};
  const changed = (d.changed || [])
    .map((r) => ({ nr: r?.nr, pavadinimas: r?.pavadinimas, lines: linesOf(r?.fields, changedLine, t) }))
    .filter((r) => r.lines.length);
  const kept = (d.kept || [])
    .map((r) => ({ nr: r?.nr, pavadinimas: r?.pavadinimas, why: r?.why, lines: linesOf(r?.fields, keptLine, t) }))
    .filter((r) => r.why === 'missing' || r.lines.length);
  return { changed, kept, added: d.added || [], removed: d.removed || [] };
}

/** True when nothing in the diff reads differently. */
export function rereadLinesEmpty(lines) {
  return !(lines?.changed?.length || lines?.kept?.length || lines?.added?.length || lines?.removed?.length);
}

/**
 * ONE room's part, for its check sheet: `{ changed: [line], kept: {why, lines} | null }`, or null when the
 * diff has nothing about the room that reads differently.
 */
export function rereadRoomLines(diff, roomNr, t) {
  const key = roomNr == null ? '' : String(roomNr).trim();
  if (!key) return null;
  const all = rereadDiffLines(diff, t);
  const changed = all.changed.find((r) => String(r.nr) === key)?.lines || [];
  const kept = all.kept.find((r) => String(r.nr) === key) || null;
  if (!changed.length && !kept) return null;
  return { changed, kept: kept ? { why: kept.why, lines: kept.lines } : null };
}
