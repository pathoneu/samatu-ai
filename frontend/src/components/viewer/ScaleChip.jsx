/**
 * ScaleChip — the sheet's scale at the drawing's bottom-left, confirmed in one click (Pathon v3 W1-D, D4).
 * It replaces the status bar's scale sentence as the way in: „1:75 — iš plano matmenų" says where
 * the scale comes from in words (lib/scaleProvenance, from the backend's own provenance; never by colour alone —
 * the border is solid for a scale read from the drawing or his own, dashed for a proposal; the full phrase,
 * „1:75 — iš plano matmenų (139 skaičiai)", heads the card); a click opens its card upward with the explanation and the actions — „Patvirtinti 1:115",
 * „Patvirtinti visiems N lapams", „Kalibruoti", „Patikrinti", and „Visi lapų masteliai" (the overview). The
 * model is lib/scaleChip (the one merged scale map + the overview's rows). Esc or a click elsewhere closes it.
 *
 * W5-B B8 (coverage #22, #23): the card also takes a typed „1:50" and offers the standard scales with the sheet's
 * paper size, and „Šiam lapui mastelio nereikia" for schedules and specifications (lib/scaleEntry) — the chip then
 * reads „Mastelio nereikia" and nobody asks for this sheet's scale again until he says it is needed.
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import { paperLabel, parseRatio, standardRatios } from '@/lib/scaleEntry';
import { useScroll } from '@embedpdf/plugin-scroll/react';
import { Check, CheckCheck, CircleSlash, ListChecks, Ruler, Scaling } from 'lucide-react';
import { scaleChipModel } from '@/lib/scaleChip';
import { useTranslation } from '@/i18n/react';
import { visiblePageOf } from '@/lib/visiblePage';

export default function ScaleChip({ documentId, scales, project, durable, totalPages, onConfirm, onCalibrate, onCheck, onOverview, left = 12, openNonce = 0, pageSizeOf = null, isNotNeeded = null, onSetRatio = null, onNotNeeded = null }) {
  const { t } = useTranslation();
  const { state: scroll } = useScroll(documentId);
  const page = visiblePageOf(scroll);
  const chip = useMemo(
    () => scaleChipModel({ page, scales, project, durable, pageCount: totalPages, t }),
    [page, scales, project, durable, totalPages, t],
  );
  const [open, setOpen] = useState(false);
  const [typed, setTyped] = useState('');
  const rootRef = useRef(null);
  const notNeeded = !!isNotNeeded?.(page);
  const paper = paperLabel(pageSizeOf?.(page));
  const typedRatio = parseRatio(typed);
  const applyRatio = (ratio) => { if (!ratio) return; setOpen(false); setTyped(''); onSetRatio?.(chip.page, ratio); };
  useEffect(() => { setOpen(false); }, [page]);
  // „Nustatyti mastelį“ beside the detection button opens this card (W5-B B7, #25) — a new nonce, one opening
  useEffect(() => { if (openNonce) setOpen(true); }, [openNonce]);
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
  const proposed = chip.line === 'dashed';
  return (
    <div ref={rootRef} className="absolute bottom-2 z-panel flex items-center" style={{ left }} data-testid="scale-chip-root">
      {open && (
        <div
          role="dialog"
          aria-label={`Lapo ${chip.page} mastelis`}
          className="absolute bottom-full mb-2 left-0 w-80 max-h-[min(560px,calc(100vh-200px))] overflow-y-auto rounded-panel border border-border bg-card text-card-foreground shadow-lg"
          data-testid="scale-chip-card"
        >
          <div className="px-3 pt-2.5 pb-2 border-b border-border">
            <p className="text-ui font-semibold">Lapas {chip.page} · {notNeeded ? 'mastelio nereikia' : chip.text}</p>
            <p className="mt-1 text-ui text-muted-foreground leading-snug" data-testid="scale-chip-explanation">
              {notNeeded ? 'Pažymėjote, kad šis lapas — lentelė ar specifikacija: jo mastelio programa nebeklausia.' : chip.title}
            </p>
          </div>
          {notNeeded && onNotNeeded && (
            <div className="p-1">
              <button type="button" className={btn} onClick={act(() => onNotNeeded(chip.page, false))} data-testid="scale-chip-needed">
                <Scaling className="w-4 h-4 shrink-0" />Šiam lapui mastelis reikalingas
              </button>
            </div>
          )}
          {!notNeeded && (<>
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
          {onSetRatio && (
            <div className="px-3 py-2 border-t border-border" data-testid="scale-chip-entry">
              <p className="text-meta text-muted-foreground">
                Žinote mastelį? Įrašykite arba pasirinkite{paper ? <> — lapas <span className="mono tabular text-foreground">{paper}</span></> : null}
              </p>
              <form className="mt-1.5 flex items-center gap-1.5" onSubmit={(e) => { e.preventDefault(); applyRatio(typedRatio); }}>
                <label htmlFor="scale-chip-ratio" className="text-ui text-foreground mono">1:</label>
                <input
                  id="scale-chip-ratio"
                  value={typed}
                  onChange={(e) => setTyped(e.target.value)}
                  inputMode="decimal"
                  placeholder="50"
                  aria-label="Mastelis, pavyzdžiui 1:50"
                  className="w-20 h-8 px-2 rounded-panel border border-border bg-card text-ui mono tabular focus:outline-none focus:ring-2 focus:ring-ring"
                  data-testid="scale-chip-ratio"
                />
                <button type="submit" disabled={!typedRatio} className="h-8 px-2.5 rounded-panel border border-border text-ui font-semibold text-foreground hover:bg-muted disabled:opacity-40" data-testid="scale-chip-ratio-apply">
                  Taikyti šiam lapui
                </button>
              </form>
              {typed && !typedRatio && <p className="mt-1 text-meta text-muted-foreground">Įrašykite skaičių po „1:“, pavyzdžiui 50 arba 1:100.</p>}
              <div className="mt-2 flex flex-wrap gap-1" role="group" aria-label="Įprasti masteliai">
                {standardRatios().map((r) => (
                  <button key={r} type="button" onClick={() => applyRatio(r)} className="h-8 px-2 rounded-panel border border-border text-ui mono tabular text-foreground hover:bg-muted" data-testid={`scale-chip-std-${r}`}>
                    1:{r}
                  </button>
                ))}
              </div>
            </div>
          )}
          {onNotNeeded && (
            <div className="p-1 border-t border-border">
              <button type="button" className={btn} onClick={act(() => onNotNeeded(chip.page, true))} data-testid="scale-chip-not-needed"
                title="Lentelėms, specifikacijoms ir titulams mastelis nereikalingas — programa jo šiam lapui nebeklaus">
                <CircleSlash className="w-4 h-4 shrink-0" />Šiam lapui mastelio nereikia
              </button>
            </div>
          )}
          </>)}
        </div>
      )}
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-haspopup="dialog"
        title={`${chip.sentence}. Spustelėkite — patvirtinti arba nustatyti.`}
        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-panel border bg-card text-ui shadow-sm hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${proposed ? 'border-dashed border-ov-proposed' : 'border-solid border-border'}`}
        data-testid="scale-chip"
        data-scale-state={chip.state}
        data-scale-line={chip.line}
      >
        <Scaling className="w-4 h-4 shrink-0 text-muted-foreground" aria-hidden="true" />
        <span className="text-muted-foreground">Mastelis</span>
        {notNeeded ? (
          <span className="font-semibold text-foreground">nereikia</span>
        ) : chip.state === 'nenustatytas' || !chip.label ? (
          <span className="font-semibold text-foreground">{t('project.scaleProvenance.chipNone')}</span>
        ) : (
          <>
            <span className="mono tabular font-semibold text-foreground">{chip.label}</span>
            <span className="text-foreground" data-testid="scale-chip-phrase">— {chip.short}</span>
          </>
        )}
      </button>
      {/* A proposed scale is confirmed in ONE click, right on the chip (Togal's chip; audit act „Confirm scale" 4 → 1).
          A scale read from the drawing can still be confirmed in the card — no second button on the drawing. */}
      {chip.canConfirm && proposed && !open && !notNeeded && (
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
