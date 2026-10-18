/**
 * SelectionBar — the floating action bar at the selection (Pathon v3 click model, W1-B B6; Kreo §11
 * fly-menu, design §5 „a floating action bar appears at the selection with icon AND Lithuanian text").
 *
 * A selected room: Taisyti kontūrą (E) · Padalyti · Sujungti (M) · Atimti (X) · Neskaičiuoti… · Įrodymai,
 * and „⋯" for „Kontūras paspaudus". Selected marks („Žymėti" / „Laso"): Pervadinti · Keisti
 * tipą · Rodyti sąraše · Ištrinti — several: Ištrinti visus · Atžymėti. Every action calls a handler the
 * viewer already had (the old toolbar's room buttons, the right-click menu's items); the bar only moves
 * them to where the eye is. Never hover-only: icon and word on every button, the key in its title.
 *
 * Placement (lib/selectionPlacement): right above the room's label or the mark, never on it; docked at
 * the top centre when the selection is off screen. `anchor` is the box from useChromeRects.
 */
import { useLayoutEffect, useRef, useState } from 'react';
import { Pentagon, Scissors, Combine, SquareDashed, CircleSlash, FileSearch, MoreHorizontal, SquarePen, Pencil, Shapes, ListTree, Trash2, X } from 'lucide-react';
import {
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem, DropdownMenuRadioGroup, DropdownMenuRadioItem,
} from '@/components/ui/dropdown-menu';
import { placeSelectionBar } from '@/lib/selectionPlacement';
import { keyText } from '@/lib/viewerShortcuts';

const btn = 'h-8 shrink-0 inline-flex items-center gap-1.5 px-2 rounded text-ui text-foreground whitespace-nowrap hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50';

function Action({ Icon, label, title, onClick, testId, coach, danger = false, disabled = false }) {
  return (
    <button
      type="button"
      className={`${btn} ${danger ? 'text-destructive hover:bg-destructive/10' : ''}`}
      title={title}
      onClick={onClick}
      disabled={disabled}
      data-testid={testId}
      data-coach={coach}
    >
      <Icon className="w-4 h-4 shrink-0" aria-hidden="true" />
      <span>{label}</span>
    </button>
  );
}

const withKeyTitle = (sentence, id) => {
  const k = keyText(id);
  return k ? `${sentence} (${k})` : sentence;
};

export default function SelectionBar({ frame, anchor, avoid = [], insetLeft = 8, room = null, marks = null }) {
  const ref = useRef(null);
  const [size, setSize] = useState({ width: 0, height: 40 });
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const w = el.offsetWidth; const h = el.offsetHeight;
    if (w !== size.width || h !== size.height) setSize({ width: w, height: h });
  });
  if (!frame || (!room && !marks)) return null;
  const pos = placeSelectionBar({
    anchor,
    frame,
    bar: { width: size.width || 480, height: size.height || 40 },
    inset: { left: insetLeft, top: 8, right: 8, bottom: 8 },
    avoid,
  });
  return (
    <div
      ref={ref}
      role="toolbar"
      aria-label={room ? `Patalpa ${room.nr}` : 'Pažymėti matavimai'}
      data-testid="selection-bar"
      data-kind={room ? 'room' : 'measure'}
      data-side={pos.side}
      className="absolute pointer-events-auto max-w-[calc(100%-1rem)] min-h-[40px] flex flex-wrap items-center gap-0.5 rounded-panel border border-border bg-card shadow-md px-1 py-1"
      style={{ left: pos.left, top: pos.top }}
    >
      {room ? <RoomActions room={room} /> : <MarkActions marks={marks} />}
    </div>
  );
}

