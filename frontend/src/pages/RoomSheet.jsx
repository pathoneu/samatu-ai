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
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { ArrowRight, Check, Loader2 } from 'lucide-react';

import {
  flushProjectSaves, getProject, markRoomVerified, refreshProjectFromBackend,
  updateProject,
} from '@/lib/projectStore';
import { mergeDarbuSarasasEdits } from '@/lib/mergeDarbuSarasas';
import { diffDarbuSarasas } from '@/lib/takeoffWorkflow';
import {
  adjustOpeningCount, canOverrideWholeRow, cornersFromPolygon, openingsPatch, orderFacts,
  progressSummary, rippleText, roomIndex, roomTitle, roomTotals, roomsInDrawingOrder,
  factsStayOnScreen, setOpeningSize, setSymbolCount, stampVerified, userEditPatch,
} from '@/lib/roomSheet';
import {
  fetchRoomFacts, overrideRoomQuantity, patchRoom, recomputeUntouched, saveAssumptionEdit, saveRoomEdit, roomsOf,
} from '@/lib/roomSheetApi';
import RoomSheetStrip from '@/components/roomsheet/RoomSheetStrip';
import RoomDrawingPane from '@/components/roomsheet/RoomDrawingPane';
import FactRow from '@/components/roomsheet/FactRow';
import QuantityLine from '@/components/roomsheet/QuantityLine';
import GeneralFactsPanel from '@/components/roomsheet/GeneralFactsPanel';
import RoomScopeSwitch from '@/components/roomsheet/RoomScopeSwitch';
import { isRoomIncluded, roomFamiliesOff, withRoomFamily, withRoomIncluded } from '@/lib/scope';
import { ltPlural } from '@/lib/ltPlural';
import { ltNumber } from '@/lib/ledger';
import { pilotSession, recordPilot, releasePilotSession } from '@/lib/telemetry';
import YourRowsPanel from '@/components/roomsheet/YourRowsPanel';
import { StepBar } from '@/pages/InteriorProject';
import { RereadRoomNote } from '@/components/project/RereadDiffBanner';

const BIG = 'inline-flex min-h-[52px] w-full items-center justify-center gap-2 '
  + 'rounded-[2px] bg-[hsl(var(--accent-2))] px-4 text-[16px] font-semibold '
  + 'text-white hover:opacity-95 disabled:opacity-50 focus-visible:outline-none '
  + 'focus-visible:ring-2 focus-visible:ring-ring';

