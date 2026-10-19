/**
 * RoomPicker — „2 iš 11 ▾": every room of the project in one list, each with its state in words, one click
 * to open it (Pathon v3 W5-C, C7 / coverage #215). Replaces walking „Kitas" eleven times to reach room 09.
 * The state is a word, never only a mark: „patikrinta", „liko patikrinti", „neskaičiuojama", „sujungta su 04".
 */

import { useTranslation } from 'react-i18next';
import { Check, ChevronDown, Circle, Minus } from 'lucide-react';

import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { pickerCounts } from '@/lib/roomSheetNav';

const ICON = { checked: Check, open: Circle, excluded: Minus, merged: Minus };

export default function RoomPicker({ items, index, total, onPick, className = '' }) {
  const { t } = useTranslation();
  const counts = pickerCounts(items);
  return (
    <DropdownMenu modal={false}>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className={`inline-flex min-h-[44px] items-center gap-1.5 rounded-[2px] border border-white/25 px-3 font-mono text-[14px] tabular-nums text-white/90 hover:bg-white/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/60 ${className}`}
          aria-label={t('project.roomPicker.open')}
          data-testid="room-picker"
        >
          {t('project.roomSheet.roomStep', { index, total })}
          <ChevronDown className="h-4 w-4" aria-hidden="true" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="max-h-[70vh] w-80 overflow-y-auto rounded-panel" data-testid="room-picker-list">
        <DropdownMenuLabel className="text-[14px] font-normal text-muted-foreground">
          {t(counts.merged ? 'project.roomPicker.countsMerged' : 'project.roomPicker.counts', { open: counts.open, checked: counts.checked, merged: counts.merged })}
        </DropdownMenuLabel>
        {items.map((it) => {
          const Icon = ICON[it.state] || Circle;
          return (
            <DropdownMenuItem
              key={it.nr}
              onSelect={() => onPick?.(it.nr)}
              aria-current={it.current ? 'true' : undefined}
              className={`flex items-start gap-2 text-[15px] ${it.current ? 'bg-muted font-semibold' : ''}`}
              data-testid={`room-picker-${it.nr}`}
              data-state-word={it.state}
            >
              <Icon className={`mt-1 h-3.5 w-3.5 shrink-0 ${it.state === 'checked' ? 'text-[hsl(var(--accent-2))]' : 'text-muted-foreground'}`} aria-hidden="true" />
              <span className="min-w-0 flex-1">
                <span className="font-mono text-muted-foreground">{it.nr}</span> {it.name}
                <span className="block text-[14px] font-normal text-muted-foreground">
                  {it.state === 'merged'
                    ? t('project.roomPicker.state.merged', { nr: it.mergedInto })
                    : t(`project.roomPicker.state.${it.state}`)}
                </span>
              </span>
            </DropdownMenuItem>
          );
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
