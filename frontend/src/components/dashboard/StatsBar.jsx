import React from 'react';
import { useTranslation } from '@/i18n/react';
import { vatPercent } from '@/lib/vatMode';

/**
 * StatsBar — 3-cell summary grid for dashboard. Mirrors claude.ai/design
 * prototype: ONE outer border, 1px gap (acts as dividers), no individual
 * card rounding. 3 honest metrics — no fabricated time-saved estimates.
 */
function StatCell({ label, value, suffix, sub }) {
  return (
    <div className="bg-card px-4 py-3.5">
      <div className="skyrius-header" style={{ fontSize: 9, marginBottom: 8 }}>
        {label}
      </div>
      <div
        className="tabular mono"
        style={{ fontSize: 22, fontWeight: 500, letterSpacing: '-0.015em' }}
      >
        {value}
        {suffix && (
          <span
            className="font-normal text-muted-foreground ml-1"
            style={{ fontSize: 14 }}
          >
            {suffix}
          </span>
        )}
      </div>
      {sub && (
        <div className="mt-1 text-muted-foreground" style={{ fontSize: 10 }}>
          {sub}
        </div>
      )}
    </div>
  );
}

function fmtDuration(seconds) {
  if (!seconds || seconds <= 0) return '—';
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m}:${String(s).padStart(2, '0')}`;
}

export default function StatsBar({ projects }) {
  const { t } = useTranslation();
  // Sprint §28: filter out archived projects from stats (consistent with Dashboard)
  const active = projects.filter(p => !p._archived);
  const totalProjects = active.length;

  // Su PVM total — sum (kiekis × kaina) × (1+VAT/100) per project
  const totalValueWithVat = active.reduce((sum, p) => {
    const net = (p.darbu_sarasas || []).reduce(
      (s, it) => s + (it.kiekis || 0) * (it.kaina || 0),
      0,
    );
    const vat = vatPercent(p);
    return sum + net * (1 + vat / 100);
  }, 0);

  // Sprint §29 (2026-04-29): nauji metrics — total m², avg pozicijų, last 30d
  const totalAreaM2 = active.reduce((s, p) => s + (p.bendras_plotas_m2 || 0), 0);
  const avgPozicijuCount = active.length > 0
    ? Math.round(active.reduce((s, p) => s + (p.darbu_sarasas?.length || 0), 0) / active.length)
    : 0;
  const recent30d = active.filter(p => {
    const ts = p.created_at ? new Date(p.created_at).getTime() : 0;
    return ts > 0 && (Date.now() - ts) < 30 * 86400 * 1000;
  }).length;

  return (
    <div
      className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 border border-border overflow-hidden mb-6"
      style={{ gap: 1, background: 'hsl(var(--border))' }}
    >
      <StatCell
        label={t('dashboard.stats.activeProjects')}
        value={String(totalProjects)}
        sub={totalProjects > 0 ? t('dashboard.stats.activeProjectsSubReady') : t('dashboard.stats.activeProjectsSubEmpty')}
      />
      <StatCell
        label={t('dashboard.stats.totalWithVat')}
        value={
          totalValueWithVat > 0
            ? totalValueWithVat.toLocaleString('lt-LT', { maximumFractionDigits: 0 })
            : '—'
        }
        suffix={totalValueWithVat > 0 ? '€' : null}
        sub={totalValueWithVat > 0 ? t('dashboard.stats.totalWithVatSubReady') : t('dashboard.stats.totalWithVatSubEmpty')}
      />
      <StatCell
        label={t('dashboard.stats.totalArea')}
        value={
          totalAreaM2 > 0
            ? totalAreaM2.toLocaleString('lt-LT', { maximumFractionDigits: 1 })
            : '—'
        }
        suffix={totalAreaM2 > 0 ? 'm²' : null}
        sub={totalAreaM2 > 0 ? t('dashboard.stats.totalAreaSub') : null}
      />
      <StatCell
        label={t('dashboard.stats.avgPositions')}
        value={avgPozicijuCount > 0 ? String(avgPozicijuCount) : '—'}
        sub={avgPozicijuCount > 0 ? t('dashboard.stats.avgPositionsSub') : null}
      />
      <StatCell
        label={t('dashboard.stats.last30d')}
        value={String(recent30d)}
        sub={recent30d > 0 ? t('dashboard.stats.last30dSub') : t('dashboard.stats.last30dSubEmpty')}
      />
    </div>
  );
}