function RoomActions({ room }) {
  const { nr, onEdit, onSplit, onMerge, onSubtract, onExclude, onEvidence, onFill } = room;
  return (
    <>
      <span className="px-2 text-ui font-semibold text-foreground whitespace-nowrap mono tabular" title={room.name || undefined}>{nr}</span>
      {onEdit && (
        <Action Icon={Pentagon} label="Taisyti kontūrą" testId="outline-edit-start" coach="outline-edit"
          title={withKeyTitle(`Taisyti patalpos ${nr} kontūrą viršūnėmis: tempkite kampą, spustelėkite vidurio tašką — pridėti, dukart spustelėkite kampą — pašalinti; prilimpa prie brėžinio sienų`, 'roomEditOutline')}
          onClick={onEdit} />
      )}
      {(onSplit || onMerge || onSubtract) && (
        <span className="inline-flex items-center gap-0.5" data-testid="outline-tool-buttons">
          {onSplit && (
            <Action Icon={Scissors} label="Padalyti" testId="outline-tool-split" onClick={onSplit}
              title={`Padalyti patalpos ${nr} kontūrą linija: dvi vietos linijai, tada spustelėkite dalį, kuri lieka; kitą dalį priskirkite kitai patalpai arba neįtraukite`} />
          )}
          {onMerge && (
            <Action Icon={Combine} label="Sujungti" testId="outline-tool-merge" onClick={onMerge}
              title={withKeyTitle(`Sujungti patalpą ${nr} su gretima: spustelėkite besiliečiantį kitos patalpos kontūrą šiame lape — abiejų plotai ir angos skaičiuojami vienoje patalpoje`, 'roomMerge')} />
          )}
          {onSubtract && (
            <Action Icon={SquareDashed} label="Atimti" testId="outline-tool-subtract" onClick={onSubtract}
              title={withKeyTitle(`Atimti iš patalpos ${nr} kontūro koloną, spintą ar šachtą: nubrėžkite stačiakampį arba daugiakampį jo viduje`, 'roomSubtract')} />
          )}
        </span>
      )}
      {onExclude && (
        <Action Icon={CircleSlash} label="Neskaičiuoti…" testId="selection-exclude" onClick={onExclude}
          title={`Atidaro patalpos ${nr} lapą Patikroje — ten pačiame viršuje „Ši patalpa: skaičiuoju / neskaičiuoju" ir kurių darbų joje neskaičiuoti`} />
      )}
      {onEvidence && (
        <Action Icon={FileSearch} label="Įrodymai" testId="selection-evidence" onClick={onEvidence}
          title={`Patalpos ${nr} lapas: kiekvienas skaičius su sakiniu, iš kur jis paimtas, ir brėžinio iškarpa`} />
      )}
      {onFill && (
        <DropdownMenu modal={false}>
          <DropdownMenuTrigger asChild>
            <button type="button" className={btn} aria-label="Daugiau veiksmų su patalpa" title="Daugiau veiksmų su patalpa" data-testid="selection-more">
              <MoreHorizontal className="w-4 h-4" aria-hidden="true" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-80 rounded-panel">
            <DropdownMenuItem onSelect={onFill} data-testid="selection-fill" className="text-ui">
              <SquarePen aria-hidden="true" />
              Kontūras paspaudus — spustelėti patalpos {nr} viduje
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      )}
    </>
  );
}

function MarkActions({ marks }) {
  const { count, kindLabel, countTypes = [], typeId = null, onRename, onChangeType, onReveal, onDelete, onDeselect } = marks;
  if (count > 1) {
    return (
      <>
        <span className="px-2 text-ui font-semibold text-foreground whitespace-nowrap">Pažymėta: {count}</span>
        <Action Icon={Trash2} label={`Ištrinti visus (${count})`} testId="selection-delete-all" danger onClick={onDelete}
          title={withKeyTitle('Ištrinti visus pažymėtus — atšaukiama istorijoje', 'deleteSelected')} />
        <Action Icon={X} label="Atžymėti" testId="selection-deselect" onClick={onDeselect} title="Nuimti pažymėjimą (Esc)" />
      </>
    );
  }
  return (
    <>
      {kindLabel && <span className="px-2 text-ui font-semibold text-foreground whitespace-nowrap">{kindLabel}</span>}
      {onRename && <Action Icon={Pencil} label="Pervadinti" testId="selection-rename" onClick={onRename} title={'Pavadinimas matysis sąraše „Matavimai" ir istorijoje'} />}
      {onChangeType && countTypes.length > 1 && (
        <DropdownMenu modal={false}>
          <DropdownMenuTrigger asChild>
            <button type="button" className={btn} data-testid="selection-type" title="Keisti žymės tipą">
              <Shapes className="w-4 h-4 shrink-0" aria-hidden="true" />
              <span>Keisti tipą</span>
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="w-56 rounded-panel">
            <DropdownMenuRadioGroup value={typeId} onValueChange={(v) => { if (v !== typeId) onChangeType(v); }}>
              {countTypes.map((t) => (
                <DropdownMenuRadioItem key={t.id} value={t.id} className="text-ui">
                  <span className="inline-block w-2.5 h-2.5 rounded-full mr-2" style={{ background: t.color }} aria-hidden="true" />
                  {t.label}
                </DropdownMenuRadioItem>
              ))}
            </DropdownMenuRadioGroup>
          </DropdownMenuContent>
        </DropdownMenu>
      )}
      {onReveal && <Action Icon={ListTree} label="Rodyti sąraše" testId="selection-reveal" onClick={onReveal} title={'Atidaryti dešinėje sąraše „Matavimai" ir parodyti šią eilutę'} />}
      {onDelete && <Action Icon={Trash2} label="Ištrinti" testId="selection-delete" danger onClick={onDelete} title={withKeyTitle('Ištrinti matavimą — atšaukiama istorijoje', 'deleteSelected')} />}
    </>
  );
}
