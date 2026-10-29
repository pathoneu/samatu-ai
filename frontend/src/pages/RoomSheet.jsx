/**
 * RoomSheet — „Kambario tikrinimo lapas", one room at a time.
 *
 * The founder's direction after the council: we may never reach 100 % accuracy,
 * so perfect the CHECKING until it still saves time — not with confidence dots,
 * but with normal explanations showing how, where and what. This screen is that
 * loop: the drawing framed on the room on the left, and on the right two layers
 * — the six facts the program read (each with the pixels it read them from) and
 * the quantities it calculated from them (each with its arithmetic in real
 * numbers). One big button moves on.
 *
 * Fix semantics, and they differ on purpose:
 *  • fixing a FACT re-runs the real math and moves every quantity and the whole
 *    sąmata — through the same two endpoints the rest of the app writes with;
 *  • fixing a QUANTITY overrides only that number, and only when it can be done
 *    honestly (see `canOverrideWholeRow`); otherwise the screen says what to do
 *    instead of offering a button that cannot keep its promise.
 *
 * v1 boundaries, stated rather than hidden:
 *  • the drawing is the real viewer since 2026-09-19 (RoomDrawingPane: sharp at
 *    any zoom, the room's outline, its walls with the numbers that were added);
 *    the cached server-side crop remains as the fallback (phones, no PDF);
 *  • the per-fact „Teisinga" is a reading aid: it marks the row as looked-at for
 *    this session and drives the footer. The durable verification is the footer
 *    button, which stamps `user_verified_at` through `markRoomVerified`;
 *  • a per-room share of a shared line cannot be overridden — no backend write
 *    path exists for it yet.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router';
import { useTranslation } from '@/i18n/react';
import { toast } from 'sonner';
import { fetchOutlineAt, fetchSplitSpace } from '@/lib/roomOutlineApi';
import { nextSplitClick, outlineFailureKey, roomsWithOutline, roomsWithSplit, splitFailureKey } from '@/lib/roomOutline';
import { ArrowRight, Check, Loader2 } from 'lucide-react';

import { getProject, markRoomVerified, refreshProjectFromBackend,
  updateProject,
} from '@/lib/projectStore';
import { useProjectFixes } from '@/lib/useProjectFixes';
import { diffDarbuSarasas } from '@/lib/takeoffWorkflow';
import {
  addOpening, adjustOpeningCount, canOverrideWholeRow, cornersFromPolygon, heightsForRooms, openingsPatch, orderFacts,
  progressSummary, rippleText, roomIndex, roomTitle, roomTotals, roomsInDrawingOrder,
  alreadyInUse, factKeyForField, factsStayOnScreen, setOpeningSize, setSymbolCount, stampVerified,
  userEditPatch,
} from '@/lib/roomSheet';
import {
  fetchRoomFacts, overrideRoomQuantity, patchRoom, recomputeUntouched, saveAssumptionEdit, saveRoomEdit, roomsOf,
} from '@/lib/roomSheetApi';
import RoomSheetStrip from '@/components/roomsheet/RoomSheetStrip';
import RoomDrawingPane from '@/components/roomsheet/RoomDrawingPane';
import FactRow from '@/components/roomsheet/FactRow';
import FixConsequence from '@/components/roomsheet/FixConsequence';
import QuantityLine from '@/components/roomsheet/QuantityLine';
import GeneralFactsPanel from '@/components/roomsheet/GeneralFactsPanel';
import RoomScopeSwitch from '@/components/roomsheet/RoomScopeSwitch';
import { isRoomIncluded, roomFamiliesOff, withRoomFamily, withRoomIncluded } from '@/lib/scope';
import { formerRoomKey } from '@/lib/roomRenumber';
import { ltPlural } from '@/lib/ltPlural';
import { ltNumber } from '@/lib/ledger';
import { pilotSession, recordPilot, releasePilotSession } from '@/lib/telemetry';
import YourRowsPanel from '@/components/roomsheet/YourRowsPanel';
import { StepBar } from '@/components/project/StepRail';
import { useWorkspaceHost } from '@/components/project/workspaceHost';
import { RereadRoomNote } from '@/components/project/RereadDiffBanner';
import RoomNameChips from '@/components/roomsheet/RoomNameChips';
import { namePatch } from '@/lib/roomNames';
import { roomPickerItems, typedDigit } from '@/lib/roomSheetNav';
import { openLayerInDocument } from '@/lib/escOrder';

const BIG = 'inline-flex min-h-[52px] w-full items-center justify-center gap-2 '
  + 'rounded-[2px] bg-accent-2 px-4 text-[16px] font-semibold '
  + 'text-white hover:opacity-95 disabled:opacity-50 focus-visible:outline-none '
  + 'focus-visible:ring-2 focus-visible:ring-ring';

export default function RoomSheet() {
  const { t } = useTranslation();
  const { id } = useParams();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  // Inside the project workspace's right panel (Pathon v3): no step rail of its own (the frame has it), one
  // column (the drawing is the workspace's), and every saved state handed back to the frame's top bar.
  const host = useWorkspaceHost();
  const embedded = Boolean(host);

  const [project, setProject] = useState(() => getProject(id));
  const hostProjectChange = host?.onProjectChange;
  useEffect(() => { if (project) hostProjectChange?.(project); }, [project, hostProjectChange]);
  const [pulled, setPulled] = useState(false);
  const [facts, setFacts] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [seen, setSeen] = useState(() => new Set());
  const [overridden, setOverridden] = useState(() => new Set());
  const [highlightCorners, setHighlightCorners] = useState(false);
  // The estimate rows a room feeds are folded by default: opened on the
  // first project, they read as „daug taisymų“ beside the six facts
  // (founder, 2026-09-10). One line says what they are; the fold stays
  // open from room to room once he opens it.
  const [showQuantities, setShowQuantities] = useState(false);
  // The plan shows the WHOLE sheet by default with this room framed and every
  // fact's rectangle on it; framed-on-the-room is one click away and stays as
  // chosen from room to room. Hovering a fact row lights its rectangle.
  const [wholeSheet, setWholeSheet] = useState(true);
  const [activeFactKey, setActiveFactKey] = useState(null);
  // the fact he last clicked or tabbed into (not hovered): a digit typed now goes into its number field (C7)
  const [focusedFactKey, setFocusedFactKey] = useState(null);
  const [typed, setTyped] = useState(null);                  // {key, char, nonce}
  // „Rodyti brėžinyje" on a fact: the drawing pane jumps to that fact's own place
  // ({key, nonce} — the nonce lets the same fact be asked for twice).
  const [focusRequest, setFocusRequest] = useState(null);
  // Waiting for clicks on the drawing: `'outline'` („Parodyti patalpą", one click) or `'split'`
  // („Padalinti erdvę", two clicks — `splitFirst` is the first of them).
  const [picking, setPickingMode] = useState(false);
  const [splitFirst, setSplitFirst] = useState(null);
  const setPicking = useCallback((mode) => { setPickingMode(mode || false); setSplitFirst(null); }, []);
  const reqRef = useRef(0);

  const stage = params.get('etapas') === 'bendri' ? 'general' : 'rooms';
  const rooms = useMemo(() => roomsInDrawingOrder(project), [project]);
  const progress = useMemo(() => progressSummary(rooms), [rooms]);

  const roomNr = params.get('kambarys') ?? (rooms[0]?.nr != null ? String(rooms[0].nr) : null);
  const idx = roomIndex(rooms, roomNr);
  const room = idx >= 0 ? rooms[idx] : null;

  // A fresh copy on mount — not only when the blob is missing from the cache.
  // The facts below are computed server-side from the current blob; the cached
  // rooms can be older (a backfill, a save from another browser), and a scope
  // toggle recomputes from and saves THOSE rooms (2026-09-10).
  useEffect(() => {
    if (pulled || !id) return;
    setPulled(true);
    refreshProjectFromBackend(id).then((fresh) => { if (fresh) setProject(fresh); });
  }, [pulled, id]);

  const loadFacts = useCallback(() => {
    if (!id || roomNr == null) return;
    const req = ++reqRef.current;
    setLoading(true);
    setLoadError(false);
    fetchRoomFacts(id, roomNr)
      .then((data) => {
        if (req !== reqRef.current) return;
        setFacts(data);
        setLoading(false);
      })
      .catch((err) => {
        if (req !== reqRef.current) return;
        console.error('[roomSheet] facts failed:', err);
        setLoadError(true);
        setLoading(false);
      });
  }, [id, roomNr]);

  const goToRoom = useCallback((nr) => {
    const next = new URLSearchParams(params);
    next.set('kambarys', String(nr));
    next.delete('etapas');
    setParams(next, { replace: false });
  }, [params, setParams]);

  // the room picker's list (C7): every room with its state in words
  const pickerItems = useMemo(
    () => roomPickerItems(rooms, (nr) => isRoomIncluded(project?._apimtis, nr), roomNr)
      .map((it) => {
        // merged-into lives on the stored room (the drawing-order list may be an older copy)
        const stored = (project?.patalpos || []).find((r) => String(r?.nr) === it.nr);
        // „buvo K2" beside a room the re-read gave the drawing's number, until it is checked (v4 3a)
        const former = formerRoomKey(project, rooms.find((r) => String(r?.nr) === it.nr));
        const item = former ? { ...it, formerNr: former } : it;
        return stored?._sujungta_i && it.state !== 'merged' ? { ...item, state: 'merged', mergedInto: String(stored._sujungta_i) } : item;
      }),
    [rooms, project, roomNr],
  );

  const goToGeneral = useCallback(() => {
    const next = new URLSearchParams(params);
    next.set('etapas', 'bendri');
    setParams(next, { replace: false });
  }, [params, setParams]);

  // ── Saving ────────────────────────────────────────────────────────────────

  // Pilot telemetry (council verdict 5): what gets accepted, what gets fixed.
  useEffect(() => {
    pilotSession(id);
    return () => { releasePilotSession(id); };
  }, [id]);
  const pilot = useCallback((type, target = {}) => recordPilot(id, type, { room: roomNr, ...target }), [id, roomNr]);

  // One landing for every fix — shared with the question list (lib/useProjectFixes): the recompute result
  // merged into the project, what it moved shown under the fixed fact, and „Atšaukti pataisymą".
  const {
    busy, run, land, undoLastFix, lastFix, setLastFix, ripple, setRipple,
  } = useProjectFixes({
    project, setProject, t, afterLand: loadFacts,
    onUndo: (fix) => pilot('fact_undo', { kind: 'fact', id: fix.factKey }),
  });

  // A new room: its facts are read, and nothing of the previous room's session state carries over.
  useEffect(() => {
    loadFacts();
    setSeen(new Set());
    setRipple(null);
    setLastFix(null);
    setPicking(false);
    setHighlightCorners(false);
    setFocusedFactKey(null);
    setTyped(null);
    // the setters are stable; this runs when the ROOM changes (loadFacts is keyed on it)
  }, [loadFacts]);

  // Digits typed straight into the focused fact (C7): no „Pataisyti" click first.
  const typingRef = useRef({});
  typingRef.current = {
    busy, kind: (facts?.facts || []).find((f) => f.key === focusedFactKey)?.editable?.kind || null, key: focusedFactKey,
  };
  useEffect(() => {
    const onKey = (e) => {
      const target = e.target instanceof Element ? e.target : null;
      const cur = typingRef.current;
      if (!cur.key) return;
      const char = typedDigit(e, {
        targetTag: target?.tagName,
        targetEditable: Boolean(target?.closest?.('[contenteditable="true"]')),
        layerOpen: openLayerInDocument(),
        busy: cur.busy,
        factKind: cur.kind,
      });
      if (char == null) return;
      e.preventDefault();
      setTyped((prev) => ({ key: cur.key, char, nonce: (prev?.nonce || 0) + 1 }));
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  // `alsoRooms`: the other rooms that ask the same question (fact.same_question) — one answer, one
  // recompute, one consequence strip, one undo for all of them.
  const saveNumber = useCallback((field, value, alsoRooms = null) => run(async () => {
    pilot(alsoRooms?.length ? 'fact_number_all' : 'fact_number', { kind: 'fact', id: field });
    // the answer may be the very number the rows were built from (the assumed height, the estimate
    // he accepts) — then nothing moves, and the strip says WHY instead of a bare „nepasikeitė"
    const sameValue = alreadyInUse(project, [roomNr, ...(alsoRooms || [])], field, value);
    if (field === 'lubu_auksciai') {
      const next = heightsForRooms(project, [roomNr, ...(alsoRooms || [])], value);
      await land(await saveAssumptionEdit(project, 'lubu_auksciai', next), { factKey: factKeyForField(field), sameValue });
      return;
    }
    // plotas_m2 / perimetras_m live on the room, so they go the room-edit way —
    // marked as his, so the sheet says so and a re-read keeps them.
    await land(await saveRoomEdit(project, patchRoom(project, roomNr, userEditPatch(field, value))),
      { fromInterior: true, factKey: factKeyForField(field), sameValue });
  }), [run, project, roomNr, land, pilot]);

  // „Ką skaičiuoti" (apimtis): the whole project object changes, then every
  // row is rebuilt server-side with the new scope — same path as a room edit.
  const saveScope = useCallback((nextScope) => run(async () => {
    pilot('scope_change', { kind: 'scope', id: 'apimtis' });
    const withScope = { ...project, _apimtis: nextScope };
    setProject(withScope);
    const result = await saveRoomEdit(withScope, roomsOf(withScope));
    await land({ ...result, _apimtis: nextScope }, { fromInterior: true, scopeChange: true });
    toast.success(t('project.roomSheet.scopeSaved'));
  }), [run, project, land, t, pilot]);

  // A room the plan labels but the model never returned: added with the label
  // as its area; purpose and perimeter stay his to set on the new room's sheet.
  const addRoom = useCallback((room) => run(async () => {
    pilot('room_add', { kind: 'room', id: String(room?.nr ?? '') });
    const next = [...roomsOf(project), room];
    const result = await saveRoomEdit(project, next);
    await land(result, { fromInterior: true });
    toast.success(t('project.roomSheet.roomAdded', { nr: room.nr }));
  }), [run, project, land, t, pilot]);

  // „Ar tai virtuvė? [Taip]" (C3): the name and kind he picks, down the room edit path — one undo
  const saveName = useCallback((choice) => run(async () => {
    pilot('room_name', { kind: 'fact', id: 'pavadinimas' });
    await land(await saveRoomEdit(project, patchRoom(project, roomNr, namePatch(choice))),
      { fromInterior: true, factKey: 'pavadinimas', summary: t('project.roomNames.saved', { name: choice.pavadinimas }) });
  }), [run, project, roomNr, land, pilot, t]);

  const saveChoice = useCallback((field, value) => run(async () => {
    pilot('fact_choice', { kind: 'fact', id: field });
    if (field === 'walls_paint_override') {
      const next = {
        ...((project?._overrides || {}).walls_paint_override || {}),
        [String(roomNr)]: Number(value),
      };
      await land(await saveAssumptionEdit(project, 'walls_paint_override', next), { factKey: factKeyForField(field) });
      return;
    }
    // `grindu_danga` (the covering itself) or `paskirtis` (older blobs' floor fact) —
    // both live on the room and are marked as his by `userEditPatch`.
    const roomField = field === 'grindu_danga' ? 'grindu_danga' : 'paskirtis';
    await land(await saveRoomEdit(project, patchRoom(project, roomNr, userEditPatch(roomField, value))),
      { fromInterior: true, factKey: factKeyForField(roomField) });
  }), [run, project, roomNr, land, pilot]);

  const adjustOpening = useCallback((detail, delta) => run(async () => {
    pilot('opening_adjust', { kind: 'opening', id: String(detail?.tipas ?? '') });
    const elementai = adjustOpeningCount(room?.elementai, detail, delta);
    await land(await saveRoomEdit(project, patchRoom(project, roomNr, openingsPatch(elementai))),
      { fromInterior: true, factKey: factKeyForField('elementai') });
  }), [run, project, room, roomNr, land, pilot]);

  // „Parodyti patalpą": one click inside the room on the drawing → the wall-exact outline, its walls
  // read again (api/room_outline.py). A click that may not become an outline is said and the pick
  // stays on, so he can try another place.
  const pickOutline = useCallback((point) => run(async () => {
    if (!point) return;
    pilot('outline_pick', { kind: 'room', id: String(roomNr) });
    const answer = await fetchOutlineAt(id, roomNr, point);
    const rooms = roomsWithOutline(project, roomNr, answer);
    if (!rooms) {
      const { key, params } = outlineFailureKey(answer);
      toast.error(t(`project.roomSheet.${key}`, params));
      return;
    }
    setPicking(false);
    await land(await saveRoomEdit(project, rooms), { fromInterior: true, factKey: 'perimetras' });
  }), [run, id, project, roomNr, land, pilot, t, setPicking]);

  // „Padalinti erdvę": two clicks draw the boundary between two rooms no wall separates; BOTH rooms
  // get their outlines, the boundary is never a wall (api/room_outline.py split-space). One undo for both.
  const pickSplit = useCallback((point) => {
    const { first, request } = nextSplitClick(splitFirst, point);
    setSplitFirst(first);
    if (!request) return;
    run(async () => {
      pilot('space_split', { kind: 'room', id: String(roomNr) });
      const answer = await fetchSplitSpace(id, roomNr, request);
      const rooms = roomsWithSplit(project, answer);
      if (!rooms) {
        const { key, params } = splitFailureKey(answer);
        toast.error(t(`project.roomSheet.${key}`, params));
        return;
      }
      setPicking(false);
      await land(await saveRoomEdit(project, rooms), { fromInterior: true, factKey: 'perimetras' });
    });
  }, [run, id, project, roomNr, land, pilot, t, splitFirst, setPicking]);

  // A door or window the reader missed — one the walls show, or a standard one („+ Durys").
  const addRoomOpening = useCallback((opening) => run(async () => {
    pilot('opening_add', { kind: 'opening', id: String(opening?.tipas ?? '') });
    const elementai = addOpening(room?.elementai, opening);
    if (elementai === room?.elementai || elementai.length === 0) return;
    await land(await saveRoomEdit(project, patchRoom(project, roomNr, openingsPatch(elementai))),
      { fromInterior: true, factKey: factKeyForField('elementai') });
  }), [run, project, room, roomNr, land, pilot]);

  // The size he knows replaces the standard one the reader assumed.
  const saveOpeningSize = useCallback((detail, size) => run(async () => {
    pilot('opening_size', { kind: 'opening', id: String(detail?.tipas ?? '') });
    const elementai = setOpeningSize(room?.elementai, detail, size);
    await land(await saveRoomEdit(project, patchRoom(project, roomNr, openingsPatch(elementai))),
      { fromInterior: true, factKey: factKeyForField('elementai') });
  }), [run, project, room, roomNr, land, pilot]);

  const totals = useMemo(() => roomTotals(room), [room]);

  const overrideQuantity = useCallback((quantity, value) => run(async () => {
    const out = overrideRoomQuantity(project, quantity, roomNr, value);
    if (!out.ok) {
      toast.error(t('project.roomSheet.overrideShared'));
      return;
    }
    const next = { ...project, darbu_sarasas: out.darbu_sarasas };
    setProject(next);
    updateProject(project.id, next);
    setOverridden((prev) => new Set(prev).add(quantity.row_id));
    setRipple(rippleText(
      diffDarbuSarasas(project.darbu_sarasas || [], out.darbu_sarasas), t));
  }), [run, project, roomNr, t]);

  const saveSymbol = useCallback((key, value) => run(async () => {
    const summary = setSymbolCount(project?.detected_symbols_summary, key, value);
    const withCount = { ...project, detected_symbols_summary: summary };
    setProject(withCount);
    updateProject(project.id, withCount);
    // The builder reads the symbol counts out of the recompute context, so a
    // plain rebuild is what turns the corrected count into corrected rows.
    await land(await recomputeUntouched(withCount));
  }), [run, project, land]);

  const doRecompute = useCallback(() => run(async () => {
    await land(await recomputeUntouched(project));
  }), [run, project, land]);

  // ── Moving on ─────────────────────────────────────────────────────────────

  const advance = useCallback(() => {
    if (idx >= 0 && idx < rooms.length - 1) goToRoom(rooms[idx + 1].nr);
    else goToGeneral();
  }, [idx, rooms, goToRoom, goToGeneral]);

  const acceptRoom = useCallback(() => {
    if (busy || !room) return;
    pilot('room_verified', { kind: 'room', id: String(room.nr) });
    markRoomVerified(id, room.nr);       // canonical write: patalpos + the event
    const fresh = getProject(id);
    if (!fresh) { advance(); return; }
    // …and the same stamp on `v8_rooms`, which the store does not touch and this
    // walk reads first. Without it the strip kept saying „Patikrinta 0 iš 11".
    const at = (fresh.patalpos || [])
      .find((r) => String(r?.nr) === String(room.nr))?.user_verified_at;
    if (at && Array.isArray(fresh.v8_rooms) && fresh.v8_rooms.length) {
      const next = { ...fresh, v8_rooms: stampVerified(fresh.v8_rooms, room.nr, at) };
      updateProject(id, next);
      setProject(next);
    } else {
      setProject(fresh);
    }
    advance();
  }, [busy, room, id, advance, pilot]);

  // Enter → next room. Guarded on the focused element as well as on the inputs'
  // own stopPropagation, so typing a height and pressing Enter saves the field
  // rather than skipping the room.
  useEffect(() => {
    if (stage !== 'rooms') return undefined;
    const onKey = (e) => {
      if (e.key !== 'Enter' || e.metaKey || e.ctrlKey || e.altKey) return;
      const tag = e.target?.tagName;
      // A focused button, link or field keeps its own Enter (2026-09-15
      // review: Enter on „Pataisyti" used to stamp the room verified instead).
      if (tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA' || tag === 'BUTTON' || tag === 'A'
        || e.target?.getAttribute?.('role') === 'button' || e.target?.isContentEditable) return;
      e.preventDefault();
      acceptRoom();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [stage, acceptRoom]);

  // ── Render ────────────────────────────────────────────────────────────────

  if (!project) {
    return (
      <p className="p-8 text-[16px] text-muted-foreground">
        {pulled ? t('project.roomSheet.notFound') : t('project.roomSheet.loading')}
      </p>
    );
  }

  if (!rooms.length) {
    return <p className="p-8 text-[16px] text-muted-foreground">{t('project.roomSheet.noRooms')}</p>;
  }

  if (stage === 'general') {
    return (
      <div className="flex min-h-full flex-col bg-background">
        <RoomSheetStrip
          onQuestions={() => navigate(`/project/${id}/patikra`)}
          title={t('project.roomSheet.generalTitle')}
          progress={progress}
          index={rooms.length}
          total={rooms.length}
          onPrev={() => goToRoom(rooms[rooms.length - 1].nr)}
          hasPrev
          hasNext={false}
        />
        <div className="mx-auto w-full max-w-[900px] flex-1 p-4">
          <div className="rounded-[2px] border border-border bg-card">
            <GeneralFactsPanel project={project} busy={busy} onSaveSymbol={saveSymbol} onSaveScope={saveScope} onAddRoom={addRoom} />
          </div>
          {/* „Jūsų eilutės" — the rows of HIS template the drawing cannot answer.
              Renders nothing when the account has no template. */}
          <div className="mt-4 rounded-[2px] border border-border bg-card">
            <YourRowsPanel
              project={project}
              onProjectChange={(next) => { setProject(next); updateProject(project.id, next); }}
            />
          </div>
          {ripple && (
            <p className="mt-3 rounded-[2px] bg-surface-2 px-3 py-2 text-[14px]">
              {ripple}
            </p>
          )}
          <div className="mt-4">
            <p className="mb-2 text-[15px] text-ink-2">
              {t('project.roomSheet.finishBody', {
                verified: progress.verified, total: progress.total,
              })}
            </p>
            <button type="button" className={BIG} onClick={() => navigate(`/project/${id}?step=samata`)}>
              {t('project.roomSheet.finishCta')}
              <ArrowRight className="h-5 w-5" aria-hidden="true" />
            </button>
          </div>
        </div>
      </div>
    );
  }

  // After a fix the same room is re-read: its facts stay on screen meanwhile (lib/roomSheet).
  const keepFacts = factsStayOnScreen(facts, roomNr, loading);
  const factList = orderFacts(facts?.facts);
  const quantities = facts?.quantities || [];
  const excluded = facts?.excluded || [];
  const allSeen = factList.length > 0 && factList.every((f) => seen.has(f.key));
  // Exactly what the plan pane draws — so a quantity line only promises to have
  // marked the corners when there are dots on the drawing to look at.
  const cornersOnPlan = cornersFromPolygon(facts?.room?.polygon_pct).length > 0;

  return (
    <div className="flex min-h-full flex-col bg-background text-[16px]">
      {/* The same four steps as the project page — this sheet IS step 2. */}
      {!embedded && (
        <StepBar
          step="patikra"
          hasPdf
          projectId={id}
          setStep={(s) => navigate(s === 'patikra' ? `/project/${id}/patikra` : `/project/${id}?step=${s}`)}
        />
      )}
      <RoomSheetStrip
        onQuestions={() => navigate(`/project/${id}/patikra`)}
        title={roomTitle(room) || String(roomNr)}
        formerNr={formerRoomKey(project, room)}
        progress={progress}
        index={idx + 1}
        total={rooms.length}
        onPrev={() => goToRoom(rooms[idx - 1].nr)}
        onNext={() => goToRoom(rooms[idx + 1].nr)}
        hasPrev={idx > 0}
        hasNext={idx < rooms.length - 1}
        picker={{ items: pickerItems, onPick: goToRoom }}
      />
      {/* What THIS room puts into the sąmata — before any row is opened. */}
      {totals.length > 0 && (
        <div className="mx-4 mt-3 flex flex-wrap items-baseline gap-x-4 gap-y-1 text-[13px] text-ink-2" data-testid="room-totals">
          <span className="font-semibold uppercase tracking-wide text-muted-foreground">{t('project.roomSheet.totalsTitle')}</span>
          {totals.map((x) => (
            <span key={x.key}>
              {t(`project.roomSheet.totals.${x.key}`)}{' '}
              <span className="font-mono font-semibold text-foreground">{ltNumber(x.value, 2)} {x.unit}</span>
            </span>
          ))}
        </div>
      )}
      <RereadRoomNote project={project} roomNr={roomNr} />

      <div className={`flex flex-1 flex-col gap-4 p-4 ${embedded ? '' : 'lg:flex-row lg:items-start'}`}>
        {/* Left — the drawing, framed on this room. */}
        <div className={`min-w-0 ${embedded ? '' : 'flex-1 lg:sticky lg:top-4 lg:basis-[52%]'}`}>
          {facts?.room
            ? (
              <RoomDrawingPane
                project={project}
                projectId={id}
                room={facts.room}
                facts={factList}
                activeFactKey={activeFactKey}
                focusRequest={focusRequest}
                pick={{
                  active: Boolean(picking), mode: picking || null, first: splitFirst, busy,
                  onStart: (mode) => setPicking(mode || 'outline'),
                  onCancel: () => setPicking(false),
                  onPoint: picking === 'split' ? pickSplit : pickOutline,
                }}
                fallback={{
                  room: facts.room, projectId: id, highlightCorners, facts: factList,
                  wholeSheet, onToggleWhole: setWholeSheet, activeFactKey,
                }}
              />
            )
            : (host?.canvasReady ? null : <div className="h-64 animate-pulse rounded-[2px] bg-muted" />)}
        </div>

        {/* Right — the two layers. */}
        <div className={`min-w-0 flex-1 rounded-[2px] border border-border bg-card ${embedded ? '' : 'lg:basis-[48%]'}`}>
          {loading && !keepFacts && (
            <p className="flex items-center gap-2 p-4 text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              {t('project.roomSheet.loading')}
            </p>
          )}

          {loadError && (
            <div className="p-4">
              <p className="text-[15px]">{t('project.roomSheet.loadError')}</p>
              <button
                type="button"
                onClick={loadFacts}
                className="mt-2 inline-flex min-h-[44px] items-center rounded-[2px] border border-border bg-card px-3 font-semibold hover:bg-muted"
              >
                {t('project.roomSheet.retry')}
              </button>
            </div>
          )}

          {keepFacts && !loadError && (
            <>
              <RoomScopeSwitch
                included={isRoomIncluded(project?._apimtis, roomNr)}
                mergedInto={(project?.patalpos || []).find((r) => String(r?.nr) === String(roomNr))?._sujungta_i || null}
                familiesOff={roomFamiliesOff(project?._apimtis, roomNr)}
                busy={busy}
                onChange={(on) => saveScope(withRoomIncluded(project?._apimtis, roomNr, on))}
                onFamily={(fam, on) => saveScope(withRoomFamily(project?._apimtis, roomNr, fam, on))}
              />
              <RoomNameChips projectId={id} room={(project?.patalpos || []).find((r) => String(r?.nr) === String(roomNr)) || room} busy={busy} onAnswer={saveName} />
              {lastFix?.factKey === 'pavadinimas' && (
                <div className="px-4 pb-2" data-testid="room-name-saved">
                  {lastFix.summary && <p className="pb-1 text-[15px] font-semibold">{lastFix.summary}</p>}
                  <FixConsequence consequence={lastFix.consequence} busy={busy} onUndo={undoLastFix} />
                </div>
              )}
              <h2 className="flex items-baseline justify-between px-4 pb-2 pt-3 text-[17px] font-semibold">
                {t('project.roomSheet.factsTitle')}
                <span className="font-mono text-[13px] font-medium text-muted-foreground">
                  {t('project.roomSheet.factsCount', { count: factList.length })}
                </span>
              </h2>

              {factList.map((fact) => (
                <div
                  key={fact.key}
                  onMouseEnter={() => setActiveFactKey(fact.key)}
                  onMouseLeave={() => setActiveFactKey((k) => (k === fact.key ? null : k))}
                  onFocusCapture={() => { setActiveFactKey(fact.key); setFocusedFactKey(fact.key); }}
                  onMouseDown={() => setFocusedFactKey(fact.key)}
                  data-fact-focused={focusedFactKey === fact.key ? '1' : undefined}
                  data-testid={`fact-${fact.key}`}
                >
                  <FactRow
                    fact={fact}
                    room={room}
                    busy={busy}
                    verified={seen.has(fact.key)}
                    onAccept={() => {
                      pilot('fact_accept', { kind: 'fact', id: fact.key });
                      setSeen((prev) => new Set(prev).add(fact.key));
                    }}
                    onSaveNumber={saveNumber}
                    onSaveChoice={saveChoice}
                    onAdjustOpening={adjustOpening}
                    onSaveOpeningSize={saveOpeningSize}
                    onAddOpening={addRoomOpening}
                    onPickOutline={fact.key === 'perimetras' ? () => setPicking('outline') : null}
                    onSplitSpace={fact.key === 'perimetras' ? () => setPicking('split') : null}
                    onShowOnDrawing={() => setFocusRequest((cur) => ({ key: fact.key, nonce: (cur?.nonce || 0) + 1 }))}
                    typed={typed?.key === fact.key ? typed : null}
                  />
                  {lastFix?.factKey === fact.key && (
                    <FixConsequence consequence={lastFix.consequence} busy={busy} onUndo={undoLastFix} />
                  )}
                </div>
              ))}

              <h2 className="mt-2 flex items-baseline justify-between border-t border-border px-4 pb-2 pt-3 text-[17px] font-semibold">
                {t('project.roomSheet.quantitiesTitle')}
                <span className="font-mono text-[13px] font-medium text-muted-foreground">
                  {t('project.roomSheet.quantitiesCount', { count: quantities.length })}
                </span>
              </h2>

              {facts?.ledger_available !== false && quantities.length > 0 && (
                <div className="flex flex-wrap items-center justify-between gap-2 px-4 pb-3">
                  <p className="max-w-[46ch] text-[15px] leading-snug text-ink-2">
                    {t('project.roomSheet.quantitiesSummary', {
                      facts: `${factList.length} ${ltPlural(factList.length,
                        t('project.roomSheet.factNounOne'), t('project.roomSheet.factNounFew'),
                        t('project.roomSheet.factNounMany'))}`,
                      rows: `${quantities.length} ${ltPlural(quantities.length,
                        t('project.roomSheet.rowNounOne'), t('project.roomSheet.rowNounFew'),
                        t('project.roomSheet.rowNounMany'))}`,
                    })}
                  </p>
                  <button
                    type="button"
                    aria-expanded={showQuantities}
                    onClick={() => setShowQuantities((v) => !v)}
                    className="inline-flex min-h-[44px] items-center rounded-[2px] border border-border bg-card px-3 font-semibold hover:bg-muted"
                  >
                    {showQuantities ? t('project.roomSheet.quantitiesHide') : t('project.roomSheet.quantitiesShow')}
                  </button>
                </div>
              )}

              {facts?.ledger_available === false ? (
                <div className="px-4 pb-3">
                  <p className="text-[15px] leading-snug text-ink-2">
                    {t('project.roomSheet.noLedger')}
                  </p>
                  <button
                    type="button"
                    disabled={busy}
                    onClick={doRecompute}
                    className="mt-2 inline-flex min-h-[44px] items-center rounded-[2px] border border-border bg-card px-3 font-semibold hover:bg-muted disabled:opacity-50"
                  >
                    {busy ? t('project.roomSheet.recomputing') : t('project.roomSheet.recompute')}
                  </button>
                </div>
              ) : quantities.length === 0 ? (
                <p className="px-4 pb-3 text-[15px] text-muted-foreground">
                  {t('project.roomSheet.quantitiesEmpty')}
                </p>
              ) : !showQuantities ? null : quantities.map((q) => (
                <QuantityLine
                  key={q.row_id}
                  quantity={q}
                  busy={busy}
                  overridden={overridden.has(q.row_id)}
                  canOverride={canOverrideWholeRow(q, project.darbu_sarasas || [], roomNr)}
                  cornersOnPlan={cornersOnPlan}
                  onOverride={(v) => overrideQuantity(q, v)}
                  onExpandChange={setHighlightCorners}
                />
              ))}

              {excluded.length > 0 && (
                <div className="border-t border-border px-4 py-3">
                  <p className="text-[13px] font-semibold uppercase tracking-wide text-muted-foreground">
                    {t('project.roomSheet.excludedTitle')}
                  </p>
                  <ul className="mt-1 space-y-0.5">
                    {excluded.map((e) => (
                      <li key={e.row_id} className="text-[14px] leading-snug text-ink-2">
                        {t('project.roomSheet.excludedRow', {
                          name: e.aprasymas, reason: e.reason,
                        })}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {ripple && (
                <p className="mx-4 my-3 rounded-[2px] bg-surface-2 px-3 py-2 text-[14px]">
                  {ripple}
                </p>
              )}

              <div className="border-t border-border p-4">
                <button type="button" className={BIG} disabled={busy} onClick={acceptRoom}>
                  <Check className="h-5 w-5" aria-hidden="true" />
                  {allSeen || ripple
                    ? (idx === rooms.length - 1
                      ? t('project.roomSheet.allCorrectLast')
                      : t('project.roomSheet.savedNext'))
                    : (idx === rooms.length - 1
                      ? t('project.roomSheet.allCorrectLast')
                      : t('project.roomSheet.allCorrect'))}
                </button>
                <div className="mt-2 flex items-center justify-between">
                  <span className="text-[13px] text-muted-foreground">
                    {t('project.roomSheet.enterHint')}
                  </span>
                  <button
                    type="button"
                    onClick={advance}
                    className="min-h-[44px] px-2 text-[14px] font-semibold text-accent-2 underline-offset-2 hover:underline"
                  >
                    {t('project.roomSheet.later')}
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
