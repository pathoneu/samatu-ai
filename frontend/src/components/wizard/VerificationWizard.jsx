// frontend/src/components/wizard/VerificationWizard.jsx
/**
 * Sprint 3: opt-in verification wizard.
 *
 * Bottom panel ~140px. Reads viewerStore.verificationQueue + verificationIndex
 * + wizardOpen. When wizardOpen===true, this component renders; the parent
 * page dims the rest of the UI to opacity 0.45.
 *
 * Three actions per step:
 *   - Taip ✓ (primary blue)         → confirm, advance. Shift+Taip = lock 🔒
 *   - Pataisyti (cream amber)       → trigger contextual gesture by dispute_type
 *   - Praleisti → (subtle text link) → mark skipped, advance
 *
 * Completion state shows "Visi N patikrinti! Σ ..." + Eksportuoti.
 *
 * Spec §5.3 + §4.5 wizard flow.
 */
import { useEffect, useState, useCallback } from 'react';
import { useStore } from 'zustand';
import { viewerStore } from '../../lib/viewerStore';
import { isQueueComplete } from '../../lib/verificationQueue';
import { overrideQuantity } from '../../lib/gestureApi';
import { abortRegistry } from '../../lib/abortRegistry';
import { InlineEditor } from './InlineEditor';

function polygonBoundingBox(poly) {
  if (!poly || poly.length === 0) return null;
  let minX = 1, minY = 1, maxX = 0, maxY = 0;
  for (const [x, y] of poly) {
    if (x < minX) minX = x;
    if (y < minY) minY = y;
    if (x > maxX) maxX = x;
    if (y > maxY) maxY = y;
  }
  return { minX, minY, maxX, maxY };
}

function fitToBox(bbox, viewportW, viewportH, paddingPct = 0.30) {
  // bbox in pdf-pct space; we want to compute scale + translate so the
  // bbox (with padding) fits the viewport center.
  if (!bbox) return null;
  const bboxW = bbox.maxX - bbox.minX;
  const bboxH = bbox.maxY - bbox.minY;
  const padW = bboxW * paddingPct;
  const padH = bboxH * paddingPct;
  // canvas natural size unknown to wizard — use viewport dims directly,
  // assuming canvas displays at scale 1.0 fills viewport
  const targetWPct = bboxW + padW * 2;
  const targetHPct = bboxH + padH * 2;
  const scale = Math.min(
    viewportW / (targetWPct * viewportW),
    viewportH / (targetHPct * viewportH),
  ) || 1;
  const cx = (bbox.minX + bbox.maxX) / 2;
  const cy = (bbox.minY + bbox.maxY) / 2;
  // translate so the centroid lands at viewport center
  const tx = viewportW / 2 - cx * viewportW * scale;
  const ty = viewportH / 2 - cy * viewportH * scale;
  return { scale, translate: { x: tx, y: ty } };
}

