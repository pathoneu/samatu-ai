/**
 * useHeldReread — on project open, pick up a paid re-read the page lost.
 *
 * The re-read card remembers its run id per project (lib/heldReread.js). If
 * the page was reloaded or closed while it waited, the server finished the
 * reading and HOLDS it on the run's job row for three days — and before this
 * hook nothing ever merged it. Now the project page asks for that run when it
 * opens (lib/heldReread.settleHeldReread, where the flow is unit-tested):
 *   • done with a held read → merged through the card's own path
 *     (lib/rereadApply.applyRereadResult), once;
 *   • still running → waits (one GET every 10 s while the page is open), and
 *     the card in Nustatymai shows the running read instead of offering a
 *     second paid one;
 *   • interrupted / failed / lost → says so, and forgets the run — only while
 *     the page is still there to say it; a page already left keeps the run,
 *     and the next open tells it. Done with nothing held is told only after a
 *     grace, if no other tab merged it (lib/heldReread.lostRunUnhandled);
 *   • not this user's run, or already merged → forgets it silently.
 */

import { useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { fetchExtractionJob, waitForExtraction, runEndText } from '@/lib/extractionRun';
import {
  recallRereadRun, settleHeldReread, rereadInFlight, trackReread,
} from '@/lib/heldReread';
import { applyRereadResult } from '@/lib/rereadApply';
import { getProject } from '@/lib/projectStore';

/**
 * @param {string|undefined} projectId
 * @param {(merged: object) => void} onApplied  the page's state setter
 */
export default function useHeldReread(projectId, onApplied) {
  const { t } = useTranslation();
  const onAppliedRef = useRef(onApplied);
  const tRef = useRef(t);
  useEffect(() => { onAppliedRef.current = onApplied; tRef.current = t; });

  useEffect(() => {
    if (!projectId) return undefined;
    let gone = false;
    const say = (key) => tRef.current(key);
    const toastId = `held-reread-${projectId}`;
    const readAtOpen = getProject(projectId)?._reextracted_at;

    // Resolves to `{error}` like the card's own read: the card shows the
    // ending of a read it did not start (components/project/ReextractButton.jsx).
    const settle = async (runId) => {
      const { told, cause } = await settleHeldReread(projectId, runId, {
        getProject,
        fetchJob: fetchExtractionJob,
        wait: (id, { isCancelled }) => waitForExtraction(id, { kind: 'reread', isCancelled }),
        apply: applyRereadResult,
        isGone: () => gone,
        onWaiting: () => toast.info(say('project.reextract.heldWaiting'), { id: toastId }),
        onApplied: (project, { merged }) => {
          onAppliedRef.current?.(project);
          if (merged) toast.success(say('project.reextract.heldApplied'), { id: toastId });
        },
      });
      if (told === 'merge') {
        console.error('[held re-read] merging the held read failed:', cause);
        const msg = say('project.reextract.errFailed');
        if (!gone) toast.error(msg, { id: toastId });
        return { error: msg };
      }
      if (told) {
        const msg = say(runEndText('reread', told));
        toast.warning(msg, { id: toastId, duration: 12000 });
        return { error: msg };
      }
      return { error: null };
    };

    const look = () => {
      if (gone) return;
      const running = rereadInFlight(projectId);
      if (running) {
        // A read already running on this page load — the card's own, or this
        // hook's from before the page was left and reopened — owns its ending.
        // When it ends: show what it saved (this page mounted before the
        // merge), then look again (a wait the page left keeps its run).
        running.then(() => {
          if (gone) return;
          const p = getProject(projectId);
          if (p && p._reextracted_at !== readAtOpen) onAppliedRef.current?.(p);
          look();
        });
        return;
      }
      const runId = recallRereadRun(projectId);
      if (!runId) return;
      trackReread(projectId, settle(runId).catch((e) => {
        console.warn('[held re-read] check failed:', e);
        return { error: null };
      }));
    };
    look();
    return () => { gone = true; };
  }, [projectId]);
}
