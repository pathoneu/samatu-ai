/**
 * Login — email + password (Phase 13).
 * On success → redirect to / (or `from` if user came from protected route —
 * the whole address, query and hash included, since 2026-10-05).
 *
 * 2026-07-05 dark graphite rebuild: two-column branded layout (form + a
 * dark blueprint panel with the detection motif), matching the landing
 * aesthetic. Orange-on-graphite, Sora headings, JetBrains Mono microcopy.
 * All auth logic/handlers/validation are unchanged — styling only.
 */

import React, { useState, useEffect } from 'react';
import { Link, useNavigate, useLocation } from 'react-router';
import { useTranslation } from 'react-i18next';
import { useAuth } from '@/lib/authContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { AlertCircle, Loader2 } from 'lucide-react';
import Logo from '@/components/layout/Logo';
import GoogleSignInButton from '@/components/auth/GoogleSignInButton';
import AuthBrandPanel from '@/components/auth/AuthBrandPanel';
import LanguageToggle from '@/components/LanguageToggle';
import { returnPathFrom } from '@/lib/returnPath';
import { emailStatus, resendVerification } from '@/lib/authEmailApi';

// The Google callback bounces failures back to /login?oauth_error=<code>.
// Codes come from backend main.py (api_google_callback) plus whatever Google
// itself returns in `error` (access_denied etc.). Anything unmapped falls back
// to the generic message — never show a raw code to the user.
const OAUTH_ERROR_KEYS = {
  invalid_state: 'invalidState',
  missing_code: 'missingCode',
  token_exchange_failed: 'tokenExchangeFailed',
  incomplete_userinfo: 'incompleteUserinfo',
  account_disabled: 'accountDisabled',
  access_denied: 'accessDenied',
  email_unverified: 'emailUnverified',
  link_needs_password: 'linkNeedsPassword',
};

export default function Login() {
  const { t } = useTranslation();
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  // The whole address that sent the visitor here — path, ?step=… / ?kambarys=…
  // and hash — for both the password and the Google sign-in (lib/returnPath.js).
  const from = returnPathFrom(location.state);

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  // v3 M2: an unverified inbox (gate on) can ask for the link again; and the
  // reset form replaces the write-to-us link once a link can reach the person.
  const [unverified, setUnverified] = useState(false);
  const [resent, setResent] = useState('');
  const [resetAvailable, setResetAvailable] = useState(false);
  useEffect(() => {
    let alive = true;
    emailStatus().then((r) => { if (alive && r.ok) setResetAvailable(r.data?.links_can_be_sent === true); });
    return () => { alive = false; };
  }, []);

  // Surface a failed Google sign-in in the existing error banner. Before this
  // the redirect landed on a pristine login form and the user had no idea why.
  useEffect(() => {
    const code = new URLSearchParams(location.search).get('oauth_error');
    if (!code) return;
    setError(t(`login.oauthErr.${OAUTH_ERROR_KEYS[code] || 'generic'}`));
  }, [location.search, t]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setUnverified(false);
    setResent('');
    setSubmitting(true);
    try {
      await login(email, password);
      navigate(from, { replace: true });
    } catch (err) {
      setError(err.message);
      setUnverified(err.body?.detail?.error === 'email_not_verified');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="pathon-landing min-h-screen grid lg:grid-cols-[1.05fr_1fr]">
      {/* ── Form column ─────────────────────────────────────────────── */}
      <div className="relative flex flex-col justify-center px-6 py-12 sm:px-10 lg:px-16">
        <div className="w-full max-w-md mx-auto">
          <div className="mb-10 flex items-center justify-between gap-3">
            <Link to="/" title={t('login.backHome')} className="no-underline inline-block">
              <Logo size="lg" showSub={false} />
            </Link>
            <LanguageToggle />
          </div>

          <div className="mb-8">
            <div className="mono-tick mb-3">{t('login.tick')}</div>
            <h1 className="font-display text-3xl font-semibold tracking-tight leading-tight">
              {t('login.title')}
            </h1>
            <p className="mt-2 text-sm text-muted-foreground">
              {t('login.sub')}
            </p>
          </div>

          {error && (
            <div className="flex items-start gap-2 p-3 mb-5 bg-destructive/10 border border-destructive/30 rounded-lg text-sm text-destructive">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <div>
                {error}
                {unverified && !resent && (
                  <button type="button" className="block mt-2 underline text-foreground"
                    onClick={async () => {
                      const r = await resendVerification(email);
                      setResent(r.message || t('authEmail.genericError'));
                    }}>
                    {t('login.resendVerification')}
                  </button>
                )}
                {resent && <p className="mt-2 text-foreground">{resent}</p>}
              </div>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="email" className="text-xs font-mono uppercase tracking-wider text-muted-foreground">
                {t('login.email')}
              </Label>
              <Input id="email" type="email" required autoFocus
                className="h-11 bg-card border-border-strong focus-visible:ring-2 focus-visible:ring-primary/60"
                value={email} onChange={e => setEmail(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="password" className="text-xs font-mono uppercase tracking-wider text-muted-foreground">
                {t('login.password')}
              </Label>
              <Input id="password" type="password" required
                className="h-11 bg-card border-border-strong focus-visible:ring-2 focus-visible:ring-primary/60"
                value={password} onChange={e => setPassword(e.target.value)} />
            </div>
            <Button type="submit" className="btn-primary w-full h-11 text-sm" disabled={submitting}>
              {submitting && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
              {t('login.submit')}
            </Button>
          </form>

          <GoogleSignInButton next={from} />

          <div className="mt-6 text-sm text-muted-foreground text-center">
            {t('login.noAccount')}{' '}
            <Link to="/register" className="text-primary font-medium hover:underline">{t('login.registerLink')}</Link>
          </div>
          <p className="text-center text-sm text-muted-foreground mt-2">
            {/* v3 M2 (2026-10-18): the reset form once a link can reach the
                person (SMTP set, or development); until then the write-to-us
                link, so a forgotten password is never a permanent lockout. */}
            {resetAvailable ? (
              <Link to="/pamirsau-slaptazodi" className="hover:text-foreground underline">
                {t('login.forgotPasswordLink')}
              </Link>
            ) : (
              <a href="mailto:solutions@pathon.eu?subject=Slapta%C5%BEod%C5%BEio%20atk%C5%ABrimas" className="hover:text-foreground underline">
                {t('login.forgotPassword')}
              </a>
            )}
          </p>

          <div className="mt-8 pt-6 border-t border-border text-xs text-muted-foreground text-center">
            <Link to="/privacy" className="hover:text-foreground transition-colors">{t('login.privacyPolicy')}</Link>
            <span className="mx-2 opacity-40">·</span>
            <Link to="/terms" className="hover:text-foreground transition-colors">{t('login.termsOfUse')}</Link>
          </div>
        </div>
      </div>

      {/* ── Brand panel (desktop only) ──────────────────────────────── */}
      <AuthBrandPanel
        eyebrow={t('login.brandEyebrow')}
        headline={<>{t('login.brandHeadlineA')}<span className="h-accent">{t('login.brandHeadlineAccent')}</span>{t('login.brandHeadlineB')}</>}
        sub={t('login.brandSub')}
      />
    </div>
  );
}
