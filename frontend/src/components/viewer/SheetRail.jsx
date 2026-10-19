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
 * Pathon v3 (workspace frame, A4): the rail opens as a 56 px STRIP of thumbnails with the sheet number
 * under each, groups kept apart by a rule; a sheet's name and group show beside the strip when its
 * thumbnail is focused or clicked (never on hover alone). „Lapai" at the top (or T) opens the full rail.
 *
 * Pathon v3 W5-B B9 (coverage #1): „Neskaityti šio lapo" — the sheet on screen carries a visible button on its row
 * of the full rail (and in the rename editor); a skipped sheet is dimmed and tagged „neskaitomas" in both widths.
 * The free re-read and the detection run read it as a blank page (backend api/skip_sheets.py); it stays in the
 * PDF. Persistence and the toast's „Atšaukti" belong to the owner (TakeoffViewer → project.neskaitomi_lapai).
 *
 * Thumbnails are not virtualized like the old ThumbnailsPane (groups break its fixed-row
 * windowing); instead each row mounts its ThumbImg only once it scrolls near the rail's viewport.
 * Sheet sets are tens of pages, not thousands.
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import { ChevronDown, ChevronRight, Pencil, RotateCcw, Check, X, PanelLeftOpen, EyeOff, Eye } from 'lucide-react';
import { useScroll } from '@embedpdf/plugin-scroll/react';
import { useSearch } from '@embedpdf/plugin-search/react';
import { ThumbImg } from '@embedpdf/plugin-thumbnail/react';
import { pageTypeColor } from '@/lib/pageTypes';
import {
  SHEET_TYPE_OPTIONS, DISCIPLINE_OPTIONS, sheetTypeLabel, searchHitsByPage, stripLabel, stripTag,
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

const selectCls = 'w-full h-7 rounded-[2px] border border-viewer-chrome-border bg-viewer-chrome-muted px-1.5 text-meta text-viewer-chrome-foreground focus:outline-none focus:ring-1 focus:ring-viewer-chrome-active';

function SheetEditor({ sheet, onSave, onCancel, onReset, skipped = false, onToggleSkip = null }) {
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
        className={`${selectCls} px-2 text-meta`}
      />
      <select value={type} onChange={(e) => setType(e.target.value)} aria-label="Lapo tipas" className={selectCls}>
        {SHEET_TYPE_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
      <select value={group} onChange={(e) => setGroup(e.target.value)} aria-label="Lapo grupė" className={selectCls}>
        {DISCIPLINE_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
      <p className="text-meta leading-snug text-viewer-chrome-foreground/75" title={sheet.autoName}>
        Automatinis: {sheet.autoName} · {sheetTypeLabel(sheet.autoTipas)}
      </p>
      <div className="flex items-center gap-1">
        <button type="button" onClick={save} className="inline-flex items-center gap-1 h-6 px-2 rounded-[2px] bg-viewer-chrome-active text-white text-meta">
          <Check className="w-3 h-3" />Išsaugoti
        </button>
        <button type="button" onClick={onCancel} className="inline-flex items-center gap-1 h-6 px-2 rounded-[2px] border border-viewer-chrome-border text-meta text-viewer-chrome-foreground hover:bg-viewer-chrome-hover">
          <X className="w-3 h-3" />Atšaukti
        </button>
      </div>
      {sheet.overridden && (
        <button type="button" onClick={onReset} className="inline-flex items-center gap-1 text-meta text-viewer-chrome-active hover:underline">
          <RotateCcw className="w-3 h-3" />Atkurti automatinį
        </button>
      )}
      {onToggleSkip && <SkipButton skipped={skipped} onClick={onToggleSkip} />}
    </div>
  );
}

/** „Neskaityti šio lapo" / „Skaityti šį lapą" — one visible button, words and icon (never hover-only). */
function SkipButton({ skipped, onClick }) {
  return (
    <button
      type="button"
      onClick={(e) => { e.stopPropagation(); onClick(); }}
      className="inline-flex items-center gap-1 text-meta text-viewer-chrome-foreground hover:text-viewer-chrome-active hover:underline"
      title={skipped
        ? 'Programa vėl skaitys šį lapą, kai perskaitysite brėžinį iš naujo'
        : 'Lapas lieka PDF ir brėžinyje, bet programa jo neskaitys (perskaitant iš naujo ir „Perskaityti lapą“) — pvz. viršelis ar kitas objektas'}
      data-testid={skipped ? 'sheet-skip-undo' : 'sheet-skip'}
    >
      {skipped ? <Eye className="w-3.5 h-3.5" /> : <EyeOff className="w-3.5 h-3.5" />}
      {skipped ? 'Skaityti šį lapą' : 'Neskaityti šio lapo'}
    </button>
  );
}

function SheetRow({ documentId, sheet, current, hits, searching, editing, rootRef, onOpen, onEdit, onSave, onCancel, onReset, rowRef, skipped = false, onToggleSkip = null }) {
  const [nearRef, near] = useNearViewport(rootRef);
  const setRefs = (el) => { nearRef.current = el; rowRef(el); };
  const numberTitle = sheet.number && sheet.number !== sheet.shortNumber ? sheet.number : undefined;
  return (
    <li
      ref={setRefs}
      data-sheet-page={sheet.page}
      aria-current={current ? 'page' : undefined}
      className={`group relative px-2 py-1.5 border-l-2 ${current ? 'border-viewer-chrome-active bg-viewer-chrome-muted' : 'border-transparent hover:bg-viewer-chrome-hover'}`}
      data-skipped={skipped ? '1' : undefined}
    >
      <button type="button" onClick={onOpen} onDoubleClick={onEdit} className="flex w-full items-start gap-2 text-left focus:outline-none" title={`Lapas ${sheet.page}: ${sheet.fullName}`}>
        <span className={`shrink-0 w-[60px] min-h-[42px] flex items-start justify-center bg-white rounded-[2px] overflow-hidden ${skipped ? 'opacity-40' : ''} ${current ? 'ring-2 ring-viewer-chrome-active' : 'ring-1 ring-viewer-chrome-border'}`}>
          {near && <ThumbImg documentId={documentId} meta={{ pageIndex: sheet.page - 1 }} style={{ width: 60, height: 'auto', display: 'block' }} />}
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex items-center gap-1.5">
            <span className={`mono tabular text-meta ${current ? 'text-viewer-chrome-active font-semibold' : 'text-viewer-chrome-foreground/75'}`} title={numberTitle}>
              {sheet.shortNumber || sheet.page}
            </span>
            {sheet.shortNumber && <span className="mono tabular text-meta text-viewer-chrome-foreground/75">psl. {sheet.page}</span>}
            {searching && (
              <span
                className={`ml-auto mono tabular text-meta px-1 rounded-[2px] ${hits ? 'bg-viewer-chrome-active text-white' : 'text-viewer-chrome-foreground/75'}`}
                title={hits ? `Paieškos rezultatų šiame lape: ${hits}` : 'Šiame lape paieška nieko nerado'}
                data-testid="sheet-hits"
              >{hits || 0}</span>
            )}
          </span>
          <span className="block text-meta leading-tight text-viewer-chrome-foreground line-clamp-2 break-words">
            {sheet.name}
          </span>
          <span className="mt-0.5 flex items-center gap-1 flex-wrap">
            <span className="inline-flex items-center gap-1 rounded-[2px] border border-viewer-chrome-border px-1 text-meta leading-[14px] text-viewer-chrome-foreground/75">
              <span className="w-1.5 h-1.5 rounded-full" style={{ background: pageTypeColor(sheet.tipas) }} />
              {sheetTypeLabel(sheet.tipas)}
            </span>
            {sheet.overridden && (
              <span className="text-meta text-viewer-chrome-active" title={`Pakeitėte jūs. Automatinis: ${sheet.autoName} · ${sheetTypeLabel(sheet.autoTipas)}`}>jūsų</span>
            )}
            {!sheet.classified && !sheet.overridden && (
              <span className="text-meta text-viewer-chrome-foreground/75" title="Šio lapo programa neklasifikavo — pavadinkite jį patys">neklasifikuotas</span>
            )}
            {skipped && (
              <span className="text-meta font-semibold text-viewer-chrome-foreground" data-testid="sheet-skipped-tag" title="Programa šio lapo neskaito — jis lieka PDF ir brėžinyje">neskaitomas</span>
            )}
          </span>
        </span>
      </button>
      {onToggleSkip && !editing && (current || skipped) && (
        <div className="mt-1 pl-[68px]"><SkipButton skipped={skipped} onClick={onToggleSkip} /></div>
      )}
      {!editing && onEdit && (
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); onEdit(); }}
          title="Pervadinti lapą"
          aria-label={`Pervadinti lapą ${sheet.page}`}
          className="absolute right-1.5 top-1.5 w-6 h-6 rounded-[2px] flex items-center justify-center text-viewer-chrome-foreground/75 bg-viewer-chrome border border-viewer-chrome-border opacity-0 group-hover:opacity-100 focus:opacity-100 hover:text-viewer-chrome-active"
        >
          <Pencil className="w-3 h-3" />
        </button>
      )}
      {editing && <SheetEditor sheet={sheet} onSave={onSave} onCancel={onCancel} onReset={onReset} skipped={skipped} onToggleSkip={onToggleSkip} />}
    </li>
  );
}

