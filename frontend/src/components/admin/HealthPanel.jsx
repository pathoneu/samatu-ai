/**
 * HealthPanel — system-health snapshot from /api/admin/v2/system-health:
 *   { totals, events_by_kind[], db_size_bytes, recent_activity, storage_backend,
 *     backup, error_log_tail[], note }
 *
 * Renders the nightly DB backup (red when the last good snapshot is missing or
 * older than 26 h, when the latest attempt failed, or when the backup is off —
 * lib/adminStatus.js), table totals, event-kind volume (30d), DB size,
 * recent-activity timestamps, and the error-log `note` gracefully (there is no
 * persisted log — error_log_tail is always []; we show the note instead).
 */
import React from 'react';
import { useTranslation } from 'react-i18next';
import { Database, DatabaseBackup, Info, Activity } from 'lucide-react';
import { SectionHead, Panel, EmptyLine, ErrorLine, BlockSkeleton } from './adminPrimitives';
import { fmtInt, fmtBytes, fmtRelative, fmtDateTime } from './adminUtils';
import { backupStatus } from '@/lib/adminStatus';

// Keys of the recent-activity block, in display order. Labels resolve via i18n.
const ACTIVITY_KEYS = ['last_signup', 'last_project', 'last_usage_event', 'last_invoice'];

export default function HealthPanel({ health, loading, error }) {
  const { t } = useTranslation();
  return (
    <section>
      <SectionHead
        eyebrow={t('admin.health.eyebrow')}
        title={t('admin.health.title')}
        hint={t('admin.health.hint')}
      />

      {error && <ErrorLine message={error} />}
      {loading && !health && !error && <BlockSkeleton height={220} />}

      {health && <BackupPanel backup={health.backup} storageBackend={health.storage_backend} />}

      {health && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* Table totals */}
          <Panel className="p-4">
            <div className="skyrius-header mb-3">{t('admin.health.tableRecords')}</div>
            <ul className="space-y-1.5">
              {Object.entries(health.totals || {}).map(([k, v]) => (
                <li key={k} className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">{t(`admin.health.totals.${k}`, { defaultValue: k })}</span>
                  <span className="font-mono tabular-nums text-foreground">{fmtInt(v)}</span>
                </li>
              ))}
              {Object.keys(health.totals || {}).length === 0 && (
                <EmptyLine>{t('admin.health.noData')}</EmptyLine>
              )}
            </ul>
            <div className="mt-4 pt-3 border-t border-border flex items-center justify-between">
              <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <Database className="w-3.5 h-3.5" /> {t('admin.health.dbSize')}
              </span>
              <span className="font-mono tabular-nums text-sm text-foreground">
                {fmtBytes(health.db_size_bytes)}
              </span>
            </div>
          </Panel>

          {/* Event kinds (30d) */}
          <Panel className="p-4">
            <div className="skyrius-header mb-3">{t('admin.health.eventsByKind')}</div>
            {(health.events_by_kind || []).length === 0 ? (
              <EmptyLine>{t('admin.health.noEvents')}</EmptyLine>
            ) : (
              <EventKindBars events={health.events_by_kind} />
            )}
          </Panel>

          {/* Recent activity + error-log note */}
          <div className="space-y-4">
            <Panel className="p-4">
              <div className="flex items-center gap-1.5 skyrius-header mb-3">
                <Activity className="w-3.5 h-3.5" /> {t('admin.health.recentActivity')}
              </div>
              <ul className="space-y-2">
                {ACTIVITY_KEYS.map((k) => {
                  const ts = health.recent_activity?.[k];
                  return (
                    <li key={k} className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">{t(`admin.health.activity.${k}`)}</span>
                      <span className="text-xs text-foreground tabular-nums" title={ts ? fmtDateTime(ts) : ''}>
                        {fmtRelative(ts)}
                      </span>
                    </li>
                  );
                })}
              </ul>
            </Panel>

            <Panel className="p-4">
              <div className="skyrius-header mb-2">{t('admin.health.errorLog')}</div>
              {(health.error_log_tail || []).length > 0 ? (
                <pre className="text-[11px] font-mono text-muted-foreground whitespace-pre-wrap max-h-40 overflow-auto">
                  {health.error_log_tail.join('\n')}
                </pre>
              ) : (
                <div className="flex items-start gap-2 text-xs text-muted-foreground">
                  <Info className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                  <span>{health.note || t('admin.health.noErrorLog')}</span>
                </div>
              )}
            </Panel>
          </div>
        </div>
      )}
    </section>
  );
}

