/**
 * useBilling — THE frontend flag gate for all billing UI (Phase 7).
 *
 * Fetches /api/billing/v2/status + /usage once (per mount, cached via
 * react-query) and returns { enabled, plans, currency, vatMode, usage, refresh }.
 *
 * INVARIANT: when the backend reports `enabled:false` (the default), every
 * consumer must render NOTHING billing-related. The app must look exactly as
 * it did before billing existed. Never assume enabled — treat any error or
 * missing field as disabled (fail closed).
 */

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { API_BASE } from '@/lib/apiBase';

async function fetchJson(path) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'GET',
    credentials: 'include',
    headers: { Accept: 'application/json' },
  });
  if (!res.ok) {
    // Fail closed: an unreachable/erroring billing endpoint disables the UI.
    const err = new Error(`HTTP ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

export function useBilling() {
  const queryClient = useQueryClient();

  const statusQuery = useQuery({
    queryKey: ['billing', 'status'],
    queryFn: () => fetchJson('/api/billing/v2/status'),
    staleTime: 5 * 60 * 1000,
    // Missing backend / network error ⇒ treat as disabled, no console noise.
    retry: false,
  });

  const enabled = statusQuery.data?.enabled === true;

  const usageQuery = useQuery({
    queryKey: ['billing', 'usage'],
    queryFn: () => fetchJson('/api/billing/v2/usage'),
    // Only fetch usage once we know billing is on — otherwise it's noise.
    enabled,
    staleTime: 60 * 1000,
    retry: false,
  });

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['billing'] });
  };

  const usageData = usageQuery.data;
  const usage = usageData?.enabled === false ? null : (usageData || null);

  return {
    enabled,
    plans: enabled ? (statusQuery.data?.plans || []) : [],
    currency: statusQuery.data?.currency || 'EUR',
    vatMode: statusQuery.data?.vat_mode || 'be_pvm',
    usage,
    isLoading: statusQuery.isLoading,
    refresh,
  };
}
