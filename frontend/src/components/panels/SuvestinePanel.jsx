// frontend/src/components/panels/SuvestinePanel.jsx
/**
 * Sprint 3: Suvestinė tab.
 *
 * Σ totals card (medžiagos, DU, mechanizmai, pridėtinės, pelnas, PVM)
 * + per-category horizontal bars showing relative share.
 *
 * Spec §5.6 Suvestinė tab.
 */
export function SuvestinePanel({ rooms = [], pozicijos = [] }) {
  // Compute breakdown by skyrius
  const byCategory = new Map();
  let total = 0;
  for (const p of pozicijos) {
    const k = p.skyrius_label || p.skyrius || 'Kita';
    const v = Number(p.kiekis_x_kaina) || 0;
    byCategory.set(k, (byCategory.get(k) || 0) + v);
    total += v;
  }
  const sorted = Array.from(byCategory.entries()).sort((a, b) => b[1] - a[1]);
  const pvm = total * 0.21;
  const grand = total + pvm;

  const fmt = (n) => n.toFixed(2).replace('.', ',') + ' €';

  return (
    <div style={{ height: '100%', overflow: 'auto', padding: 16, background: '#fff', fontSize: 12 }}>
      <div style={{
        background: '#fbfaf7', border: '1px solid #d4d2cb', borderRadius: 8,
        padding: 14, marginBottom: 16,
      }}>
        <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px', color: '#6b6863' }}>
          Suvestinė
        </div>
        <div style={{ fontSize: 24, fontWeight: 700, marginTop: 4, fontVariantNumeric: 'tabular-nums' }}>
          {fmt(grand)}
        </div>
        <div style={{ fontSize: 11, color: '#6b6863', marginTop: 6 }}>
          Σ neto: <strong>{fmt(total)}</strong> &nbsp;·&nbsp; PVM 21%: {fmt(pvm)}
        </div>
      </div>

      <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px', color: '#6b6863', marginBottom: 8 }}>
        Pagal skyrius
      </div>
      {sorted.map(([cat, value]) => {
        const pct = total > 0 ? (value / total) * 100 : 0;
        return (
          <div key={cat} style={{ marginBottom: 10 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
              <span>{cat}</span>
              <span style={{ fontVariantNumeric: 'tabular-nums', color: '#3b3b3b' }}>{fmt(value)}</span>
            </div>
            <div style={{ height: 6, background: '#f0eeea', borderRadius: 3, overflow: 'hidden' }}>
              <div style={{ width: `${pct}%`, height: '100%', background: '#2a6fb5' }} />
            </div>
          </div>
        );
      })}
      {sorted.length === 0 && (
        <div style={{ padding: '20px 0', textAlign: 'center', color: '#94a3b8' }}>
          Nėra duomenų.
        </div>
      )}

      <div style={{ marginTop: 24, display: 'flex', gap: 8 }}>
        <button style={{
          flex: 1, background: '#2a6fb5', border: '1px solid #2a6fb5', color: '#fff',
          padding: '8px 12px', borderRadius: 5, fontSize: 12, fontWeight: 500, cursor: 'pointer',
        }}>Eksportuoti Excel</button>
        <button style={{
          flex: 1, background: '#fff', border: '1px solid #d4d2cb', color: '#3b3b3b',
          padding: '8px 12px', borderRadius: 5, fontSize: 12, fontWeight: 500, cursor: 'pointer',
        }}>PDF</button>
      </div>
    </div>
  );
}
