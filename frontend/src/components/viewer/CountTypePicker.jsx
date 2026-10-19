/**
 * CountTypePicker — which type the next count marks are, chosen BESIDE THE POINTER (Pathon v3 W5-A A7 [#115];
 * design §5 Count: „right-click — type menu"). Opens when the count tool is armed and on a right-click while it
 * is: the types (each with its shape AND colour, the running count), ↑ / ↓ and Enter to choose, and „Naujas tipas"
 * — a name, a shape (four buttons, the shape is the type's meaning beside its colour) and Enter. A click on the
 * drawing closes it and still places the mark (it never costs a click). Esc closes it and leaves the tool.
 */
import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { Plus } from 'lucide-react';
import { Glyph } from './CountLegendPanel';
import { COUNT_TYPE_SHAPES, COUNT_TYPE_SHAPE_NAMES, nextTypeLook } from '@/lib/measurements';

export default function CountTypePicker({ at, countTypes = [], activeId = null, tallies = {}, onPick, onCreate, onClose }) {
  const ref = useRef(null);
  const inputRef = useRef(null);
  const [hi, setHi] = useState(() => Math.max(0, countTypes.findIndex((t) => t.id === activeId)));
  const [name, setName] = useState('');
  const [shape, setShape] = useState(() => nextTypeLook(countTypes).shape);
  const [pos, setPos] = useState(null);
  useLayoutEffect(() => {
    if (!at || !ref.current) return;
    const w = ref.current.offsetWidth; const h = ref.current.offsetHeight;
    setPos({ left: Math.min(Math.max(8, at.x + 18), window.innerWidth - w - 8), top: Math.min(Math.max(8, at.y + 10), window.innerHeight - h - 8) });
  }, [at]);
  // no type yet: the name field has the keyboard at once
  useEffect(() => { if (at && !countTypes.length) inputRef.current?.focus(); }, [at]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!at) return undefined;
    const onKey = (e) => {
      // Esc closes the picker and goes on to the viewer's Esc step (design §5 Count: „Esc — exits"): one press
      // leaves the count tool, the picker with it — it is a helper beside the pointer, not a dialog to dismiss first
      if (e.key === 'Escape') { onClose?.(); return; }
      if (e.target === inputRef.current) return;
      if (e.key === 'ArrowDown') { e.preventDefault(); e.stopPropagation(); setHi((i) => Math.min(countTypes.length - 1, i + 1)); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); e.stopPropagation(); setHi((i) => Math.max(0, i - 1)); }
      else if (e.key === 'Enter' && countTypes[hi]) { e.preventDefault(); e.stopPropagation(); onPick?.(countTypes[hi].id); }
    };
    const onDown = (e) => { if (ref.current && !ref.current.contains(e.target)) onClose?.(); };
    window.addEventListener('keydown', onKey, true);
    window.addEventListener('pointerdown', onDown, true);
    return () => { window.removeEventListener('keydown', onKey, true); window.removeEventListener('pointerdown', onDown, true); };
  }, [at, countTypes, hi, onPick, onClose]);
  if (!at) return null;
  const create = () => {
    const label = name.trim();
    if (!label) { inputRef.current?.focus(); return; }
    onCreate?.(label, shape);
    setName('');
  };
  const look = nextTypeLook(countTypes, { shape });
  return (
    <div
      ref={ref}
      role="group"
      aria-label="Kiekio tipas"
      data-testid="count-type-picker"
      className="fixed z-[60] w-72 rounded-panel border border-border bg-card shadow-lg p-1.5 flex flex-col gap-1"
      style={pos ? { left: pos.left, top: pos.top } : { left: at.x + 18, top: at.y + 10, visibility: 'hidden' }}
    >
      {countTypes.length > 0 && (
        <ul role="listbox" aria-label="Tipai" className="flex flex-col max-h-60 overflow-auto">
          {countTypes.map((t, i) => (
            <li key={t.id} role="option" aria-selected={t.id === activeId}>
              <button
                type="button"
                className={`w-full h-9 inline-flex items-center gap-2 px-2 rounded text-ui text-left ${i === hi ? 'bg-muted' : ''} ${t.id === activeId ? 'font-semibold' : ''} hover:bg-muted`}
                onMouseEnter={() => setHi(i)}
                onClick={() => onPick?.(t.id)}
                data-testid={`count-type-option-${t.id}`}
                title={`${t.label} — ${COUNT_TYPE_SHAPE_NAMES[t.shape] || 'apskritimas'}`}
              >
                <Glyph shape={t.shape} color={t.color} />
                <span className="flex-1 truncate">{t.label}</span>
                <span className="mono tabular text-muted-foreground">{tallies[t.id] || 0}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      <div className="border-t border-border pt-1.5 px-1 flex flex-col gap-1.5">
        <label className="text-ui text-muted-foreground" htmlFor="count-type-new">Naujas tipas</label>
        <div className="flex items-center gap-1">
          <input
            id="count-type-new"
            ref={inputRef}
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); e.stopPropagation(); create(); } }}
            placeholder="pvz. Rozetės"
            className="flex-1 h-8 px-2 rounded border border-border bg-background text-ui"
            data-testid="count-type-new-name"
          />
          <button type="button" onClick={create} className="h-8 px-2 inline-flex items-center gap-1 rounded bg-primary text-primary-foreground text-ui disabled:opacity-50" disabled={!name.trim()} data-testid="count-type-new-add">
            <Plus className="w-4 h-4" aria-hidden="true" />Pridėti
          </button>
        </div>
        <div className="flex items-center gap-1" role="radiogroup" aria-label="Žymės forma">
          {COUNT_TYPE_SHAPES.map((sh) => (
            <button
              key={sh}
              type="button"
              role="radio"
              aria-checked={sh === shape}
              aria-label={COUNT_TYPE_SHAPE_NAMES[sh]}
              title={`Žymės forma: ${COUNT_TYPE_SHAPE_NAMES[sh]}`}
              onClick={() => setShape(sh)}
              className={`h-8 w-8 inline-flex items-center justify-center rounded border ${sh === shape ? 'border-foreground bg-muted' : 'border-border'}`}
              data-testid={`count-type-shape-${sh}`}
            >
              <Glyph shape={sh} color={sh === shape ? look.color : 'hsl(var(--muted-foreground))'} />
            </button>
          ))}
          <span className="ml-1 text-ui text-muted-foreground">{COUNT_TYPE_SHAPE_NAMES[shape]}</span>
        </div>
      </div>
    </div>
  );
}
