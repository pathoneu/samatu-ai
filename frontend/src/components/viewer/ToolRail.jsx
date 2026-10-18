/**
 * ToolRail — the viewer's tools as floating cards on the drawing's left (Pathon v3 click model, W1-B B1;
 * design 2026-10-18 §5–§6). It replaces the horizontal toolbar whose far half was hidden behind a sideways
 * scroll at 1440 and 1280 px (audit §4.1).
 *
 * Two cards: the tools (Naršyti · Matuoti · Skaityti brėžinį, one mode at a time) and the layers plus
 * „Daugiau". Every tile has an icon AND a short Lithuanian word under it; the tooltip adds the key and one
 * sentence (lib/toolRail, keys from lib/viewerShortcuts). When the canvas is too short for the labelled
 * tiles, `compact` keeps the icons only — the rail never scrolls and never runs off the canvas.
 *
 * What a tile does is the viewer's business: `onTool(id)` arms or disarms, `onToggleLayer(id)` flips a
 * layer, `more` lists the menu's items. A tool whose handler the viewer has not given (`available[id]`
 * false) is drawn disabled with the reason in its tooltip — never silently missing.
 */
import {
  MousePointer2, Lasso, Hand, Ruler, Pentagon, Spline, Hash, SquareDashedMousePointer, ScanSearch, Scaling,
  Layers, BrickWall, MoreHorizontal,
} from 'lucide-react';
import { Tooltip, TooltipTrigger, TooltipContent } from '@/components/ui/tooltip';
import {
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem, DropdownMenuCheckboxItem,
  DropdownMenuSeparator, DropdownMenuShortcut,
} from '@/components/ui/dropdown-menu';
import { RAIL_GROUPS, railKey, railTool } from '@/lib/toolRail';

const ICONS = {
  select: MousePointer2,
  lasso: Lasso,
  pan: Hand,
  distance: Ruler,
  area: Pentagon,
  perimeter: Spline,
  count: Hash,
  room: SquareDashedMousePointer,
  findSimilar: ScanSearch,
  calibrate: Scaling,
  zones: Layers,
  walls: BrickWall,
};

// Test ids the smoke suite and the coach marks already know (kept from the old toolbar).
const TEST_IDS = { findSimilar: 'viewer-symbol-search', walls: 'viewer-walls-layer' };

// Tile and card geometry — RAIL_HEIGHT is what the labelled rail needs; below it the rail goes compact.
export const RAIL_WIDTH = 72;            // card (64 px tiles + padding + border)
const TILE_H = 34;
const COMPACT_TILE_H = 28;
const SEPARATOR_H = 7;
const CARD_CHROME_H = 10;                // padding + border per card
const CARD_GAP = 8;
export function railHeight({ compact = false } = {}) {
  const tiles = RAIL_GROUPS.reduce((n, g) => n + g.tools.length, 0) + 1;   // + „Daugiau"
  const separators = RAIL_GROUPS.length - 2 + 1;                          // between cards' groups
  return tiles * (compact ? COMPACT_TILE_H : TILE_H) + separators * SEPARATOR_H + 2 * CARD_CHROME_H + CARD_GAP;
}

function Tile({ id, pressed = false, disabled = false, disabledReason = null, compact, onClick, mac, extra = {} }) {
  const tool = railTool(id);
  const Icon = ICONS[id] || MoreHorizontal;
  const key = railKey(id, { mac });
  const keyAll = railKey(id, { mac, all: true });
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          aria-label={tool.name}
          aria-pressed={pressed}
          aria-keyshortcuts={key || undefined}
          aria-disabled={disabled || undefined}
          disabled={disabled}
          onClick={onClick}
          data-coach={id}
          data-tool={id}
          data-testid={TEST_IDS[id] || `tool-${id}`}
          className={`w-16 ${compact ? 'h-7' : 'h-[34px]'} shrink-0 rounded flex flex-col items-center justify-center gap-px px-0.5 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${pressed
            ? 'bg-viewer-chrome-active/15 text-viewer-chrome-active'
            : 'text-viewer-chrome-foreground hover:bg-viewer-chrome-hover'} disabled:opacity-40 disabled:hover:bg-transparent`}
          {...extra}
        >
          <Icon className="w-4 h-4 shrink-0" aria-hidden="true" />
          {!compact && <span className="text-meta leading-[14px] max-w-full truncate">{tool.label}</span>}
        </button>
      </TooltipTrigger>
      <TooltipContent side="right" sideOffset={10} className="max-w-[300px] rounded px-3 py-2 text-ui leading-snug">
        <span className="font-semibold">{tool.name}</span>
        {keyAll && <kbd className="mono ml-2 px-1 rounded border border-primary-foreground/30 text-meta">{keyAll}</kbd>}
        <span className="block mt-0.5 text-primary-foreground/85">{disabled && disabledReason ? disabledReason : tool.sentence}</span>
      </TooltipContent>
    </Tooltip>
  );
}

