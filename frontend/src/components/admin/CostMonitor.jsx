/**
 * CostMonitor — the prominent "don't go bankrupt" screen. Sourced entirely
 * from /api/admin/v2/cost-monitor (usage_events.cost_eur, the accurate meter)
 * plus the analytics daily series for the cost chart.
 *
 * Layout:
 *  - Left rail: today's spend vs a soft daily budget (progress), avg
 *    €/ekstrakcija, and the threshold-alerts list (warning severity).
 *  - Right: a daily cost_eur area chart over the window + per-model cost bars.
 *
 * Backend key names confirmed against admin_v2.py / db.py:
 *   total_cost_eur, today_cost_eur, avg_cost_per_extraction_eur,
 *   alert_threshold_eur, top_users[], by_model[{model,cost_eur,event_count}],
 *   alerts[{user_id, email, spend_today_eur}].
 */
import React from 'react';
import { useTranslation } from 'react-i18next';
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from 'recharts';
import { AlertTriangle, ShieldCheck, Wallet, Gauge } from 'lucide-react';
import { Panel, SectionHead, EmptyLine, ErrorLine, BlockSkeleton } from './adminPrimitives';
import { fmtEur, fmtEurPrecise, fmtInt, fmtAxisDate, densifySeries } from './adminUtils';

const ORANGE = 'hsl(22 93% 54%)';
const NEUTRAL = 'hsl(215 11% 59%)';
const GRID = 'hsl(220 15% 19%)';

/** Soft daily budget = alert threshold × a small fleet factor. Tunable;
 *  purely a visual reference bar, not enforced anywhere. */
function softDailyBudget(alertThreshold) {
  const t = Number(alertThreshold) || 5;
  return Math.max(t * 4, 20);
}

function CostTooltip({ active, payload, label }) {
  const { t } = useTranslation();
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-border/60 bg-background px-3 py-2 text-xs shadow-xl">
      <div className="font-medium text-foreground mb-1">{label}</div>
      <div className="flex items-center justify-between gap-4 tabular-nums">
        <span className="text-muted-foreground">{t('admin.cost.expenses')}</span>
        <span className="font-mono text-primary">{fmtEur(payload[0].value)}</span>
      </div>
    </div>
  );
}

function ModelTooltip({ active, payload }) {
  const { t } = useTranslation();
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  return (
    <div className="rounded-lg border border-border/60 bg-background px-3 py-2 text-xs shadow-xl">
      <div className="font-mono text-foreground mb-1 break-all max-w-[220px]">{p.model}</div>
      <div className="flex items-center justify-between gap-4 tabular-nums">
        <span className="text-muted-foreground">{t('admin.cost.expenses')}</span>
        <span className="font-mono text-primary">{fmtEur(p.cost_eur)}</span>
      </div>
      <div className="flex items-center justify-between gap-4 tabular-nums">
        <span className="text-muted-foreground">{t('admin.cost.events')}</span>
        <span className="font-mono text-foreground">{fmtInt(p.event_count)}</span>
      </div>
    </div>
  );
}

function StatTile({ icon: Icon, label, value, sub }) {
  return (
    <div className="rounded-lg border border-border bg-secondary/40 p-3">
      <div className="flex items-center gap-1.5 skyrius-header mb-1.5">
        <Icon className="w-3.5 h-3.5" />
        {label}
      </div>
      <div
        className="tabular-nums text-foreground"
        style={{ fontFamily: 'var(--font-mono)', fontSize: 20, fontWeight: 600, letterSpacing: '-0.01em' }}
      >
        {value}
      </div>
      {sub && <div className="text-[11px] text-muted-foreground mt-0.5">{sub}</div>}
    </div>
  );
}

