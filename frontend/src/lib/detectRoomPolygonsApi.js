/**
 * detectRoomPolygonsApi — batch accurate-polygon detection.
 *
 * POSTs the floor-plan page + room list (nr + plotas_m2) and gets back a
 * wall-following polygon for the rooms the area-prior could solve, plus a
 * 'manual_needed' marker for the rest (no garbage polygons). The PDF is sent
 * once and cached server-side (same cache as click-to-fill).
 *
 * Returns { results: { [nr]: { polygon_pct, polygon_pdf, page_width_pdf,
 *   page_height_pdf, polygon_source, confidence, area_err } | { polygon_source:
 *   'manual_needed' } }, stats }.
 */
import { API_BASE } from './apiBase';

const TIMEOUT_MS = 60000;

export async function detectRoomPolygons({ projectId, pageNr, rooms, pdfBlob = null }) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  const fd = new FormData();
  fd.set('page_nr', String(pageNr));
  fd.set('rooms_json', JSON.stringify(
    (rooms || []).map((r) => ({
      nr: String(r.nr), plotas_m2: r.plotas_m2 ?? r.plotas ?? 0, bbox_pct: r.bbox_pct ?? null,
    }))));
  if (pdfBlob) fd.set('pdf_file', pdfBlob, pdfBlob.name || 'project.pdf');
  try {
    const res = await fetch(`${API_BASE}/api/projects/${projectId}/detect-room-polygons`, {
      method: 'POST',
      credentials: 'include',
      signal: controller.signal,
      body: fd,
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || `detect-room-polygons HTTP ${res.status}`);
    }
    return await res.json();
  } finally {
    clearTimeout(timer);
  }
}
