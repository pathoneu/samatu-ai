/**
 * SheetRail — the viewer's left rail of sheets (Togal-v2 W7, research §1 „Sheets"). Replaces the
 * plain thumbnail strip: per sheet a thumbnail, its number, name and type, grouped by discipline in
 * collapsible groups. The current sheet is highlighted and kept in view; a click scrolls the
 * viewer to it. „Pervadinti" edits the name, type and group in place; „Atkurti automatinį" drops
 * the user's version. While a text search is active each sheet shows its hit count.
 *
 * The model (names, groups, what is automatic) is lib/sheetRail.buildSheetRail; persistence and
 * undo belong to the owner (TakeoffViewer → InteriorWorkspace → project.sheet_overrides).
 *
 * Thumbnails are not virtualized like the old ThumbnailsPane (groups break its fixed-row
 * windowing); instead each row mounts its ThumbImg only once it scrolls near the rail's viewport.
 * Sheet sets are tens of pages, not thousands.
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import { ChevronDown, ChevronRight, Pencil, RotateCcw, Check, X } from 'lucide-react';
import { useScroll } from '@embedpdf/plugin-scroll/react';
import { useSearch } from '@embedpdf/plugin-search/react';
import { ThumbImg } from '@embedpdf/plugin-thumbnail/react';
import { pageTypeColor } from '@/lib/pageTypes';
import {
  SHEET_TYPE_OPTIONS, DISCIPLINE_OPTIONS, sheetTypeLabel, searchHitsByPage,
} from '@/lib/sheetRail';

const CLOSED_KEY = 'samatu_viewer_sheet_groups_closed';

function readClosed() {
  try {
    const v = JSON.parse(localStorage.getItem(CLOSED_KEY) || '[]');
    return new Set(Array.isArray(v) ? v : []);
  } catch { return new Set(); }
}

/** Mounts its children once the row is within 300 px of the rail's visible area. */
function useNearViewport(rootRef) {
  const ref = useRef(null);
  const [near, setNear] = useState(false);
  useEffect(() => {
    if (near || !ref.current) return undefined;
    if (typeof IntersectionObserver === 'undefined') { setNear(true); return undefined; }
    const io = new IntersectionObserver((entries) => {
      if (entries.some((e) => e.isIntersecting)) { setNear(true); io.disconnect(); }
    }, { root: rootRef.current, rootMargin: '300px 0px' });
    io.observe(ref.current);
    return () => io.disconnect();
  }, [near, rootRef]);
  return [ref, near];
}

const selectCls = 'w-full h-7 rounded-[2px] border border-[hsl(var(--viewer-chrome-border))] bg-[hsl(var(--viewer-chrome-muted))] px-1.5 text-[11px] text-[hsl(var(--viewer-chrome-foreground))] focus:outline-none focus:ring-1 focus:ring-[hsl(var(--viewer-chrome-active))]';

