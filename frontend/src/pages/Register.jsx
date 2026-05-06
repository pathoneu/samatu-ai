/**
 * Register — new account creation (Phase 13).
 * email + password + optional name + company. First user becomes admin.
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
      <div className="min-h-screen flex items-center justify-center p-6 bg-background">
        <div className="text-center">
          <ShieldCheck className="w-16 h-16 mx-auto text-primary mb-4" />
          <h1 className="text-2xl font-semibold mb-2">Sveiki, administratoriau!</h1>
          <p className="text-muted-foreground">Esate pirmasis vartotojas — gausite admin teises.</p>
          <p className="text-sm text-muted-foreground mt-4">Nukreipiame į pulpitą...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-6 bg-background">
      <div className="w-full max-w-md">
        <div className="mb-8 flex justify-center">
          <Logo />
        </div>

        <div className="border border-border bg-card rounded-xl p-6">
          <h1 className="text-xl font-semibold mb-1">Sukurti paskyrą</h1>
          <p className="text-sm text-muted-foreground mb-6">
            Vienas vartotojas — savo projektai. Duomenys saugomi LT/EU serveryje.
          </p>

          {error && (
            <div className="flex items-start gap-2 p-3 mb-4 bg-destructive/10 border border-destructive/30 rounded-lg text-sm text-destructive">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <div>{error}</div>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-3">
            <div>
              <Label htmlFor="email">El. paštas *</Label>
              <Input id="email" type="email" required autoFocus
                value={email} onChange={e => setEmail(e.target.value)} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label htmlFor="name">Vardas</Label>
                <Input id="name" value={name} onChange={e => setName(e.target.value)} />
              </div>
              <div>
                <Label htmlFor="company">Įmonė</Label>
                <Input id="company" value={companyName} onChange={e => setCompanyName(e.target.value)} />
              </div>
            </div>
            <div>
              <Label htmlFor="password">Slaptažodis *  <span className="text-xs text-muted-foreground">(min 8 simb.)</span></Label>
              <Input id="password" type="password" required minLength={8}
                value={password} onChange={e => setPassword(e.target.value)} />
            </div>
            <div>
              <Label htmlFor="password2">Pakartoti slaptažodį *</Label>
              <Input id="password2" type="password" required
                value={password2} onChange={e => setPassword2(e.target.value)} />
            </div>

            <label className="flex items-start gap-2 text-sm cursor-pointer pt-1">
              <input
                type="checkbox"
                className="mt-1"
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

            <Button type="submit" className="w-full" disabled={submitting || !agreed}>
              {submitting && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
              Sukurti paskyrą
            </Button>
          </form>

          <GoogleSignInButton next="/" label="Registruotis su Google" />

          <div className="mt-4 text-sm text-muted-foreground text-center">
            Jau turite paskyrą?{' '}
            <Link to="/login" className="text-primary hover:underline">Prisijungti</Link>
          </div>
        </div>
      </div>
    </div>
  );
}
