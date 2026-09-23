/**
 * useProjectFixes — the ONE way a fix made in Patikra lands on the project.
 *
 * Extracted from pages/RoomSheet.jsx (2026-09-21) when the question list became the second screen that fixes
 * facts: both go through the same landing, so there is one place where a recompute result is merged into the
 * project — `mergeDarbuSarasasEdits`, the only thing standing between an edit and a pile of deleted priced
 * rows — one consequence („what moved in the sąmata") and one undo.
 *
 *  • `run(work)`      — one save at a time, errors as a toast;
 *  • `land(result, …)` — merge a recompute result, persist, say what moved: under a fact/question
 *                        (`factKey` → `lastFix`, with the way back) or as a plain ripple line;
 *  • `undoLastFix()`  — the project goes back to EXACTLY what it was before the last fix: the stored
 *                        object, not a recomputation of it (lib/roomSheet.undoPatch).
 *
 * `afterLand` re-reads whatever the screen shows (the room's facts, the question list). The server computes
 * those from the STORED blob and `updateProject` writes on a debounce, so the save is flushed first —
 * refetching straight away raced the write and redrew the card with the pre-edit numbers (measured in the
 * browser, 2026-09-13).
 */

import { useCallback, useState } from 'react';
import { toast } from 'sonner';

import { flushProjectSaves, updateProject } from '@/lib/projectStore';
import { mergeDarbuSarasasEdits } from '@/lib/mergeDarbuSarasas';
import { diffDarbuSarasas } from '@/lib/takeoffWorkflow';
import { consequenceOf, rippleText, undoPatch } from '@/lib/roomSheet';

export function useProjectFixes({ project, setProject, t, afterLand, onUndo = null }) {
  const [busy, setBusy] = useState(false);
  const [ripple, setRipple] = useState(null);
  // The last fix: which fact (or question), what it moved in the sąmata, and the project as it was before.
  const [lastFix, setLastFix] = useState(null);

  const run = useCallback(async (work) => {
    if (busy) return;
    setBusy(true);
    try {
      await work();
    } catch (err) {
      console.error('[patikra] save failed:', err);
      toast.error(t('project.roomSheet.saveError', { msg: err.message }));
    } finally {
      setBusy(false);
    }
  }, [busy, t]);

  /**
   * Land a recompute result on the project. Mirrors InteriorProject's own merge, with one addition:
   * `/api/recompute-quantities` returns the rebuilt rooms under `rooms` only, so they are written to BOTH
   * `patalpos` and `v8_rooms`. Writing one and not the other would leave the walk (which reads `v8_rooms`
   * first) showing the pre-edit room forever.
   */
  const land = useCallback((result, {
    fromInterior = false, scopeChange = false, factKey = null, sameValue = false, summary = null,
  } = {}) => {
    const prior = project?.darbu_sarasas || [];
    const notes = [];
    const rebuilt = result.rooms || result.v8_rooms || result.patalpos;
    const next = fromInterior
      ? {
        ...project,
        ...result,
        name: project.name,
        company_name: project.company_name,
        vat_rate: project.vat_rate,
        // a scope choice removes rows on purpose — do not carry them back as orphans
        darbu_sarasas: mergeDarbuSarasasEdits(result.darbu_sarasas, prior, notes, undefined, { scopeChange }),
      }
      : {
        ...project,
        patalpos: rebuilt || project.patalpos,
        v8_rooms: rebuilt || project.v8_rooms,
        pozicijos: result.pozicijos || project.pozicijos,
        // `scopeChange` here too (2026-09-23): an answer that takes a row away on purpose — „vidaus durys
        // su apvadais" removes the frameless-door row — must not see it carried back as an orphan
        darbu_sarasas: mergeDarbuSarasasEdits(
          result.darbu_sarasas, prior, notes,
          (result._merge_notes || []).filter((n) => n.reason === 'relabeled'), { scopeChange }),
        _overrides: { ...(project._overrides || {}), ...(result.assumptions || {}) },
      };
    setProject(next);
    updateProject(project.id, next);
    const diff = diffDarbuSarasas(prior, next.darbu_sarasas || []);
    if (factKey) {
      // a FACT was fixed: what it moved is shown under that fact, with the way back
      setLastFix({ factKey, consequence: consequenceOf(diff, 3, { sameValue }), prevProject: project, summary });
      setRipple(null);
    } else {
      setLastFix(null);
      setRipple(rippleText(diff, t));
    }
    return flushProjectSaves().then(afterLand, afterLand);
  }, [project, setProject, t, afterLand]);

  const undoLastFix = useCallback(() => run(async () => {
    if (!lastFix?.prevProject) return;
    onUndo?.(lastFix);
    const back = undoPatch(lastFix.prevProject, project);
    const restored = { ...project, ...back };
    Object.keys(back).forEach((k) => { if (back[k] === null) delete restored[k]; });
    setProject(restored);
    updateProject(project.id, back);
    setLastFix(null);
    setRipple(null);
    await flushProjectSaves().then(afterLand, afterLand);
    toast.success(t('project.roomSheet.fixUndone'));
  }), [run, lastFix, project, setProject, afterLand, onUndo, t]);

  return { busy, run, land, undoLastFix, lastFix, setLastFix, ripple, setRipple };
}
