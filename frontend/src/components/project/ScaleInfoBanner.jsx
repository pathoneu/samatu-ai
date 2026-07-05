/**
 * ScaleInfoBanner — Brėžinio mastelio aptikimo statusas su perspėjimais.
 *
 * Rodo:
 * - Aptiktas mastelis (1:50, 1:100 ir t.t.)
 * - Confidence (high/medium/low)
 * - Šaltinis (text / dimensions / sanity / fallback)
 * - Perspėjimai jei sanity rodė anomalijas
 */

import { useTranslation } from 'react-i18next';
import { Ruler, AlertTriangle, CheckCircle2, AlertOctagon } from 'lucide-react';

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
  const containerCls = isWarning
    ? 'bg-amber-50 border-amber-200 text-amber-900 dark:bg-amber-950/20 dark:border-amber-900/40 dark:text-amber-200'
    : 'bg-card border-border text-foreground';
  const Icon = conf === 'high' ? CheckCircle2 :
               conf === 'medium' ? Ruler :
               AlertTriangle;
  const iconColor = isWarning ? 'text-amber-600' : 'text-muted-foreground';

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
    <div className={`flex items-start gap-2 p-3 border rounded-lg text-sm ${containerCls}`}>
      <Icon className={`w-4 h-4 shrink-0 mt-0.5 ${iconColor}`} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-semibold">{t('project.scaleBanner.scale', { ratio })}</span>
          <span className="text-xs opacity-75">
            {t('project.scaleBanner.confSource', { conf: confLabel, source: sourceLabel })}
          </span>
        </div>

        {warnings.length > 0 && (
          <ul className="mt-2 space-y-1">
            {warnings.slice(0, 5).map((w, i) => {
              const text = typeof w === 'string' ? w : (w?.message || JSON.stringify(w));
              return (
                <li key={i} className="text-xs flex items-start gap-1.5">
                  <AlertOctagon className="w-3 h-3 shrink-0 mt-0.5 opacity-60" />
                  <span>{text}</span>
                </li>
              );
            })}
            {warnings.length > 5 && (
              <li className="text-xs opacity-60">
                {t('project.scaleBanner.moreWarnings', { count: warnings.length - 5 })}
              </li>
            )}
          </ul>
        )}

        {sanity && sanity.suggested_scale_multiplier && (
          <div className="mt-2 text-xs bg-background/40 rounded px-2 py-1.5 border border-current/20">
            <strong>{t('project.scaleBanner.tipLabel')}</strong>{t('project.scaleBanner.tipBody', { pct: sanity.anomaly_pct, multiplier: sanity.suggested_scale_multiplier.toFixed(2) })}
          </div>
        )}
      </div>
    </div>
  );
}
