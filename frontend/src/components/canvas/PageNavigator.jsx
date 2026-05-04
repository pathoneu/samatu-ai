// frontend/src/components/canvas/PageNavigator.jsx
/**
 * Sprint 3: page picker dropdown.
 *
 * Renders a list of pages with text label (page-type if available,
 * else "Puslapis N"). Click → setCurrentPage. Closes on outside click
 * or selection.
 *
 * Spec §5.4 (page nav) + §9 open question (thumbnails defer to Sprint 4).
 */
import { useEffect, useRef } from 'react';

export function PageNavigator({ pages, currentPage, onSelect, onClose }) {
  const ref = useRef(null);

  useEffect(() => {
    const onClickOutside = (e) => {
      if (ref.current && !ref.current.contains(e.target)) onClose?.();
    };
    document.addEventListener('mousedown', onClickOutside);
    return () => document.removeEventListener('mousedown', onClickOutside);
  }, [onClose]);

  return (
    <div ref={ref} style={{
      position: 'absolute', top: 48, left: 'calc(50% - 200px)',
      width: 400, maxHeight: 480, overflow: 'auto',
      background: '#fff', border: '1px solid #d4d2cb', borderRadius: 8,
      boxShadow: '0 8px 24px rgba(0,0,0,0.12)', padding: 8, zIndex: 50,
    }}>
      {pages.map((p, i) => (
        <button key={i} onClick={() => { onSelect(i); onClose?.(); }} style={{
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          width: '100%', padding: '8px 12px', borderRadius: 5,
          background: i === currentPage ? '#fdf6e7' : 'transparent',
          border: 0, cursor: 'pointer', textAlign: 'left', fontSize: 12,
        }}>
          <span style={{ fontWeight: i === currentPage ? 600 : 400 }}>
            Puslapis {i + 1}
          </span>
          <span style={{ opacity: 0.6, fontSize: 11 }}>{p.title || p.kind || '—'}</span>
        </button>
      ))}
    </div>
  );
}
