// frontend/src/components/wizard/InlineEditor.jsx
/**
 * Sprint 3: inline editor used in wizard question slot when fixing a
 * number dispute. Replaces the question card text with [← back] +
 * input + [✓ Įrašyti].
 *
 * Spec §5.3 inline editor.
 */
import { useState, useEffect, useRef } from 'react';

export function InlineEditor({ poz, onCommit, onCancel }) {
  const [value, setValue] = useState(String(poz.kiekis ?? ''));
  const inputRef = useRef(null);

  useEffect(() => {
    inputRef.current?.focus();
    inputRef.current?.select();
  }, []);

  const tryCommit = () => {
    const n = Number.parseFloat(value);
    if (!Number.isFinite(n)) return;
    onCommit(n);
  };

  return (
    <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 10 }}>
      <button onClick={onCancel} title="Grįžti (Esc)" style={{
        background: 'transparent', border: '1px solid #d4d2cb',
        color: '#3b3b3b', padding: '6px 10px', borderRadius: 5,
        fontSize: 12, cursor: 'pointer',
      }}>← Grįžti</button>
      <span style={{ fontSize: 13, color: '#3b3b3b' }}>
        {poz.label.split('·')[1]?.trim() || poz.label}:
      </span>
      <input
        ref={inputRef}
        type="number" step="any" value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') tryCommit();
          if (e.key === 'Escape') onCancel();
        }}
        style={{
          width: 120, padding: '6px 10px',
          border: '1px solid #2a6fb5', borderRadius: 5,
          fontSize: 14, fontWeight: 600,
          fontVariantNumeric: 'tabular-nums',
        }}
      />
      <span style={{ fontSize: 13, color: '#3b3b3b' }}>{poz.vnt}</span>
      <button onClick={tryCommit} style={{
        background: '#2a6fb5', border: '1px solid #2a6fb5', color: '#fff',
        padding: '6px 14px', borderRadius: 5, fontSize: 12, fontWeight: 600, cursor: 'pointer',
      }}>✓ Įrašyti</button>
    </div>
  );
}
