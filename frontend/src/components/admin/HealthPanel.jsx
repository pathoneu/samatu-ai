/**
 * HealthPanel — system-health snapshot from /api/admin/v2/system-health:
 *   { totals, events_by_kind[], db_size_bytes, recent_activity, error_log_tail[], note }
 *
 * Renders table totals, event-kind volume (30d), DB size, recent-activity
 * timestamps, and the error-log `note` gracefully (there is no persisted log —
 * error_log_tail is always []; we show the note instead of a broken tail).
 */
import React from 'react';
import { Database, Info, Activity } from 'lucide-react';
import { SectionHead, Panel, EmptyLine, ErrorLine, BlockSkeleton } from './adminPrimitives';
import { fmtInt, fmtBytes, fmtRelative, fmtDateTime } from './adminUtils';

const TOTAL_LABELS = {
  users: 'Vartotojai',
  projects: 'Projektai',
  extractions: 'Ekstrakcijos',
  usage_events: 'Naudojimo įvykiai',
  invoices: 'Sąskaitos',
  corrections: 'Korekcijos',
};

const ACTIVITY_LABELS = {
  last_signup: 'Pask. registracija',
  last_project: 'Pask. projektas',
  last_usage_event: 'Pask. įvykis',
  last_invoice: 'Pask. sąskaita',
};

export default function HealthPanel({ health, loading, error }) {
  return (
    <section>
      <SectionHead
        eyebrow="Sistema"
        title="Būklė"
        hint="Lentelių dydžiai, įvykių apimtis, DB dydis ir paskutinis aktyvumas."
      />

      {error && <ErrorLine message={error} />}
      {loading && !health && !error && <BlockSkeleton height={220} />}

      {health && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* Table totals */}
          <Panel className="p-4">
            <div className="skyrius-header mb-3">Lentelių įrašai</div>
            <ul className="space-y-1.5">
              {Object.entries(health.totals || {}).map(([k, v]) => (
                <li key={k} className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">{TOTAL_LABELS[k] || k}</span>
                  <span className="font-mono tabular-nums text-foreground">{fmtInt(v)}</span>
                </li>
              ))}
              {Object.keys(health.totals || {}).length === 0 && (
                <EmptyLine>Nėra duomenų.</EmptyLine>
              )}
            </ul>
            <div className="mt-4 pt-3 border-t border-border flex items-center justify-between">
              <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <Database className="w-3.5 h-3.5" /> DB dydis
              </span>
              <span className="font-mono tabular-nums text-sm text-foreground">
                {fmtBytes(health.db_size_bytes)}
              </span>
            </div>
          </Panel>

          {/* Event kinds (30d) */}
          <Panel className="p-4">
            <div className="skyrius-header mb-3">Įvykiai pagal tipą (30 d.)</div>
            {(health.events_by_kind || []).length === 0 ? (
              <EmptyLine>Įvykių nėra.</EmptyLine>
            ) : (
              <EventKindBars events={health.events_by_kind} />
            )}
          </Panel>

          {/* Recent activity + error-log note */}
          <div className="space-y-4">
            <Panel className="p-4">
              <div className="flex items-center gap-1.5 skyrius-header mb-3">
                <Activity className="w-3.5 h-3.5" /> Paskutinis aktyvumas
              </div>
              <ul className="space-y-2">
                {Object.entries(ACTIVITY_LABELS).map(([k, label]) => {
                  const ts = health.recent_activity?.[k];
                  return (
                    <li key={k} className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">{label}</span>
                      <span className="text-xs text-foreground tabular-nums" title={ts ? fmtDateTime(ts) : ''}>
                        {fmtRelative(ts)}
                      </span>
                    </li>
                  );
                })}
              </ul>
            </Panel>

            <Panel className="p-4">
              <div className="skyrius-header mb-2">Klaidų žurnalas</div>
              {(health.error_log_tail || []).length > 0 ? (
                <pre className="text-[11px] font-mono text-muted-foreground whitespace-pre-wrap max-h-40 overflow-auto">
                  {health.error_log_tail.join('\n')}
                </pre>
              ) : (
                <div className="flex items-start gap-2 text-xs text-muted-foreground">
                  <Info className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                  <span>{health.note || 'Nėra išsaugoto klaidų žurnalo.'}</span>
                </div>
              )}
            </Panel>
          </div>
        </div>
      )}
    </section>
  );
}

function EventKindBars({ events }) {
  const max = Math.max(...events.map((e) => e.count), 1);
  return (
    <ul className="space-y-2.5">
      {events.map((e) => (
        <li key={e.kind}>
          <div className="flex items-center justify-between text-xs mb-1">
            <span className="font-mono text-foreground truncate max-w-[160px]" title={e.kind}>
              {e.kind}
            </span>
            <span className="font-mono tabular-nums text-muted-foreground">{fmtInt(e.count)}</span>
          </div>
          <div className="h-1.5 w-full rounded-full bg-secondary overflow-hidden">
            <div
              className="h-full rounded-full bg-primary/70"
              style={{ width: `${Math.max((e.count / max) * 100, 3)}%` }}
            />
          </div>
        </li>
      ))}
    </ul>
  );
}