function SheetEditor({ sheet, onSave, onCancel, onReset }) {
  const [name, setName] = useState(sheet.fullName);
  const [type, setType] = useState(sheet.tipas);
  const [group, setGroup] = useState(sheet.discipline);
  const inputRef = useRef(null);
  useEffect(() => { inputRef.current?.focus(); inputRef.current?.select(); }, []);
  const save = () => onSave({ name, type, dalis: group });
  return (
    <div
      className="mt-1.5 space-y-1.5"
      onClick={(e) => e.stopPropagation()}
      onKeyDown={(e) => {
        e.stopPropagation();
        if (e.key === 'Enter') { e.preventDefault(); save(); }
        if (e.key === 'Escape') { e.preventDefault(); onCancel(); }
      }}
    >
      <input
        ref={inputRef}
        value={name}
        maxLength={200}
        onChange={(e) => setName(e.target.value)}
        aria-label="Lapo pavadinimas"
        className={`${selectCls} px-2 text-[12px]`}
      />
      <select value={type} onChange={(e) => setType(e.target.value)} aria-label="Lapo tipas" className={selectCls}>
        {SHEET_TYPE_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
      <select value={group} onChange={(e) => setGroup(e.target.value)} aria-label="Lapo grupė" className={selectCls}>
        {DISCIPLINE_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
      <p className="text-[10px] leading-snug text-[hsl(var(--viewer-chrome-foreground)/0.6)]" title={sheet.autoName}>
        Automatinis: {sheet.autoName} · {sheetTypeLabel(sheet.autoTipas)}
      </p>
      <div className="flex items-center gap-1">
        <button type="button" onClick={save} className="inline-flex items-center gap-1 h-6 px-2 rounded-[2px] bg-[hsl(var(--viewer-chrome-active))] text-white text-[11px]">
          <Check className="w-3 h-3" />Išsaugoti
        </button>
        <button type="button" onClick={onCancel} className="inline-flex items-center gap-1 h-6 px-2 rounded-[2px] border border-[hsl(var(--viewer-chrome-border))] text-[11px] text-[hsl(var(--viewer-chrome-foreground))] hover:bg-[hsl(var(--viewer-chrome-hover))]">
          <X className="w-3 h-3" />Atšaukti
        </button>
      </div>
      {sheet.overridden && (
        <button type="button" onClick={onReset} className="inline-flex items-center gap-1 text-[11px] text-[hsl(var(--viewer-chrome-active))] hover:underline">
          <RotateCcw className="w-3 h-3" />Atkurti automatinį
        </button>
      )}
    </div>
  );
}

function SheetRow({ documentId, sheet, current, hits, searching, editing, rootRef, onOpen, onEdit, onSave, onCancel, onReset, rowRef }) {
  const [nearRef, near] = useNearViewport(rootRef);
  const setRefs = (el) => { nearRef.current = el; rowRef(el); };
  const numberTitle = sheet.number && sheet.number !== sheet.shortNumber ? sheet.number : undefined;
  return (
    <li
      ref={setRefs}
      data-sheet-page={sheet.page}
      aria-current={current ? 'page' : undefined}
      className={`group relative px-2 py-1.5 border-l-2 ${current ? 'border-[hsl(var(--viewer-chrome-active))] bg-[hsl(var(--viewer-chrome-muted))]' : 'border-transparent hover:bg-[hsl(var(--viewer-chrome-hover))]'}`}
    >
      <button type="button" onClick={onOpen} onDoubleClick={onEdit} className="flex w-full items-start gap-2 text-left focus:outline-none" title={`Lapas ${sheet.page}: ${sheet.fullName}`}>
        <span className={`shrink-0 w-[60px] min-h-[42px] flex items-start justify-center bg-white rounded-[2px] overflow-hidden ${current ? 'ring-2 ring-[hsl(var(--viewer-chrome-active))]' : 'ring-1 ring-[hsl(var(--viewer-chrome-border))]'}`}>
          {near && <ThumbImg documentId={documentId} meta={{ pageIndex: sheet.page - 1 }} style={{ width: 60, height: 'auto', display: 'block' }} />}
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex items-center gap-1.5">
            <span className={`mono tabular text-[10px] ${current ? 'text-[hsl(var(--viewer-chrome-active))] font-semibold' : 'text-[hsl(var(--viewer-chrome-foreground)/0.6)]'}`} title={numberTitle}>
              {sheet.shortNumber || sheet.page}
            </span>
            {sheet.shortNumber && <span className="mono tabular text-[9px] text-[hsl(var(--viewer-chrome-foreground)/0.45)]">psl. {sheet.page}</span>}
            {searching && (
              <span
                className={`ml-auto mono tabular text-[10px] px-1 rounded-[2px] ${hits ? 'bg-[hsl(var(--viewer-chrome-active))] text-white' : 'text-[hsl(var(--viewer-chrome-foreground)/0.4)]'}`}
                title={hits ? `Paieškos rezultatų šiame lape: ${hits}` : 'Šiame lape paieška nieko nerado'}
                data-testid="sheet-hits"
              >{hits || 0}</span>
            )}
          </span>
          <span className="block text-[11.5px] leading-tight text-[hsl(var(--viewer-chrome-foreground))] line-clamp-2 break-words">
            {sheet.name}
          </span>
          <span className="mt-0.5 flex items-center gap-1 flex-wrap">
            <span className="inline-flex items-center gap-1 rounded-[2px] border border-[hsl(var(--viewer-chrome-border))] px-1 text-[9.5px] leading-[14px] text-[hsl(var(--viewer-chrome-foreground)/0.75)]">
              <span className="w-1.5 h-1.5 rounded-full" style={{ background: pageTypeColor(sheet.tipas) }} />
              {sheetTypeLabel(sheet.tipas)}
            </span>
            {sheet.overridden && (
              <span className="text-[9.5px] text-[hsl(var(--viewer-chrome-active))]" title={`Pakeitėte jūs. Automatinis: ${sheet.autoName} · ${sheetTypeLabel(sheet.autoTipas)}`}>jūsų</span>
            )}
            {!sheet.classified && !sheet.overridden && (
              <span className="text-[9.5px] text-[hsl(var(--viewer-chrome-foreground)/0.5)]" title="Šio lapo programa neklasifikavo — pavadinkite jį patys">neklasifikuotas</span>
            )}
          </span>
        </span>
      </button>
      {!editing && onEdit && (
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); onEdit(); }}
          title="Pervadinti lapą"
          aria-label={`Pervadinti lapą ${sheet.page}`}
          className="absolute right-1.5 top-1.5 w-6 h-6 rounded-[2px] flex items-center justify-center text-[hsl(var(--viewer-chrome-foreground)/0.6)] bg-[hsl(var(--viewer-chrome))] border border-[hsl(var(--viewer-chrome-border))] opacity-0 group-hover:opacity-100 focus:opacity-100 hover:text-[hsl(var(--viewer-chrome-active))]"
        >
          <Pencil className="w-3 h-3" />
        </button>
      )}
      {editing && <SheetEditor sheet={sheet} onSave={onSave} onCancel={onCancel} onReset={onReset} />}
    </li>
  );
}

