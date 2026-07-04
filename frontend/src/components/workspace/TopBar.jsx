// frontend/src/components/workspace/TopBar.jsx
/**
 * Sprint 3: chrome top bar (48px tall).
 *
 * Layout (left → right):
 *   [logo] {projectName} / {subtitle}  |  ← {page/total ▾} →  {pageTitle}
 *   ...flex spacer...
 *   [− zoom% +]  [🔍 Ieškoti]  [✨ Pathon]  [⋯]
 *
 * Sprint 3-B: dropped the Patikrinti queue badge along with the
 * verification wizard. Trust by default, fix by exception.
 *
 * Spec §5.4 top-bar behaviors.
 */
import { useStore } from 'zustand';
import { viewerStore } from '../../lib/viewerStore';

export function TopBar({
  projectName,
  subtitle,
  pageTitle,
  totalPages,
  onPrevPage,
  onNextPage,
  onPagePicker,
  onZoomOut,
  onZoomIn,
  onSearch,
  onAiRun,
  onMore,
}) {
  const scale = useStore(viewerStore, (s) => s.scale);
  const currentPage = useStore(viewerStore, (s) => s.currentPage);
  const zoomPct = Math.round(scale * 100);

  return (
    <div style={{
      display: 'flex', alignItems: 'center', height: 48,
      background: 'hsl(var(--card))', borderBottom: '1px solid hsl(var(--border))',
      padding: '0 12px', gap: 10, fontSize: 13, color: 'hsl(var(--foreground))',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <div style={{
          width: 26, height: 26, background: 'hsl(var(--primary))',
          borderRadius: 5, display: 'flex', alignItems: 'center',
          justifyContent: 'center', color: 'hsl(var(--primary-foreground))', fontWeight: 700, fontSize: 11,
        }}>SĄ</div>
        <span style={{ fontWeight: 600 }}>{projectName}</span>
        {subtitle && <>
          <span style={{ opacity: 0.4 }}>/</span>
          <span style={{ opacity: 0.7 }}>{subtitle}</span>
        </>}
      </div>
      <div style={{ height: 20, width: 1, background: 'hsl(var(--border))' }} />
      <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
        <button onClick={onPrevPage} disabled={currentPage <= 0}
          style={{ background: 'transparent', border: 0, color: 'hsl(var(--foreground))', fontSize: 14, padding: '2px 4px', cursor: 'pointer' }}>←</button>
        <button onClick={onPagePicker} style={{
          background: 'hsl(var(--muted))', border: '1px solid hsl(var(--border-strong))', color: 'hsl(var(--foreground))',
          padding: '3px 10px', borderRadius: 5, fontSize: 12, fontWeight: 500, cursor: 'pointer',
        }}>{currentPage + 1} / {totalPages} ▾</button>
        <button onClick={onNextPage} disabled={currentPage >= totalPages - 1}
          style={{ background: 'transparent', border: 0, color: 'hsl(var(--foreground))', fontSize: 14, padding: '2px 4px', cursor: 'pointer' }}>→</button>
      </div>
      {pageTitle && <span style={{ opacity: 0.6, fontSize: 12 }}>{pageTitle}</span>}
      <div style={{ flex: 1 }} />
      <div style={{
        display: 'flex', alignItems: 'center', background: 'hsl(var(--muted))',
        border: '1px solid hsl(var(--border-strong))', borderRadius: 5, padding: 1, color: 'hsl(var(--foreground))',
      }}>
        <button onClick={onZoomOut} style={{ background: 'transparent', border: 0, color: 'inherit', padding: '2px 8px', fontSize: 14, cursor: 'pointer' }}>−</button>
        <span style={{ fontVariantNumeric: 'tabular-nums', minWidth: 42, textAlign: 'center', fontSize: 12 }}>{zoomPct}%</span>
        <button onClick={onZoomIn} style={{ background: 'transparent', border: 0, color: 'inherit', padding: '2px 8px', fontSize: 14, cursor: 'pointer' }}>+</button>
      </div>
      <button onClick={onSearch} style={{
        background: 'hsl(var(--muted))', border: '1px solid hsl(var(--border-strong))', color: 'hsl(var(--foreground))',
        padding: '5px 10px', borderRadius: 5, fontSize: 12, cursor: 'pointer',
      }}>🔍 Ieškoti</button>
      <button onClick={onAiRun} style={{
        background: 'hsl(var(--primary))', border: '1px solid hsl(var(--primary))', color: 'hsl(var(--primary-foreground))',
        padding: '6px 14px', borderRadius: 5, fontSize: 12, fontWeight: 600,
        display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer',
        boxShadow: '0 1px 3px hsl(var(--primary) / 0.3)',
      }}>✨ Pathon</button>
      <button onClick={onMore} style={{
        background: 'hsl(var(--muted))', border: '1px solid hsl(var(--border-strong))', color: 'hsl(var(--foreground))',
        padding: '5px 10px', borderRadius: 5, fontSize: 12, cursor: 'pointer',
      }}>⋯</button>
    </div>
  );
}
