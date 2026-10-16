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
 */
import { useEffect, useState } from 'react';
import { Pencil, Shapes, Trash2, ListTree } from 'lucide-react';
import {
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel,
  DropdownMenuSeparator, DropdownMenuSub, DropdownMenuSubTrigger, DropdownMenuSubContent,
  DropdownMenuRadioGroup, DropdownMenuRadioItem,
} from '@/components/ui/dropdown-menu';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog';

const KIND_LT = { distance: 'Atstumas', perimeter: 'Perimetras', area: 'Plotas', count: 'Žymė' };

export default function MeasureContextMenu({ target, measurement, countTypes = [], onClose, onRename, onChangeType, onDelete, onReveal }) {
  const [renaming, setRenaming] = useState(null);       // { id, value } while the rename dialog is open
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
          <DropdownMenuLabel className="text-[11px] font-normal text-muted-foreground truncate">{heading}</DropdownMenuLabel>
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
          {onReveal && (
            <DropdownMenuItem onSelect={() => { onReveal(measurement); onClose?.(); }}>
              <ListTree className="w-3.5 h-3.5 mr-2" />Rodyti sąraše
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

function RenameDialog({ state, onCancel, onSave }) {
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
