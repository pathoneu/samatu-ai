/**
 * CookieBanner — Pathon slapukų sutikimo juosta.
 *
 * Route-aware skin (2026-07-08): on the landing routes (/, /en, /about) the
 * banner wears the paper + clay palette so it matches the marketing page it
 * floats over; everywhere else (the app, legal/BoFu pages) it keeps the dark
 * graphite look. The dark path is unchanged — only a `paper` branch was added.
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
 * Docked (B1-D, the project workspace /project/…): the floating card covered the drawing's bottom edge, so
 * there it is ONE bar laid over the step bar at the bottom of the window (the same three choices, the two
 * policy links) and never over the canvas; „Tvarkyti" opens the categories above the bar.
 *
 * Privacy-first: kol nėra sutikimo, jokios nebūtinosios kategorijos neįjungtos.
 * Būtinasis sesijos slapukas veikia nepriklausomai nuo šio pasirinkimo.
 */
import React, { useState, useEffect, useCallback } from 'react';
import { Link, useLocation } from 'react-router';
import { useTranslation } from 'react-i18next';
import '@/pages/landing/landing.css'; // paper-palette tokens + pl-btn-* (scoped under #plr)

export const STORAGE_KEY = 'pathon_cookie_consent';
const OPEN_EVENT = 'pathon:open-cookie-settings';

// Landing (/, /en, /about) is the only paper+clay surface today; the app and
// the legal/BoFu pages are dark graphite. Extend this set if those get reskinned.
const PAPER_ROUTES = new Set(['/', '/en', '/about']);

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
  // Same-tab listeners (consent-gated analytics loader) need a signal —
  // the `storage` event only fires in OTHER tabs.
  try {
    window.dispatchEvent(
      new CustomEvent('pathon:cookie-consent-changed', { detail: categories })
    );
  } catch {
    /* no-op */
  }
}

// ─── Small toggle switch ─────────────────────────────────────────────

