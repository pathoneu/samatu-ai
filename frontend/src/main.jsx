import React from 'react'
import ReactDOM from 'react-dom/client'
import App from '@/App.jsx'
import ErrorBoundary from '@/components/ErrorBoundary'
import '@/index.css'

// Capture unhandled promise rejections + window errors → backend log endpoint.
// Lightweight; production should swap for Sentry SDK.
const reportError = (msg, stack, component) => {
  try {
    fetch('/api/log-error', {
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
