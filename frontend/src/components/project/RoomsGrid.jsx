/**
 * RoomsGrid — visų patalpų grid view su totals.
 *
 * Iš V8 backend'o gauna:
 * - v8_rooms: per-kambarį skaičiai
 * - v8_totals: suminiai
 *
 * Vartotojas gali:
 * - Redaguoti kiekvieną patalpą (RoomCard inline edit)
 * - Pašalinti patalpą
 * - Pridėti naują patalpą
 *
 * Live recalc: kai vartotojas keičia patalpą — totals atnaujina vietoje.
 */

import { useMemo, useState } from 'react';
import { Plus } from 'lucide-react';
import RoomCard from './RoomCard';

// Universal industries skaičiavimas frontend'e (tas pats, kas backend V8)
const ROOM_RULES = {
  gyvenamoji:  { walls_paint: 1.0, ceiling: 'gkp', tile_walls_to_m: 0,   tile_floor: false },
  miegamoji:   { walls_paint: 1.0, ceiling: 'gkp', tile_walls_to_m: 0,   tile_floor: false },
  valgomasis:  { walls_paint: 1.0, ceiling: 'gkp', tile_walls_to_m: 0,   tile_floor: false },
  virtuve:     { walls_paint: 1.0, ceiling: 'gkp', tile_walls_to_m: 0.6, tile_floor: true },
  vonia:       { walls_paint: 1.0, ceiling: 'pakabinamos', tile_walls_to_m: 2.0, tile_floor: true },
  wc:          { walls_paint: 1.0, ceiling: 'pakabinamos', tile_walls_to_m: 2.0, tile_floor: true },
  san:         { walls_paint: 1.0, ceiling: 'pakabinamos', tile_walls_to_m: 2.0, tile_floor: true },
  koridorius:  { walls_paint: 1.0, ceiling: 'gkp', tile_walls_to_m: 0,   tile_floor: false },
  holas:       { walls_paint: 1.0, ceiling: 'gkp', tile_walls_to_m: 0,   tile_floor: false },
  drabuzine:   { walls_paint: 1.0, ceiling: 'gkp', tile_walls_to_m: 0,   tile_floor: false },
  rubine:      { walls_paint: 1.0, ceiling: 'gkp', tile_walls_to_m: 0,   tile_floor: false },
  katiline:    { walls_paint: 1.0, ceiling: 'gkp', tile_walls_to_m: 0,   tile_floor: true },
  skalbykla:   { walls_paint: 1.0, ceiling: 'gkp', tile_walls_to_m: 0,   tile_floor: true },
  tambūras:    { walls_paint: 0.0, ceiling: 'betonas', tile_walls_to_m: 0, tile_floor: true },
  garazas:     { walls_paint: 0.0, ceiling: 'betonas', tile_walls_to_m: 0, tile_floor: false },
  sandeliukas: { walls_paint: 1.0, ceiling: 'gkp', tile_walls_to_m: 0,   tile_floor: false },
};

function calcRoomQuantities(room) {
  const rules = ROOM_RULES[room.paskirtis] || ROOM_RULES.gyvenamoji;
  const plotas = parseFloat(room.plotas_m2) || 0;
  const H = parseFloat(room.lubu_aukstis_m) || 2.82;
  let perim = parseFloat(room.perimetras_m) || 0;
  if (perim <= 0 && plotas > 0) {
    perim = 4.18 * Math.sqrt(plotas);
  }

  const wallsGross = perim * H;
  const doorsTotal = 1 * 1.85;       // default 1 durys
  const windowsTotal = 1 * 1.40;     // default 1 langas
  const tileWallsArea = perim * rules.tile_walls_to_m;
  const wallsNet = Math.max(0, wallsGross - doorsTotal - windowsTotal - tileWallsArea);
  const wallsPaintable = wallsNet * rules.walls_paint;
  const ceilingPaintable = rules.ceiling === 'gkp' ? plotas : 0;
  const isHigh = H > 3.0;
  const dazymo = wallsPaintable + ceilingPaintable;
  const kampai = rules.walls_paint > 0 ? perim + 4 * H : 0;
  const plytSienos = tileWallsArea;
  const plytGrindys = rules.tile_floor ? plotas : 0;
  const grindjuostes = !rules.tile_floor && rules.walls_paint > 0 ? Math.max(0, perim - 0.85) : 0;

  return {
    ...room,
    perimetras_m: perim,
    walls_paintable_m2: wallsPaintable,
    ceiling_paintable_m2: ceilingPaintable,
    dazymo_plotas_m2: dazymo,
    gkp_lubu_standart_m2: !isHigh ? ceilingPaintable : 0,
    gkp_lubu_virs_3m_m2: isHigh ? ceilingPaintable : 0,
    kampai_m: kampai,
    plyteles_sienos_m2: plytSienos,
    plyteles_grindys_m2: plytGrindys,
    grindjuostes_m: grindjuostes,
  };
}

