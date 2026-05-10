import React, { useState, useEffect } from 'react';
import { AlertTriangle, X } from 'lucide-react';

/**
 * BetaDisclosureBanner — surface known formula limitations to live beta users.
 *
 * Required by the 2026-05-08 council "liability blind spot" + canonical plan
 * Task 1.1 (D1). Shows on every authenticated route (mounted in AppLayout).
 * Dismissible per session via localStorage so a returning user isn't nagged
 * forever, but the underlying language and intent are preserved.
 *
 * Tone: factual, non-alarming. Names the four positions estimators must
 * verify before bidding (langų plotai, angokraščiai, hidroizoliacija,
 * paslėptų durų staktos) so disclosure is actionable, not generic.
 */
const STORAGE_KEY = 'beta_disclosure_dismissed_2026_05_10';

export function BetaDisclosureBanner() {
  const [dismissed, setDismissed] = useState(() => {
    try {
      return window.localStorage.getItem(STORAGE_KEY) === '1';
    } catch {
      return false;
    }
  });

  useEffect(() => {
    if (!dismissed) return;
    try {
      window.localStorage.setItem(STORAGE_KEY, '1');
    } catch {
      /* ignore storage errors */
    }
  }, [dismissed]);

  if (dismissed) return null;

  return (
    <aside
      role="alert"
      className="border-y border-amber-300 bg-amber-50 px-4 py-2 text-sm text-amber-950"
      data-testid="beta-disclosure-banner"
    >
      <div className="max-w-7xl mx-auto flex items-start gap-3">
        <AlertTriangle className="w-4 h-4 mt-0.5 flex-shrink-0" />
        <div className="flex-1 min-w-0">
          <strong className="font-medium">Sąmatų AI yra beta versijoje. </strong>
          <span>
            Aptikome kelias kiekio skaičiavimo klaidas, kurios galėjo paveikti{' '}
            <strong>dažų, angokraščių, hidroizoliacijos</strong> ir{' '}
            <strong>bendrų sienų</strong> skaičiavimus. Iki kol eilutė pažymėta
            „<strong>Patikrinta</strong>“, rezultatą laikykite pagalbiniu
            juodraščiu, o ne galutine sąmata. Prieš teikdami kainos pasiūlymą
            patikrinkite kiekius.
          </span>
        </div>
        <button
          onClick={() => setDismissed(true)}
          className="flex-shrink-0 p-1 rounded hover:bg-amber-100 transition-colors"
          aria-label="Užverti perspėjimą"
          title="Užverti perspėjimą"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
    </aside>
  );
}

export default BetaDisclosureBanner;
