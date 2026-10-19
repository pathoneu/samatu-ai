/**
 * AdminDashboard — Pathon operational cockpit (v2, dark graphite).
 *
 * A scan-then-operate ops screen backed by /api/admin/v2/*:
 *   1. Header + range selector (7/30/90 d.) — refetches analytics + cost-monitor.
 *   2. KPI row (KpiRow)              — headline totals + delta vs prior window.
 *   3. Cost monitor (CostMonitor)    — the "don't go bankrupt" screen.
 *   4. Analytics (AnalyticsCharts)   — signups / projects / extractions per day.
 *   5. User management (UsersTable)  — paginated, searchable, disable/enable.
 *   6. System health (HealthPanel)   — table totals, events, DB size, activity.
 *   7. Export                        — credentialed CSV downloads (users, cost).
 *
 * Auth: the /admin route is already gated by <AdminRoute> in App.jsx; this
 * component keeps its own guard as defence-in-depth. Fetches use cookie auth
 * (credentials:'include') and each endpoint 401/403s for anon/non-admin.
 */
import React from 'react';
import { Navigate } from 'react-router';
import { useTranslation } from '@/i18n/react';
import { Download, RefreshCw } from 'lucide-react';
import { useAuth } from '@/lib/authContext';
import { Button } from '@/components/ui/button';

import KpiRow from '@/components/admin/KpiRow';
import CostMonitor from '@/components/admin/CostMonitor';
import AnalyticsCharts from '@/components/admin/AnalyticsCharts';
import UsersTable from '@/components/admin/UsersTable';
import AuditLogPanel from '@/components/admin/AuditLogPanel';
import HealthPanel from '@/components/admin/HealthPanel';
import { fetchAdmin, downloadCsv } from '@/components/admin/adminUtils';

const RANGES = [7, 30, 90];

export default function AdminDashboard() {
  const { t } = useTranslation();
  const { user, isAdmin, isLoading } = useAuth();
  const [days, setDays] = React.useState(30);

  // Window-scoped data (refetches on range change).
  const [analytics, setAnalytics] = React.useState(null);
  const [cost, setCost] = React.useState(null);
  const [windowLoading, setWindowLoading] = React.useState(true);
  const [analyticsError, setAnalyticsError] = React.useState(null);
  const [costError, setCostError] = React.useState(null);

  // Health is window-independent (30d baked into the endpoint).
  const [health, setHealth] = React.useState(null);
  const [healthLoading, setHealthLoading] = React.useState(true);
  const [healthError, setHealthError] = React.useState(null);

  const [refreshing, setRefreshing] = React.useState(false);

  const loadWindow = React.useCallback(() => {
    setWindowLoading(true);
    setAnalyticsError(null);
    setCostError(null);
    // Fetch independently so one endpoint failing doesn't blank the other.
    const a = fetchAdmin(`/api/admin/v2/analytics?days=${days}`)
      .then((res) => setAnalytics(res))
      .catch((e) => setAnalyticsError(e.message));
    const c = fetchAdmin(`/api/admin/v2/cost-monitor?days=${days}`)
      .then((res) => setCost(res))
      .catch((e) => setCostError(e.message));
    return Promise.allSettled([a, c]).finally(() => setWindowLoading(false));
  }, [days]);

  const loadHealth = React.useCallback(() => {
    setHealthLoading(true);
    setHealthError(null);
    return fetchAdmin('/api/admin/v2/system-health')
      .then((res) => setHealth(res))
      .catch((e) => setHealthError(e.message))
      .finally(() => setHealthLoading(false));
  }, []);

  React.useEffect(() => {
    if (!isAdmin) return;
    loadWindow();
  }, [isAdmin, loadWindow]);

  React.useEffect(() => {
    if (!isAdmin) return;
    loadHealth();
  }, [isAdmin, loadHealth]);

  async function refreshAll() {
    setRefreshing(true);
    await Promise.allSettled([loadWindow(), loadHealth()]);
    setRefreshing(false);
  }

  if (isLoading) return <div className="p-8 text-muted-foreground">{t('admin.loading')}</div>;
  if (!user) return <Navigate to="/login" replace />;
  if (!isAdmin) return <Navigate to="/dashboard" replace />;

  return (
    <div className="min-h-screen bg-background">
      <div className="max-w-7xl mx-auto px-6 py-6 space-y-8">
        {/* ── Header + controls ── */}
        <header className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4">
          <div>
            <div className="mono-tick mb-1">{t('admin.dash.eyebrow')}</div>
            <h1
              className="text-foreground"
              style={{ fontFamily: 'var(--font-display)', fontSize: 26, fontWeight: 700, letterSpacing: '-0.02em' }}
            >
              {t('admin.dash.title')}
            </h1>
            <p className="text-sm text-muted-foreground mt-0.5">
              {t('admin.dash.subtitle')}
            </p>
          </div>

          <div className="flex items-center gap-2">
            {/* Range selector */}
            <div className="inline-flex items-center rounded-lg border border-border bg-card p-0.5">
              {RANGES.map((r) => (
                <button
                  key={r}
                  onClick={() => setDays(r)}
                  className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors tabular-nums ${
                    days === r
                      ? 'bg-primary text-primary-foreground'
                      : 'text-muted-foreground hover:text-foreground'
                  }`}
                >
                  {t('admin.dash.rangeDays', { count: r })}
                </button>
              ))}
            </div>
            <Button
              variant="outline"
              size="sm"
              className="h-9"
              onClick={refreshAll}
              disabled={refreshing}
              title={t('admin.dash.refresh')}
            >
              <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
            </Button>
          </div>
        </header>

        {/* ── 2. KPI row ── */}
        <KpiRow analytics={analytics} cost={cost} loading={windowLoading} />

        {/* ── 3. Cost monitor (prominent) ── */}
        <CostMonitor
          cost={cost}
          analytics={analytics}
          loading={windowLoading}
          error={costError}
          days={days}
        />

        {/* ── 4. Analytics ── */}
        <AnalyticsCharts
          analytics={analytics}
          loading={windowLoading}
          error={analyticsError}
          days={days}
        />

        {/* ── 5. User management ── */}
        <UsersTable />

        {/* ── 5b. Admin audit log (read-only accountability trail) ── */}
        <AuditLogPanel />

        {/* ── 6. System health ── */}
        <HealthPanel health={health} loading={healthLoading} error={healthError} />

        {/* ── 7. Export ── */}
        <section>
          <div className="skyrius-header mb-3">{t('admin.dash.exportHead')}</div>
          <div className="flex flex-wrap gap-3">
            <Button
              variant="outline"
              onClick={() => downloadCsv('/api/admin/v2/export/users.csv', 'pathon-users.csv')}
            >
              <Download className="w-4 h-4" />
              {t('admin.dash.exportUsers')}
            </Button>
            <Button
              variant="outline"
              onClick={() =>
                downloadCsv(`/api/admin/v2/export/cost.csv?days=${days}`, 'pathon-cost.csv')
              }
            >
              <Download className="w-4 h-4" />
              {t('admin.dash.exportCost')}
            </Button>
          </div>
        </section>
      </div>
    </div>
  );
}
