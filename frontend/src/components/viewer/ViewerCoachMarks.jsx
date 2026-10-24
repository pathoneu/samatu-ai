/**
 * ViewerCoachMarks — the viewer's first-run walkthrough (lib/viewerCoachMarks) and, once it is over, the
 * one-sentence first-use pills at the panels (lib/firstUseHints).
 *
 * Walkthrough (B1-E, 2026-10-19 — founder: „more of them, less writing in each, one by one"): ten short
 * cards, one at a time, each at the element it explains — a ring around it, the card beside, under or over
 * it. One sentence, at most one key, „Toliau" and „Praleisti viską", progress „3 iš 10". Resumable: the
 * card he reached is remembered. While a dialog is open it steps aside (v3 W7-A M6) and Esc is the
 * dialog's; otherwise Esc skips it all.
 *
 * Not the project-level OnboardingTooltips pattern: that one is a centred balloon behind a backdrop;
 * these cards must point at a button and leave the drawing usable underneath.
 */
import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { useTranslation } from '@/i18n/react';
import { X } from 'lucide-react';
import {
  COACH_STEPS, coachMarksDone, markCoachMarksDone, coachCardPosition, coachStartStep, saveCoachStep, modalOpen,
  coachAvoid, COACH_AVOID_SELECTOR,
} from '@/lib/viewerCoachMarks';
import { keyText } from '@/lib/viewerShortcuts';
import { FIRST_USE_PANELS, firstUseSeen, markFirstUseSeen } from '@/lib/firstUseHints';

const CARD_W = 300;

function findAnchor(rootRef, selector) {
  const inViewer = rootRef?.current?.querySelector(selector);
  const el = inViewer || (typeof document !== 'undefined' ? document.querySelector(selector) : null);
  const r = el?.getBoundingClientRect?.();
  return r && r.width > 0 && r.height > 0 ? { el, rect: { left: r.left, top: r.top, width: r.width, height: r.height, bottom: r.bottom } } : null;
}

/** Every on-screen header the card must keep clear of (lib/viewerCoachMarks.coachAvoid). */
function avoidRects() {
  if (typeof document === 'undefined') return [];
  return [...document.querySelectorAll(COACH_AVOID_SELECTOR)].map((el) => {
    const r = el.getBoundingClientRect();
    return { left: r.left, top: r.top, width: r.width, height: r.height };
  }).filter((r) => r.width > 0 && r.height > 0);
}

function stepKey(step) {
  if (!step.key) return null;
  return keyText(step.key, { mac: false }) || step.key;
}