/**
 * The nightly DB backup at a glance: a red border and „Reikia dėmesio" whenever
 * backupStatus() says so, the reason in one plain sentence, then the last good
 * snapshot, the latest error, where files are stored and the retention setting.
 */
function BackupPanel({ backup, storageBackend }) {
  const { t } = useTranslation();
  const b = backup || {};
  const status = backupStatus(b);
  const bad = status.tone === 'bad';
  const prune = b.last_prune && typeof b.last_prune === 'object' ? b.last_prune : null;

  const storageLabel = storageBackend === 'r2'
    ? t('admin.health.backup.storageR2')
    : storageBackend === 'local'
      ? t('admin.health.backup.storageLocal')
      : storageBackend || '—';

  let retention = t('admin.health.backup.retentionOff');
  if (b.keep_days) {
    retention = t('admin.health.backup.retentionOn', { days: b.keep_days, newest: b.keep_newest ?? 7 });
    if (prune && !prune.error) retention += ` · ${t('admin.health.backup.lastPrune', { n: prune.deleted ?? 0 })}`;
  }

  return (
    <Panel className={`p-4 mb-4 ${bad ? 'border-destructive/50' : ''}`}>
      <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
        <div className="flex items-center gap-1.5 skyrius-header">
          <DatabaseBackup className="w-3.5 h-3.5" /> {t('admin.health.backup.title')}
        </div>
        <span
          className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[11px] font-medium ${
            bad
              ? 'border-destructive/30 bg-destructive/10 text-destructive'
              : 'border-[hsl(var(--accent-2)/0.35)] bg-[hsl(var(--accent-2)/0.08)] text-[hsl(var(--accent-2))]'
          }`}
        >
          <span className={`w-1.5 h-1.5 rounded-full ${bad ? 'bg-destructive' : 'bg-[hsl(var(--accent-2))]'}`} />
          {bad ? t('admin.health.backup.statusBad') : t('admin.health.backup.statusOk')}
        </span>
      </div>

      <p className={`text-sm ${bad ? 'text-destructive font-medium' : 'text-foreground'}`}>
        {t(`admin.health.backup.reason.${status.reason}`, { hours: status.staleAfterHours })}
      </p>

      <dl className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-1.5 text-sm">
        <BackupRow label={t('admin.health.backup.lastGood')}>
          {b.last_ok_at ? `${fmtRelative(b.last_ok_at)} · ${fmtDateTime(b.last_ok_at)}` : t('admin.health.backup.none')}
        </BackupRow>
        <BackupRow label={t('admin.health.backup.size')}>
          {b.last_size != null ? fmtBytes(b.last_size) : '—'}
        </BackupRow>
        <BackupRow label={t('admin.health.backup.file')} mono>
          {b.last_key || '—'}
        </BackupRow>
        <BackupRow label={t('admin.health.backup.storage')}>{storageLabel}</BackupRow>
        <BackupRow label={t('admin.health.backup.retention')}>{retention}</BackupRow>
      </dl>

      {status.error && (
        <div className="mt-3 text-xs text-destructive break-words">
          <span className="font-semibold">{t('admin.health.backup.error')}</span>
          {b.last_attempt?.at ? ` (${fmtDateTime(b.last_attempt.at)})` : ''}: {status.error}
        </div>
      )}
      {prune?.error && (
        <div className="mt-2 text-xs text-destructive break-words">
          {t('admin.health.backup.pruneFailed', { error: prune.error })}
        </div>
      )}
    </Panel>
  );
}

function BackupRow({ label, mono, children }) {
  return (
    <div className="flex items-baseline justify-between gap-3 min-w-0">
      <dt className="text-muted-foreground shrink-0">{label}</dt>
      <dd
        className={`text-right text-foreground min-w-0 ${mono ? 'font-mono text-xs truncate' : 'tabular-nums break-words'}`}
        title={typeof children === 'string' ? children : undefined}
      >
        {children}
      </dd>
    </div>
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
