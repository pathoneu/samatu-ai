// frontend/src/components/panels/QuantitiesPanel.jsx
/**
 * Sprint 3: Kiekiai tab content. Replaces MiniKZPanel.
 *
 * - Filter pills (Visos / 🔴 N / 🟡 N / 🔒 N)
 * - Search filter
 * - Category-grouped tree (skyrius header + rows)
 * - Each row: aprasymas | kiekis vnt | confidence dot
 * - Click row → setSelection (drives G2/G3 target)
 * - Hover row → setHoveredRoomId (bidirectional highlight)
 * - Click kiekis text → G7 inline edit
 * - Footer: Σ neto + Eksportuoti
 *
 * Spec §5.6 Kiekiai tab.
 */
import { useState, useMemo, useCallback } from 'react';
import { useStore } from 'zustand';
import { viewerStore } from '../../lib/viewerStore';
import { overrideQuantity } from '../../lib/gestureApi';
import { abortRegistry } from '../../lib/abortRegistry';

const FILTERS = [
  { id: 'all',  label: 'Visos',  match: () => true,                 active: { bg: '#2a6fb5', fg: '#fff' } },
  { id: 'low',  label: '🔴 N',  match: (p) => p.confidence === 'low' && !p.override_locked },
  { id: 'med',  label: '🟡 N',  match: (p) => p.confidence === 'med' && !p.override_locked },
  { id: 'lock', label: '🔒 N',  match: (p) => p.override_locked },
];