const Separator = () => <span aria-hidden="true" className="block h-px bg-border mx-1.5 my-[3px]" />;

/**
 * activeTool — the armed mode's rail id, or null at rest.
 * available  — { [toolId]: false | string } — false/a reason string draws the tile disabled.
 * layers     — { zones, walls } booleans; onToggleLayer(id) or null (no layers card).
 * more       — [{ id, label, Icon, onSelect, checked?, shortcut?, testId?, disabled? } | 'separator'].
 */
export default function ToolRail({
  activeTool = null, onTool, available = {}, layers = null, onToggleLayer = null, more = [], compact = false, mac = false,
}) {
  const toolGroups = RAIL_GROUPS.filter((g) => !g.toggles);
  const layerGroup = RAIL_GROUPS.find((g) => g.toggles);
  const card = 'pointer-events-auto bg-card border border-border rounded-panel shadow-md p-1 flex flex-col items-center';
  return (
    <div className="flex flex-col gap-2" data-tool-rail role="toolbar" aria-orientation="vertical" aria-label="Brėžinio įrankiai">
      <div className={card}>
        {toolGroups.map((g, gi) => (
          <div key={g.id} role="group" aria-label={g.title} className="flex flex-col items-center">
            {gi > 0 && <Separator />}
            {g.tools.map((t) => {
              const reason = available[t.id];
              const off = reason === false || typeof reason === 'string';
              return (
                <Tile
                  key={t.id}
                  id={t.id}
                  compact={compact}
                  mac={mac}
                  pressed={activeTool === t.id}
                  disabled={off}
                  disabledReason={typeof reason === 'string' ? reason : null}
                  onClick={() => onTool?.(t.id)}
                />
              );
            })}
          </div>
        ))}
      </div>
      <div className={card}>
        {layers && onToggleLayer && layerGroup && (
          <div role="group" aria-label={layerGroup.title} className="flex flex-col items-center">
            {layerGroup.tools.map((t) => (
              <Tile key={t.id} id={t.id} compact={compact} mac={mac} pressed={!!layers[t.id]} onClick={() => onToggleLayer(t.id)} />
            ))}
            <Separator />
          </div>
        )}
        <DropdownMenu modal={false}>
          <Tooltip>
            <TooltipTrigger asChild>
              <DropdownMenuTrigger asChild>
                <button
                  type="button"
                  aria-label="Daugiau"
                  data-testid="viewer-more"
                  className={`w-16 ${compact ? 'h-7' : 'h-[34px]'} shrink-0 rounded flex flex-col items-center justify-center gap-px text-viewer-chrome-foreground hover:bg-viewer-chrome-hover data-[state=open]:bg-viewer-chrome-active/15 data-[state=open]:text-viewer-chrome-active focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring`}
                >
                  <MoreHorizontal className="w-4 h-4" aria-hidden="true" />
                  {!compact && <span className="text-meta leading-[14px]">Daugiau</span>}
                </button>
              </DropdownMenuTrigger>
            </TooltipTrigger>
            <TooltipContent side="right" sideOffset={10} className="max-w-[300px] rounded px-3 py-2 text-ui leading-snug">
              Masteliai, istorija, spausdinimas, atsisiuntimas, klavišai
            </TooltipContent>
          </Tooltip>
          <DropdownMenuContent side="right" align="end" sideOffset={10} className="w-80 rounded-panel" data-testid="viewer-more-menu">
            {more.map((item, i) => {
              if (item === 'separator') return <DropdownMenuSeparator key={`sep-${i}`} />;
              const { id, label, Icon, onSelect, checked, shortcut, testId, disabled } = item;
              const body = (
                <>
                  {Icon && <Icon aria-hidden="true" />}
                  <span className="flex-1 text-ui">{label}</span>
                  {shortcut && <DropdownMenuShortcut className="mono text-meta">{shortcut}</DropdownMenuShortcut>}
                </>
              );
              return checked == null ? (
                <DropdownMenuItem key={id} inset onSelect={onSelect} data-testid={testId} disabled={disabled}>{body}</DropdownMenuItem>
              ) : (
                <DropdownMenuCheckboxItem key={id} checked={checked} onCheckedChange={() => onSelect?.()} data-testid={testId} disabled={disabled} className="gap-2">
                  {body}
                </DropdownMenuCheckboxItem>
              );
            })}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </div>
  );
}
