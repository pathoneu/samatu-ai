/**
 * RightPanelHost — the workspace's right panel as a MODE HOST (Pathon v3, design §3; Kreo's pattern).
 *
 * One strip of tabs — Patalpos ir eilutės · Kiekiai · Patikra · Sąmata · Pokalbis — over one content area.
 * The host owns only the frame: which tab is shown, how wide the panel is, where notices sit. What a tab
 * shows is the existing component, mounted unchanged by the workspace (WorkspacePanel, the Kiekiai tree,
 * the chat, Patikra's question list / room sheet, the Sąmata rows).
 *
 *  - `panels`: [{ id, node, keepMounted?, scroll? }] — `keepMounted` panels stay in the DOM while hidden
 *    (their filters, folds and chat history survive a switch); the others mount when shown. `scroll`
 *    gives the panel its own scroll area (contents that are a whole page, not a list).
 *  - `width`: px, or null with `grow` to take the remaining width (the Sąmata „Išskleisti" layout).
 *  - `onWidthChange(width, { final })`: when given, the panel's left edge is a resize handle (mouse drag,
 *    or arrow keys on the focused handle); `final` marks the end of a drag, when the owner stores it.
 *  - `notices`: shown above the tabs — outside the drawing's column, so a notice never takes its height.
 *  - `tabBarExtra`: one control at the right end of the tab strip.
 *  - `moreTabs`: tabs the current step does not need (B1-D) — listed under one „Daugiau ▾" at the end of the
 *    strip (a click menu, never hover); choosing one is the same `onTabChange` as a tab.
 *  - notices fold (W6-A NoticeFold): two or more notices show as one „Pranešimai (N)" line.
 *  - `cover`: a node laid over the tabs and their contents while a tool needs the panel (the legend review,
 *    v3 W2-B); the panels stay mounted underneath and come back as they were.
 */

import { useEffect, useRef, useState } from 'react';
import { ChevronDown } from 'lucide-react';
import NoticeFold from './NoticeFold';

const KEY_STEP = 16;

export default function RightPanelHost({
  tabs = [],
  activeTab,
  onTabChange,
  panels = [],
  width = null,
  grow = false,
  minWidth = 300,
  maxWidth = 960,
  onWidthChange = null,
  notices = null,
  // One control at the right end of the tab strip (the Sąmata „Išskleisti" switch).
  tabBarExtra = null,
  moreTabs = [],
  cover = null,
  className = '',
}) {
  const dragRef = useRef(null);

  const startDrag = (e) => {
    if (!onWidthChange || width == null) return;
    e.preventDefault();
    const startX = e.clientX;
    const startW = width;
    let last = startW;
    const clamp = (w) => Math.round(Math.min(maxWidth, Math.max(minWidth, w)));
    const onMove = (ev) => {
      // the panel is on the right: dragging its left edge to the left makes it wider
      last = clamp(startW + (startX - ev.clientX));
      onWidthChange(last, { final: false });
    };
    const onUp = () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
      document.body.style.removeProperty('cursor');
      document.body.style.removeProperty('user-select');
      onWidthChange(last, { final: true });
    };
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  };

  const onHandleKey = (e) => {
    if (!onWidthChange || width == null) return;
    const delta = e.key === 'ArrowLeft' ? KEY_STEP : e.key === 'ArrowRight' ? -KEY_STEP : 0;
    if (!delta) return;
    e.preventDefault();
    onWidthChange(Math.round(Math.min(maxWidth, Math.max(minWidth, width + delta))), { final: true });
  };

  return (
    <aside
      data-testid="right-panel"
      data-active-tab={activeTab || undefined}
      aria-label="Dešinysis skydelis"
      className={`relative flex flex-col min-h-0 min-w-0 bg-background ${grow ? 'flex-1' : 'shrink-0'} ${className}`}
      style={width != null && !grow ? { width } : undefined}
    >
      {onWidthChange && width != null && !grow && (
        <div
          ref={dragRef}
          role="separator"
          aria-orientation="vertical"
          aria-label="Skydelio plotis — tempkite arba spauskite rodykles kairėn / dešinėn"
          aria-valuenow={width}
          aria-valuemin={minWidth}
          aria-valuemax={maxWidth}
          tabIndex={0}
          title="Tempkite, kad pakeistumėte skydelio plotį"
          data-testid="right-panel-resizer"
          onMouseDown={startDrag}
          onKeyDown={onHandleKey}
          className="absolute left-0 top-0 bottom-0 z-20 w-1.5 -translate-x-1/2 cursor-col-resize hover:bg-foreground/15 focus-visible:bg-ring focus-visible:outline-none"
        />
      )}

      {notices && (
        <div data-testid="workspace-notices" className="shrink-0 max-h-[45%] overflow-y-auto border-b border-border px-3 pb-3 has-[[data-testid=notice-fold-body]:empty]:hidden">
          <NoticeFold className="mt-3 w-full">{notices}</NoticeFold>
        </div>
      )}

      {/* The tabs wrap rather than scroll: at 340 px five labels do not fit one line, and a tab behind a
          scrollbar is a tab he does not have. */}
      <div role="tablist" aria-label="Dešinysis skydelis" className="shrink-0 flex flex-wrap items-end border-b border-border bg-card">
        {tabs.map(({ id, label }) => (
          <button
            key={id}
            type="button"
            role="tab"
            id={`right-tab-${id}`}
            aria-selected={activeTab === id}
            aria-controls={`right-panel-${id}`}
            data-testid={`right-tab-${id}`}
            onClick={() => onTabChange?.(id)}
            className={`shrink-0 whitespace-nowrap px-3 min-h-[40px] text-[14px] border-b-2 -mb-px transition-colors ${activeTab === id
              ? 'border-foreground text-foreground font-semibold'
              : 'border-transparent text-muted-foreground hover:text-foreground'}`}
          >
            {label}
          </button>
        ))}
        {moreTabs.length > 0 && <MoreTabs tabs={moreTabs} onPick={(id) => onTabChange?.(id)} />}
        {tabBarExtra && <div className="ml-auto flex items-center px-2 shrink-0">{tabBarExtra}</div>}
      </div>

      {panels.map(({ id, node, keepMounted = false, scroll = false }) => {
        const shown = activeTab === id;
        if (!shown && !keepMounted) return null;
        return (
          <div
            key={id}
            id={`right-panel-${id}`}
            role="tabpanel"
            aria-labelledby={`right-tab-${id}`}
            data-testid={`right-panel-${id}`}
            className={shown ? `flex-1 min-h-0${scroll ? ' overflow-y-auto' : ''}` : 'hidden'}
          >
            {node}
          </div>
        );
      })}
      {cover && (
        <div className="absolute inset-0 z-10 flex flex-col bg-background" data-testid="right-panel-cover">{cover}</div>
      )}
    </aside>
  );
}

