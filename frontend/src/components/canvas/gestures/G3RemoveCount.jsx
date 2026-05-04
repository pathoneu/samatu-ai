// frontend/src/components/canvas/gestures/G3RemoveCount.jsx
/**
 * Sprint 2 G3 — click-to-remove count.
 *
 * Decrements the selected pozicija's kiekis by 1. Click target should be
 * an existing dot but for Sprint 2 we just decrement without dot-matching;
 * Sprint 3 adds nearest-dot detection so the visual dot also disappears.
 *
 * Spec §5.4 G3 row.
 */
import { useCallback } from 'react';
import { useStore } from 'zustand';
import { viewerStore } from '../../../lib/viewerStore';
import { removeSymbol } from '../../../lib/gestureApi';
import { abortRegistry } from '../../../lib/abortRegistry';

export function useG3Handler({ rooms, pozicijos, currentAssumptions,
                               onRecomputed, onGestureEvent }) {
  const tool = useStore(viewerStore, (s) => s.currentTool);
  const selection = useStore(viewerStore, (s) => s.selection);

  return useCallback(async (_e) => {
    if (tool !== 'g3') return false;
    if (selection?.kind !== 'pozicija') {
      alert('Pasirink poziciją KŽ panelėje, tada spausk tašką brėžinyje.');
      return true;
    }
    const startedAt = Date.now();
    try {
      const signal = abortRegistry.takeSignal('g3');
      const result = await removeSymbol({
        rooms, pozicijos, currentAssumptions,
        targetPozicijaId: selection.id, signal,
      });
      onRecomputed?.(result);
      onGestureEvent?.({
        type: 'G3', target: { kind: 'pozicija', id: selection.id },
        outcome: 'success', duration_ms: Date.now() - startedAt,
      });
    } catch (err) {
      if (err.name === 'AbortError') return true;
      console.error('[G3] remove_symbol failed:', err);
      onGestureEvent?.({
        type: 'G3', target: { kind: 'pozicija', id: selection.id },
        outcome: 'error', duration_ms: Date.now() - startedAt,
      });
      alert(err.envelope?.user_message || `G3 nepavyko: ${err.message}`);
    }
    return true;
  }, [tool, selection, rooms, pozicijos, currentAssumptions,
      onRecomputed, onGestureEvent]);
}
