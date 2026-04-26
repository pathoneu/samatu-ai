/**
 * PageStructureCard — projekto PDF puslapių klasifikacijos sąrašas.
 *
 * Vartotojas mato medį: kiek grindų planų, kiek lubų planų, kiek sienų
 * išklotinių, kiek specifikacijų. Spustelėjus tipą — perjungia į Brėžinio
 * tab'ą su tuo puslapiu.
 */

import { FileText, Layers, Square, Building2, BookOpen, Zap, Droplets, HelpCircle, ChevronRight } from 'lucide-react';

// Visi tipai vienodai neutralūs — atskiriame tik per ikoną ir pavadinimą.
const TYPE_META = {
  floor_plan:     { icon: FileText },
  ceiling_plan:   { icon: Layers },
  wall_elevation: { icon: Square },
  facade:         { icon: Building2 },
  section:        { icon: ChevronRight },
  electrical:     { icon: Zap },
  plumbing:       { icon: Droplets },
  specification:  { icon: BookOpen },
  unknown:        { icon: HelpCircle },
  title:          { icon: FileText },
};

const TYPE_ORDER = [
  'floor_plan', 'ceiling_plan', 'wall_elevation',
  'facade', 'section', 'electrical', 'plumbing',
  'specification', 'title', 'unknown',
];

const TYPE_LABELS = {
  floor_plan:     'Grindų planai',
  ceiling_plan:   'Lubų planai',
  wall_elevation: 'Sienų išklotinės',
  facade:         'Fasadai',
  section:        'Pjūviai',
  electrical:     'Elektros',
  plumbing:       'Santechnikos',
  specification:  'Specifikacijos',
  title:          'Tituliniai',
  unknown:        'Nežinomi',
};

export default function PageStructureCard({ pages = [], summary = null, onPageClick }) {
  if (!pages.length && !summary) return null;

  const byType = summary?.by_type || pages.reduce((acc, p) => {
    const t = p.type || 'unknown';
    (acc[t] = acc[t] || []).push(p.page);
    return acc;
  }, {});

  const totalPages = pages.length || summary?.total_pages || 0;
  const knownTypes = TYPE_ORDER.filter(t => byType[t]?.length > 0 && t !== 'unknown' && t !== 'title');
  const unknownCount = byType.unknown?.length || 0;

  return (
    <div className="bg-card border border-border rounded-xl p-4">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold text-foreground flex items-center gap-2">
          <FileText className="w-4 h-4 text-muted-foreground" />
          Brėžinio struktūra
          <span className="text-xs font-normal text-muted-foreground">
            ({totalPages} puslapių, atpažinta {totalPages - unknownCount}/{totalPages})
          </span>
        </h2>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
        {knownTypes.map(type => {
          const pageNrs = byType[type] || [];
          const meta = TYPE_META[type] || TYPE_META.unknown;
          const Icon = meta.icon;

          return (
            <button
              key={type}
              onClick={() => onPageClick?.(pageNrs[0], type)}
              className="flex items-start gap-2 p-2.5 rounded-lg border border-border bg-card hover:border-foreground/30 hover:bg-muted/40 transition-all text-left"
              title={`Puslapiai: ${pageNrs.join(', ')}`}
            >
              <Icon className="w-4 h-4 shrink-0 mt-0.5 text-muted-foreground" />
              <div className="min-w-0 flex-1">
                <div className="text-xs font-semibold text-foreground">
                  {TYPE_LABELS[type]}
                </div>
                <div className="text-xs text-muted-foreground mt-0.5">
                  {pageNrs.length} {pageNrs.length === 1 ? 'puslapis' : 'puslapiai'}
                </div>
                <div className="text-[10px] text-muted-foreground/70 mt-0.5 truncate">
                  Psl. {pageNrs.slice(0, 4).join(', ')}{pageNrs.length > 4 ? '…' : ''}
                </div>
              </div>
            </button>
          );
        })}
      </div>

      {unknownCount > 0 && (
        <div className="mt-3 pt-3 border-t border-border text-xs text-muted-foreground">
          <HelpCircle className="w-3 h-3 inline mr-1" />
          {unknownCount} {unknownCount === 1 ? 'puslapis nežinomas' : 'puslapiai nežinomi'} — galimai
          rastriniai brėžiniai be teksto antraštinėje plokštelėje.
        </div>
      )}
    </div>
  );
}
