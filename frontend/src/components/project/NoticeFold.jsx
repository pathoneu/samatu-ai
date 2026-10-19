/**
 * NoticeFold — Patikra's notices behind one „Pranešimai (N)" line (Pathon v3 W6-A; why: lib/noticeFold.js).
 *
 * The notices stay mounted (each decides for itself whether it shows, and keeps its state); the fold only
 * counts the ones that rendered and hides them until the line is opened. One notice shows as it is. The line
 * names every notice it folds — nothing disappears without a word.
 */
import { useLayoutEffect, useRef, useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { foldLabel, shouldFold } from '@/lib/noticeFold';

const presentIds = (el) => (el ? [...el.children].map((c) => c.getAttribute('data-testid') || '') : []);

export default function NoticeFold({ children, className = '' }) {
  const box = useRef(null);
  const [ids, setIds] = useState([]);
  const [open, setOpen] = useState(false);

  useLayoutEffect(() => {
    const el = box.current;
    if (!el) return undefined;
    const sync = () => {
      const next = presentIds(el);
      setIds((prev) => (prev.join('|') === next.join('|') ? prev : next));
    };
    sync();
    const mo = new MutationObserver(sync);
    mo.observe(el, { childList: true });
    return () => mo.disconnect();
  }, []);

  const fold = shouldFold(ids.length);
  const { title, names } = foldLabel(ids);
  const Chevron = open ? ChevronDown : ChevronRight;
  return (
    <>
      {fold && (
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
          data-testid="notice-fold"
          className={`flex min-h-[44px] flex-wrap items-center gap-x-2 gap-y-0.5 rounded-[2px] border border-border bg-card px-3 py-2 text-left leading-snug text-ui text-foreground hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${className}`}
        >
          <Chevron className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
          <span className="font-semibold">{title}</span>
          {names && <span className="min-w-0 flex-1 text-muted-foreground">{names}</span>}
        </button>
      )}
      <div ref={box} className={fold && !open ? 'hidden' : 'contents'} data-testid="notice-fold-body">
        {children}
      </div>
    </>
  );
}
