/**
 * ScaleChip — the sheet's scale at the drawing's bottom-left, confirmed in one click (Pathon v3 W1-D, D4).
 * It replaces the status bar's scale sentence as the way in: „1:115 · spėjamas" says the state in words (never
 * by colour alone); a click opens its card upward with the explanation and the actions — „Patvirtinti 1:115",
 * „Patvirtinti visiems N lapams", „Kalibruoti", „Patikrinti", and „Visi lapų masteliai" (the overview). The
 * model is lib/scaleChip (the one merged scale map + the overview's rows). Esc or a click elsewhere closes it.
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import { useScroll } from '@embedpdf/plugin-scroll/react';
import { Check, CheckCheck, ListChecks, Ruler, Scaling } from 'lucide-react';
import { scaleChipModel } from '@/lib/scaleChip';
import { SCALE_STATE_LT } from '@/lib/scaleLabel';
import { visiblePageOf } from '@/lib/visiblePage';

export default function ScaleChip({ documentId, scales, project, durable, totalPages, onConfirm, onCalibrate, onCheck, onOverview, left = 12 }) {
  const { state: scroll } = useScroll(documentId);
  const page = visiblePageOf(scroll);
  const chip = useMemo(
    () => scaleChipModel({ page, scales, project, durable, pageCount: totalPages }),
    [page, scales, project, durable, totalPages],
  );
  const [open, setOpen] = useState(false);
  const rootRef = useRef(null);
  useEffect(() => { setOpen(false); }, [page]);
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => { if (e.key === 'Escape') { e.stopPropagation(); setOpen(false); } };
    const onDown = (e) => { if (!rootRef.current?.contains(e.target)) setOpen(false); };
    window.addEventListener('keydown', onKey, true);
    window.addEventListener('pointerdown', onDown, true);
    return () => { window.removeEventListener('keydown', onKey, true); window.removeEventListener('pointerdown', onDown, true); };
  }, [open]);
  const act = (fn) => () => { setOpen(false); fn?.(); };
  const btn = 'w-full inline-flex items-center gap-2 px-3 py-2 rounded text-ui text-left text-foreground hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50';
  const guessed = chip.state === 'spejamas';
  return (
    <div ref={rootRef} className="absolute bottom-2 z-panel flex items-center" style={{ left }} data-testid="scale-chip-root">
      {open && (
        <div
          role="dialog"
          aria-label={`Lapo ${chip.page} mastelis`}
          className="absolute bottom-full mb-2 left-0 w-80 rounded-panel border border-border bg-card text-card-foreground shadow-lg"
          data-testid="scale-chip-card"
        >
          <div className="px-3 pt-2.5 pb-2 border-b border-border">
            <p className="text-ui font-semibold">Lapas {chip.page} · {chip.text}</p>
            <p className="mt-1 text-meta text-muted-foreground leading-snug">{chip.title}</p>
          </div>
          <div className="p-1">
            {chip.canConfirm && (
              <button type="button" className={btn} onClick={act(() => onConfirm?.([chip.page]))} data-testid="scale-chip-confirm">
                <Check className="w-4 h-4 shrink-0" />Patvirtinti {chip.label} šiam lapui
              </button>
            )}
            {chip.group && (
              <button type="button" className={btn} onClick={act(() => onConfirm?.(chip.group.pages))} data-testid="scale-chip-confirm-all">
                <CheckCheck className="w-4 h-4 shrink-0" />Patvirtinti {chip.group.label} visiems {chip.group.pages.length} lapams ({chip.group.pages.join(', ')})
              </button>
            )}
            <button type="button" className={btn} onClick={act(onCalibrate)} data-testid="scale-chip-calibrate"
              title="Spustelėkite atkarpos, kurios tikrą ilgį žinote, pradžią ir pabaigą, tada įrašykite ilgį — artimiausias įprastas mastelis bus pasiūlytas">
              <Scaling className="w-4 h-4 shrink-0" />{chip.state === 'nenustatytas' ? 'Nustatyti pagal žinomą ilgį' : 'Kalibruoti pagal žinomą ilgį'}
            </button>
            {chip.state !== 'nenustatytas' && (
              <button type="button" className={btn} onClick={act(onCheck)} data-testid="scale-chip-check"
                title="Spustelėkite du taškus — pamatysite ilgį pagal šį mastelį ir artimiausius plane užrašytus matmenis; niekas nekeičiama">
                <Ruler className="w-4 h-4 shrink-0" />Patikrinti žinomu matmeniu
              </button>
            )}
            {onOverview && (
              <button type="button" className={btn} onClick={act(onOverview)} data-testid="scale-chip-overview">
                <ListChecks className="w-4 h-4 shrink-0" />Visų lapų masteliai
              </button>
            )}
          </div>
        </div>
      )}
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-haspopup="dialog"
        title={`${chip.sentence}. Spustelėkite — patvirtinti arba nustatyti.`}
        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-panel border bg-card text-ui shadow-sm hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${guessed ? 'border-[hsl(var(--ov-proposed))]' : 'border-border'}`}
        data-testid="scale-chip"
        data-scale-state={chip.state}
      >
        <Scaling className="w-4 h-4 shrink-0 text-muted-foreground" aria-hidden="true" />
        <span className="text-muted-foreground">Mastelis</span>
        {chip.state === 'nenustatytas' || !chip.label ? (
          <span className="font-semibold text-foreground">nenustatytas</span>
        ) : (
          <>
            <span className="mono tabular font-semibold text-foreground">{chip.label}</span>
            <span className="text-foreground">· {SCALE_STATE_LT[chip.state]}</span>
          </>
        )}
      </button>
      {/* A guessed scale is confirmed in ONE click, right on the chip (Togal's chip; audit act „Confirm scale" 4 → 1). */}
      {chip.canConfirm && !open && (
        <button
          type="button"
          onClick={() => onConfirm?.([chip.page])}
          title={`Patvirtinti, kad lapo ${chip.page} mastelis ${chip.label} teisingas — jis taps jūsų`}
          className="ml-1 inline-flex items-center gap-1 px-2.5 py-1 rounded-panel border border-border bg-card text-ui font-semibold text-foreground shadow-sm hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          data-testid="scale-chip-confirm-inline"
        >
          <Check className="w-4 h-4 shrink-0" aria-hidden="true" />Patvirtinti
        </button>
      )}
    </div>
  );
}
