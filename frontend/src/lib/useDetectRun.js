/**
 * useDetectRun — one „Perskaityti lapą" run for one project: start, follow the
 * stages, land the result, report in numbers. The viewer stays usable the
 * whole time: nothing here blocks, and the result lands on the project AS IT
 * STANDS when the read finishes (getProject), so an edit made meanwhile goes
 * through the re-read's merge rules like any other (lib/mergeReextract.js).
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { toast } from 'sonner';

import { fetchDetectRun, startDetectRun } from '@/lib/detectRunApi';
import { landFreeRereadResult } from '@/lib/freeRereadApi';
import { flushProjectSaves, getProject, updateProject } from '@/lib/projectStore';
import { appliedTo, needsPolling, requestBody, scopeCounts, summaryText, viewOf } from '@/lib/detectRun';

const POLL_MS = 400;

export function useDetectRun(project, onProjectChange) {
  const id = project?.id;
  const [run, setRun] = useState(null);         // { pages, features, snapshot, client }
  const alive = useRef(true);
  const timer = useRef(null);
  const latest = useRef({ project, onProjectChange });
  latest.current = { project, onProjectChange };

  useEffect(() => () => { alive.current = false; clearTimeout(timer.current); }, []);

  const land = useCallback(async (snapshot, pages, features) => {
    setRun((r) => r && { ...r, snapshot, client: { status: 'running', note: 'Perskaičiuojami kiekiai…' } });
    try {
      const base = getProject(id) || latest.current.project;
      const { project: merged } = await landFreeRereadResult(base, snapshot.result);
      // the whole drawing read again → „perskaityta“; one sheet's landing → „lapas“ (Istorija)
      updateProject(id, merged, { versionSource: pages === 'all' ? 'perskaityta' : 'lapas' });
      await flushProjectSaves();
      latest.current.onProjectChange?.(merged);
      const note = summaryText(scopeCounts(merged, snapshot.result?.taikymas?.patalpos), features);
      if (alive.current) setRun((r) => r && { ...r, client: { status: 'done', note } });
      const where = pages === 'all' ? '' : `, pritaikyta ${appliedTo(pages, merged?._meta?.geometrija?.grupes)}`;
      toast.success(`Perskaitytas visas brėžinys${where}: ${note}`);
    } catch (err) {
      console.error('[detectRun] landing failed:', err);
      const note = err?.code === 'lane_failed'
        ? 'Brėžinys perskaitytas, bet patalpų nėra — projektas nepakeistas.'
        : 'Kiekių perskaičiuoti nepavyko — projektas nepakeistas. Bandykite dar kartą.';
      if (alive.current) setRun((r) => r && { ...r, client: { status: 'failed', note } });
      toast.error(`Kiekiai: ${note}`);
    }
  }, [id]);

  const follow = useCallback((jobId, pages, features) => {
    const tick = async () => {
      if (!alive.current) return;
      let snapshot;
      try {
        snapshot = await fetchDetectRun(id, jobId);
      } catch (err) {
        console.error('[detectRun] status failed:', err);
        setRun((r) => r && { ...r, lost: err?.message || 'ryšys nutrūko' });
        toast.error(`Skaitymo eigos gauti nepavyko: ${err?.message || 'ryšys nutrūko'}`);
        return;
      }
      if (!alive.current) return;
      setRun((r) => r && { ...r, snapshot });
      if (needsPolling(snapshot)) {
        timer.current = setTimeout(tick, POLL_MS);
      } else if (snapshot.result_ready) {
        land(snapshot, pages, features);
      } else if (snapshot.failed) {
        const v = viewOf(snapshot);
        toast.error(`${v.failedStage?.label || 'Skaitymas'}: ${v.failedStage?.note || 'nepavyko'}`);
      }
    };
    timer.current = setTimeout(tick, POLL_MS);
  }, [id, land]);

  const start = useCallback(async (pages, features) => {
    if (!id) return;
    clearTimeout(timer.current);
    setRun({ pages, features, snapshot: null, client: null });
    try {
      await flushProjectSaves();          // the server reads the stored project: his last edit must be there
      const snapshot = await startDetectRun(id, requestBody(pages, features));
      if (!alive.current) return;
      setRun({ pages, features, snapshot, client: null });
      follow(snapshot.job, pages, features);
    } catch (err) {
      console.error('[detectRun] start failed:', err);
      const msg = err?.status === 409 ? 'Šis projektas jau skaitomas — palaukite, kol baigs.'
        : err?.status === 404 ? (err.message || 'Brėžinio saugykloje nėra.')
          : `Pradėti nepavyko: ${err?.message || ''}`;
      setRun({ pages, features, snapshot: null, client: null, startError: msg });
      toast.error(msg);
    }
  }, [id, follow]);

  const dismiss = useCallback(() => { clearTimeout(timer.current); setRun(null); }, []);

  const view = run && (run.snapshot || !run.startError) ? viewOf(run.snapshot, run.client) : null;
  const busy = Boolean(run && !run.startError && !run.lost && !(view && view.terminal));
  return { run, view, busy, start, dismiss };
}
