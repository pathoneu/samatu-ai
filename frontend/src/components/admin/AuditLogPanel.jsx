/**
 * AuditLogPanel — read-only trail of state-changing admin actions from
 * /api/admin/v2/audit-log: [{ id, actor_user_id, actor_email, action,
 * target_user_id, target_email, detail, created_at }], newest first.
 *
 * Accountability surface for the 2026-07-06 audit finding: disable/enable (and
 * any future admin mutation) now records WHO did WHAT to WHOM and WHEN. Purely
 * read-only — the log is written server-side; this panel only displays it and
 * self-refreshes (like UsersTable, it owns its fetch rather than taking props).
 */
import React from 'react';
import { useTranslation } from '@/i18n/react';
import { RefreshCw } from 'lucide-react';
import { SectionHead, Panel, EmptyLine, ErrorLine } from './adminPrimitives';
import { fetchAdmin, fmtDateTime } from './adminUtils';

export default function AuditLogPanel() {
  const { t } = useTranslation();
  const [rows, setRows] = React.useState(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState(null);

  const load = React.useCallback(() => {
    setLoading(true);
    setError(null);
    return fetchAdmin('/api/admin/v2/audit-log?limit=100')
      .then((res) => setRows(Array.isArray(res?.rows) ? res.rows : []))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  React.useEffect(() => {
    load();
  }, [load]);

  return (
    <section>
      <SectionHead
        eyebrow={t('admin.audit.eyebrow')}
        title={t('admin.audit.title')}
        hint={t('admin.audit.hint')}
        right={
          <button
            onClick={load}
            disabled={loading}
            className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors disabled:opacity-50"
            title={t('admin.audit.refresh')}
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          </button>
        }
      />

      {error && <ErrorLine message={error} />}

      {!error && (
        <Panel>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left border-b border-border bg-secondary/30">
                  <Th>{t('admin.audit.colTime')}</Th>
                  <Th>{t('admin.audit.colActor')}</Th>
                  <Th>{t('admin.audit.colAction')}</Th>
                  <Th>{t('admin.audit.colTarget')}</Th>
                  <Th>{t('admin.audit.colDetail')}</Th>
                </tr>
              </thead>
              <tbody>
                {loading && !rows &&
                  Array.from({ length: 5 }).map((_, i) => (
                    <tr key={i} className="border-b border-border/50 last:border-0">
                      <td colSpan={5} className="px-4 py-3">
                        <div className="h-4 w-full bg-muted/40 rounded animate-pulse" />
                      </td>
                    </tr>
                  ))}

                {!loading && rows && rows.length === 0 && (
                  <tr>
                    <td colSpan={5}>
                      <EmptyLine>{t('admin.audit.none')}</EmptyLine>
                    </td>
                  </tr>
                )}

                {rows &&
                  rows.map((r) => (
                    <tr
                      key={r.id}
                      className="border-b border-border/50 last:border-0 hover:bg-muted/20 transition-colors"
                    >
                      <td className="px-4 py-2.5 text-xs text-muted-foreground tabular-nums whitespace-nowrap">
                        {fmtDateTime(r.created_at)}
                      </td>
                      <td
                        className="px-4 py-2.5 text-foreground truncate max-w-[200px]"
                        title={r.actor_email || r.actor_user_id || ''}
                      >
                        {r.actor_email || r.actor_user_id || '—'}
                      </td>
                      <td className="px-4 py-2.5">
                        <ActionPill action={r.action} label={actionLabel(t, r.action)} />
                      </td>
                      <td
                        className="px-4 py-2.5 text-muted-foreground truncate max-w-[200px]"
                        title={r.target_email || r.target_user_id || ''}
                      >
                        {r.target_email || r.target_user_id || '—'}
                      </td>
                      <td
                        className="px-4 py-2.5 text-xs text-muted-foreground truncate max-w-[220px]"
                        title={r.detail || ''}
                      >
                        {r.detail || '—'}
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </Panel>
      )}
    </section>
  );
}

/** Human label for a dotted action verb; unknown actions render verbatim. */
function actionLabel(t, action) {
  const map = {
    'user.disable': t('admin.audit.actions.disable'),
    'user.enable': t('admin.audit.actions.enable'),
  };
  return map[action] || action;
}

/** Small colour-coded pill: disable = red, enable = green, other = muted. */
function ActionPill({ action, label }) {
  const cls =
    action === 'user.enable'
      ? 'border-emerald-500/30 bg-emerald-500/12 text-emerald-400'
      : action === 'user.disable'
        ? 'border-red-500/30 bg-red-500/12 text-red-400'
        : 'border-border bg-muted text-muted-foreground';
  return (
    <span className={`inline-flex items-center rounded-md border px-2 py-0.5 text-[11px] font-medium ${cls}`}>
      {label}
    </span>
  );
}

function Th({ children }) {
  return (
    <th className="px-4 py-2.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground text-left">
      {children}
    </th>
  );
}
