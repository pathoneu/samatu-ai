/**
 * UsersTable — paginated + debounced-search user management. Each row exposes
 * an Išjungti / Aktyvuoti action wired to POST /users/{id}/disable|enable.
 *
 * Disable is destructive-ish → confirmed via an AlertDialog. Admin rows show
 * an "admin" badge and no disable button (the backend also 400s self/other-
 * admin disable — we surface that error inline if it slips through).
 *
 * Row shape (admin_list_users_paginated): id, email, name, company_name,
 * company_code, plan, plan_status, is_admin, is_active, created_at,
 * last_login_at, project_count, total_spend_eur, deleted_at.
 *
 * A deleted account (deleted_at set) is a tombstone kept for its invoices: it
 * reads „Ištrinta paskyra" with the deletion date instead of its placeholder
 * email, and has no action — the backend refuses to switch it either way.
 */
import React from 'react';
import { useTranslation } from '@/i18n/react';
import { Search, ShieldAlert, UserX, UserCheck, Loader2, ChevronLeft, ChevronRight, Trash2 } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { SectionHead, Panel, PlanPill, StatusPill, EmptyLine, ErrorLine } from './adminPrimitives';
import { fetchAdmin, postAdmin, fmtEur, fmtInt, fmtDate } from './adminUtils';
import { isDeletedAccount } from '@/lib/adminStatus';

const LIMIT = 25;

