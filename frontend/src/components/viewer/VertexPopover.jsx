/**
 * VertexPopover — the pop-up beside a corner or an edge being edited (Pathon v3 W5-A A2 [#91]; design §5
 * „Edit outline: vertex pop-up: Ištrinti · Iškirpti angą"). Opened by a click on a corner (never hover-only)
 * or a right-click on a corner or an edge. Icon AND text on every action; a disabled action says why.
 *
 *   „Ištrinti"       — the corner goes (never below the shape's minimum);
 *   „Iškirpti angą"  — on a room's outline: a door in this wall, added like the room sheet's one-click add;
 *                      on a perimeter or distance: the doorway's gap cut out of the length here;
 *   „Pridėti kampą"  — on an edge: a corner where he right-clicked.
 *
 * Esc closes it (its own listener, before the viewer's Esc step: role="menu" makes lib/escOrder stand still).
 */
import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { Trash2, DoorOpen, Plus } from 'lucide-react';

const item = 'w-full h-9 inline-flex items-center gap-2 px-2.5 rounded text-ui text-left text-foreground hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50 disabled:hover:bg-transparent';

/**
 * menu = {kind: 'vertex' | 'edge', x, y} (screen px); actions = {
 *   onDelete?, deleteDisabled?: reason, onCut?, cutLabel, cutDisabled?: reason, onInsert?
 * }
 */
export default function VertexPopover({ menu, actions = {}, onClose }) {
  const ref = useRef(null);
  const [pos, setPos] = useState(null);
  useLayoutEffect(() => {
    if (!menu || !ref.current) return;
    const w = ref.current.offsetWidth; const h = ref.current.offsetHeight;
    const vw = window.innerWidth; const vh = window.innerHeight;
    setPos({ left: Math.min(Math.max(8, menu.x + 14), vw - w - 8), top: Math.min(Math.max(8, menu.y - h / 2), vh - h - 8) });
  }, [menu]);
  useEffect(() => {
    if (!menu) return undefined;
    const onKey = (e) => {
      if (e.key !== 'Escape') return;
      e.preventDefault();
      e.stopPropagation();
      onClose?.();
    };
    const onDown = (e) => { if (ref.current && !ref.current.contains(e.target)) onClose?.(); };
    window.addEventListener('keydown', onKey, true);
    window.addEventListener('pointerdown', onDown, true);
    return () => { window.removeEventListener('keydown', onKey, true); window.removeEventListener('pointerdown', onDown, true); };
  }, [menu, onClose]);
  if (!menu) return null;
  const act = (fn) => () => { onClose?.(); fn?.(); };
  return (
    <div
      ref={ref}
      role="menu"
      aria-label={menu.kind === 'vertex' ? 'Kampo veiksmai' : 'Kraštinės veiksmai'}
      data-testid="vertex-popover"
      className="fixed z-[60] w-64 rounded-panel border border-border bg-card shadow-lg p-1 flex flex-col"
      style={pos ? { left: pos.left, top: pos.top } : { left: menu.x + 14, top: menu.y, visibility: 'hidden' }}
    >
      {menu.kind === 'vertex' && actions.onDelete && (
        <button type="button" role="menuitem" className={item} data-testid="vertex-delete"
          disabled={!!actions.deleteDisabled} title={actions.deleteDisabled || 'Pašalinti šį kampą (Delete)'} onClick={act(actions.onDelete)}>
          <Trash2 className="w-4 h-4 shrink-0" aria-hidden="true" />
          <span>Ištrinti</span>
        </button>
      )}
      {menu.kind === 'edge' && actions.onInsert && (
        <button type="button" role="menuitem" className={item} data-testid="vertex-insert" title="Pridėti kampą čia" onClick={act(actions.onInsert)}>
          <Plus className="w-4 h-4 shrink-0" aria-hidden="true" />
          <span>Pridėti kampą</span>
        </button>
      )}
      {actions.onCut !== undefined && (
        <button type="button" role="menuitem" className={item} data-testid="vertex-cut"
          disabled={!!actions.cutDisabled || !actions.onCut} title={actions.cutDisabled || actions.cutTitle || ''} onClick={act(actions.onCut)}>
          <DoorOpen className="w-4 h-4 shrink-0" aria-hidden="true" />
          <span>{actions.cutLabel || 'Iškirpti angą'}</span>
        </button>
      )}
      {(actions.deleteDisabled || actions.cutDisabled) && (
        <p className="px-2.5 pt-1 pb-1.5 text-ui text-muted-foreground leading-snug">{actions.cutDisabled || actions.deleteDisabled}</p>
      )}
    </div>
  );
}
