/**
 * CookieBanner — minimal single-line bottom strip (subtle, not a modal).
 * Only essential session cookie used; no tracking — LT/EU rules don't
 * mandate consent but transparent notice is still good practice.
 */

import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { X } from 'lucide-react';

const STORAGE_KEY = 'samatu_cookie_acknowledged';

export default function CookieBanner() {
  const [show, setShow] = useState(false);

  useEffect(() => {
    try {
      if (!localStorage.getItem(STORAGE_KEY)) setShow(true);
    } catch {
      setShow(true);
    }
  }, []);

  const acknowledge = () => {
    try { localStorage.setItem(STORAGE_KEY, '1'); } catch {}
    setShow(false);
  };

  if (!show) return null;

  return (
    <div
      className="fixed bottom-0 left-0 right-0 z-50 flex items-center justify-center"
      style={{
        background: 'hsl(var(--card))',
        borderTop: '1px solid hsl(var(--border))',
        padding: '8px 16px',
        fontSize: 11,
      }}
    >
      <span className="text-muted-foreground">
        Esminis prisijungimo slapukas, jokio tracking'o.{' '}
        <Link to="/privacy" className="underline hover:text-foreground">
          Privatumas
        </Link>
      </span>
      <button
        onClick={acknowledge}
        className="ml-3 flex items-center gap-1 text-foreground/80 hover:text-foreground"
        title="Suprantu"
      >
        <X className="w-3 h-3" />
      </button>
    </div>
  );
}
