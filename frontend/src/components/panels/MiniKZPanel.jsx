// frontend/src/components/panels/MiniKZPanel.jsx
/**
 * Sprint 2: minimal KŽ panel hosting G7 numeric override.
 *
 * Shows a flat list of pozicijos (skyrius / aprasymas / kiekis / vnt).
 * Click on a row → select it (drives G2/G3 target). Click on the kiekis
 * cell → inline editor; Enter applies overrideQuantity, Esc cancels.
 *
 * Sprint 3 replaces this with the full QuantitiesPanel (folder tree,
 * confidence badges, bidirectional highlight). For now, just enough
 * surface for G7 to be testable and for G2/G3 to have a selection target.
 */
import { useState, useCallback } from 'react';
import { useStore } from 'zustand';
import { viewerStore } from '../../lib/viewerStore';
import { overrideQuantity } from '../../lib/gestureApi';
import { abortRegistry } from '../../lib/abortRegistry';

export function MiniKZPanel({ rooms, pozicijos, currentAssumptions,
                              onRecomputed, onGestureEvent }) {
  const setSelection = useStore(viewerStore, (s) => s.setSelection);
  const selection = useStore(viewerStore, (s) => s.selection);
  const [editingId, setEditingId] = useState(null);
  const [editValue, setEditValue] = useState('');

  const startEdit = useCallback((poz) => {
    setEditingId(poz.id);
    setEditValue(String(poz.kiekis ?? ''));
  }, []);

  const commitEdit = useCallback(async (poz) => {
    setEditingId(null);
    const parsed = Number.parseFloat(editValue);
    if (!Number.isFinite(parsed) || parsed === poz.kiekis) return;
    const startedAt = Date.now();
    try {
      const signal = abortRegistry.takeSignal('g7');
      const result = await overrideQuantity({
        rooms, pozicijos, currentAssumptions,
        targetPozicijaId: poz.id, newValue: parsed, signal,
      });
      onRecomputed?.(result);
      onGestureEvent?.({
        type: 'G7', target: { kind: 'pozicija', id: poz.id },
        outcome: 'success', duration_ms: Date.now() - startedAt,
      });
    } catch (err) {
      if (err.name === 'AbortError') return;
      console.error('[G7] override_pozicija failed:', err);
      onGestureEvent?.({
        type: 'G7', target: { kind: 'pozicija', id: poz.id },
        outcome: 'error', duration_ms: Date.now() - startedAt,
      });
      alert(err.envelope?.user_message || `G7 nepavyko: ${err.message}`);
    }
  }, [editValue, rooms, pozicijos, currentAssumptions,
      onRecomputed, onGestureEvent]);

  const cancelEdit = useCallback(() => setEditingId(null), []);

  return (
    <aside style={{
      width: 240, height: '100%', overflow: 'auto',
      background: '#0f1419', color: '#e2e8f0',
      borderLeft: '1px solid #1f2937', fontSize: 13,
    }}>
      <header style={{ padding: '8px 12px', borderBottom: '1px solid #1f2937', fontWeight: 600 }}>
        KŽ ({pozicijos.length})
      </header>
      <ul style={{ listStyle: 'none', margin: 0, padding: 0 }}>
        {pozicijos.map((poz) => {
          const isSelected = selection?.kind === 'pozicija' && selection.id === poz.id;
          return (
            <li
              key={poz.id}
              onClick={() => setSelection({ kind: 'pozicija', id: poz.id })}
              style={{
                padding: '6px 12px', cursor: 'pointer',
                background: isSelected ? '#1e293b' : 'transparent',
                borderBottom: '1px solid #111827',
              }}
            >
              <div style={{ fontSize: 11, color: '#9ca3af' }}>{poz.skyrius}</div>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 6 }}>
                <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {poz.aprasymas}
                </span>
                {editingId === poz.id ? (
                  <input
                    autoFocus
                    type="number"
                    value={editValue}
                    onChange={(e) => setEditValue(e.target.value)}
                    onBlur={() => commitEdit(poz)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') commitEdit(poz);
                      if (e.key === 'Escape') cancelEdit();
                    }}
                    onClick={(e) => e.stopPropagation()}
                    style={{ width: 60, background: '#0b0f14', color: '#fff',
                             border: '1px solid #facc15', padding: '2px 4px' }}
                  />
                ) : (
                  <span
                    onClick={(e) => { e.stopPropagation(); startEdit(poz); }}
                    style={{
                      fontVariantNumeric: 'tabular-nums',
                      color: poz.override_locked ? '#facc15' : '#e2e8f0',
                    }}
                  >
                    {poz.kiekis} {poz.vnt}
                    {poz.override_locked && ' 🔒'}
                  </span>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </aside>
  );
}
