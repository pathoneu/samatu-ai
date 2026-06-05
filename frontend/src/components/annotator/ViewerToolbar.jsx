/**
 * ViewerToolbar — fixed top toolbar for the Annotator viewer.
 *
 * Tools: Select / Measure / Calibrate / Symbols / Edit Wall
 * Actions: Undo / Redo / Save / Export Excel / Verify All Rooms
 *
 * 2026-06-05: emoji glyphs replaced with Lucide React icons. Every
 * icon-only button carries an aria-label so Playwright's
 * `getByRole('button', {name})` and screen readers both work. Active
 * tool gets a colored bottom bar (sub-pixel underline) and a tinted
 * background — same visual language as Togal / Kreo / Figma toolbars.
 * Light-paper theme to match the rest of the app (index.css's
 * `--background: #f6f5f2`).
 */
import React from 'react';
import {
  MousePointer2, Ruler, Crosshair, Zap, Pencil,
  Undo2, Redo2, Save, RotateCcw, FileSpreadsheet, CheckSquare,
  Minus, Plus, Sparkles, Scale,
} from 'lucide-react';
import { TOOLS } from './AnnotationCanvas';

const TOOL_BUTTONS = [
  { tool: TOOLS.NONE,         label: 'Pasirinkti',      Icon: MousePointer2, hotkey: 'V' },
  { tool: TOOLS.MEASURE,      label: 'Matuoti',         Icon: Ruler,         hotkey: 'M' },
  { tool: TOOLS.CALIBRATE,    label: 'Kalibruoti',      Icon: Crosshair,     hotkey: 'C' },
  { tool: TOOLS.PLACE_SYMBOL, label: 'Simboliai',       Icon: Zap,           hotkey: 'Y' },
  { tool: TOOLS.EDIT_WALL,    label: 'Redaguoti sieną', Icon: Pencil,        hotkey: 'E' },
];

// Tailwind class for any toolbar button. The Icon is always rendered;
// the text label appears at sm+ so the visible button is "[icon] Matuoti"
// — preserves Playwright's getByRole({name:/Matuoti/}) and works in
// narrow viewports too via aria-label.
function btnClass(active, disabled = false) {
  return [
    'flex items-center gap-1.5 rounded border px-2.5 py-1.5 text-sm transition-colors relative',
    active
      ? 'border-blue-600 bg-blue-50 text-blue-700 font-medium'
      : 'border-neutral-300 bg-white text-neutral-700 hover:bg-neutral-50',
    disabled ? 'cursor-not-allowed opacity-40 hover:bg-white' : 'cursor-pointer',
  ].join(' ');
}

