/**
 * CookieBanner — Pathon slapukų sutikimo juosta (DARK graphite identitetas).
 *
 * Real consent UX:
 *   • Pirmą kartą (kol nėra įrašo `pathon_cookie_consent`) rodoma juosta su
 *     trumpu tekstu + nuorodomis į /cookies ir /privacy ir trimis veiksmais:
 *       „Sutikti su visais" · „Tik būtinieji" · „Tvarkyti".
 *   • „Tvarkyti" išplečia kategorijų perjungiklius:
 *       Būtinieji  — visada įjungti (disabled toggle),
 *       Analitiniai — pagal sutikimą,
 *       Rinkodaros  — pagal sutikimą.
 *   • Pasirinkimas įrašomas į localStorage kaip JSON:
 *       { categories: { necessary:true, analytics:bool, marketing:bool },
 *         timestamp: <ms> }
 *     Įrašius — juosta nebekartojama.
 *   • Persvarstyti: `openCookieSettings()` (eksportuota) arba poraštės nuoroda
 *     „Slapukų nustatymai" atveria juostą iš naujo su esamais pasirinkimais.
 *
 * Privacy-first: kol nėra sutikimo, jokios nebūtinosios kategorijos neįjungtos.
 * Būtinasis sesijos slapukas veikia nepriklausomai nuo šio pasirinkimo.
 */
import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';

export const STORAGE_KEY = 'pathon_cookie_consent';
const OPEN_EVENT = 'pathon:open-cookie-settings';

// Privacy-first default — nothing non-essential enabled until consent.
const DEFAULT_CATEGORIES = { necessary: true, analytics: false, marketing: false };

/** Read stored consent, or null if the user hasn't chosen yet. */
export function getCookieConsent() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed.categories !== 'object') return null;
    return parsed;
  } catch {
    return null;
  }
}

/** Re-open the consent banner from anywhere (footer link, /cookies page). */
export function openCookieSettings() {
  try {
    window.dispatchEvent(new CustomEvent(OPEN_EVENT));
  } catch {
    /* no-op (SSR / older browser) */
  }
}

function persist(categories) {
  try {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ categories, timestamp: Date.now() })
    );
  } catch {
    /* storage unavailable — banner will simply reappear next visit */
  }
}

// ─── Small toggle switch (dark, orange when on) ──────────────────────

