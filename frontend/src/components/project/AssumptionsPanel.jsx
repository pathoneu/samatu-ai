import React, { useState, useCallback, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { AlertCircle, ChevronDown, ChevronUp, Plus, Trash2, Info, Calculator } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { toast } from 'sonner';
import { recompute } from '../../lib/recomputeApi';
import { parseLtNumber } from '@/lib/parseLtNumber';
import { buildRecomputeContext } from '@/lib/recomputeContext';
import { rulesWithScope } from '@/lib/scope';
import { isStretchCeiling as isStretchCeilingNr, withStretchCeiling } from '@/lib/stretchCeiling';

// Every assumption edit triggers a backend recompute. Without a debounce each
// keystroke fired its own request and the answers raced (2026-07-27 audit).
const RECOMPUTE_DEBOUNCE_MS = 400;

// Plausible LT ceiling-height window (soviet 2.50 … double-height voids ~5.7).
const H_MIN_M = 2.0;
const H_MAX_M = 6.0;

// ── Helpers ───────────────────────────────────────────────────────────────────

/**
 * The room array every other surface reads (ProjectMainView, WorkspacePanel,
 * ExportDropdown, ExportModal, AiChat): `v8_rooms` when it has rooms, else the
 * legacy `patalpos`.
 *
 * This panel used to read `patalpos` unconditionally. The two arrays DO diverge
 * — on the Objektas A demo, patalpos totals 607.11 m² of dažomas plotas while
 * v8_rooms totals 561.54 (3 of 23 dev projects diverge) — so the panel showed
 * one set of numbers while the Kiekiai table and the export showed another.
 * Worse, it SEEDED /api/recompute-quantities from the stale array, so a single
 * assumption edit migrated the whole project onto the wrong numbers.
 * (2026-07-28 improvement sweep, F2.)
 */
function panelRooms(rawData) {
  return rawData?.v8_rooms?.length ? rawData.v8_rooms : (rawData?.patalpos || []);
}

function fmtM(val) {
  if (val == null) return '—';
  return `${ltDecimal(Number(val).toFixed(2))} m`;
}

// LT decimal comma for DISPLAY. Input parsing accepts both (parseLtNumber), but
// the field showed "2.8" while the rest of the app writes "2,8".
// (2026-07-28 UX walkthrough.)
function ltDecimal(val) {
  if (val == null || val === '') return '';
  return String(val).replace('.', ',');
}

/**
 * NumberInput — commits ONLY a finite, in-range number.
 *
 * The old version did `parseFloat(e.target.value) || value`, which meant:
 * 0 could never be entered, an empty field silently re-committed the previous
 * value, and a LT decimal comma was read as an integer. Now the field keeps a
 * local draft: an empty or out-of-range draft is shown with a subtle error
 * border and commits NOTHING (so no recompute fires until the number is valid).
 */
function NumberInput({ value, onChange, min, max, step = 0.01, unit, className, errorMessage, label, hint }) {
  const [draft, setDraft] = useState(() => ltDecimal(value ?? ''));
  const [invalid, setInvalid] = useState(false);
  const [focused, setFocused] = useState(false);

  // Re-sync from the committed value only while the user isn't typing —
  // otherwise a mid-typing "3." would be rewritten to "3".
  useEffect(() => {
    if (!focused) {
      setDraft(ltDecimal(value ?? ''));
      setInvalid(false);
    }
  }, [value, focused]);

  const handleChange = (e) => {
    const raw = e.target.value;
    setDraft(raw);
    if (raw.trim() === '') { setInvalid(false); return; }  // wait for a number
    const n = parseLtNumber(raw);
    const outOfRange = (min != null && n < min) || (max != null && n > max);
    if (!Number.isFinite(n) || outOfRange) { setInvalid(true); return; }
    setInvalid(false);
    onChange(n);
  };

  return (
    <div className="min-w-0">
      <div className="flex items-center gap-1.5">
        <Input
          type="text"
          inputMode="decimal"
          value={draft}
          step={step}
          onFocus={(e) => { setFocused(true); e.target.select(); }}  // typing replaces, never appends (3,22,8)
          onBlur={() => setFocused(false)}
          onChange={handleChange}
          aria-invalid={invalid || undefined}
          aria-label={label || undefined}
          /* Naked number boxes: a grid of identical fields with no accessible
             name and a tooltip that only appeared once you were already wrong.
             `hint` says what the field is for BEFORE the mistake; the range is
             appended while invalid. (2026-07-28 explainability pass.) */
          title={
            invalid && min != null && max != null
              ? `${hint ? hint + ' — ' : ''}${ltDecimal(min)}–${ltDecimal(max)}${unit ? ' ' + unit : ''}`
              : (hint || undefined)
          }
          className={`${className || 'h-7 w-20'} text-xs bg-card text-right tabular-nums ${
            invalid ? 'border-destructive text-destructive' : 'border-border'
          }`}
        />
        {unit && <span className="text-xs text-muted-foreground">{unit}</span>}
      </div>
      {/* A red border + a title tooltip was the ONLY feedback for an
          out-of-range value — invisible in practice. Say it out loud; the
          commit behaviour (nothing is written, nothing is clamped) is
          unchanged. (2026-07-28 UX walkthrough.) */}
      {invalid && errorMessage && (
        <p className="mt-0.5 text-[10px] leading-tight text-destructive" role="alert">
          {errorMessage}
        </p>
      )}
    </div>
  );
}

function Row({ label, note, children }) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-border/40 last:border-0 gap-4">
      <div className="min-w-0">
        <span className="text-sm text-foreground">{label}</span>
        {note && <p className="text-xs text-muted-foreground mt-0.5">{note}</p>}
      </div>
      <div className="shrink-0">{children}</div>
    </div>
  );
}

