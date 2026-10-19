/**
 * MeasureContextMenu — right-click on a committed measurement or count mark
 * (2026-10-16, Togal analysis §6): „Pervadinti", „Keisti tipą" (count marks),
 * „Ištrinti", „Rodyti sąraše". Every change goes through the viewer's history,
 * so Ctrl+Z takes it back.
 *
 * Built on the shadcn DropdownMenu opened at the pointer rather than the
 * ContextMenu primitive: ContextMenu opens on ANY right-click inside its
 * trigger, while this menu must open only when the click hits a mark (a miss
 * keeps the browser's own menu) — PageOverlayHost hit-tests and hands us the spot.
 *
 * Batch mode (2026-10-16, „Laso"): when the click lands inside a multi-mark selection, the menu acts
 * on all of it — „Keisti žymių tipą" (count marks), „Spalva" (measurements), „Atžymėti", „Ištrinti
 * visus". One history entry per action.
 */
import { useEffect, useState } from 'react';
import { Pencil, Shapes, Trash2, ListTree, Palette, Rows3, SquareDashedMousePointer, ScanSearch } from 'lucide-react';
import {
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel,
  DropdownMenuSeparator, DropdownMenuSub, DropdownMenuSubTrigger, DropdownMenuSubContent,
  DropdownMenuRadioGroup, DropdownMenuRadioItem,
} from '@/components/ui/dropdown-menu';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog';

const KIND_LT = { distance: 'Atstumas', perimeter: 'Perimetras', area: 'Plotas', count: 'Žymė' };
// The colours a measurement can take in a batch (the count-type palette of lib/measurements). No red: on the
// drawing red means an error and nothing else (v3 overlay vocabulary) — a measurement already stored red keeps
// its colour (it is his data), it just cannot be chosen any more.
const COLOURS = [
  { id: '#2a6fb5', label: 'Mėlyna' }, { id: '#2f6b4f', label: 'Žalia' }, { id: '#d97706', label: 'Oranžinė' },
  { id: '#0d9488', label: 'Žalsvai mėlyna' }, { id: '#7c3aed', label: 'Violetinė' }, { id: '#475569', label: 'Pilka' },
];

// „3 matavimai", „5 žymės" — Lithuanian count agreement for the two nouns the menu names.
function ltMany(n, [one, few, many]) {
  const t = n % 10;
  const h = n % 100;
  if (t === 1 && h !== 11) return `${n} ${one}`;
  if (t >= 2 && t <= 9 && (h < 12 || h > 19)) return `${n} ${few}`;
  return `${n} ${many}`;
}
const MEASURES = ['matavimas', 'matavimai', 'matavimų'];
const MARKS = ['žymė', 'žymės', 'žymių'];

