/**
 * The three row kinds of the Kiekiai tree: section header, family (one sąmata line) and room (one
 * contribution). Presentational only — every number arrives from lib/quantitiesTree.js, which takes it
 * verbatim from the server; nothing here adds or rescales a quantity.
 */

import { ChevronDown, ChevronRight, Eye, EyeOff, Info } from 'lucide-react';
import { CONFIDENCE_DOT_CLASS, confidenceLabel } from '@/lib/confidence';
import { ltNumber, ltQuantity } from '@/lib/ledger';
import { cleanUserText } from '@/lib/userText';

const SOURCE_CLASS = {
  user: 'text-primary border-primary/40',
  walls: 'text-foreground/80 border-border',
  approx: 'text-amber-700 border-amber-500/40',
  marker: 'text-muted-foreground border-border',
  none: 'text-muted-foreground border-border',
};

const SOURCE_TITLE = {
  user: 'Patalpos kontūrą nubrėžėte arba pataisėte jūs',
  walls: 'Kontūras atsektas pagal sienų linijas brėžinyje',
  approx: 'Kontūras apytikslis — patikrinkite brėžinyje ir, jei reikia, pataisykite',
  marker: 'Brėžinyje rastas tik patalpos numeris, kontūro nėra',
  none: 'Patalpos kontūro brėžinyje nėra',
};

function rowStateClass({ active, focused }) {
  return [
    focused ? 'bg-primary/10 shadow-[inset_3px_0_0_hsl(var(--primary))]' : '',
    active ? 'outline outline-1 -outline-offset-1 outline-primary/60' : '',
  ].join(' ');
}

export function SectionRow({ section, collapsed, active, onToggle }) {
  return (
    <button
      type="button"
      data-qkey={section.key}
      onClick={onToggle}
      aria-expanded={!collapsed}
      className={`w-full flex items-center gap-1.5 px-2.5 py-1.5 text-left bg-muted/40 border-b border-border/60 hover:bg-muted/70 transition-colors ${rowStateClass({ active })}`}
      title={collapsed ? 'Išskleisti skyrių' : 'Suskleisti skyrių'}
    >
      {collapsed
        ? <ChevronRight className="w-3 h-3 text-muted-foreground shrink-0" />
        : <ChevronDown className="w-3 h-3 text-muted-foreground shrink-0" />}
      <span className="skyrius-header truncate">{section.label}</span>
      <span className="ml-auto mono tabular text-muted-foreground" style={{ fontSize: 10 }}>
        {section.families.length}
      </span>
    </button>
  );
}

export function FamilyRow({ family, expanded, active, containsFocused, onToggle, onMouseEnter, onMouseLeave }) {
  const dot = CONFIDENCE_DOT_CLASS[family.confidence];
  const confTitle = `${confidenceLabel(family.confidence)}${family.confidenceReason
    ? ` — ${cleanUserText(family.confidenceReason)}` : ''}`;
  return (
    <div
      role="treeitem"
      aria-expanded={expanded}
      data-qkey={family.key}
      onClick={onToggle}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      className={`grid items-center cursor-pointer border-b border-border/50 hover:bg-muted/50 transition-colors ${rowStateClass({ active, focused: containsFocused })}`}
      style={{ gridTemplateColumns: '14px 9px 1fr auto', gap: 6, padding: '5px 10px 5px 14px', fontSize: 12 }}
    >
      {expanded
        ? <ChevronDown className="w-3 h-3 text-muted-foreground" />
        : <ChevronRight className="w-3 h-3 text-muted-foreground" />}
      <span className={`dot ${dot}`} title={confTitle} aria-label={confTitle} />
      <span className="text-foreground/90 truncate" title={family.label}>{family.label}</span>
      <span className="mono tabular whitespace-nowrap text-foreground" style={{ fontSize: 11 }}>
        {family.overridden && (
          <span className="mr-1 rounded border border-primary/40 px-1 text-primary" style={{ fontSize: 9, lineHeight: '14px' }} title="Kiekį įrašėte ranka">
            ranka
          </span>
        )}
        {family.total == null
          ? <span className="text-muted-foreground" title="Kiekio programa neapskaičiavo — suveskite jį sąmatoje">— {family.unit}</span>
          : ltQuantity(family.total, family.unit)}
      </span>
    </div>
  );
}

