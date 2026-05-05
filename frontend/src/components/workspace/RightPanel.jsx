// frontend/src/components/workspace/RightPanel.jsx
/**
 * Sprint 3: tabbed right panel (320px wide).
 *
 * Three tabs: ✨ AI · 📋 Kiekiai (default active) · 📊 Suvestinė.
 * Switches via internal useState. Renders provided children based on
 * active tab.
 *
 * Spec §5.6 RightPanel tabs.
 */
import { useState } from 'react';

const TABS = [
  { id: 'ai',         label: '✨ AI',        icon: '✨' },
  { id: 'kiekiai',    label: '📋 Kiekiai',   icon: '📋' },
  { id: 'suvestine',  label: '📊 Suvestinė', icon: '📊' },
];

export function RightPanel({
  activeTab: controlledActive,
  onTabChange,
  badges = {}, // {ai: 2, kiekiai: 47, suvestine: undefined}
  ai,          // <AiPanel /> JSX
  kiekiai,     // <QuantitiesPanel /> JSX
  suvestine,   // <SuvestinePanel /> JSX
}) {
  const [internalActive, setInternalActive] = useState('kiekiai');
  const active = controlledActive ?? internalActive;
  const setActive = (t) => {
    if (controlledActive == null) setInternalActive(t);
    onTabChange?.(t);
  };

  return (
    <aside style={{
      width: 320, background: '#fbfaf7',
      borderLeft: '1px solid #d4d2cb',
      display: 'flex', flexDirection: 'column',
      fontSize: 12, color: '#171717', height: '100%',
    }}>
      <div style={{ display: 'flex', borderBottom: '1px solid #d4d2cb', background: '#f0eeea' }}>
        {TABS.map((t) => {
          const isActive = active === t.id;
          const badge = badges[t.id];
          return (
            <button key={t.id} onClick={() => setActive(t.id)} style={{
              flex: 1, background: isActive ? '#fbfaf7' : 'transparent',
              border: 0, borderBottom: isActive ? '2px solid #2a6fb5' : '2px solid transparent',
              padding: '10px 0', cursor: 'pointer',
              color: isActive ? '#171717' : '#6b6863',
              fontWeight: isActive ? 600 : 500, fontSize: 12,
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
            }}>
              {t.label}
              {badge != null && <span style={{
                background: t.id === 'ai' && badge > 0 ? '#fdf6e7' : '#e8e5df',
                color: t.id === 'ai' && badge > 0 ? '#9a5d20' : '#6b6863',
                fontSize: 9, padding: '1px 5px', borderRadius: 6,
              }}>{badge}</span>}
            </button>
          );
        })}
      </div>
      <div style={{ flex: 1, overflow: 'hidden' }}>
        {active === 'ai' && ai}
        {active === 'kiekiai' && kiekiai}
        {active === 'suvestine' && suvestine}
      </div>
    </aside>
  );
}
