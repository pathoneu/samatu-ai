import React from 'react';

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
        className="tabular"
        style={{ fontSize: 22, fontWeight: 600, letterSpacing: '-0.015em' }}
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
  // Sprint §28: filter out archived projects from stats (consistent with Dashboard)
  const active = projects.filter(p => !p._archived);
  const totalProjects = active.length;

  // Su PVM total — sum (kiekis × kaina) × (1+VAT/100) per project
  const totalValueWithVat = active.reduce((sum, p) => {
    const net = (p.darbu_sarasas || []).reduce(
      (s, it) => s + (it.kiekis || 0) * (it.kaina || 0),
      0,
    );
    const vat = p.vat_rate || 21;
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
      className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 border border-border rounded-md overflow-hidden mb-6"
      style={{ gap: 1, background: 'hsl(var(--border))' }}
    >
      <StatCell
        label="Aktyvūs projektai"
        value={String(totalProjects)}
        sub={totalProjects > 0 ? 'visi paruošti' : 'pradėk pirmąjį'}
      />
      <StatCell
        label="Bendra suma su PVM"
        value={
          totalValueWithVat > 0
            ? totalValueWithVat.toLocaleString('lt-LT', { maximumFractionDigits: 0 })
            : '—'
        }
        suffix={totalValueWithVat > 0 ? '€' : null}
        sub={totalValueWithVat > 0 ? 'visi paruošti' : 'kainos dar nesuvestos'}
      />
      <StatCell
        label="Visas plotas"
        value={
          totalAreaM2 > 0
            ? totalAreaM2.toLocaleString('lt-LT', { maximumFractionDigits: 1 })
            : '—'
        }
        suffix={totalAreaM2 > 0 ? 'm²' : null}
        sub={totalAreaM2 > 0 ? 'patalpų suma per visus' : null}
      />
      <StatCell
        label="Vid. pozicijų sk."
        value={avgPozicijuCount > 0 ? String(avgPozicijuCount) : '—'}
        sub={avgPozicijuCount > 0 ? 'eilutės per projektą' : null}
      />
      <StatCell
        label="Per 30 d."
        value={String(recent30d)}
        sub={recent30d > 0 ? 'naujų projektų' : 'nėra naujų'}
      />
    </div>
  );
}