export default function CostMonitor({ cost, analytics, loading, error, days }) {
  const { t } = useTranslation();
  return (
    <section>
      <SectionHead
        eyebrow={t('admin.cost.eyebrow')}
        title={t('admin.cost.title')}
        hint={t('admin.cost.hint')}
      />

      {error && <ErrorLine message={error} />}

      {loading && !cost && !error && <BlockSkeleton height={280} />}

      {cost && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* ── Left rail: today vs budget + avg + alerts ── */}
          <div className="space-y-3">
            <TodayVsBudget cost={cost} />
            <div className="grid grid-cols-2 gap-3">
              <StatTile
                icon={Wallet}
                label={t('admin.cost.totalTile')}
                value={fmtEur(cost.total_cost_eur)}
                sub={t('admin.cost.perDays', { count: days })}
              />
              <StatTile
                icon={Gauge}
                label={t('admin.cost.avgTile')}
                value={fmtEurPrecise(cost.avg_cost_per_extraction_eur)}
                sub={t('admin.cost.avgSub')}
              />
            </div>
            <AlertsList cost={cost} />
          </div>

          {/* ── Right: cost chart + per-model bars ── */}
          <div className="lg:col-span-2 space-y-4">
            <Panel className="p-4">
              <div className="skyrius-header mb-3">{t('admin.cost.dailyCost')}</div>
              <CostAreaChart analytics={analytics} days={days} />
            </Panel>
            <Panel className="p-4">
              <div className="skyrius-header mb-3">{t('admin.cost.byModel')}</div>
              <ModelBars byModel={cost.by_model} />
            </Panel>
          </div>
        </div>
      )}
    </section>
  );
}

function TodayVsBudget({ cost }) {
  const { t } = useTranslation();
  const today = Number(cost.today_cost_eur) || 0;
  const budget = softDailyBudget(cost.alert_threshold_eur);
  const pct = Math.min(100, (today / budget) * 100);
  const over = today > budget;
  const barColor = over
    ? 'bg-red-500'
    : pct > 75
      ? 'bg-primary'
      : 'bg-emerald-500';

  return (
    <Panel className="p-4" tone={over ? 'warning' : undefined}>
      <div className="skyrius-header mb-1.5">{t('admin.cost.today')}</div>
      <div className="flex items-baseline gap-2">
        <span
          className="tabular-nums text-foreground"
          style={{ fontFamily: 'var(--font-mono)', fontSize: 30, fontWeight: 700, letterSpacing: '-0.02em', lineHeight: 1 }}
        >
          {fmtEur(today)}
        </span>
        <span className="text-xs text-muted-foreground tabular-nums">
          / {fmtEur(budget)} {t('admin.cost.budgetSuffix')}
        </span>
      </div>
      <div className="mt-3 h-2 w-full rounded-full bg-secondary overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${barColor}`}
          style={{ width: `${Math.max(pct, 2)}%` }}
        />
      </div>
      <div className="mt-1.5 text-[11px] text-muted-foreground">
        {over
          ? t('admin.cost.over')
          : t('admin.cost.pctOfBudget', { pct: Math.round(pct) })}
      </div>
    </Panel>
  );
}

