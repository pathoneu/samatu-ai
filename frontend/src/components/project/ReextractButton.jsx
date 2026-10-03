/**
 * ReextractButton — reads the saved PDF again from scratch (Limitation 10 fix).
 *
 * Use cases:
 * - Prompt was improved since original extraction (admin updates → user wants fresh result)
 * - Original extraction had errors / missing rooms
 * - Switching rules_override drastically (full re-extract vs cheap recompute)
 *
 * Flow: confirm → load PDF blob from IndexedDB → the free preflight (time
 * estimate) → POST /extract-interior-stream with `reread_of` → MERGE the fresh
 * read into the stored project (lib/mergeReextract.js: verified rooms and the
 * facts he set himself stay, prices ride on the rebuilt rows, the diff is
 * recorded) → rebuild the rows on the merged rooms through the same
 * /recompute-interior path a room edit uses → save. The diff shows up as
 * `RereadDiffBanner` on the project page until he dismisses it.
 *
 * THE STREAM, NOT THE BLOCKING CALL (2026-10-03, audit frontend-architecture-4).
 * This used to POST the blocking /extract-interior with a 600 s client timeout,
 * while real reads take 13–27 min — and Railway's edge cuts any request at
 * 900 s anyway. It now runs through lib/extractionRun.js, the same stream,
 * edge hand-off and wait a new project uses. If the connection goes, the
 * server finishes the read and HOLDS it on the run's record (a re-read is never
 * a second project); the wait takes it from there and merges it here exactly
 * as a read that arrived over the stream. A read the server reports stopped
 * (restart, failure) leaves the project untouched and says so.
 */

import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { RefreshCw, Loader2, AlertCircle, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { getPdfBlob } from '@/lib/pdfStore';
import { getProject, updateProject } from '@/lib/projectStore';
import { mergeReextract } from '@/lib/mergeReextract';
import { mergeDarbuSarasasEdits } from '@/lib/mergeDarbuSarasas';
import { saveRoomEdit } from '@/lib/roomSheetApi';
import { recordPilot } from '@/lib/telemetry';
import { fetchPreflight, pollLimitMs } from '@/lib/preflight';
import {
  runExtraction, runEndText, ExtractionStopped, reduceStreamProgress, progressLine,
} from '@/lib/extractionRun';

// The preflight is a convenience (an estimate on screen, a wait sized to the
// file): it never holds the paid read back for more than this.
const PREFLIGHT_WAIT_MS = 20_000;

// Re-reads in flight on this page load, per project id → Promise<{error}>.
// The button lives inside the Prielaidos panel; closing and reopening the
// panel mid-read mounts a fresh button, which must show the read that is
// running instead of offering a second paid one.
const inflight = new Map();

/**
 * The stored project after a fresh read: merged, then its rows rebuilt on the
 * merged rooms (the fresh read built them on its own rooms — without the facts
 * he set, without the project's scope). If the rebuild fails, the merged
 * project is still a complete, honest state: fresh rows with his prices.
 */
export async function projectAfterReread(base, result) {
  const { project: merged } = mergeReextract(base, result);
  try {
    const re = await saveRoomEdit(merged, merged.patalpos);
    const notes = [];
    return {
      ...merged,
      ...re,
      name: base.name,
      company_name: base.company_name,
      vat_rate: base.vat_rate,
      _overrides: merged._overrides,
      _apimtis: merged._apimtis,
      _per_room_overrides: merged._per_room_overrides,
      _reextracted_at: merged._reextracted_at,
      _reread_diff: merged._reread_diff,
      darbu_sarasas: mergeDarbuSarasasEdits(re.darbu_sarasas, base.darbu_sarasas, notes),
    };
  } catch (e) {
    console.warn('[reextract] rebuilding rows on the merged rooms failed — keeping the merged read:', e);
    return merged;
  }
}

/** The preflight of the stored PDF, or null after PREFLIGHT_WAIT_MS. */
async function quickPreflight(blob, name) {
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), PREFLIGHT_WAIT_MS);
  try {
    const file = new File([blob], `${name || 'brezinys'}.pdf`, { type: 'application/pdf' });
    return await fetchPreflight(file, { signal: ctl.signal });
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}