export function VerificationWizard({
  rooms = [], pozicijos = [], currentAssumptions = {},
  onRecomputed, onGestureEvent,
}) {
  const wizardOpen = useStore(viewerStore, (s) => s.wizardOpen);
  const setWizardOpen = useStore(viewerStore, (s) => s.setWizardOpen);
  const setWizardItemPolygon = useStore(viewerStore, (s) => s.setWizardItemPolygon);
  const setLockOnConfirm = useStore(viewerStore, (s) => s.setLockOnConfirm);
  const setCurrentTool = useStore(viewerStore, (s) => s.setCurrentTool);
  const setTransform = useStore(viewerStore, (s) => s.setTransform);
  const queue = useStore(viewerStore, (s) => s.verificationQueue);
  const index = useStore(viewerStore, (s) => s.verificationIndex);
  const advance = useStore(viewerStore, (s) => s.advanceVerification);

  const [showInlineEditor, setShowInlineEditor] = useState(false);

  const item = queue[index];

  // Drive auto-zoom: whenever active item changes, set wizardItemPolygon
  // and fit transform so polygon bbox + 30% padding lands centered in
  // the canvas viewport (window dims minus chrome: 50px rail + 320px right
  // panel, 48px topbar + 140px wizard).
  useEffect(() => {
    if (wizardOpen && item?.polygon) {
      setWizardItemPolygon(item.polygon);
      const bbox = polygonBoundingBox(item.polygon);
      const fit = fitToBox(bbox, window.innerWidth - 50 - 320, window.innerHeight - 48 - 140);
      if (fit) setTransform(fit);
    } else {
      setWizardItemPolygon(null);
    }
  }, [wizardOpen, item, setWizardItemPolygon, setTransform]);

  // Esc closes wizard
  useEffect(() => {
    if (!wizardOpen) return;
    const onKey = (e) => {
      if (e.key === 'Escape') {
        if (showInlineEditor) {
          setShowInlineEditor(false);
        } else {
          setWizardOpen(false);
        }
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [wizardOpen, showInlineEditor, setWizardOpen]);

  const handleYes = useCallback(async (e) => {
    if (!item) return;
    const lock = e?.shiftKey === true;
    setLockOnConfirm(lock);
    onGestureEvent?.({
      type: lock ? 'verify_yes_lock' : 'verify_yes',
      target: { kind: 'pozicija', id: item.id },
      outcome: 'success', duration_ms: 0,
    });
    if (lock) {
      // Apply lock via override-with-same-value
      const startedAt = Date.now();
      try {
        const signal = abortRegistry.takeSignal('verify_lock');
        const result = await overrideQuantity({
          rooms, pozicijos, currentAssumptions,
          targetPozicijaId: item.id, newValue: item.kiekis, signal,
        });
        onRecomputed?.(result);
      } catch (err) {
        if (err.name !== 'AbortError') console.error('[verify lock] failed:', err);
      }
    }
    advance();
  }, [item, setLockOnConfirm, onGestureEvent, advance, rooms, pozicijos, currentAssumptions, onRecomputed]);

  const handleFix = useCallback(() => {
    if (!item) return;
    if (item.dispute_type === 'number') {
      setShowInlineEditor(true);
    } else if (item.dispute_type === 'count') {
      setCurrentTool('g2');
      onGestureEvent?.({ type: 'verify_fix', target: { kind: 'pozicija', id: item.id }, outcome: 'success', duration_ms: 0 });
    } else {
      setCurrentTool('g1');
      onGestureEvent?.({ type: 'verify_fix', target: { kind: 'pozicija', id: item.id }, outcome: 'success', duration_ms: 0 });
    }
  }, [item, setCurrentTool, onGestureEvent]);

  const handleSkip = useCallback(() => {
    if (!item) return;
    onGestureEvent?.({
      type: 'verify_skip',
      target: { kind: 'pozicija', id: item.id },
      outcome: 'success', duration_ms: 0,
    });
    advance();
  }, [item, onGestureEvent, advance]);

  const handleClose = useCallback(() => {
    setWizardOpen(false);
    setWizardItemPolygon(null);
  }, [setWizardOpen, setWizardItemPolygon]);

  const handleInlineCommit = useCallback(async (newValue) => {
    if (!item) return;
    setShowInlineEditor(false);
    const startedAt = Date.now();
    try {
      const signal = abortRegistry.takeSignal('g7');
      const result = await overrideQuantity({
        rooms, pozicijos, currentAssumptions,
        targetPozicijaId: item.id, newValue, signal,
      });
      onRecomputed?.(result);
      onGestureEvent?.({ type: 'verify_fix_commit', target: { kind: 'pozicija', id: item.id }, outcome: 'success', duration_ms: Date.now() - startedAt });
      advance();
    } catch (err) {
      if (err.name !== 'AbortError') {
        onGestureEvent?.({ type: 'verify_fix_commit', target: { kind: 'pozicija', id: item.id }, outcome: 'error', duration_ms: Date.now() - startedAt });
        alert(err.envelope?.user_message || `Klaida: ${err.message}`);
      }
    }
  }, [item, rooms, pozicijos, currentAssumptions, onRecomputed, onGestureEvent, advance]);

  if (!wizardOpen) return null;

  // Completion state
  if (isQueueComplete(index, queue.length)) {
    return (
      <div style={wizardPanelStyle}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 18, justifyContent: 'space-between' }}>
          <div>
            <div style={{ fontSize: 14, fontWeight: 600, color: '#2f7d5b' }}>
              ✓ Visi {queue.length} patikrinti
            </div>
            <div style={{ fontSize: 12, color: '#6b6863', marginTop: 4 }}>
              Suvestinė pasiekiama dešinės panelės skirtuke „Suvestinė".
            </div>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={handleClose} style={primaryBtn}>Eksportuoti KŽ</button>
            <button onClick={handleClose} style={ghostBtn}>Grįžti</button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={wizardPanelStyle}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 18, position: 'relative' }}>
        {/* Progress */}
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: 60 }}>
          <div style={{ fontSize: 11, color: '#6b6863', textTransform: 'uppercase', letterSpacing: '0.5px', fontWeight: 600 }}>
            {index + 1} / {queue.length}
          </div>
          <div style={{ display: 'flex', gap: 4, marginTop: 6 }}>
            {queue.map((_, i) => (
              <span key={i} style={{
                width: 16, height: 4, borderRadius: 2,
                background: i < index ? '#2f7d5b' : i === index ? '#c97a2c' : '#e8e5df',
              }} />
            ))}
          </div>
        </div>
        <div style={{ height: 50, width: 1, background: '#e8e5df' }} />

        {/* Question or InlineEditor */}
        {showInlineEditor && item ? (
          <InlineEditor
            poz={item}
            onCommit={handleInlineCommit}
            onCancel={() => setShowInlineEditor(false)}
          />
        ) : item && (
          <>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 11, color: '#9a5d20', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px', display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ display: 'inline-block', width: 6, height: 6, background: item.confidence === 'low' ? '#a7493f' : '#c97a2c', borderRadius: '50%' }} />
                Reikia patikrinti · {item.label.split('·')[0]?.trim() || 'Pozicija'}
              </div>
              <div style={{ fontSize: 15, fontWeight: 600, marginTop: 4, color: '#171717' }}>
                {item.label.split('·')[1]?.trim() || item.label}: <span style={{ color: '#9a5d20' }}>{item.kiekis} {item.vnt}</span>
              </div>
              {item.saltinis && (
                <div style={{ fontSize: 11, color: '#6b6863', marginTop: 3 }}>
                  Šaltinis: {item.saltinis}
                </div>
              )}
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6, alignItems: 'stretch', minWidth: 200 }}>
              <div style={{ display: 'flex', gap: 6 }}>
                <button onClick={handleYes} style={primaryBtn} title="Shift+Taip = užfiksuoti 🔒">✓ Taip</button>
                <button onClick={handleFix} style={amberBtn}>Pataisyti</button>
              </div>
              <button onClick={handleSkip} style={skipBtn}>Praleisti →</button>
            </div>
          </>
        )}

        {/* Close button */}
        <button onClick={handleClose} title="Uždaryti (Esc)" style={{
          position: 'absolute', top: -8, right: -8,
          background: 'transparent', border: 0, fontSize: 16, color: '#94a3b8', cursor: 'pointer',
        }}>✕</button>
      </div>
    </div>
  );
}

const wizardPanelStyle = {
  position: 'absolute', bottom: 0, left: 0, right: 0,
  background: '#fff', borderTop: '2px solid #c97a2c',
  padding: '14px 20px', boxShadow: '0 -4px 12px rgba(0,0,0,0.06)',
  zIndex: 20,
};

const primaryBtn = {
  flex: 1, background: '#2a6fb5', border: '1px solid #2a6fb5',
  color: '#fff', padding: '8px 14px', borderRadius: 5,
  fontSize: 12, fontWeight: 600, cursor: 'pointer',
};

const amberBtn = {
  flex: 1, background: '#fff', border: '1px solid #c97a2c',
  color: '#9a5d20', padding: '8px 14px', borderRadius: 5,
  fontSize: 12, fontWeight: 600, cursor: 'pointer',
};

const skipBtn = {
  background: 'transparent', border: 0, color: '#6b6863',
  padding: '4px 8px', borderRadius: 5, fontSize: 11, cursor: 'pointer',
};

const ghostBtn = {
  background: 'transparent', border: '1px solid #d4d2cb',
  color: '#3b3b3b', padding: '8px 14px', borderRadius: 5,
  fontSize: 12, fontWeight: 500, cursor: 'pointer',
};