export default function UsersTable() {
  const { t } = useTranslation();
  const [search, setSearch] = React.useState('');
  const [debounced, setDebounced] = React.useState('');
  const [page, setPage] = React.useState(1);
  const [data, setData] = React.useState(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState(null);

  // Row-level action state: which user is mid-toggle + a per-page action error.
  const [busyId, setBusyId] = React.useState(null);
  const [actionError, setActionError] = React.useState(null);

  // Confirm dialog target (a user row) — non-null opens the dialog.
  const [confirmUser, setConfirmUser] = React.useState(null);

  // Debounce the search box → refetch.
  React.useEffect(() => {
    const timer = setTimeout(() => {
      setDebounced(search.trim());
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  const load = React.useCallback(() => {
    setLoading(true);
    setError(null);
    const q = new URLSearchParams({
      search: debounced,
      page: String(page),
      limit: String(LIMIT),
    });
    fetchAdmin(`/api/admin/v2/users?${q.toString()}`)
      .then((res) => setData(res))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [debounced, page]);

  React.useEffect(() => {
    load();
  }, [load]);

  async function toggleActive(user) {
    setBusyId(user.id);
    setActionError(null);
    const path = user.is_active
      ? `/api/admin/v2/users/${user.id}/disable`
      : `/api/admin/v2/users/${user.id}/enable`;
    try {
      await postAdmin(path);
      load(); // refetch — authoritative state, avoids optimistic drift
    } catch (e) {
      setActionError(e.message);
    } finally {
      setBusyId(null);
      setConfirmUser(null);
    }
  }

  const rows = data?.rows || [];
  const total = data?.total || 0;
  const totalPages = Math.max(1, Math.ceil(total / LIMIT));
  const from = total === 0 ? 0 : (page - 1) * LIMIT + 1;
  const to = Math.min(page * LIMIT, total);

  return (
    <section>
      <SectionHead
        eyebrow={t('admin.users.eyebrow')}
        title={t('admin.users.title')}
        hint={t('admin.users.hint')}
        right={
          <div className="relative w-64 max-w-[60vw]">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground pointer-events-none" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={t('admin.users.search')}
              className="pl-8 h-9 bg-secondary/50 border-border"
            />
          </div>
        }
      />

      {actionError && (
        <div className="mb-3">
          <ErrorLine message={actionError} />
        </div>
      )}

      <Panel>
        {error ? (
          <div className="p-4">
            <ErrorLine message={error} />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left border-b border-border bg-secondary/30">
                  <Th>{t('admin.users.colEmail')}</Th>
                  <Th>{t('admin.users.colCompany')}</Th>
                  <Th>{t('admin.users.colPlan')}</Th>
                  <Th>{t('admin.users.colStatus')}</Th>
                  <Th align="right">{t('admin.users.colProjects')}</Th>
                  <Th align="right">{t('admin.users.colSpend')}</Th>
                  <Th>{t('admin.users.colRegistered')}</Th>
                  <Th>{t('admin.users.colLastLogin')}</Th>
                  <Th align="right">{t('admin.users.colAction')}</Th>
                </tr>
              </thead>
              <tbody>
                {loading && rows.length === 0 &&
                  Array.from({ length: 6 }).map((_, i) => (
                    <tr key={i} className="border-b border-border/50 last:border-0">
                      <td colSpan={9} className="px-4 py-3">
                        <div className="h-4 w-full bg-muted/40 rounded animate-pulse" />
                      </td>
                    </tr>
                  ))}

                {!loading && rows.length === 0 && (
                  <tr>
                    <td colSpan={9}>
                      <EmptyLine>
                        {debounced
                          ? t('admin.users.notFound', { search: debounced })
                          : t('admin.users.none')}
                      </EmptyLine>
                    </td>
                  </tr>
                )}

                {rows.map((u) => (
                  <tr
                    key={u.id}
                    className={`border-b border-border/50 last:border-0 hover:bg-muted/20 transition-colors ${
                      !u.is_active ? 'opacity-60' : ''
                    }`}
                  >
                    <td className="px-4 py-2.5">
                      {isDeletedAccount(u) ? (
                        <div title={`${t('admin.users.deletedHint')} (${u.email})`}>
                          <div className="flex items-center gap-1.5 text-foreground">
                            <Trash2 className="w-3.5 h-3.5 text-muted-foreground" />
                            {t('admin.users.deletedAccount')}
                          </div>
                          <div className="text-[11px] text-muted-foreground tabular-nums">
                            {t('admin.users.deletedOn', { date: fmtDate(u.deleted_at) })}
                          </div>
                        </div>
                      ) : (
                        <>
                          <div className="flex items-center gap-2">
                            <span className="text-foreground truncate max-w-[220px]" title={u.email}>
                              {u.email}
                            </span>
                            {u.is_admin ? (
                              <span className="inline-flex items-center gap-1 rounded border border-primary/30 bg-primary/12 px-1.5 py-0.5 text-[10px] font-semibold text-primary uppercase tracking-wide">
                                <ShieldAlert className="w-3 h-3" /> admin
                              </span>
                            ) : null}
                          </div>
                          {u.name && (
                            <div className="text-[11px] text-muted-foreground truncate max-w-[220px]">{u.name}</div>
                          )}
                        </>
                      )}
                    </td>
                    <td className="px-4 py-2.5 text-muted-foreground truncate max-w-[160px]" title={u.company_name || ''}>
                      {u.company_name || '—'}
                    </td>
                    <td className="px-4 py-2.5">
                      <PlanPill plan={u.plan} />
                    </td>
                    <td className="px-4 py-2.5">
                      {isDeletedAccount(u) ? (
                        <span className="inline-flex items-center gap-1 rounded-md border border-border bg-muted px-2 py-0.5 text-[11px] font-medium text-muted-foreground">
                          <span className="w-1.5 h-1.5 rounded-full bg-muted-foreground/60" />
                          {t('admin.status.deleted')}
                        </span>
                      ) : (
                        <StatusPill active={!!u.is_active} />
                      )}
                    </td>
                    <td className="px-4 py-2.5 text-right tabular-nums font-mono text-foreground">
                      {fmtInt(u.project_count)}
                    </td>
                    <td className="px-4 py-2.5 text-right tabular-nums font-mono text-foreground">
                      {fmtEur(u.total_spend_eur)}
                    </td>
                    <td className="px-4 py-2.5 text-xs text-muted-foreground tabular-nums">
                      {fmtDate(u.created_at)}
                    </td>
                    <td className="px-4 py-2.5 text-xs text-muted-foreground tabular-nums">
                      {u.last_login_at ? fmtDate(u.last_login_at) : t('admin.users.never')}
                    </td>
                    <td className="px-4 py-2.5 text-right">
                      {u.is_admin || isDeletedAccount(u) ? (
                        <span className="text-[11px] text-muted-foreground/60">—</span>
                      ) : u.is_active ? (
                        <Button
                          variant="outline"
                          size="sm"
                          className="h-7 px-2 text-xs border-red-500/30 text-red-400 hover:bg-red-500/10 hover:text-red-300"
                          disabled={busyId === u.id}
                          onClick={() => setConfirmUser(u)}
                        >
                          {busyId === u.id ? (
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          ) : (
                            <UserX className="w-3.5 h-3.5" />
                          )}
                          {t('admin.users.disable')}
                        </Button>
                      ) : (
                        <Button
                          variant="outline"
                          size="sm"
                          className="h-7 px-2 text-xs border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/10 hover:text-emerald-300"
                          disabled={busyId === u.id}
                          onClick={() => toggleActive(u)}
                        >
                          {busyId === u.id ? (
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          ) : (
                            <UserCheck className="w-3.5 h-3.5" />
                          )}
                          {t('admin.users.enable')}
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination footer */}
        {!error && total > 0 && (
          <div className="flex items-center justify-between gap-3 px-4 py-2.5 border-t border-border bg-secondary/20">
            <span className="text-xs text-muted-foreground tabular-nums">
              {fmtInt(from)}–{fmtInt(to)} {t('admin.users.pageOf')} {fmtInt(total)}
            </span>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                className="h-7 px-2"
                disabled={page <= 1 || loading}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                <ChevronLeft className="w-4 h-4" />
              </Button>
              <span className="text-xs text-muted-foreground tabular-nums">
                {page} / {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                className="h-7 px-2"
                disabled={page >= totalPages || loading}
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              >
                <ChevronRight className="w-4 h-4" />
              </Button>
            </div>
          </div>
        )}
      </Panel>

      {/* Disable confirmation */}
      <AlertDialog open={!!confirmUser} onOpenChange={(open) => !open && setConfirmUser(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('admin.users.confirmTitle')}</AlertDialogTitle>
            <AlertDialogDescription>
              {t('admin.users.confirmDescA')}
              <span className="font-mono text-foreground">{confirmUser?.email}</span>
              {t('admin.users.confirmDescB')}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t('admin.users.cancel')}</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={(e) => {
                e.preventDefault(); // keep dialog until the request settles
                if (confirmUser) toggleActive(confirmUser);
              }}
            >
              {busyId === confirmUser?.id ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                t('admin.users.disable')
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  );
}

function Th({ children, align }) {
  return (
    <th
      className={`px-4 py-2.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground ${
        align === 'right' ? 'text-right' : 'text-left'
      }`}
    >
      {children}
    </th>
  );
}
