/**
 * EvidenceCrop — the actual pixels the reader looked at.
 *
 * One image, lazily loaded, with a caption that is honest about what it is:
 * a framed rectangle when the backend measured one on that page, and „visas
 * lapas" when it did not. That distinction is a contract rule, not a nicety —
 * a whole-sheet crop dressed up as a pinpoint tells the contractor to look
 * somewhere the data never pointed (docs/ARCHITECTURE.md § Room facts).
 *
 * 2026-09-07 (founder: „nieko nesimato, negaliu nei pamatyti nei prisiartinti"):
 * every crop is a button. A click opens the same rectangle large — at the
 * evidence endpoint's sharpest rendering — so a whole-sheet thumbnail of 104 px
 * becomes a readable sheet instead of a grey postage stamp.
 */

import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Maximize2 } from 'lucide-react';
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog';
import { evidenceUrl } from '@/lib/roomSheetApi';

/** The same crop URL asked at the endpoint's sharpest dpi (its own ceiling caps it). */
export function sharpCropUrl(cropUrl, dpi = 160) {
  if (!cropUrl) return null;
  return /([?&])dpi=\d+/.test(cropUrl)
    ? cropUrl.replace(/([?&])dpi=\d+/, `$1dpi=${dpi}`)
    : `${cropUrl}${cropUrl.includes('?') ? '&' : '?'}dpi=${dpi}`;
}

export default function EvidenceCrop({
  fact, alt, className = '', imgClassName = '', showCaption = true, enlargeable = true,
}) {
  const { t } = useTranslation();
  const [failed, setFailed] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [open, setOpen] = useState(false);

  const src = evidenceUrl(fact?.crop_url);
  const large = useMemo(() => evidenceUrl(sharpCropUrl(fact?.crop_url)), [fact?.crop_url]);
  const page = fact?.source?.page;
  const whole = !fact?.source?.rect_pct;

  if (!src) return null;

  const caption = [
    page != null ? t('project.roomSheet.sourcePage', { page }) : null,
    whole ? t('project.roomSheet.wholeSheet') : null,
  ].filter(Boolean).join(' · ');

  const image = failed ? (
    <p className="p-2 text-[13px] leading-snug text-muted-foreground">
      {t('project.roomSheet.cropFailed')}
    </p>
  ) : (
    <img
      src={src}
      alt={alt || ''}
      loading="lazy"
      decoding="async"
      onLoad={() => setLoaded(true)}
      onError={() => setFailed(true)}
      // A whole-sheet crop cropped again to a thumbnail shows nothing but
      // the sheet's white margin; `contain` at least renders as a page.
      className={`block w-full ${whole ? 'h-[68px] object-contain' : imgClassName}`}
    />
  );

  return (
    <figure className={`m-0 ${className}`}>
      {enlargeable && !failed ? (
        <button
          type="button"
          onClick={() => setOpen(true)}
          aria-label={t('project.roomSheet.cropEnlarge', { page: page ?? '' })}
          title={t('project.roomSheet.cropEnlarge', { page: page ?? '' })}
          className="group relative block w-full overflow-hidden rounded-[2px] border border-border bg-card text-left hover:border-[hsl(var(--accent-2))] focus:outline-none focus-visible:ring-2 focus-visible:ring-[hsl(var(--accent-2))]"
        >
          {!loaded && (
            <div className="absolute inset-0 animate-pulse bg-muted" aria-hidden="true" />
          )}
          {image}
          <span
            aria-hidden="true"
            className="absolute bottom-1 right-1 inline-flex h-6 w-6 items-center justify-center rounded-[2px] border border-border bg-card/90 text-[hsl(var(--ink-2))] opacity-80 group-hover:opacity-100"
          >
            <Maximize2 className="h-3.5 w-3.5" />
          </span>
        </button>
      ) : (
        <div className="relative overflow-hidden rounded-[2px] border border-border bg-card">
          {!loaded && !failed && (
            <div className="absolute inset-0 animate-pulse bg-muted" aria-hidden="true" />
          )}
          {image}
        </div>
      )}
      {showCaption && (
        <figcaption className="mt-1 font-mono text-[12px] leading-tight text-muted-foreground">
          {caption}
        </figcaption>
      )}
      {enlargeable && (
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogContent className="max-h-[92vh] w-[min(96vw,1400px)] max-w-none overflow-auto p-4">
            <DialogTitle className="text-[16px] font-semibold">{alt || t('project.roomSheet.cropTitle')}</DialogTitle>
            <DialogDescription className="font-mono text-[13px] text-muted-foreground">{caption}</DialogDescription>
            {open && (
              <img
                src={large || src}
                alt={alt || ''}
                decoding="async"
                className="mt-2 block h-auto w-full rounded-[2px] border border-border bg-white"
              />
            )}
            <p className="mt-2 text-[13px] text-muted-foreground">{t('project.roomSheet.cropHint')}</p>
          </DialogContent>
        </Dialog>
      )}
    </figure>
  );
}