export default function ViewerCoachMarks({ rootRef, enabled = true, delayMs = 900 }) {
  const { t } = useTranslation();
  const [visible, setVisible] = useState(false);
  const [step, setStep] = useState(() => coachStartStep());
  const [rect, setRect] = useState(null);
  const [barRect, setBarRect] = useState(null);
  const cardRef = useRef(null);   // the card's real height keeps it inside the window
  const [, setTick] = useState(0);
  // A dialog or drawer is open: step aside until it closes (v3 M6 — the card
  // sat on the coach layer above every dialog and covered it).
  const [yielding, setYielding] = useState(false);
  const [over, setOver] = useState(() => coachMarksDone());
  // Headers it must not cover (Patikra's room header): the card moves under one, or waits until it is gone.
  const [avoid, setAvoid] = useState([]);
  const shownRef = useRef(false);   // Esc skips the walkthrough only while a card is actually on screen

  useEffect(() => {
    if (!enabled || coachMarksDone()) return undefined;
    const t0 = setTimeout(() => setVisible(true), delayMs);
    return () => clearTimeout(t0);
  }, [enabled, delayMs]);

  const current = COACH_STEPS[step];
  // Follow the anchor: elements come and go (the right panel's tabs, the sheet strip collapsing).
  useLayoutEffect(() => {
    if (!visible || !current) return undefined;
    const measure = () => {
      const found = findAnchor(rootRef, current.anchor);
      setRect(found?.rect || null);
      // No anchor on screen: sit beside the tool cards instead.
      const bar = rootRef?.current?.querySelector('[data-tool-rail]')?.getBoundingClientRect();
      setBarRect(bar && bar.width > 0 ? { left: bar.left, top: bar.top, width: bar.width, height: Math.min(bar.height, 120), bottom: bar.bottom } : null);
      setYielding(modalOpen());
      setAvoid(avoidRects());
      setTick((n) => n + 1);
    };
    measure();
    const id = setInterval(measure, 400);
    window.addEventListener('resize', measure);
    return () => { clearInterval(id); window.removeEventListener('resize', measure); };
  }, [visible, current, rootRef]);

  const finish = () => { markCoachMarksDone(); setVisible(false); setOver(true); };
  const go = (n) => { saveCoachStep(n); setStep(n); };
  useEffect(() => {
    if (!visible || yielding) return undefined;   // with a dialog open, Esc is the dialog's
    const onKey = (e) => {
      if (e.key !== 'Escape' || modalOpen() || !shownRef.current) return;
      e.stopPropagation();
      finish();
    };
    window.addEventListener('keydown', onKey, true);
    return () => window.removeEventListener('keydown', onKey, true);
  }, [visible, yielding]);

  shownRef.current = false;
  if (!visible || !current) return over ? <FirstUsePills rootRef={rootRef} /> : null;
  if (yielding) return null;
  const cardH = cardRef.current?.offsetHeight || 150;
  const vp = { vw: window.innerWidth, vh: window.innerHeight, cardW: CARD_W, cardH };
  const placed = rect
    ? coachCardPosition(rect, { ...vp, side: current.place || 'below' })
    : { ...coachCardPosition(barRect, { ...vp, side: 'right' }), arrowLeft: null, arrowTop: null };
  const pos = coachAvoid(placed, { cardW: CARD_W, cardH, vh: vp.vh, avoid, anchored: Boolean(rect) });
  if (!pos) return null;   // it would cover a header: wait, the same card comes back when the header is gone
  shownRef.current = true;
  // the ring stays on its anchor; a card moved under a header is no longer beside it, so no ring then
  const movedOff = pos !== placed;
  const last = step === COACH_STEPS.length - 1;
  const title = t(`project.coach.${current.id}.title`);
  const key = stepKey(current);
  const keyNote = t(`project.coach.${current.id}.keyNote`, { defaultValue: '' });
  const ring = rect && current.place !== 'over' && !movedOff;
  return (
    <>
      {ring && (
        <div
          aria-hidden
          className="fixed z-coach pointer-events-none rounded-[3px] ring-2 ring-primary ring-offset-2 ring-offset-background"
          style={{ left: rect.left - 2, top: rect.top - 2, width: rect.width + 4, height: rect.height + 4 }}
        />
      )}
      <div
        ref={cardRef}
        role="dialog"
        aria-label={t('project.coach.aria', { title })}
        className="fixed z-coach rounded-[2px] border border-border bg-card text-card-foreground shadow-xl px-4 py-3"
        style={{ left: pos.left, top: pos.top, width: CARD_W }}
        data-testid="viewer-coach-mark"
        data-coach-step={current.id}
      >
        {pos.arrowLeft != null && (
          <span
            aria-hidden
            className={`absolute w-[10px] h-[10px] rotate-45 bg-card border-border ${pos.arrowDown ? '-bottom-[6px] border-r border-b' : '-top-[6px] border-l border-t'}`}
            style={{ left: pos.arrowLeft - 5 }}
          />
        )}
        {pos.arrowTop != null && (
          <span
            aria-hidden
            className="absolute -left-[6px] w-[10px] h-[10px] rotate-45 bg-card border-l border-b border-border"
            style={{ top: pos.arrowTop - 5 }}
          />
        )}
        <div className="flex items-center justify-between gap-2">
          <h3 className="text-[14px] font-semibold text-foreground">{title}</h3>
          <span className="mono tabular text-ui text-muted-foreground" data-testid="viewer-coach-progress">
            {t('project.coach.progress', { n: step + 1, total: COACH_STEPS.length })}
          </span>
        </div>
        <p className="mt-1 text-ui text-foreground leading-snug" data-testid="viewer-coach-body">{t(`project.coach.${current.id}.body`)}</p>
        {!rect && <p className="mt-1 text-ui text-muted-foreground">{t('project.coach.missing')}</p>}
        {key && (
          <p className="mt-1.5 text-ui text-muted-foreground" data-testid="viewer-coach-key">
            <kbd className="mono inline-block min-w-[22px] text-center px-1 rounded-[2px] border border-border bg-muted text-foreground">{key}</kbd>
            {' '}{keyNote ? `— ${keyNote}` : t('project.coach.keyWord')}
          </p>
        )}
        <div className="mt-2.5 flex items-center justify-between">
          <button
            type="button"
            onClick={finish}
            title={t('project.coach.skipAllTitle')}
            className="inline-flex items-center gap-1 text-ui text-muted-foreground hover:text-foreground hover:underline"
            data-testid="viewer-coach-skip"
          >
            <X className="w-3.5 h-3.5" aria-hidden /> {t('project.coach.skipAll')}
          </button>
          <button
            type="button"
            onClick={() => (last ? finish() : go(step + 1))}
            className="px-3 py-1 rounded-[2px] bg-primary text-primary-foreground text-ui hover:bg-primary/90"
            data-testid="viewer-coach-next"
          >{last ? t('project.coach.finish') : t('project.coach.next')}</button>
        </div>
      </div>
    </>
  );
}

