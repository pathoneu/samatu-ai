/**
 * clickToFillApi — POST /api/click-to-fill wrapper for Phase C-3.
 *
 * Backend accepts multipart form. Caller passes the PDF as a Blob/File on
 * the FIRST click for a project; the server caches it for subsequent clicks
 * (1h TTL). If the cache evicts, caller can re-send the PDF.
 *
 * Returns Promise<{polygon_pdf, page_width_pdf, page_height_pdf, confidence}>.
 * Throws Error with `.userMessage` (Lithuanian) for direct toast.
 */

import { API_BASE } from './apiBase';

const TIMEOUT_MS = 15000;

export async function clickToFill({
  projectId,
  pageNr,
  clickXPct,
  clickYPct,
  sensitivity = 0.7,
  pdfBlob = null,   // optional File/Blob — only needed once per project session
}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  const fd = new FormData();
  fd.set('project_id', projectId);
  fd.set('page_nr', String(pageNr));
  fd.set('click_x_pct', String(clickXPct));
  fd.set('click_y_pct', String(clickYPct));
  fd.set('sensitivity', String(sensitivity));
  if (pdfBlob) {
    fd.set('pdf_file', pdfBlob, pdfBlob.name || 'project.pdf');
  }
  try {
    const res = await fetch(`${API_BASE}/api/click-to-fill`, {
      method: 'POST',
      credentials: 'include',
      signal: controller.signal,
      body: fd,
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      const detail = data.detail || `HTTP ${res.status}`;
      const err = new Error(detail);
      err.userMessage = friendlyMessage(data.detail, res.status);
      err.status = res.status;
      err.rawDetail = detail;
      // 2026-05-06: log the real backend error for debugging — friendly
      // message hides it but devs need to see what actually failed.
      console.warn('[click-to-fill] backend error:', res.status, detail);
      throw err;
    }
    return await res.json();
  } catch (e) {
    if (e.name === 'AbortError') {
      const err = new Error('timeout');
      err.userMessage = 'Užpildymas užtruko per ilgai — bandykite rankiniu būdu.';
      throw err;
    }
    if (!e.userMessage) {
      e.userMessage = 'Nepavyko užpildyti — bandykite rankiniu būdu.';
    }
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

function friendlyMessage(detail, status) {
  if (status === 404) return 'Projekto PDF nerastas.';
  if (!detail) return 'Nepavyko užpildyti — bandykite rankiniu būdu.';
  if (/byte cache/i.test(detail)) {
    return 'Nepavyko rasti PDF cache — vidinė klaida. Atnaujinkite puslapį.';
  }
  if (/wall pixel/i.test(detail)) return 'Spustelėkite giliau patalpos viduje.';
  if (/too small/i.test(detail)) return 'Užpildyta zona per maža — bandykite kitoje vietoje.';
  if (/too large/i.test(detail)) return 'Užpildymas peržengė patalpos ribas — apveskite rankiniu būdu.';
  if (/jagged/i.test(detail)) return 'Užpildyta forma per netvarkinga — apveskite rankiniu būdu.';
  return 'Nepavyko užpildyti — bandykite rankiniu būdu.';
}
