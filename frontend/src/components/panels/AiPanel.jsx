// frontend/src/components/panels/AiPanel.jsx
/**
 * Sprint 3: AI tab content.
 *
 * - "Run Sąmatų AI" button (calls existing /extract-interior)
 * - Recent runs list (timestamps, page count, ✓/✗ status)
 * - Click history item → loads that run back into Kiekiai (Sprint 4)
 *
 * For Sprint 3 we just render the Run button + an empty-state list.
 * History persistence is Sprint 4.
 *
 * Spec §5.6 AI tab.
 */
export function AiPanel({ onRunAi, isRunning = false, recentRuns = [] }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ padding: 16, background: '#fbfaf7', borderBottom: '1px solid #d4d2cb' }}>
        <button onClick={onRunAi} disabled={isRunning} style={{
          width: '100%', background: isRunning ? '#94a3b8' : '#2a6fb5',
          border: '1px solid #2a6fb5', color: '#fff',
          padding: '10px 12px', borderRadius: 6, fontSize: 13, fontWeight: 600,
          cursor: isRunning ? 'wait' : 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
        }}>
          {isRunning ? '⏳ AI dirba…' : '✨ Paleisti Sąmatų AI'}
        </button>
        <p style={{ marginTop: 10, fontSize: 11, color: '#6b6863', lineHeight: 1.5 }}>
          AI peržvelgs visus puslapius ir užpildys KŽ pozicijas. Esamos
          🔒 užfiksuotos pozicijos liks nepakitę.
        </p>
      </div>
      <div style={{ flex: 1, overflow: 'auto', padding: 12, background: '#fff' }}>
        <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px', color: '#6b6863', marginBottom: 8 }}>
          Paskutiniai paleidimai
        </div>
        {recentRuns.length === 0 ? (
          <div style={{ padding: '20px 0', textAlign: 'center', color: '#94a3b8', fontSize: 11 }}>
            Dar nebuvo AI paleidimų.
          </div>
        ) : recentRuns.map((run, i) => (
          <div key={i} style={{
            padding: '8px 10px', marginBottom: 4, background: '#f6f5f2', borderRadius: 5,
            display: 'flex', alignItems: 'center', gap: 8, fontSize: 11,
          }}>
            <span>{run.success ? '✓' : '✗'}</span>
            <div style={{ flex: 1 }}>
              <div>{new Date(run.timestamp).toLocaleString('lt-LT')}</div>
              <div style={{ fontSize: 10, opacity: 0.6 }}>
                {run.page_count} psl. · {run.model || 'opus-4-7'}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
