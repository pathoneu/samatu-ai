import { useEffect, useState } from 'react';
import { recordDecision } from '@/lib/cvToolsApi';

/**
 * Right-side review queue for click-to-count candidates.
 *
 * Decisions are persisted via /api/cv/record-decision (which writes
 * the crop into data/symbol_training/<klass>/ for future YOLO).
 *
 * Hotkeys:
 *   A    accept the focused candidate
 *   R    reject the focused candidate
 *   ↑/↓  move focus
 *   Esc  close panel
 *
 * On "Užbaigti", calls onComplete(acceptedBboxes[]) so the parent
 * (PdfViewer / ProjectMainView) can convert them to a Kiekiai pozicija.
 */
export default function CountReviewPanel({
  projectId,
  pageIdx,
  candidates,
  klass,
  setKlass,
  onClose,
  onComplete,
  onUpdateMarkers,
  templateBbox,
  templateDpi = 200,
}) {
  const [decisions, setDecisions] = useState({});
  const [focus, setFocus] = useState(0);

  const high = candidates.filter(c => c.confidence >= 0.9);
  const med = candidates.filter(c => c.confidence >= 0.75 && c.confidence < 0.9);
  const low = candidates.filter(c => c.confidence < 0.75);

  const decide = async (idx, decision) => {
    const next = { ...decisions, [idx]: decision };
    setDecisions(next);
    onUpdateMarkers?.(candidates.map((c, i) => ({
      ...c,
      status: next[i] || 'pending',
    })));
    if (!klass) return;
    const c = candidates[idx];
    try {
      await recordDecision({
        project_id: projectId,
        page_idx: pageIdx,
        bbox: c.bbox,
        klass,
        decision,
        confidence: c.confidence,
        dpi: templateDpi,
      });
    } catch {
      // training-data write is best-effort; the user's takeoff is unaffected.
    }
  };

  const acceptAllHigh = () => {
    high.forEach(h => {
      const idx = candidates.indexOf(h);
      if (decisions[idx] !== 'accept') decide(idx, 'accept');
    });
  };

  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'a' || e.key === 'A') decide(focus, 'accept');
      else if (e.key === 'r' || e.key === 'R') decide(focus, 'reject');
      else if (e.key === 'ArrowDown') setFocus(f => Math.min(candidates.length - 1, f + 1));
      else if (e.key === 'ArrowUp') setFocus(f => Math.max(0, f - 1));
      else if (e.key === 'Escape') onClose?.();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focus, candidates, klass]);

  const acceptedCount = Object.entries(decisions)
    .filter(([, d]) => d === 'accept').length;

  const finish = () => {
    const accepted = candidates.filter((_, i) => decisions[i] === 'accept');
    onComplete?.(accepted, { klass, templateBbox, templateDpi });
  };

  return (
    <div className="border-l border-border w-80 p-3 space-y-3 text-sm bg-background flex flex-col h-full overflow-hidden">
      <div className="flex items-center justify-between">
        <div className="font-semibold">Rasta {candidates.length} kandidatų</div>
        <button onClick={onClose} className="text-muted-foreground hover:text-foreground text-xs">
          ✕
        </button>
      </div>

      <div className="text-xs text-muted-foreground">
        🟢 {high.length} aukšto · 🟡 {med.length} vidutinio · 🔴 {low.length} žemo
      </div>

      <label className="flex items-center gap-2 text-xs">
        <span className="w-16 shrink-0">Klasė</span>
        <input
          type="text"
          value={klass}
          onChange={(e) => setKlass(e.target.value)}
          placeholder="pvz., rozete"
          className="flex-1 px-2 py-1 border border-input rounded text-xs"
        />
      </label>

      <button
        onClick={acceptAllHigh}
        className="w-full bg-emerald-600 text-white py-1.5 rounded text-xs hover:bg-emerald-700 transition-colors"
      >
        Priimti visus aukšto pasitikėjimo ({high.length})
      </button>

      <ul className="flex-1 space-y-1 overflow-y-auto">
        {candidates.map((c, i) => {
          const dec = decisions[i] || 'pending';
          return (
            <li
              key={i}
              onMouseEnter={() => setFocus(i)}
              className={`flex items-center gap-2 text-xs px-2 py-1 rounded cursor-pointer ${
                i === focus ? 'bg-muted' : ''
              } ${dec === 'reject' ? 'opacity-50' : ''}`}
            >
              <span className={
                c.confidence >= 0.9 ? 'text-emerald-700'
                  : c.confidence >= 0.75 ? 'text-amber-700'
                  : 'text-red-700'
              }>
                {Math.round(c.confidence * 100)}%
              </span>
              <span className="flex-1 font-mono text-muted-foreground">
                @{c.x},{c.y}
              </span>
              <button
                onClick={() => decide(i, 'accept')}
                className={`px-1.5 rounded ${dec === 'accept' ? 'bg-emerald-600 text-white' : 'hover:bg-emerald-50'}`}
                title="Priimti (A)"
              >
                ✓
              </button>
              <button
                onClick={() => decide(i, 'reject')}
                className={`px-1.5 rounded ${dec === 'reject' ? 'bg-red-600 text-white' : 'hover:bg-red-50'}`}
                title="Atmesti (R)"
              >
                ✕
              </button>
            </li>
          );
        })}
      </ul>

      <button
        onClick={finish}
        disabled={acceptedCount === 0 || !klass}
        className="w-full bg-blue-600 text-white py-2 rounded text-xs hover:bg-blue-700 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
      >
        Užbaigti — pridėti {acceptedCount} į Kiekius
      </button>
    </div>
  );
}
