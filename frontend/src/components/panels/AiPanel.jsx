// frontend/src/components/panels/AiPanel.jsx
/**
 * Sprint 3: AI tab content.
 *
 * - "Run Pathon" button (calls existing /extract-interior)
 * - Recent runs list (timestamps, page count, ✓/✗ status)
 * - Click history item → loads that run back into Kiekiai (Sprint 4)
 *
 * For Sprint 3 we just render the Run button + an empty-state list.
 * History persistence is Sprint 4.
 *
 * Spec §5.6 AI tab.
 */
import { useTranslation } from '@/i18n/react';

export function AiPanel({ onRunAi, isRunning = false, recentRuns = [] }) {
  const { t } = useTranslation();
  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ padding: 16, background: 'hsl(var(--card))', borderBottom: '1px solid hsl(var(--border))' }}>
        <button onClick={onRunAi} disabled={isRunning} style={{
          width: '100%', background: isRunning ? 'hsl(var(--muted))' : 'hsl(var(--primary))',
          border: '1px solid hsl(var(--primary))', color: 'hsl(var(--primary-foreground))',
          padding: '10px 12px', borderRadius: 6, fontSize: 13, fontWeight: 600,
          cursor: isRunning ? 'wait' : 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
        }}>
          {isRunning ? t('workspace.ai.running') : t('workspace.ai.run')}
        </button>
        <p style={{ marginTop: 10, fontSize: 11, color: 'hsl(var(--muted-foreground))', lineHeight: 1.5 }}>
          {t('workspace.ai.desc')}
        </p>
      </div>
      <div style={{ flex: 1, overflow: 'auto', padding: 12, background: 'hsl(var(--background))' }}>
        <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px', color: 'hsl(var(--muted-foreground))', marginBottom: 8 }}>
          {t('workspace.ai.recentRuns')}
        </div>
        {recentRuns.length === 0 ? (
          <div style={{ padding: '20px 0', textAlign: 'center', color: 'hsl(var(--muted-foreground))', fontSize: 11 }}>
            {t('workspace.ai.noRuns')}
          </div>
        ) : recentRuns.map((run, i) => (
          <div key={i} style={{
            padding: '8px 10px', marginBottom: 4, background: 'hsl(var(--muted))', borderRadius: 5,
            display: 'flex', alignItems: 'center', gap: 8, fontSize: 11, color: 'hsl(var(--foreground))',
          }}>
            <span>{run.success ? '✓' : '✗'}</span>
            <div style={{ flex: 1 }}>
              <div>{new Date(run.timestamp).toLocaleString('lt-LT')}</div>
              <div style={{ fontSize: 10, opacity: 0.6 }}>
                {t('workspace.ai.runInfo', { pages: run.page_count, model: run.model || 'opus-4-7' })}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
