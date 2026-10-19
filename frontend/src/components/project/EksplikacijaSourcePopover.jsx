/**
 * EksplikacijaSourcePopover — honest replacement for the random halo flash.
 *
 * Shows a small dropdown with the parsed eksplikacija row data when the user
 * clicks an "iš eksplikacijos" provenance chip. Uses ONLY the actual parsed
 * data (room nr, name, area, page); no PDF-coordinate guessing. Anchored to
 * the chip itself; dismissed on click-outside or Esc.
 *
 * Why this replaces EksplikacijaRowFlash:
 * The halo overlay on the rendered PDF page tried to draw a yellow rectangle
 * over the literal table row using row_bbox + canvas-to-PDF coord conversion.
 * On real projects the bbox-vs-canvas math drifted, and the halo flashed in
 * arbitrary spots — exactly the dishonest UX we set out to remove.
 */

import { useEffect, useRef } from 'react';
import { useTranslation } from '@/i18n/react';
import { areaSourceSentence } from '@/lib/areaConfidence';

export default function EksplikacijaSourcePopover({ room, anchorRect, onClose }) {
  const { t } = useTranslation();
  const ref = useRef(null);

  useEffect(() => {
    if (!room) return;
    const onKey = (e) => { if (e.key === 'Escape') onClose?.(); };
    const onClick = (e) => {
      if (ref.current && !ref.current.contains(e.target)) onClose?.();
    };
    window.addEventListener('keydown', onKey);
    window.addEventListener('mousedown', onClick);
    return () => {
      window.removeEventListener('keydown', onKey);
      window.removeEventListener('mousedown', onClick);
    };
  }, [room, onClose]);

  if (!room || !anchorRect) return null;
  const source = areaSourceSentence(room);

  // Anchor below the chip; clip to viewport.
  const top = Math.min(anchorRect.bottom + 4, window.innerHeight - 200);
  const left = Math.max(8, Math.min(anchorRect.left, window.innerWidth - 280));

  return (
    <div
      ref={ref}
      role="dialog"
      style={{
        position: 'fixed', top, left, width: 264, zIndex: 60,
        background: 'hsl(var(--card))',
        border: '1px solid hsl(var(--border))',
        borderRadius: 8,
        boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
        padding: '10px 12px',
        fontSize: 12,
        color: 'hsl(var(--foreground))',
      }}
      data-testid="eksplikacija-popover"
    >
      <div className="text-[10px] uppercase tracking-wide text-muted-foreground mb-1.5">
        {t('project.eksplikacijaPopover.head')}
      </div>
      <div className="flex items-baseline justify-between mb-1">
        <span className="font-semibold">{room.pavadinimas || t('project.eksplikacijaPopover.roomFallback', { nr: room.nr })}</span>
        <span className="mono tabular text-muted-foreground text-[10px]">{t('project.eksplikacijaPopover.nr', { nr: room.nr })}</span>
      </div>
      <div className="flex items-baseline justify-between">
        <span className="text-muted-foreground">{t('project.eksplikacijaPopover.area')}</span>
        <span className="mono tabular font-semibold">
          {room.plotas_m2?.toFixed?.(2) ?? '—'} m²
        </span>
      </div>
      {room.paskirtis && (
        <div className="flex items-baseline justify-between mt-0.5">
          <span className="text-muted-foreground">{t('project.eksplikacijaPopover.purpose')}</span>
          <span className="text-foreground/80 capitalize">{room.paskirtis}</span>
        </div>
      )}
      <div className="border-t border-border/60 mt-2 pt-2 text-[10px] text-muted-foreground">
        {t(`project.eksplikacijaPopover.source.${source.id}`, { page: source.page })}
      </div>
    </div>
  );
}