export default function ViewerToolbar({
  tool,
  setTool,
  onUndo,
  onRedo,
  canUndo,
  canRedo,
  onSave,
  onLoad,
  onExport,
  onCalibrateModal,
  onDetectSymbols,
  detectingSymbols,
  onVerifyAll,
  walkthroughActive,
  saveStatus,
  scale,
  zoom,
  onZoom,
  pageNum,
  numPages,
  onPageChange,
  measurementsCount,
  symbolsCount,
}) {
  return (
    <div className="flex items-center gap-1 border-b border-neutral-200 bg-white px-3 py-2 shadow-sm">
      {/* Tool group */}
      <div className="flex items-center gap-1">
        {TOOL_BUTTONS.map(({ tool: t, label, Icon, hotkey }) => {
          const isActive = tool === t;
          return (
            <button
              key={t}
              type="button"
              onClick={() => setTool(t)}
              className={btnClass(isActive)}
              title={`${label} (${hotkey})`}
              aria-label={label}
              aria-pressed={isActive}
            >
              <Icon size={16} strokeWidth={1.75} aria-hidden="true" />
              <span className="hidden sm:inline">{label}</span>
              {isActive && (
                <span
                  aria-hidden="true"
                  className="absolute -bottom-px left-1/2 h-0.5 w-4 -translate-x-1/2 rounded-full bg-blue-600"
                />
              )}
            </button>
          );
        })}
      </div>

      <div className="mx-3 h-6 w-px bg-neutral-200" />

      {/* Undo/Redo */}
      <div className="flex items-center gap-1">
        <button
          type="button"
          onClick={onUndo}
          disabled={!canUndo}
          className={btnClass(false, !canUndo)}
          title="Atšaukti (Ctrl+Z)"
          aria-label="Atšaukti"
        >
          <Undo2 size={16} strokeWidth={1.75} aria-hidden="true" />
          <span className="hidden sm:inline">Atšaukti</span>
        </button>
        <button
          type="button"
          onClick={onRedo}
          disabled={!canRedo}
          className={btnClass(false, !canRedo)}
          title="Pakartoti (Ctrl+Y)"
          aria-label="Pakartoti"
        >
          <Redo2 size={16} strokeWidth={1.75} aria-hidden="true" />
          <span className="hidden sm:inline">Pakartoti</span>
        </button>
      </div>

      <div className="mx-3 h-6 w-px bg-neutral-200" />

      {/* Zoom controls */}
      <div className="flex items-center gap-1">
        <button
          type="button" onClick={() => onZoom && onZoom('out')}
          className={btnClass(false)} title="Mažinti" aria-label="Mažinti">
          <Minus size={14} strokeWidth={2} aria-hidden="true" />
        </button>
        <span className="font-mono text-xs text-neutral-600 px-1 min-w-[3em] text-center">
          {zoom ? `${Math.round(zoom * 100)}%` : '100%'}
        </span>
        <button
          type="button" onClick={() => onZoom && onZoom('in')}
          className={btnClass(false)} title="Didinti" aria-label="Didinti">
          <Plus size={14} strokeWidth={2} aria-hidden="true" />
        </button>
        <button
          type="button" onClick={() => onZoom && onZoom('reset')}
          className={btnClass(false)} title="Atstatyti mastelį (100%)" aria-label="Atstatyti mastelį">
          <span className="font-mono text-xs">1:1</span>
        </button>
      </div>

      <div className="mx-3 h-6 w-px bg-neutral-200" />

      {/* Save / Load / Export / Verify */}
      <div className="flex items-center gap-1">
        {onDetectSymbols && (
          <button
            type="button" onClick={onDetectSymbols} disabled={detectingSymbols}
            className={btnClass(false, detectingSymbols)}
            title="Aptikti simbolius brėžinyje"
            aria-label={detectingSymbols ? 'Aptinkama' : 'Aptikti simbolius'}>
            <Sparkles size={16} strokeWidth={1.75} aria-hidden="true" />
            <span className="hidden lg:inline">{detectingSymbols ? 'Aptinkama…' : 'Aptikti'}</span>
          </button>
        )}
        {onCalibrateModal && (
          <button
            type="button" onClick={onCalibrateModal}
            className={btnClass(false)}
            title="Kalibruoti pagal mano sumas"
            aria-label="Kalibruoti pagal mano sumas">
            <Scale size={16} strokeWidth={1.75} aria-hidden="true" />
            <span className="hidden lg:inline">Kalibruoti</span>
          </button>
        )}
        <button
          type="button" onClick={onSave}
          className={btnClass(false)}
          title="Išsaugoti anotacijas (Ctrl+S)"
          aria-label="Saugoti">
          <Save size={16} strokeWidth={1.75} aria-hidden="true" />
          <span className="hidden sm:inline">Saugoti</span>
        </button>
        {onLoad && (
          <button
            type="button" onClick={onLoad}
            className={btnClass(false)}
            title="Atkurti išsaugotas anotacijas"
            aria-label="Atkurti">
            <RotateCcw size={16} strokeWidth={1.75} aria-hidden="true" />
            <span className="hidden lg:inline">Atkurti</span>
          </button>
        )}
        {onExport && (
          <button
            type="button" onClick={onExport}
            className={btnClass(false)}
            title="Eksportuoti į Excel"
            aria-label="Excel">
            <FileSpreadsheet size={16} strokeWidth={1.75} aria-hidden="true" />
            <span className="hidden sm:inline">Excel</span>
          </button>
        )}
        <button
          type="button" onClick={onVerifyAll}
          className={btnClass(walkthroughActive)}
          title="Tikrinti visus kambarius paeiliui"
          aria-label="Tikrinti">
          <CheckSquare size={16} strokeWidth={1.75} aria-hidden="true" />
          <span className="hidden sm:inline">Tikrinti</span>
        </button>
      </div>

      <div className="flex-1" />

      {/* Status info */}
      <div className="flex items-center gap-3 text-xs text-neutral-500">
        <span title="Aktyvus mastelis">
          Mastelis: <strong className="font-mono">{scale ? `${scale.toFixed(2)} mm/px` : 'nekalibruota'}</strong>
        </span>
        {typeof measurementsCount === 'number' && (
          <span>Matavimai: <strong>{measurementsCount}</strong></span>
        )}
        {typeof symbolsCount === 'number' && (
          <span>Simboliai: <strong>{symbolsCount}</strong></span>
        )}
        {saveStatus === 'saved' && (
          <span className="rounded bg-emerald-50 px-2 py-0.5 text-emerald-700">✓ Išsaugota</span>
        )}
        {saveStatus === 'saving' && (
          <span className="text-neutral-500">Saugoma…</span>
        )}
        {numPages > 1 && onPageChange && (
          <div className="flex items-center gap-1">
            <button type="button" onClick={() => onPageChange(Math.max(1, pageNum - 1))}
              disabled={pageNum <= 1}
              className="rounded border border-neutral-300 px-2 py-0.5 disabled:opacity-30">‹</button>
            <span className="font-mono">{pageNum}/{numPages}</span>
            <button type="button" onClick={() => onPageChange(Math.min(numPages, pageNum + 1))}
              disabled={pageNum >= numPages}
              className="rounded border border-neutral-300 px-2 py-0.5 disabled:opacity-30">›</button>
          </div>
        )}
      </div>
    </div>
  );
}
