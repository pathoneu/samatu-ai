/**
 * SymbolCounter — Togal-style „spauskite ant simbolio → suskaičiuokite visus".
 *
 * Vartotojo flow:
 *   1. Spauskite mygtuką „🎯 Skaičiuoti panašius"
 *   2. Cursor pasikeičia į kryžių, fonas pažymimas
 *   3. Spauskite ant simbolio brėžinyje (rozetė, langas, durys ir t.t.)
 *   4. Backend kvietimas /v9/symbols/count-by-template
 *   5. Rezultatai grąžinami kaip raudoni dot'ai overlay'iuje
 *   6. Vartotojas mato „Rasta 32 panašūs simboliai" su confidence breakdown
 */

import { useState, useRef, useCallback } from 'react';
import {
  Target, X, Loader2, Check,
  Plug, ToggleLeft, Lightbulb, Wind, Toilet, DoorOpen, Square, MousePointer2,
} from 'lucide-react';
import { Stage, Layer, Circle, Text as KonvaText, Group, Rect } from 'react-konva';

const PRESET_TYPES = [
  { id: 'rozetes',     label: 'Rozetė',         Icon: Plug },
  { id: 'jungikliai',  label: 'Jungiklis',      Icon: ToggleLeft },
  { id: 'sviestuvai',  label: 'Šviestuvas',     Icon: Lightbulb },
  { id: 'difuzoriai',  label: 'Difūzorius',     Icon: Wind },
  { id: 'klozetai',    label: 'Klozetas',       Icon: Toilet },
  { id: 'durys',       label: 'Durys',          Icon: DoorOpen },
  { id: 'langai',      label: 'Langas',         Icon: Square },
  { id: 'custom',      label: 'Pasirinkti spaudžiant', Icon: MousePointer2 },
];

/**
 * Naudojimo pavyzdys:
 *   <SymbolCounter pdfFile={blob} pageNr={1} imgWidth={W} imgHeight={H}
 *                  renderToolbar       // jei true — render TIK toolbar (viewport-fixed)
 *                  renderOverlay       // jei true — render TIK overlay'us (PDF coords)
 *                  state={state} onState={...} />
 *
 * Tipiniai du naudojimai:
 *   1. Toolbar viršuje (viewport-fixed): <SymbolCounter renderToolbar ...>
 *   2. Click+overlay ant PDF: <SymbolCounter renderOverlay ...>
 *   Abiems perduodam tą patį `state` ir `onState` (lifted state).
 */
