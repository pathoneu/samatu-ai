/**
 * Re-run AI patikrinimai on a saved project without re-uploading the PDF.
 *
 * Used by SanityWarningsBanner when the user clicks "Atnaujinti AI patikrinimus".
 * Backend endpoint: POST /api/projects/{project_id}/revalidate (auth required).
 *
 * Response includes refreshed `lt_sanity` (UI mirror), `patalpos` (rooms after
 * any aukstas regrouping), and `warnings_count` for a toast.
 */

import { API_BASE } from './apiBase';

export async function revalidateProject(projectId) {
  if (!projectId) {
    throw new Error('revalidateProject: projectId is required');
  }
  const res = await fetch(
    `${API_BASE}/api/projects/${encodeURIComponent(projectId)}/revalidate`,
    {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
    }
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `revalidate failed: ${res.status}`);
  }
  return res.json();
}
