import React, { useState } from 'react';
import { X } from 'lucide-react';
import { postCorrections, buildUpdateOp, buildVerifyOp } from '../api/correctionsApi';

/**
 * CorrectionPanel — slide-out side panel for editing a single quantity line.
 * Mounts when the user clicks a Kiekiai cell. Saves go to
 * /api/corrections/<project_id>; the consumer is responsible for
 * re-fetching state after onSaved fires.
 *
 * UX inspired by Togal's binary-commit pattern (no confidence axis exposed
 * here — caller owns the dot rendering). The "Patikrinta" green button
 * upgrades the line's source to "verified".
 */
export function CorrectionPanel({ projectId, line, onClose, onSaved }) {
  const [value, setValue] = useState(String(line?.quantity ?? ''));
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function save() {
    setBusy(true);
    setError(null);
    try {
      const newQty = parseFloat(value);
      if (!Number.isFinite(newQty)) {
        throw new Error('Neteisinga skaičiaus reikšmė');
      }
      await postCorrections(projectId, [
        buildUpdateOp({
          targetCode: line.code,
          beforeQty: line.quantity,
          afterQty: newQty,
          reason,
        }),
      ]);
      onSaved?.({ ...line, quantity: newQty, source: 'user' });
      onClose?.();
    } catch (err) {
      setError(err?.message || 'Nepavyko išsaugoti');
    } finally {
      setBusy(false);
    }
  }

  async function verify() {
    setBusy(true);
    setError(null);
    try {
      await postCorrections(projectId, [
        buildVerifyOp({ targetCode: line.code }),
      ]);
      onSaved?.({ ...line, source: 'verified' });
      onClose?.();
    } catch (err) {
      setError(err?.message || 'Nepavyko pažymėti Patikrinta');
    } finally {
      setBusy(false);
    }
  }

  if (!line) return null;

  return (
    <div
      role="dialog"
      aria-label="Pataisyti kiekį"
      className="fixed inset-y-0 right-0 w-96 bg-white border-l shadow-xl z-50 flex flex-col"
    >
      <div className="flex items-start justify-between p-4 border-b">
        <div>
          <h3 className="font-semibold">{line.label_lt || line.code}</h3>
          <p className="text-xs text-stone-500 font-mono mt-0.5">{line.code}</p>
        </div>
        <button
          onClick={onClose}
          className="p-1 rounded hover:bg-stone-100"
          aria-label="Užverti"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="flex-1 p-4 space-y-3 overflow-y-auto">
        <label className="block text-sm">
          <span className="text-stone-700">Kiekis ({line.unit})</span>
          <input
            type="number"
            step="0.01"
            className="mt-1 block w-full border rounded px-2 py-1.5 text-sm"
            value={value}
            onChange={(e) => setValue(e.target.value)}
          />
        </label>

        <label className="block text-sm">
          <span className="text-stone-700">Pastaba (kodėl taisai?)</span>
          <input
            type="text"
            placeholder="pvz. „papildomas angokraštis prie paslėptų durų"
            className="mt-1 block w-full border rounded px-2 py-1.5 text-sm"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
        </label>

        {error && (
          <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded p-2">
            {error}
          </div>
        )}

        <div className="text-xs text-stone-500 space-y-1 pt-2">
          <p>
            <strong>Išsaugoti:</strong> pakeičia kiekį ir pažymi šaltinį „Vartotojo redaguota".
          </p>
          <p>
            <strong>Patikrinta:</strong> palieka kiekį, bet pažymi šaltinį „Patikrinta"
            (eksportui ir audito takui).
          </p>
        </div>
      </div>

      <div className="border-t p-4 flex gap-2">
        <button
          onClick={save}
          disabled={busy}
          className="flex-1 bg-blue-600 hover:bg-blue-700 text-white px-3 py-2 rounded text-sm font-medium disabled:opacity-50"
        >
          {busy ? 'Saugoma…' : 'Išsaugoti'}
        </button>
        <button
          onClick={verify}
          disabled={busy}
          className="flex-1 bg-emerald-600 hover:bg-emerald-700 text-white px-3 py-2 rounded text-sm font-medium disabled:opacity-50"
        >
          {busy ? '…' : 'Patikrinta ✓'}
        </button>
      </div>
    </div>
  );
}

export default CorrectionPanel;
