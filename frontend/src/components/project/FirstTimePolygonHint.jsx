import { useEffect, useState } from 'react';

const STORAGE_KEY = 'samatu_polygon_hint_seen';

export default function FirstTimePolygonHint({ active, onDismiss }) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (!active) { setVisible(false); return; }
    try {
      if (localStorage.getItem(STORAGE_KEY) === '1') return;
    } catch { return; }
    setVisible(true);
  }, [active]);

  const dismiss = () => {
    try { localStorage.setItem(STORAGE_KEY, '1'); } catch {}
    setVisible(false);
    onDismiss?.();
  };

  if (!visible) return null;
  return (
    <div
      className="absolute top-4 left-1/2 -translate-x-1/2 z-50 max-w-md"
      onClick={dismiss}
      style={{
        background: 'rgba(15, 23, 42, 0.95)',
        color: '#e2e8f0',
        borderRadius: 8,
        padding: '12px 16px',
        boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
        cursor: 'pointer',
      }}
    >
      <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 6 }}>
        Apveskite kambarį spustelėdami kampus
      </div>
      <div style={{ fontSize: 11, lineHeight: 1.5, opacity: 0.85 }}>
        <strong>Enter</strong> arba dvigubas paspaudimas — užbaigti<br/>
        <strong>Esc</strong> — atšaukti  ·  <strong>Backspace</strong> — pašalinti paskutinį tašką<br/>
        <strong>Shift</strong> — laisva kryptis  ·  <strong>Alt</strong> — laikinas snap'o išjungimas
      </div>
    </div>
  );
}
