/**
 * intakeApi — several drawings (PDFs, PNG / JPG / TIFF pictures) made into ONE project PDF before anything else
 * happens to them (Pathon v3 W5-D, D14; backend api/intake.py, extractor/intake.py). €0, the server saves nothing.
 * The New Project page then goes on exactly as with one PDF; the sheets are named after their files through
 * `sheet_overrides` (the sheet rail's own names), which he can rename like any other.
 */
import { API_BASE } from './apiBase.js';

export const INTAKE_ACCEPT = '.pdf,.png,.jpg,.jpeg,.tif,.tiff';
const PDF_RE = /\.pdf$/i;

/** True when the chosen files need combining: more than one, or a picture. */
export function needsCombine(files) {
  const list = Array.from(files || []);
  return list.length > 1 || (list.length === 1 && !PDF_RE.test(list[0]?.name || ''));
}

/** {page: name} from the server → the sheet rail's overrides ({"3": {name}}). */
export function sheetOverridesFromNames(names) {
  const out = {};
  for (const [page, name] of Object.entries(names || {})) {
    const n = Number(page);
    const text = String(name || '').trim();
    if (Number.isInteger(n) && n >= 1 && text) out[String(n)] = { name: text };
  }
  return out;
}

/** The combined file's name: the first file's, with „ir dar N". */
export function combinedName(files) {
  const list = Array.from(files || []);
  const stem = String(list[0]?.name || 'brėžiniai').replace(/\.[^.]+$/, '');
  return `${stem}${list.length > 1 ? ` ir dar ${list.length - 1}` : ''}.pdf`;
}

/**
 * POST the files; → `{ file: File (application/pdf), overrides: {page: {name}}, pages }`. Throws an Error whose
 * message is the server's plain sentence when it refuses.
 */
export async function combineUploads(files, { fetchImpl = fetch } = {}) {
  const list = Array.from(files || []);
  const fd = new FormData();
  for (const f of list) fd.append('files', f, f.name);
  const res = await fetchImpl(`${API_BASE}/api/intake/combine`, { method: 'POST', credentials: 'include', body: fd });
  if (!res.ok) {
    let detail = 'Failų sujungti nepavyko — bandykite įkelti juos po vieną.';
    try { detail = (await res.json())?.detail || detail; } catch { /* keep the plain sentence */ }
    throw new Error(detail);
  }
  let meta = {};
  try { meta = JSON.parse(decodeURIComponent(res.headers.get('x-pathon-lapai') || '')) || {}; } catch { meta = {}; }
  const blob = await res.blob();
  const file = new File([blob], combinedName(list), { type: 'application/pdf' });
  return { file, overrides: sheetOverridesFromNames(meta.pavadinimai), pages: Array.isArray(meta.lapai) ? meta.lapai.length : null };
}
