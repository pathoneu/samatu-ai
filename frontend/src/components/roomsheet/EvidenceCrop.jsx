/**
 * EvidenceCrop — the actual pixels the reader looked at.
 *
 * One image, lazily loaded, with a caption that is honest about what it is:
 * a framed rectangle when the backend measured one on that page, and „visas
 * lapas" when it did not. That distinction is a contract rule, not a nicety —
 * a whole-sheet crop dressed up as a pinpoint tells the contractor to look
 * somewhere the data never pointed (docs/ARCHITECTURE.md § Room facts).
 */

import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { evidenceUrl } from '@/lib/roomSheetApi';

export default function EvidenceCrop({
  fact, alt, className = '', imgClassName = '', showCaption = true,
}) {
  const { t } = useTranslation();
  const [failed, setFailed] = useState(false);
  const [loaded, setLoaded] = useState(false);

  const src = evidenceUrl(fact?.crop_url);
  const page = fact?.source?.page;
  const whole = !fact?.source?.rect_pct;

  if (!src) return null;

  return (
    <figure className={`m-0 ${className}`}>
      <div className="relative overflow-hidden rounded-[2px] border border-border bg-card">
        {!loaded && !failed && (
          <div className="absolute inset-0 animate-pulse bg-muted" aria-hidden="true" />
        )}
        {failed ? (
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
        )}
      </div>
      {showCaption && (
        <figcaption className="mt-1 font-mono text-[12px] leading-tight text-muted-foreground">
          {page != null && t('project.roomSheet.sourcePage', { page })}
          {page != null && whole ? ' · ' : ''}
          {whole && t('project.roomSheet.wholeSheet')}
        </figcaption>
      )}
    </figure>
  );
}
