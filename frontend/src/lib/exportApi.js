/**
 * exportApi — the two export routes of togal-v2 W8:
 *   POST /api/projects/{id}/export-excel/preview  the first rows of the grouped Excel (api/export_excel.py)
 *   POST /api/projects/{id}/export-overlay-pdf    the sheets with marks + legend, or (dry_run) sheet 1 as PNG
 */
import { API_BASE } from './apiBase';

async function post(path, body, { signal, timeoutMs = 120_000 } = {}) {
  const timeout = AbortSignal.timeout(timeoutMs);
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal: signal ? AbortSignal.any([signal, timeout]) : timeout,
  });
  if (!res.ok) {
    const detail = await res.json().then((b) => b?.detail).catch(() => null);
    const err = new Error(typeof detail === 'string' ? detail : `Serverio klaida (${res.status})`);
    err.status = res.status;
    throw err;
  }
  return res;
}

/** {grupavimas, rows: [{kind:'heading',label}|{kind:'row',…, kaip_gauta, programos}], row_count, groups} */
export async function fetchExportPreview(projectId, { grupavimas, eilutes, patalpos, lapai, limit = 20 }, opts) {
  const res = await post(`/api/projects/${encodeURIComponent(projectId)}/export-excel/preview`,
    { grupavimas, eilutes, patalpos, lapai, limit }, opts);
  return res.json();
}

/** The overlay PDF (or, with body.dry_run, the first sheet as a PNG) as a Blob. */
export async function fetchOverlayPdf(projectId, body, opts) {
  const res = await post(`/api/projects/${encodeURIComponent(projectId)}/export-overlay-pdf`, body, opts);
  return res.blob();
}