/**
 * The first-use pills at the panels (Matavimai, a Patikra question card): one sentence above the panel
 * the first time it is on screen; the first click inside it uses it up. One pill at a time, never over a
 * dialog. Not hover: it is just there until used.
 */
function FirstUsePills({ rootRef }) {
  const { t } = useTranslation();
  const [hint, setHint] = useState(null);   // { id, rect }
  useEffect(() => {
    const measure = () => {
      if (modalOpen()) { setHint(null); return; }
      for (const p of FIRST_USE_PANELS) {
        if (firstUseSeen(p.id)) continue;
        const found = findAnchor(rootRef, p.anchor);
        const r = found?.rect;
        if (!r || r.top > window.innerHeight - 40 || r.bottom < 40) continue;
        setHint({ id: p.id, rect: r, el: found.el });
        return;
      }
      setHint(null);
    };
    measure();
    const id = setInterval(measure, 700);
    window.addEventListener('resize', measure);
    return () => { clearInterval(id); window.removeEventListener('resize', measure); };
  }, [rootRef]);
  useEffect(() => {
    if (!hint?.el) return undefined;
    const used = (e) => {
      if (!(e.target instanceof Node) || !hint.el.contains(e.target)) return;
      markFirstUseSeen(hint.id);
      setHint(null);
    };
    window.addEventListener('pointerdown', used, true);
    window.addEventListener('keydown', used, true);
    return () => { window.removeEventListener('pointerdown', used, true); window.removeEventListener('keydown', used, true); };
  }, [hint?.id, hint?.el]);
  if (!hint) return null;
  const width = Math.min(320, Math.max(200, hint.rect.width - 16));
  const left = Math.min(Math.max(8, hint.rect.left + 8), window.innerWidth - width - 8);
  const top = hint.rect.top > 44 ? hint.rect.top - 36 : hint.rect.top + 6;   // just above the panel, else inside its top edge
  return (
    <div
      role="status"
      aria-live="polite"
      data-testid="first-use-pill"
      data-first-use={hint.id}
      className="fixed z-popover pointer-events-none rounded bg-primary text-primary-foreground text-ui leading-snug px-2 py-1 shadow-md"
      style={{ left, top, maxWidth: width }}
    >
      {t(`project.firstUse.${hint.id}`)}
    </div>
  );
}