export default function RoomSheet() {
  const { t } = useTranslation();
  const { id } = useParams();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();

  const [project, setProject] = useState(() => getProject(id));
  const [pulled, setPulled] = useState(false);
  const [facts, setFacts] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [busy, setBusy] = useState(false);
  const [ripple, setRipple] = useState(null);
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
  // „Rodyti brėžinyje" on a fact: the drawing pane jumps to that fact's own place
  // ({key, nonce} — the nonce lets the same fact be asked for twice).
  const [focusRequest, setFocusRequest] = useState(null);
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

  useEffect(() => {
    loadFacts();
    setSeen(new Set());
    setRipple(null);
    setHighlightCorners(false);
  }, [loadFacts]);

  const goToRoom = useCallback((nr) => {
    const next = new URLSearchParams(params);
    next.set('kambarys', String(nr));
    next.delete('etapas');
    setParams(next, { replace: false });
  }, [params, setParams]);

  const goToGeneral = useCallback(() => {
    const next = new URLSearchParams(params);
    next.set('etapas', 'bendri');
    setParams(next, { replace: false });
  }, [params, setParams]);

  // ── Saving ────────────────────────────────────────────────────────────────

  /**
   * Land a recompute result on the project. Mirrors InteriorProject's own merge
   * — `mergeDarbuSarasasEdits` is the only thing standing between an edit and a
   * pile of deleted priced rows — with one addition: `/api/recompute-quantities`
   * returns the rebuilt rooms under `rooms` only, so they are written to BOTH
   * `patalpos` and `v8_rooms`. Writing one and not the other would leave this
   * walk (which reads `v8_rooms` first) showing the pre-edit room forever.
   */
  const land = useCallback((result, { fromInterior = false, scopeChange = false } = {}) => {
    const prior = project?.darbu_sarasas || [];
    const notes = [];
    const rebuilt = result.rooms || result.v8_rooms || result.patalpos;
    const next = fromInterior
      ? {
        ...project,
        ...result,
        name: project.name,
        company_name: project.company_name,
        vat_rate: project.vat_rate,
        // a scope choice removes rows on purpose — do not carry them back as orphans
        darbu_sarasas: mergeDarbuSarasasEdits(result.darbu_sarasas, prior, notes, undefined, { scopeChange }),
      }
      : {
        ...project,
        patalpos: rebuilt || project.patalpos,
        v8_rooms: rebuilt || project.v8_rooms,
        pozicijos: result.pozicijos || project.pozicijos,
        darbu_sarasas: mergeDarbuSarasasEdits(
          result.darbu_sarasas, prior, notes,
          (result._merge_notes || []).filter((n) => n.reason === 'relabeled')),
        _overrides: { ...(project._overrides || {}), ...(result.assumptions || {}) },
      };
    setProject(next);
    updateProject(project.id, next);
    setRipple(rippleText(diffDarbuSarasas(prior, next.darbu_sarasas || []), t));
    // The facts endpoint reads the STORED blob, and `updateProject` writes on a
    // debounce. Refetching straight away raced the write and redrew the card
    // with the pre-edit numbers while the ripple underneath announced the new
    // ones — measured in the browser: the height was already 3,10 server-side
    // and the card still read „iki 3m". Flush first, then re-read.
    return flushProjectSaves().then(loadFacts, loadFacts);
  }, [project, t, loadFacts]);

  const run = useCallback(async (work) => {
    if (busy) return;
    setBusy(true);
    try {
      await work();
    } catch (err) {
      console.error('[roomSheet] save failed:', err);
      toast.error(t('project.roomSheet.saveError', { msg: err.message }));
    } finally {
      setBusy(false);
    }
  }, [busy, t]);

  // Pilot telemetry (council verdict 5): what gets accepted, what gets fixed.
  useEffect(() => {
    pilotSession(id);
    return () => { releasePilotSession(id); };
  }, [id]);
  const pilot = useCallback((type, target = {}) => recordPilot(id, type, { room: roomNr, ...target }), [id, roomNr]);

  const saveNumber = useCallback((field, value) => run(async () => {
    pilot('fact_number', { kind: 'fact', id: field });
    if (field === 'lubu_auksciai') {
      const next = { ...((project?._overrides || {}).lubu_auksciai || {}), [String(roomNr)]: value };
      await land(await saveAssumptionEdit(project, 'lubu_auksciai', next));
      return;
    }
    // plotas_m2 / perimetras_m live on the room, so they go the room-edit way —
    // marked as his, so the sheet says so and a re-read keeps them.
    await land(await saveRoomEdit(project, patchRoom(project, roomNr, userEditPatch(field, value))),
      { fromInterior: true });
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

  const saveChoice = useCallback((field, value) => run(async () => {
    pilot('fact_choice', { kind: 'fact', id: field });
    if (field === 'walls_paint_override') {
      const next = {
        ...((project?._overrides || {}).walls_paint_override || {}),
        [String(roomNr)]: Number(value),
      };
      await land(await saveAssumptionEdit(project, 'walls_paint_override', next));
      return;
    }
    // `grindu_danga` (the covering itself) or `paskirtis` (older blobs' floor fact) —
    // both live on the room and are marked as his by `userEditPatch`.
    const roomField = field === 'grindu_danga' ? 'grindu_danga' : 'paskirtis';
    await land(await saveRoomEdit(project, patchRoom(project, roomNr, userEditPatch(roomField, value))),
      { fromInterior: true });
  }), [run, project, roomNr, land, pilot]);

  const adjustOpening = useCallback((detail, delta) => run(async () => {
    pilot('opening_adjust', { kind: 'opening', id: String(detail?.tipas ?? '') });
    const elementai = adjustOpeningCount(room?.elementai, detail, delta);
    await land(await saveRoomEdit(project, patchRoom(project, roomNr, openingsPatch(elementai))),
      { fromInterior: true });
  }), [run, project, room, roomNr, land, pilot]);

  // The size he knows replaces the standard one the reader assumed.
  const saveOpeningSize = useCallback((detail, size) => run(async () => {
    pilot('opening_size', { kind: 'opening', id: String(detail?.tipas ?? '') });
    const elementai = setOpeningSize(room?.elementai, detail, size);
    await land(await saveRoomEdit(project, patchRoom(project, roomNr, openingsPatch(elementai))),
      { fromInterior: true });
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
            <p className="mt-3 rounded-[2px] bg-[hsl(var(--surface-2))] px-3 py-2 text-[14px]">
              {ripple}
            </p>
          )}
          <div className="mt-4">
            <p className="mb-2 text-[15px] text-[hsl(var(--ink-2))]">
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
      <StepBar
        step="patikra"
        hasPdf
        setStep={(s) => navigate(s === 'patikra' ? `/project/${id}/patikra` : `/project/${id}?step=${s}`)}
      />
      <RoomSheetStrip
        title={roomTitle(room) || String(roomNr)}
        progress={progress}
        index={idx + 1}
        total={rooms.length}
        onPrev={() => goToRoom(rooms[idx - 1].nr)}
        onNext={() => goToRoom(rooms[idx + 1].nr)}
        hasPrev={idx > 0}
        hasNext={idx < rooms.length - 1}
      />
      {/* What THIS room puts into the sąmata — before any row is opened. */}
      {totals.length > 0 && (
        <div className="mx-4 mt-3 flex flex-wrap items-baseline gap-x-4 gap-y-1 text-[13px] text-[hsl(var(--ink-2))]" data-testid="room-totals">
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

      <div className="flex flex-1 flex-col gap-4 p-4 lg:flex-row lg:items-start">
        {/* Left — the drawing, framed on this room. */}
        <div className="min-w-0 flex-1 lg:sticky lg:top-4 lg:basis-[52%]">
          {facts?.room
            ? (
              <RoomDrawingPane
                project={project}
                projectId={id}
                room={facts.room}
                facts={factList}
                activeFactKey={activeFactKey}
                focusRequest={focusRequest}
                fallback={{
                  room: facts.room, projectId: id, highlightCorners, facts: factList,
                  wholeSheet, onToggleWhole: setWholeSheet, activeFactKey,
                }}
              />
            )
            : <div className="h-64 animate-pulse rounded-[2px] bg-muted" />}
        </div>

        {/* Right — the two layers. */}
        <div className="min-w-0 flex-1 rounded-[2px] border border-border bg-card lg:basis-[48%]">
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
                familiesOff={roomFamiliesOff(project?._apimtis, roomNr)}
                busy={busy}
                onChange={(on) => saveScope(withRoomIncluded(project?._apimtis, roomNr, on))}
                onFamily={(fam, on) => saveScope(withRoomFamily(project?._apimtis, roomNr, fam, on))}
              />
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
                  onFocusCapture={() => setActiveFactKey(fact.key)}
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
                    onShowOnDrawing={() => setFocusRequest((cur) => ({ key: fact.key, nonce: (cur?.nonce || 0) + 1 }))}
                  />
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
                  <p className="max-w-[46ch] text-[15px] leading-snug text-[hsl(var(--ink-2))]">
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
                  <p className="text-[15px] leading-snug text-[hsl(var(--ink-2))]">
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
                      <li key={e.row_id} className="text-[14px] leading-snug text-[hsl(var(--ink-2))]">
                        {t('project.roomSheet.excludedRow', {
                          name: e.aprasymas, reason: e.reason,
                        })}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {ripple && (
                <p className="mx-4 my-3 rounded-[2px] bg-[hsl(var(--surface-2))] px-3 py-2 text-[14px]">
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
                    className="min-h-[44px] px-2 text-[14px] font-semibold text-[hsl(var(--accent-2))] underline-offset-2 hover:underline"
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
