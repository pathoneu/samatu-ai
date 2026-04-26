/**
 * ScaleInfoBanner — Brėžinio mastelio aptikimo statusas su perspėjimais.
 *
 * Rodo:
 * - Aptiktas mastelis (1:50, 1:100 ir t.t.)
 * - Confidence (high/medium/low)
 * - Šaltinis (text / dimensions / sanity / fallback)
 * - Perspėjimai jei sanity rodė anomalijas
 */

import { Ruler, AlertTriangle, CheckCircle2, AlertOctagon } from 'lucide-react';

export default function ScaleInfoBanner({ scaleInfo }) {
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
    text: 'tekstinis žymeklis',
    dimensions: 'dimensijų užrašai',
    'text+dimensions': 'tekstas + dimensijos',
    sanity: 'logikos patikrinimas',
    fallback: 'numatytasis (1:50)',
  }[source] || source;

  const confLabel = {
    high: 'Aukšto patikimumo',
    medium: 'Vidutinio patikimumo',
    low: 'Žemo patikimumo',
  }[conf];

  return (
    <div className={`flex items-start gap-2 p-3 border rounded-lg text-sm ${containerCls}`}>
      <Icon className={`w-4 h-4 shrink-0 mt-0.5 ${iconColor}`} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-semibold">Brėžinio mastelis: 1:{ratio}</span>
          <span className="text-xs opacity-75">
            ({confLabel} — {sourceLabel})
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
                + dar {warnings.length - 5} perspėjimai
              </li>
            )}
          </ul>
        )}

        {sanity && sanity.suggested_scale_multiplier && (
          <div className="mt-2 text-xs bg-white/50 rounded px-2 py-1.5 border border-current/20">
            <strong>Patarimas:</strong> Plotai atrodo netinkamo dydžio
            ({sanity.anomaly_pct}% patalpų už normos ribų). Galimas mastelio
            koregavimas: ×{sanity.suggested_scale_multiplier.toFixed(2)}.
            Patikrinkite brėžinį arba pažymėkite plotus rankiniu būdu Brėžinio tab'e.
          </div>
        )}
      </div>
    </div>
  );
}
