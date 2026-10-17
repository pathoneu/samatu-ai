/**
 * pdfRevisions.js — a second edition of the drawing laid over the project's own (togal-v2 W10).
 *
 * The server keeps the new PDF under its own key, matches every new sheet to an old one by the walls
 * (backend/extractor/revision_alignment.py) and paints the comparison picture in the OLD sheet's display
 * frame (api/pdf_revisions.py): the browser only lays one transparent PNG over the sheet. Nothing here
 * changes a quantity, and the overlay is never saved — off by default, off on Esc / „Išjungti".
 */
import { API_BASE } from './apiBase.js';
import { normalizeRotation } from './viewerEngine/pageRotation.js';

export const MODES = Object.freeze(['skirtumas', 'naujas']);
export const MODE_LABELS = Object.freeze({ skirtumas: 'Skirtumai', naujas: 'Naujas leidimas' });
export const DEFAULT_OPACITY = 0.6;
// The overlay is fetched at a few fixed sharpnesses so zooming does not ask again on every step;
// the <img> scales between them. 150 is the server's cap.
export const DPI_TIERS = Object.freeze([72, 96, 150]);

const base = (projectId) => `${API_BASE}/api/projects/${encodeURIComponent(projectId)}/pdf-revisions`;

/** The sheet's width as displayed, in points (/Rotate 90/270 swaps the mediabox). */
export function displayWidthPt(pageSizePt, rotation) {
  const w = Number(pageSizePt?.width);
  const h = Number(pageSizePt?.height);
  if (!(w > 0) || !(h > 0)) return null;
  return normalizeRotation(rotation) % 180 === 90 ? h : w;
}

/** The smallest tier that is at least as sharp as the sheet is drawn on screen now. */
export function dpiTier(renderedWidthPx, widthPt) {
  const need = (Number(renderedWidthPx) || 0) / (Number(widthPt) || 0) * 72;
  if (!Number.isFinite(need) || need <= 0) return DPI_TIERS[0];
  return DPI_TIERS.find((t) => t >= need) || DPI_TIERS[DPI_TIERS.length - 1];
}

export function overlayUrl(projectId, rid, page, mode, dpi) {
  const m = MODES.includes(mode) ? mode : 'skirtumas';
  return `${base(projectId)}/${encodeURIComponent(rid)}/overlay/${Number(page)}?mode=${m}&dpi=${Number(dpi)}`;
}

const lt2 = (v) => Number(v).toLocaleString('lt-LT', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

/**
 * What the control says about one sheet of the project: which new sheet lies over it and how it was laid.
 * `{ matched, newPage, byWalls, text }` — `text` is one plain sentence; null record → nothing to say.
 */
export function sheetInfo(record, page) {
  if (!record) return null;
  const m = record.pagal_sena?.[String(page)];
  if (!m) {
    return { matched: false, newPage: null, byWalls: false, text: `Šiam lapui naujame leidime atitikmens nėra.` };
  }
  const byWalls = m.budas === 'sienos';
  let text = byWalls
    ? `Ant šio lapo — naujo leidimo lapas ${m.naujas_lapas}, sulygiuotas pagal sienas (sutapimas ${lt2(m.sutapimas)}).`
    : `Ant šio lapo — naujo leidimo lapas ${m.naujas_lapas}, sulygiuotas tik pagal lapo kraštus: sienos nesutapo, `
      + 'tad poslinkis gali būti netikslus.';
  if (byWalls && m.geriausias?.old_page != null && m.geriausias.old_page !== page) {
    text += ` Sienomis jis panašus ir į lapą ${m.geriausias.old_page} (${lt2(m.geriausias.sutapimas)}) — palikta pagal lapo numerį.`;
  } else if (!byWalls && m.geriausias?.old_page != null) {
    text += ` Geriausiai sienos sutapo su lapu ${m.geriausias.old_page} (${lt2(m.geriausias.sutapimas)}) — per mažai sulygiuoti.`;
  }
  return { matched: true, newPage: m.naujas_lapas, byWalls, text };
}

/** „spalio 17 d." style short label for an edition in the picker. */
export function editionLabel(record) {
  if (!record) return '';
  const d = new Date(record.created_at);
  const when = Number.isNaN(d.getTime()) ? '' : d.toLocaleDateString('lt-LT', { month: 'long', day: 'numeric', timeZone: 'Europe/Vilnius' });
  return [record.pavadinimas || 'Naujas leidimas', when].filter(Boolean).join(' · ');
}

async function json(res) {
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(typeof body.detail === 'string' ? body.detail : `HTTP ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return body;
}

export const listRevisions = (projectId) =>
  fetch(base(projectId), { credentials: 'include' }).then(json).then((b) => b.leidimai || []);

export function uploadRevision(projectId, file) {
  const form = new FormData();
  form.append('pdf_file', file);
  return fetch(base(projectId), { method: 'POST', credentials: 'include', body: form }).then(json);
}

export const deleteRevision = (projectId, rid) =>
  fetch(`${base(projectId)}/${encodeURIComponent(rid)}`, { method: 'DELETE', credentials: 'include' }).then(json);
