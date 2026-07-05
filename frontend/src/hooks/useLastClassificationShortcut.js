import { useEffect } from 'react';

/**
 * auto-count-style `L` shortcut (Week 5 Task 5.2 — R3 implementation pattern).
 *
 * Press `L` outside an input/textarea to re-arm the last-used classification
 * tool. 1 keystroke instead of toolbar hunt — auto-count tools's most-loved muscle-
 * memory feature.
 *
 * The hook does NOT own state — caller passes lastClassification + onArm.
 * That keeps the shortcut composable across SymbolCounter, QuantityTable, etc.
 */
export function useLastClassificationShortcut({ lastClassification, onArm }) {
  useEffect(() => {
    function handler(e) {
      if (!e?.key) return;
      if (e.key.toLowerCase() !== 'l') return;
      const target = e.target;
      const tag = target?.tagName ?? '';
      if (tag === 'INPUT' || tag === 'TEXTAREA') return;
      if (target?.isContentEditable) return;
      if (!lastClassification) return;
      onArm(lastClassification);
    }
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [lastClassification, onArm]);
}

export default useLastClassificationShortcut;
