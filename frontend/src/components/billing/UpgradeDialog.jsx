/**
 * UpgradeDialog — the paywall block dialog (Phase 7, Task 17).
 *
 * Opened when project creation (/extract-interior) is refused by the backend:
 *   - 403 company_code_required → prompt for įmonės kodas, save via PUT profile,
 *     then call onRetry() so the user's action completes without re-uploading.
 *   - 402 quota_exceeded / trial_used → show upgrade (Pro/Studio) + one-off,
 *     each linking to Stripe Checkout.
 *
 * Reads prices from useBilling().plans — never hardcoded here. Mounts only when
 * billing is enabled (the caller already gates on that, and reason==null keeps
 * it closed).
 */

import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Building2, Sparkles, ArrowRight } from 'lucide-react';
import { toast } from 'sonner';
import { useBilling } from '@/hooks/useBilling';
import { startCheckout, saveCompanyCode } from '@/lib/billingApi';
import { planById } from '@/lib/paywall';

const eur = (n) => `${Number(n).toFixed(0)} €`;

/**
 * @param {object}   props
 * @param {null|'company_code_required'|'quota_exceeded'|'trial_used'} props.reason
 * @param {string=}  props.message  backend message to surface
 * @param {()=>void} props.onClose
 * @param {()=>void=} props.onRetry  called after company code saved (re-run the blocked action)
 */