export default function MeasureContextMenu({
  target, measurement, selection = null, countTypes = [], onClose, onRename, onChangeType, onDelete, onReveal,
  onDeleteMany, onChangeTypeMany, onRecolorMany, onDeselect,
  // „Rasti panašius" from a count mark (W5-A A8): (mark) => void.
  onFindSimilar = null,
}) {
  const [renaming, setRenaming] = useState(null);       // { id, value } while the rename dialog is open
  if (target && Array.isArray(selection) && selection.length > 1) {
    return <BatchMenu target={target} selection={selection} countTypes={countTypes} onClose={onClose}
      onDeleteMany={onDeleteMany} onChangeTypeMany={onChangeTypeMany} onRecolorMany={onRecolorMany} onDeselect={onDeselect} />;
  }
  const open = !!(target && measurement);
  const typeLabel = measurement?.kind === 'count'
    ? (countTypes.find((t) => t.id === measurement.typeId)?.label || measurement.typeId)
    : null;
  const heading = [KIND_LT[measurement?.kind] || 'Matavimas', typeLabel, measurement?.name ? `„${measurement.name}"` : null]
    .filter(Boolean).join(' · ');

  return (
    <>
      <DropdownMenu open={open} onOpenChange={(v) => { if (!v) onClose?.(); }} modal={false}>
        <DropdownMenuTrigger asChild>
          <span
            aria-hidden
            style={{ position: 'fixed', left: target?.clientX ?? -9999, top: target?.clientY ?? -9999, width: 1, height: 1, pointerEvents: 'none' }}
          />
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" sideOffset={2} className="w-56" data-testid="measure-context-menu" onCloseAutoFocus={(e) => e.preventDefault()}>
          <DropdownMenuLabel className="text-meta font-normal text-muted-foreground truncate">{heading}</DropdownMenuLabel>
          <DropdownMenuSeparator />
          <DropdownMenuItem onSelect={() => { setRenaming({ id: measurement.id, value: measurement.name || '' }); onClose?.(); }}>
            <Pencil className="w-3.5 h-3.5 mr-2" />Pervadinti
          </DropdownMenuItem>
          {measurement?.kind === 'count' && countTypes.length > 1 && (
            <DropdownMenuSub>
              <DropdownMenuSubTrigger><Shapes className="w-3.5 h-3.5 mr-2" />Keisti tipą</DropdownMenuSubTrigger>
              <DropdownMenuSubContent className="w-52">
                <DropdownMenuRadioGroup
                  value={measurement.typeId}
                  onValueChange={(v) => { if (v !== measurement.typeId) onChangeType?.(measurement.id, v); onClose?.(); }}
                >
                  {countTypes.map((t) => (
                    <DropdownMenuRadioItem key={t.id} value={t.id}>
                      <span className="inline-block w-2 h-2 rounded-full mr-2" style={{ background: t.color }} />
                      {t.label}
                    </DropdownMenuRadioItem>
                  ))}
                </DropdownMenuRadioGroup>
              </DropdownMenuSubContent>
            </DropdownMenuSub>
          )}
          {onFindSimilar && measurement?.kind === 'count' && (
            <DropdownMenuItem onSelect={() => { onFindSimilar(measurement); onClose?.(); }} data-testid="measure-menu-find-similar">
              <ScanSearch className="w-3.5 h-3.5 mr-2" />Rasti panašius
            </DropdownMenuItem>
          )}
          {onReveal && (
            <DropdownMenuItem onSelect={() => { onReveal(measurement); onClose?.(); }}>
              <ListTree className="w-3.5 h-3.5 mr-2" />Rodyti sąraše
            </DropdownMenuItem>
          )}
          {/* Pathon v3 W4-A: the measurement (a count mark: its whole type) onto a sąmata row — the panel's
              „Į eilutę…" picker (WorkspacePanel listens). Shown where „Rodyti sąraše" is: the main viewer. */}
          {onReveal && measurement && ['distance', 'perimeter', 'area', 'count'].includes(measurement.kind) && (
            <DropdownMenuItem
              onSelect={() => {
                const key = measurement.kind === 'count' ? `type:${measurement.typeId}` : `m:${measurement.id}`;
                window.dispatchEvent(new CustomEvent('samatu:measure-to-row', { detail: { key } }));
                onClose?.();
              }}
              data-testid="measure-menu-to-row"
            >
              <Rows3 className="w-3.5 h-3.5 mr-2" />Į eilutę…
            </DropdownMenuItem>
          )}
          <DropdownMenuSeparator />
          <DropdownMenuItem
            className="text-destructive focus:text-destructive"
            onSelect={() => { onDelete?.(measurement.id); onClose?.(); }}
          >
            <Trash2 className="w-3.5 h-3.5 mr-2" />Ištrinti
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      <RenameDialog
        state={renaming}
        onCancel={() => setRenaming(null)}
        onSave={(name) => { onRename?.(renaming.id, name); setRenaming(null); }}
      />
    </>
  );
}

