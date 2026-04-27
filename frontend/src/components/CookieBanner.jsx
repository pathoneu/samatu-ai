/**
 * CookieBanner — minimal GDPR-friendly notice (Phase 13).
 * We only use ESSENTIAL session cookies (no tracking/ads). Per LT/EU rules,
 * essential cookies don't need explicit consent — but transparent notice is good practice.
 */

import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Cookie } from 'lucide-react';

const STORAGE_KEY = 'samatu_cookie_acknowledged';

export default function CookieBanner() {
  const [show, setShow] = useState(false);

  useEffect(() => {
    try {
      if (!localStorage.getItem(STORAGE_KEY)) setShow(true);
    } catch { /* private mode — show banner */ setShow(true); }
  }, []);

  const acknowledge = () => {
    try { localStorage.setItem(STORAGE_KEY, '1'); } catch {}
    setShow(false);
  };

  if (!show) return null;

  return (
    <div className="fixed bottom-4 left-4 right-4 md:left-auto md:right-4 md:max-w-md z-50">
      <div className="bg-card border border-border rounded-xl shadow-lg p-4">
        <div className="flex items-start gap-3">
          <Cookie className="w-5 h-5 text-primary shrink-0 mt-0.5" />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium mb-1">Slapukai</p>
            <p className="text-xs text-muted-foreground mb-3">
              Naudojame VIENĄ esminį prisijungimo slapuką (samatu_session).
              Reklamos ar tracking slapukų nėra. Daugiau —{' '}
              <Link to="/privacy" className="text-primary hover:underline">privatumo politika</Link>.
            </p>
            <button
              onClick={acknowledge}
              className="text-xs px-3 py-1.5 bg-primary text-primary-foreground rounded hover:opacity-90"
            >
              Suprantu
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
