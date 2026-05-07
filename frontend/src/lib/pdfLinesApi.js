/**
 * pdfLinesApi — fetch'ina vector linijas iš backend'o per puslapį.
 *
 * Cache'inamas per projekto ID + page, kad neperkraunant tos pačios
 * linijos iš naujo kiekvieną kartą.
 */

import { getPdfBlob } from './pdfStore';
import { API_BASE } from './apiBase';

const _cache = new Map();  // key = `${projectId}:${page}` → lines array

export async function fetchPageLines(projectId, page) {
  const key = `${projectId}:${page}`;
  if (_cache.has(key)) return _cache.get(key);

  const blob = await getPdfBlob(projectId);
  if (!blob) return null;

  const fd = new FormData();
  fd.append('files', blob, 'project.pdf');
  fd.append('page', String(page));

  try {
    const res = await fetch(`${API_BASE}/pdf-lines`, { method: 'POST', credentials: 'include', body: fd });
    const json = await res.json();
    if (json.status !== 'ok' && !json.lines) return null;
    const data = {
      lines: json.lines || [],
      page_width_pdf: json.page_width_pdf || 0,
      page_height_pdf: json.page_height_pdf || 0,
    };
    _cache.set(key, data);
    return data;
  } catch (e) {
    console.warn('fetchPageLines failed:', e);
    return null;
  }
}

export function clearLinesCache(projectId) {
  if (!projectId) {
    _cache.clear();
    return;
  }
  for (const k of [..._cache.keys()]) {
    if (k.startsWith(`${projectId}:`)) _cache.delete(k);
  }
}
