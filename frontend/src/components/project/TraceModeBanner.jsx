// Phase C-1 Task 23: TraceModeBanner — modal-mode indicator shown only while
// the polygon trace tool is active. Surfaces live vertex count, finish/cancel
// hint, and ortho-toggle status. Per UX research §7: "no mode indicator" is
// the #1 support ticket on every annotation tool, so this banner is mandatory.

import { ltPlural } from '@/lib/ltPlural';

export default function TraceModeBanner({ visible, polygonDraft, orthoEnabled }) {
  if (!visible) return null;
  const vertexCount = polygonDraft?.points?.length || 0;

  return (
    <div
      className="absolute top-3 left-1/2 -translate-x-1/2 z-40 flex items-center gap-3"
      style={{
        background: 'rgba(0, 184, 217, 0.95)', color: '#0f172a',
        padding: '6px 14px', borderRadius: 999,
        fontSize: 12, fontWeight: 600,
        boxShadow: '0 4px 12px rgba(0,0,0,0.25)',
      }}
    >
      <span>📐 Apvedinėjamas kambarys</span>
      <span style={{ opacity: 0.7 }}>·</span>
      <span style={{ opacity: 0.85, fontWeight: 500 }}>
        {vertexCount} {ltPlural(vertexCount, 'taškas', 'taškai', 'taškų')}
      </span>
      <span style={{ opacity: 0.7 }}>·</span>
      <span style={{ opacity: 0.85, fontWeight: 500 }}>
        Enter užbaigti  ·  Esc atšaukti
      </span>
      {!orthoEnabled && (
        <>
          <span style={{ opacity: 0.7 }}>·</span>
          <span style={{ background: 'rgba(255,255,255,0.4)', padding: '1px 6px', borderRadius: 4, fontSize: 10 }}>
            ortho IŠJUNGTA (F8)
          </span>
        </>
      )}
    </div>
  );
}