function AlertsList({ cost }) {
  const { t } = useTranslation();
  const alerts = cost.alerts || [];
  const threshold = cost.alert_threshold_eur;

  if (alerts.length === 0) {
    return (
      <Panel className="p-4">
        <div className="flex items-center gap-2 text-emerald-400">
          <ShieldCheck className="w-4 h-4" />
          <span className="text-sm font-medium">{t('admin.cost.noAlerts')}</span>
        </div>
        <p className="text-[11px] text-muted-foreground mt-1">
          {t('admin.cost.noAlertsDesc', { threshold: fmtEur(threshold) })}
        </p>
      </Panel>
    );
  }

  return (
    <Panel className="overflow-hidden" tone="warning">
      <div className="flex items-center gap-2 px-4 py-2.5 bg-primary/10 border-b border-primary/25">
        <AlertTriangle className="w-4 h-4 text-primary" />
        <span className="text-sm font-semibold text-foreground">
          {t('admin.cost.alerts', { count: alerts.length })}
        </span>
        <span className="ml-auto text-[11px] text-muted-foreground tabular-nums">
          {t('admin.cost.limitPerDay', { threshold: fmtEur(threshold) })}
        </span>
      </div>
      <ul className="divide-y divide-border/60">
        {alerts.map((a) => (
          <li key={a.user_id} className="flex items-center justify-between gap-3 px-4 py-2">
            <span className="text-xs text-foreground truncate" title={a.email || a.user_id}>
              {a.email || a.user_id?.slice(0, 8) || '—'}
            </span>
            <span className="text-xs font-mono tabular-nums text-primary shrink-0">
              {fmtEur(a.spend_today_eur)}
            </span>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

function CostAreaChart({ analytics, days }) {
  const { t } = useTranslation();
  const series = densifySeries(analytics?.series, days).map((r) => ({
    date: r.date,
    cost_eur: Number(r.cost_eur) || 0,
  }));
  const hasData = series.some((r) => r.cost_eur > 0);

  if (!hasData) {
    return <EmptyLine>{t('admin.cost.noCostData')}</EmptyLine>;
  }

  return (
    <div style={{ height: 200 }}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={series} margin={{ top: 4, right: 8, left: -8, bottom: 0 }}>
          <defs>
            <linearGradient id="costFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={ORANGE} stopOpacity={0.35} />
              <stop offset="100%" stopColor={ORANGE} stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke={GRID} strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="date"
            tickFormatter={fmtAxisDate}
            tick={{ fill: NEUTRAL, fontSize: 10 }}
            tickLine={false}
            axisLine={{ stroke: GRID }}
            minTickGap={24}
          />
          <YAxis
            tick={{ fill: NEUTRAL, fontSize: 10 }}
            tickLine={false}
            axisLine={false}
            width={44}
            tickFormatter={(v) => `${v}€`}
          />
          <Tooltip content={<CostTooltip />} cursor={{ stroke: GRID }} />
          <Area
            type="monotone"
            dataKey="cost_eur"
            stroke={ORANGE}
            strokeWidth={2}
            fill="url(#costFill)"
            dot={false}
            activeDot={{ r: 3, fill: ORANGE }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

function ModelBars({ byModel }) {
  const { t } = useTranslation();
  const data = (byModel || [])
    .map((m) => ({ ...m, cost_eur: Number(m.cost_eur) || 0 }))
    .filter((m) => m.cost_eur > 0);

  if (data.length === 0) {
    return <EmptyLine>{t('admin.cost.noModelData')}</EmptyLine>;
  }

  // Short label for the axis (strip vendor prefixes / date suffixes visually).
  const shortLabel = (model) => {
    const s = String(model || 'unknown');
    return s.length > 22 ? `${s.slice(0, 20)}…` : s;
  };

  return (
    <div style={{ height: Math.max(120, data.length * 38) }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 0, right: 12, left: 0, bottom: 0 }}
        >
          <CartesianGrid stroke={GRID} strokeDasharray="3 3" horizontal={false} />
          <XAxis
            type="number"
            tick={{ fill: NEUTRAL, fontSize: 10 }}
            tickLine={false}
            axisLine={{ stroke: GRID }}
            tickFormatter={(v) => `${v}€`}
          />
          <YAxis
            type="category"
            dataKey="model"
            tick={{ fill: NEUTRAL, fontSize: 10, fontFamily: 'var(--font-mono)' }}
            tickFormatter={shortLabel}
            tickLine={false}
            axisLine={false}
            width={150}
          />
          <Tooltip content={<ModelTooltip />} cursor={{ fill: 'hsl(222 16% 16% / 0.5)' }} />
          <Bar dataKey="cost_eur" radius={[0, 4, 4, 0]} maxBarSize={22}>
            {data.map((_, i) => (
              <Cell key={i} fill={i === 0 ? ORANGE : NEUTRAL} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