export default function SheetRail({ documentId, rail, currentPageOf, onRename = null, onReset = null }) {
  const { state: scroll, provides: scrollApi } = useScroll(documentId);
  const { state: search } = useSearch(documentId);
  const cur = currentPageOf ? currentPageOf(scroll) : (scroll?.currentPage ?? 1);
  const [closed, setClosedState] = useState(readClosed);
  const [editingPage, setEditingPage] = useState(null);
  const rootRef = useRef(null);
  const rows = useRef(new Map());

  const searching = !!(search?.query && search?.active !== false && !search?.loading);
  const hits = useMemo(() => (searching ? searchHitsByPage(search?.results) : {}), [searching, search?.results]);

  const toggleGroup = (key) => setClosedState((prev) => {
    const next = new Set(prev);
    if (next.has(key)) next.delete(key); else next.add(key);
    try { localStorage.setItem(CLOSED_KEY, JSON.stringify([...next])); } catch { /* private mode */ }
    return next;
  });

  // Keep the current sheet in view — and open its group when the viewer scrolls into it.
  const curGroup = rail.sheets.find((s) => s.page === cur)?.discipline;
  useEffect(() => {
    const el = rows.current.get(cur);
    el?.scrollIntoView?.({ block: 'nearest' });
  }, [cur, closed]);

  const open = (page) => scrollApi?.scrollToPage({ pageNumber: page, behavior: 'smooth' });

  return (
    <aside
      ref={rootRef}
      className="w-[232px] shrink-0 overflow-y-auto bg-[hsl(var(--viewer-chrome))] border-r border-[hsl(var(--viewer-chrome-border))]"
      aria-label="Brėžinio lapai"
      data-testid="sheet-rail"
    >
      {rail.groups.map((g) => {
        const isClosed = closed.has(g.key) && g.key !== curGroup;
        const groupHits = searching ? g.sheets.reduce((n, s) => n + (hits[s.page] || 0), 0) : 0;
        return (
          <section key={g.key} aria-label={g.label}>
            <button
              type="button"
              onClick={() => toggleGroup(g.key)}
              aria-expanded={!isClosed}
              className="sticky top-0 z-10 flex w-full items-center gap-1 px-2 h-7 bg-[hsl(var(--viewer-chrome))] border-b border-[hsl(var(--viewer-chrome-border))] text-[10.5px] font-semibold uppercase tracking-wide text-[hsl(var(--viewer-chrome-foreground)/0.75)] hover:text-[hsl(var(--viewer-chrome-foreground))]"
            >
              {isClosed ? <ChevronRight className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
              <span className="truncate">{g.label}</span>
              <span className="ml-auto shrink-0 whitespace-nowrap mono tabular font-normal normal-case text-[hsl(var(--viewer-chrome-foreground)/0.5)]">
                {searching ? `${groupHits} / ` : ''}{g.sheets.length}
              </span>
            </button>
            {!isClosed && (
              <ul>
                {g.sheets.map((s) => (
                  <SheetRow
                    key={s.page}
                    documentId={documentId}
                    sheet={s}
                    current={s.page === cur}
                    hits={hits[s.page] || 0}
                    searching={searching}
                    editing={editingPage === s.page}
                    rootRef={rootRef}
                    rowRef={(el) => { if (el) rows.current.set(s.page, el); else rows.current.delete(s.page); }}
                    onOpen={() => open(s.page)}
                    onEdit={onRename ? () => setEditingPage(s.page) : null}
                    onSave={(patch) => { setEditingPage(null); onRename?.(s, patch); }}
                    onCancel={() => setEditingPage(null)}
                    onReset={() => { setEditingPage(null); onReset?.(s); }}
                  />
                ))}
              </ul>
            )}
          </section>
        );
      })}
      {rail.sheets.length === 0 && (
        <p className="p-3 text-[11px] text-[hsl(var(--viewer-chrome-foreground)/0.6)]">Lapų sąrašas dar neparuoštas.</p>
      )}
    </aside>
  );
}
