/**
 * BillingSettings — "Atsiskaitymas" section for the Settings page (Phase 7, Task 18).
 *
 * Renders ONLY when billing is enabled (returns null otherwise → flag-off
 * invariant holds). Shows:
 *   - current plan + status + period end (from useBilling().usage)
 *   - įmonės kodas + PVM kodas fields (save via PUT /api/auth/profile)
 *   - invoice list with per-row PDF download
 *   - "Tvarkyti prenumeratą" button — STUB (no live Stripe portal call yet;
 *     the /portal endpoint isn't wired here per Phase 7 scope).
 */

import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { CreditCard, Save, Download, ExternalLink } from 'lucide-react';
import { toast } from 'sonner';
import { useAuth } from '@/lib/authContext';
import { useBilling } from '@/hooks/useBilling';
import { getInvoices, invoiceDownloadUrl, saveCompanyCode } from '@/lib/billingApi';

const PLAN_LABEL_KEYS = {
  free: 'billing.plans.free',
  pro: 'billing.plans.pro',
  studio: 'billing.plans.studio',
  oneoff: 'billing.plans.oneoff',
};

const STATUS_LABEL_KEYS = {
  active: 'billing.status.active',
  trialing: 'billing.status.trialing',
  past_due: 'billing.status.past_due',
  canceled: 'billing.status.canceled',
  incomplete: 'billing.status.incomplete',
};

export default function BillingSettings() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const { enabled, usage } = useBilling();

  const [companyCode, setCompanyCode] = useState('');
  const [pvmCode, setPvmCode] = useState('');
  const [saving, setSaving] = useState(false);

  const [invoices, setInvoices] = useState([]);
  const [invLoading, setInvLoading] = useState(false);

  // Prefill from the user profile (backend echoes company_code / pvm_code).
  useEffect(() => {
    if (user) {
      setCompanyCode(user.company_code || '');
      setPvmCode(user.pvm_code || '');
    }
  }, [user]);

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    setInvLoading(true);
    getInvoices()
      .then((list) => { if (!cancelled) setInvoices(list); })
      .catch(() => { if (!cancelled) setInvoices([]); })
      .finally(() => { if (!cancelled) setInvLoading(false); });
    return () => { cancelled = true; };
  }, [enabled]);

  // Flag-off invariant: no section at all when billing is disabled.
  if (!enabled) return null;

  const planLabel = PLAN_LABEL_KEYS[usage?.plan] ? t(PLAN_LABEL_KEYS[usage.plan]) : (usage?.plan || '—');
  const statusLabel = usage?.plan_status
    ? (STATUS_LABEL_KEYS[usage.plan_status] ? t(STATUS_LABEL_KEYS[usage.plan_status]) : usage.plan_status)
    : null;
  const periodEnd = formatDate(usage?.current_period_end);

  const handleSaveCode = async () => {
    if (!companyCode.trim()) {
      toast.error(t('billing.settings.toastEnterCode'));
      return;
    }
    setSaving(true);
    try {
      await saveCompanyCode({
        company_code: companyCode.trim(),
        pvm_code: pvmCode.trim() || undefined,
      });
      toast.success(t('billing.settings.toastSaved'));
    } catch (e) {
      toast.error(e.message || t('billing.settings.toastSaveFail'));
    } finally {
      setSaving(false);
    }
  };

  const handleManage = () => {
    // STUB — Stripe Billing Portal not wired yet. Point users to plans for now.
    toast.info(t('billing.settings.toastManageSoon'));
  };

  return (
    <div className="bg-card border border-border rounded-xl p-6">
      <div className="flex items-center gap-3 mb-5">
        <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
          <CreditCard className="w-5 h-5 text-primary" />
        </div>
        <div>
          <h2 className="font-semibold text-foreground">{t('billing.settings.heading')}</h2>
          <p className="text-xs text-muted-foreground">{t('billing.settings.sub')}</p>
        </div>
      </div>

      {/* Current plan */}
      <div className="rounded-lg border border-border bg-background p-4 mb-5">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div>
            <div className="text-sm font-semibold text-foreground">{planLabel}</div>
            <div className="text-xs text-muted-foreground mt-0.5">
              {statusLabel && <span>{statusLabel}</span>}
              {statusLabel && periodEnd && <span> · </span>}
              {periodEnd && <span>{t('billing.settings.validUntil', { date: periodEnd })}</span>}
              {!statusLabel && !periodEnd && <span>{t('billing.settings.planNotSet')}</span>}
            </div>
          </div>
          <Button variant="outline" size="sm" onClick={handleManage}>
            <ExternalLink className="w-4 h-4 mr-2" />
            {t('billing.settings.managePlan')}
          </Button>
        </div>
      </div>

      {/* Company code — required before free trial */}
      <div className="space-y-4 mb-5">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <Label className="text-sm text-muted-foreground">{t('billing.settings.companyCode')}</Label>
            <Input
              value={companyCode}
              onChange={(e) => setCompanyCode(e.target.value)}
              placeholder="123456789"
              className="mt-1.5 bg-background border-border"
            />
          </div>
          <div>
            <Label className="text-sm text-muted-foreground">{t('billing.settings.pvmCode')}</Label>
            <Input
              value={pvmCode}
              onChange={(e) => setPvmCode(e.target.value)}
              placeholder="LT123456789"
              className="mt-1.5 bg-background border-border"
            />
          </div>
        </div>
        <p className="text-[11px] text-muted-foreground">
          {t('billing.settings.codeHint')}
        </p>
        <Button onClick={handleSaveCode} disabled={saving} variant="outline">
          <Save className="w-4 h-4 mr-2" />
          {saving ? t('billing.settings.saving') : t('billing.settings.saveData')}
        </Button>
      </div>

      {/* Invoices */}
      <div>
        <h3 className="text-sm font-semibold text-foreground mb-2">{t('billing.settings.invoices')}</h3>
        {invLoading ? (
          <p className="text-xs text-muted-foreground italic">{t('billing.settings.loading')}</p>
        ) : invoices.length === 0 ? (
          <p className="text-xs text-muted-foreground italic">{t('billing.settings.noInvoices')}</p>
        ) : (
          <div className="space-y-2">
            {invoices.map((inv) => (
              <div
                key={inv.id}
                className="flex items-center gap-2 px-3 py-2 rounded border border-border/60 bg-background"
              >
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-foreground truncate">
                    {inv.number || t('billing.settings.invoiceFallback', { id: inv.id })}
                  </div>
                  <div className="text-[11px] text-muted-foreground">
                    {formatDate(inv.created_at) || '—'}
                    {inv.total_eur != null && <span> · {Number(inv.total_eur).toFixed(2)} €</span>}
                    {inv.vat_mode === 'be_pvm' && <span> · {t('billing.settings.noVat')}</span>}
                  </div>
                </div>
                <a
                  href={invoiceDownloadUrl(inv.id)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center px-2.5 py-1.5 text-xs rounded border border-border bg-card hover:bg-muted/40"
                >
                  <Download className="w-3.5 h-3.5 mr-1.5" />
                  {t('billing.settings.download')}
                </a>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function formatDate(iso) {
  if (!iso) return null;
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return null;
    return d.toISOString().slice(0, 10);
  } catch {
    return null;
  }
}
