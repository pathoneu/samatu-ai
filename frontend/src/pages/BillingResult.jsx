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
  const { enabled, refresh } = useBilling();
  const fired = useRef(false);

  useEffect(() => {
    if (fired.current) return;
    fired.current = true;
    if (variant === 'success') {
      toast.success('Apmokėjimas sėkmingas — planas aktyvuotas.');
      // Re-pull status/usage so the meter + settings reflect the new plan.
      refresh();
    } else {
      toast.info('Apmokėjimas atšauktas. Planas nepakeistas.');
    }
  }, [variant, refresh]);

  // If billing is somehow off, still just land on the dashboard.
  void enabled;
  return <Navigate to="/dashboard" replace />;
}
