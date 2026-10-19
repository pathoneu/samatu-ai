/**
 * MeasureGroups — the Matavimai list in named groups, with filters (Pathon v3 W5-B, B10; coverage #126, #127).
 * WorkspacePanel hands in the list's items ({key, kind, source, pages}) and how to draw one row (its own row, with
 * W4-A's drag-to-row and „Į eilutę…" untouched); this component only arranges them.
 *
 *   filters  „Rasta automatiškai" / „Jūsų", „Šis lapas" (the sheet on screen, from the viewer's
 *            `samatu:viewer-page` event), and the kind — Atstumai · Perimetrai · Plotai · Kiekiai · Pastabos
 *            (note pins are listed by NotesList under the list; the chip says so);
 *   groups   „+ Grupė" makes „Grupė N"; a double-click on the name or „Pervadinti" renames it in place (Enter /
 *            Esc / leaving the field); a row dragged onto a group's head joins it, onto „Be grupės" leaves it;
 *            „Pridėti…" in a group's head does the same with clicks (nothing is drag-only — Rimas §5); removing
 *            a group keeps its measurements (they go back to „Be grupės"), with „Atšaukti".
 *
 * Groups are stored in `project.measureGroups` (lib/measureGroups — beside the measurements, never on them).
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import { toast } from 'sonner';
import { ChevronDown, ChevronRight, FolderPlus, Pencil, Plus, Trash2 } from 'lucide-react';

import { getProject, updateProject } from '@/lib/projectStore';
import { MEASURE_DRAG_TYPE } from '@/lib/measuredRows';
import {
  KIND_FILTERS, NO_FILTERS, SOURCE_FILTERS, addGroup, assignToGroup, filtersActive, groupedSections, groupsOf,
  passesFilters, removeGroup, renameGroup,
} from '@/lib/measureGroups';

export const VIEWER_PAGE_EVENT = 'samatu:viewer-page';

function useViewerPage() {
  const [page, setPage] = useState(() => (typeof window !== 'undefined' ? Number(window.__pathonViewerPage) || null : null));
  useEffect(() => {
    const on = (e) => setPage(Number(e.detail?.page) || null);
    window.addEventListener(VIEWER_PAGE_EVENT, on);
    return () => window.removeEventListener(VIEWER_PAGE_EVENT, on);
  }, []);
  return page;
}

const chip = (on) => `inline-flex min-h-[32px] items-center rounded-[2px] border px-2 text-ui focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${on
  ? 'border-foreground bg-foreground text-background'
  : 'border-border bg-card text-foreground hover:bg-muted'}`;

function GroupName({ name, editing, onStart, onDone }) {
  const [value, setValue] = useState(name);
  const ref = useRef(null);
  useEffect(() => { if (editing) { setValue(name); setTimeout(() => ref.current?.select(), 0); } }, [editing, name]);
  if (!editing) {
    return (
      <span className="flex-1 min-w-0 truncate font-medium text-foreground" onDoubleClick={onStart} title="Dukart spustelėkite — pervadinti">{name}</span>
    );
  }
  return (
    <input
      ref={ref}
      value={value}
      autoFocus
      maxLength={60}
      aria-label="Grupės pavadinimas"
      onChange={(e) => setValue(e.target.value)}
      onKeyDown={(e) => {
        e.stopPropagation();
        if (e.key === 'Enter') { e.preventDefault(); onDone(value); }
        if (e.key === 'Escape') { e.preventDefault(); onDone(null); }
      }}
      onBlur={() => onDone(value)}
      onClick={(e) => e.stopPropagation()}
      className="flex-1 min-w-0 h-7 px-1.5 rounded-[2px] border border-border bg-card text-ui text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
      data-testid="meas-group-name-input"
    />
  );
}

export default function MeasureGroups({ project, onProjectChange, items, renderRow, noteCount = 0 }) {
  const page = useViewerPage();
  const [filters, setFilters] = useState(NO_FILTERS);
  const [editing, setEditing] = useState(null);       // group id being renamed
  const [over, setOver] = useState(undefined);         // section id a drag is over (null = „Be grupės")
  const [adding, setAdding] = useState(null);          // group id whose „Pridėti…" list is open
  const [closed, setClosed] = useState(() => new Set());
  const state = useMemo(() => groupsOf(project), [project]);
  const shown = useMemo(() => items.filter((it) => passesFilters(it, filters, { page })), [items, filters, page]);
  const sections = useMemo(() => groupedSections(shown, state), [shown, state]);

  const save = (next, message = null, before = null) => {
    const base = getProject(project.id) || project;
    const saved = updateProject(project.id, { measureGroups: next });
    if (saved) onProjectChange?.(saved);
    if (message) {
      const prev = before ?? groupsOf(base);
      toast(message, {
        duration: 8000,
        action: { label: 'Atšaukti', onClick: () => { const back = updateProject(project.id, { measureGroups: prev }); if (back) onProjectChange?.(back); } },
      });
    }
  };
  const current = () => groupsOf(getProject(project.id) || project);
  const newGroup = () => {
    const next = addGroup(current());
    save(next);
    setEditing(next.groups[next.groups.length - 1].id);
  };
  const moveTo = (key, groupId) => {
    const before = current();
    if ((before.members[key] || null) === (groupId || null)) return;
    const name = groupId ? before.groups.find((g) => g.id === groupId)?.name : null;
    save(assignToGroup(before, key, groupId), groupId ? `Perkelta į „${name}“` : 'Išimta iš grupės', before);
  };
  const dropProps = (sectionId) => ({
    onDragOver: (e) => {
      if (!Array.from(e.dataTransfer?.types || []).includes(MEASURE_DRAG_TYPE)) return;
      e.preventDefault();
      e.dataTransfer.dropEffect = 'link';
      if (over !== sectionId) setOver(sectionId);
    },
    onDragLeave: () => setOver(undefined),
    onDrop: (e) => {
      const key = e.dataTransfer?.getData(MEASURE_DRAG_TYPE);
      setOver(undefined);
      if (!key) return;
      e.preventDefault();
      e.stopPropagation();
      moveTo(key, sectionId);
    },
  });
  const toggle = (id) => setClosed((prev) => { const n = new Set(prev); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  const setF = (patch) => setFilters((f) => ({ ...f, ...patch }));
  const ungroupedAll = items.filter((it) => !state.members[it.key]);

  return (
    <div data-testid="meas-groups">
      <div className="flex flex-wrap items-center gap-1.5 px-3 py-2 border-b border-border/50" role="group" aria-label="Matavimų filtrai">
        {SOURCE_FILTERS.map((f) => (
          <button key={f.id} type="button" className={chip(filters.source === f.id)} aria-pressed={filters.source === f.id}
            onClick={() => setF({ source: filters.source === f.id ? null : f.id })} data-testid={`meas-filter-${f.id}`}>{f.label}</button>
        ))}
        <button type="button" className={chip(filters.thisSheet)} aria-pressed={filters.thisSheet} disabled={page == null}
          title={page == null ? 'Atidarykite brėžinį — filtras rodys tik jame matomo lapo matavimus' : `Tik ${page} lapo matavimai`}
          onClick={() => setF({ thisSheet: !filters.thisSheet })} data-testid="meas-filter-sheet">
          {page ? `Šis lapas (${page})` : 'Šis lapas'}
        </button>
        {KIND_FILTERS.map((f) => (
          <button key={f.id} type="button" className={chip(filters.kind === f.id)} aria-pressed={filters.kind === f.id}
            onClick={() => setF({ kind: filters.kind === f.id ? null : f.id })} data-testid={`meas-filter-kind-${f.id}`}>
            {f.label}{f.id === 'note' && noteCount ? ` (${noteCount})` : ''}
          </button>
        ))}
        {filtersActive(filters) && (
          <button type="button" className="text-ui text-primary hover:underline" onClick={() => setFilters(NO_FILTERS)} data-testid="meas-filter-clear">Rodyti visus</button>
        )}
        <span className="flex-1" />
        <button type="button" onClick={newGroup} className="inline-flex min-h-[32px] items-center gap-1 text-ui text-primary hover:underline" data-testid="meas-group-add">
          <FolderPlus className="h-4 w-4" aria-hidden="true" />Grupė
        </button>
      </div>
      {filters.kind === 'note' && (
        <p className="px-3 py-2 text-ui text-muted-foreground border-b border-border/50">Pastabos brėžinyje — sąraše žemiau.</p>
      )}
      {filters.kind !== 'note' && shown.length === 0 && items.length > 0 && !state.groups.length && (
        <p className="px-3 py-2 text-ui text-muted-foreground border-b border-border/50" data-testid="meas-filter-empty">
          Pagal pasirinktus filtrus matavimų nėra — spauskite „Rodyti visus“.
        </p>
      )}
      {filters.kind !== 'note' && sections.map((sec) => {
        const isClosed = closed.has(sec.id ?? '_loose');
        return (
          <section key={sec.id ?? '_loose'} aria-label={sec.name || 'Matavimai'} data-meas-group={sec.id ?? ''}>
            {sec.name && (
              <div
                {...dropProps(sec.id)}
                className={`flex items-center gap-1.5 px-3 min-h-[36px] border-b border-border/50 bg-muted/40 text-ui ${over === sec.id ? 'ring-2 ring-inset ring-primary bg-primary/10' : ''}`}
                data-testid={sec.id ? 'meas-group-head' : 'meas-group-loose'}
              >
                <button type="button" onClick={() => toggle(sec.id ?? '_loose')} aria-expanded={!isClosed} aria-label={isClosed ? 'Išskleisti grupę' : 'Suskleisti grupę'}
                  className="h-7 w-7 inline-flex items-center justify-center rounded text-muted-foreground hover:bg-muted">
                  {isClosed ? <ChevronRight className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                </button>
                {sec.id ? (
                  <GroupName
                    name={sec.name}
                    editing={editing === sec.id}
                    onStart={() => setEditing(sec.id)}
                    onDone={(v) => { setEditing(null); if (v != null && v.trim() && v.trim() !== sec.name) save(renameGroup(current(), sec.id, v)); }}
                  />
                ) : (
                  <span className="flex-1 min-w-0 truncate text-muted-foreground">{sec.name}</span>
                )}
                <span className="mono tabular text-muted-foreground">{sec.items.length}</span>
                {sec.id && (<>
                  <button type="button" title="Pridėti matavimų į šią grupę" aria-label={`Pridėti į ${sec.name}`}
                    onClick={() => setAdding(adding === sec.id ? null : sec.id)}
                    className="h-7 w-7 inline-flex items-center justify-center rounded text-foreground hover:bg-muted" data-testid="meas-group-pick"><Plus className="h-4 w-4" /></button>
                  <button type="button" title="Pervadinti grupę" aria-label={`Pervadinti ${sec.name}`} onClick={() => setEditing(sec.id)}
                    className="h-7 w-7 inline-flex items-center justify-center rounded text-foreground hover:bg-muted" data-testid="meas-group-rename"><Pencil className="h-3.5 w-3.5" /></button>
                  <button type="button" title="Pašalinti grupę — matavimai lieka sąraše" aria-label={`Pašalinti ${sec.name}`}
                    onClick={() => { const before = current(); save(removeGroup(before, sec.id), `Grupė „${sec.name}“ pašalinta — matavimai liko`, before); }}
                    className="h-7 w-7 inline-flex items-center justify-center rounded text-foreground hover:bg-muted" data-testid="meas-group-remove"><Trash2 className="h-3.5 w-3.5" /></button>
                </>)}
              </div>
            )}
            {sec.id && adding === sec.id && (
              <div className="px-3 py-2 border-b border-border/50 bg-card" data-testid="meas-group-picker">
                {ungroupedAll.length === 0
                  ? <p className="text-ui text-muted-foreground">Visi matavimai jau grupėse.</p>
                  : (
                    <ul className="space-y-1">
                      {ungroupedAll.map((it) => (
                        <li key={it.key}>
                          <button type="button" className="w-full text-left text-ui text-foreground hover:underline" onClick={() => moveTo(it.key, sec.id)}>
                            + {it.title || it.key}
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
              </div>
            )}
            {!isClosed && sec.id && sec.items.length === 0 && (
              <p className="px-3 py-2 text-ui text-muted-foreground border-b border-border/50">
                Tempkite matavimą čia arba spauskite „+“.
              </p>
            )}
            {!isClosed && sec.items.map((it) => (
              <div key={it.key}>{renderRow(it)}</div>
            ))}
          </section>
        );
      })}
      {/* „Be grupės" is a drop target even when everything is grouped (to take a row out) */}
      {state.groups.length > 0 && !sections.some((s) => s.id === null) && filters.kind !== 'note' && (
        <div {...dropProps(null)} className={`px-3 py-2 text-ui text-muted-foreground border-b border-border/50 ${over === null ? 'ring-2 ring-inset ring-primary bg-primary/10' : ''}`} data-testid="meas-group-loose-drop">
          Tempkite čia — išimti iš grupės
        </div>
      )}
    </div>
  );
}
