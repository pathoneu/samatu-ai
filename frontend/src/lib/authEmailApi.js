/**
 * authEmailApi.js — the emailed-link routes (v3 W7-A M2): password reset and
 * email verification. Backend: backend/api/auth_email.py.
 *
 * Every call resolves to { ok, message, status } and never throws, so the pages
 * only decide what to show. `message` is the server's own Lithuanian sentence
 * when it sent one.
 */
import { API_BASE } from './apiBase.js';

/** The server's message out of a FastAPI error body (string or {message}). */
export function detailMessage(body) {
  const d = body?.detail;
  if (typeof d === 'string') return d;
  if (d && typeof d.message === 'string') return d.message;
  if (typeof body?.message === 'string') return body.message;
  return '';
}

async function call(path, { method = 'POST', body } = {}, fetchImpl = fetch) {
  try {
    const res = await fetchImpl(`${API_BASE}${path}`, {
      method,
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      ...(body ? { body: JSON.stringify(body) } : {}),
    });
    let data = null;
    try { data = await res.json(); } catch { data = null; }
    return { ok: res.ok, status: res.status, message: detailMessage(data), data };
  } catch {
    return { ok: false, status: 0, message: '', data: null };
  }
}

export const emailStatus = (f) => call('/api/auth/email-status', { method: 'GET' }, f);
export const forgotPassword = (email, f) => call('/api/auth/forgot-password', { body: { email } }, f);
export const resendVerification = (email, f) => call('/api/auth/resend-verification', { body: { email } }, f);
export const verifyEmail = (token, f) => call('/api/auth/verify-email', { body: { token } }, f);
export const resetPassword = (token, newPassword, f) =>
  call('/api/auth/reset-password', { body: { token, new_password: newPassword } }, f);

/** The one-time code out of `?token=…` ('' when absent). */
export function tokenFromSearch(search) {
  try {
    return (new URLSearchParams(search || '').get('token') || '').trim();
  } catch {
    return '';
  }
}
