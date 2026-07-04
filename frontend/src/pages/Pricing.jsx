/**
 * Pricing — public-facing plan selection (Phase 7, Task 16).
 *
 * Professional 3-card layout (Pro / Studio / Vienkartinis) + a free-trial
 * callout. Prices/quotas come from useBilling().plans (backend = source of
 * truth) — NEVER hardcoded. Each purchasable CTA → POST /checkout → redirect.
 *
 * Flag gate: mounts under the protected layout, but if billing is disabled it
 * bounces to /dashboard so the route is effectively invisible when off.
 */

import React, { useState } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Check, ArrowLeft } from 'lucide-react';
import { toast } from 'sonner';
import { useBilling } from '@/hooks/useBilling';
import { startCheckout } from '@/lib/billingApi';

// Presentation order + copy. Prices/quotas are read from the backend plan by
// `name`; the values here are only labels/marketing, not the source of truth.
const PLAN_META = {
  pro: {
    label: 'Pro',
    tagline: 'Nuolatiniam darbui',
    highlight: true,
    features: [
      'Iki 10 projektų per mėnesį',
      'Interjero apdailos kiekiai',
      'PDF ir Excel eksportas',
      'Kiekių koregavimo įrankiai',
    ],
    period: '/mėn',
  },
  studio: {
    label: 'Studio',
    tagline: 'Komandoms ir biurams',
    highlight: false,
    features: [
      'Iki 35 projektų per mėnesį',
      'Visos Pro funkcijos',
      'Prioritetinis apdorojimas',
      'Papildomi projektai už mažesnę kainą',
    ],
    period: '/mėn',
  },
  oneoff: {
    label: 'Vienkartinis',
    tagline: 'Vienam projektui',
    highlight: false,
    features: [
      'Vienas projektas',
      'Be prenumeratos',
      'Pilnas kiekių skaičiavimas',
      'PDF ir Excel eksportas',
    ],
    period: '/projektas',
  },
};

const ORDER = ['pro', 'studio', 'oneoff'];

const eur = (n) => `${Number(n).toFixed(0)} €`;

export default function Pricing() {
  const navigate = useNavigate();
  const { enabled, plans, isLoading } = useBilling();
  const [checkingOut, setCheckingOut] = useState(null);

  if (isLoading) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center text-muted-foreground text-sm">
        Kraunama…
      </div>
    );
  }

  // Flag-off invariant: no billing → route is invisible.
  if (!enabled) return <Navigate to="/dashboard" replace />;

  const planByName = (name) => plans.find((p) => p.name === name);
  const orderedPlans = ORDER.map((name) => ({ name, plan: planByName(name), meta: PLAN_META[name] }))
    .filter((x) => x.plan && x.meta);

  const handleCheckout = async (name) => {
    setCheckingOut(name);
    try {
      await startCheckout(name); // redirects on success
    } catch (e) {
      toast.error(e.message || 'Nepavyko atidaryti apmokėjimo');
      setCheckingOut(null);
    }
  };

  return (
    <div className="p-6 lg:p-8 max-w-5xl mx-auto">
      <button
        onClick={() => navigate('/dashboard')}
        className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors mb-6"
      >
        <ArrowLeft className="w-4 h-4" />
        Grįžti į projektus
      </button>

      <div className="mb-8">
        <div className="font-mono text-[11px] uppercase tracking-[0.08em] text-muted-foreground mb-2">
          Planai
        </div>
        <h1 className="text-2xl font-semibold text-foreground tracking-tight">Pasirinkite planą</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Mokėkite tik už tai, ką naudojate. Bet kada galite keisti planą.
        </p>
      </div>

      {/* Free-trial callout */}
      <div className="mb-6 rounded-xl border border-primary/25 bg-primary/5 p-4 flex items-start gap-3">
        <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
          <Check className="w-5 h-5 text-primary" />
        </div>
        <div>
          <h2 className="text-sm font-semibold text-foreground">Nemokamas bandymas</h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Išbandykite su vienu projektu nemokamai. Reikalingas įmonės kodas — verslo klientams.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {orderedPlans.map(({ name, plan, meta }) => (
          <div
            key={name}
            className={`relative flex flex-col rounded-xl border p-6 bg-card ${
              meta.highlight ? 'border-primary shadow-sm' : 'border-border'
            }`}
          >
            {meta.highlight && (
              <span className="absolute -top-2.5 left-6 text-[10px] uppercase tracking-wide font-medium px-2 py-0.5 rounded bg-primary text-primary-foreground">
                Populiariausias
              </span>
            )}

            <h3 className="text-base font-semibold text-foreground">{meta.label}</h3>
            <p className="text-xs text-muted-foreground mt-0.5">{meta.tagline}</p>

            <div className="mt-4 flex items-baseline gap-1">
              <span className="text-3xl font-semibold text-foreground tracking-tight">
                {eur(plan.price_eur)}
              </span>
              <span className="text-sm text-muted-foreground">{meta.period}</span>
            </div>

            <ul className="mt-5 space-y-2 flex-1">
              {meta.features.map((f) => (
                <li key={f} className="flex items-start gap-2 text-sm text-foreground/85">
                  <Check className="w-4 h-4 text-primary shrink-0 mt-0.5" />
                  <span>{f}</span>
                </li>
              ))}
            </ul>

            <Button
              onClick={() => handleCheckout(name)}
              disabled={checkingOut != null}
              className={`mt-6 w-full font-medium ${
                meta.highlight
                  ? 'bg-primary hover:bg-primary/90 text-primary-foreground'
                  : ''
              }`}
              variant={meta.highlight ? 'default' : 'outline'}
            >
              {checkingOut === name ? 'Nukreipiama…' : 'Pasirinkti'}
            </Button>
          </div>
        ))}
      </div>

      <p className="text-xs text-muted-foreground text-center mt-6">
        Kainos be PVM — verslo klientams taikomas atvirkštinis apmokestinimas.
      </p>
    </div>
  );
}
