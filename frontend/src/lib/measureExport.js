// Export/import of measurement sets to JSON and CSV (LT locale).
import { measurementValue } from './measurements.js';
import { formatNumberLT } from './measureGeometry.js';

export function toJSON(doc, pretty = true) { return JSON.stringify(doc, null, pretty ? 2 : 0); }

export function fromJSON(text) {
  const d = JSON.parse(text);
  if (!d || typeof d !== 'object' || !('measurements' in d)) throw new Error('Netinkamas matavimų failas (neatpažintas formatas).');
  return d;
}

// doc = { measurements, measureScales, countTypes, display:{decimals} }
export function toMeasurementsCSV(doc) {
  const measurements = doc.measurements || [];
  const measureScales = doc.measureScales || {};
  const countTypes = doc.countTypes || [];
  const decimals = doc.display?.decimals ?? 2;
  const uncal = { metersPerPointX: 0, metersPerPointY: 0, calibrated: false };
  const SEP = ';';
  const esc = (v) => (/[";\n]/.test(v) ? `"${String(v).replace(/"/g, '""')}"` : String(v));
  const rows = [['Lapas', 'Tipas', 'Klasifikacija', 'Kiekis', 'Vnt.', 'Antrinis', 'Antrinis vnt.', 'Patikimumas', 'Šaltinis']];
  for (const m of measurements) {
    if (m.kind === 'count') continue;
    const scale = measureScales[m.page] || uncal;
    const { value, secondary } = measurementValue(m, scale);
    const isArea = m.kind === 'area';
    rows.push([
      String(m.page),
      isArea ? 'Plotas' : m.kind === 'perimeter' ? 'Perimetras' : 'Atstumas',
      m.classification || '',
      formatNumberLT(value, decimals),
      isArea ? 'm²' : 'm',
      secondary !== undefined ? formatNumberLT(secondary, decimals) : '',
      secondary !== undefined ? 'm' : '',
      m.confidence || '',
      m.source || '',
    ]);
  }
  const tallies = {};
  for (const m of measurements) if (m.kind === 'count' && m.typeId) tallies[m.typeId] = (tallies[m.typeId] || 0) + 1;
  for (const t of countTypes) { const n = tallies[t.id] || 0; if (!n) continue; rows.push(['—', 'Skaičius', t.label, String(n), 'vnt.', '', '', '', '']); }
  return rows.map((r) => r.map(esc).join(SEP)).join('\r\n');
}

export function downloadText(filename, text, mime = 'text/plain') {
  if (typeof document === 'undefined') return;
  const blob = new Blob([text], { type: `${mime};charset=utf-8` });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = filename;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export function exportJSONFile(doc, filename = 'matavimai.json') { downloadText(filename, toJSON(doc), 'application/json'); }
export function exportCSVFile(doc, filename = 'matavimai.csv') { downloadText(filename, '﻿' + toMeasurementsCSV(doc), 'text/csv'); }
