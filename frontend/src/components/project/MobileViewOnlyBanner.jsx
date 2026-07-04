// Phase C-1 Task 24: MobileViewOnlyBanner — bottom banner shown to
// coarse-pointer (touch) devices stating that Pathon editing is
// desktop-only. Mobile editing is Phase D. Dismissal persisted to
// localStorage so the banner only nags once per device.

import { useState, useEffect } from 'react';

const STORAGE_KEY = 'samatu_mobile_banner_dismissed';

export default function MobileViewOnlyBanner() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const isCoarse = typeof window !== 'undefined'
      && window.matchMedia?.('(pointer: coarse)').matches;
    if (!isCoarse) return;
    try {
      if (localStorage.getItem(STORAGE_KEY) === '1') return;
    } catch { return; }
    setVisible(true);
  }, []);

  const dismiss = () => {
    try { localStorage.setItem(STORAGE_KEY, '1'); } catch {}
    setVisible(false);
  };

  if (!visible) return null;
  return (
    <div className="absolute bottom-3 left-1/2 -translate-x-1/2 z-40 max-w-md text-center"
      style={{
        background: 'rgba(15,23,42,0.95)', color: '#fef3c7',
        padding: '10px 16px', borderRadius: 8, fontSize: 12,
      }}>
      Geriausia naudoti kompiuteryje. Mobilus režimas — peržiūros tik.
      <button onClick={dismiss} className="ml-3 underline">
        Aišku
      </button>
    </div>
  );
}
