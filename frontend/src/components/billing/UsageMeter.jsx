/**
 * UsageMeter — compact "used / quota" bar for the Dashboard (Phase 7, Task 17).
 *
 * Renders NOTHING unless billing is enabled AND usage data is present. When a
 * light user is well under quota, shows a gentle one-off nudge. Purely
 * informational — no destructive actions.
 */

import React from 'react';
import { Link } from 'react-router';
import { useTranslation } from '@/i18n/react';
import { Progress } from '@/components/ui/progress';
import { useBilling } from '@/hooks/useBilling';

const PLAN_LABEL_KEYS = {
  free: 'usageMeter.plans.free',
  pro: 'usageMeter.plans.pro',
  studio: 'usageMeter.plans.studio',
  oneoff: 'usageMeter.plans.oneoff',
};

export default function UsageMeter() {
  const { t } = useTranslation();
  const { enabled, usage } = useBilling();

  // Flag-off invariant: no billing → no meter, ever.
  if (!enabled || !usage) return null;

  const used = Number(usage.used || 0);
  const quota = Number(usage.quota || 0);
  const remaining = usage.remaining != null ? Number(usage.remaining) : Math.max(0, quota - used);
  const hasQuota = quota > 0;
  const pct = hasQuota ? Math.min(100, Math.round((used / quota) * 100)) : 0;
  const planLabel = PLAN_LABEL_KEYS[usage.plan] ? t(PLAN_LABEL_KEYS[usage.plan]) : (usage.plan || '—');

  // Light-user nudge: subscriber using <30% of a monthly quota may be
  // overpaying vs. one-off. Only for recurring plans with a real quota.
  const showLightNudge =
    hasQuota && (usage.plan === 'pro' || usage.plan === 'studio') && used > 0 && pct < 30;

  const nearLimit = hasQuota && remaining <= Math.max(1, Math.ceil(quota * 0.1));

  const periodEnd = formatPeriodEnd(usage.current_period_end);

  return (
    <div className="rounded-xl border border-border bg-card p-4 mb-6">
      <div className="flex items-center justify-between gap-3 mb-2">
        <div className="flex items-baseline gap-2 min-w-0">
          <span className="text-sm font-semibold text-foreground">
            {hasQuota ? `${used} / ${quota}` : `${used}`} {t('usageMeter.projectsThisMonth')}
          </span>
          <span className="text-xs text-muted-foreground truncate">· {planLabel}</span>
        </div>
        {periodEnd && (
          <span className="text-[11px] text-muted-foreground shrink-0">
            {t('usageMeter.renews', { date: periodEnd })}
          </span>
        )}
      </div>

      {hasQuota && (
        <Progress value={pct} className="h-1.5" />
      )}

      {nearLimit && (
        <p className="text-[11px] mt-2" style={{ color: 'hsl(var(--source-ai))' }}>
          {remaining === 1
            ? t('usageMeter.nearLimitOne', { count: remaining })
            : t('usageMeter.nearLimitMany', { count: remaining })}
          <Link to="/pricing" className="underline underline-offset-2">{t('usageMeter.upgradePlan')}</Link>
        </p>
      )}

      {showLightNudge && !nearLimit && (
        <p className="text-[11px] text-muted-foreground mt-2">
          {t('usageMeter.lightNudgePrefix')}
          <Link to="/pricing" className="underline underline-offset-2 text-foreground/80">
            {t('usageMeter.lightNudgeLink')}
          </Link>.
        </p>
      )}
    </div>
  );
}

function formatPeriodEnd(iso) {
  if (!iso) return null;
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return null;
    return d.toISOString().slice(0, 10);
  } catch {
    return null;
  }
}
