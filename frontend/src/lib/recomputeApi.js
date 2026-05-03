/**
 * Sprint 0 Fix 2: delegate paint formula recompute to backend.
 *
 * Replaces hardcoded `*2/9, *2/10` from interiorCalc.js:187-188 which
 * ignored paint class and 1.8× absorption.
 */

const API_BASE = import.meta.env?.VITE_API_BASE || '';

export async function recompute({ rooms, edits, current_assumptions }) {
  const res = await fetch(`${API_BASE}/api/recompute-quantities`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ rooms, edits, current_assumptions }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `recompute failed: ${res.status}`);
  }
  return res.json();
}
