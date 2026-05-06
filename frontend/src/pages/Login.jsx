/**
 * Login — email + password (Phase 13).
 * On success → redirect to / (or `from` if user came from protected route).
 */

import React, { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '@/lib/authContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { AlertCircle, Loader2 } from 'lucide-react';
import Logo from '@/components/layout/Logo';
import GoogleSignInButton from '@/components/auth/GoogleSignInButton';

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = location.state?.from?.pathname || '/';

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(email, password);
      navigate(from, { replace: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-6 bg-background">
      <div className="w-full max-w-md">
        <div className="mb-8 flex justify-center">
          <Logo />
        </div>

        <div className="border border-border bg-card rounded-xl p-6">
          <h1 className="text-xl font-semibold mb-1">Prisijungti</h1>
          <p className="text-sm text-muted-foreground mb-6">
            Naudoti Sąmatų AI — įveskite savo el. paštą ir slaptažodį.
          </p>

          {error && (
            <div className="flex items-start gap-2 p-3 mb-4 bg-destructive/10 border border-destructive/30 rounded-lg text-sm text-destructive">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <div>{error}</div>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <Label htmlFor="email">El. paštas</Label>
              <Input id="email" type="email" required autoFocus
                value={email} onChange={e => setEmail(e.target.value)} />
            </div>
            <div>
              <Label htmlFor="password">Slaptažodis</Label>
              <Input id="password" type="password" required
                value={password} onChange={e => setPassword(e.target.value)} />
            </div>
            <Button type="submit" className="w-full" disabled={submitting}>
              {submitting && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
              Prisijungti
            </Button>
          </form>

          <GoogleSignInButton next={from} />

          <div className="mt-4 text-sm text-muted-foreground text-center">
            Neturite paskyros?{' '}
            <Link to="/register" className="text-primary hover:underline">Registruokis</Link>
          </div>
        </div>

        <div className="mt-4 text-xs text-muted-foreground text-center">
          <Link to="/privacy" className="hover:underline">Privatumo politika</Link>
          {' · '}
          <Link to="/terms" className="hover:underline">Naudojimo sąlygos</Link>
        </div>
      </div>
    </div>
  );
}