export default function RoomsGrid({ initialRooms = [], onChange, onShowOnPdf }) {
  const [rooms, setRooms] = useState(() =>
    initialRooms.map(calcRoomQuantities)
  );

  const totals = useMemo(() => {
    const t = {
      bendras_plotas_m2: 0, dazymo_plotas_m2: 0,
      gkp_lubu_standart_m2: 0, gkp_lubu_virs_3m_m2: 0,
      kampai_m: 0, plyteles_sienos_m2: 0,
      plyteles_grindys_m2: 0, grindjuostes_m: 0,
      hidroizoliacijos_vnt: 0,
    };
    rooms.forEach(r => {
      t.bendras_plotas_m2 += r.plotas_m2 || 0;
      t.dazymo_plotas_m2 += r.dazymo_plotas_m2 || 0;
      t.gkp_lubu_standart_m2 += r.gkp_lubu_standart_m2 || 0;
      t.gkp_lubu_virs_3m_m2 += r.gkp_lubu_virs_3m_m2 || 0;
      t.kampai_m += r.kampai_m || 0;
      t.plyteles_sienos_m2 += r.plyteles_sienos_m2 || 0;
      t.plyteles_grindys_m2 += r.plyteles_grindys_m2 || 0;
      t.grindjuostes_m += r.grindjuostes_m || 0;
      if (['vonia', 'wc', 'san', 'katiline', 'skalbykla'].includes(r.paskirtis)) {
        t.hidroizoliacijos_vnt += 1;
      }
    });
    return t;
  }, [rooms]);

  const handleRoomChange = (idx, newRoom) => {
    const updated = [...rooms];
    updated[idx] = calcRoomQuantities(newRoom);
    setRooms(updated);
    onChange?.(updated, totals);
  };

  const handleRemove = (idx) => {
    const updated = rooms.filter((_, i) => i !== idx);
    setRooms(updated);
    onChange?.(updated);
  };

  const handleAdd = () => {
    const nextNr = String(rooms.length + 1).padStart(2, '0');
    const newRoom = calcRoomQuantities({
      nr: nextNr,
      pavadinimas: 'Nauja patalpa',
      paskirtis: 'gyvenamoji',
      plotas_m2: 10,
      perimetras_m: 0,
      lubu_aukstis_m: 2.82,
    });
    setRooms([...rooms, newRoom]);
  };

  return (
    <div className="space-y-4">
      {/* Totals header */}
      <div className="bg-gradient-to-r from-stone-100 to-stone-50 rounded-xl p-4 border border-stone-200">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
          <div>
            <div className="text-stone-500 text-xs">Patalpų</div>
            <div className="font-bold text-lg text-stone-800">{rooms.length}</div>
          </div>
          <div>
            <div className="text-stone-500 text-xs">Bendras plotas</div>
            <div className="font-bold text-lg text-stone-800">
              {totals.bendras_plotas_m2.toFixed(1)} m²
            </div>
          </div>
          <div>
            <div className="text-stone-500 text-xs">Dažomas plotas</div>
            <div className="font-bold text-lg text-amber-700">
              {totals.dazymo_plotas_m2.toFixed(1)} m²
            </div>
          </div>
          <div>
            <div className="text-stone-500 text-xs">Dažymo kampai</div>
            <div className="font-bold text-lg text-orange-600">
              {totals.kampai_m.toFixed(1)} m
            </div>
          </div>
        </div>
      </div>

      {/* Rooms grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {rooms.map((room, idx) => (
          <RoomCard
            key={`${room.nr}-${idx}`}
            room={room}
            onChange={(updated) => handleRoomChange(idx, updated)}
            onRemove={() => handleRemove(idx)}
            onShowOnPdf={onShowOnPdf}
          />
        ))}
        {/* Add card */}
        <button onClick={handleAdd}
          className="border-2 border-dashed border-stone-300 rounded-xl p-6 hover:border-stone-400 hover:bg-stone-50 transition-colors flex flex-col items-center justify-center gap-2 text-stone-500 hover:text-stone-700">
          <Plus className="w-8 h-8" />
          <span className="text-sm font-medium">Pridėti patalpą</span>
        </button>
      </div>

      {/* Detalūs totals */}
      <div className="bg-white border border-stone-200 rounded-xl p-4">
        <h3 className="text-sm font-semibold text-stone-700 mb-3">Sumarinis kiekis</h3>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-x-6 gap-y-2 text-sm">
          {totals.gkp_lubu_standart_m2 > 0 && (
            <div className="flex justify-between">
              <span className="text-stone-600">GKP lubos (standart)</span>
              <span className="font-medium">{totals.gkp_lubu_standart_m2.toFixed(1)} m²</span>
            </div>
          )}
          {totals.gkp_lubu_virs_3m_m2 > 0 && (
            <div className="flex justify-between">
              <span className="text-stone-600">GKP lubos (virš 3m)</span>
              <span className="font-medium">{totals.gkp_lubu_virs_3m_m2.toFixed(1)} m²</span>
            </div>
          )}
          {totals.plyteles_sienos_m2 > 0 && (
            <div className="flex justify-between">
              <span className="text-stone-600">Plytelės sienose</span>
              <span className="font-medium">{totals.plyteles_sienos_m2.toFixed(1)} m²</span>
            </div>
          )}
          {totals.plyteles_grindys_m2 > 0 && (
            <div className="flex justify-between">
              <span className="text-stone-600">Plytelės grindyse</span>
              <span className="font-medium">{totals.plyteles_grindys_m2.toFixed(1)} m²</span>
            </div>
          )}
          {totals.grindjuostes_m > 0 && (
            <div className="flex justify-between">
              <span className="text-stone-600">Grindjuostės</span>
              <span className="font-medium">{totals.grindjuostes_m.toFixed(1)} m</span>
            </div>
          )}
          {totals.hidroizoliacijos_vnt > 0 && (
            <div className="flex justify-between">
              <span className="text-stone-600">Hidroizoliacija</span>
              <span className="font-medium">{totals.hidroizoliacijos_vnt} vnt</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
