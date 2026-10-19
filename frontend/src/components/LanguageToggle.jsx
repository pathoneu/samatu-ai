/**
 * LanguageToggle — small LT/EN segmented switch for the public marketing
 * chrome (landing nav, footer, legal pages). Styled for the dark graphite
 * identity: mono labels, orange active segment, subtle bordered pill.
 *
 * Switches i18next live and persists the choice to localStorage
 * (`pathon_lang`) via changeAppLanguage(). Public pages only — the
 * authenticated app stays LT for a later phase.
 */
import React from 'react';
import { useTranslation } from '@/i18n/react';
import { changeAppLanguage, SUPPORTED_LANGS } from '@/i18n';

export default function LanguageToggle({ className = '', size = 'sm' }) {
  const { i18n, t } = useTranslation();
  const active = SUPPORTED_LANGS.includes(i18n.resolvedLanguage)
    ? i18n.resolvedLanguage
    : 'lt';

  const pad = size === 'sm' ? 'px-2 py-0.5' : 'px-2.5 py-1';

  return (
    <div
      className={`inline-flex items-center rounded-md border border-border bg-surface-2/60 p-0.5 ${className}`}
      role="group"
      aria-label={t('lang.label')}
    >
      {SUPPORTED_LANGS.map((lng) => {
        const isActive = lng === active;
        return (
          <button
            key={lng}
            type="button"
            onClick={() => changeAppLanguage(lng)}
            aria-pressed={isActive}
            className={`font-mono text-[11px] uppercase tracking-[0.06em] rounded ${pad} transition-colors ${
              isActive
                ? 'bg-primary/[0.14] text-primary'
                : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            {t(`lang.${lng}`)}
          </button>
        );
      })}
    </div>
  );
}
