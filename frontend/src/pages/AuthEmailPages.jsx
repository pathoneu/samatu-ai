/**
 * AuthEmailPages — the three pages an emailed link or the login page opens
 * (v3 W7-A M2): „Pamiršote slaptažodį?" (ask for a reset link), the new-password
 * form (`/slaptazodzio-keitimas?token=…`) and the email confirmation
 * (`/el-pasto-patvirtinimas?token=…`). Backend: backend/api/auth_email.py.
 *
 * The one-time code is read once and removed from the address bar, so it does
 * not linger in the history or leave in a Referer header.
 */
import React, { useEffect, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router';
import { useTranslation } from '@/i18n/react';
import { AlertCircle, CheckCircle2, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import Logo from '@/components/layout/Logo';
import {
  emailStatus, forgotPassword, resetPassword, verifyEmail, tokenFromSearch,
} from '@/lib/authEmailApi';

const CONTACT = 'solutions@pathon.eu';

function Shell({ title, sub, children }) {
  return (
    <div className="pathon-landing min-h-screen flex flex-col justify-center px-4 py-12 bg-background">
      <div className="w-full max-w-md mx-auto">
        <Link to="/" className="no-underline inline-block mb-10"><Logo size="lg" showSub={false} /></Link>
        <h1 className="font-display text-3xl font-semibold tracking-tight leading-tight">{title}</h1>
        {sub && <p className="mt-2 text-sm text-muted-foreground">{sub}</p>}
        <div className="mt-8">{children}</div>
      </div>
    </div>
  );
}

function Notice({ kind, children }) {
  const ok = kind === 'ok';
  const Icon = ok ? CheckCircle2 : AlertCircle;
  return (
    <div role={ok ? 'status' : 'alert'}
      className={`flex items-start gap-2 p-3 mb-5 rounded-[2px] border text-sm ${ok
        ? 'bg-primary/10 border-primary/30 text-foreground'
        : 'bg-destructive/10 border-destructive/30 text-destructive'}`}>
      <Icon className="w-4 h-4 shrink-0 mt-0.5" />
      <div>{children}</div>
    </div>
  );
}

/** Read `?token=` once, then drop it from the address bar. */
function useOneTimeToken() {
  const location = useLocation();
  const [token] = useState(() => tokenFromSearch(location.search));
  useEffect(() => {
    if (token && typeof window !== 'undefined') {
      window.history.replaceState(window.history.state, '', location.pathname);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  return token;
}

export function ForgotPassword() {
  const { t } = useTranslation();
  const [email, setEmail] = useState('');
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState('');
  const [error, setError] = useState('');
  const [available, setAvailable] = useState(true);

  useEffect(() => {
    let alive = true;
    emailStatus().then((r) => { if (alive && r.ok) setAvailable(r.data?.links_can_be_sent !== false); });
    return () => { alive = false; };
  }, []);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true); setError('');
    const r = await forgotPassword(email);
    setBusy(false);
    if (r.ok) setSent(r.message);
    else setError(r.message || t('authEmail.genericError'));
  };

  return (
    <Shell title={t('authEmail.forgotTitle')} sub={available ? t('authEmail.forgotSub') : null}>
      {!available ? (
        <p className="text-sm text-foreground">
          {t('authEmail.forgotUnavailable')}{' '}
          <a className="underline" href={`mailto:${CONTACT}?subject=Slapta%C5%BEod%C5%BEio%20atk%C5%ABrimas`}>{CONTACT}</a>
        </p>
      ) : sent ? (
        <Notice kind="ok">{sent}</Notice>
      ) : (
        <form onSubmit={submit} className="space-y-4">
          {error && <Notice kind="error">{error}</Notice>}
          <div className="space-y-1.5">
            <Label htmlFor="email" className="text-sm text-muted-foreground">{t('login.email')}</Label>
            <Input id="email" type="email" required autoFocus value={email}
              onChange={(e) => setEmail(e.target.value)} className="h-11 bg-card" />
          </div>
          <Button type="submit" className="btn-primary w-full h-11 text-sm" disabled={busy}>
            {busy && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
            {t('authEmail.forgotSubmit')}
          </Button>
        </form>
      )}
      <p className="mt-6 text-sm text-center"><Link to="/login" className="text-primary hover:underline">{t('authEmail.backToLogin')}</Link></p>
    </Shell>
  );
}

export function ResetPassword() {
  const { t } = useTranslation();
  const token = useOneTimeToken();
  const [pw, setPw] = useState('');
  const [pw2, setPw2] = useState('');
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState('');
  const [error, setError] = useState(token ? '' : t('authEmail.noToken'));

  const submit = async (e) => {
    e.preventDefault();
    if (pw !== pw2) { setError(t('authEmail.errMismatch')); return; }
    if (pw.length < 8) { setError(t('authEmail.errShort')); return; }
    setBusy(true); setError('');
    const r = await resetPassword(token, pw);
    setBusy(false);
    if (r.ok) setDone(r.message);
    else setError(r.message || t('authEmail.genericError'));
  };

  return (
    <Shell title={t('authEmail.resetTitle')} sub={done ? null : t('authEmail.resetSub')}>
      {done ? (
        <>
          <Notice kind="ok">{done}</Notice>
          <Link to="/login" className="text-primary hover:underline text-sm">{t('authEmail.toLogin')}</Link>
        </>
      ) : (
        <>
          {error && <Notice kind="error">{error}</Notice>}
          {token ? (
            <form onSubmit={submit} className="space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="pw" className="text-sm text-muted-foreground">{t('authEmail.newPassword')}</Label>
                <Input id="pw" type="password" required autoFocus autoComplete="new-password" value={pw}
                  onChange={(e) => setPw(e.target.value)} className="h-11 bg-card" />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="pw2" className="text-sm text-muted-foreground">{t('authEmail.newPassword2')}</Label>
                <Input id="pw2" type="password" required autoComplete="new-password" value={pw2}
                  onChange={(e) => setPw2(e.target.value)} className="h-11 bg-card" />
              </div>
              <Button type="submit" className="btn-primary w-full h-11 text-sm" disabled={busy}>
                {busy && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
                {t('authEmail.resetSubmit')}
              </Button>
            </form>
          ) : null}
          {error && (
            <p className="mt-4 text-sm"><Link to="/pamirsau-slaptazodi" className="text-primary hover:underline">{t('authEmail.askNewLink')}</Link></p>
          )}
        </>
      )}
    </Shell>
  );
}

export function VerifyEmail() {
  const { t } = useTranslation();
  const token = useOneTimeToken();
  const [state, setState] = useState(token ? 'busy' : 'error');
  const [message, setMessage] = useState(token ? '' : t('authEmail.noToken'));
  const once = useRef(false);

  useEffect(() => {
    if (!token || once.current) return;
    once.current = true; // a single-use code: never post it twice (StrictMode runs effects twice)
    verifyEmail(token).then((r) => {
      setState(r.ok ? 'ok' : 'error');
      setMessage(r.message || t('authEmail.genericError'));
    });
  }, [token, t]);

  return (
    <Shell title={t('authEmail.verifyTitle')}>
      {state === 'busy' && (
        <p className="text-sm text-muted-foreground flex items-center gap-2">
          <Loader2 className="w-4 h-4 animate-spin" />{t('authEmail.verifying')}
        </p>
      )}
      {state !== 'busy' && <Notice kind={state === 'ok' ? 'ok' : 'error'}>{message}</Notice>}
      {state !== 'busy' && (
        <Link to="/login" className="text-primary hover:underline text-sm">{t('authEmail.toLogin')}</Link>
      )}
    </Shell>
  );
}
