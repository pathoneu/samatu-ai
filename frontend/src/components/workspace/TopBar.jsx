// frontend/src/components/workspace/TopBar.jsx
/**
 * Sprint 3: chrome top bar (48px tall).
 *
 * Layout (left → right):
 *   [logo] {projectName} / {subtitle}  |  ← {page/total ▾} →  {pageTitle}
 *   ...flex spacer...
 *   [− zoom% +]  [🔍 Ieškoti]  [🟡 N →]?  [✨ Sąmatų AI]  [⋯]
 *
 * Patikrinti button hidden when queueCount===0.
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
  queueCount,
  onPrevPage,
  onNextPage,
  onPagePicker,
  onZoomOut,
  onZoomIn,
  onSearch,
  onWizard,
  onAiRun,
  onMore,
}) {
  const scale = useStore(viewerStore, (s) => s.scale);
  const currentPage = useStore(viewerStore, (s) => s.currentPage);
  const zoomPct = Math.round(scale * 100);

  return (
    <div style={{
      display: 'flex', alignItems: 'center', height: 48,
      background: '#fbfaf7', borderBottom: '1px solid #d4d2cb',
      padding: '0 12px', gap: 10, fontSize: 13, color: '#171717',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <div style={{
          width: 26, height: 26, background: '#2a6fb5',
          borderRadius: 5, display: 'flex', alignItems: 'center',
          justifyContent: 'center', color: '#fff', fontWeight: 700, fontSize: 11,
        }}>SĄ</div>
        <span style={{ fontWeight: 600 }}>{projectName}</span>
        {subtitle && <>
          <span style={{ opacity: 0.4 }}>/</span>
          <span style={{ opacity: 0.7 }}>{subtitle}</span>
        </>}
      </div>
      <div style={{ height: 20, width: 1, background: '#d4d2cb' }} />
      <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
        <button onClick={onPrevPage} disabled={currentPage <= 0}
          style={{ background: 'transparent', border: 0, color: '#171717', fontSize: 14, padding: '2px 4px', cursor: 'pointer' }}>←</button>
        <button onClick={onPagePicker} style={{
          background: '#fff', border: '1px solid #d4d2cb', color: '#171717',
          padding: '3px 10px', borderRadius: 5, fontSize: 12, fontWeight: 500, cursor: 'pointer',
        }}>{currentPage + 1} / {totalPages} ▾</button>
        <button onClick={onNextPage} disabled={currentPage >= totalPages - 1}
          style={{ background: 'transparent', border: 0, color: '#171717', fontSize: 14, padding: '2px 4px', cursor: 'pointer' }}>→</button>
      </div>
      {pageTitle && <span style={{ opacity: 0.6, fontSize: 12 }}>{pageTitle}</span>}
      <div style={{ flex: 1 }} />
      <div style={{
        display: 'flex', alignItems: 'center', background: '#fff',
        border: '1px solid #d4d2cb', borderRadius: 5, padding: 1,
      }}>
        <button onClick={onZoomOut} style={{ background: 'transparent', border: 0, padding: '2px 8px', fontSize: 14, cursor: 'pointer' }}>−</button>
        <span style={{ fontVariantNumeric: 'tabular-nums', minWidth: 42, textAlign: 'center', fontSize: 12 }}>{zoomPct}%</span>
        <button onClick={onZoomIn} style={{ background: 'transparent', border: 0, padding: '2px 8px', fontSize: 14, cursor: 'pointer' }}>+</button>
      </div>
      <button onClick={onSearch} style={{
        background: '#fff', border: '1px solid #d4d2cb', color: '#3b3b3b',
        padding: '5px 10px', borderRadius: 5, fontSize: 12, cursor: 'pointer',
      }}>🔍 Ieškoti</button>
      {queueCount > 0 && (
        <button onClick={onWizard} style={{
          background: '#fdf6e7', border: '1px solid #c97a2c', color: '#9a5d20',
          padding: '6px 12px', borderRadius: 5, fontSize: 12, fontWeight: 600,
          display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer',
        }}>
          <span style={{ display: 'inline-block', width: 6, height: 6, background: '#c97a2c', borderRadius: '50%' }} />
          Patikrinti {queueCount} →
        </button>
      )}
      <button onClick={onAiRun} style={{
        background: '#2a6fb5', border: '1px solid #2a6fb5', color: '#fff',
        padding: '6px 14px', borderRadius: 5, fontSize: 12, fontWeight: 600,
        display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer',
        boxShadow: '0 1px 3px rgba(42,111,181,0.3)',
      }}>✨ Sąmatų AI</button>
      <button onClick={onMore} style={{
        background: '#fff', border: '1px solid #d4d2cb', color: '#3b3b3b',
        padding: '5px 10px', borderRadius: 5, fontSize: 12, cursor: 'pointer',
      }}>⋯</button>
    </div>
  );
}