function Toggle({ checked, disabled, onChange, label }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => !disabled && onChange(!checked)}
      className={`relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors duration-200
        ${checked ? 'bg-primary' : 'bg-border-strong'}
        ${disabled ? 'opacity-60 cursor-not-allowed' : 'cursor-pointer hover:brightness-110'}`}
    >
      <span
        className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow-sm transition-transform duration-200
          ${checked ? 'translate-x-[18px]' : 'translate-x-[3px]'}`}
      />
    </button>
  );
}

function CategoryRow({ title, desc, checked, disabled, badge, onChange }) {
  return (
    <div className="flex items-start justify-between gap-4 py-3 border-b border-border/70 last:border-b-0">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-[13.5px] font-medium text-foreground">{title}</span>
          {badge && (
            <span className="font-mono text-[9.5px] uppercase tracking-[0.1em] text-muted-foreground border border-border rounded px-1.5 py-0.5">
              {badge}
            </span>
          )}
        </div>
        <p className="mt-1 text-[12.5px] text-muted-foreground leading-[1.5]">{desc}</p>
      </div>
      <div className="pt-0.5">
        <Toggle checked={checked} disabled={disabled} onChange={onChange} label={title} />
      </div>
    </div>
  );
}

// ─── Banner ──────────────────────────────────────────────────────────

export default function CookieBanner() {
  const [show, setShow] = useState(false);
  const [manage, setManage] = useState(false);
  const [cats, setCats] = useState(DEFAULT_CATEGORIES);

  // First-visit: show if no stored consent yet.
  useEffect(() => {
    const existing = getCookieConsent();
    if (!existing) {
      setShow(true);
    }
  }, []);

  // Allow re-opening from the footer link / cookies page.
  useEffect(() => {
    const onOpen = () => {
      const existing = getCookieConsent();
      setCats(existing?.categories ?? DEFAULT_CATEGORIES);
      setManage(true);
      setShow(true);
    };
    window.addEventListener(OPEN_EVENT, onOpen);
    return () => window.removeEventListener(OPEN_EVENT, onOpen);
  }, []);

  const close = useCallback(() => {
    setShow(false);
    setManage(false);
  }, []);

  const acceptAll = () => {
    const chosen = { necessary: true, analytics: true, marketing: true };
    persist(chosen);
    close();
  };

  const rejectNonEssential = () => {
    const chosen = { necessary: true, analytics: false, marketing: false };
    persist(chosen);
    close();
  };

  const saveSelection = () => {
    persist({ ...cats, necessary: true });
    close();
  };

  if (!show) return null;

  return (
    <div
      className="fixed inset-x-0 bottom-0 z-[60] px-3 pb-3 sm:px-5 sm:pb-5 pointer-events-none"
      role="dialog"
      aria-modal="false"
      aria-label="Slapukų sutikimas"
    >
      <div
        className="pointer-events-auto mx-auto max-w-[720px] rounded-2xl border border-border-strong bg-card/95 backdrop-blur-md
                   shadow-[0_2px_4px_hsl(220_40%_2%/0.5),0_24px_60px_-24px_hsl(220_40%_2%/0.75)]"
      >
        <div className="p-5 sm:p-6">
          <div className="flex items-center gap-2.5">
            <span className="w-2 h-2 rounded-full bg-primary" aria-hidden />
            <span className="font-mono text-[10.5px] uppercase tracking-[0.16em] text-primary">
              Slapukai
            </span>
          </div>

          <p className="mt-3 text-[13.5px] text-ink-2 leading-[1.6]">
            Naudojame būtinuosius slapukus, kad paslauga veiktų. Su jūsų sutikimu —
            ir analitinius bei rinkodaros. Pasirinkite, ką leidžiate. Daugiau —{' '}
            <Link to="/cookies" className="text-primary hover:underline">Slapukų politikoje</Link>{' '}
            ir{' '}
            <Link to="/privacy" className="text-primary hover:underline">Privatumo politikoje</Link>.
          </p>

          {/* Category toggles — shown when "Tvarkyti" is expanded */}
          {manage && (
            <div className="mt-4 rounded-xl border border-border bg-surface-2/60 px-4">
              <CategoryRow
                title="Būtinieji"
                badge="Visada"
                desc="Prisijungimas, sesija, saugumas ir jūsų slapukų pasirinkimas. Be jų paslauga neveiktų."
                checked
                disabled
                onChange={() => {}}
              />
              <CategoryRow
                title="Analitiniai"
                desc="Apibendrinta naudojimo statistika, padedanti tobulinti paslaugą."
                checked={cats.analytics}
                onChange={(v) => setCats((c) => ({ ...c, analytics: v }))}
              />
              <CategoryRow
                title="Rinkodaros"
                desc="Aktualesnio turinio rodymas ir rinkodaros veiklos vertinimas."
                checked={cats.marketing}
                onChange={(v) => setCats((c) => ({ ...c, marketing: v }))}
              />
            </div>
          )}

          {/* Actions */}
          <div className="mt-5 flex flex-col sm:flex-row sm:items-center gap-2.5">
            {manage ? (
              <button
                onClick={saveSelection}
                className="btn-primary justify-center px-4 py-2.5 text-[13.5px]"
              >
                Įrašyti pasirinkimą
              </button>
            ) : (
              <button
                onClick={acceptAll}
                className="btn-primary justify-center px-4 py-2.5 text-[13.5px]"
              >
                Sutikti su visais
              </button>
            )}
            <button
              onClick={rejectNonEssential}
              className="btn-ghost justify-center px-4 py-2.5 text-[13.5px]"
            >
              Tik būtinieji
            </button>
            {!manage && (
              <button
                onClick={() => setManage(true)}
                className="justify-center px-4 py-2.5 text-[13.5px] text-muted-foreground hover:text-foreground transition-colors font-medium"
              >
                Tvarkyti
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
