/**
 * ScaleInfoBanner — Brėžinio mastelio aptikimo statusas su perspėjimais.
 *
 * Rodo:
 * - Aptiktas mastelis (1:50, 1:100 ir t.t.)
 * - Confidence (high/medium/low)
 * - Šaltinis (text / dimensions / sanity / fallback)
 * - Perspėjimai jei sanity rodė anomalijas
 *
 * v3 W1-C: drawn by the one Notice — warning tone when the scale is a guess or the checks
 * complained, info otherwise (was its own amber box with dark-theme leftovers).
 */

import { useTranslation } from '@/i18n/react';
import { Ruler, AlertTriangle, CheckCircle2, AlertOctagon } from 'lucide-react';
import Notice from '@/components/ui/Notice';

export default function ScaleInfoBanner({ scaleInfo }) {
  const { t } = useTranslation();
  if (!scaleInfo) return null;

  const conf = scaleInfo.confidence || 'low';
  const ratio = scaleInfo.scale_ratio;
  const source = scaleInfo.source || 'fallback';
  const warnings = scaleInfo.warnings || [];
  const sanity = scaleInfo.sanity;

  // Default — neutral. Tik LOW confidence gauna amber warning tone'ą.
  const isWarning = conf === 'low' || warnings.length > 0;
  const Icon = conf === 'high' ? CheckCircle2 :
               conf === 'medium' ? Ruler :
               AlertTriangle;

  const sourceLabel = {
    text: t('project.scaleBanner.srcText'),
    dimensions: t('project.scaleBanner.srcDimensions'),
    'text+dimensions': t('project.scaleBanner.srcTextDimensions'),
    sanity: t('project.scaleBanner.srcSanity'),
    fallback: t('project.scaleBanner.srcFallback'),
  }[source] || source;

  const confLabel = {
    high: t('project.scaleBanner.confHigh'),
    medium: t('project.scaleBanner.confMedium'),
    low: t('project.scaleBanner.confLow'),
  }[conf];

  return (
    <Notice
      tone={isWarning ? 'warning' : 'info'}
      icon={Icon}
      title={(
        <>
          {t('project.scaleBanner.scale', { ratio })}
          <span className="ml-2 text-meta font-normal text-muted-foreground">
            {t('project.scaleBanner.confSource', { conf: confLabel, source: sourceLabel })}
          </span>
        </>
      )}
    >
      {warnings.length > 0 && (
        <ul className="space-y-1">
          {warnings.slice(0, 5).map((w, i) => {
            const text = typeof w === 'string' ? w : (w?.message || JSON.stringify(w));
            return (
              <li key={i} className="flex items-start gap-1.5">
                <AlertOctagon className="w-3.5 h-3.5 shrink-0 mt-0.5 text-muted-foreground" aria-hidden="true" />
                <span>{text}</span>
              </li>
            );
          })}
          {warnings.length > 5 && (
            <li className="text-muted-foreground">
              {t('project.scaleBanner.moreWarnings', { count: warnings.length - 5 })}
            </li>
          )}
        </ul>
      )}

      {sanity && sanity.suggested_scale_multiplier && (
        <p className="rounded px-2 py-1.5 border border-border bg-card">
          <strong>{t('project.scaleBanner.tipLabel')}</strong>{t('project.scaleBanner.tipBody', { pct: sanity.anomaly_pct, multiplier: sanity.suggested_scale_multiplier.toFixed(2) })}
        </p>
      )}
    </Notice>
  );
}
