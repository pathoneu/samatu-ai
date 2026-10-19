/**
 * OpeningPopover — a door or window edited where it is drawn (Pathon v3 W5-A A9 [D-openings]). With the walls
 * layer on, a click on an opening mark opens this beside the pointer: its width in metres and what it is —
 * langas / durys / praėjimas (no door: nothing is counted there). „Išsaugoti" (Enter) saves it the way the room
 * sheet's opening edit does (the room's openings become his) and the toast holds „Atšaukti". Esc closes it.
 */
import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { DoorOpen } from 'lucide-react';
import { OPENING_KINDS } from '@/lib/openingEdit';
import { parseLtNumber } from '@/lib/parseLtNumber';

export default function OpeningPopover({ target, onSave, onClose }) {
  const ref = useRef(null);
  const [kind, setKind] = useState(target?.state?.kind || 'durys');
  const [width, setWidth] = useState(() => (target?.state?.plotisMm ? (target.state.plotisMm / 1000).toFixed(2).replace('.', ',') : ''));
  const [pos, setPos] = useState(null);
  useLayoutEffect(() => {
    if (!target || !ref.current) return;
    const w = ref.current.offsetWidth; const h = ref.current.offsetHeight;
    setPos({ left: Math.min(Math.max(8, target.x + 16), window.innerWidth - w - 8), top: Math.min(Math.max(8, target.y - h / 2), window.innerHeight - h - 8) });
  }, [target]);
  useEffect(() => {
    if (!target) return undefined;
    const onKey = (e) => { if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); onClose?.(); } };
    const onDown = (e) => { if (ref.current && !ref.current.contains(e.target)) onClose?.(); };
    window.addEventListener('keydown', onKey, true);
    window.addEventListener('pointerdown', onDown, true);
    return () => { window.removeEventListener('keydown', onKey, true); window.removeEventListener('pointerdown', onDown, true); };
  }, [target, onClose]);
  if (!target) return null;
  const metres = parseLtNumber(width);
  const widthOk = kind === 'praejimas' || (Number.isFinite(metres) && metres >= 0.3 && metres <= 6);
  const save = () => { if (widthOk) onSave?.({ kind, plotisMm: kind === 'praejimas' ? null : Math.round(metres * 1000) }); };
  const between = target.o?.i && /^\d/.test(target.o.i) ? ` tarp ${target.nr} ir ${target.o.i}` : (target.o?.i === 'laukas' ? ` į lauką (${target.nr})` : ` (${target.nr})`);
  return (
    <div
      ref={ref}
      role="dialog"
      aria-label="Anga"
      data-testid="opening-popover"
      className="fixed z-[60] w-72 rounded-panel border border-border bg-card shadow-lg p-2.5 flex flex-col gap-2"
      style={pos ? { left: pos.left, top: pos.top } : { left: target.x + 16, top: target.y, visibility: 'hidden' }}
      onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); e.stopPropagation(); save(); } }}
    >
      <div className="flex items-center gap-2 text-ui font-semibold text-foreground">
        <DoorOpen className="w-4 h-4" aria-hidden="true" />
        <span>Anga{between}</span>
      </div>
      <div role="radiogroup" aria-label="Kas tai" className="flex flex-col gap-0.5">
        {OPENING_KINDS.map((k) => (
          <label key={k.id} className="h-8 inline-flex items-center gap-2 px-1 rounded text-ui hover:bg-muted cursor-pointer">
            <input type="radio" name="opening-kind" value={k.id} checked={kind === k.id} onChange={() => setKind(k.id)} data-testid={`opening-kind-${k.id}`} />
            {k.label}
          </label>
        ))}
      </div>
      {kind !== 'praejimas' && (
        <label className="flex items-center gap-2 text-ui">
          <span className="text-muted-foreground">Plotis</span>
          <input
            autoFocus
            value={width}
            onChange={(e) => setWidth(e.target.value)}
            inputMode="decimal"
            className={`w-24 h-8 px-2 rounded border bg-background text-ui mono tabular ${widthOk ? 'border-border' : 'border-destructive'}`}
            aria-label="Angos plotis metrais"
            data-testid="opening-width"
          />
          <span>m</span>
        </label>
      )}
      {!widthOk && <p className="text-ui text-destructive">Plotis turi būti nuo 0,30 iki 6,00 m</p>}
      {kind === 'praejimas' && <p className="text-ui text-muted-foreground leading-snug">Be durų: šioje angoje durys ir angokraščiai neskaičiuojami.</p>}
      <div className="flex items-center justify-end gap-1.5">
        <button type="button" className="h-8 px-2.5 rounded border border-border text-ui hover:bg-muted" onClick={onClose}>Atšaukti</button>
        <button type="button" className="h-8 px-2.5 rounded bg-primary text-primary-foreground text-ui disabled:opacity-50" disabled={!widthOk} onClick={save} data-testid="opening-save">Išsaugoti</button>
      </div>
    </div>
  );
}
