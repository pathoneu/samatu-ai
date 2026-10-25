import React, { useState, useCallback, useEffect, useRef } from 'react';
import { useTranslation } from '@/i18n/react';
import { AlertCircle, ChevronDown, ChevronUp, Plus, Trash2, Info, Undo2 } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { toast } from 'sonner';
import { recompute } from '../../lib/recomputeApi';
import { parseLtNumber } from '@/lib/parseLtNumber';
import { buildRecomputeContext } from '@/lib/recomputeContext';
import { rulesWithScope } from '@/lib/scope';
import { isStretchCeiling as isStretchCeilingNr, withStretchCeiling } from '@/lib/stretchCeiling';
import { createDebouncedRun, createRequestOrder } from '@/lib/debouncedRun';
import { BAG_KEY, BAG_RANGE, BUCKET_KEY, BUCKET_RANGE, packagingSizes } from '@/lib/packaging';
import { perRoomSplit, sectionForField, visibleRoomRows } from '@/lib/settingsSections';
import { firstUseSeen, markFirstUseSeen } from '@/lib/firstUseHints';
import { diffDarbuSarasas } from '@/lib/takeoffWorkflow';
import { rippleText } from '@/lib/roomSheet';

// Every assumption edit triggers a backend recompute. Without a debounce each
// keystroke fired its own request and the answers raced (2026-07-27 audit).
const RECOMPUTE_DEBOUNCE_MS = 400;
// Which recompute answer counts — the newest per project. Module-level, not a
// per-mount ref: a run flushed when the drawer closed can still be answering
// after it is opened again, and an edit made then must supersede it.
const recomputeOrder = createRequestOrder();

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
// `commitOnBlur` (B1-E): the value is written when he leaves the field or presses Enter, not per keystroke —
// for the „Visoms patalpoms" height, where a half-typed „2" would set every room to 2,00 m for a moment.
function NumberInput({ value, onChange, min, max, step = 0.01, unit, className, errorMessage, label, hint, placeholder, commitOnBlur = false }) {
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
    if (!commitOnBlur) onChange(n);
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
          onBlur={() => {
            setFocused(false);
            if (!commitOnBlur || draft.trim() === '') return;
            const n = parseLtNumber(draft);
            const ok = Number.isFinite(n) && !((min != null && n < min) || (max != null && n > max));
            if (ok && !(Number.isFinite(Number(value)) && Math.abs(Number(value) - n) < 1e-9)) onChange(n);
          }}
          onKeyDown={(e) => { if (commitOnBlur && e.key === 'Enter') e.currentTarget.blur(); }}
          placeholder={placeholder}
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
          className={`${className || 'h-8 w-20'} text-ui bg-card text-right tabular-nums ${
            invalid ? 'border-destructive text-destructive' : 'border-border'
          }`}
        />
        {unit && <span className="text-ui text-muted-foreground">{unit}</span>}
      </div>
      {/* A red border + a title tooltip was the ONLY feedback for an
          out-of-range value — invisible in practice. Say it out loud; the
          commit behaviour (nothing is written, nothing is clamped) is
          unchanged. (2026-07-28 UX walkthrough.) */}
      {invalid && errorMessage && (
        <p className="mt-0.5 text-ui leading-tight text-destructive" role="alert">
          {errorMessage}
        </p>
      )}
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
        <div key={i} className="flex items-center gap-2 text-ui">
          <span className="text-muted-foreground w-4 text-right">{i + 1}.</span>
          {item.patalpa && (
            <span className="text-muted-foreground truncate max-w-[80px]">{item.patalpa}</span>
          )}
          <Input
            type="number"
            value={item.width_mm}
            onChange={e => handleChange(i, 'width_mm', e.target.value)}
            className="h-8 w-20 text-ui bg-card border-border text-right tabular-nums"
            placeholder={t('project.assumptions.widthPlaceholder')}
            title={t('project.assumptions.openingWidthTitle', { label })}
            aria-label={t('project.assumptions.openingWidthTitle', { label })}
          />
          <span className="text-muted-foreground">×</span>
          <Input
            type="number"
            value={item.height_mm}
            onChange={e => handleChange(i, 'height_mm', e.target.value)}
            className="h-8 w-20 text-ui bg-card border-border text-right tabular-nums"
            placeholder={t('project.assumptions.heightPlaceholder')}
            title={t('project.assumptions.openingHeightTitle', { label })}
            aria-label={t('project.assumptions.openingHeightTitle', { label })}
          />
          <span className="text-muted-foreground">mm</span>
          {item.suggested && (
            <Badge
              variant="outline"
              title={t('project.assumptions.estimatedTitle')}
              className="text-ui border-conf-med/50 text-conf-med py-0 px-1"
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
        className="flex items-center gap-1 text-ui text-muted-foreground hover:text-foreground mt-1"
      >
        <Plus className="w-3 h-3" /> {t('project.assumptions.add', { label: label.toLowerCase() })}
      </button>
    </div>
  );
}


// ── Building blocks of a setting line (B1-E, 2026-10-19) ─────────────────────
//
// Founder: „Nustatymai all messed up" — a wall of buttons. Each setting is now
// ONE line: label · its current value in words · the control. Its note is one
// sentence behind a „?" button (a real button: Tab reaches it, Enter opens it —
// never hover-only).

const CHOICE_BASE = 'min-h-[34px] px-2.5 text-ui border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring';

/** 2–4 choices side by side; the one in force is pressed. */
function Segmented({ options, value, onChange, label, dataAssumption }) {
  return (
    <div role="group" aria-label={label} className="inline-flex flex-wrap rounded-[2px]">
      {options.map((o, i) => {
        const on = String(value) === String(o.value);
        return (
          <button
            key={String(o.value)}
            type="button"
            onClick={() => { if (!on) onChange(o.value); }}
            title={o.title || undefined}
            aria-pressed={on}
            data-assumption={dataAssumption ? `${dataAssumption}:${o.value}` : undefined}
            className={`${CHOICE_BASE} ${i > 0 ? '-ml-px' : ''} ${
              on ? 'relative z-[1] bg-primary/10 border-primary text-foreground font-medium'
                : 'bg-card border-border text-muted-foreground hover:text-foreground hover:border-foreground/30'}`}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}

/** The „?" that opens a setting's one-sentence note. */
function NoteToggle({ open, onToggle, label }) {
  const { t } = useTranslation();
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-expanded={open}
      aria-label={t('project.settings.whatIs', { label })}
      title={t('project.settings.whatIs', { label })}
      className="shrink-0 inline-flex items-center justify-center w-7 h-7 rounded-full border border-border text-ui text-muted-foreground hover:text-foreground hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      data-testid="setting-note-toggle"
    >
      ?
    </button>
  );
}

/** One setting: label · value in words · control · „?"; the note under it when opened. */
function SettingLine({ id, label, value, note, evidence, children, wide = false }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  return (
    <div className="py-2 border-b border-border/50 last:border-0" data-setting={id}>
      <div className={`flex ${wide ? 'flex-wrap' : 'flex-wrap sm:flex-nowrap'} items-center gap-x-3 gap-y-1.5`}>
        <div className="min-w-0 flex-1 basis-40">
          <span className="text-ui font-medium text-foreground">{label}</span>
          {value != null && value !== '' && (
            <span className="text-ui text-muted-foreground" data-testid="setting-value"> · {value}</span>
          )}
        </div>
        <div className="flex items-center gap-1.5 max-w-full">
          {children}
          {note && <NoteToggle open={open} onToggle={() => setOpen((v) => !v)} label={label} />}
        </div>
      </div>
      {open && note && (
        <p className="mt-1 text-ui text-muted-foreground" data-testid="setting-note">
          {note}
          {evidence && <span className="block mt-0.5 text-foreground">{t('project.settings.fromDrawing', { text: evidence })}</span>}
        </p>
      )}
    </div>
  );
}

/** A collapsible group of settings; its summary says the main values in words while closed. */
function Section({ id, title, summary, open, onToggle, children }) {
  return (
    <section className="border border-border rounded-[2px] bg-card" data-settings-section={id}>
      <h3>
        <button
          type="button"
          onClick={onToggle}
          aria-expanded={open}
          className="w-full flex items-center gap-2 px-3 py-2.5 text-left hover:bg-muted/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          data-testid={`settings-section-${id}`}
        >
          <span className="text-[15px] font-semibold text-foreground">{title}</span>
          {!open && summary && <span className="min-w-0 flex-1 truncate text-ui text-muted-foreground">{summary}</span>}
          {open && <span className="flex-1" />}
          {open ? <ChevronUp className="w-4 h-4 shrink-0 text-muted-foreground" /> : <ChevronDown className="w-4 h-4 shrink-0 text-muted-foreground" />}
        </button>
      </h3>
      {open && <div className="px-3 pb-2 border-t border-border/60">{children}</div>}
    </section>
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
  const [recomputing, setRecomputing] = useState(false);
  // Sections: collapsed except the one a caller asked for (B1-E).
  const [openSections, setOpenSections] = useState(() => {
    const s = sectionForField(focusField?.field);
    return new Set(s ? [s] : []);
  });
  const toggleSection = (id) => setOpenSections((prev) => {
    const n = new Set(prev);
    if (n.has(id)) n.delete(id); else n.add(id);
    return n;
  });
  const [showAllRooms, setShowAllRooms] = useState({});
  const [touchedRooms, setTouchedRooms] = useState({});
  const [windowsOpen, setWindowsOpen] = useState(false);
  const [doorsOpen, setDoorsOpen] = useState(false);
  // The last change, with Undo and — once the recompute answered — what moved in the sąmata.
  const [lastEdit, setLastEdit] = useState(null);
  const [undone, setUndone] = useState(null);
  const [firstUseOpen, setFirstUseOpen] = useState(() => !firstUseSeen('nustatymai'));

  // 2026-05-06: defensive defaults so a fresh project (assumptions={}) doesn't
  // throw when accessing lubu_auksciai[room.nr] etc.
  const safeAssumptions = assumptions || {};
  // 2026-07-05: the sample/demo project's numbers are hand-authored to look
  // complete, so they don't derive from its rooms — a recompute can't reproduce
  // them and any edit would shift the sąmata. Lock it to a pristine, view-only
  // showcase. Live editing/recompute stays fully functional on real projects.
  const isDemo = !!(rawData?.is_demo);
  const sienos_storis_m = safeAssumptions.sienos_storis_m;
  const packSizes = packagingSizes(safeAssumptions);
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

  // Debounced + request-ordered recompute (2026-07-27 audit):
  //  - `debounced` collapses a burst of keystrokes into ONE backend call
  //  - recomputeOrder makes stale answers unusable, so a slow first response can
  //    no longer overwrite the quantities produced by a newer edit
  //  - revertRef holds the assumptions as they were BEFORE the burst; on
  //    failure we roll back, because otherwise the panel kept showing the new
  //    assumption next to the OLD quantities (a silently wrong sąmata).
  const [debounced] = useState(() => createDebouncedRun(RECOMPUTE_DEBOUNCE_MS));
  const revertRef = useRef(null);

  // The drawer closing unmounts this panel. A recompute still waiting out its
  // debounce runs NOW: it used to be dropped here, so a setting toggled just
  // before ✕ / a click outside / Esc was saved and its rows never recomputed
  // (2026-10-06). The run answers to the page's onRecomputed / onChange, which
  // outlive the panel; its own setRecomputing is a no-op by then (React 18) and
  // the toast is global.
  useEffect(() => () => { debounced.flush(); }, [debounced]);

  const handleRecompute = useCallback((field, newValue, meta = null) => {
    if (!onRecomputed || isDemo) return;  // Skip if parent won't accept results, or on the view-only sample
    // The assumptions the edit applies to: the current ones — or, for an Undo, the
    // snapshot being restored (this render's props still hold the edited value).
    const base = meta?.base || assumptions || {};
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
    setRecomputing(true);
    const orderKey = rawData?.id ?? '';
    debounced.schedule(async () => {
      const reqId = recomputeOrder.next(orderKey);
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
          current_assumptions: rulesWithScope(base, rawData?._apimtis),
          // Reader/extraction context so a ceiling-height edit rebuilds the
          // canonical pozicijos (paint iki/virš split, kampai…) without losing
          // the door/fixture/symbol lines. (2026-06-17 recompute fix.)
          // One helper shared with /recompute-interior's caller so the two
          // recompute paths cannot drift (lib/recomputeContext.js).
          context: buildRecomputeContext(rawData),
        });
        if (!recomputeOrder.isLatest(orderKey, reqId)) return;  // superseded by a newer edit
        revertRef.current = null;
        onRecomputed(result);
      } catch (err) {
        if (!recomputeOrder.isLatest(orderKey, reqId)) return;
        console.error('Recompute failed:', err);
        const revertTo = revertRef.current;
        revertRef.current = null;
        if (revertTo) onChange(revertTo);
        setLastEdit(null);
        toast.error(t('project.assumptions.toastRecomputeErr', { msg: err.message }));
      } finally {
        if (recomputeOrder.isLatest(orderKey, reqId)) setRecomputing(false);
      }
    });
  }, [rawData, pozicijos, darbuSarasas, assumptions, onRecomputed, onChange, onCorrection, isDemo, t, debounced]);

  /**
   * Every write goes through here: the new assumptions, the recompute (unless the
   * setting is a note only, like packaging), and the Undo for it. A burst on the
   * same setting (typing a number) keeps the FIRST snapshot, so Undo goes back to
   * where he started, not to the previous keystroke.
   */
  const commit = (next, { field, value, label, recompute: doRecompute = true, roomNr = null }) => {
    const now = Date.now();
    if (roomNr != null) {
      setTouchedRooms((m) => (m[field]?.includes(String(roomNr)) ? m : { ...m, [field]: [...(m[field] || []), String(roomNr)] }));
    }
    const sameBurst = lastEdit && lastEdit.field === field && lastEdit.roomNr === roomNr && now - lastEdit.at < 4000;
    setLastEdit({
      field, roomNr, label, at: now, recompute: doRecompute, moved: null,
      prev: sameBurst ? lastEdit.prev : safeAssumptions,
      prevValue: sameBurst ? lastEdit.prevValue : effectiveValue(field),
      prior: sameBurst ? lastEdit.prior : (darbuSarasas || []),
      waiting: doRecompute,
    });
    setUndone(null);
    if (firstUseOpen) { markFirstUseSeen('nustatymai'); setFirstUseOpen(false); }
    onChange(next);
    if (doRecompute) handleRecompute(field, value, roomNr != null ? { roomNr } : null);
  };
  const setOne = (field, value, label, opts = {}) => commit({ ...safeAssumptions, [field]: value }, { field, value, label, ...opts });

  const undo = () => {
    if (!lastEdit) return;
    const { prev, prevValue, field, label, recompute: doRecompute } = lastEdit;
    setLastEdit(null);
    setUndone({ label, prior: darbuSarasas || [], waiting: !!doRecompute, moved: null });
    onChange(prev);
    // The recompute gets the value the panel SHOWED before the change, explicitly: a
    // key that was absent cannot be sent back as „absent" — the engine keeps the
    // quantity it has when a setting is missing (e.g. the putty kg stay at Q3).
    if (doRecompute) {
      const back = prevValue !== undefined ? prevValue : (prev[field] ?? null);
      handleRecompute(field, back, { base: { ...prev, [field]: back } });
    }
  };

  /** What the panel shows for a setting right now — the value Undo goes back to. */
  function effectiveValue(field) {
    switch (field) {
      case 'glaistimo_lygis': return glaistimo_lygis;
      case 'santechnika_potinkinis': return mixersOn;
      case 'vidaus_durys_beapvadines': return framelessCurrent;
      case 'angokrasciai_apimtis': return { ...revealsCurrent };
      case 'sienos_storis_m': return sienos_storis_m ?? 0.10;
      case 'lubu_auksciai': return Object.fromEntries(rooms.map((r) => [String(r.nr), heightOf(r)]));
      case 'walls_paint_override': return Object.fromEntries(rooms.map((r) => [r.nr, isWallsPainted(r) ? 1 : 0]));
      case 'stretch_ceiling_override': return Object.fromEntries(rooms.map((r) => [r.nr, isStretchCeiling(r) ? 1 : 0]));
      case 'custom_windows': return displayWindows;
      case 'custom_doors': return displayDoors;
      default: return safeAssumptions[field];
    }
  }

  // What the recompute moved: compared once the page has handed the new rows back.
  useEffect(() => {
    if (recomputing) return;
    const movedSince = (prior) => rippleText(diffDarbuSarasas(prior || [], darbuSarasas || []), t);
    if (lastEdit?.waiting) setLastEdit((e) => (e ? { ...e, waiting: false, moved: movedSince(e.prior) } : e));
    if (undone?.waiting) setUndone((u) => (u ? { ...u, waiting: false, moved: movedSince(u.prior) } : u));
  }, [darbuSarasas, recomputing]); // eslint-disable-line react-hooks/exhaustive-deps

  const rooms = panelRooms(rawData);
  const roomLabel = (room) => room.pavadinimas || room.nr;

  const heightOf = (room) => {
    const v = Number(lubu_auksciai[room.nr] ?? room.lubu_aukstis_m);
    return Number.isFinite(v) && v > 0 ? v : 2.80;
  };
  const setLubuAukstis = (roomNr, val) => {
    const next_lubu = { ...lubu_auksciai, [roomNr]: val };
    commit({ ...safeAssumptions, lubu_auksciai: next_lubu },
      { field: 'lubu_auksciai', value: next_lubu, roomNr, label: `${t('project.settings.heightLabel')} — ${roomLabel(rooms.find((r) => String(r.nr) === String(roomNr)) || { nr: roomNr })}` });
  };
  // Bulk override — set the same height for ALL rooms at once.
  const setLubuAukstisAll = (val) => {
    const next_lubu = {};
    rooms.forEach(r => { if (r.nr != null) next_lubu[String(r.nr)] = val; });
    commit({ ...safeAssumptions, lubu_auksciai: next_lubu },
      { field: 'lubu_auksciai', value: next_lubu, label: `${t('project.settings.heightLabel')} — ${t('project.settings.allRooms').toLowerCase()}` });
  };

  // Per-room finishing override (2026-07-05). Some rooms (garažas, tambūras)
  // default to raw/unpainted walls; when a contractor finishes them the user
  // flips this and the paint quantities recalc live (same path as ceiling height).
  const isWallsPainted = (room) => {
    const ov = walls_paint_override[room.nr];
    if (ov != null) return Number(ov) >= 0.5;
    return Number(room.walls_paintable_m2 || 0) > 0;
  };
  const setWallsPaint = (targetRooms, painted, label) => {
    const map = { ...walls_paint_override };
    targetRooms.forEach((r) => { map[r.nr] = painted ? 1 : 0; });
    commit({ ...safeAssumptions, walls_paint_override: map }, {
      field: 'walls_paint_override', value: map, label,
      roomNr: targetRooms.length === 1 ? targetRooms[0].nr : null,
    });
  };

  // Per-room ĮTEMPIAMOS LUBOS (2026-09-02 contractor ask). A stretch ceiling is
  // a separate trade stretched under a raw slab, so the room's ceiling
  // glaistymas/gruntavimas/dažymas/šlifavimas is work nobody performs — the
  // backend drops it from the sąmata. Karnizas, LED nišos, GKP lubos and
  // grindjuostės stay. Absent key = dažomos, so nothing changes until the
  // user actually flips a room.
  const isStretchCeiling = (room) => isStretchCeilingNr(safeAssumptions, room.nr);
  const setStretchCeiling = (targetRooms, stretch, label) => {
    let next = safeAssumptions;
    targetRooms.forEach((r) => { next = withStretchCeiling(next, r.nr, stretch); });
    commit(next, {
      field: 'stretch_ceiling_override', value: next.stretch_ceiling_override, label,
      roomNr: targetRooms.length === 1 ? targetRooms[0].nr : null,
    });
  };

  // Land on the control that was named, not at the top of a long panel: open
  // its section (and, for a room, that room's row), scroll on the next macrotask
  // once it is laid out, ring it for a moment and focus it.
  const rootRef = useRef(null);
  const [focusRoom, setFocusRoom] = useState(focusField?.roomNr ?? null);
  useEffect(() => {
    if (!focusField?.field) return undefined;
    setOpen(true);
    const section = sectionForField(focusField.field);
    if (section) setOpenSections((prev) => (prev.has(section) ? prev : new Set([...prev, section])));
    setFocusRoom(focusField.roomNr ?? null);
    // A macrotask, NOT requestAnimationFrame: rAF does not fire while the tab is
    // in the background, so a jump made from a hidden tab (or a browser that
    // throttles frames) silently did nothing.
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

  // ── values in words ──
  const puttyWords = (q) => String(t(`project.assumptions.puttyLevelPlain.${q}`)).replace(/^Q\d\s*—\s*/, '');
  const heights = perRoomSplit(rooms, heightOf);
  const walls = perRoomSplit(rooms, isWallsPainted);
  const stretch = perRoomSplit(rooms, isStretchCeiling);
  const paintedCount = rooms.filter(isWallsPainted).length;
  const stretchCount = rooms.filter(isStretchCeiling).length;
  const m = (v) => `${ltDecimal(Number(v).toFixed(2))} m`;
  const framelessCurrent = Boolean(safeAssumptions.vidaus_durys_beapvadines ?? rawData?._paruosimas?.frameless?.value ?? false);
  const revealDefaults = { langai: true, lauko_durys: true, praejimai: true, vidaus_durys: false };
  const revealsCurrent = {
    ...revealDefaults,
    ...(rawData?._paruosimas?.angokrasciai?.value || {}),
    ...(safeAssumptions.angokrasciai_apimtis || {}),
  };
  const REVEAL_KINDS = ['langai', 'lauko_durys', 'praejimai', 'vidaus_durys'];
  const revealsWords = REVEAL_KINDS.filter((k) => revealsCurrent[k])
    .map((k) => String(t(`project.assumptions.revealKinds.${k}`)).toLowerCase()).join(', ') || t('project.settings.noneOn');
  const mixersOn = String(safeAssumptions.santechnika_potinkinis ?? true) === 'true';
  const paintedWords = t('project.settings.paintedRooms', { n: paintedCount, total: rooms.length });
  const stretchWords = t('project.settings.stretchRooms', { n: stretchCount, total: rooms.length });
  const heightWords = heights.allSame ? m(heights.common) : `${m(heights.common)}, ${t('project.settings.differs')}: ${heights.differing.length}`;

  const summaries = {
    bendra: `${glaistimo_lygis} — ${puttyWords(glaistimo_lygis)}`,
    patalpos: rooms.length ? [
      `${t('project.settings.heightLabel')} ${heightWords}`,
      `${t('project.settings.wallsPaintLabel').toLowerCase()} ${paintedWords}`,
      `${t('project.settings.stretchLabel').toLowerCase()} ${stretchWords}`,
    ].join(' · ') : '',
    angos: `${framelessCurrent ? t('project.assumptions.framelessYes') : t('project.assumptions.framelessNo')} · ${revealsWords}`,
    medziagos: `${ltDecimal(packSizes.bagKg)} kg · ${ltDecimal(packSizes.bucketL)} l`,
    pasirinkimai: mixersOn ? t('project.assumptions.concealedYes') : t('project.assumptions.concealedNo'),
  };

  /**
   * A per-room setting: the value for all rooms first, then a row only for the
   * rooms that differ (or every room, on request; or the one a jump named).
   */
  const perRoom = ({ id, split, renderAll, renderRoom }) => {
    const all = !!showAllRooms[id];
    // a room he is editing keeps its row even once it matches the rest (the field must not vanish mid-typing)
    const also = [...(touchedRooms[id] || []), focusField?.field === id ? focusRoom : null];
    const rows = visibleRoomRows(rooms, split.differing, { showAll: all, also });
    return (
      <div className="pl-3 border-l-2 border-border/60 ml-0.5 mt-1">
        {renderAll()}
        {rows.length > 0 && (
          <table className="w-full mt-1 text-ui">
            <tbody>
              {rows.map((room) => (
                <tr key={room.nr} className="border-t border-border/40">
                  <td className="py-1 pr-2 text-muted-foreground mono tabular w-10">{room.nr}</td>
                  <td className="py-1 pr-2 text-foreground truncate max-w-[180px]" title={room.pavadinimas || undefined}>{room.pavadinimas || ''}</td>
                  <td className="py-1 text-right">{renderRoom(room)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <div className="flex items-center gap-3 mt-1">
          {split.allSame && !all && <span className="text-ui text-muted-foreground">{t('project.settings.allSame')}</span>}
          {rooms.length > 1 && (
            <button
              type="button"
              onClick={() => setShowAllRooms((s) => ({ ...s, [id]: !all }))}
              className="text-ui text-primary hover:underline"
              aria-expanded={all}
              data-testid={`settings-rooms-${id}`}
            >
              {all ? t('project.settings.onlyDiffering') : t('project.settings.showAllRooms', { count: rooms.length })}
            </button>
          )}
        </div>
      </div>
    );
  };

  const yesNo = (onLabel, offLabel) => [{ value: true, label: onLabel }, { value: false, label: offLabel }];

  return (
    <div ref={rootRef} className={bare ? '' : 'border border-border rounded-xl overflow-hidden'} data-testid="settings-panel">
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
            <Badge className="text-ui bg-conf-med/15 text-conf-med border-conf-med/30 border font-normal">
              {t('project.assumptions.windowsFallbackBadge')}
            </Badge>
          )}
        </span>
        {open ? <ChevronUp className="w-4 h-4 text-muted-foreground" /> : <ChevronDown className="w-4 h-4 text-muted-foreground" />}
      </button>
      )}

      {(open || bare) && (
        <div className={`${bare ? '' : 'px-4 '}pb-4 pt-1 space-y-2${isDemo ? ' pointer-events-none' : ''}`}>

          {isDemo ? (
            <div className="flex items-start gap-2 p-3 bg-primary/10 border border-primary/30 rounded-[2px]">
              <Info className="w-4 h-4 shrink-0 mt-0.5 text-primary" />
              <p className="text-ui text-foreground">{t('project.assumptions.demoReadonly')}</p>
            </div>
          ) : (
            <p className="text-ui text-muted-foreground">
              {t('project.settings.intro')}
              {firstUseOpen && (
                <span className="ml-1.5 inline-block rounded bg-primary text-primary-foreground px-2 py-0.5" data-testid="first-use-pill" data-first-use="nustatymai">
                  {t('project.firstUse.nustatymai')}
                </span>
              )}
            </p>
          )}

          {/* The last change: what it was, what it moved, and the way back. */}
          {(lastEdit || undone || recomputing) && !isDemo && (
            <div
              role="status"
              aria-live="polite"
              className="sticky top-0 z-[2] flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2 rounded-[2px] border border-primary/40 bg-background text-ui"
              data-testid="settings-last-change"
            >
              <span className="min-w-0 flex-1 text-foreground">
                {lastEdit ? t('project.settings.changed', { label: lastEdit.label }) : t('project.settings.undone', { label: undone?.label || '' })}
                {' '}
                <span className="text-muted-foreground">
                  {recomputing ? t('project.settings.recomputing') : ((lastEdit ? lastEdit.moved : undone?.moved) || '')}
                </span>
              </span>
              {lastEdit && (
                <button
                  type="button"
                  onClick={undo}
                  className="inline-flex items-center gap-1 min-h-[30px] px-2.5 rounded-[2px] border border-border bg-card text-foreground hover:bg-muted"
                  data-testid="settings-undo"
                >
                  <Undo2 className="w-3.5 h-3.5" aria-hidden /> {t('project.settings.undo')}
                </button>
              )}
            </div>
          )}

          {/* Window fallback warning */}
          {isFallback && (
            <div className="flex items-start gap-2 p-3 bg-conf-med/10 border border-conf-med/30 rounded-[2px] text-ui text-foreground">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5 text-conf-med" />
              <div>
                <p className="font-medium">{t('project.assumptions.windowsNotFound')}</p>
                <p className="mt-0.5 text-muted-foreground">{t('project.assumptions.windowsNotFoundDesc')}</p>
              </div>
            </div>
          )}

          {/* ── Bendra ── */}
          <Section id="bendra" title={t('project.settings.sections.bendra')} summary={summaries.bendra}
            open={openSections.has('bendra')} onToggle={() => toggleSection('bendra')}>
            {/* Design §3: the levels are named by what goes on top („po matiniais dažais");
                the button says Q1–Q4 and the line says it in words. */}
            <SettingLine id="glaistimo_lygis" label={t('project.assumptions.puttyLevel')} value={puttyWords(glaistimo_lygis)}
              note={t('project.settings.notes.putty')}>
              <Segmented
                label={t('project.assumptions.puttyLevel')}
                dataAssumption="glaistimo_lygis"
                value={glaistimo_lygis}
                options={['Q1', 'Q2', 'Q3', 'Q4'].map((q) => ({ value: q, label: q, title: t(`project.assumptions.puttyLevelTitles.${q}`) }))}
                onChange={(q) => setOne('glaistimo_lygis', q, `${t('project.assumptions.puttyLevel')} ${q}`)}
              />
            </SettingLine>
          </Section>

          {/* ── Patalpos ──
              Design §4 says these belong on the room's own sheet; they stay HERE
              until that sheet edits height / walls / ceilings — removing them would
              delete the only way to fix a defaulted 2,80 m. */}
          {rooms.length > 0 && (
            <Section id="patalpos" title={t('project.settings.sections.patalpos')} summary={summaries.patalpos}
              open={openSections.has('patalpos')} onToggle={() => toggleSection('patalpos')}>
              <SettingLine id="lubu_auksciai" label={t('project.settings.heightLabel')} value={heightWords}
                note={t('project.settings.notes.height')} wide>
                <span />
              </SettingLine>
              {perRoom({
                id: 'lubu_auksciai',
                split: heights,
                renderAll: () => (
                  <div className="flex items-center justify-between gap-2 py-1" data-assumption="lubu_auksciai:*">
                    <span className="text-ui font-medium text-foreground">{t('project.settings.allRooms')}</span>
                    <NumberInput
                      key={`all-${heights.common}`}
                      value={heights.common}
                      commitOnBlur
                      min={H_MIN_M} max={H_MAX_M} step={0.05} unit="m"
                      label={`${t('project.settings.heightLabel')} — ${t('project.settings.allRooms')}`}
                      hint={t('project.assumptions.allRoomsTitle')}
                      errorMessage={t('project.assumptions.heightRangeErr', { min: ltDecimal(H_MIN_M.toFixed(2)), max: ltDecimal(H_MAX_M.toFixed(2)) })}
                      onChange={setLubuAukstisAll}
                    />
                  </div>
                ),
                renderRoom: (room) => (
                  <div className="inline-flex" data-assumption={`lubu_auksciai:${room.nr}`}>
                    <NumberInput
                      value={lubu_auksciai[room.nr] ?? heightOf(room)}
                      min={H_MIN_M} max={H_MAX_M} step={0.05} unit="m"
                      label={t('project.assumptions.roomHeightAria', { room: roomLabel(room) })}
                      hint={t('project.assumptions.roomHeightHint', { room: roomLabel(room) })}
                      errorMessage={t('project.assumptions.heightRangeErr', { min: ltDecimal(H_MIN_M.toFixed(2)), max: ltDecimal(H_MAX_M.toFixed(2)) })}
                      onChange={(v) => setLubuAukstis(room.nr, v)}
                    />
                  </div>
                ),
              })}

              <SettingLine id="walls_paint_override" label={t('project.settings.wallsPaintLabel')}
                value={paintedWords} note={t('project.settings.notes.wallsPaint')} wide>
                <span />
              </SettingLine>
              {perRoom({
                id: 'walls_paint_override',
                split: walls,
                renderAll: () => (
                  <div className="flex items-center justify-between gap-2 py-1" data-assumption="walls_paint_override:*">
                    <span className="text-ui font-medium text-foreground">{t('project.settings.allRooms')}</span>
                    <Segmented
                      label={`${t('project.settings.wallsPaintLabel')} — ${t('project.settings.allRooms')}`}
                      value={walls.allSame ? walls.common : ''}
                      options={yesNo(t('project.assumptions.wallsPaintOn'), t('project.assumptions.wallsPaintOff'))}
                      onChange={(v) => setWallsPaint(rooms, v, `${t('project.settings.wallsPaintLabel')} — ${t('project.settings.allRooms').toLowerCase()}`)}
                    />
                  </div>
                ),
                renderRoom: (room) => (
                  <span className="inline-flex" data-assumption={`walls_paint_override:${room.nr}`}>
                    <Segmented
                      label={t('project.assumptions.wallsPaintLabel')}
                      value={isWallsPainted(room)}
                      options={yesNo(t('project.assumptions.wallsPaintOn'), t('project.assumptions.wallsPaintOff'))}
                      onChange={(v) => setWallsPaint([room], v, `${t('project.settings.wallsPaintLabel')} — ${roomLabel(room)}`)}
                    />
                  </span>
                ),
              })}

              <SettingLine id="stretch_ceiling_override" label={t('project.settings.stretchLabel')}
                value={stretchWords} note={t('project.settings.notes.stretch')} wide>
                <span />
              </SettingLine>
              {perRoom({
                id: 'stretch_ceiling_override',
                split: stretch,
                renderAll: () => (
                  <div className="flex items-center justify-between gap-2 py-1" data-assumption="stretch_ceiling_override:*">
                    <span className="text-ui font-medium text-foreground">{t('project.settings.allRooms')}</span>
                    <Segmented
                      label={`${t('project.settings.stretchLabel')} — ${t('project.settings.allRooms')}`}
                      value={stretch.allSame ? stretch.common : ''}
                      options={yesNo(t('project.assumptions.stretchCeilingOn'), t('project.assumptions.stretchCeilingOff'))}
                      onChange={(v) => setStretchCeiling(rooms, v, `${t('project.settings.stretchLabel')} — ${t('project.settings.allRooms').toLowerCase()}`)}
                    />
                  </div>
                ),
                renderRoom: (room) => (
                  <span className="inline-flex" data-assumption={`stretch_ceiling_override:${room.nr}`}>
                    <Segmented
                      label={t('project.assumptions.stretchCeilingLabel')}
                      value={isStretchCeiling(room)}
                      options={yesNo(t('project.assumptions.stretchCeilingOn'), t('project.assumptions.stretchCeilingOff'))}
                      onChange={(v) => setStretchCeiling([room], v, `${t('project.settings.stretchLabel')} — ${roomLabel(room)}`)}
                    />
                  </span>
                ),
              })}
            </Section>
          )}

          {/* ── Angos ir angokraščiai ── */}
          <Section id="angos" title={t('project.settings.sections.angos')} summary={summaries.angos}
            open={openSections.has('angos')} onToggle={() => toggleSection('angos')}>
            {/* Vidaus durys: beapvadinės ar su apvadais (2026-09-23). The drawing's text decides
                it when it says anything; his choice here wins — the same
                `_overrides.vidaus_durys_beapvadines` the Patikra question writes. */}
            <SettingLine id="vidaus_durys_beapvadines" label={t('project.assumptions.framelessDoors')}
              note={t('project.settings.notes.frameless')} evidence={rawData?._paruosimas?.frameless?.sakinys}>
              <Segmented
                label={t('project.assumptions.framelessDoors')}
                dataAssumption="vidaus_durys_beapvadines"
                value={framelessCurrent}
                options={[true, false].map((v) => ({
                  value: v,
                  label: v ? t('project.assumptions.framelessYes') : t('project.assumptions.framelessNo'),
                  title: t(`project.assumptions.framelessTitles.${v}`),
                }))}
                onChange={(v) => setOne('vidaus_durys_beapvadines', v, `${t('project.assumptions.framelessDoors')}: ${v ? t('project.assumptions.framelessYes') : t('project.assumptions.framelessNo')}`)}
              />
            </SettingLine>

            {/* Angokraščiai — kurių angų (2026-09-25): his scope; same `_overrides.angokrasciai_apimtis`. */}
            <SettingLine id="angokrasciai_apimtis" label={t('project.assumptions.revealsScope')} value={revealsWords}
              note={t('project.settings.notes.reveals')} evidence={rawData?._paruosimas?.angokrasciai?.sakinys} wide>
              <div role="group" aria-label={t('project.assumptions.revealsScope')} className="flex flex-wrap gap-1">
                {REVEAL_KINDS.map((kind) => {
                  const on = Boolean(revealsCurrent[kind]);
                  return (
                    <button
                      key={kind}
                      type="button"
                      onClick={() => {
                        const next = { ...revealsCurrent, [kind]: !on };
                        setOne('angokrasciai_apimtis', next, `${t('project.assumptions.revealsScope')}: ${t(`project.assumptions.revealKinds.${kind}`)}`);
                      }}
                      title={t(`project.assumptions.revealKindTitles.${kind}`)}
                      aria-pressed={on}
                      data-assumption={`angokrasciai_apimtis:${kind}:${on ? 'on' : 'off'}`}
                      className={`${CHOICE_BASE} rounded-[2px] ${on
                        ? 'bg-primary/10 border-primary text-foreground font-medium'
                        : 'bg-card border-border text-muted-foreground hover:text-foreground hover:border-foreground/30'}`}
                    >
                      {on ? '✓ ' : ''}{t(`project.assumptions.revealKinds.${kind}`)}
                    </button>
                  );
                })}
              </div>
            </SettingLine>

            <SettingLine id="sienos_storis_m" label={t('project.assumptions.wallThickness')} note={t('project.settings.notes.wallThickness')}>
              <span className="inline-flex" data-assumption="sienos_storis_m:value">
                <NumberInput
                  value={sienos_storis_m}
                  placeholder="0,10"
                  onChange={v => setOne('sienos_storis_m', v, t('project.assumptions.wallThickness'))}
                  min={0.05} max={0.50} step={0.01} unit="m"
                  label={t('project.assumptions.wallThickness')}
                  hint={t('project.assumptions.wallThicknessHint')}
                  errorMessage={t('project.assumptions.wallThicknessRangeErr', { min: ltDecimal('0.05'), max: ltDecimal('0.50') })}
                />
              </span>
            </SettingLine>

            <SettingLine id="custom_windows" label={t('project.settings.windowsLabel')}
              value={`${t('project.settings.openingsCount', { count: displayWindows.length })}${isFallback && !custom_windows ? ` (${t('project.assumptions.windowsFallback')})` : ''}`}
              note={t('project.settings.notes.windows')}>
              <button type="button" onClick={() => setWindowsOpen((v) => !v)} aria-expanded={windowsOpen}
                title={t('project.assumptions.windowsTitle')}
                className="min-h-[34px] px-2.5 rounded-[2px] border border-border bg-card text-ui text-foreground hover:bg-muted"
                data-assumption="custom_windows:edit">
                {windowsOpen ? t('project.settings.hide') : t('project.settings.edit')}
              </button>
            </SettingLine>
            {windowsOpen && (
              <OpeningEditor
                items={displayWindows}
                onChange={wins => setOne('custom_windows', wins, t('project.settings.windowsLabel'))}
                label={t('project.assumptions.windowLabel')}
                defaultItem={{ width_mm: 1200, height_mm: 1500 }}
              />
            )}

            <SettingLine id="custom_doors" label={t('project.settings.doorsLabel')}
              value={t('project.settings.openingsCount', { count: displayDoors.length })}
              note={t('project.settings.notes.doors')}>
              <button type="button" onClick={() => setDoorsOpen((v) => !v)} aria-expanded={doorsOpen}
                title={t('project.assumptions.doorsTitle')}
                className="min-h-[34px] px-2.5 rounded-[2px] border border-border bg-card text-ui text-foreground hover:bg-muted"
                data-assumption="custom_doors:edit">
                {doorsOpen ? t('project.settings.hide') : t('project.settings.edit')}
              </button>
            </SettingLine>
            {doorsOpen && (
              <OpeningEditor
                items={displayDoors}
                onChange={ds => setOne('custom_doors', ds, t('project.settings.doorsLabel'))}
                label={t('project.assumptions.doorLabel')}
                defaultItem={{ width_mm: 800, height_mm: 2200 }}
              />
            )}
          </Section>

          {/* ── Medžiagos ir pakuotės ── (v3 W5-E): only the note beside the Medžiagos kg / l —
              nothing recomputes, the kg stay. */}
          <Section id="medziagos" title={t('project.settings.sections.medziagos')} summary={summaries.medziagos}
            open={openSections.has('medziagos')} onToggle={() => toggleSection('medziagos')}>
            <SettingLine id={BAG_KEY} label={t('project.assumptions.packagingBag')} note={t('project.settings.notes.packaging')}>
              <span className="inline-flex" data-assumption={`${BAG_KEY}:value`}>
                <NumberInput
                  value={packSizes.bagKg}
                  onChange={v => setOne(BAG_KEY, v, t('project.assumptions.packagingBag'), { recompute: false })}
                  min={BAG_RANGE[0]} max={BAG_RANGE[1]} step={1} unit="kg"
                  label={t('project.assumptions.packagingBag')}
                  errorMessage={t('project.assumptions.packagingRangeErr', { min: BAG_RANGE[0], max: BAG_RANGE[1] })}
                />
              </span>
            </SettingLine>
            <SettingLine id={BUCKET_KEY} label={t('project.assumptions.packagingBucket')} note={t('project.settings.notes.packaging')}>
              <span className="inline-flex" data-assumption={`${BUCKET_KEY}:value`}>
                <NumberInput
                  value={packSizes.bucketL}
                  onChange={v => setOne(BUCKET_KEY, v, t('project.assumptions.packagingBucket'), { recompute: false })}
                  min={BUCKET_RANGE[0]} max={BUCKET_RANGE[1]} step={0.5} unit="l"
                  label={t('project.assumptions.packagingBucket')}
                  errorMessage={t('project.assumptions.packagingRangeErr', { min: ltDecimal(BUCKET_RANGE[0]), max: BUCKET_RANGE[1] })}
                />
              </span>
            </SettingLine>
          </Section>

          {/* ── Skaičiavimo pasirinkimai ── */}
          <Section id="pasirinkimai" title={t('project.settings.sections.pasirinkimai')} summary={summaries.pasirinkimai}
            open={openSections.has('pasirinkimai')} onToggle={() => toggleSection('pasirinkimai')}>
            {/* Santechnika: potinkiniai ar virštinkiniai maišytuvai. The backend defaults to
                CONCEALED (two jobs, two lines); measured against four real sąmatos this is a
                genuine per-project convention, so the contractor must be able to flip it. (2026-07-29) */}
            <SettingLine id="santechnika_potinkinis" label={t('project.assumptions.concealedMixers')} note={t('project.settings.notes.mixers')}>
              <Segmented
                label={t('project.assumptions.concealedMixers')}
                dataAssumption="santechnika_potinkinis"
                value={mixersOn}
                options={[true, false].map((v) => ({
                  value: v,
                  label: v ? t('project.assumptions.concealedYes') : t('project.assumptions.concealedNo'),
                  title: t(`project.assumptions.concealedTitles.${v}`),
                }))}
                onChange={(v) => setOne('santechnika_potinkinis', v, `${t('project.assumptions.concealedMixers')}: ${v ? t('project.assumptions.concealedYes') : t('project.assumptions.concealedNo')}`)}
              />
            </SettingLine>

            {/* LED lengths come from the drawing's legend (v4, 2026-10-25): the estimate switch is gone. */}
            <p className="text-ui text-muted-foreground" data-testid="settings-led-note">{t('project.settings.notes.led')}</p>
          </Section>
        </div>
      )}
    </div>
  );
}
