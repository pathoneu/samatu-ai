/**
 * BillingResult — /billing/success and /billing/cancel landing routes
 * (Phase 7, Task 16). Stripe Checkout redirects the browser back here. We
 * show a shadcn/sonner toast and bounce to the dashboard so the user lands
 * back in the app with feedback, not a dead page.
 *
 * `variant` is 'success' | 'cancel'.
 */

import React, { useEffect, useRef } from 'react';
import { Navigate } from 'react-router-dom';
import { toast } from 'sonner';
import { useBilling } from '@/hooks/useBilling';

export default function BillingResult({ variant }) {
  const { enabled, isLoading, refresh } = useBilling();
  const fired = useRef(false);

  useEffect(() => {
    if (isLoading || fired.current) return;
    fired.current = true;
    // Billing OFF (the beta default): nobody paid — this route is only
    // reachable via a stray/bookmarked/shared URL. Redirect silently. Firing
    // "Apmokėjimas sėkmingas" here told any visitor their payment succeeded
    // (2026-07-27 pre-prod fix; the flag used to be read and discarded).
    if (!enabled) return;
    if (variant === 'success') {
      toast.success('Apmokėjimas sėkmingas — planas aktyvuotas.');
      // Re-pull status/usage so the meter + settings reflect the new plan.
      refresh();
    } else {
      toast.info('Apmokėjimas atšauktas. Planas nepakeistas.');
    }
  }, [variant, refresh, enabled, isLoading]);

  // Hold the redirect until the flag is known — navigating on the first render
  // would unmount this component before the effect can decide, and the toast
  // would never fire on the billing-enabled path.
  if (isLoading) return null;
  return <Navigate to="/dashboard" replace />;
}
