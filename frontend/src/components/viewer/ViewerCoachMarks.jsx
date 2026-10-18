/**
 * ViewerCoachMarks — the viewer's first-run walkthrough (lib/viewerCoachMarks):
 * Mastelis → Atstumas → Taisyti kontūrą, each card at its button (`data-coach="…"`
 * inside `rootRef`) — beside a tool card on the left rail, under the selected room's
 * action bar — a ring around the button, shown once per browser. „Praleisti", the X,
 * Esc and finishing all mark it done.
 *
 * Not the project-level OnboardingTooltips pattern: that one is a centred
 * balloon behind a backdrop; these cards must point at a button and leave the
 * drawing usable underneath.
 */
import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { X } from 'lucide-react';
import { COACH_STEPS, coachMarksDone, markCoachMarksDone, coachCardPosition, modalOpen } from '@/lib/viewerCoachMarks';

const CARD_W = 320;

export default function ViewerCoachMarks({ rootRef, enabled = true, delayMs = 900 }) {
  const [visible, setVisible] = useState(false);
  const [step, setStep] = useState(0);
  const [rect, setRect] = useState(null);
  const [barRect, setBarRect] = useState(null);
  const [side, setSide] = useState('below');
  const cardRef = useRef(null);   // the card's real height keeps a card beside a low tool inside the window
  const [, setTick] = useState(0);
  // A dialog or drawer is open: step aside until it closes (v3 M6 — the card
  // sat on the coach layer above every dialog and covered it).
  const [yielding, setYielding] = useState(false);

  useEffect(() => {
    if (!enabled || coachMarksDone()) return undefined;
    const t = setTimeout(() => setVisible(true), delayMs);
    return () => clearTimeout(t);
  }, [enabled, delayMs]);

  const current = COACH_STEPS[step];
  // Follow the anchor: buttons come and go (the room's action bar exists only while a room is selected).
  useLayoutEffect(() => {
    if (!visible) return undefined;
    const measure = () => {
      const el = rootRef?.current?.querySelector(`[data-coach="${current.anchor}"]`);
      const r = el?.getBoundingClientRect();
      setRect(r && r.width > 0 ? { left: r.left, top: r.top, width: r.width, height: r.height, bottom: r.bottom } : null);
      // A tool card stands in a column on the left: its card goes beside it, not over the next tools.
      setSide(el?.closest?.('[data-tool-rail]') || !el ? 'right' : 'below');
      // No button (e.g. „Taisyti kontūrą" before a room is chosen): sit beside the tool cards instead.
      const bar = rootRef?.current?.querySelector('[data-tool-rail]')?.getBoundingClientRect();
      setBarRect(bar && bar.width > 0 ? { left: bar.left, top: bar.top, width: bar.width, height: Math.min(bar.height, 120), bottom: bar.bottom } : null);
      setYielding(modalOpen());
      setTick((n) => n + 1);
    };
    measure();
    const id = setInterval(measure, 400);
    window.addEventListener('resize', measure);
    return () => { clearInterval(id); window.removeEventListener('resize', measure); };
  }, [visible, current, rootRef]);

  const finish = () => { markCoachMarksDone(); setVisible(false); };
  useEffect(() => {
    if (!visible || yielding) return undefined;   // with a dialog open, Esc is the dialog's
    const onKey = (e) => {
      if (e.key !== 'Escape' || modalOpen()) return;
      e.stopPropagation();
      finish();
    };
    window.addEventListener('keydown', onKey, true);
    return () => window.removeEventListener('keydown', onKey, true);
  }, [visible, yielding]);

  if (!visible || !current || yielding) return null;
  const pos = rect
    ? coachCardPosition(rect, { vw: window.innerWidth, vh: window.innerHeight, cardW: CARD_W, cardH: cardRef.current?.offsetHeight || 300, side })
    : { ...coachCardPosition(barRect, { vw: window.innerWidth, vh: window.innerHeight, cardW: CARD_W, cardH: cardRef.current?.offsetHeight || 300, side: 'right' }), arrowLeft: null, arrowTop: null };
  const last = step === COACH_STEPS.length - 1;
  return (
    <>
      {rect && (
        <div
          aria-hidden
          className="fixed z-coach pointer-events-none rounded-[3px] ring-2 ring-primary ring-offset-2 ring-offset-background"
          style={{ left: rect.left - 2, top: rect.top - 2, width: rect.width + 4, height: rect.height + 4 }}
        />
      )}
      <div
        ref={cardRef}
        role="dialog"
        aria-label={`Įvadas: ${current.title}`}
        className="fixed z-coach rounded-[2px] border border-border bg-card text-card-foreground shadow-xl p-4"
        style={{ left: pos.left, top: pos.top, width: CARD_W }}
        data-testid="viewer-coach-mark"
        data-coach-step={current.id}
      >
        {pos.arrowLeft != null && (
          <span
            aria-hidden
            className="absolute -top-[6px] w-[10px] h-[10px] rotate-45 bg-card border-l border-t border-border"
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
        <div className="flex items-start justify-between mb-1.5">
          <span className="mono tabular text-meta font-semibold text-primary">
            Žingsnis {step + 1} iš {COACH_STEPS.length}
          </span>
          <button type="button" onClick={finish} title="Praleisti įvadą (Esc)" aria-label="Praleisti įvadą" className="p-0.5 -m-0.5 rounded-[2px] text-muted-foreground hover:bg-muted">
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
        <h3 className="text-[14px] font-semibold text-foreground mb-1">{current.title}</h3>
        <p className="text-ui text-muted-foreground leading-relaxed">{current.body}</p>
        {!rect && current.missingAnchorNote && (
          <p className="mt-1.5 text-meta text-foreground">{current.missingAnchorNote}</p>
        )}
        <div className="mt-3 flex items-center justify-between">
          <button type="button" onClick={finish} className="text-meta text-muted-foreground hover:text-foreground hover:underline">Praleisti</button>
          <div className="flex items-center gap-1.5">
            {step > 0 && (
              <button type="button" onClick={() => setStep((s) => s - 1)} className="px-2.5 py-1 rounded-[2px] border border-border text-meta hover:bg-muted">Atgal</button>
            )}
            <button
              type="button"
              onClick={() => (last ? finish() : setStep((s) => s + 1))}
              className="px-2.5 py-1 rounded-[2px] bg-primary text-primary-foreground text-meta hover:bg-primary/90"
              data-testid="viewer-coach-next"
            >{last ? 'Supratau' : 'Toliau'}</button>
          </div>
        </div>
      </div>
    </>
  );
}
