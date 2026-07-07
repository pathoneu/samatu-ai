import React from 'react'
import ReactDOM from 'react-dom/client'
import App from '@/App.jsx'
import ErrorBoundary from '@/components/ErrorBoundary'
import { initErrorTracker } from '@/lib/errorTracker'
import { initAnalytics } from '@/lib/analytics'
import { API_BASE } from '@/lib/apiBase'
import '@/i18n' // side-effect: initialise react-i18next (LT default, EN additive)
import '@/index.css'

// Sprint §24 (2026-04-29): localStorage error log so users can export
// their last 100 errors via Settings → "Eksportuoti klaidų žurnalą".
// Complementary to the backend /api/log-error post below.
initErrorTracker();

// Consent-gated GA4 (no-op until VITE_GA4_ID is set AND the visitor grants
// the "analytics" cookie category — see src/lib/analytics.js).
initAnalytics();

// Capture unhandled promise rejections + window errors → backend log endpoint.
// Lightweight; production should swap for Sentry SDK.
//
// Throttle: dedupe identical (msg|stack-head) within 5 s so one buggy render
// frame doesn't fire log-error 10× from the same root cause.
const _errorSeen = new Map(); // key -> last-fired ms
const ERROR_THROTTLE_MS = 5000;

const reportError = (msg, stack, component) => {
  if (!msg) return;
  const key = `${msg}|${(stack || '').slice(0, 200)}`;
  const now = Date.now();
  const prev = _errorSeen.get(key) || 0;
  if (now - prev < ERROR_THROTTLE_MS) return;
  _errorSeen.set(key, now);
  // Trim the dedup map occasionally so it doesn't grow unbounded.
  if (_errorSeen.size > 64) {
    for (const [k, t] of _errorSeen) {
      if (now - t > ERROR_THROTTLE_MS) _errorSeen.delete(k);
    }
  }
  try {
    fetch(`${API_BASE}/api/log-error`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: msg, stack, component, url: location.href, user_agent: navigator.userAgent }),
    }).catch(() => {});
  } catch {}
};

window.addEventListener('error', (e) => {
  reportError(e.message, e.error?.stack || '', 'window.onerror');
});
window.addEventListener('unhandledrejection', (e) => {
  reportError(
    typeof e.reason === 'string' ? e.reason : (e.reason?.message || String(e.reason)),
    e.reason?.stack || '',
    'unhandledrejection',
  );
});

ReactDOM.createRoot(document.getElementById('root')).render(
  <ErrorBoundary>
    <App />
  </ErrorBoundary>,
)
