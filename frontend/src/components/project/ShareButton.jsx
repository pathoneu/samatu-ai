/**
 * ShareButton — generate / copy / revoke a read-only project share link (SM04).
 *
 * Issues a UUID via POST /api/projects/{id}/share, displays /share/{token},
 * copies to clipboard. DELETE revokes.
 */

import { useState } from 'react';
import { Share2, Check, Copy, Loader2, Trash2, ExternalLink } from 'lucide-react';
import { toast } from 'sonner';

const API = '';

export default function ShareButton({ project }) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [token, setToken] = useState(null);
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
      toast.success('Nuoroda sugeneruota');
    } catch (e) {
      toast.error(`Klaida: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  const revoke = async () => {
    if (!window.confirm('Atšaukti nuorodą? Po to ji nebeveiks.')) return;
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
      toast.success('Nuoroda atšaukta');
    } catch (e) {
      toast.error(`Klaida: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  const copy = async () => {
    if (!url) return;
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      toast.success('Nuoroda nukopijuota');
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast.error('Nepavyko nukopijuoti');
    }
  };

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border border-border hover:bg-muted/40 transition-colors"
        title="Bendrinti su nuoroda (read-only)"
      >
        <Share2 className="w-3.5 h-3.5" />
        Bendrinti
      </button>

      {open && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4"
             onClick={() => !loading && setOpen(false)}>
          <div className="bg-card border border-border rounded-xl shadow-2xl w-full max-w-md p-5"
               onClick={e => e.stopPropagation()}>
            <div className="flex items-center gap-2 mb-3">
              <Share2 className="w-4 h-4 text-muted-foreground" />
              <h2 className="text-sm font-semibold text-foreground">
                Skaitomos nuorodos generavimas
              </h2>
            </div>
            <p className="text-xs text-muted-foreground mb-4">
              Sukūrę nuorodą, galėsite ja pasidalinti su statybos vadovu / klientu.
              Jis pamatys tik kiekius (be kainų redagavimo). Nuorodą bet kada galite atšaukti.
            </p>

            {!token ? (
              <button
                onClick={generate}
                disabled={loading}
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
                    className="flex-1 px-3 py-2 bg-background border border-border rounded text-xs font-mono"
                    onFocus={e => e.target.select()}
                  />
                  <button
                    onClick={copy}
                    className="px-2.5 rounded border border-border hover:bg-muted/40"
                    title="Kopijuoti"
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
                    title="Atidaryti naujame skirtuke"
                  >
                    <ExternalLink className="w-3.5 h-3.5" />
                  </a>
                </div>
                <button
                  onClick={revoke}
                  disabled={loading}
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
