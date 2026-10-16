/**
 * RoomScopeSwitch — „Ši patalpa: skaičiuoju / neskaičiuoju" + which work areas
 * are counted in THIS room.
 *
 * The one control that answers the sheet's own warnings („greičiausiai ta pati
 * patalpa antrą kartą", „ne jūsų patalpa"): switched off, the room stays on the
 * sheet and leaves every row server-side (extractor/scope.py). Below it, three
 * chips — apdaila / grindys / plytelės — for the families a single room can
 * drop; plumbing and electrics are counted per project, so they live on the
 * general page. Two big buttons, one sentence saying what the state means.
 */

import { useTranslation } from 'react-i18next';
import { ROOM_FAMILIES } from '@/lib/scope';

export default function RoomScopeSwitch({ included, familiesOff = [], busy = false, onChange, onFamily, mergedInto = null }) {
  const { t } = useTranslation();
  if (mergedInto) {
    // „Sujungti" (2026-10-16): not a room he chose not to count — its table row is billed inside another room
    return (
      <div className="border-b border-border px-4 pb-3 pt-3" data-testid="room-scope-merged">
        <span className="text-[15px] font-semibold">Ši patalpa sujungta į {mergedInto}</span>
        <p className="mt-1.5 text-[13px] leading-snug text-muted-foreground">
          Jos plotas iš eksplikacijos ir jos langai bei durys skaičiuojami patalpoje {mergedInto}; atskirų eilučių ji neturi.
        </p>
      </div>
    );
  }
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
  const off = new Set(familiesOff);
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
      {included && onFamily && (
        <div className="mt-3" data-testid="room-scope-families">
          <p className="text-[14px] font-semibold">{t('project.roomSheet.scopeRoomFamiliesLabel')}</p>
          <div className="mt-1.5 flex flex-wrap gap-2">
            {ROOM_FAMILIES.map((fam) => {
              const on = !off.has(fam);
              return (
                <button
                  key={fam}
                  type="button"
                  role="checkbox"
                  aria-checked={on}
                  disabled={busy}
                  onClick={() => onFamily(fam, !on)}
                  className={`inline-flex min-h-[40px] items-center gap-2 rounded-[2px] border px-3 text-[14px] ${
                    on ? 'border-[hsl(var(--accent-2))] bg-[hsl(var(--accent-2))]/10 font-semibold' : 'border-border bg-card text-muted-foreground'
                  }`}
                >
                  <span aria-hidden className={`inline-flex h-[16px] w-[16px] items-center justify-center rounded-sm border text-[11px] ${
                    on ? 'border-[hsl(var(--accent-2))] bg-[hsl(var(--accent-2))] text-white' : 'border-border'}`}>
                    {on ? '✓' : ''}
                  </span>
                  {t(`newProject.q.family.${fam}`)}
                </button>
              );
            })}
          </div>
          <p className="mt-1.5 text-[13px] leading-snug text-muted-foreground">{t('project.roomSheet.scopeRoomFamiliesNote')}</p>
        </div>
      )}
    </div>
  );
}
