/**
 * NoticeFold — stacked notices behind one „Pranešimai (N)" line (Pathon v3 W6-A for Patikra; B1-D also above the
 * right panel on Brėžinys and Sąmata and on Siųsti — why: lib/noticeFold.js).
 *
 * The notices stay mounted (each decides for itself whether it shows, and keeps its state); the fold only
 * counts the ones that rendered and hides them until the line is opened. One notice shows as it is. The line
 * names every notice it folds — nothing disappears without a word.
 *
 * 2026-10-25 (walk on objektas_i): the free re-read offer sat folded and unreachable. A LEAD notice (the offer, or
 * after the read its done line — lib/noticeFold LEAD_NOTICES) stays on screen while the fold is closed and carries
 * the fold's control in its own line (`NoticeFoldMore`), so there is still one notice line, never two stacked.
 */
import { useLayoutEffect, useMemo, useRef, useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { foldLabel, leadNotice, opensOnArrival, shouldFold } from '@/lib/noticeFold';
import { NoticeFoldContext, useNoticeFold } from './noticeFoldContext';

// A notice may sit in a spacing wrapper (ServerRefreshNotice, RereadDiffBanner's chip): its name is the first
// test id inside it.
const noticeId = (c) => c.getAttribute('data-testid') || c.querySelector('[data-testid]')?.getAttribute('data-testid') || '';
const presentIds = (el) => (el ? [...el.children].map(noticeId) : []);

export default function NoticeFold({ children, className = '' }) {
  const box = useRef(null);
  const [ids, setIds] = useState([]);
  const [open, setOpen] = useState(false);

  useLayoutEffect(() => {
    const el = box.current;
    if (!el) return undefined;
    let seen = null;   // null until the first look: what is there on load never opens the fold
    const sync = () => {
      const next = presentIds(el);
      const stamped = [...el.children].map((c, i) => {
        const stamp = c.getAttribute('data-notice-stamp') || c.querySelector('[data-notice-stamp]')?.getAttribute('data-notice-stamp');
        return stamp ? `${next[i]}@${stamp}` : next[i];
      });
      if (opensOnArrival(seen, stamped)) setOpen(true);
      seen = stamped;
      setIds((prev) => (prev.join('|') === next.join('|') ? prev : next));
    };
    sync();
    const mo = new MutationObserver(sync);
    mo.observe(el, { childList: true, subtree: true, attributes: true, attributeFilter: ['data-notice-stamp'] });
    return () => mo.disconnect();
  }, []);

  const fold = shouldFold(ids.length);
  // The free re-read offer (or its done line) stays on screen while the fold is closed (lib/noticeFold
  // LEAD_NOTICES) and carries the fold's control inside its own line (NoticeFoldMore) — no second line under it.
  const lead = fold ? leadNotice(ids) : null;
  const { title, names } = foldLabel(ids);
  const Chevron = open ? ChevronDown : ChevronRight;

  // mark the lead's element so the closed fold can show it alone (index.css `.notice-fold-lead-only`)
  useLayoutEffect(() => {
    const el = box.current;
    if (!el) return;
    for (const c of el.children) {
      if (lead && noticeId(c) === lead) c.setAttribute('data-fold-lead', '');
      else c.removeAttribute('data-fold-lead');
    }
  }, [lead, ids]);

  const ctx = useMemo(() => {
    if (!lead) return null;
    const rest = foldLabel(ids, lead);
    return { lead, open, title: rest.title, names: rest.names, openFold: () => setOpen(true) };
  }, [lead, ids, open]);

  // the „Pranešimai (N)" line: always when folded without a lead; with a lead only once opened (to fold again)
  const line = fold && (!lead || open) && (
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
  );
  let bodyClass = 'contents';
  if (fold && !open) bodyClass = lead ? 'contents notice-fold-lead-only' : 'hidden';
  return (
    <NoticeFoldContext.Provider value={ctx}>
      {line}
      <div ref={box} className={bodyClass} data-testid="notice-fold-body">
        {children}
      </div>
    </NoticeFoldContext.Provider>
  );
}

/**
 * The fold's control inside the lead notice's own line: „Dar pranešimai (2) · skaitymo įvertinimas · priminimai".
 * Renders nothing outside a fold, when `notice` does not lead it, or once it is open.
 */
export function NoticeFoldMore({ notice, className = '' }) {
  const ctx = useNoticeFold();
  if (!ctx || ctx.lead !== notice || ctx.open) return null;
  return (
    <button
      type="button"
      onClick={ctx.openFold}
      aria-expanded={false}
      data-testid="notice-fold-more"
      className={`inline-flex min-h-[24px] flex-wrap items-center gap-x-1 rounded px-1 text-left text-ui text-foreground hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${className}`}
    >
      <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
      <span className="font-medium underline underline-offset-2">{ctx.title}</span>
      {ctx.names && <span className="text-muted-foreground">{ctx.names}</span>}
    </button>
  );
}