export function RoomRow({
  family, room, active, focused, onClick, onToggleHidden, onMouseEnter, onMouseLeave,
}) {
  const share = !family.rollUpAuthoritative && !family.overridden && family.total > 0 && room.value != null
    ? Math.round((room.value / family.total) * 100) : null;
  const sourceKind = room.source.kind;
  return (
    <div
      role="treeitem"
      data-qkey={`${family.key}/${room.key}`}
      onClick={onClick}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      className={`grid items-center cursor-pointer border-b border-border/40 hover:bg-muted/50 transition-colors ${room.hidden ? 'opacity-50' : ''} ${rowStateClass({ active, focused })}`}
      style={{ gridTemplateColumns: '22px 1fr auto auto 18px', gap: 6, padding: '4px 10px 4px 34px', fontSize: 11.5 }}
      title={[
        room.includedBecause ? cleanUserText(room.includedBecause) : null,
        room.page ? `Lapas ${room.page} — spustelėkite, kad parodytų brėžinyje` : 'Spustelėkite, kad parodytų brėžinyje',
      ].filter(Boolean).join(' · ')}
    >
      <span className="mono tabular text-muted-foreground" style={{ fontSize: 10 }}>{room.nr}</span>
      <span className="text-foreground/85 truncate">{room.name}</span>
      <span
        className={`rounded border px-1 whitespace-nowrap ${SOURCE_CLASS[sourceKind] || SOURCE_CLASS.none}`}
        style={{ fontSize: 9, lineHeight: '14px' }}
        title={SOURCE_TITLE[sourceKind]}
      >
        {room.source.label}
      </span>
      <span className="mono tabular whitespace-nowrap text-foreground/90" style={{ fontSize: 11 }}>
        {ltQuantity(room.value, room.unit)}
        {share != null && (
          <span className="text-muted-foreground ml-1" style={{ fontSize: 9 }}>{share} %</span>
        )}
      </span>
      <button
        type="button"
        onClick={(e) => { e.stopPropagation(); onToggleHidden?.(); }}
        disabled={!onToggleHidden}
        className="flex items-center justify-center text-muted-foreground hover:text-foreground disabled:opacity-30"
        style={{ width: 16, height: 16 }}
        title={room.hidden ? 'Rodyti patalpos kontūrą brėžinyje' : 'Slėpti patalpos kontūrą brėžinyje'}
        aria-label={room.hidden ? 'Rodyti kontūrą' : 'Slėpti kontūrą'}
        aria-pressed={room.hidden}
      >
        {room.hidden ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
      </button>
    </div>
  );
}

/**
 * What sits under the room rows of an open family: the roll_up explanation when the rooms do not add
 * up to the total, the honest „not split by room" line when there are no contributions, the rooms left
 * out and why, and the reminder that the program computes the line — changes go through Prielaidos.
 */
export function FamilyFooter({ family, onOpenAssumptions }) {
  const noRooms = family.rooms.length === 0;
  return (
    <div className="border-b border-border/50 bg-muted/20 text-muted-foreground" style={{ padding: '5px 10px 6px 34px', fontSize: 10.5, lineHeight: '15px' }}>
      {family.rollUpAuthoritative && (
        <p className="text-foreground/80">
          <Info className="inline w-3 h-3 mr-1 -mt-0.5" />
          {family.rollUpLine}
          {family.rollUpNote ? ` — ${cleanUserText(family.rollUpNote)}` : ''}
        </p>
      )}
      {family.overridden && !noRooms && (
        <p className="text-foreground/80">
          Kiekį įrašėte ranka
          {family.programTotal != null ? ` (programa skaičiavo ${ltQuantity(family.programTotal, family.unit)})` : ''}
          {' '}— patalpų kiekiai rodo programos skaičiavimą.
        </p>
      )}
      {noRooms && family.total == null && (
        <p>Šio kiekio programa neapskaičiavo — suveskite jį sąmatoje.</p>
      )}
      {noRooms && family.total != null && family.manual && (
        <p>Šią eilutę įrašėte ranka — ji neskaidoma pagal patalpas.</p>
      )}
      {noRooms && family.total != null && !family.manual && (
        <p>
          Šis kiekis neskaidomas pagal patalpas
          {family.sourceLabel ? ` — šaltinis: ${family.sourceLabel}` : ''}.
        </p>
      )}
      {family.excluded.length > 0 && (
        <p title={family.excluded.map((e) => `${e.nr} ${e.name}${e.because ? `: ${cleanUserText(e.because)}` : ''}`).join('\n')}>
          {family.excluded.some((e) => !e.mergedInto) && <>Neįtraukta: {family.excluded.filter((e) => !e.mergedInto).map((e) => `${e.nr} ${e.name}`).join(', ')} </>}
          {family.excluded.some((e) => e.mergedInto) && <>Sujungta: {family.excluded.filter((e) => e.mergedInto).map((e) => `${e.nr} → ${e.mergedInto}`).join(', ')}</>}
        </p>
      )}
      {!family.manual && (
        <p>
          Kiekį apskaičiavo programa iš brėžinio.{' '}
          {onOpenAssumptions ? (
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); onOpenAssumptions(); }}
              className="text-primary hover:underline"
            >
              Keisti nustatymus →
            </button>
          ) : 'Pakeisti galite per „Nustatymai“.'}
        </p>
      )}
    </div>
  );
}

/** Σ per unit of the lines shown — server `kiekis` added up, said plainly. */
export function TotalsFooter({ totals, shown, all }) {
  return (
    <div
      className="shrink-0 border-t border-border bg-card px-2.5 py-1.5 text-muted-foreground"
      style={{ fontSize: 10.5 }}
      title="Rodomų eilučių kiekių suma pagal mato vienetą. Skirtingi darbai su tuo pačiu vienetu sudedami — tai apžvalga, ne viena sąmatos eilutė."
    >
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5">
        <span>Rodoma {shown}{shown !== all ? ` iš ${all}` : ''} eil.</span>
        {totals.units.map((u) => (
          <span key={u.unit} className="mono tabular text-foreground/90">
            Σ {ltNumber(u.value)} {u.unit}
          </span>
        ))}
        {totals.missing > 0 && <span>{totals.missing} be kiekio</span>}
      </div>
    </div>
  );
}
