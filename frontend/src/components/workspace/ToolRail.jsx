// frontend/src/components/workspace/ToolRail.jsx
/**
 * Sprint 3: vertical tool rail (50px wide).
 *
 * 6 buttons (top → bottom). Sprint 3-B trim: dropped the duplicate Pan,
 * Liniuotė, Markup and Undo stubs that just alerted "Sprint 4". They
 * were rail noise, not features.
 *
 *   ↖ Pan / select (Esc / V) — default active
 *   ───
 *   ⌖ G1 click-to-fill (1) — ✨ uses Vision
 *   ◌ G5 lasso (5)        — ✨ uses Vision
 *   🎨 G4 spalvos pipetė (4) — ✨ uses Vision
 *   ───
 *   ＋ G2 pridėti skaičių (2)
 *   − G3 šalinti skaičių (3)
 *
 * Reads viewerStore.currentTool; calls setCurrentTool on click.
 * Keyboard shortcuts (Sprint 2 keyboardShortcuts.js) still work.
 *
 * Spec §5.5 ToolRail behaviors.
 */
import { useStore } from 'zustand';
import { viewerStore } from '../../lib/viewerStore';

const TOOLS = [
  { id: 'pan',  label: 'Pan (Esc / V)',     icon: '↖', kind: 'pan' },
  { divider: true },
  { id: 'g1', label: 'AI Click-to-fill (1)', icon: '⌖', kind: 'g1', ai: true },
  { id: 'g5', label: 'AI Lasso (5)',         icon: '◌', kind: 'g5', ai: true },
  { id: 'g4', label: 'Spalvos pipetė (4)',   icon: '🎨', kind: 'g4', ai: true },
  { divider: true },
  { id: 'g2', label: 'Pridėti skaičių (2)',  icon: '＋', kind: 'g2' },
  { id: 'g3', label: 'Šalinti skaičių (3)',  icon: '−',  kind: 'g3' },
];

export function ToolRail() {
  const currentTool = useStore(viewerStore, (s) => s.currentTool);
  const setCurrentTool = useStore(viewerStore, (s) => s.setCurrentTool);

  const handle = (tool) => {
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