// ── Window/Door list editor ───────────────────────────────────────────────────

function OpeningEditor({ items, onChange, label, defaultItem }) {
  const { t } = useTranslation();
  const handleChange = (i, field, val) => {
    const next = items.map((item, idx) =>
      idx === i ? { ...item, [field]: parseInt(val) || 0 } : item
    );
    onChange(next);
  };

  const handleAdd = () => onChange([...items, { ...defaultItem }]);
  const handleRemove = i => onChange(items.filter((_, idx) => idx !== i));

  return (
    <div className="space-y-1">
      {items.map((item, i) => (
        <div key={i} className="flex items-center gap-2 text-xs">
          <span className="text-muted-foreground w-4 text-right">{i + 1}.</span>
          {item.patalpa && (
            <span className="text-muted-foreground truncate max-w-[80px]">{item.patalpa}</span>
          )}
          <Input
            type="number"
            value={item.width_mm}
            onChange={e => handleChange(i, 'width_mm', e.target.value)}
            className="h-6 w-16 text-xs bg-card border-border text-right tabular-nums"
            placeholder={t('project.assumptions.widthPlaceholder')}
            title={t('project.assumptions.openingWidthTitle', { label })}
            aria-label={t('project.assumptions.openingWidthTitle', { label })}
          />
          <span className="text-muted-foreground">×</span>
          <Input
            type="number"
            value={item.height_mm}
            onChange={e => handleChange(i, 'height_mm', e.target.value)}
            className="h-6 w-16 text-xs bg-card border-border text-right tabular-nums"
            placeholder={t('project.assumptions.heightPlaceholder')}
            title={t('project.assumptions.openingHeightTitle', { label })}
            aria-label={t('project.assumptions.openingHeightTitle', { label })}
          />
          <span className="text-muted-foreground">mm</span>
          {item.suggested && (
            <Badge
              variant="outline"
              title={t('project.assumptions.estimatedTitle')}
              className="text-[10px] border-amber-400/50 text-amber-600 py-0 px-1"
            >
              {t('project.assumptions.estimatedBadge')}
            </Badge>
          )}
          <button
            type="button"
            onClick={() => handleRemove(i)}
            title={t('project.assumptions.removeOpening', { label: label.toLowerCase() })}
            aria-label={t('project.assumptions.removeOpening', { label: label.toLowerCase() })}
            className="ml-auto text-muted-foreground hover:text-destructive"
          >
            <Trash2 className="w-3 h-3" />
          </button>
        </div>
      ))}
      <button
        onClick={handleAdd}
        className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground mt-1"
      >
        <Plus className="w-3 h-3" /> {t('project.assumptions.add', { label: label.toLowerCase() })}
      </button>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function AssumptionsPanel({
  assumptions, onChange, prielaidos, rawData, pozicijos, darbuSarasas,
  onRecomputed, defaultOpen = false, title,
  // `bare` = rendered inside the Nustatymai drawer, which supplies its own
  // title and close button; the panel's collapsible header would print the
  // heading twice and offer a collapse that makes no sense in a drawer.
  bare = false,
  // Patikra (2026-09-02): {field, roomNr, nonce} — the control „Pataisyti" or a
  // sanity warning sent the user here to change. The nonce is what makes a
  // SECOND jump to the same field scroll again.
  focusField = null,
  // Every fix is training material, but only if it is written down. The panel
  // knows the field, the room and the value it is replacing; the page owns the
  // log call. (2026-09-02.)
  onCorrection = null,
}) {
  const { t } = useTranslation();
  const resolvedTitle = title ?? t('project.assumptions.defaultTitle');
  const [open, setOpen] = useState(defaultOpen);
  const [windowsExpanded, setWindowsExpanded] = useState(false);
  const [doorsExpanded, setDoorsExpanded] = useState(false);
  const [recomputing, setRecomputing] = useState(false);

  // 2026-05-06: defensive defaults so a fresh project (assumptions={}) doesn't
  // throw when accessing lubu_auksciai[room.nr] etc.
  const safeAssumptions = assumptions || {};
  // 2026-07-05: the sample/demo project's numbers are hand-authored to look
  // complete, so they don't derive from its rooms — a recompute can't reproduce
  // them and any edit would shift the sąmata. Lock it to a pristine, view-only
  // showcase. Live editing/recompute stays fully functional on real projects.
  const isDemo = !!(rawData?.is_demo);
  const sienos_storis_m = safeAssumptions.sienos_storis_m;
  // A settings screen where NOTHING is selected tells the contractor his
  // sąmata was built with no putty level at all. Fall back to what the
  // extraction actually used, then to the LT default Q2 — the one the copy
  // calls „įprasta". (Design principle 4.)
  const glaistimo_lygis = safeAssumptions.glaistimo_lygis
    ?? prielaidos?.glaistimo_lygis ?? 'Q2';
  const lubu_auksciai = safeAssumptions.lubu_auksciai || {};
  const walls_paint_override = safeAssumptions.walls_paint_override || {};
  const custom_windows = safeAssumptions.custom_windows;
  const custom_doors = safeAssumptions.custom_doors;
  const isFallback = prielaidos?.langai_fallback;

  // Derive display windows list: custom or fallback-suggested or empty
  const displayWindows = custom_windows ?? (
    isFallback ? (prielaidos?.langai_suggested || []) : []
  );

  // Derive display doors list: custom or meta doors
  const metaDoors = rawData?.meta?.doors || [];
  const displayDoors = custom_doors ?? metaDoors;

  const setField = (field, val) => onChange({ ...safeAssumptions, [field]: val });

  // Debounced + request-ordered recompute (2026-07-27 audit):
  //  - timerRef collapses a burst of keystrokes into ONE backend call
  //  - reqIdRef makes stale answers unusable, so a slow first response can no
  //    longer overwrite the quantities produced by a newer edit
  //  - revertRef holds the assumptions as they were BEFORE the burst; on
  //    failure we roll back, because otherwise the panel kept showing the new
  //    assumption next to the OLD quantities (a silently wrong sąmata).
  const recomputeTimerRef = useRef(null);
  const reqIdRef = useRef(0);
  const revertRef = useRef(null);

  useEffect(() => () => {
    if (recomputeTimerRef.current) clearTimeout(recomputeTimerRef.current);
  }, []);

  const handleRecompute = useCallback((field, newValue, meta = null) => {
    if (!onRecomputed || isDemo) return;  // Skip if parent won't accept results, or on the view-only sample
    // Keep the OLDEST pre-edit snapshot of the burst as the rollback target.
    if (revertRef.current === null) revertRef.current = assumptions || {};
    // Write the correction down BEFORE the debounce: `assumptions` still holds
    // the pre-edit value here (the caller has already handed the new one to
    // onChange, but this component has not re-rendered yet), and a burst of
    // keystrokes on one field should still log the value the user landed on —
    // which it does, because each keystroke logs its own old→new pair.
    if (onCorrection) {
      const roomNr = meta?.roomNr != null ? String(meta.roomNr) : null;
      const prior = (assumptions || {})[field];
      onCorrection({
        field_path: roomNr ? `${field}.${roomNr}` : field,
        old_value: roomNr && prior && typeof prior === 'object' ? prior[roomNr] ?? null : prior ?? null,
        new_value: roomNr && newValue && typeof newValue === 'object'
          ? newValue[roomNr] ?? null : newValue,
        room_nr: roomNr,
        source: 'prielaidos',
      });
    }
    if (recomputeTimerRef.current) clearTimeout(recomputeTimerRef.current);
    setRecomputing(true);
    recomputeTimerRef.current = setTimeout(async () => {
      recomputeTimerRef.current = null;
      const reqId = ++reqIdRef.current;
      try {
        const result = await recompute({
          rooms: panelRooms(rawData),
          pozicijos: pozicijos || [],
          // The prices the user actually entered live here, NOT in pozicijos —
          // without them the backend merge can't tell which rows carry money.
          // (P0 2026-07-28.)
          darbu_sarasas: darbuSarasas || rawData?.darbu_sarasas || [],
          edits: [{ field, new_value: newValue }],
          // the contractor's scope choices ride on every recompute (extractor/scope.py)
          current_assumptions: rulesWithScope(assumptions, rawData?._apimtis),
          // Reader/extraction context so a ceiling-height edit rebuilds the
          // canonical pozicijos (paint iki/virš split, kampai…) without losing
          // the door/fixture/symbol lines. (2026-06-17 recompute fix.)
          // One helper shared with /recompute-interior's caller so the two
          // recompute paths cannot drift (lib/recomputeContext.js).
          context: buildRecomputeContext(rawData),
        });
        if (reqId !== reqIdRef.current) return;  // superseded by a newer edit
        revertRef.current = null;
        onRecomputed(result);
      } catch (err) {
        if (reqId !== reqIdRef.current) return;
        console.error('Recompute failed:', err);
        const revertTo = revertRef.current;
        revertRef.current = null;
        if (revertTo) onChange(revertTo);
        toast.error(t('project.assumptions.toastRecomputeErr', { msg: err.message }));
      } finally {
        if (reqId === reqIdRef.current) setRecomputing(false);
      }
    }, RECOMPUTE_DEBOUNCE_MS);
  }, [rawData, pozicijos, darbuSarasas, assumptions, onRecomputed, onChange, onCorrection, isDemo, t]);

  const setLubuAukstis = (roomNr, val) => {
    const next = { ...safeAssumptions, lubu_auksciai: { ...lubu_auksciai, [roomNr]: val } };
    onChange(next);
    handleRecompute('lubu_auksciai', next.lubu_auksciai, { roomNr });
  };

  // Bulk override — set the same height for ALL rooms at once. Useful when
  // the house has uniform ceilings and the user doesn't want to edit each
  // row individually.
  const setLubuAukstisAll = (val) => {
    const rooms = panelRooms(rawData);
    const next_lubu = {};
    rooms.forEach(r => { if (r.nr != null) next_lubu[String(r.nr)] = val; });
    const next = { ...safeAssumptions, lubu_auksciai: next_lubu };
    onChange(next);
    handleRecompute('lubu_auksciai', next_lubu);
  };

  // Per-room finishing override (2026-07-05). Some rooms (garažas, tambūras)
  // default to raw/unpainted walls; when a contractor finishes them the user
  // flips this and the paint quantities recalc live (same path as ceiling height).
  const setWallsPaint = (roomNr, painted) => {
    const next = {
      ...safeAssumptions,
      walls_paint_override: { ...walls_paint_override, [roomNr]: painted ? 1 : 0 },
    };
    onChange(next);
    handleRecompute('walls_paint_override', next.walls_paint_override, { roomNr });
  };
  const isWallsPainted = (room) => {
    const ov = walls_paint_override[room.nr];
    if (ov != null) return Number(ov) >= 0.5;
    return Number(room.walls_paintable_m2 || 0) > 0;
  };

  // Per-room ĮTEMPIAMOS LUBOS (2026-09-02 contractor ask). A stretch ceiling is
  // a separate trade stretched under a raw slab, so the room's ceiling
  // glaistymas/gruntavimas/dažymas/šlifavimas is work nobody performs — the
  // backend drops it from the sąmata. Karnizas, LED nišos, GKP lubos and
  // grindjuostės stay. Absent key = dažomos, so nothing changes until the
  // user actually flips a room.
  const setStretchCeiling = (roomNr, stretch) => {
    const next = withStretchCeiling(safeAssumptions, roomNr, stretch);
    onChange(next);
    handleRecompute('stretch_ceiling_override', next.stretch_ceiling_override, { roomNr });
  };
  const isStretchCeiling = (room) => isStretchCeilingNr(safeAssumptions, room.nr);

  // Land on the control that was named, not at the top of a long panel. The
  // panel can arrive collapsed (Prielaidos tab opens it, a sanity jump may not),
  // so open it first and scroll on the NEXT frame, once the section is laid out.
  const rootRef = useRef(null);
  useEffect(() => {
    if (!focusField?.field) return undefined;
    setOpen(true);
    // A macrotask, NOT requestAnimationFrame: rAF does not fire while the tab is
    // in the background, so a jump made from a hidden tab (or a browser that
    // throttles frames) silently did nothing. `setOpen(true)` has been flushed
    // by the time this runs, so the section is laid out either way.
    const timer = window.setTimeout(() => {
      const selector = focusField.roomNr != null
        ? `[data-assumption="${focusField.field}:${focusField.roomNr}"]`
        : `[data-assumption^="${focusField.field}:"]`;
      const el = rootRef.current?.querySelector(selector);
      if (!el) return;
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      // A ring the user can actually see arriving, then gone — a permanent
      // highlight reads as "this field is in an error state".
      el.style.outline = '2px solid hsl(var(--primary))';
      el.style.outlineOffset = '2px';
      window.setTimeout(() => {
        el.style.outline = '';
        el.style.outlineOffset = '';
      }, 2400);
      const field = el.matches('input, button') ? el : el.querySelector('input, button');
      field?.focus?.({ preventScroll: true });
    }, 0);
    return () => window.clearTimeout(timer);
  }, [focusField?.field, focusField?.roomNr, focusField?.nonce]);

  const rooms = panelRooms(rawData);
  const avgH  = rooms.length > 0
    ? rooms.reduce((s, r) => s + (Number(r.lubu_aukstis_m) || 2.80), 0) / rooms.length
    : 2.80;

  return (
    <div ref={rootRef} className={bare ? '' : 'border border-border rounded-xl overflow-hidden'}>
      {!bare && (
      <button
        className="w-full flex items-center justify-between px-4 py-3 bg-card hover:bg-muted/40 transition-colors"
        onClick={() => setOpen(v => !v)}
        title={t('project.assumptions.headerTitle')}
        aria-expanded={open}
      >
        <span className="flex items-center gap-2 text-sm font-semibold text-foreground">
          <Info className="w-4 h-4 text-muted-foreground" />
          {resolvedTitle}
          {isFallback && (
            <Badge className="text-xs bg-amber-500/15 text-amber-300 border-amber-500/30 border font-normal">
              {t('project.assumptions.windowsFallbackBadge')}
            </Badge>
          )}
        </span>
        {open ? <ChevronUp className="w-4 h-4 text-muted-foreground" /> : <ChevronDown className="w-4 h-4 text-muted-foreground" />}
      </button>
      )}

      {(open || bare) && (
        <div className={`${bare ? '' : 'px-4 '}pb-4 pt-1 space-y-1${isDemo ? ' pointer-events-none' : ''}`}>

          {/* Intro: explain that edits live-recalculate everything in the
              right panel (Kiekiai). On the view-only sample, explain instead
              that these are the AI's assumptions and editing is disabled. */}
          {isDemo ? (
            <div className="flex items-start gap-2 p-3 bg-primary/10 border border-primary/30 rounded-lg mb-3">
              <Info className="w-4 h-4 shrink-0 mt-0.5 text-primary" />
              <p className="text-xs text-foreground leading-relaxed">
                {t('project.assumptions.demoReadonly')}
              </p>
            </div>
          ) : (
            <p className="text-xs text-muted-foreground mb-3 leading-relaxed">
              {t('project.assumptions.intro')}
              {' '}
              {/* Not every row survives a recompute — rows the backend cannot
                  rebuild are carried over with their ORIGINAL numbers and a
                  warning toast. Say so here so the toast isn't a surprise.
                  (2026-07-28 explainability pass.) */}
              {t('project.assumptions.introOrphans')}
            </p>
          )}

          {/* Window fallback warning */}
          {isFallback && (
            <div className="flex items-start gap-2 p-3 bg-amber-500/10 border border-amber-500/30 rounded-lg text-sm text-amber-300 mb-3">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <div>
                <p className="font-medium">{t('project.assumptions.windowsNotFound')}</p>
                <p className="text-xs mt-0.5">
                  {t('project.assumptions.windowsNotFoundDesc')}
                </p>
              </div>
            </div>
          )}

          {/* Glaistymo lygis */}
          <Row
            label={t('project.assumptions.puttyLevel')}
            note={t('project.assumptions.puttyLevelNote')}
          >
            {/* Design §3, word for word: „Q2 — po matiniais dažais (įprasta)"
                / „Q3 — po pusiau blizgiais" / „Q4 — po blizgiais, pilnas
                glaistymas". Q1 stays reachable (it is under heavy wallpaper and
                a real choice) but is named the same way. A bare Q1–Q4 chip row
                is a spec-sheet, not a question a contractor can answer. */}
            <div className="flex flex-col items-stretch gap-1.5 w-full">
              {['Q1','Q2','Q3','Q4'].map(q => (
                <button
                  key={q}
                  onClick={() => { setField('glaistimo_lygis', q); handleRecompute('glaistimo_lygis', q); }}
                  title={t(`project.assumptions.puttyLevelTitles.${q}`)}
                  aria-pressed={glaistimo_lygis === q}
                  className={`text-left rounded border transition-colors ${
                    glaistimo_lygis === q
                      ? 'bg-primary/10 text-foreground border-primary font-medium'
                      : 'bg-card text-muted-foreground border-border hover:border-foreground/30'
                  }`}
                  style={{ minHeight: 44, padding: '0 12px', fontSize: 15 }}
                >
                  {t(`project.assumptions.puttyLevelPlain.${q}`)}
                </button>
              ))}
            </div>
          </Row>

          {/* Santechnika: potinkiniai ar virštinkiniai maišytuvai.
              The backend defaults to CONCEALED (LT convention: an in-wall body
              during rough-in + visible trim after tiling = two separate jobs,
              two lines). Measured against four real sąmatos, 3 of 4 contractors
              build concealed but only 2 of 4 BILL it as a pair — one bundles it
              into a single line, and one project's own text says "(ne
              potinkinės)". So this is a genuine per-project convention, and the
              contractor must be able to flip it. (2026-07-29) */}
          <Row
            label={t('project.assumptions.concealedMixers')}
            note={t('project.assumptions.concealedMixersNote')}
          >
            <div className="flex gap-1">
              {[['true', t('project.assumptions.concealedYes')],
                ['false', t('project.assumptions.concealedNo')]].map(([val, lbl]) => {
                const on = String(safeAssumptions.santechnika_potinkinis ?? true) === val;
                return (
                  <button
                    key={val}
                    onClick={() => {
                      const v = val === 'true';
                      setField('santechnika_potinkinis', v);
                      handleRecompute('santechnika_potinkinis', v);
                    }}
                    title={t(`project.assumptions.concealedTitles.${val}`)}
                    aria-pressed={on}
                    className={`rounded border font-medium transition-colors ${
                      on
                        ? 'bg-primary/10 text-foreground border-primary'
                        : 'bg-card text-muted-foreground border-border hover:border-foreground/30'
                    }`}
                    style={{ minHeight: 44, padding: '0 14px', fontSize: 15 }}
                  >
                    {lbl}
                  </button>
                );
              })}
            </div>
          </Row>

          {/* Vidaus durys: beapvadinės ar su apvadais (2026-09-23). The drawing's text (a door schedule, a
              note, the openings annotated for frameless doors, the door products on a finish board) decides
              it when it says anything; the plan's symbols alone only propose. His choice here wins over all
              of it — the same `_overrides.vidaus_durys_beapvadines` the Patikra question writes. */}
          <Row
            label={t('project.assumptions.framelessDoors')}
            note={[t('project.assumptions.framelessDoorsNote'), rawData?._paruosimas?.frameless?.sakinys].filter(Boolean).join(' ')}
          >
            <div className="flex gap-1">
              {[['true', t('project.assumptions.framelessYes')],
                ['false', t('project.assumptions.framelessNo')]].map(([val, lbl]) => {
                const current = safeAssumptions.vidaus_durys_beapvadines ?? rawData?._paruosimas?.frameless?.value ?? false;
                const on = String(Boolean(current)) === val;
                return (
                  <button
                    key={val}
                    onClick={() => {
                      const v = val === 'true';
                      setField('vidaus_durys_beapvadines', v);
                      handleRecompute('vidaus_durys_beapvadines', v);
                    }}
                    title={t(`project.assumptions.framelessTitles.${val}`)}
                    aria-pressed={on}
                    data-assumption={`vidaus_durys_beapvadines:${val}`}
                    className={`rounded border font-medium transition-colors ${
                      on
                        ? 'bg-primary/10 text-foreground border-primary'
                        : 'bg-card text-muted-foreground border-border hover:border-foreground/30'
                    }`}
                    style={{ minHeight: 44, padding: '0 14px', fontSize: 15 }}
                  >
                    {lbl}
                  </button>
                );
              })}
            </div>
          </Row>

          {/* Angokraščiai — kurių angų (2026-09-25). The drawing shows the openings; which reveals the finisher
              bills is his scope: windows, exterior doors and door-less passages by default, interior doors
              off (their reveals sit under architraves or on the frameless-door row). Same
              `_overrides.angokrasciai_apimtis` the engine reads (universal_rules.settle_reveals_scope). */}
          <Row
            label={t('project.assumptions.revealsScope')}
            note={[t('project.assumptions.revealsScopeNote'), rawData?._paruosimas?.angokrasciai?.sakinys].filter(Boolean).join(' ')}
          >
            <div className="flex flex-wrap gap-1">
              {['langai', 'lauko_durys', 'praejimai', 'vidaus_durys'].map((kind) => {
                const defaults = { langai: true, lauko_durys: true, praejimai: true, vidaus_durys: false };
                const current = {
                  ...defaults,
                  ...(rawData?._paruosimas?.angokrasciai?.value || {}),
                  ...(safeAssumptions.angokrasciai_apimtis || {}),
                };
                const on = Boolean(current[kind]);
                return (
                  <button
                    key={kind}
                    type="button"
                    onClick={() => {
                      const next = { ...current, [kind]: !on };
                      setField('angokrasciai_apimtis', next);
                      handleRecompute('angokrasciai_apimtis', next);
                    }}
                    title={t(`project.assumptions.revealKindTitles.${kind}`)}
                    aria-pressed={on}
                    data-assumption={`angokrasciai_apimtis:${kind}:${on ? 'on' : 'off'}`}
                    className={`rounded border font-medium transition-colors ${
                      on
                        ? 'bg-primary/10 text-foreground border-primary'
                        : 'bg-card text-muted-foreground border-border hover:border-foreground/30'
                    }`}
                    style={{ minHeight: 44, padding: '0 14px', fontSize: 15 }}
                  >
                    {on ? '✓ ' : ''}{t(`project.assumptions.revealKinds.${kind}`)}
                  </button>
                );
              })}
            </div>
          </Row>

          {/* Sienos storis */}
          <Row
            label={t('project.assumptions.wallThickness')}
            note={t('project.assumptions.wallThicknessNote')}
          >
            <NumberInput
              value={sienos_storis_m}
              onChange={v => { setField('sienos_storis_m', v); handleRecompute('sienos_storis_m', v); }}
              min={0.05} max={0.50} step={0.01} unit="m"
              label={t('project.assumptions.wallThickness')}
              hint={t('project.assumptions.wallThicknessHint')}
              errorMessage={t('project.assumptions.wallThicknessRangeErr', {
                min: ltDecimal('0.05'), max: ltDecimal('0.50'),
              })}
            />
          </Row>

          {/* ── Per-room settings ────────────────────────────────────────
              Design §4 says these belong on the room's own sheet, not in a
              project-wide settings panel. They stay HERE until that sheet
              exists: the room grid (RoomsGrid/RoomCard) edits plotas,
              perimetras and paskirtis but exposes no height, no walls-painted
              and no stretch-ceiling toggle, and it is not reachable from the
              UI at all. Removing them now would delete the only way to fix a
              defaulted 2,80 m. Move them the day the room sheet ships. */}
          {rooms.length > 0 && (
            <div className="mt-5 pt-4 border-t border-border">
              <h3 className="text-foreground font-medium" style={{ fontSize: 15 }}>
                {t('project.assumptions.perRoomHeading')}
              </h3>
              <p className="text-muted-foreground mt-0.5" style={{ fontSize: 13 }}>
                {t('project.assumptions.perRoomNote')}
              </p>
            </div>
          )}

          {/* Lubų aukštis per kambarį */}
          {rooms.length > 0 && (
            <div className="py-2">
              <p className="text-sm text-foreground mb-1">
                {t('project.assumptions.ceilingHeightLabel')}<span className="text-xs text-muted-foreground">{t('project.assumptions.ceilingHeightDefault', { avg: ltDecimal(avgH.toFixed(2)) })}</span>
              </p>
              <p className="text-xs text-muted-foreground mb-2 leading-relaxed">
                {t('project.assumptions.ceilingHeightNote')}
              </p>

              {/* 2026-05-06: bulk override — set all rooms' aukštis at once.
                  Works for the common case where the whole house has the same
                  height; user can then tweak individual rooms below if needed. */}
              <div className="mb-3 flex items-center gap-2 px-2 py-2 rounded-md bg-muted/40 border border-border/60">
                <span className="text-xs font-medium text-foreground flex-1">
                  {t('project.assumptions.allRooms')}
                </span>
                <Input
                  type="text"
                  inputMode="decimal"
                  /* „Lubų aukštis, jei žinote" from the upload screen lands
                     here — the one place the upload copy promises it will. */
                  defaultValue={Number(rawData?.lubu_aukstis_default_m) > 0
                    ? ltDecimal(Number(rawData.lubu_aukstis_default_m).toFixed(2)) : ''}
                  placeholder={ltDecimal(avgH.toFixed(2))}
                  step={0.05}
                  onBlur={e => {
                    const raw = e.target.value.trim();
                    if (!raw) return;                       // nothing typed — no-op
                    const v = parseLtNumber(raw);
                    // Same 2.0–6.0 window the per-room inputs enforce; out of
                    // range is reported, not silently clamped or ignored.
                    if (!Number.isFinite(v) || v < H_MIN_M || v > H_MAX_M) {
                      toast.error(t('project.assumptions.heightRangeErr', {
                        min: ltDecimal(H_MIN_M.toFixed(2)),
                        max: ltDecimal(H_MAX_M.toFixed(2)),
                      }));
                      return;
                    }
                    setLubuAukstisAll(v);
                    e.target.value = '';
                  }}
                  onKeyDown={e => {
                    if (e.key === 'Enter') {
                      e.target.blur();
                    }
                  }}
                  className="h-7 w-20 text-xs bg-card border-border text-right tabular-nums"
                  title={t('project.assumptions.allRoomsTitle')}
                />
                <span className="text-xs text-muted-foreground">m</span>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                {rooms.map(room => (
                  <div
                    key={room.nr}
                    data-assumption={`lubu_auksciai:${room.nr}`}
                    className="flex items-center gap-2 rounded transition-colors"
                  >
                    <span className="text-xs text-muted-foreground truncate flex-1" title={room.pavadinimas}>
                      {room.pavadinimas || room.nr}
                    </span>
                    {/* Blanking this field used to commit 2.8 m and fire a
                        recompute; NumberInput now waits for a valid number. */}
                    <NumberInput
                      value={lubu_auksciai[room.nr] ?? (Number(room.lubu_aukstis_m) || 2.80)}
                      min={H_MIN_M} max={H_MAX_M} step={0.05}
                      unit="m"
                      className="h-6 w-16"
                      label={t('project.assumptions.roomHeightAria', {
                        room: room.pavadinimas || room.nr,
                      })}
                      hint={t('project.assumptions.roomHeightHint', {
                        room: room.pavadinimas || room.nr,
                      })}
                      errorMessage={t('project.assumptions.heightRangeErr', {
                        min: ltDecimal(H_MIN_M.toFixed(2)),
                        max: ltDecimal(H_MAX_M.toFixed(2)),
                      })}
                      onChange={v => setLubuAukstis(room.nr, v)}
                    />
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Sienų apdaila per kambarį — dažomos vs nedažomos (2026-07-05).
              Garažas/tambūras pagal nutylėjimą nedažomi; užbaigtiems projektams
              vartotojas perjungia ir kiekiai persiskaičiuoja gyvai. */}
          {rooms.length > 0 && (
            <div className="py-2">
              <p className="text-sm text-foreground mb-1">
                {t('project.assumptions.wallsPaintLabel')}
              </p>
              <p className="text-xs text-muted-foreground mb-2 leading-relaxed">
                {t('project.assumptions.wallsPaintNote')}
              </p>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                {rooms.map(room => {
                  const painted = isWallsPainted(room);
                  return (
                    <button
                      key={room.nr}
                      data-assumption={`walls_paint_override:${room.nr}`}
                      onClick={() => setWallsPaint(room.nr, !painted)}
                      title={t(painted ? 'project.assumptions.wallsPaintOffTitle' : 'project.assumptions.wallsPaintOnTitle', {
                        room: room.pavadinimas || room.nr,
                      })}
                      aria-pressed={painted}
                      className={`flex items-center justify-between gap-1.5 px-2 py-1.5 rounded text-xs border transition-colors ${
                        painted
                          ? 'bg-primary/10 border-primary/40 text-foreground'
                          : 'bg-card border-border text-muted-foreground hover:border-foreground/30'
                      }`}
                    >
                      <span className="truncate">{room.pavadinimas || room.nr}</span>
                      <span className={`shrink-0 text-[10px] font-medium ${painted ? 'text-primary' : 'text-muted-foreground'}`}>
                        {painted ? t('project.assumptions.wallsPaintOn') : t('project.assumptions.wallsPaintOff')}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* Lubų apdaila per kambarį — dažomos vs įtempiamos (2026-09-02).
              Įtempiamos lubos = atskiras darbas; tos patalpos lubų glaistymas,
              gruntavimas, dažymas ir šlifavimas iškrenta iš sąmatos. Karnizas,
              LED nišos, GKP lubos ir grindjuostės nekeičiami. */}
          {rooms.length > 0 && (
            <div className="py-2">
              <p className="text-sm text-foreground mb-1">
                {t('project.assumptions.stretchCeilingLabel')}
              </p>
              <p className="text-xs text-muted-foreground mb-2 leading-relaxed">
                {t('project.assumptions.stretchCeilingNote')}
              </p>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                {rooms.map(room => {
                  const stretch = isStretchCeiling(room);
                  return (
                    <button
                      key={room.nr}
                      data-assumption={`stretch_ceiling_override:${room.nr}`}
                      onClick={() => setStretchCeiling(room.nr, !stretch)}
                      title={t(stretch ? 'project.assumptions.stretchCeilingOffTitle' : 'project.assumptions.stretchCeilingOnTitle', {
                        room: room.pavadinimas || room.nr,
                      })}
                      aria-pressed={stretch}
                      className={`flex items-center justify-between gap-1.5 px-2 py-1.5 rounded text-xs border transition-colors ${
                        stretch
                          ? 'bg-primary/10 border-primary/40 text-foreground'
                          : 'bg-card border-border text-muted-foreground hover:border-foreground/30'
                      }`}
                    >
                      <span className="truncate">{room.pavadinimas || room.nr}</span>
                      <span className={`shrink-0 text-[10px] font-medium ${stretch ? 'text-primary' : 'text-muted-foreground'}`}>
                        {stretch ? t('project.assumptions.stretchCeilingOn') : t('project.assumptions.stretchCeilingOff')}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* Langai */}
          <div className="py-2 border-b border-border/40">
            <button
              className="flex items-center justify-between w-full mb-2"
              onClick={() => setWindowsExpanded(v => !v)}
              title={t('project.assumptions.windowsTitle')}
              aria-expanded={windowsExpanded}
            >
              <span className="text-sm text-foreground">
                {t('project.assumptions.windows')}
                <span className="text-xs text-muted-foreground ml-2">
                  {t('project.assumptions.windowsCount', { count: displayWindows.length })}
                  {isFallback && !custom_windows && <span className="text-amber-600 ml-1">{t('project.assumptions.windowsFallback')}</span>}
                </span>
              </span>
              {windowsExpanded
                ? <ChevronUp className="w-3.5 h-3.5 text-muted-foreground" />
                : <ChevronDown className="w-3.5 h-3.5 text-muted-foreground" />
              }
            </button>
            {windowsExpanded && (
              <OpeningEditor
                items={displayWindows}
                onChange={wins => { setField('custom_windows', wins); handleRecompute('custom_windows', wins); }}
                label={t('project.assumptions.windowLabel')}
                defaultItem={{ width_mm: 1200, height_mm: 1500 }}
              />
            )}
          </div>

          {/* Durys */}
          <div className="py-2">
            <button
              className="flex items-center justify-between w-full mb-2"
              onClick={() => setDoorsExpanded(v => !v)}
              title={t('project.assumptions.doorsTitle')}
              aria-expanded={doorsExpanded}
            >
              <span className="text-sm text-foreground">
                {t('project.assumptions.doors')}
                <span className="text-xs text-muted-foreground ml-2">{t('project.assumptions.doorsCount', { count: displayDoors.length })}</span>
              </span>
              {doorsExpanded
                ? <ChevronUp className="w-3.5 h-3.5 text-muted-foreground" />
                : <ChevronDown className="w-3.5 h-3.5 text-muted-foreground" />
              }
            </button>
            {doorsExpanded && (
              <OpeningEditor
                items={displayDoors}
                onChange={ds => { setField('custom_doors', ds); handleRecompute('custom_doors', ds); }}
                label={t('project.assumptions.doorLabel')}
                defaultItem={{ width_mm: 800, height_mm: 2200 }}
              />
            )}
          </div>

          {recomputing && (
            <p className="text-xs text-muted-foreground pt-1">
              {t('project.assumptions.recomputing')}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

// ── Calculation formulas card (Phase 14 / QW03) ──────────────────────────────
//
// Surfaces the universal LT interior formulas applied to this project.
// Values from the current Prielaidos panel are plugged in so the user can see
// exactly which numbers their toggles change. Sources: CLAUDE.md §1.

const Q_LEVEL_KG_PER_M2_MM = { Q1: 0.8, Q2: 1.0, Q3: 1.2, Q4: 1.5 };

function FormulaRow({ name, formula, current, source }) {
  return (
    <li className="space-y-0.5 pb-2 last:pb-0 border-b last:border-0 border-border/40">
      <div className="text-xs font-semibold text-foreground">{name}</div>
      <code className="block text-[11px] text-muted-foreground font-mono whitespace-pre-wrap leading-relaxed">
        {formula}
      </code>
      {current && (
        <div className="text-[11px] text-foreground/80">
          <span className="text-muted-foreground">Su jūsų prielaidomis: </span>
          <span className="font-mono">{current}</span>
        </div>
      )}
      {source && (
        <div className="text-[10px] text-muted-foreground/70">{source}</div>
      )}
    </li>
  );
}

function FormulasCard({ sienosStorisM, glaistimoLygis }) {
  const [open, setOpen] = useState(false);
  const qCoef = Q_LEVEL_KG_PER_M2_MM[glaistimoLygis] ?? 1.0;
  const reveal = (sienosStorisM ?? 0).toFixed(2);

  return (
    <div className="mt-3 border border-border rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(v => !v)}
        className="w-full flex items-center justify-between px-3 py-2 bg-muted/30 hover:bg-muted/50 transition-colors text-left"
      >
        <span className="flex items-center gap-2 text-xs font-semibold text-foreground">
          <Calculator className="w-3.5 h-3.5 text-muted-foreground" />
          Skaičiavimo formulės
          <span className="text-[10px] font-normal text-muted-foreground">
            (kaip kiekvienas skaičius gaunamas)
          </span>
        </span>
        {open
          ? <ChevronUp className="w-3.5 h-3.5 text-muted-foreground" />
          : <ChevronDown className="w-3.5 h-3.5 text-muted-foreground" />}
      </button>

      {open && (
        <ul className="px-3 py-2 space-y-2">
          <FormulaRow
            name="Sienų dažomas plotas"
            formula="S_neto = perimetras × lubų_aukštis − Σ(angos > 0.5 m²) + lubos"
            source="RICS NRM2 §29 — angos < 0.5 m² neatimamos"
          />
          <FormulaRow
            name="Angokraščiai (langai/durys)"
            formula="ilgis = 2 × H + W;  plotas = ilgis × sienos_storis"
            current={`sienos_storis = ${reveal} m`}
            source="CLAUDE.md §1.2"
          />
          <FormulaRow
            name="Glaistymas"
            formula={`kg = plotas × storis_mm × Q_koef\nQ_koef: Q1=0.8 · Q2=1.0 · Q3=1.2 · Q4=1.5 kg/m²/mm`}
            current={`Q_koef = ${qCoef} (lygis ${glaistimoLygis})`}
            source="CLAUDE.md §1.11"
          />
          <FormulaRow
            name="Dažų kiekis"
            formula="l = (plotas × sluoksniai) / coverage_m²/l\ncoverage: glaistytas Q2 ~9 · šviežias tinkas ~4 · gruntas ~7"
            source="2 sluoksniai = ×1.8 (ne ×2 — pirmas sluoksnis sugeria daugiau)"
          />
          {/* 2026-10-03 (audit calc-engine-5): the formula as the engine computes
              it (universal_rules.calc_room_quantities) — it used to read
              „išorinių kampų skaičius × lubų aukštis", which is not the math. */}
          <FormulaRow
            name="Glaistymo kampai"
            formula={'kampų_metrai = perimetras (sienų ir lubų sandūra)\n'
              + '  + kampų_skaičius × lubų_aukštis (vidiniai kampai, jei skaičiuojami)\n'
              + '  + durų_sk. × (0,9 + 2 × 2,05) + langų_sk. × (1,2 + 2 × 1,5) (angų kraštai)\n'
              + '  + pertvarų_sandūrų_sk. × lubų_aukštis'}
            source="Angų kraštai skaičiuojami pagal standartinį durų ir lango dydį, ne pagal brėžinio matmenis. Vidinius kampus įjungia arba išjungia „Ką skaičiuoti“ → „Dažymo kampai (kampuotės)“."
          />
          <FormulaRow
            name="Grindjuostės"
            formula="ilgis = perimetras − Σ(durų_plotis) + 10% atliekų"
            source="CLAUDE.md §1.4"
          />
          <FormulaRow
            name="Lubų perimetras (karnizas)"
            formula="ilgis = perimetras + 5% atliekų  (durys neatimamos)"
            source="CLAUDE.md §1.4"
          />
          <FormulaRow
            name="Užuolaidų nišos"
            formula="L_niša = lango_plotis + 2 × 0.20 m\nplotas = L_niša × nišos_gylis × 3 (viršus + 2 šonai)"
            source="CLAUDE.md §1.5"
          />
          <FormulaRow
            name="GK lapai"
            formula="lapai = ⌈sienų_plotas / 3.0⌉ × 1.10  (1 lapas = 1.2×2.5 m, +10% atliekų)"
            source="CLAUDE.md §1.8"
          />
          <FormulaRow
            name="Plytelės (sienos)"
            formula="plotas = plyteliuotos_sienos_ilgis × plytelių_aukštis\natliekos: tiesiai +8% · eglutė +12% · šešiakampis +16%"
            source="CLAUDE.md §1.7 — vonia: paprastai iki 2.0–2.4 m"
          />
          <FormulaRow
            name="Hidroizoliacija (vonia)"
            formula="grindys: visas plotas\nsienos: perimetras × 0.30 m + dušo_zona × lubų_aukštis"
            source="CLAUDE.md §1.12 — dažnai pamirštama!"
          />
        </ul>
      )}
    </div>
  );
}