export default function SymbolCounter({
  pdfFile,           // File ar Blob
  pageNr,            // 1-indexed
  imgWidth,          // PDF rendered image width (px)
  imgHeight,         // PDF rendered image height (px)
  onResultClick,     // callback when matches found
  // Lifted state (kad toolbar + overlay matytų tą patį)
  state = null,
  onState = null,
  // Render mode flags
  renderToolbar = false,
  renderOverlay = false,
}) {
  // Local fallback state jei nebuvo perduotas lifted
  const [localState, setLocalState] = useState({
    active: false, loading: false, matches: null,
    error: null, selectedType: null, lastClick: null,
  });
  const s = state || localState;
  const setS = (updater) => {
    if (onState) {
      onState(typeof updater === 'function' ? updater(s) : updater);
    } else {
      setLocalState(prev => typeof updater === 'function' ? updater(prev) : updater);
    }
  };

  const active = s.active;
  const loading = s.loading;
  const matches = s.matches;
  const error = s.error;
  const selectedType = s.selectedType;
  const lastClick = s.lastClick;

  const setActive = (v) => setS(p => ({ ...p, active: v }));
  const setLoading = (v) => setS(p => ({ ...p, loading: v }));
  const setMatches = (v) => setS(p => ({ ...p, matches: v }));
  const setError = (v) => setS(p => ({ ...p, error: v }));
  const setSelectedType = (v) => setS(p => ({ ...p, selectedType: v }));
  const setLastClick = (v) => setS(p => ({ ...p, lastClick: v }));

  const reset = () => {
    setS({ active: false, loading: false, matches: null,
           error: null, selectedType: null, lastClick: null });
  };

  // Vartotojas paspauskite ant simbolio (template pick)
  const handleStageClick = useCallback(async (e) => {
    if (!active || loading) return;
    const stage = e.target.getStage();
    const pos = stage.getPointerPosition();
    if (!pos) return;
    const x_pct = pos.x / imgWidth;
    const y_pct = pos.y / imgHeight;
    setLastClick({ x_pct, y_pct });
    setLoading(true);
    setError(null);

    try {
      const fd = new FormData();
      fd.append('files', pdfFile);
      fd.append('template_x_pct', x_pct.toString());
      fd.append('template_y_pct', y_pct.toString());
      fd.append('template_size_pct', '0.05');
      fd.append('page_nr', pageNr.toString());

      let endpoint, body;
      if (selectedType && selectedType !== 'custom') {
        // Greitas tipas — naudojam type-aware detect endpoint
        const fd2 = new FormData();
        fd2.append('files', pdfFile);
        fd2.append('symbol_type', selectedType);
        fd2.append('page_nr', pageNr.toString());
        endpoint = '/v9/symbols/detect';
        body = fd2;
      } else {
        // Click-to-count (template)
        endpoint = '/v9/symbols/count-by-template';
        body = fd;
      }

      const r = await fetch(endpoint, { method: 'POST', body });
      const j = await r.json();

      if (j.status === 'error' || j.error) {
        throw new Error(j.error || 'Detekcija nepavyko');
      }

      const matchesArr = j.matches || j.symbols || [];
      setMatches({
        count: j.count || matchesArr.length,
        matches: matchesArr,
      });
      setActive(false);
    } catch (e) {
      setError(e.message || String(e));
      setActive(false);
    } finally {
      setLoading(false);
    }
  }, [active, loading, pdfFile, pageNr, imgWidth, imgHeight, selectedType]);

  // Default: render BOTH (backwards compat). Jei renderToolbar/Overlay nustatyta —
  // grąžinam tik tą dalį.
  const showToolbar = !renderOverlay;  // jei tik overlay — toolbar OFF
  const showOverlay = !renderToolbar;  // jei tik toolbar — overlay OFF

  return (
    <>
      {/* Toolbar — viewport-fixed pozicijoje (skirtumas: pos absolute viduj parent'o,
          kuris turi turėti `position: relative`) */}
      {showToolbar && (
      <div className="absolute top-2 right-2 z-30 flex flex-col gap-2 max-w-xs">
        {!active && !matches && !loading && (
          <div className="bg-card/95 backdrop-blur border border-border rounded-lg shadow-lg p-3 space-y-2">
            <div className="flex items-center gap-1.5 text-[11px] uppercase tracking-wider text-muted-foreground font-semibold">
              <Target className="w-3 h-3" />
              <span>Skaičiuoti simbolius</span>
            </div>
            <div className="grid grid-cols-2 gap-1">
              {PRESET_TYPES.map(t => {
                const I = t.Icon;
                return (
                  <button
                    key={t.id}
                    onClick={() => { setSelectedType(t.id); setActive(true); }}
                    className="flex items-center gap-2 px-2.5 py-2 text-xs text-left hover:bg-muted rounded text-foreground border border-border/50 hover:border-foreground/40 transition-colors"
                    title={t.id === 'custom'
                      ? 'Spausk ant simbolio brėžinyje, AI ras visus panašius'
                      : `AI ras visus ${t.label.toLowerCase()} brėžinyje`}
                  >
                    <I className="w-3.5 h-3.5 shrink-0 text-muted-foreground" />
                    <span className="truncate">{t.label}</span>
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {active && !loading && (
          <div className="bg-amber-100 dark:bg-amber-900/40 border border-amber-400 rounded-lg shadow-lg p-3 max-w-xs">
            <div className="flex items-center gap-2 mb-1.5">
              <Target className="w-4 h-4 text-amber-700" />
              <strong className="text-sm text-amber-900 dark:text-amber-100">
                {selectedType === 'custom' ? 'Spausk ant simbolio' : `Spausk ant ${PRESET_TYPES.find(t=>t.id===selectedType)?.label?.toLowerCase()}`}
              </strong>
            </div>
            <div className="text-xs text-amber-800 dark:text-amber-200 mb-2">
              {selectedType === 'custom'
                ? 'AI ras visus panašius simbolius brėžinyje pagal pasirinktą šabloną.'
                : 'AI ras visus šio tipo simbolius visame brėžinyje.'}
            </div>
            <button onClick={reset}
              className="text-xs underline text-amber-900 dark:text-amber-100">
              Atšaukti
            </button>
          </div>
        )}

        {loading && (
          <div className="bg-card border border-border rounded-lg shadow-lg p-3 flex items-center gap-2">
            <Loader2 className="w-4 h-4 animate-spin text-foreground" />
            <span className="text-sm">AI skaičiuoja simbolius...</span>
          </div>
        )}

        {matches && (
          <div className="bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-300 dark:border-emerald-800 rounded-lg shadow-lg p-3 max-w-xs">
            <div className="flex items-center justify-between gap-2 mb-1.5">
              <div className="flex items-center gap-1.5">
                <Check className="w-4 h-4 text-emerald-700 dark:text-emerald-300" />
                <strong className="text-sm text-emerald-900 dark:text-emerald-100">
                  Rasta: {matches.count}
                </strong>
              </div>
              <button onClick={reset}
                className="p-1 hover:bg-emerald-100 dark:hover:bg-emerald-900/50 rounded text-emerald-700 dark:text-emerald-300">
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
            <div className="text-xs text-emerald-800 dark:text-emerald-200 mb-2 flex flex-wrap items-center gap-x-3 gap-y-1">
              {(() => {
                const high = matches.matches.filter(m => m.confidence === 'high').length;
                const med = matches.matches.filter(m => m.confidence === 'medium').length;
                const low = matches.matches.filter(m => m.confidence === 'low').length;
                return (
                  <>
                    <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />{high} aiškūs</span>
                    <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-amber-500" />{med} galimi</span>
                    <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-red-500" />{low} neaiškūs</span>
                  </>
                );
              })()}
            </div>
            <div className="text-xs text-muted-foreground">
              Raudoni dot'ai brėžinyje pažymi rastas vietas.
            </div>
            {onResultClick && (
              <button
                onClick={() => onResultClick(selectedType, matches)}
                className="mt-2 w-full px-2 py-1 text-xs bg-emerald-700 dark:bg-emerald-600 text-white rounded hover:bg-emerald-800 dark:hover:bg-emerald-500"
              >
                Įtraukti į pasiūlymą
              </button>
            )}
          </div>
        )}

        {error && (
          <div className="bg-red-50 dark:bg-red-950/30 border border-red-300 rounded-lg shadow-lg p-3 max-w-xs">
            <div className="text-xs text-red-700 dark:text-red-200 mb-1.5">
              <strong>Klaida:</strong> {error}
            </div>
            <button onClick={reset}
              className="text-xs underline text-red-700 dark:text-red-300">
              Bandyti dar kartą
            </button>
          </div>
        )}
      </div>
      )}

      {/* Click target overlay (only when armed) */}
      {showOverlay && active && !loading && imgWidth > 0 && (
        <Stage
          width={imgWidth}
          height={imgHeight}
          onClick={handleStageClick}
          onTap={handleStageClick}
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            cursor: 'crosshair',
            zIndex: 25,
          }}
        >
          <Layer>
            {/* Semi-transparent dim, kad būtų aišku jog mode aktyvus */}
            <Rect
              x={0} y={0} width={imgWidth} height={imgHeight}
              fill="rgba(245, 158, 11, 0.08)"
            />
          </Layer>
        </Stage>
      )}

      {/* Match results overlay (raudoni dot'ai) */}
      {showOverlay && matches && imgWidth > 0 && (
        <Stage
          width={imgWidth}
          height={imgHeight}
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            pointerEvents: 'none',
            zIndex: 26,
          }}
        >
          <Layer>
            {matches.matches.map((m, i) => {
              const x = m.x_pct * imgWidth;
              const y = m.y_pct * imgHeight;
              const color = m.confidence === 'high' ? '#10b981'
                          : m.confidence === 'medium' ? '#f59e0b' : '#ef4444';
              return (
                <Group key={i}>
                  <Circle
                    x={x} y={y} radius={10}
                    stroke={color}
                    strokeWidth={2}
                    fill={`${color}33`}
                  />
                  <KonvaText
                    x={x - 6} y={y - 5}
                    text={String(i + 1)}
                    fontSize={9}
                    fontStyle="bold"
                    fill={color}
                    width={12}
                    align="center"
                  />
                </Group>
              );
            })}
            {/* Last-click marker (vartotojo pasirinktas šablonas) */}
            {lastClick && (
              <Circle
                x={lastClick.x_pct * imgWidth}
                y={lastClick.y_pct * imgHeight}
                radius={14}
                stroke="#3b82f6"
                strokeWidth={2}
                dash={[4, 4]}
              />
            )}
          </Layer>
        </Stage>
      )}
    </>
  );
}
