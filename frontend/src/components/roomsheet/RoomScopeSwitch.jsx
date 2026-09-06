/**
 * RoomScopeSwitch — „Ši patalpa: skaičiuoju / neskaičiuoju".
 *
 * The one control that answers the sheet's own warnings („greičiausiai ta pati
 * patalpa antrą kartą", „ne jūsų patalpa"): switched off, the room stays on the
 * sheet and leaves every row server-side (extractor/scope.py). Two big
 * buttons, one sentence saying what the current state means.
 */

import { useTranslation } from 'react-i18next';

export default function RoomScopeSwitch({ included, busy = false, onChange }) {
  const { t } = useTranslation();
  const btn = (on, label, active) => (
    <button
      type="button"
      role="radio"
      aria-checked={active}
      disabled={busy || active}
      onClick={() => onChange?.(on)}
      className={`inline-flex min-h-[44px] items-center rounded-[2px] border px-4 text-[15px] font-semibold ${
        active
          ? 'border-[hsl(var(--accent-2))] bg-[hsl(var(--accent-2))] text-white'
          : 'border-border bg-card hover:bg-muted disabled:opacity-60'
      }`}
    >
      {label}
    </button>
  );
  return (
    <div className="border-b border-border px-4 pb-3 pt-3" data-testid="room-scope-switch">
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-[15px] font-semibold">{t('project.roomSheet.scopeRoomTitle')}</span>
        <div role="radiogroup" aria-label={t('project.roomSheet.scopeRoomTitle')} className="flex gap-2">
          {btn(true, t('project.roomSheet.scopeRoomOn'), included)}
          {btn(false, t('project.roomSheet.scopeRoomOff'), !included)}
        </div>
      </div>
      <p className="mt-1.5 text-[13px] leading-snug text-muted-foreground">
        {included ? t('project.roomSheet.scopeRoomOnNote') : t('project.roomSheet.scopeRoomOffNote')}
      </p>
    </div>
  );
}
