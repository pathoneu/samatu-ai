/**
 * M4 (2026-05-06) — Google sign-in button.
 *
 * Lights up only when the backend reports OAuth is configured. Without env
 * vars set, the button is hidden so users only see email/password login.
 *
 * Backend integration:
 *   GET  /api/auth/google/status  →  { enabled: boolean }
 *   GET  /api/auth/google?next=…   →  302 to Google consent (sets session state)
 *   GET  /api/auth/google/callback →  302 back to `next` after token exchange
 */
import { useEffect, useState } from 'react';
import { API_BASE } from '@/lib/apiBase';
import { noteSignInStarted } from '@/lib/signInHint';

export default function GoogleSignInButton({ next = '/', label = 'Prisijungti su Google' }) {
  const [enabled, setEnabled] = useState(null);

  useEffect(() => {
    let cancelled = false;
    fetch(`${API_BASE}/api/auth/google/status`, { credentials: 'include' })
      .then(r => r.ok ? r.json() : { enabled: false })
      .then(data => { if (!cancelled) setEnabled(!!data.enabled); })
      .catch(() => { if (!cancelled) setEnabled(false); });
    return () => { cancelled = true; };
  }, []);

  if (!enabled) return null;

  const href = `${API_BASE}/api/auth/google?next=${encodeURIComponent(next)}`;
  return (
    <>
      <div className="my-4 flex items-center gap-3 text-xs text-muted-foreground">
        <div className="h-px flex-1 bg-border" />
        <span>arba</span>
        <div className="h-px flex-1 bg-border" />
      </div>
      <a
        href={href}
        // The session begins behind a server redirect; this note tells the
        // restore on the way back that someone signed in (see signInHint.js).
        onClick={noteSignInStarted}
        className="w-full inline-flex items-center justify-center gap-2 px-4 py-2 border border-border rounded-md bg-background hover:bg-muted/40 text-sm font-medium transition-colors"
        data-testid="google-signin-button"
      >
        <svg viewBox="0 0 18 18" className="w-4 h-4" aria-hidden="true">
          <path fill="#4285F4" d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.71v2.26h2.92c1.7-1.57 2.68-3.88 2.68-6.61z"/>
          <path fill="#34A853" d="M9 18c2.43 0 4.47-.81 5.96-2.18l-2.92-2.26c-.81.54-1.84.86-3.04.86-2.34 0-4.32-1.58-5.03-3.7H.95v2.32A9 9 0 0 0 9 18z"/>
          <path fill="#FBBC05" d="M3.97 10.71A5.4 5.4 0 0 1 3.68 9c0-.59.1-1.16.29-1.71V4.97H.95A9 9 0 0 0 0 9c0 1.45.35 2.83.95 4.04l3.02-2.33z"/>
          <path fill="#EA4335" d="M9 3.58c1.32 0 2.51.45 3.44 1.35l2.59-2.59A9 9 0 0 0 9 0 9 9 0 0 0 .95 4.97L3.97 7.3C4.68 5.18 6.66 3.58 9 3.58z"/>
        </svg>
        <span>{label}</span>
      </a>
    </>
  );
}
