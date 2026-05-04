// frontend/src/components/workspace/ToolRail.jsx
/**
 * Sprint 3: vertical tool rail (50px wide).
 *
 * 10 buttons (top → bottom):
 *   ↖ Selection (Esc) — default active
 *   ✥ Pan (V or Space)
 *   ⊏ Liniuotė (matavimas)
 *   ───
 *   ⌖ G1 click-to-fill (1) — ✨ uses Vision
 *   ◌ G5 lasso (5)        — ✨ uses Vision
 *   🎨 G4 eyedropper (4)   — ✨ uses Vision
 *   ───
 *   ＋ G2 add count (2)
 *   − G3 remove count (3)
 *   ───
 *   ↶ Undo (Cmd+Z)
 *   ✎ Markup
 *
 * Reads viewerStore.currentTool; calls setCurrentTool on click.
 * Keyboard shortcuts (Sprint 2 keyboardShortcuts.js) still work.
 *
 * Spec §5.5 ToolRail behaviors.
 */
import { useStore } from 'zustand';
import { viewerStore } from '../../lib/viewerStore';

const TOOLS = [
  { id: 'pan',  label: 'Selection (Esc)',   icon: '↖', kind: 'pan' },
  { id: 'pan2', label: 'Pan (V / Space)',   icon: '✥', kind: 'pan' },
  { id: 'ruler', label: 'Liniuotė',         icon: '⊏', kind: 'ruler' },
  { divider: true },
  { id: 'g1', label: 'Click-to-fill (1)',   icon: '⌖', kind: 'g1', ai: true },
  { id: 'g5', label: 'Lasso (5)',           icon: '◌', kind: 'g5', ai: true },
  { id: 'g4', label: 'Eyedropper (4)',      icon: '🎨', kind: 'g4', ai: true },
  { divider: true },
  { id: 'g2', label: 'Skaičiuoti (2)',      icon: '＋', kind: 'g2' },
  { id: 'g3', label: 'Šalinti (3)',         icon: '−',  kind: 'g3' },
  { divider: true },
  { id: 'undo',   label: 'Atšaukti (Cmd+Z)', icon: '↶', kind: 'undo' },
  { id: 'markup', label: 'Markup',          icon: '✎', kind: 'markup' },
];

export function ToolRail({ onUndo, onMarkup, onRuler }) {
  const currentTool = useStore(viewerStore, (s) => s.currentTool);
  const setCurrentTool = useStore(viewerStore, (s) => s.setCurrentTool);

  const handle = (tool) => {
    if (tool.kind === 'undo') return onUndo?.();
    if (tool.kind === 'markup') return onMarkup?.();
    if (tool.kind === 'ruler') return onRuler?.();
    setCurrentTool(tool.kind);
  };

  return (
    <div style={{
      width: 50, background: '#fbfaf7', borderRight: '1px solid #d4d2cb',
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      padding: '6px 0', gap: 2, fontSize: 15,
    }}>
      {TOOLS.map((t, i) => t.divider ? (
        <div key={`d${i}`} style={{ height: 1, width: 30, background: '#d4d2cb', margin: '4px 0' }} />
      ) : (
        <button key={t.id} title={t.label} onClick={() => handle(t)}
          style={{
            width: 38, height: 38, border: 0, cursor: 'pointer', borderRadius: 5,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            background: currentTool === t.kind ? '#2a6fb5' : 'transparent',
            color: currentTool === t.kind ? '#fff' : '#3b3b3b',
            position: 'relative',
          }}>
          {t.icon}
          {t.ai && <span style={{ position: 'absolute', top: 0, right: 1, fontSize: 7, color: '#c97a2c' }}>✨</span>}
        </button>
      ))}
    </div>
  );
}