export function QuantitiesPanel({
  rooms = [], pozicijos = [], currentAssumptions = {},
  onRecomputed, onGestureEvent,
}) {
  const setSelection = useStore(viewerStore, (s) => s.setSelection);
  const setHoveredRoomId = useStore(viewerStore, (s) => s.setHoveredRoomId);
  const selection = useStore(viewerStore, (s) => s.selection);

  const [filter, setFilter] = useState('all');
  const [search, setSearch] = useState('');
  const [editingId, setEditingId] = useState(null);
  const [editValue, setEditValue] = useState('');

  const counts = useMemo(() => ({
    all:  pozicijos.length,
    low:  pozicijos.filter(p => p.confidence === 'low' && !p.override_locked).length,
    med:  pozicijos.filter(p => p.confidence === 'med' && !p.override_locked).length,
    lock: pozicijos.filter(p => p.override_locked).length,
  }), [pozicijos]);

  const filtered = useMemo(() => {
    const f = FILTERS.find(x => x.id === filter);
    const q = search.trim().toLowerCase();
    return pozicijos.filter(p => f.match(p) && (!q || (p.aprasymas || '').toLowerCase().includes(q)));
  }, [pozicijos, filter, search]);

  const grouped = useMemo(() => {
    const map = new Map();
    for (const p of filtered) {
      const k = p.skyrius_label || p.skyrius || 'Kita';
      if (!map.has(k)) map.set(k, []);
      map.get(k).push(p);
    }
    return Array.from(map.entries());
  }, [filtered]);

  const totalNet = useMemo(() =>
    filtered.reduce((s, p) => s + (Number(p.kiekis_x_kaina) || 0), 0),
  [filtered]);

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
      onGestureEvent?.({ type: 'G7', target: { kind: 'pozicija', id: poz.id }, outcome: 'success', duration_ms: Date.now() - startedAt });
    } catch (err) {
      if (err.name === 'AbortError') return;
      onGestureEvent?.({ type: 'G7', target: { kind: 'pozicija', id: poz.id }, outcome: 'error', duration_ms: Date.now() - startedAt });
      alert(err.envelope?.user_message || `Klaida: ${err.message}`);
    }
  }, [editValue, rooms, pozicijos, currentAssumptions, onRecomputed, onGestureEvent]);

  const confDot = (poz) => {
    if (poz.override_locked) return '#6f5fa3';
    const map = { high: '#2f7d5b', med: '#c97a2c', low: '#a7493f' };
    return map[poz.confidence] || '#94a3b8';
  };

  const rowBg = (poz) => {
    if (poz.confidence === 'med') return '#fdf6e7';
    if (poz.confidence === 'low') return '#fcecea';
    return 'transparent';
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Filter pills */}
      <div style={{ padding: '8px 12px', borderBottom: '1px solid #d4d2cb', display: 'flex', gap: 5, flexWrap: 'wrap', background: '#fbfaf7' }}>
        {FILTERS.map(f => {
          const isActive = filter === f.id;
          const count = counts[f.id];
          return (
            <button key={f.id} onClick={() => setFilter(f.id)} style={{
              background: isActive ? '#2a6fb5' : '#fff',
              color: isActive ? '#fff' : '#3b3b3b',
              border: `1px solid ${isActive ? '#2a6fb5' : '#d4d2cb'}`,
              padding: '3px 9px', borderRadius: 12, fontSize: 10, fontWeight: 500, cursor: 'pointer',
            }}>{f.label.replace('N', count)}</button>
          );
        })}
      </div>
      {/* Search */}
      <div style={{ padding: '8px 12px', borderBottom: '1px solid #d4d2cb', background: '#fbfaf7' }}>
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Filtruoti pozicijas…"
          style={{ width: '100%', padding: '5px 8px', border: '1px solid #d4d2cb', borderRadius: 5, fontSize: 11, background: '#fff', boxSizing: 'border-box' }}
        />
      </div>
      {/* Tree */}
      <div style={{ flex: 1, overflow: 'auto', background: '#fff' }}>
        {grouped.map(([skyrius, items]) => (
          <div key={skyrius}>
            <div style={{ padding: '8px 12px', background: '#f6f5f2', display: 'flex', alignItems: 'center', gap: 8, borderBottom: '1px solid #ebe8e3' }}>
              <span style={{ display: 'inline-block', width: 8, height: 8, background: '#2a6fb5', borderRadius: '50%' }} />
              <span style={{ fontWeight: 600, flex: 1 }}>{skyrius}</span>
              <span style={{ background: '#e8e5df', color: '#6b6863', fontSize: 9, padding: '1px 6px', borderRadius: 8 }}>{items.length}</span>
            </div>
            {items.map(poz => {
              const isSelected = selection?.kind === 'pozicija' && selection.id === poz.id;
              return (
                <div
                  key={poz.id}
                  onClick={() => setSelection({ kind: 'pozicija', id: poz.id, room_id: poz.room_id })}
                  onMouseEnter={() => poz.room_id && setHoveredRoomId(poz.room_id)}
                  onMouseLeave={() => setHoveredRoomId(null)}
                  style={{
                    padding: '7px 12px 7px 30px', borderBottom: '1px solid #ebe8e3',
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    cursor: 'pointer',
                    background: isSelected ? 'rgba(42,111,181,0.08)' : rowBg(poz),
                    borderLeft: isSelected ? '3px solid #2a6fb5' : '3px solid transparent',
                  }}
                >
                  <span style={{ flex: 1, color: isSelected ? '#171717' : '#3b3b3b', fontWeight: isSelected ? 500 : 400 }}>
                    {poz.aprasymas || poz.pavadinimas || '—'}
                  </span>
                  {editingId === poz.id ? (
                    <input
                      autoFocus type="number" value={editValue}
                      onClick={(e) => e.stopPropagation()}
                      onChange={(e) => setEditValue(e.target.value)}
                      onBlur={() => commitEdit(poz)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') commitEdit(poz);
                        if (e.key === 'Escape') setEditingId(null);
                      }}
                      style={{ width: 70, marginRight: 8, padding: '2px 4px', border: '1px solid #2a6fb5', borderRadius: 3, fontSize: 11, background: '#fff' }}
                    />
                  ) : (
                    <span
                      onClick={(e) => { e.stopPropagation(); startEdit(poz); }}
                      style={{ marginRight: 8, fontVariantNumeric: 'tabular-nums', color: poz.override_locked ? '#6f5fa3' : '#3b3b3b' }}
                    >
                      {poz.kiekis} {poz.vnt}
                      {poz.override_locked && ' 🔒'}
                    </span>
                  )}
                  <span title={`confidence: ${poz.confidence || '—'}`} style={{ width: 7, height: 7, background: confDot(poz), borderRadius: '50%' }} />
                </div>
              );
            })}
          </div>
        ))}
        {filtered.length === 0 && (
          <div style={{ padding: 20, textAlign: 'center', color: '#94a3b8', fontSize: 12 }}>
            {pozicijos.length === 0 ? 'Nėra pozicijų. Paleisk Sąmatų AI viršuje.' : 'Nėra atitinkančių filtrui.'}
          </div>
        )}
      </div>
      {/* Footer */}
      <div style={{ borderTop: '1px solid #d4d2cb', background: '#fbfaf7', padding: '10px 12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <div style={{ fontSize: 10, opacity: 0.6 }}>Σ neto</div>
          <div style={{ fontSize: 14, fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>{totalNet.toFixed(2)} €</div>
        </div>
        <button style={{
          background: '#2a6fb5', border: '1px solid #2a6fb5', color: '#fff',
          padding: '6px 12px', borderRadius: 5, fontSize: 12, fontWeight: 500, cursor: 'pointer',
        }}>Eksportuoti</button>
      </div>
    </div>
  );
}
