/**
 * ScaleCheckCard — „Patikrinti mastelį" readout (Togal-v2 W6, 2026-10-16). Two clicks on the sheet → the
 * length the current scale gives, next to the dimension strings the lane read nearest to that line, each with
 * what the current scale makes of its own drawn line. Changes nothing; the tool stays armed for another pair.
 * Numbers from lib/scaleCheck (pure).
 */
import { X } from 'lucide-react';
import { formatNumberLT } from '@/lib/measureGeometry';
import { scaleStatusText } from '@/lib/scaleLabel';

const m = (v) => `${formatNumberLT(v, 2)} m`;

export default function ScaleCheckCard({ readout, page, scale, onClose }) {
  if (!readout) return null;
  return (
    <div className="w-80 rounded-[2px] border border-border bg-card text-card-foreground shadow-lg text-[12px]" data-testid="scale-check">
      <div className="flex items-center gap-2 px-3 py-2 border-b border-border">
        <span className="text-[13px] font-semibold flex-1">Mastelio patikra · lapas {page}</span>
        <button type="button" className="p-1 rounded-[2px] hover:bg-muted" onClick={onClose} title="Uždaryti (Esc)" aria-label="Uždaryti patikrą"><X className="w-4 h-4" /></button>
      </div>
      <div className="px-3 py-2 border-b border-border">
        <div className="text-muted-foreground text-[11px]">{scaleStatusText(scale)}</div>
        <div className="mt-1">
          Pažymėta atkarpa:{' '}
          {readout.lengthM != null
            ? <b className="mono tabular text-[14px]" data-testid="scale-check-length">{m(readout.lengthM)}</b>
            : <b>mastelis nenustatytas — metrų nėra</b>}
        </div>
        <div className="mt-1 text-muted-foreground text-[11px]">Palyginkite su matmeniu, kurio tikrą ilgį žinote. Niekas nepakeičiama.</div>
      </div>
      <div className="px-3 py-2">
        {readout.nearest.length ? (
          <>
            <div className="text-[11px] text-muted-foreground mb-1">Artimiausi plane užrašyti matmenys šiame lape:</div>
            <table className="w-full text-[11.5px]">
              <thead>
                <tr className="text-muted-foreground text-left">
                  <th className="font-normal">Užrašyta</th>
                  <th className="font-normal text-right">Pagal mastelį</th>
                  <th className="font-normal text-right">Skirtumas</th>
                </tr>
              </thead>
              <tbody>
                {readout.nearest.map((n, i) => (
                  <tr key={i} data-scale-check-string={n.text}>
                    <td className="mono tabular">{n.text} <span className="text-muted-foreground">({m(n.value_m)})</span></td>
                    <td className="mono tabular text-right" title={n.available ? undefined : 'Šiam nuskaitymui patikra negalima'}>{n.drawnM != null ? m(n.drawnM) : '—'}</td>
                    <td className="mono tabular text-right">{n.diffPct != null ? `${n.diffPct > 0 ? '+' : ''}${formatNumberLT(n.diffPct, 1)} %` : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="mt-1 text-muted-foreground text-[11px] leading-snug">„Pagal mastelį" — nupieštos linijos ilgis be brūkšnio storio × mastelis; „Skirtumas" — prieš užrašą.</div>
            {readout.nearest.some((n) => !n.available) && (
              <div className="mt-1 text-[11px] leading-snug text-foreground" data-testid="scale-check-unavailable">
                Šiam brėžinio nuskaitymui patikra negalima: jame neišsaugotas linijų ilgis. Perskaitykite brėžinį iš naujo (nemokamai) ir patikra veiks.
              </div>
            )}
          </>
        ) : (
          <div className="text-muted-foreground text-[11.5px] leading-snug">Šiame lape programa nerado užrašytų matmenų, su kuriais būtų galima palyginti — palyginkite su matmeniu, kurį matote brėžinyje.</div>
        )}
      </div>
    </div>
  );
}
