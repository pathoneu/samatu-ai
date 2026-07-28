// Phase C-1 Task 24: MobileViewOnlyBanner — bottom banner shown to
// coarse-pointer (touch) devices stating that Pathon editing is
// desktop-only. Mobile editing is Phase D. Dismissal persisted to
// localStorage so the banner only nags once per device.

import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';

const STORAGE_KEY = 'samatu_mobile_banner_dismissed';

export default function MobileViewOnlyBanner() {
  const { t } = useTranslation();
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
    // `fixed`, not `absolute` (2026-07-28): the workspace container is taller
    // than a phone viewport, so an absolutely-placed banner sat ~90 px below
    // the fold — mounted but unreadable. Pinned to the viewport it is seen.
    <div className="fixed bottom-3 left-1/2 -translate-x-1/2 z-40 max-w-[92vw] text-center"
      style={{
        background: 'rgba(15,23,42,0.95)', color: '#fef3c7',
        padding: '10px 16px', borderRadius: 8, fontSize: 12,
      }}>
      {t('project.mobileBanner.text')}
      <button onClick={dismiss} className="ml-3 underline">
        {t('project.mobileBanner.ok')}
      </button>
    </div>
  );
}
