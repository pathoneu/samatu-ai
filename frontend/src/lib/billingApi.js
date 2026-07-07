/**
 * billingApi — thin fetch wrappers for the /api/billing/v2 surface (Phase 7).
 * Mirrors the existing *Api.js idiom (recomputeApi.js et al): explicit fetch,
 * credentials:'include', throw an Error carrying `status` + `body` so callers
 * (e.g. the paywall intercept) can branch on the HTTP code.
 */

import { API_BASE } from './apiBase.js';

async function post(path, body) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  });
  let json;
  try { json = await res.json(); } catch { json = null; }
  if (!res.ok) {
    const err = new Error(json?.message || json?.detail || `HTTP ${res.status}`);
    err.status = res.status;
    err.body = json;
    throw err;
  }
  return json;
}

/**
 * Start a Stripe Checkout session for a plan and redirect the browser there.
 * plan: 'pro' | 'studio' | 'oneoff'. On 403 {enabled:false} the caller should
 * simply do nothing (billing is off) — but that path shouldn't be reachable
 * because CTAs only mount when enabled.
 */
export async function startCheckout(plan) {
  const { url } = await post('/api/billing/v2/checkout', { plan });
  if (!url) throw new Error('Checkout negrąžino nuorodos');
  window.location.href = url;
}

/** GET invoice list: { invoices: [{ id, number, total_eur, vat_mode, created_at }] }. */
export async function getInvoices() {
  const res = await fetch(`${API_BASE}/api/billing/v2/invoices`, {
    method: 'GET',
    credentials: 'include',
    headers: { Accept: 'application/json' },
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const json = await res.json();
  return json.invoices || [];
}

/** Direct download URL for an invoice PDF (GET streams the file). */
export function invoiceDownloadUrl(id) {
  return `${API_BASE}/api/billing/v2/invoices/${id}`;
}

/**
 * Save company code (įmonės kodas) + optional PVM code via the profile PUT.
 * Required before the free trial can be consumed.
 */
export async function saveCompanyCode({ company_code, pvm_code }) {
  const res = await fetch(`${API_BASE}/api/auth/profile`, {
    method: 'PUT',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ company_code, pvm_code }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `HTTP ${res.status}`);
  }
  return res.json().catch(() => ({}));
}