/** „Daugiau ▾" — the tabs this step does not need, one click away (a menu: Esc or a click outside closes it). */
function MoreTabs({ tabs, onPick }) {
  const [open, setOpen] = useState(false);
  const box = useRef(null);
  const button = useRef(null);
  useEffect(() => {
    if (!open) return undefined;
    const onDown = (e) => { if (box.current && !box.current.contains(e.target)) setOpen(false); };
    const onKey = (e) => {
      if (e.key === 'Escape') { e.stopPropagation(); setOpen(false); button.current?.focus(); }
    };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey, true);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey, true);
    };
  }, [open]);
  const onMenuKey = (e) => {
    if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp') return;
    e.preventDefault();
    const items = [...(box.current?.querySelectorAll('[role="menuitem"]') || [])];
    const at = items.indexOf(document.activeElement);
    const next = e.key === 'ArrowDown' ? (at + 1) % items.length : (at - 1 + items.length) % items.length;
    items[next]?.focus();
  };
  return (
    <div ref={box} className="relative shrink-0">
      <button
        ref={button}
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        data-testid="right-tab-more"
        onClick={() => setOpen((o) => !o)}
        className="inline-flex items-center gap-1 whitespace-nowrap px-3 min-h-[40px] text-ui border-b-2 border-transparent -mb-px text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        Daugiau
        <ChevronDown className={`h-4 w-4 transition-transform ${open ? 'rotate-180' : ''}`} aria-hidden="true" />
      </button>
      {open && (
        <div
          role="menu"
          aria-label="Kiti skydelio skirtukai"
          onKeyDown={onMenuKey}
          className="absolute left-0 top-full z-30 mt-1 min-w-[200px] rounded-panel border border-border bg-card py-1 shadow-lg"
        >
          {tabs.map(({ id, label }) => (
            <button
              key={id}
              type="button"
              role="menuitem"
              data-testid={`right-more-${id}`}
              onClick={() => { setOpen(false); onPick(id); }}
              className="flex w-full items-center px-3 min-h-[40px] text-left text-ui text-foreground hover:bg-muted focus-visible:bg-muted focus-visible:outline-none"
            >
              {label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
