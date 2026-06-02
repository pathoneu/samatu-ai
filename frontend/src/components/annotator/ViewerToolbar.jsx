/**
 * ViewerToolbar — fixed top toolbar for the Annotator viewer.
 *
 * Tools: Select / Measure / Calibrate / Symbols / Edit Wall
 * Actions: Undo / Redo / Save / Export Excel / Verify All Rooms
 *
 * Active tool gets a highlighted background. Each control has a
 * Lithuanian tooltip + keyboard shortcut where applicable.
 *
 * No business logic — purely a presentational dispatcher. Callers
 * pass current tool + state and a callback per action.
 */
import React from 'react';
import { TOOLS } from './AnnotationCanvas';

const TOOL_BUTTONS = [
  { tool: TOOLS.NONE,         label: 'Pasirinkti',     icon: '↖',  hotkey: 'S' },
  { tool: TOOLS.MEASURE,      label: 'Matuoti',        icon: '📏', hotkey: 'M' },
  { tool: TOOLS.CALIBRATE,    label: 'Kalibruoti',     icon: '⚖',  hotkey: 'C' },
  { tool: TOOLS.PLACE_SYMBOL, label: 'Simboliai',      icon: '⚡', hotkey: 'Y' },
  { tool: TOOLS.EDIT_WALL,    label: 'Redaguoti sieną', icon: '✎', hotkey: 'E' },
];

export default function ViewerToolbar({
  tool,
  setTool,
  onUndo,
  onRedo,
  canUndo,
  canRedo,
  onSave,
  onExport,
  onVerifyAll,
  walkthroughActive,
  saveStatus,
  scale,
  pageNum,
  numPages,
  onPageChange,
}) {
  const btn = (active, disabled = false) =>
    `flex items-center gap-1.5 rounded border px-3 py-1.5 text-sm transition-colors
     ${active
       ? 'border-blue-600 bg-blue-50 text-blue-700 font-medium'
       : 'border-neutral-300 bg-white text-neutral-700 hover:bg-neutral-50'}
     ${disabled ? 'cursor-not-allowed opacity-40 hover:bg-white' : 'cursor-pointer'}
    `;

  return (
    <div className="flex items-center gap-1 border-b border-neutral-200 bg-white px-3 py-2 shadow-sm">
      {/* Tool group */}
      <div className="flex items-center gap-1">
        {TOOL_BUTTONS.map((b) => (
          <button
            key={b.tool}
            type="button"
            onClick={() => setTool(b.tool)}
            className={btn(tool === b.tool)}
            title={`${b.label} (${b.hotkey})`}
          >
            <span className="text-base leading-none">{b.icon}</span>
            <span className="hidden sm:inline">{b.label}</span>
          </button>
        ))}
      </div>

      <div className="mx-3 h-6 w-px bg-neutral-200" />

      {/* Undo/Redo */}
      <div className="flex items-center gap-1">
        <button
          type="button"
          onClick={onUndo}
          disabled={!canUndo}
          className={btn(false, !canUndo)}
          title="Atšaukti (Ctrl+Z)"
        >
          <span className="text-base leading-none">↶</span>
          <span className="hidden sm:inline">Atšaukti</span>
        </button>
        <button
          type="button"
          onClick={onRedo}
          disabled={!canRedo}
          className={btn(false, !canRedo)}
          title="Pakartoti (Ctrl+Y)"
        >
          <span className="text-base leading-none">↷</span>
          <span className="hidden sm:inline">Pakartoti</span>
        </button>
      </div>

      <div className="mx-3 h-6 w-px bg-neutral-200" />

      {/* Save / Export / Verify */}
      <div className="flex items-center gap-1">
        <button
          type="button"
          onClick={onSave}
          className={btn(false)}
          title="Išsaugoti anotacijas"
        >
          <span className="text-base leading-none">💾</span>
          <span className="hidden sm:inline">Saugoti</span>
        </button>
        {onExport && (
          <button
            type="button"
            onClick={onExport}
            className={btn(false)}
            title="Eksportuoti į Excel"
          >
            <span className="text-base leading-none">⬇</span>
            <span className="hidden sm:inline">Excel</span>
          </button>
        )}
        <button
          type="button"
          onClick={onVerifyAll}
          className={btn(walkthroughActive)}
          title="Tikrinti visus kambarius paeiliui"
        >
          <span className="text-base leading-none">✓</span>
          <span className="hidden sm:inline">Tikrinti</span>
        </button>
      </div>

      <div className="flex-1" />

      {/* Status info */}
      <div className="flex items-center gap-3 text-xs text-neutral-500">
        {scale && (
          <span title="Aktyvus mastelis">
            Mastelis: <strong className="font-mono">{scale.toFixed(2)}</strong> mm/px
          </span>
        )}
        {saveStatus === 'saved' && (
          <span className="rounded bg-emerald-50 px-2 py-0.5 text-emerald-700">✓ Išsaugota</span>
        )}
        {saveStatus === 'saving' && (
          <span className="text-neutral-500">Saugoma…</span>
        )}
        {numPages > 1 && onPageChange && (
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => onPageChange(Math.max(1, pageNum - 1))}
              disabled={pageNum <= 1}
              className="rounded border border-neutral-300 px-2 py-0.5 disabled:opacity-30"
            >‹</button>
            <span className="font-mono">{pageNum}/{numPages}</span>
            <button
              type="button"
              onClick={() => onPageChange(Math.min(numPages, pageNum + 1))}
              disabled={pageNum >= numPages}
              className="rounded border border-neutral-300 px-2 py-0.5 disabled:opacity-30"
            >›</button>
          </div>
        )}
      </div>
    </div>
  );
}
