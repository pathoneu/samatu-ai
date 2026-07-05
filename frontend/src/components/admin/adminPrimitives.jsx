/**
 * Small shared UI atoms for the Admin v2 cockpit: section shells, a delta
 * chip (colored good/bad vs prior window), severity pills, and calm
 * loading / error / empty states. Dark-graphite identity throughout.
 */
import React from 'react';
import { useTranslation } from 'react-i18next';
import { ArrowUp, ArrowDown, Minus, AlertTriangle } from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';

/** Section header: uppercase eyebrow + title + optional right-side controls. */
export function SectionHead({ eyebrow, title, hint, right }) {
  return (
    <div className="flex items-end justify-between gap-4 mb-3">
      <div>
        {eyebrow && <div className="skyrius-header mb-1">{eyebrow}</div>}
        <h2
          className="font-semibold text-foreground"
          style={{ fontFamily: 'var(--font-display)', fontSize: 17, letterSpacing: '-0.01em' }}
        >
          {title}
        </h2>
        {hint && <p className="text-xs text-muted-foreground mt-0.5">{hint}</p>}
      </div>
      {right && <div className="shrink-0">{right}</div>}
    </div>
  );
}

/** Elevated panel — the standard card surface for a sub-section. */
export function Panel({ className, children, tone }) {
  return (
    <div
      className={cn(
        'border rounded-xl bg-card overflow-hidden',
        tone === 'warning' ? 'border-primary/40' : 'border-border',
        className,
      )}
    >
      {children}
    </div>
  );
}

/**
 * Delta chip vs prior window. `delta` is the backend shape
 * {current, prior, abs, pct}. `invert` flips good/bad colouring (used for
 * cost — a rise is "bad"). pct === null (prior 0) renders a neutral "naujas".
 */
export function DeltaChip({ delta, invert = false, unit = '%' }) {
  const { t } = useTranslation();
  if (!delta) return null;
  const { pct } = delta;

  if (pct === null || pct === undefined) {
    return (
      <span className="inline-flex items-center gap-1 text-[11px] font-medium text-muted-foreground tabular-nums">
        <Minus className="w-3 h-3" /> {t('admin.delta.new')}
      </span>
    );
  }

  const rising = pct > 0;
  const flat = pct === 0;
  // "good" = the direction the operator wants. For most metrics up is good;
  // for cost, up is bad → invert.
  const good = flat ? null : invert ? !rising : rising;
  const Icon = flat ? Minus : rising ? ArrowUp : ArrowDown;

  const color = flat
    ? 'text-muted-foreground'
    : good
      ? 'text-emerald-400'
      : 'text-red-400';

  return (
    <span
      className={cn(
        'inline-flex items-center gap-0.5 text-[11px] font-semibold tabular-nums',
        color,
      )}
      title={t('admin.delta.vsPrior')}
    >
      <Icon className="w-3 h-3" />
      {Math.abs(pct)}
      {unit}
    </span>
  );
}

/** Plan pill — coloured by plan name. */
export function PlanPill({ plan }) {
  const p = (plan || 'free').toLowerCase();
  const map = {
    free: 'bg-muted text-muted-foreground border-border',
    pro: 'bg-primary/15 text-primary border-primary/30',
    business: 'bg-violet-500/15 text-violet-300 border-violet-500/30',
    enterprise: 'bg-violet-500/15 text-violet-300 border-violet-500/30',
  };
  const cls = map[p] || 'bg-muted text-muted-foreground border-border';
  return (
    <span className={cn('inline-flex items-center rounded-md border px-2 py-0.5 text-[11px] font-medium', cls)}>
      {plan || 'free'}
    </span>
  );
}

/** Status pill — Aktyvus (green) / Išjungtas (red). */
export function StatusPill({ active }) {
  const { t } = useTranslation();
  return active ? (
    <span className="inline-flex items-center gap-1 rounded-md border border-emerald-500/30 bg-emerald-500/12 px-2 py-0.5 text-[11px] font-medium text-emerald-400">
      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
      {t('admin.status.active')}
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 rounded-md border border-red-500/30 bg-red-500/12 px-2 py-0.5 text-[11px] font-medium text-red-400">
      <span className="w-1.5 h-1.5 rounded-full bg-red-400" />
      {t('admin.status.disabled')}
    </span>
  );
}

/** Compact inline error line. */
export function ErrorLine({ message }) {
  return (
    <div className="flex items-start gap-2 p-3 bg-destructive/10 border border-destructive/30 rounded-lg text-sm text-destructive">
      <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
      <div>{message}</div>
    </div>
  );
}

/** Calm empty state. */
export function EmptyLine({ children }) {
  return (
    <div className="px-4 py-6 text-center text-sm text-muted-foreground">{children}</div>
  );
}

/** KPI-row skeleton — five card placeholders. */
export function KpiSkeleton() {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="border border-border rounded-xl bg-card p-4">
          <Skeleton className="h-3 w-20 mb-3" />
          <Skeleton className="h-7 w-24" />
        </div>
      ))}
    </div>
  );
}

/** A generic panel-height skeleton for chart / table sections. */
export function BlockSkeleton({ height = 260 }) {
  return (
    <div className="border border-border rounded-xl bg-card p-4">
      <Skeleton className="h-4 w-40 mb-4" />
      <Skeleton className="w-full" style={{ height }} />
    </div>
  );
}
