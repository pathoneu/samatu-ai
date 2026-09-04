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
 *  • the drawing is a cached server-side crop, not the EmbedPDF viewer — the
 *    viewer has no focus-region entry point that could be added without editing
 *    its files, and the crop is honest and fast;
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
  flushProjectSaves, getProject, markRoomVerified, pullProjectsFromBackend,
  updateProject,
} from '@/lib/projectStore';
import { mergeDarbuSarasasEdits } from '@/lib/mergeDarbuSarasas';
import { diffDarbuSarasas } from '@/lib/takeoffWorkflow';
import {
  adjustOpeningCount, canOverrideWholeRow, cornersFromPolygon, orderFacts,
  progressSummary, rippleText, roomIndex, roomTitle, roomsInDrawingOrder,
  setSymbolCount, stampVerified,
} from '@/lib/roomSheet';
import {
  fetchRoomFacts, overrideRoomQuantity, patchRoom, recomputeUntouched,
  saveAssumptionEdit, saveRoomEdit,
} from '@/lib/roomSheetApi';
import RoomSheetStrip from '@/components/roomsheet/RoomSheetStrip';
import RoomPlanPane from '@/components/roomsheet/RoomPlanPane';
import FactRow from '@/components/roomsheet/FactRow';
import QuantityLine from '@/components/roomsheet/QuantityLine';
import GeneralFactsPanel from '@/components/roomsheet/GeneralFactsPanel';
import { StepBar } from '@/pages/InteriorProject';

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
  const reqRef = useRef(0);

  const stage = params.get('etapas') === 'bendri' ? 'general' : 'rooms';
  const rooms = useMemo(() => roomsInDrawingOrder(project), [project]);
  const progress = useMemo(() => progressSummary(rooms), [rooms]);

  const roomNr = params.get('kambarys') ?? (rooms[0]?.nr != null ? String(rooms[0].nr) : null);
  const idx = roomIndex(rooms, roomNr);
  const room = idx >= 0 ? rooms[idx] : null;

  // Direct-URL access: the blob may not be in the local cache yet.
  useEffect(() => {
    if (project || pulled || !id) return;
    setPulled(true);
    pullProjectsFromBackend({ force: true }).then(() => setProject(getProject(id)));
  }, [project, pulled, id]);

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
  const land = useCallback((result, { fromInterior = false } = {}) => {
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
        darbu_sarasas: mergeDarbuSarasasEdits(result.darbu_sarasas, prior, notes),
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

  const saveNumber = useCallback((field, value) => run(async () => {
    if (field === 'lubu_auksciai') {
      const next = { ...((project?._overrides || {}).lubu_auksciai || {}), [String(roomNr)]: value };
      await land(await saveAssumptionEdit(project, 'lubu_auksciai', next));
      return;
    }
    // plotas_m2 / perimetras_m live on the room, so they go the room-edit way.
    await land(await saveRoomEdit(project, patchRoom(project, roomNr, { [field]: value })),
      { fromInterior: true });
  }), [run, project, roomNr, land]);

  const saveChoice = useCallback((field, value) => run(async () => {
    if (field === 'walls_paint_override') {
      const next = {
        ...((project?._overrides || {}).walls_paint_override || {}),
        [String(roomNr)]: Number(value),
      };
      await land(await saveAssumptionEdit(project, 'walls_paint_override', next));
      return;
    }
    await land(await saveRoomEdit(project, patchRoom(project, roomNr, { paskirtis: value })),
      { fromInterior: true });
  }), [run, project, roomNr, land]);

  const adjustOpening = useCallback((detail, delta) => run(async () => {
    const elementai = adjustOpeningCount(room?.elementai, detail, delta);
    await land(await saveRoomEdit(project, patchRoom(project, roomNr, { elementai })),
      { fromInterior: true });
  }), [run, project, room, roomNr, land]);

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
  }, [busy, room, id, advance]);

  // Enter → next room. Guarded on the focused element as well as on the inputs'
  // own stopPropagation, so typing a height and pressing Enter saves the field
  // rather than skipping the room.
  useEffect(() => {
    if (stage !== 'rooms') return undefined;
    const onKey = (e) => {
      if (e.key !== 'Enter' || e.metaKey || e.ctrlKey || e.altKey) return;
      const tag = e.target?.tagName;
      if (tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA'
        || e.target?.isContentEditable) return;
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
            <GeneralFactsPanel project={project} busy={busy} onSaveSymbol={saveSymbol} />
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

      <div className="flex flex-1 flex-col gap-4 p-4 lg:flex-row lg:items-start">
        {/* Left — the drawing, framed on this room. */}
        <div className="min-w-0 flex-1 lg:sticky lg:top-4 lg:basis-[52%]">
          {facts?.room
            ? (
              <RoomPlanPane
                room={facts.room}
                projectId={id}
                highlightCorners={highlightCorners}
              />
            )
            : <div className="h-64 animate-pulse rounded-[2px] bg-muted" />}
        </div>

        {/* Right — the two layers. */}
        <div className="min-w-0 flex-1 rounded-[2px] border border-border bg-card lg:basis-[48%]">
          {loading && (
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

          {!loading && !loadError && (
            <>
              <h2 className="flex items-baseline justify-between px-4 pb-2 pt-3 text-[17px] font-semibold">
                {t('project.roomSheet.factsTitle')}
                <span className="font-mono text-[13px] font-medium text-muted-foreground">
                  {t('project.roomSheet.factsCount', { count: factList.length })}
                </span>
              </h2>

              {factList.map((fact) => (
                <FactRow
                  key={fact.key}
                  fact={fact}
                  room={room}
                  busy={busy}
                  verified={seen.has(fact.key)}
                  onAccept={() => setSeen((prev) => new Set(prev).add(fact.key))}
                  onSaveNumber={saveNumber}
                  onSaveChoice={saveChoice}
                  onAdjustOpening={adjustOpening}
                />
              ))}

              <h2 className="mt-2 flex items-baseline justify-between border-t border-border px-4 pb-2 pt-3 text-[17px] font-semibold">
                {t('project.roomSheet.quantitiesTitle')}
                <span className="font-mono text-[13px] font-medium text-muted-foreground">
                  {t('project.roomSheet.quantitiesCount', { count: quantities.length })}
                </span>
              </h2>

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
              ) : quantities.map((q) => (
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
