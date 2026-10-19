/**
 * QuantitiesPanel — „Kiekiai": Togal's Quantities Panel on Pathon's data (capability B,
 * docs/superpowers/plans/2026-10-16-togal-v2-program.md; research §5, §8).
 *
 * Tree: skyrius → sąmata line (its kiekis, unit, confidence) → the rooms that produced it (the server's
 * contributions[]). Two-way highlight with the viewer: a room row focuses the room on the sheet, a room
 * focused on the sheet lights up its rows here, hovering a row brightens its outline. Right-click opens
 * the row's actions. ↑/↓ moves the row focus, →/← opens and closes, Enter shows the room on the sheet.
 *
 * Derived from props on every render (`project.darbu_sarasas`, the rooms, hiddenRoomNrs): a recompute
 * replaces the project and the panel follows; the only local state is view state (filter, sort, which
 * rows are open, the keyboard cursor). Lines cannot be moved between families here — the engine
 * computes them, and the way to change one is Prielaidos. What he CAN do here (Pathon v3 W4-A): type a line's
 * number (double-click it, or F2; Enter saves, Esc cancels, Tab goes on to the next line — the „ranka"
 * override of lib/quantityOverride, with Atšaukti), and put a measurement on a line (drag a chip of the
 * Matavimai tray onto it, or click the chip → „Į eilutę…"); a line carrying measurements shows „iš matavimų".
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router';
import { Search } from 'lucide-react';
import { toast } from 'sonner';
import {
  ContextMenu, ContextMenuContent, ContextMenuItem, ContextMenuLabel, ContextMenuSeparator,
  ContextMenuTrigger,
} from '@/components/ui/context-menu';
import {
  SORT_ALPHA, SORT_ORDER, SORT_QUANTITY, buildQuantitiesTree, familiesWithRoom, footerTotals, visibleRowKeys,
} from '@/lib/quantitiesTree';
import { FamilyFooter, FamilyRow, RoomRow, SectionRow, TotalsFooter } from './QuantityRows';
import { getProject, updateProject } from '@/lib/projectStore';
import { updatePositionQuantity } from '@/lib/quantityOverride';
import { restoreRow } from '@/lib/measuredRows';
import { ltQuantity } from '@/lib/ledger';
import { useMeasureRows } from '@/components/project/measure/useMeasureRows';
import MeasureRowPicker from '@/components/project/measure/MeasureRowPicker';
import MeasuredChip from '@/components/project/measure/MeasuredChip';
import MeasureTray from '@/components/project/measure/MeasureTray';

const SORT_LABELS = {
  [SORT_ORDER]: 'Kaip sąmatoje',
  [SORT_ALPHA]: 'A–Ž',
  [SORT_QUANTITY]: 'Pagal kiekį',
};

// The materials list repeats the work lines' quantities in purchase units; it starts folded so the
// first screen is the work.
const START_COLLAPSED = ['section-Medžiagos'];

export default function QuantitiesPanel({
  project,
  rooms,
  focusedRoomNr = null,
  hiddenRoomNrs = null,
  onFocusRoom = null,
  onToggleRoomVisibility = null,
  onSetRoomsHidden = null,
  onIsolateRooms = null,
  onRoomRowHover = null,
  onOpenAssumptions = null,
  onActiveRowChange = null,   // (row | null) — the line under the cursor, offered to „Pokalbis"
  onAddToChat = null,         // ({kind: 'row', row} | {kind: 'room', nr}) — „Pridėti į pokalbį"
  // Pathon v3 W4-A: the panel writes — a typed quantity (double-click / F2) and measurements put on a row.
  // Without it the panel stays read-only, as before.
  onProjectChange = null,
  onJumpToPage = null,        // (page) — a measurement line's „Rodyti brėžinyje"
}) {
  const navigate = useNavigate();
  const [filter, setFilter] = useState('');
  const [sort, setSort] = useState(SORT_ORDER);
  const [collapsedSections, setCollapsedSections] = useState(() => new Set(START_COLLAPSED));
  const [expandedFamilies, setExpandedFamilies] = useState(() => new Set());
  const [activeKey, setActiveKey] = useState(null);
  const [menuTarget, setMenuTarget] = useState(null);
  const listRef = useRef(null);
  // The line whose number is being typed (family key) and the measurement whose row is being picked.
  const [editingKey, setEditingKey] = useState(null);
  const [pickerKey, setPickerKey] = useState(null);
  const measure = useMeasureRows(project, onProjectChange);
  const canWrite = !!(onProjectChange && project?.id);

  const tree = useMemo(
    () => buildQuantitiesTree(project?.darbu_sarasas, rooms, { filter, sort, hiddenRoomNrs }),
    [project?.darbu_sarasas, rooms, filter, sort, hiddenRoomNrs],
  );
  const familyByKey = useMemo(() => new Map(tree.families.map((f) => [f.key, f])), [tree]);
  const activeRow = familyByKey.get(String(activeKey || '').split('/')[0])?.row || null;
  useEffect(() => { onActiveRowChange?.(activeRow); }, [activeRow, onActiveRowChange]);
  const focusedNr = focusedRoomNr != null ? String(focusedRoomNr) : null;
  const focusedFamilies = useMemo(() => new Set(familiesWithRoom(tree, focusedNr)), [tree, focusedNr]);
  // „N eil." under the selected room counts every line it is in, not only the ones the filter shows.
  const focusedLineCount = useMemo(() => (focusedNr
    ? familiesWithRoom(buildQuantitiesTree(project?.darbu_sarasas, rooms), focusedNr).length : 0),
  [project?.darbu_sarasas, rooms, focusedNr]);
  const focusedRoom = useMemo(
    () => (focusedNr ? (rooms || []).find((r) => String(r?.nr) === focusedNr) || null : null),
    [rooms, focusedNr]);

  // While searching, everything that matched is open: a room hit has to be visible without clicks.
  const searching = filter.trim().length > 0;
  const effectiveCollapsed = useMemo(
    () => (searching ? new Set() : collapsedSections), [searching, collapsedSections]);
  const effectiveExpanded = useMemo(() => {
    if (!searching) return expandedFamilies;
    const next = new Set(expandedFamilies);
    tree.families.forEach((f) => { if (f.matchedBy === 'room') next.add(f.key); });
    return next;
  }, [searching, expandedFamilies, tree]);

  const keys = useMemo(
    () => visibleRowKeys(tree, { collapsedSections: effectiveCollapsed, expandedFamilies: effectiveExpanded }),
    [tree, effectiveCollapsed, effectiveExpanded]);

  const toggleIn = (setter, key) => setter((prev) => {
    const next = new Set(prev);
    if (next.has(key)) next.delete(key); else next.add(key);
    return next;
  });
  const toggleSection = (key) => toggleIn(setCollapsedSections, key);
  const toggleFamily = (key) => toggleIn(setExpandedFamilies, key);

  const focusRoom = useCallback((room) => {
    if (!room) return;
    onFocusRoom?.(room.room || { nr: room.nr, puslapio_nr: room.page, pavadinimas: room.name });
  }, [onFocusRoom]);

  // Sheet → panel: bring the first line the focused room is in into view.
  useEffect(() => {
    if (!focusedNr || !listRef.current) return;
    const hit = listRef.current.querySelector(`[data-qkey$="/room-${CSS.escape(focusedNr)}"]`)
      || listRef.current.querySelector('[data-focused-family="true"]');
    hit?.scrollIntoView?.({ block: 'nearest' });
  }, [focusedNr]);

  // Keyboard cursor follows into view.
  useEffect(() => {
    if (!activeKey || !listRef.current) return;
    listRef.current.querySelector(`[data-qkey="${CSS.escape(activeKey)}"]`)?.scrollIntoView?.({ block: 'nearest' });
  }, [activeKey]);

  const onKeyDown = (e) => {
    if (keys.length === 0) return;
    const idx = keys.findIndex((k) => k.key === activeKey);
    const item = idx >= 0 ? keys[idx] : null;
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      const step = e.key === 'ArrowDown' ? 1 : -1;
      const next = idx < 0 ? (step > 0 ? 0 : keys.length - 1) : Math.min(keys.length - 1, Math.max(0, idx + step));
      setActiveKey(keys[next].key);
      return;
    }
    if (!item) return;
    if (e.key === 'F2' && item.kind === 'family' && canWrite) {
      e.preventDefault();
      setEditingKey(item.key);
      return;
    }
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      if (item.kind === 'section') toggleSection(item.key);
      else if (item.kind === 'family') toggleFamily(item.key);
      else focusRoom(familyByKey.get(item.familyKey)?.rooms.find((r) => r.nr === item.nr));
    } else if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
      e.preventDefault();
      const open = e.key === 'ArrowRight';
      if (item.kind === 'section' && effectiveCollapsed.has(item.key) === open) toggleSection(item.key);
      else if (item.kind === 'family' && effectiveExpanded.has(item.key) !== open) toggleFamily(item.key);
      else if (item.kind === 'room' && !open) setActiveKey(item.familyKey);
    }
  };

  // ── Context menu: one menu for the whole list, aimed by the row under the pointer. ──
  const onListContextMenu = (e) => {
    const el = e.target.closest?.('[data-qkey]');
    const key = el?.getAttribute('data-qkey');
    const [famKey, roomKey] = String(key || '').split('/');
    const family = familyByKey.get(famKey);
    if (!family) { e.preventDefault(); setMenuTarget(null); return; }  // no row → no menu
    const room = roomKey ? family.rooms.find((r) => r.key === roomKey) : null;
    setActiveKey(key);
    setMenuTarget({ family, room });
  };

  // ── A typed quantity: Enter saves, Tab saves and opens the next line (lib/quantityOverride — the same
  // „ranka" override every other table writes; Atšaukti in the toast puts the row back as it was). ──
  const familyKeys = useMemo(() => keys.filter((k) => k.kind === 'family').map((k) => k.key), [keys]);
  const commitQuantity = (family, value, move) => {
    const at = familyKeys.indexOf(family.key);
    const nextKey = move ? familyKeys[at + move] || null : null;
    setEditingKey(nextKey);
    if (nextKey) setActiveKey(nextKey);
    const base = getProject(project.id) || project;
    const row = family.row;
    const previous = (base.darbu_sarasas || []).find((r) => (r?.id ?? r?._id) === (row.id ?? row._id)) || row;
    if (Number(previous.kiekis) === value && previous.manual_override) return;
    const rowId = row._id || `${row.eil_nr}-${row.aprasymas}`;
    let rows;
    try { rows = updatePositionQuantity(base.darbu_sarasas || [], rowId, value); } catch { return; }
    const saved = updateProject(project.id, { darbu_sarasas: rows });
    if (!saved) return;
    onProjectChange?.(saved);
    const unit = row.mato_vnt || row.vnt || '';
    toast.success(`„${row.aprasymas}“: ${ltQuantity(previous.kiekis, unit)} → ${ltQuantity(value, unit)}`, {
      description: 'Kiekį įrašėte ranka — perskaičiuojant jis nesikeis.',
      duration: 8000,
      action: {
        label: 'Atšaukti',
        onClick: () => {
          const now = getProject(project.id) || saved;
          const back = updateProject(project.id, { darbu_sarasas: restoreRow(now.darbu_sarasas, row, previous) });
          if (back) onProjectChange?.(back);
        },
      },
    });
  };
  const cancelEdit = (key) => setEditingKey((cur) => (cur === key ? null : cur));

  const recompute = () => {
    if (typeof window === 'undefined' || !project?.id) return;
    window.dispatchEvent(new CustomEvent('samatu:project-recompute', {
      detail: { projectId: project.id, reason: 'quantities-panel' },
    }));
  };

  const openCheckSheet = (room) => {
    const base = `/project/${encodeURIComponent(project.id)}/patikra`;
    navigate(room ? `${base}?kambarys=${encodeURIComponent(room.nr)}` : base);
  };

  const menuNrs = menuTarget
    ? (menuTarget.room ? [menuTarget.room.nr] : menuTarget.family.rooms.map((r) => r.nr)) : [];
  const menuAllHidden = menuTarget
    ? (menuTarget.room ? menuTarget.room.hidden : menuTarget.family.rooms.length > 0
      && menuTarget.family.rooms.every((r) => r.hidden))
    : false;
  const toggleMenuHidden = () => {
    if (!menuTarget) return;
    if (menuTarget.room) onToggleRoomVisibility?.(menuTarget.room.nr);
    else onSetRoomsHidden?.(menuNrs, !menuAllHidden);
  };
  const showMenuOnSheet = () => {
    if (!menuTarget) return;
    if (menuTarget.room) focusRoom(menuTarget.room);
    else onIsolateRooms?.(menuNrs);
  };

  const rowCount = project?.darbu_sarasas?.length || 0;

  return (
    <div className="flex flex-col h-full overflow-hidden bg-background">
      {/* Filter + sort */}
      <div className="shrink-0 flex gap-1.5 p-2.5 border-b border-border/60">
        <div className="relative flex-1">
          <Search className="absolute left-2 top-2 w-3 h-3 text-muted-foreground" />
          <input
            type="text"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Ieškoti darbo ar patalpos…"
            aria-label="Ieškoti darbo ar patalpos"
            title="Įrašykite darbo, skyriaus ar patalpos pavadinimą arba numerį"
            className="w-full pl-7 pr-2.5 text-foreground bg-card border border-border rounded outline-none focus:border-primary"
            style={{ fontSize: 12, height: 28 }}
          />
        </div>
        <select
          value={sort}
          onChange={(e) => setSort(e.target.value)}
          aria-label="Rikiuoti"
          title="Rikiuoti eilutes ir patalpas"
          className="bg-card border border-border rounded text-foreground px-1.5 outline-none focus:border-primary"
          style={{ fontSize: 12, height: 28 }}
        >
          {Object.entries(SORT_LABELS).map(([value, label]) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </select>
      </div>

      {/* Sheet → panel: which room is selected and how many lines it is in. */}
      {focusedNr && (
        <div className="shrink-0 flex items-center gap-2 px-2.5 py-1 border-b border-border/60 bg-primary/5 text-foreground/85" style={{ fontSize: 12 }}>
          <span className="truncate">
            Pasirinkta <span className="mono">{focusedNr}</span> {focusedRoom?.pavadinimas || ''}
            {' '}— {focusedLineCount} eil.
          </span>
          {filter !== focusedNr && focusedLineCount > 0 && (
            <button type="button" className="ml-auto text-primary hover:underline whitespace-nowrap" onClick={() => setFilter(focusedNr)}>
              Rodyti tik jas
            </button>
          )}
          {filter === focusedNr && (
            <button type="button" className="ml-auto text-primary hover:underline whitespace-nowrap" onClick={() => setFilter('')}>
              Rodyti visas
            </button>
          )}
        </div>
      )}

      {canWrite && <MeasureTray project={project} onPickRow={setPickerKey} />}

      <ContextMenu onOpenChange={(open) => { if (!open) setMenuTarget(null); }}>
        {/* onContextMenu sits on the Trigger, not the div: only there does Radix skip opening when the
            handler calls preventDefault (a right-click on empty space opens nothing). */}
        <ContextMenuTrigger asChild onContextMenu={onListContextMenu}>
          <div
            ref={listRef}
            role="tree"
            aria-label="Kiekiai pagal darbus ir patalpas"
            tabIndex={0}
            onKeyDown={onKeyDown}
            className="flex-1 overflow-y-auto outline-none focus-visible:ring-1 focus-visible:ring-primary/40"
          >
            {rowCount === 0 && (
              <p className="px-3 py-6 text-center text-xs text-muted-foreground">
                Kiekių dar nėra — jie atsiras, kai programa perskaitys brėžinį.
              </p>
            )}
            {rowCount > 0 && tree.sections.length === 0 && (
              <p className="px-3 py-6 text-center text-xs text-muted-foreground">
                Nieko nerasta pagal „{filter}".
              </p>
            )}
            {tree.sections.map((section) => {
              const sectionCollapsed = effectiveCollapsed.has(section.key);
              return (
                <div key={section.key} role="group">
                  <SectionRow
                    section={section}
                    collapsed={sectionCollapsed}
                    active={activeKey === section.key}
                    onToggle={() => { setActiveKey(section.key); toggleSection(section.key); }}
                  />
                  {!sectionCollapsed && section.families.map((family) => {
                    const expanded = effectiveExpanded.has(family.key);
                    const containsFocused = focusedFamilies.has(family.key);
                    return (
                      <div key={family.key} data-focused-family={containsFocused ? 'true' : undefined}>
                        <FamilyRow
                          family={family}
                          expanded={expanded}
                          active={activeKey === family.key}
                          containsFocused={containsFocused}
                          onToggle={() => { if (editingKey !== family.key) { setActiveKey(family.key); toggleFamily(family.key); } }}
                          editing={editingKey === family.key}
                          onStartEdit={canWrite ? () => { setActiveKey(family.key); setEditingKey(family.key); } : null}
                          onCommitEdit={(value, move) => commitQuantity(family, value, move)}
                          onCancelEdit={() => cancelEdit(family.key)}
                          dropProps={canWrite ? measure.dropProps(family.row) : null}
                          dropOver={!!family.row?.id && measure.overRowId === family.row.id}
                          chip={(
                            <MeasuredChip
                              row={family.row}
                              compact
                              onSetKaip={canWrite ? measure.setKaip : null}
                              onUnlink={canWrite ? measure.unlink : null}
                              onJumpToPage={onJumpToPage}
                            />
                          )}
                        />
                        {expanded && family.rooms.map((room) => {
                          const key = `${family.key}/${room.key}`;
                          return (
                            <RoomRow
                              key={key}
                              family={family}
                              room={room}
                              active={activeKey === key}
                              focused={focusedNr === room.nr}
                              onClick={() => { setActiveKey(key); focusRoom(room); }}
                              onToggleHidden={onToggleRoomVisibility ? () => onToggleRoomVisibility(room.nr) : null}
                              onMouseEnter={onRoomRowHover ? () => onRoomRowHover(room.nr) : undefined}
                              onMouseLeave={onRoomRowHover ? () => onRoomRowHover(null) : undefined}
                            />
                          );
                        })}
                        {expanded && <FamilyFooter family={family} onOpenAssumptions={onOpenAssumptions} />}
                      </div>
                    );
                  })}
                </div>
              );
            })}
          </div>
        </ContextMenuTrigger>
        <ContextMenuContent className="w-60">
          {menuTarget && (
            <>
              <ContextMenuLabel className="truncate text-xs">
                {menuTarget.room ? `${menuTarget.room.nr} ${menuTarget.room.name}` : menuTarget.family.label}
              </ContextMenuLabel>
              <ContextMenuSeparator />
              <ContextMenuItem
                onSelect={showMenuOnSheet}
                disabled={menuTarget.room ? !onFocusRoom : (!onIsolateRooms || menuNrs.length === 0)}
              >
                {menuTarget.room ? 'Rodyti brėžinyje' : 'Rodyti brėžinyje tik šias patalpas'}
              </ContextMenuItem>
              <ContextMenuItem
                onSelect={toggleMenuHidden}
                disabled={menuNrs.length === 0 || (menuTarget.room ? !onToggleRoomVisibility : !onSetRoomsHidden)}
              >
                {menuAllHidden ? 'Rodyti kontūrą' : 'Slėpti kontūrą'}
                {!menuTarget.room && menuNrs.length > 0 ? ` (${menuNrs.length})` : ''}
              </ContextMenuItem>
              {!menuTarget.room && canWrite && (
                <ContextMenuItem onSelect={() => setEditingKey(menuTarget.family.key)}>
                  Taisyti kiekį…
                </ContextMenuItem>
              )}
              <ContextMenuItem onSelect={() => openCheckSheet(menuTarget.room)}>
                {menuTarget.room ? 'Atidaryti patikros lapą' : 'Atidaryti patikrą'}
              </ContextMenuItem>
              <ContextMenuItem onSelect={recompute}>Perskaičiuoti</ContextMenuItem>
              {onAddToChat && (
                <ContextMenuItem
                  onSelect={() => onAddToChat(menuTarget.room
                    ? { kind: 'room', nr: menuTarget.room.nr }
                    : { kind: 'row', row: menuTarget.family.row })}
                >
                  {menuTarget.room ? 'Klausti pokalbyje apie šią patalpą' : 'Klausti pokalbyje apie šią eilutę'}
                </ContextMenuItem>
              )}
              <ContextMenuSeparator />
              <ContextMenuItem onSelect={() => onOpenAssumptions?.()} disabled={!onOpenAssumptions}>
                Keisti nustatymus…
              </ContextMenuItem>
              <p className="px-2 pb-1.5 pt-0.5 text-muted-foreground" style={{ fontSize: 12, lineHeight: '14px' }}>
                Eilutes skaičiuoja programa — perkelti kiekio į kitą darbą čia negalima.
              </p>
            </>
          )}
        </ContextMenuContent>
      </ContextMenu>

      {rowCount > 0 && <TotalsFooter footer={footerTotals(tree, filter)} shown={tree.families.length} all={tree.familyCount} />}
      {canWrite && (
        <MeasureRowPicker
          open={!!pickerKey}
          onOpenChange={(v) => { if (!v) setPickerKey(null); }}
          project={project}
          sourceKey={pickerKey}
          onPick={(row, kaip) => measure.link(pickerKey, row, kaip)}
        />
      )}
    </div>
  );
}
