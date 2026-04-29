import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { Loader2 } from 'lucide-react';
import { format } from 'date-fns';
import { lt } from 'date-fns/locale';

/**
 * ProjectCard — vertical card mirroring claude.ai/design prototype
 * (`prototype/screen-dashboard.jsx ProjectCard`):
 * - Title (13/600) + company (11 muted) + status pill (PARUOŠTA/AP)
 * - Big 26px tabular gross sum with tiny € suffix
 * - Footer: row count + date, separated by top border
 * - Hover: translate-y(-1px) + accent border
 */

function fmtDate(value) {
  if (!value) return '—';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return '—';
  try { return format(d, 'yyyy-MM-dd', { locale: lt }); }
  catch { return '—'; }
}

function fmtSum(net, vatRate = 21) {
  if (!net) return null;
  const gross = net * (1 + vatRate / 100);
  return Math.round(gross).toLocaleString('lt-LT');
}

export default function ProjectCard({ project }) {
  const [hover, setHover] = useState(false);
  // Sprint §FIX (2026-04-29): backend's /extract-interior emits status="ok",
  // recompute-interior also emits "ok", and legacy projects have undefined.
  // All three should render as "Paruošta", not "Klaida".
  const isReady = project.status === 'ready'
    || project.status === 'ok'
    || project.status === undefined;
  const isProcessing = project.status === 'processing';

  // Compute net & gross from darbu_sarasas if total_value not set
  const totalNet = project.total_value
    || (project.darbu_sarasas || []).reduce(
      (s, it) => s + (it.kiekis || 0) * (it.kaina || 0), 0,
    );
  const grossDisplay = fmtSum(totalNet, project.vat_rate || 21);
  const dateStr = fmtDate(project.created_date || project.created_at || project.updated_at);
  const rowCount = project.darbu_sarasas?.length || project.total_rows || 0;

  const card = (
    <div
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      className="flex flex-col gap-3.5 transition-all"
      style={{
        background: 'hsl(var(--card))',
        border: '1px solid ' + (hover && isReady ? 'hsl(var(--primary) / 0.3)' : 'hsl(var(--border))'),
        borderRadius: 6, padding: 16,
        cursor: isReady ? 'pointer' : 'default',
        transform: hover && isReady ? 'translateY(-1px)' : 'none',
      }}
    >
      <div className="flex justify-between items-start gap-2.5">
        <div className="min-w-0">
          <div
            className="font-semibold text-foreground truncate"
            style={{ fontSize: 13, letterSpacing: '-0.005em' }}
          >
            {project.name || 'Be pavadinimo'}
          </div>
          {project.company_name && (
            <div className="text-muted-foreground truncate mt-0.5" style={{ fontSize: 11 }}>
              {project.company_name}
            </div>
          )}
        </div>
        <span
          className="font-medium uppercase tracking-wide whitespace-nowrap"
          style={{
            fontSize: 10, padding: '2px 7px', borderRadius: 3,
            border: '1px solid ' + (isReady
              ? 'hsl(var(--primary) / 0.3)'
              : 'hsl(var(--source-ai) / 0.4)'),
            color: isReady ? 'hsl(var(--primary))' : 'hsl(var(--source-ai))',
            background: 'hsl(var(--card))',
          }}
        >
          {isReady ? 'Paruošta' : isProcessing ? 'Apdoroja' : 'Klaida'}
        </span>
      </div>

      {grossDisplay ? (
        <div
          className="tabular text-foreground font-semibold mono"
          style={{ fontSize: 26, letterSpacing: '-0.02em' }}
        >
          {grossDisplay}
          <span className="text-muted-foreground font-normal ml-1" style={{ fontSize: 15 }}>
            €
          </span>
        </div>
      ) : isProcessing ? (
        <div className="flex items-center gap-2" style={{ height: 32 }}>
          <Loader2 className="w-3.5 h-3.5 animate-spin text-primary" />
          <span className="text-muted-foreground" style={{ fontSize: 11 }}>
            Apdorojama PDF…
          </span>
        </div>
      ) : (
        <div className="text-muted-foreground" style={{ fontSize: 11, height: 32, lineHeight: '32px' }}>
          Kainos dar nesuvestos
        </div>
      )}

      <div
        className="flex justify-between text-muted-foreground"
        style={{
          fontSize: 10, paddingTop: 8,
          borderTop: '1px solid hsl(var(--border) / 0.6)',
        }}
      >
        <span className="tabular">{rowCount} eilučių</span>
        <span className="tabular">{dateStr}</span>
      </div>
    </div>
  );

  return isReady
    ? <Link to={`/project/${project.id}`} className="no-underline">{card}</Link>
    : <div>{card}</div>;
}