function Toggle({ checked, disabled, onChange, label, paper }) {
  if (paper) {
    return (
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={label}
        disabled={disabled}
        onClick={() => !disabled && onChange(!checked)}
        style={{
          position: 'relative',
          display: 'inline-flex',
          alignItems: 'center',
          height: 20,
          width: 36,
          flexShrink: 0,
          borderRadius: 999,
          border: 'none',
          padding: 0,
          background: checked ? 'var(--acc)' : 'var(--line2)',
          opacity: disabled ? 0.6 : 1,
          cursor: disabled ? 'not-allowed' : 'pointer',
          transition: 'background .2s ease',
        }}
      >
        <span
          style={{
            display: 'inline-block',
            height: 14,
            width: 14,
            borderRadius: '50%',
            background: '#fff',
            boxShadow: '0 1px 2px rgba(0,0,0,0.25)',
            transform: `translateX(${checked ? 18 : 3}px)`,
            transition: 'transform .2s ease',
          }}
        />
      </button>
    );
  }
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

function CategoryRow({ title, desc, checked, disabled, badge, onChange, paper }) {
  if (paper) {
    return (
      <div
        style={{
          display: 'flex',
          alignItems: 'flex-start',
          justifyContent: 'space-between',
          gap: 16,
          padding: '12px 0',
          borderBottom: '1px solid color-mix(in srgb, var(--line) 70%, transparent)',
        }}
      >
        <div style={{ minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 13.5, fontWeight: 500, color: 'var(--ink)' }}>{title}</span>
            {badge && (
              <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9.5, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--mut)', border: '1px solid var(--line2)', borderRadius: 4, padding: '2px 6px' }}>
                {badge}
              </span>
            )}
          </div>
          <p style={{ margin: '4px 0 0', fontSize: 12.5, color: 'var(--mut)', lineHeight: 1.5 }}>{desc}</p>
        </div>
        <div style={{ paddingTop: 2 }}>
          <Toggle checked={checked} disabled={disabled} onChange={onChange} label={title} paper />
        </div>
      </div>
    );
  }
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
  const { t } = useTranslation();
  const { pathname } = useLocation();
  const paper = PAPER_ROUTES.has(pathname);
  const docked = !paper && /^\/project\//.test(pathname || '');
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

  if (docked) {
    return (
      <div
        className="fixed inset-x-0 bottom-0 z-[60] border-t border-border-strong bg-card shadow-[0_-8px_24px_-16px_hsl(var(--foreground)/0.35)]"
        role="dialog"
        aria-modal="false"
        aria-label={t('cookie.ariaLabel')}
        data-testid="cookie-banner"
        data-docked="1"
      >
        {manage && (
          <div className="mx-auto max-w-[960px] px-4 pt-2">
            <CategoryRow
              title={t('cookie.catNecessaryTitle')}
              badge={t('cookie.catNecessaryBadge')}
              desc={t('cookie.catNecessaryDesc')}
              checked
              disabled
              onChange={() => {}}
            />
            <CategoryRow
              title={t('cookie.catAnalyticsTitle')}
              desc={t('cookie.catAnalyticsDesc')}
              checked={cats.analytics}
              onChange={(v) => setCats((c) => ({ ...c, analytics: v }))}
            />
            <CategoryRow
              title={t('cookie.catMarketingTitle')}
              desc={t('cookie.catMarketingDesc')}
              checked={cats.marketing}
              onChange={(v) => setCats((c) => ({ ...c, marketing: v }))}
            />
          </div>
        )}
        <div className="flex min-h-[64px] flex-wrap items-center gap-x-4 gap-y-1.5 px-4 py-2">
          <p className="min-w-[16rem] flex-1 text-ui leading-snug text-ink-2">
            {t('cookie.bodyDocked')}{' '}
            <Link to="/cookies" className="text-primary underline hover:no-underline">{t('cookie.dockedCookiesLink')}</Link>
            {' · '}
            <Link to="/privacy" className="text-primary underline hover:no-underline">{t('cookie.dockedPrivacyLink')}</Link>
          </p>
          <div className="flex shrink-0 flex-wrap items-center gap-2">
            {manage ? (
              <button onClick={saveSelection} className="btn-primary justify-center px-4 py-2 text-ui">
                {t('cookie.saveSelection')}
              </button>
            ) : (
              <button onClick={acceptAll} className="btn-primary justify-center px-4 py-2 text-ui">
                {t('cookie.acceptAll')}
              </button>
            )}
            <button onClick={rejectNonEssential} className="btn-ghost justify-center px-4 py-2 text-ui">
              {t('cookie.onlyNecessary')}
            </button>
            {!manage && (
              <button
                onClick={() => setManage(true)}
                className="justify-center px-3 py-2 text-ui font-medium text-muted-foreground transition-colors hover:text-foreground"
              >
                {t('cookie.manage')}
              </button>
            )}
          </div>
        </div>
      </div>
    );
  }

  // Paper button sizing override (the landing pl-btn-* are hero-sized).
  const paperBtn = { padding: '11px 20px', fontSize: '13.5px', borderRadius: '9px' };

  const inner = (
    <div
      className="fixed inset-x-0 bottom-0 z-[60] px-3 pb-3 sm:px-5 sm:pb-5 pointer-events-none"
      role="dialog"
      aria-modal="false"
      aria-label={t('cookie.ariaLabel')}
    >
      <div
        className={
          paper
            ? 'pointer-events-auto mx-auto max-w-[720px] rounded-2xl backdrop-blur-md'
            : 'pointer-events-auto mx-auto max-w-[720px] rounded-2xl border border-border-strong bg-card/95 backdrop-blur-md shadow-[0_2px_4px_hsl(220_40%_2%/0.5),0_24px_60px_-24px_hsl(220_40%_2%/0.75)]'
        }
        style={
          paper
            ? {
                border: '1px solid var(--line2)',
                background: 'color-mix(in srgb, var(--bg1) 96%, transparent)',
                boxShadow: '0 2px 4px color-mix(in srgb, var(--shadow) 40%, transparent), 0 28px 64px -28px var(--shadow)',
              }
            : undefined
        }
      >
        <div className="p-5 sm:p-6">
          <div className="flex items-center gap-2.5">
            <span
              className={paper ? '' : 'bg-primary'}
              style={{ width: 8, height: 8, borderRadius: '50%', background: paper ? 'var(--acc)' : undefined }}
              aria-hidden
            />
            <span
              className={paper ? '' : 'font-mono text-[10.5px] uppercase tracking-[0.16em] text-primary'}
              style={paper ? { fontFamily: "'JetBrains Mono', monospace", fontSize: 10.5, textTransform: 'uppercase', letterSpacing: '0.16em', color: 'var(--acc)' } : undefined}
            >
              {t('cookie.eyebrow')}
            </span>
          </div>

          <p
            className={paper ? '' : 'mt-3 text-[13.5px] text-ink-2 leading-[1.6]'}
            style={paper ? { margin: '12px 0 0', fontSize: 13.5, lineHeight: 1.6, color: 'var(--ink2)' } : undefined}
          >
            {t('cookie.body')}{' '}
            <Link to="/cookies" className={paper ? 'underline' : 'text-primary hover:underline'} style={paper ? { color: 'var(--acc)' } : undefined}>{t('cookie.bodyCookiesLink')}</Link>{' '}
            {t('cookie.bodyAnd')}{' '}
            <Link to="/privacy" className={paper ? 'underline' : 'text-primary hover:underline'} style={paper ? { color: 'var(--acc)' } : undefined}>{t('cookie.bodyPrivacyLink')}</Link>.
          </p>

          {/* Category toggles — shown when "Tvarkyti" is expanded */}
          {manage && (
            <div
              className={paper ? '' : 'mt-4 rounded-xl border border-border bg-surface-2/60 px-4'}
              style={paper ? { margin: '16px 0 0', borderRadius: 12, border: '1px solid var(--line)', background: 'color-mix(in srgb, var(--bg2) 45%, transparent)', padding: '0 16px' } : undefined}
            >
              <CategoryRow
                title={t('cookie.catNecessaryTitle')}
                badge={t('cookie.catNecessaryBadge')}
                desc={t('cookie.catNecessaryDesc')}
                checked
                disabled
                onChange={() => {}}
                paper={paper}
              />
              <CategoryRow
                title={t('cookie.catAnalyticsTitle')}
                desc={t('cookie.catAnalyticsDesc')}
                checked={cats.analytics}
                onChange={(v) => setCats((c) => ({ ...c, analytics: v }))}
                paper={paper}
              />
              <CategoryRow
                title={t('cookie.catMarketingTitle')}
                desc={t('cookie.catMarketingDesc')}
                checked={cats.marketing}
                onChange={(v) => setCats((c) => ({ ...c, marketing: v }))}
                paper={paper}
              />
            </div>
          )}

          {/* Actions */}
          <div className="mt-5 flex flex-col sm:flex-row sm:items-center gap-2.5">
            {manage ? (
              <button
                onClick={saveSelection}
                className={paper ? 'pl-btn-primary' : 'btn-primary justify-center px-4 py-2.5 text-[13.5px]'}
                style={paper ? paperBtn : undefined}
              >
                {t('cookie.saveSelection')}
              </button>
            ) : (
              <button
                onClick={acceptAll}
                className={paper ? 'pl-btn-primary' : 'btn-primary justify-center px-4 py-2.5 text-[13.5px]'}
                style={paper ? paperBtn : undefined}
              >
                {t('cookie.acceptAll')}
              </button>
            )}
            <button
              onClick={rejectNonEssential}
              className={paper ? 'pl-btn-ghost' : 'btn-ghost justify-center px-4 py-2.5 text-[13.5px]'}
              style={paper ? paperBtn : undefined}
            >
              {t('cookie.onlyNecessary')}
            </button>
            {!manage && (
              <button
                onClick={() => setManage(true)}
                className={paper ? '' : 'justify-center px-4 py-2.5 text-[13.5px] text-muted-foreground hover:text-foreground transition-colors font-medium'}
                style={paper ? { padding: '11px 18px', fontSize: 13.5, fontWeight: 500, color: 'var(--mut)', background: 'none', border: 'none', cursor: 'pointer' } : undefined}
              >
                {t('cookie.manage')}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );

  // Paper variant: expose the landing palette (D) variables + pl-btn-* by
  // scoping under #plr, but neutralize the #plr base layout (min-height:100vh /
  // full-bleed background) so the wrapper stays a 0-size var provider.
  if (paper) {
    return (
      <div id="plr" data-palette="N" style={{ minHeight: 0, background: 'transparent' }}>
        {inner}
      </div>
    );
  }
  return inner;
}
