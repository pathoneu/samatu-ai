/**
 * RoomNameChips — „Ar tai virtuvė? [Taip] [Kita…]" for a room outlined without a row in the room table
 * (Pathon v3 W5-C, C3 / coverage #39). The proposal comes from the words the drawing writes inside the
 * room's outline (lib/roomNames → GET …/name-hints), the word itself is shown as the evidence, and one click
 * answers. „Kita…" opens the known room kinds and a field for his own name. Nothing is saved until he
 * answers; the answer goes down the room edit path (the sheet shows what moved and „Atšaukti pataisymą").
 */

import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Check, Tag } from 'lucide-react';

import { fetchNameHints, namesAreAsked, openHints, ROOM_NAME_CHOICES } from '@/lib/roomNames';

const CHIP = 'inline-flex min-h-[36px] items-center gap-1.5 rounded-[2px] border px-3 text-[14px] font-semibold '
  + 'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50';

export default function RoomNameChips({ projectId, room, busy = false, onAnswer }) {
  const { t } = useTranslation();
  const [hints, setHints] = useState(null);
  const [other, setOther] = useState(false);
  const [own, setOwn] = useState('');
  const asked = namesAreAsked(room);
  const nr = room?.nr != null ? String(room.nr) : null;

  useEffect(() => {
    setHints(null);
    setOther(false);
    setOwn('');
    if (!asked || !projectId || !nr) return undefined;
    const ctl = new AbortController();
    fetchNameHints(projectId, nr, { signal: ctl.signal })
      .then((data) => setHints(Array.isArray(data?.hints) ? data.hints : []))
      .catch(() => { if (!ctl.signal.aborted) setHints([]); });
    return () => ctl.abort();
  }, [asked, projectId, nr]);

  const open = openHints(room, hints);
  if (!asked || open.length === 0) return null;
  const first = open[0];

  return (
    <div className="border-t border-border px-4 py-3" data-testid="room-name-chips">
      <p className="flex items-start gap-2 text-[15px] font-semibold">
        <Tag className="mt-0.5 h-4 w-4 shrink-0 text-ink-2" aria-hidden="true" />
        {t('project.roomNames.question', { name: first.pavadinimas.toLocaleLowerCase('lt-LT') })}
      </p>
      <p className="mt-0.5 pl-6 text-[14px] leading-snug text-ink-2">
        {t('project.roomNames.evidence', { word: first.zodis })}
      </p>
      <div className="mt-2 flex flex-wrap gap-2 pl-6">
        <button
          type="button"
          disabled={busy}
          onClick={() => onAnswer?.(first)}
          className={`${CHIP} border-accent-2 bg-accent-2 text-white`}
          data-testid="room-name-yes"
        >
          <Check className="h-4 w-4" aria-hidden="true" />
          {t('project.roomNames.yes')}
        </button>
        {open.slice(1).map((h) => (
          <button
            key={h.pavadinimas}
            type="button"
            disabled={busy}
            onClick={() => onAnswer?.(h)}
            className={`${CHIP} border-border bg-card hover:bg-muted`}
            title={t('project.roomNames.evidence', { word: h.zodis })}
          >
            {h.pavadinimas}
          </button>
        ))}
        <button
          type="button"
          disabled={busy}
          aria-expanded={other}
          onClick={() => setOther((v) => !v)}
          className={`${CHIP} border-border bg-card hover:bg-muted`}
          data-testid="room-name-other"
        >
          {t('project.roomNames.other')}
        </button>
      </div>
      {other && (
        <div className="mt-2 pl-6" data-testid="room-name-other-list">
          <div className="flex flex-wrap gap-1.5">
            {ROOM_NAME_CHOICES.map((c) => (
              <button
                key={c.pavadinimas}
                type="button"
                disabled={busy}
                onClick={() => onAnswer?.(c)}
                className={`${CHIP} min-h-[32px] border-border bg-card font-medium hover:bg-muted`}
              >
                {c.pavadinimas}
              </button>
            ))}
          </div>
          <form
            className="mt-2 flex flex-wrap items-center gap-2"
            onSubmit={(e) => { e.preventDefault(); if (own.trim()) onAnswer?.({ pavadinimas: own.trim() }); }}
          >
            <label className="text-[14px] text-ink-2" htmlFor={`room-name-own-${nr}`}>{t('project.roomNames.ownLabel')}</label>
            <input
              id={`room-name-own-${nr}`}
              value={own}
              onChange={(e) => setOwn(e.target.value)}
              className="h-9 w-48 rounded-[2px] border border-border bg-card px-2 text-[15px]"
            />
            <button type="submit" disabled={busy || !own.trim()} className={`${CHIP} border-border bg-card hover:bg-muted`}>
              {t('project.roomNames.save')}
            </button>
          </form>
        </div>
      )}
    </div>
  );
}