export default function ReextractButton({ project, onComplete }) {
  // This component carried a complete set of i18n keys that nothing used: the
  // strings were hard-coded LT, so no vocabulary pass could reach them.
  const { t } = useTranslation();
  const [confirming, setConfirming] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const [progress, setProgress] = useState('');
  const [elapsed, setElapsed] = useState(null);
  const [estimate, setEstimate] = useState('');
  const [error, setError] = useState(null);

  // A read already running for this project (started before this button was
  // mounted): show it, and its ending, instead of the start button.
  useEffect(() => {
    const running = inflight.get(project.id);
    if (!running) return undefined;
    let live = true;
    setExtracting(true);
    running.then(({ error: err }) => {
      if (!live) return;
      setExtracting(false);
      if (err) { setConfirming(true); setError(err); }
    });
    return () => { live = false; };
  }, [project.id]);

  const endMessage = (why) => {
    const { key, defaultValue } = runEndText('reread', why);
    return defaultValue ? t(key, { defaultValue }) : t(key);
  };

  const readAgain = async () => {
    const t0 = Date.now();
    const clock = setInterval(() => setElapsed(Math.floor((Date.now() - t0) / 1000)), 1000);
    try {
      setProgress(t('project.reextract.loadingPdf'));
      const blob = await getPdfBlob(project.id);
      if (!blob) {
        throw new Error(t('project.reextract.pdfNotFound'));
      }

      // The free five-second look at the same PDF: its estimate replaces a
      // hard-coded range, and its page tier sizes the wait after a hand-off.
      setProgress(t('newProject.preflight.checking'));
      const pre = await quickPreflight(blob, project.name);
      if (pre?.est_minutes) setEstimate(pre.est_minutes);

      const fd = new FormData();
      fd.append('files', blob, project.name + '.pdf');
      // Forward existing rules_override so user's prefs aren't lost. Read them
      // from the STORE, not the render-time prop — a Prielaidos edit that
      // didn't re-render this button would otherwise re-extract under the old
      // assumptions.
      const overrides = (getProject(project.id) || project)._overrides;
      if (overrides) {
        fd.append('rules_override', JSON.stringify(overrides));
      }
      // The server checks it is his, and if the connection goes it holds the
      // read for this project instead of saving a second one.
      fd.append('reread_of', project.id);

      let step = null;
      setProgress(t(...progressLine(step)));
      const run = await runExtraction(fd, {
        kind: 'reread',
        onEvent: (ev) => {
          step = reduceStreamProgress(step, ev);
          setProgress(t(...progressLine(step)));
        },
        onHandoff: () => setProgress(t(...progressLine({ step: 'finishing' }))),
        waitLimitMs: pollLimitMs(pre),
      });

      // The stream's own result, or the read the server held after the
      // connection went — merged the same way either way.
      const result = (run.status === 'done' || run.status === 'recovered') ? run.result : null;
      if (!result) return { error: endMessage(run.status) };
      if (result.status === 'error') {
        throw new Error(result._error || t('project.reextract.pipelineErr'));
      }
      if (!result.patalpos) {
        throw new Error(t('project.reextract.badFormat'));
      }

      // 2026-07-28 audit: the base of the merge used to be the `project`
      // PROP — a render-time snapshot taken up to 10 minutes before the
      // extraction returned. Everything the user changed while it ran
      // (prices, measurements, polygons, per-room overrides, the name) was
      // silently rolled back to that snapshot. Re-read the CURRENT stored
      // project first; same idiom as InteriorWorkspace.jsx.
      //
      // 2026-09-13: no longer a wholesale replace — see projectAfterReread.
      setProgress(t('project.reextract.rebuilding'));
      const base = getProject(project.id) || project;
      const merged = await projectAfterReread(base, result);
      recordPilot(project.id, 'reread', { kind: 'reread', id: String((merged._reread_diff?.changed || []).length) });
      updateProject(project.id, merged);
      setProgress(t('project.reextract.updated'));
      setTimeout(() => {
        onComplete?.(merged);
        setExtracting(false);
        setConfirming(false);
      }, 800);
      return { error: null };
    } catch (e) {
      console.error('Re-extract failed:', e);
      if (e instanceof ExtractionStopped) return { error: endMessage(e.reason) };
      return { error: e.message || t('project.reextract.error') };
    } finally {
      clearInterval(clock);
    }
  };

  const handleReextract = async () => {
    if (inflight.has(project.id)) return;
    setError(null);
    setEstimate('');
    setElapsed(null);
    setExtracting(true);
    const running = readAgain();
    inflight.set(project.id, running);
    try {
      const { error: err } = await running;
      if (err) {
        setError(err);
        setExtracting(false);
      }
    } finally {
      inflight.delete(project.id);
    }
  };

  if (extracting) {
    return (
      <div className="border border-primary/30 bg-primary/5 rounded-lg p-3 flex items-center gap-3 min-w-[280px]">
        <Loader2 className="w-4 h-4 animate-spin text-primary shrink-0" />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium">{t('project.reextract.inProgress')}</p>
          {progress && <p className="text-xs text-muted-foreground truncate">{progress}</p>}
          {/* Elapsed + the honest horizon, as on the new-project screen:
              „praėjo 6 min · numatyta apie iki 30 min", never a countdown. */}
          {elapsed != null && (
            <p className="text-xs text-muted-foreground tabular-nums">
              {t('upload.stream.elapsedMin', { min: Math.floor(elapsed / 60), sec: elapsed % 60 })}
              {estimate && <> · {t('upload.stream.estimate', { value: estimate })}</>}
            </p>
          )}
        </div>
      </div>
    );
  }

  if (!confirming) {
    return (
      <Button
        variant="outline"
        size="sm"
        onClick={() => setConfirming(true)}
        title={t('project.reextract.buttonTitle')}
      >
        <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
        {t('project.reextract.button')}
      </Button>
    );
  }

  return (
    <div className="border border-amber-300 bg-amber-50 dark:bg-amber-950/20 dark:border-amber-900/40 rounded-lg p-3 max-w-md">
      <div className="flex items-start gap-2">
        <AlertCircle className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-amber-900 dark:text-amber-200">
            {t('project.reextract.confirmTitle')}
          </p>
          <ul className="text-xs text-amber-800 dark:text-amber-300/80 mt-1 mb-3 space-y-0.5 list-disc pl-4">
            <li>{t('project.reextract.bullet1')}</li>
            <li>{t('project.reextract.bullet2')}</li>
            <li>{t('project.reextract.bullet3')}</li>
            <li>{t('project.reextract.bullet5')}</li>
            <li>{t('project.reextract.bullet4', { count: Object.keys(project._overrides || {}).length })}</li>
          </ul>
          <div className="flex gap-2">
            <Button size="sm" onClick={handleReextract}>{t('project.reextract.yesRepeat')}</Button>
            <Button size="sm" variant="ghost" onClick={() => setConfirming(false)}>
              <X className="w-3.5 h-3.5" />
            </Button>
          </div>
          {error && (
            <p className="text-xs text-destructive mt-2">{error}</p>
          )}
        </div>
      </div>
    </div>
  );
}
