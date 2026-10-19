// frontend/src/components/panels/SuvestinePanel.jsx
/**
 * Sprint 3: Suvestinė tab.
 *
 * Σ totals card (medžiagos, DU, mechanizmai, pridėtinės, pelnas, PVM)
 * + per-category horizontal bars showing relative share.
 *
 * Spec §5.6 Suvestinė tab.
 */
import { useTranslation } from '@/i18n/react';

export function SuvestinePanel({ rooms = [], pozicijos = [] }) {
  const { t } = useTranslation();
  // Compute breakdown by skyrius
  const byCategory = new Map();
  let total = 0;
  for (const p of pozicijos) {
    const k = p.skyrius_label || p.skyrius || t('workspace.suvestine.other');
    const v = Number(p.kiekis_x_kaina) || 0;
    byCategory.set(k, (byCategory.get(k) || 0) + v);
    total += v;
  }
  const sorted = Array.from(byCategory.entries()).sort((a, b) => b[1] - a[1]);
  const pvm = total * 0.21;
  const grand = total + pvm;

  const fmt = (n) => n.toFixed(2).replace('.', ',') + ' €';

  return (
    <div style={{ height: '100%', overflow: 'auto', padding: 16, background: 'hsl(var(--background))', fontSize: 12, color: 'hsl(var(--foreground))' }}>
      <div style={{
        background: 'hsl(var(--card))', border: '1px solid hsl(var(--border))', borderRadius: 8,
        padding: 14, marginBottom: 16,
      }}>
        <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px', color: 'hsl(var(--muted-foreground))' }}>
          {t('workspace.suvestine.title')}
        </div>
        <div style={{ fontSize: 24, fontWeight: 700, marginTop: 4, fontVariantNumeric: 'tabular-nums' }}>
          {fmt(grand)}
        </div>
        <div style={{ fontSize: 11, color: 'hsl(var(--muted-foreground))', marginTop: 6 }}>
          {t('workspace.suvestine.netVat')}<strong>{fmt(total)}</strong> &nbsp;·&nbsp;{t('workspace.suvestine.vatLabel', { pvm: fmt(pvm) })}
        </div>
      </div>

      <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px', color: 'hsl(var(--muted-foreground))', marginBottom: 8 }}>
        {t('workspace.suvestine.byCategory')}
      </div>
      {sorted.map(([cat, value]) => {
        const pct = total > 0 ? (value / total) * 100 : 0;
        return (
          <div key={cat} style={{ marginBottom: 10 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
              <span>{cat}</span>
              <span style={{ fontVariantNumeric: 'tabular-nums', color: 'hsl(var(--muted-foreground))' }}>{fmt(value)}</span>
            </div>
            <div style={{ height: 6, background: 'hsl(var(--muted))', borderRadius: 3, overflow: 'hidden' }}>
              <div style={{ width: `${pct}%`, height: '100%', background: 'hsl(var(--primary))' }} />
            </div>
          </div>
        );
      })}
      {sorted.length === 0 && (
        <div style={{ padding: '20px 0', textAlign: 'center', color: 'hsl(var(--muted-foreground))' }}>
          {t('workspace.suvestine.noData')}
        </div>
      )}

      <div style={{ marginTop: 24, display: 'flex', gap: 8 }}>
        <button style={{
          flex: 1, background: 'hsl(var(--primary))', border: '1px solid hsl(var(--primary))', color: 'hsl(var(--primary-foreground))',
          padding: '8px 12px', borderRadius: 5, fontSize: 12, fontWeight: 500, cursor: 'pointer',
        }}>{t('workspace.suvestine.exportExcel')}</button>
        <button style={{
          flex: 1, background: 'hsl(var(--card))', border: '1px solid hsl(var(--border-strong))', color: 'hsl(var(--foreground))',
          padding: '8px 12px', borderRadius: 5, fontSize: 12, fontWeight: 500, cursor: 'pointer',
        }}>{t('workspace.suvestine.exportPdf')}</button>
      </div>
    </div>
  );
}
