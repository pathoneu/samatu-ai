/**
 * WorkspacePanel — kompaktinė sąmatos panelė šalia brėžinio.
 *
 * Vartotojas brūkšnioja zoną PDF'e (kairėje), automatiškai atsiranda
 * dešinėje su plotu, perimetru, paskirtimi. Visi totals atsinaujina.
 */

import { useState, useMemo, useEffect } from 'react';
import { Plus, Eye, Edit2, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { loadTakeoff, removePolygon } from '@/lib/takeoffStore';

function fmt(v, d = 1) {
  if (v == null) return '—';
  return Number(v).toLocaleString('lt-LT', { maximumFractionDigits: d });
}
function fmtEur(v) {
  if (v == null) return '—';
  return `${Number(v).toLocaleString('lt-LT', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €`;
}

// Auto-poll takeoff store kas 800ms (kad gauti naujus polygon'us iš PdfViewer)
function useTakeoff(projectId) {
  const [takeoff, setTakeoff] = useState(() => loadTakeoff(projectId));
  useEffect(() => {
    const id = setInterval(() => {
      setTakeoff(loadTakeoff(projectId));
    }, 800);
    return () => clearInterval(id);
  }, [projectId]);
  return [takeoff, setTakeoff];
}

export default function WorkspacePanel({ project, onShowDrawing }) {
  const [takeoff, setTakeoff] = useTakeoff(project.id);

  // V8 patalpos + manualiai brūkšniotos zonos
  const allRooms = useMemo(() => {
    const v8 = (project.v8_rooms || []).map(r => ({
      ...r, source: 'ai',
    }));
    const manual = (takeoff.polygons || [])
      .filter(p => p.type === 'room')
      .map(p => ({
        nr: p.room_nr,
        pavadinimas: p.label || 'Patalpa',
        paskirtis: p.paskirtis || 'gyvenamoji',
        plotas_m2: p.area_m2 || 0,
        perimetras_m: p.perimeter_m || 0,
        lubu_aukstis_m: p.lubu_aukstis_m || 2.82,
        page: p.page,
        polygon_id: p.id,
        source: 'manual',
      }));
    return [...v8, ...manual];
  }, [project.v8_rooms, takeoff.polygons]);

  const totalArea = allRooms.reduce((s, r) => s + (r.plotas_m2 || 0), 0);
  const manualCount = allRooms.filter(r => r.source === 'manual').length;

  // Live darbu_sarasas perskaičiavimas (paprasčiausias variantas — naudojam projekto sumas)
  const projectTotal = useMemo(() => {
    let viso = 0;
    (project.darbu_sarasas || []).forEach(it => {
      viso += (it.kiekis || 0) * (it.kaina || 0);
    });
    return viso;
  }, [project.darbu_sarasas]);

  const handleRemovePolygon = (id) => {
    if (!window.confirm('Ištrinti pažymėjimą?')) return;
    setTakeoff(t => removePolygon(t, id));
  };

  return (
    <div className="flex flex-col h-full bg-background overflow-hidden">
      {/* Top stats */}
      <div className="px-3 py-2.5 border-b border-border bg-card">
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div>
            <div className="text-muted-foreground">Patalpų</div>
            <div className="text-base font-semibold tabular-nums text-foreground">
              {allRooms.length}
              {manualCount > 0 && (
                <span className="ml-1 text-[10px] text-emerald-600 font-normal">
                  +{manualCount} pažym.
                </span>
              )}
            </div>
          </div>
          <div>
            <div className="text-muted-foreground">Bendras plotas</div>
            <div className="text-base font-semibold tabular-nums text-foreground">
              {fmt(totalArea)} m²
            </div>
          </div>
          <div className="col-span-2 pt-1.5 border-t border-border">
            <div className="text-muted-foreground text-[10px] uppercase tracking-wide">
              Sąmatos suma (be PVM)
            </div>
            <div className="text-lg font-bold tabular-nums text-foreground">
              {fmtEur(projectTotal)}
            </div>
          </div>
        </div>
      </div>

      {/* Pridėti zonos hint */}
      <div className="px-3 py-2 border-b border-border bg-muted/40 text-xs text-muted-foreground">
        Pažymėk kambarį brėžinyje — automatiškai atsiras sąraše su plotu ir perimetru.
      </div>

      {/* Patalpų sąrašas — kompaktinė lentelė */}
      <div className="flex-1 overflow-y-auto">
        {allRooms.length === 0 ? (
          <div className="p-6 text-center text-xs text-muted-foreground">
            Patalpų dar nėra.<br />
            Spauskite "Pažymėti zoną" toolbar'e ir<br />
            brūkšniokite kambario kraštus.
          </div>
        ) : (
          <table className="w-full text-xs">
            <thead className="bg-muted/40 text-muted-foreground sticky top-0">
              <tr className="border-b border-border">
                <th className="px-2 py-1.5 text-left font-medium uppercase tracking-wide">Patalpa</th>
                <th className="px-2 py-1.5 text-right font-medium uppercase tracking-wide">m²</th>
                <th className="px-2 py-1.5 text-right font-medium uppercase tracking-wide">m</th>
                <th className="w-8" />
              </tr>
            </thead>
            <tbody>
              {allRooms.map((r, i) => (
                <tr key={`${r.nr}-${i}`}
                    className="border-b border-border/50 last:border-0 hover:bg-muted/30 group">
                  <td className="px-2 py-1.5">
                    <div className="flex items-center gap-1.5">
                      <span className={`w-1.5 h-1.5 rounded-full ${
                        r.source === 'manual' ? 'bg-emerald-500' : 'bg-blue-500'
                      }`} title={r.source === 'manual' ? 'Pažymėta brėžinyje' : 'AI atpažino'} />
                      <div className="min-w-0">
                        <div className="text-foreground truncate font-medium">
                          {r.pavadinimas}
                        </div>
                        <div className="text-[10px] text-muted-foreground">{r.paskirtis}</div>
                      </div>
                    </div>
                  </td>
                  <td className="px-2 py-1.5 text-right tabular-nums text-foreground font-medium">
                    {fmt(r.plotas_m2)}
                  </td>
                  <td className="px-2 py-1.5 text-right tabular-nums text-muted-foreground">
                    {fmt(r.perimetras_m)}
                  </td>
                  <td className="px-1 py-1.5 text-right">
                    {r.source === 'manual' && (
                      <button onClick={() => handleRemovePolygon(r.polygon_id)}
                        className="opacity-0 group-hover:opacity-100 p-0.5 hover:bg-red-50 dark:hover:bg-red-900/30 text-red-600 rounded transition-opacity"
                        title="Ištrinti pažymėjimą">
                        <Trash2 className="w-3 h-3" />
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot className="bg-muted/30 sticky bottom-0">
              <tr className="border-t border-border">
                <td className="px-2 py-1.5 font-semibold uppercase tracking-wide text-muted-foreground">
                  Viso
                </td>
                <td className="px-2 py-1.5 text-right font-bold tabular-nums text-foreground">
                  {fmt(totalArea)}
                </td>
                <td colSpan={2} />
              </tr>
            </tfoot>
          </table>
        )}
      </div>

      {/* Bottom hint */}
      <div className="px-3 py-2 border-t border-border bg-muted/20 text-[10px] text-muted-foreground flex items-center gap-3">
        <span className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-blue-500" />
          AI atpažinta
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-emerald-500" />
          pažymėta brėžinyje
        </span>
      </div>
    </div>
  );
}
