/**
 * KpiRow — five headline metrics with a delta chip vs the prior window.
 * Numbers render in JetBrains Mono, tabular-nums. Cost delta is inverted
 * (a rise is bad → red).
 *
 * Data sources:
 *  - Vartotojai / Projektai / Ekstrakcijos / Pajamos ← analytics.totals + .deltas
 *  - API sąnaudos ← cost-monitor.total_cost_eur (the accurate meter), with the
 *    delta taken from analytics.deltas.cost_eur (same underlying series).
 */
import React from 'react';
import { useTranslation } from '@/i18n/react';
import { Users, FolderKanban, ScanLine, Wallet, TrendingUp } from 'lucide-react';
import { DeltaChip, KpiSkeleton } from './adminPrimitives';
import { fmtInt, fmtEur } from './adminUtils';

function KpiCard({ icon: Icon, label, value, delta, invert }) {
  return (
    <div className="border border-border rounded-xl bg-card p-4 flex flex-col justify-between min-h-[112px]">
      <div className="flex items-center justify-between">
        <span className="skyrius-header">{label}</span>
        <Icon className="w-4 h-4 text-muted-foreground/70" />
      </div>
      <div className="mt-3">
        <div
          className="tabular-nums text-foreground"
          style={{ fontFamily: 'var(--font-mono)', fontSize: 26, fontWeight: 600, letterSpacing: '-0.02em', lineHeight: 1 }}
        >
          {value}
        </div>
        <div className="mt-2 h-4">
          <DeltaChip delta={delta} invert={invert} />
        </div>
      </div>
    </div>
  );
}

export default function KpiRow({ analytics, cost, loading }) {
  const { t } = useTranslation();
  if (loading || !analytics) return <KpiSkeleton />;

  const tot = analytics.totals || {};
  const d = analytics.deltas || {};
  // Prefer the accurate cost meter from cost-monitor; fall back to analytics
  // totals if cost-monitor errored independently.
  const totalCost = cost?.total_cost_eur ?? tot.cost_eur ?? 0;

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
      <KpiCard icon={Users}        label={t('admin.kpi.users')}       value={fmtInt(tot.signups)}     delta={d.signups} />
      <KpiCard icon={FolderKanban} label={t('admin.kpi.projects')}    value={fmtInt(tot.projects)}    delta={d.projects} />
      <KpiCard icon={ScanLine}     label={t('admin.kpi.extractions')} value={fmtInt(tot.extractions)} delta={d.extractions} />
      <KpiCard icon={Wallet}       label={t('admin.kpi.apiCost')}     value={fmtEur(totalCost)}       delta={d.cost_eur} invert />
      <KpiCard icon={TrendingUp}   label={t('admin.kpi.revenue')}     value={fmtEur(tot.revenue_eur)} delta={d.revenue_eur} />
    </div>
  );
}
