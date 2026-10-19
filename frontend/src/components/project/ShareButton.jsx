/**
 * ShareButton — generate / copy / revoke a read-only project share link (SM04).
 *
 * Issues a UUID via POST /api/projects/{id}/share, displays /share/{token},
 * copies to clipboard. DELETE revokes.
 */

import { useState, useEffect, useMemo } from 'react';
import { useTranslation } from '@/i18n/react';
import { Share2, Check, Copy, Loader2, Trash2, ExternalLink } from 'lucide-react';
import { toast } from 'sonner';
import { useConfirm } from '@/components/ui/confirm-provider';
import { API_BASE as API } from '@/lib/apiBase';
import { linesWithoutPrice, sharedLines } from '@/lib/exportLines';

// `expires_at` is a UTC ISO string ("2026-08-26T09:12:33.441+00:00") or null
// when the link was issued with expires_in_days: 0 (= never expires). Slice the
// date part instead of going through Date, so the viewer's timezone can never
// shift the displayed day off the day the backend will actually enforce.
const shareExpiryDate = (iso) =>
  (typeof iso === 'string' && iso.length >= 10 ? iso.slice(0, 10) : null);

// `onGoToPrices` (2026-10-06): „Įrašyti kainas" beside the unpriced count —
// closes this dialog and opens the Sąmata step at the first unpriced row.
export default function ShareButton({ project, onGoToPrices }) {
  const { t } = useTranslation();
  // The link lists every section, so every row with a quantity and no price
  // reaches the client at 0,00 € (lib/exportLines.sharedLines).
  const unpriced = useMemo(
    () => linesWithoutPrice(sharedLines(project)).length, [project]);
  const confirm = useConfirm();
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [token, setToken] = useState(null);
  // Backend defaults links to a 30-day life and returns expires_at on both
  // GET and POST. Not showing it meant links died silently in the client's
  // inbox with no warning anywhere in the UI (2026-07-27 fix).
  const [expiresAt, setExpiresAt] = useState(null);

  // Load the EXISTING share state when the dialog opens (pre-prod audit
  // 2026-07-25: token always started null, so the dialog always offered
  // "generate" — and regenerating silently invalidated the link the user had
  // already emailed to their client).
  useEffect(() => {
    if (!open || !project?.id) return;
    let dead = false;
    (async () => {
      try {
        const res = await fetch(`${API}/api/projects/${project.id}/share`, { credentials: 'include' });
        if (!res.ok) return;
        const body = await res.json();
        if (!dead && body?.token) {
          setToken(body.token);
          setExpiresAt(body.expires_at || null);
        }
      } catch { /* offline — dialog still allows generating */ }
    })();
    return () => { dead = true; };
  }, [open, project?.id]);
  const [copied, setCopied] = useState(false);

  const url = token ? `${window.location.origin}/share/${token}` : null;

  const generate = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/projects/${project.id}/share`, {
        method: 'POST',
        credentials: 'include',
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `HTTP ${res.status}`);
      }
      const body = await res.json();
      setToken(body.token);
      setExpiresAt(body.expires_at || null);
      toast.success(t('project.share.toastGenerated'));
    } catch (e) {
      toast.error(t('project.share.toastError', { msg: e.message }));
    } finally {
      setLoading(false);
    }
  };

  const revoke = async () => {
    if (!(await confirm({
      title: t('project.share.confirmRevokeTitle'),
      description: t('project.share.confirmRevokeDesc'),
      confirmText: t('project.share.confirmRevoke'),
      destructive: true,
    }))) return;
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/projects/${project.id}/share`, {
        method: 'DELETE',
        credentials: 'include',
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `HTTP ${res.status}`);
      }
      setToken(null);
      setExpiresAt(null);
      toast.success(t('project.share.toastRevoked'));
    } catch (e) {
      toast.error(t('project.share.toastError', { msg: e.message }));
    } finally {
      setLoading(false);
    }
  };

  const copy = async () => {
    if (!url) return;
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      toast.success(t('project.share.toastCopied'));
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast.error(t('project.share.toastCopyFail'));
    }
  };

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border border-border hover:bg-muted/40 transition-colors"
        title={t('project.share.buttonTitle')}
      >
        <Share2 className="w-3.5 h-3.5" />
        {t('project.share.button')}
      </button>

      {open && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4"
             onClick={() => !loading && setOpen(false)}>
          <div className="bg-card border border-border rounded-xl shadow-2xl w-full max-w-md p-5"
               onClick={e => e.stopPropagation()}>
            <div className="flex items-center gap-2 mb-3">
              <Share2 className="w-4 h-4 text-muted-foreground" />
              <h2 className="text-sm font-semibold text-foreground">
                {t('project.share.modalTitle')}
              </h2>
            </div>
            <p className="text-xs text-muted-foreground mb-4">
              {t('project.share.modalDesc')}
            </p>

            {unpriced > 0 && (
              <div className="mb-4" role="status">
                <p className="text-[12px]" style={{ color: 'hsl(var(--conf-med))' }}>
                  {t('project.send.checkNoPrice', { count: unpriced })}
                </p>
                {onGoToPrices && (
                  <button type="button" disabled={loading}
                    onClick={() => { setOpen(false); onGoToPrices(null); }}
                    title={t('project.send.goToPricesTitle')}
                    className="mt-2 px-2.5 py-1 text-xs rounded border border-border bg-background hover:bg-muted disabled:opacity-50">
                    {t('project.send.goToPrices')}
                  </button>
                )}
              </div>
            )}

            {!token ? (
              <button
                onClick={generate}
                disabled={loading}
                title="Sukurti peržiūros nuorodą — galios 30 dienų"
                className="w-full inline-flex items-center justify-center gap-2 px-3 py-2 bg-foreground text-background rounded text-sm font-medium hover:opacity-90 disabled:opacity-50"
              >
                {loading
                  ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  : <Share2 className="w-3.5 h-3.5" />}
                Sukurti nuorodą
              </button>
            ) : (
              <div className="space-y-3">
                <div className="flex items-stretch gap-1.5">
                  <input
                    readOnly
                    value={url}
                    aria-label="Peržiūros nuoroda"
                    title="Nusiųskite šią nuorodą klientui — spustelėjus tekstas pažymimas"
                    className="flex-1 px-3 py-2 bg-background border border-border rounded text-xs font-mono"
                    onFocus={e => e.target.select()}
                  />
                  <button
                    onClick={copy}
                    className="px-2.5 rounded border border-border hover:bg-muted/40"
                    title="Kopijuoti nuorodą į iškarpinę"
                    aria-label="Kopijuoti nuorodą"
                  >
                    {copied
                      ? <Check className="w-3.5 h-3.5 text-emerald-600" />
                      : <Copy className="w-3.5 h-3.5" />}
                  </button>
                  <a
                    href={url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="px-2.5 flex items-center rounded border border-border hover:bg-muted/40"
                    title="Atidaryti naujame skirtuke — pamatysite tai, ką matys klientas"
                    aria-label="Atidaryti nuorodą naujame skirtuke"
                  >
                    <ExternalLink className="w-3.5 h-3.5" />
                  </a>
                </div>
                {shareExpiryDate(expiresAt) && (
                  <p className="text-[11px] text-muted-foreground -mt-1.5">
                    Galioja iki {shareExpiryDate(expiresAt)}
                  </p>
                )}
                <button
                  onClick={revoke}
                  disabled={loading}
                  title="Nuoroda nustos veikti — klientas sąmatos nebematys"
                  className="w-full inline-flex items-center justify-center gap-2 px-3 py-2 border border-destructive/50 text-destructive rounded text-sm hover:bg-destructive/10 disabled:opacity-50"
                >
                  {loading
                    ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    : <Trash2 className="w-3.5 h-3.5" />}
                  Atšaukti nuorodą
                </button>
              </div>
            )}

            <button
              onClick={() => !loading && setOpen(false)}
              disabled={loading}
              title="Užverti langą — nuoroda lieka galioti"
              className="mt-3 w-full text-center text-xs text-muted-foreground hover:text-foreground"
            >
              Užverti
            </button>
          </div>
        </div>
      )}
    </>
  );
}