/**
 * The rail in two widths (Pathon v3 frame, A4): `mode="strip"` — 56 px of thumbnails, the drawing gets the
 * room — and `mode="full"` — numbers, names, types and the rename editor. Two components, so switching
 * never mixes their state.
 */
export default function SheetRail({ mode = 'full', ...props }) {
  return mode === 'strip' ? <SheetStrip {...props} /> : <SheetRailFull {...props} />;
}

function SheetStripRow({ documentId, sheet, current, hits, searching, label, rootRef, rowRef, onOpen, onShowLabel, onHideLabel, skipped = false }) {
  const [nearRef, near] = useNearViewport(rootRef);
  const setRefs = (el) => { nearRef.current = el; rowRef(el); };
  return (
    <li ref={setRefs} data-sheet-page={sheet.page} aria-current={current ? 'page' : undefined} className="relative">
      <button
        type="button"
        onClick={() => { onOpen(); onShowLabel(); }}
        onFocus={onShowLabel}
        onBlur={onHideLabel}
        aria-label={label}
        className={`flex w-full flex-col items-center gap-0.5 border-l-2 px-1 py-1.5 focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-viewer-chrome-active ${current
          ? 'border-viewer-chrome-active bg-viewer-chrome-muted'
          : 'border-transparent hover:bg-viewer-chrome-hover'}`}
      >
        <span className={`flex min-h-[28px] w-10 items-start justify-center overflow-hidden rounded-[2px] bg-white ${skipped ? 'opacity-40' : ''} ${current ? 'ring-2 ring-viewer-chrome-active' : 'ring-1 ring-viewer-chrome-border'}`}>
          {near && <ThumbImg documentId={documentId} meta={{ pageIndex: sheet.page - 1 }} style={{ width: 40, height: 'auto', display: 'block' }} />}
        </span>
        <span className={`mono tabular text-meta leading-tight ${current ? 'font-semibold text-viewer-chrome-active' : 'text-viewer-chrome-foreground/75'}`}>
          {stripTag(sheet)}
        </span>
      </button>
      {searching && hits > 0 && (
        <span
          className="pointer-events-none absolute right-1 top-1 rounded-[2px] bg-viewer-chrome-active px-1 text-meta leading-[16px] text-white mono tabular"
          data-testid="sheet-hits"
        >{hits}</span>
      )}
    </li>
  );
}

