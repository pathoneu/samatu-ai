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
 *
 * v3 W1-C: drawn by the one Notice (info tone) like every other notice of the workspace.
 * B1-D: one line with one button — the five-line paragraph pushed the Sąmata rows and the room list below the
 * fold; what stays of it is the promise that his corrections and prices are kept.
 * B2-B: one line at 340 px — „Tiksliau, nemokamai" + [icon] „Perskaityti" + ✕; the promise is the button's title.
 */

import { useEffect, useState } from 'react';
import { useTranslation } from '@/i18n/react';
import { Loader2, ScanLine } from 'lucide-react';
import { toast } from 'sonner';

import Notice from '@/components/ui/Notice';
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
      <Notice tone="info" icon={ScanLine} className={className} data-testid="free-reread-done">
        <p>{freeRereadDoneText(done, t)}</p>
      </Notice>
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
      updateProject(id, merged, { versionSource: 'perskaityta' });
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
    <Notice
      compact
      oneLine
      tone="info"
      icon={false}
      className={`w-full ${className}`}
      title={t('project.freeReread.titleLine')}
      onDismiss={busy ? null : later}
      dismissLabel={t('project.freeReread.later')}
      data-testid="free-reread-banner"
      action={(
        <button
          type="button"
          disabled={busy}
          onClick={run}
          title={t('project.freeReread.ctaTitle')}
          className="inline-flex min-h-[36px] shrink-0 items-center gap-1.5 rounded-[2px] bg-accent-2 px-2 text-ui font-semibold text-white hover:opacity-95 disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          {busy ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : <ScanLine className="h-4 w-4" aria-hidden="true" />}
          {busy ? t('project.freeReread.running') : t('project.freeReread.ctaShort')}
        </button>
      )}
    />
  );
}
