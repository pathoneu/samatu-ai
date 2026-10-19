/**
 * useChromeCompact — measures the viewer's top-right row (its first child = the sheet pill, its last = the
 * buttons' card) and says when the buttons go icon-only (lib/chromeCompact). Returns [callback ref, compact].
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { nextChromeCompact, pillNaturalWidth } from '@/lib/chromeCompact';

export default function useChromeCompact() {
  const [el, setEl] = useState(null);
  const stateRef = useRef({ compact: false, fullWidth: null });
  const [compact, setCompact] = useState(false);
  const ref = useCallback((node) => setEl(node), []);
  useEffect(() => {
    if (!el || typeof ResizeObserver === 'undefined') return undefined;
    const check = () => {
      const kids = [...el.children];
      if (kids.length < 2) return;
      const pill = kids[0]; const card = kids[kids.length - 1];
      const name = pill.querySelector('[data-testid="sheet-name"]');
      const next = nextChromeCompact(stateRef.current, {
        rowWidth: el.clientWidth,
        pillNatural: pillNaturalWidth(pill.offsetWidth, name?.scrollWidth, name?.clientWidth),
        cardWidth: card.offsetWidth,
      });
      if (next !== stateRef.current) {
        stateRef.current = next;
        setCompact(next.compact);
      }
    };
    const ro = new ResizeObserver(check);
    ro.observe(el);
    for (const k of el.children) ro.observe(k);
    check();
    return () => ro.disconnect();
  }, [el]);
  return [ref, compact];
}