function SheetStrip({ documentId, rail, currentPageOf, onExpand = null, skipped = null }) {
  const { state: scroll, provides: scrollApi } = useScroll(documentId);
  const { state: search } = useSearch(documentId);
  const cur = currentPageOf ? currentPageOf(scroll) : (scroll?.currentPage ?? 1);
  const rootRef = useRef(null);
  const rows = useRef(new Map());
  // The sheet whose name is shown beside the strip: on focus or click, never on hover alone (Rimas).
  const [label, setLabel] = useState(null);       // {page, top, left} in viewport px

  const searching = !!(search?.query && search?.active !== false && !search?.loading);
  const hits = useMemo(() => (searching ? searchHitsByPage(search?.results) : {}), [searching, search?.results]);
  const groupLabelOf = useMemo(() => {
    const m = new Map();
    rail.groups.forEach((g) => g.sheets.forEach((s) => m.set(s.page, g.label)));
    return m;
  }, [rail.groups]);

  useEffect(() => {
    rows.current.get(cur)?.scrollIntoView?.({ block: 'nearest' });
  }, [cur]);

  const showLabel = (page) => {
    const el = rows.current.get(page);
    if (!el) return;
    const r = el.getBoundingClientRect();
    setLabel({ page, top: Math.round(r.top + r.height / 2), left: Math.round(r.right + 6) });
  };
  // Esc, a click elsewhere or a scroll of the strip puts the name away.
  useEffect(() => {
    if (!label) return undefined;
    const onKey = (e) => { if (e.key === 'Escape') setLabel(null); };
    const onDown = (e) => { if (!rootRef.current?.contains(e.target)) setLabel(null); };
    const onScroll = () => setLabel(null);
    const root = rootRef.current;
    document.addEventListener('keydown', onKey);
    document.addEventListener('pointerdown', onDown, true);
    root?.addEventListener('scroll', onScroll);
    return () => {
      document.removeEventListener('keydown', onKey);
      document.removeEventListener('pointerdown', onDown, true);
      root?.removeEventListener('scroll', onScroll);
    };
  }, [label]);

  const open = (page) => scrollApi?.scrollToPage({ pageNumber: page, behavior: 'smooth' });
  const labelSheet = label ? rail.sheets.find((s) => s.page === label.page) : null;

  return (
    <aside
      ref={rootRef}
      className="w-14 shrink-0 overflow-y-auto overflow-x-hidden bg-viewer-chrome border-r border-viewer-chrome-border"
      aria-label="Brėžinio lapai"
      data-testid="sheet-rail"
      data-mode="strip"
    >
      {onExpand && (
        <button
          type="button"
          onClick={onExpand}
          title="Lapų sąrašas su pavadinimais ir tipais (T)"
          aria-label="Rodyti lapų sąrašą su pavadinimais"
          data-testid="sheet-rail-expand"
          className="sticky top-0 z-10 flex w-full flex-col items-center gap-0.5 border-b border-viewer-chrome-border bg-viewer-chrome py-1.5 text-viewer-chrome-foreground hover:bg-viewer-chrome-hover focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-viewer-chrome-active"
        >
          <PanelLeftOpen className="h-4 w-4" aria-hidden />
          <span className="text-[14px] leading-tight">Lapai</span>
        </button>
      )}
      {rail.groups.map((g, gi) => (
        <section key={g.key} aria-label={g.label}>
          {gi > 0 && <div aria-hidden className="mx-2 my-1 border-t border-viewer-chrome-border" />}
          <ul>
            {g.sheets.map((s) => (
              <SheetStripRow
                key={s.page}
                documentId={documentId}
                sheet={s}
                current={s.page === cur}
                hits={hits[s.page] || 0}
                searching={searching}
                label={`${stripLabel(s, g.label)}${skipped?.has(s.page) ? ' — neskaitomas' : ''}`}
                skipped={!!skipped?.has(s.page)}
                rootRef={rootRef}
                rowRef={(el) => { if (el) rows.current.set(s.page, el); else rows.current.delete(s.page); }}
                onOpen={() => open(s.page)}
                onShowLabel={() => showLabel(s.page)}
                onHideLabel={() => setLabel((cur2) => (cur2?.page === s.page ? null : cur2))}
              />
            ))}
          </ul>
        </section>
      ))}
      {labelSheet && (
        <div
          role="tooltip"
          data-testid="sheet-strip-label"
          className="pointer-events-none fixed z-40 max-w-[320px] -translate-y-1/2 rounded-[2px] border border-border bg-card px-2.5 py-1.5 text-[14px] leading-snug text-foreground shadow-md"
          style={{ top: label.top, left: label.left }}
        >
          {stripLabel(labelSheet, groupLabelOf.get(labelSheet.page))}{skipped?.has(labelSheet.page) ? ' — neskaitomas' : ''}
        </div>
      )}
    </aside>
  );
}

function SheetRailFull({ documentId, rail, currentPageOf, onRename = null, onReset = null, skipped = null, onToggleSkip = null }) {
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
      className="w-[232px] shrink-0 overflow-y-auto bg-viewer-chrome border-r border-viewer-chrome-border"
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
              className="sticky top-0 z-10 flex w-full items-center gap-1 px-2 h-7 bg-viewer-chrome border-b border-viewer-chrome-border text-meta font-semibold text-viewer-chrome-foreground/75 hover:text-viewer-chrome-foreground"
            >
              {isClosed ? <ChevronRight className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
              <span className="truncate">{g.label}</span>
              <span className="ml-auto shrink-0 whitespace-nowrap mono tabular font-normal normal-case text-viewer-chrome-foreground/75">
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
                    skipped={!!skipped?.has(s.page)}
                    onToggleSkip={onToggleSkip ? () => onToggleSkip(s) : null}
                  />
                ))}
              </ul>
            )}
          </section>
        );
      })}
      {rail.sheets.length === 0 && (
        <p className="p-3 text-meta text-viewer-chrome-foreground/75">Lapų sąrašas dar neparuoštas.</p>
      )}
    </aside>
  );
}