export function RenameDialog({ state, onCancel, onSave }) {
  const [value, setValue] = useState('');
  useEffect(() => { if (state) setValue(state.value); }, [state]);
  return (
    <Dialog open={!!state} onOpenChange={(v) => { if (!v) onCancel(); }}>
      <DialogContent className="sm:max-w-sm">
        <DialogHeader>
          <DialogTitle>Pervadinti matavimą</DialogTitle>
          <DialogDescription>Pavadinimas matysis sąraše „Matavimai" ir istorijoje. Tuščias — be pavadinimo.</DialogDescription>
        </DialogHeader>
        <form onSubmit={(e) => { e.preventDefault(); onSave(value.trim()); }}>
          <input
            autoFocus
            value={value}
            onChange={(e) => setValue(e.target.value)}
            maxLength={80}
            placeholder="pvz., Virtuvės siena"
            aria-label="Matavimo pavadinimas"
            className="w-full h-9 px-2.5 rounded-[2px] border border-input bg-background text-sm focus:outline-none focus:ring-1 focus:ring-ring"
          />
          <DialogFooter className="mt-4">
            <button type="button" onClick={onCancel} className="px-3 py-1.5 rounded-[2px] border border-border text-sm hover:bg-muted">Atšaukti</button>
            <button type="submit" className="px-3 py-1.5 rounded-[2px] bg-primary text-primary-foreground text-sm hover:bg-primary/90">Išsaugoti</button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function BatchMenu({ target, selection, countTypes, onClose, onDeleteMany, onChangeTypeMany, onRecolorMany, onDeselect }) {
  const ids = selection.map((m) => m.id);
  const marks = selection.filter((m) => m.kind === 'count');
  const lines = selection.filter((m) => m.kind !== 'count');
  const parts = [lines.length ? ltMany(lines.length, MEASURES) : null, marks.length ? ltMany(marks.length, MARKS) : null].filter(Boolean);
  return (
    <DropdownMenu open onOpenChange={(v) => { if (!v) onClose?.(); }} modal={false}>
      <DropdownMenuTrigger asChild>
        <span aria-hidden style={{ position: 'fixed', left: target.clientX, top: target.clientY, width: 1, height: 1, pointerEvents: 'none' }} />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" sideOffset={2} className="w-60" data-testid="measure-batch-menu" onCloseAutoFocus={(e) => e.preventDefault()}>
        <DropdownMenuLabel className="text-meta font-normal text-muted-foreground">Pažymėta: {parts.join(', ')}</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {marks.length > 0 && countTypes.length > 0 && (
          <DropdownMenuSub>
            <DropdownMenuSubTrigger><Shapes className="w-3.5 h-3.5 mr-2" />Keisti žymių tipą ({marks.length})</DropdownMenuSubTrigger>
            <DropdownMenuSubContent className="w-52">
              {countTypes.map((t) => (
                <DropdownMenuItem key={t.id} onSelect={() => { onChangeTypeMany?.(ids, t.id); onClose?.(); }}>
                  <span className="inline-block w-2 h-2 rounded-full mr-2" style={{ background: t.color }} />
                  {t.label}
                </DropdownMenuItem>
              ))}
            </DropdownMenuSubContent>
          </DropdownMenuSub>
        )}
        {lines.length > 0 && (
          <DropdownMenuSub>
            <DropdownMenuSubTrigger><Palette className="w-3.5 h-3.5 mr-2" />Spalva ({ltMany(lines.length, MEASURES)})</DropdownMenuSubTrigger>
            <DropdownMenuSubContent className="w-44">
              {COLOURS.map((c) => (
                <DropdownMenuItem key={c.id} onSelect={() => { onRecolorMany?.(ids, c.id); onClose?.(); }}>
                  <span className="inline-block w-2.5 h-2.5 rounded-sm mr-2" style={{ background: c.id }} />
                  {c.label}
                </DropdownMenuItem>
              ))}
            </DropdownMenuSubContent>
          </DropdownMenuSub>
        )}
        <DropdownMenuItem onSelect={() => { onDeselect?.(); onClose?.(); }}>
          <SquareDashedMousePointer className="w-3.5 h-3.5 mr-2" />Atžymėti
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem className="text-destructive focus:text-destructive" onSelect={() => { onDeleteMany?.(ids); onClose?.(); }}>
          <Trash2 className="w-3.5 h-3.5 mr-2" />Ištrinti visus ({selection.length})
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