export default function UpgradeDialog({ reason, message, onClose, onRetry }) {
  const { t } = useTranslation();
  const { plans, refresh } = useBilling();
  const [companyCode, setCompanyCode] = useState('');
  const [pvmCode, setPvmCode] = useState('');
  const [saving, setSaving] = useState(false);
  const [checkingOut, setCheckingOut] = useState(null); // plan name being redirected

  const open = reason != null;
  const isCompanyCode = reason === 'company_code_required';

  // Match on plan `id` ('pro'/'studio'/'oneoff'), NOT `name` — the backend
  // emits `name` as the display label ("Pro"/"Studio"/"Vienkartinis"), so the
  // old name-match resolved nothing and this dialog rendered with zero
  // purchasable options the moment billing flipped on (2026-07-27; same bug
  // fixed in Pricing.jsx by 175a206).
  const pro = planById(plans, 'pro');
  const studio = planById(plans, 'studio');
  const oneoff = planById(plans, 'oneoff');

  const handleSaveCode = async () => {
    if (!companyCode.trim()) {
      toast.error(t('billing.upgrade.toastEnterCode'));
      return;
    }
    setSaving(true);
    try {
      await saveCompanyCode({
        company_code: companyCode.trim(),
        pvm_code: pvmCode.trim() || undefined,
      });
      refresh();
      toast.success(t('billing.upgrade.toastCodeSaved'));
      onClose();
      onRetry?.();
    } catch (e) {
      toast.error(e.message || t('billing.upgrade.toastSaveFail'));
    } finally {
      setSaving(false);
    }
  };

  const handleCheckout = async (planName) => {
    setCheckingOut(planName);
    try {
      await startCheckout(planName); // redirects on success
    } catch (e) {
      toast.error(e.message || t('billing.upgrade.toastCheckoutFail'));
      setCheckingOut(null);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onClose(); }}>
      <DialogContent className="max-w-md">
        {isCompanyCode ? (
          <>
            <DialogHeader>
              <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center mb-2">
                <Building2 className="w-5 h-5 text-primary" />
              </div>
              <DialogTitle>{t('billing.upgrade.companyCodeTitle')}</DialogTitle>
              <DialogDescription>
                {message || t('billing.upgrade.companyCodeDesc')}
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-4 py-1">
              <div>
                <Label htmlFor="upgrade-company-code" className="text-sm text-muted-foreground">
                  {t('billing.upgrade.companyCode')}
                </Label>
                <Input
                  id="upgrade-company-code"
                  value={companyCode}
                  onChange={(e) => setCompanyCode(e.target.value)}
                  placeholder="123456789"
                  className="mt-1.5"
                  autoFocus
                />
              </div>
              <div>
                <Label htmlFor="upgrade-pvm-code" className="text-sm text-muted-foreground">
                  {t('billing.upgrade.pvmCode')} <span className="opacity-60">{t('billing.upgrade.optional')}</span>
                </Label>
                <Input
                  id="upgrade-pvm-code"
                  value={pvmCode}
                  onChange={(e) => setPvmCode(e.target.value)}
                  placeholder="LT123456789"
                  className="mt-1.5"
                />
              </div>
            </div>

            <DialogFooter>
              <Button variant="outline" onClick={onClose} disabled={saving}>
                {t('billing.upgrade.cancel')}
              </Button>
              <Button
                onClick={handleSaveCode}
                disabled={saving}
                className="bg-primary hover:bg-primary/90 text-primary-foreground"
              >
                {saving ? t('billing.upgrade.saving') : t('billing.upgrade.saveAndContinue')}
              </Button>
            </DialogFooter>
          </>
        ) : (
          <>
            <DialogHeader>
              <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center mb-2">
                <Sparkles className="w-5 h-5 text-primary" />
              </div>
              <DialogTitle>
                {reason === 'trial_used' ? t('billing.upgrade.trialUsedTitle') : t('billing.upgrade.quotaTitle')}
              </DialogTitle>
              <DialogDescription>
                {message ||
                  (reason === 'trial_used'
                    ? t('billing.upgrade.trialUsedDesc')
                    : t('billing.upgrade.quotaDesc'))}
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-2.5 py-1">
              {pro && (
                <PlanRow
                  title={t('billing.plans.pro')}
                  price={`${eur(pro.price_eur)}/${t('billing.upgrade.perMonth')}`}
                  sub={t('billing.upgrade.projectsPerMonth', { count: pro.pdf_quota_per_month })}
                  busy={checkingOut === 'pro'}
                  onClick={() => handleCheckout('pro')}
                  highlight
                />
              )}
              {studio && (
                <PlanRow
                  title={t('billing.plans.studio')}
                  price={`${eur(studio.price_eur)}/${t('billing.upgrade.perMonth')}`}
                  sub={t('billing.upgrade.projectsPerMonth', { count: studio.pdf_quota_per_month })}
                  busy={checkingOut === 'studio'}
                  onClick={() => handleCheckout('studio')}
                />
              )}
              {oneoff && (
                <PlanRow
                  title={t('billing.plans.oneoff')}
                  price={`${eur(oneoff.price_eur)}`}
                  sub={t('billing.upgrade.oneoffSub')}
                  busy={checkingOut === 'oneoff'}
                  onClick={() => handleCheckout('oneoff')}
                />
              )}
            </div>

            <p className="text-[11px] text-muted-foreground text-center">
              {t('billing.upgrade.vatNote')}
            </p>

            <DialogFooter>
              <Button variant="outline" onClick={onClose} disabled={!!checkingOut}>
                {t('billing.upgrade.later')}
              </Button>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

function PlanRow({ title, price, sub, onClick, busy, highlight }) {
  const { t } = useTranslation();
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={busy}
      className={`w-full flex items-center justify-between gap-3 p-3 rounded-lg border text-left transition-colors ${
        highlight
          ? 'border-primary bg-primary/5 hover:bg-primary/10'
          : 'border-border bg-card hover:border-foreground/30'
      } disabled:opacity-60`}
    >
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-foreground">{title}</span>
          {highlight && (
            <span className="text-[10px] uppercase tracking-wide font-medium px-1.5 py-0.5 rounded bg-primary/15 text-primary">
              {t('billing.upgrade.popular')}
            </span>
          )}
        </div>
        <div className="text-xs text-muted-foreground mt-0.5 truncate">{sub}</div>
      </div>
      <div className="flex items-center gap-1.5 shrink-0">
        <span className="text-sm font-semibold text-foreground">{price}</span>
        <ArrowRight className="w-4 h-4 text-muted-foreground" />
      </div>
    </button>
  );
}
