// frontend/src/components/workspace/RightPanel.jsx
/**
 * Sprint 3-B simplification: dropped the 3-tab strip (AI / 📋 Kiekiai
 * / 📊 Suvestinė) in favour of a single Kiekiai panel. AiPanel and
 * SuvestinePanel files retained — Sprint 4 may resurrect the tabs once
 * those views actually carry their weight.
 */
import { QuantitiesPanel } from '../panels/QuantitiesPanel';

export function RightPanel({ rooms, pozicijos, currentAssumptions, onRecomputed, onGestureEvent, warnings }) {
  return (
    <aside style={{
      width: 320, background: 'hsl(var(--card))',
      borderLeft: '1px solid hsl(var(--border))',
      display: 'flex', flexDirection: 'column',
      fontSize: 12, color: 'hsl(var(--foreground))', height: '100%',
    }}>
      <QuantitiesPanel
        rooms={rooms} pozicijos={pozicijos}
        currentAssumptions={currentAssumptions}
        onRecomputed={onRecomputed} onGestureEvent={onGestureEvent}
        warnings={warnings}
      />
    </aside>
  );
}
