/**
 * OutlineToolButtons — „Padalyti" / „Sujungti" / „Atimti" in the viewer toolbar, next to „Redaguoti
 * kontūrą", for the focused room (2026-10-16). Pressed while its tool is active; a second press cancels.
 */
import { Scissors, Combine, SquareDashed } from 'lucide-react';

const TOOLS = [
  { id: 'split', Icon: Scissors, label: 'Padalyti', title: (nr) => `Padalyti patalpos ${nr} kontūrą linija: dvi vietos linijai, tada spustelėkite dalį, kuri lieka; kitą dalį priskirkite kitai patalpai arba neįtraukite` },
  { id: 'merge', Icon: Combine, label: 'Sujungti', title: (nr) => `Sujungti patalpą ${nr} su gretima: spustelėkite besiliečiantį kitos patalpos kontūrą šiame lape — ta patalpa bus neįtraukta į skaičiavimus` },
  { id: 'subtract', Icon: SquareDashed, label: 'Atimti', title: (nr) => `Atimti iš patalpos ${nr} kontūro koloną, spintą ar šachtą: nubrėžkite stačiakampį arba daugiakampį jo viduje` },
];

export default function OutlineToolButtons({ focusedRoomNr, active = null, onStart, onCancel }) {
  if (focusedRoomNr == null || !onStart) return null;
  const btn = 'inline-flex items-center gap-1 px-1.5 py-1 rounded text-[hsl(var(--viewer-chrome-foreground))] hover:bg-[hsl(var(--viewer-chrome-hover))]';
  const pressed = 'inline-flex items-center gap-1 px-1.5 py-1 rounded bg-[hsl(var(--viewer-chrome-active)/0.18)] text-[hsl(var(--viewer-chrome-active))]';
  return (
    <span className="inline-flex items-center gap-0.5 mr-1" data-testid="outline-tool-buttons">
      {TOOLS.map(({ id, Icon, label, title }) => (
        <button
          key={id}
          type="button"
          className={active === id ? pressed : btn}
          aria-pressed={active === id}
          title={title(focusedRoomNr)}
          data-testid={`outline-tool-${id}`}
          onClick={() => (active === id ? onCancel?.() : onStart(id))}
        >
          <Icon className="w-3.5 h-3.5" />
          <span className="text-[11px] leading-none hidden lg:inline">{label}</span>
        </button>
      ))}
    </span>
  );
}
