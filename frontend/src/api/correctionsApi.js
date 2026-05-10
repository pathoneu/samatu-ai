/**
 * Per-quantity corrections API client (Week 5 Task 5.1, canonical plan).
 *
 * Distinct from `recomputeApi.js`: that one handles ASSUMPTION edits
 * (paint_class, lubu_aukstis, gestures); this one handles direct AUDIT
 * edits to a single line item (user clicks a Kiekiai cell, edits the
 * number, saves).
 */
import { API_BASE } from '../lib/apiBase';

export async function postCorrections(projectId, operations) {
  const res = await fetch(`${API_BASE}/api/corrections/${projectId}`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ project_id: projectId, operations }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Corrections POST failed: ${res.status}`);
  }
  return res.json();
}

export async function getCorrections(projectId) {
  const res = await fetch(`${API_BASE}/api/corrections/${projectId}`, {
    credentials: 'include',
  });
  if (!res.ok) {
    throw new Error(`Corrections GET failed: ${res.status}`);
  }
  return res.json();
}

/** Helper: build an `update` op for a single quantity line. */
export function buildUpdateOp({ targetCode, beforeQty, afterQty, reason }) {
  return {
    op: 'update',
    target_type: 'quantity_line',
    target_code: targetCode,
    before: { quantity: Number(beforeQty) },
    after: { quantity: Number(afterQty) },
    reason: reason || null,
  };
}

/** Helper: build a `verify` (Patikrinta) op. */
export function buildVerifyOp({ targetCode }) {
  return {
    op: 'verify',
    target_type: 'quantity_line',
    target_code: targetCode,
  };
}
