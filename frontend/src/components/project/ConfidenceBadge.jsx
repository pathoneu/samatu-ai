/**
 * ConfidenceBadge — Phase C-2 replacement for PolygonReviewBadge.
 *
 * Reflects AREA confidence (whether plotas_m2 is trustworthy) — NOT polygon
 * existence. A room with eksplikacija-derived plotas_m2 but no manual polygon
 * is 🟡 medium-trust and offers a one-click ✓ patvirtinta to flip to 🟢.
 *
 * Colors:
 *   🟢 tikslus  — multiple sources agree, OR user clicked ✓ patvirtinta
 *   🟡 tikrinti — single source, plausible
 *   🔴 neaišku — sources disagree, OR weak Vision-only
 */

import { useTranslation } from 'react-i18next';
import { computeAreaConfidence } from '@/lib/areaConfidence';
import { markRoomVerified } from '@/lib/projectStore';
import { Check } from 'lucide-react';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';

// Dark graphite palette (2026-07-05). -300 text on a /15 fill of the same
// hue reads clearly and passes AA on the graphite background; the previous
// -700-on-(-50) treatment (from the light-paper era) washed out to bright
// pastel pills on dark. Mirrors the --conf-* tokens.
// label/meaning resolve against i18n at render (project.confidence.*).
const STYLES = {
  high: {
    cls: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
    dot: '🟢',
    labelKey: 'project.confidence.highLabel',
    meaningKey: 'project.confidence.highMeaning',
  },
  medium: {
    cls: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
    dot: '🟡',
    labelKey: 'project.confidence.mediumLabel',
    meaningKey: 'project.confidence.mediumMeaning',
  },
  low: {
    cls: 'bg-red-500/15 text-red-300 border-red-500/30',
    dot: '🔴',
    labelKey: 'project.confidence.lowLabel',
    meaningKey: 'project.confidence.lowMeaning',
  },
};

export default function ConfidenceBadge({ room, projectId, onClick }) {
  const { t } = useTranslation();
  const result = computeAreaConfidence(room);
  if (result.confidence === 'unknown') return null;
  // Founder ask (2026-07-09): show the confidence dot on EVERY room, including
  // 🟢 high — the traffic-light system (🟢 read directly / 🟡 assumption /
  // 🔴 default) is a core trust signal and must be visible per CLAUDE.md §7,
  // not hidden for "clean" rooms. (Was: hide 'high' to declutter — 2026-05-06.)

  const style = STYLES[result.confidence];
  if (!style) return null;

  const sourceList = result.sources
    .map((s) => `${s.label}: ${s.value?.toFixed?.(2) ?? '—'} m²`);
  const verifiedLine = result.userVerified
    ? t('project.confidence.verifiedLine', { date: new Date(room.user_verified_at).toLocaleDateString('lt-LT') })
    : null;
  const disagreementLine = result.disagreement
    ? t('project.confidence.disagreementLine')
    : null;

  const showVerifyButton =
    result.confidence === 'medium' &&
    !result.userVerified &&
    projectId;

  const handleVerify = (e) => {
    e?.stopPropagation?.();
    if (projectId && room?.nr) {
      markRoomVerified(projectId, room.nr);
    }
  };

  return (
    <span className="inline-flex items-center gap-1">
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            onClick={onClick}
            className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded border text-[10px] font-medium ${style.cls}`}
            data-testid={`confidence-badge-${room.nr}`}
            data-confidence={result.confidence}
          >
            <span>{style.dot}</span>
            <span>{t(style.labelKey)}</span>
          </button>
        </TooltipTrigger>
        <TooltipContent side="top" className="max-w-[240px] text-left">
          <div className="font-semibold">{style.dot} {t(style.meaningKey)}</div>
          <div className="mt-1 opacity-90">{t('project.confidence.areaLabel', { area: room.plotas_m2?.toFixed?.(2) ?? '—' })}</div>
          {sourceList.length > 0 && (
            <ul className="mt-0.5 opacity-90">
              {sourceList.map((s, i) => <li key={i}>{s}</li>)}
            </ul>
          )}
          {verifiedLine && <div className="mt-1 opacity-90">{verifiedLine}</div>}
          {disagreementLine && <div className="mt-1">{disagreementLine}</div>}
        </TooltipContent>
      </Tooltip>
      {showVerifyButton && (
        <button
          onClick={handleVerify}
          title={t('project.confidence.verifyTitle')}
          className="inline-flex items-center gap-0.5 px-1 py-0.5 rounded border text-[9px] font-medium bg-muted/40 text-muted-foreground border-muted hover:bg-emerald-50 hover:text-emerald-700 hover:border-emerald-600 dark:hover:bg-emerald-500/15 dark:hover:text-emerald-300 dark:hover:border-emerald-500/30"
          data-testid={`verify-button-${room.nr}`}
        >
          <Check className="w-2.5 h-2.5" />
          <span>{t('project.confidence.verify')}</span>
        </button>
      )}
    </span>
  );
}
