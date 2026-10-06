/**
 * FreeRereadBanner — „this drawing can be read better, for free".
 *
 * A project extracted before the geometry lane existed (vector outlines,
 * perimeters added from the written strings, floor coverings off the floor
 * plan) has none of it, and a full re-extraction costs money. The lane needs
 * no Vision call — only the stored PDF — so the offer is one click
 * (api/free_reread.py, lib/freeReread.js). It is an OFFER, never automatic: a
 * re-read moves quantities, and that is an event he has to see. What changed
 * is then shown by RereadDiffBanner / RereadRoomNote, as after any re-read.
 */

import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Loader2, ScanLine, X } from 'lucide-react';
import { toast } from 'sonner';

import { fetchFreeRereadStatus, runFreeReread } from '@/lib/freeRereadApi';
import { freeRereadDoneText, freeRereadState } from '@/lib/freeReread';
import { flushProjectSaves, getProject, updateProject } from '@/lib/projectStore';
import { recordPilot } from '@/lib/telemetry';

const dismissedKey = (id) => `pathon_free_reread_later_${id}`;

export default function FreeRereadBanner({ project, onComplete, className = '' }) {
  const { t } = useTranslation();
  const id = project?.id;
  const [offer, setOffer] = useState(false);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(null);

  useEffect(() => {
    if (!id) return undefined;
    let later = false;
    try { later = sessionStorage.getItem(dismissedKey(id)) === '1'; } catch { /* private window */ }
    if (later) return undefined;
    const ctl = new AbortController();
    fetchFreeRereadStatus(id, { signal: ctl.signal })
      .then((s) => setOffer(Boolean(s?.available && s?.needed)))
      .catch(() => setOffer(false));          // no offer is the safe answer to any failure
    return () => ctl.abort();
  }, [id]);

  if (done) {
    // the project as it stands after the read (lib/freeReread.freeRereadState) — never a count of what this one
    // run added, which read „0" for walls an earlier read had already taken from the dimensions; only the parts
    // with something in them are said (freeRereadDoneText)
    return (
      <div className={`rounded-[2px] border border-[hsl(var(--accent-2)/0.35)] bg-[hsl(var(--accent-2)/0.06)] px-3 py-2 text-[14px] ${className}`} role="status" data-testid="free-reread-done">
        {freeRereadDoneText(done, t)}
      </div>
    );
  }
  if (!offer) return null;

  const later = () => {
    try { sessionStorage.setItem(dismissedKey(id), '1'); } catch { /* private window */ }
    setOffer(false);
  };

  const run = async () => {
    if (busy) return;
    setBusy(true);
    try {
      const base = getProject(id) || project;
      const { project: merged } = await runFreeReread(base);
      updateProject(id, merged);
      await flushProjectSaves();
      recordPilot(id, 'free_reread', { kind: 'reread', id: String((merged._reread_diff?.changed || []).length) });
      setDone(freeRereadState(merged));
      setOffer(false);
      onComplete?.(merged);
    } catch (err) {
      console.error('[freeReread] failed:', err);
      toast.error(err?.status === 409 ? t('project.freeReread.alreadyRunning')
        : err?.code === 'lane_failed' ? t('project.freeReread.nothingRead')
          : t('project.freeReread.failed', { msg: err?.message || '' }));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      className={`rounded-[2px] border border-[hsl(var(--accent-2)/0.35)] bg-[hsl(var(--accent-2)/0.06)] px-3 py-3 ${className}`}
      data-testid="free-reread-banner"
    >
      <div className="flex flex-wrap items-start gap-3">
        <ScanLine className="mt-0.5 h-5 w-5 shrink-0 text-[hsl(var(--accent-2))]" aria-hidden="true" />
        <div className="min-w-0 flex-1">
          <p className="text-[15px] font-semibold text-foreground">{t('project.freeReread.title')}</p>
          <p className="mt-0.5 max-w-[80ch] text-[14px] leading-snug text-[hsl(var(--ink-2))]">{t('project.freeReread.body')}</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            disabled={busy}
            onClick={run}
            className="inline-flex min-h-[44px] items-center gap-2 rounded-[2px] bg-[hsl(var(--accent-2))] px-4 text-[15px] font-semibold text-white hover:opacity-95 disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {busy && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
            {busy ? t('project.freeReread.running') : t('project.freeReread.cta')}
          </button>
          {!busy && (
            <button
              type="button"
              onClick={later}
              aria-label={t('project.freeReread.later')}
              title={t('project.freeReread.later')}
              className="inline-flex h-11 w-11 items-center justify-center rounded-[2px] text-muted-foreground hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <X className="h-4 w-4" aria-hidden="true" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
