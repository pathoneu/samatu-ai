/**
 * Register — new account creation (Phase 13).
 * email + password + optional name + company. First user becomes admin.
 *
 * 2026-07-05 dark graphite rebuild: two-column branded layout matching the
 * landing (form + blueprint detection panel). Orange-on-graphite, Sora
 * headings, JetBrains Mono microcopy. All validation/handlers unchanged.
 */

import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '@/lib/authContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { AlertCircle, Loader2, ShieldCheck } from 'lucide-react';
import Logo from '@/components/layout/Logo';
import GoogleSignInButton from '@/components/auth/GoogleSignInButton';
import AuthBrandPanel from '@/components/auth/AuthBrandPanel';

export default function Register() {
  const { register } = useAuth();
  const navigate = useNavigate();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [password2, setPassword2] = useState('');
  const [name, setName] = useState('');
  const [companyName, setCompanyName] = useState('');
  const [agreed, setAgreed] = useState(false);
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [firstAdmin, setFirstAdmin] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    if (password !== password2) {
      setError('Slaptažodžiai nesutampa');
      return;
    }
    if (password.length < 8) {
      setError('Slaptažodis turi būti ne trumpesnis nei 8 simboliai');
      return;
    }
    if (!agreed) {
      setError('Privalote sutikti su naudojimo sąlygomis ir privatumo politika');
      return;
    }
    setSubmitting(true);
    try {
      const r = await register({ email, password, name, company_name: companyName });
      setFirstAdmin(r.isFirstAdmin);
      // Brief celebration if first admin, then redirect
      setTimeout(() => navigate('/', { replace: true }), r.isFirstAdmin ? 1500 : 100);
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  if (firstAdmin) {
    return (
      <div className="pathon-landing min-h-screen flex items-center justify-center p-6">
        <div className="blueprint-grid-major absolute inset-0 pointer-events-none" aria-hidden />
        <div className="relative text-center">
          <div className="mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10 border border-primary/30">
            <ShieldCheck className="w-8 h-8 text-primary" />
          </div>
          <h1 className="font-display text-2xl font-semibold tracking-tight mb-2">Sveiki, administratoriau!</h1>
          <p className="text-muted-foreground">Esate pirmasis vartotojas — gausite admin teises.</p>
          <p className="text-sm text-muted-foreground mt-4 font-mono">Nukreipiame į pulpitą…</p>
        </div>
      </div>
    );
  }

  return (
    <div className="pathon-landing min-h-screen grid lg:grid-cols-[1.05fr_1fr]">
      {/* ── Form column ─────────────────────────────────────────────── */}
      <div className="relative flex flex-col justify-center px-6 py-12 sm:px-10 lg:px-16">
        <div className="w-full max-w-md mx-auto">
          <div className="mb-10">
            <Link to="/" title="Į pradžią" className="no-underline inline-block">
              <Logo size="lg" showSub={false} />
            </Link>
          </div>

          <div className="mb-8">
            <div className="mono-tick mb-3">01 / REGISTRACIJA</div>
            <h1 className="font-display text-3xl font-semibold tracking-tight leading-tight">
              Sukurti paskyrą
            </h1>
            <p className="mt-2 text-sm text-muted-foreground">
              Vienas vartotojas — savo projektai. Duomenys saugomi LT/EU serveryje.
            </p>
          </div>

          {error && (
            <div className="flex items-start gap-2 p-3 mb-5 bg-destructive/10 border border-destructive/30 rounded-lg text-sm text-destructive">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <div>{error}</div>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-3.5">
            <div className="space-y-1.5">
              <Label htmlFor="email" className="text-xs font-mono uppercase tracking-wider text-muted-foreground">
                El. paštas *
              </Label>
              <Input id="email" type="email" required autoFocus
                className="h-11 bg-card border-border-strong focus-visible:ring-2 focus-visible:ring-primary/60"
                value={email} onChange={e => setEmail(e.target.value)} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="name" className="text-xs font-mono uppercase tracking-wider text-muted-foreground">
                  Vardas
                </Label>
                <Input id="name"
                  className="h-11 bg-card border-border-strong focus-visible:ring-2 focus-visible:ring-primary/60"
                  value={name} onChange={e => setName(e.target.value)} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="company" className="text-xs font-mono uppercase tracking-wider text-muted-foreground">
                  Įmonė
                </Label>
                <Input id="company"
                  className="h-11 bg-card border-border-strong focus-visible:ring-2 focus-visible:ring-primary/60"
                  value={companyName} onChange={e => setCompanyName(e.target.value)} />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="password" className="text-xs font-mono uppercase tracking-wider text-muted-foreground">
                Slaptažodis * <span className="normal-case tracking-normal opacity-70">(min 8 simb.)</span>
              </Label>
              <Input id="password" type="password" required minLength={8}
                className="h-11 bg-card border-border-strong focus-visible:ring-2 focus-visible:ring-primary/60"
                value={password} onChange={e => setPassword(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="password2" className="text-xs font-mono uppercase tracking-wider text-muted-foreground">
                Pakartoti slaptažodį *
              </Label>
              <Input id="password2" type="password" required
                className="h-11 bg-card border-border-strong focus-visible:ring-2 focus-visible:ring-primary/60"
                value={password2} onChange={e => setPassword2(e.target.value)} />
            </div>

            <label className="flex items-start gap-2.5 text-sm cursor-pointer pt-1">
              <input
                type="checkbox"
                className="mt-0.5 h-4 w-4 accent-[hsl(var(--primary))]"
                checked={agreed}
                onChange={e => setAgreed(e.target.checked)}
              />
              <span className="text-muted-foreground">
                Sutinku su{' '}
                <Link to="/terms" className="text-primary hover:underline" target="_blank">naudojimo sąlygomis</Link>
                {' '}ir{' '}
                <Link to="/privacy" className="text-primary hover:underline" target="_blank">privatumo politika</Link>
              </span>
            </label>

            <Button type="submit" className="btn-primary w-full h-11 text-sm" disabled={submitting || !agreed}>
              {submitting && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
              Sukurti paskyrą
            </Button>
          </form>

          <GoogleSignInButton next="/" label="Registruotis su Google" />

          <div className="mt-6 text-sm text-muted-foreground text-center">
            Jau turite paskyrą?{' '}
            <Link to="/login" className="text-primary font-medium hover:underline">Prisijungti</Link>
          </div>
        </div>
      </div>

      {/* ── Brand panel (desktop only) ──────────────────────────────── */}
      <AuthBrandPanel
        eyebrow="PATHON — STATYBŲ SĄMATOS"
        headline={<>Nustok matuoti ranka. <span className="h-accent">Tikrink, ne skaičiuok.</span></>}
        sub="Pathon perskaito brėžinį, aptinka kambarius ir kiekius — tu tik patvirtini."
      />
    </div>
  );
}
