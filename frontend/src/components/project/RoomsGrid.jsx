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
  // LT STR defaults — must stay in sync with backend extractor/universal_rules.py
  // (UNIVERSAL_RULES dict). NRM2 §29: only deduct openings ≥ 1.0 m².
  const DEFAULT_DOOR_M2 = 1.85;     // 0.9 × 2.05 m (LT STR 2.02.09)
  const DEFAULT_WINDOW_M2 = 1.80;   // 1.2 × 1.5 m (LT STR standard)
  const doorsTotal = 1 * DEFAULT_DOOR_M2;
  const windowsTotal = 1 * DEFAULT_WINDOW_M2;
  const tileWallsArea = perim * rules.tile_walls_to_m;
  const wallsNet = Math.max(0, wallsGross - doorsTotal - windowsTotal - tileWallsArea);
  const wallsPaintable = wallsNet * rules.walls_paint;
  const ceilingPaintable = rules.ceiling === 'gkp' ? plotas : 0;
  const isHigh = H > 3.0;
  const dazymo = wallsPaintable + ceilingPaintable;
  const kampai = rules.walls_paint > 0 ? perim + 4 * H : 0;
  const plytSienos = tileWallsArea;
  const plytGrindys = rules.tile_floor ? plotas : 0;
  // NRM2 §27: baseboard = (perimetras − Σ door widths) × 1.10 (10% waste)
  const grindjuostes = !rules.tile_floor && rules.walls_paint > 0
    ? Math.max(0, perim - 0.85) * 1.10
    : 0;

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

export default function RoomsGrid({ initialRooms = [], onChange, onShowOnPdf, project, onJumpToPage }) {
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
      <div className="bg-gradient-to-r from-muted to-muted/50 rounded-xl p-4 border border-border">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
          <div>
            <div className="text-muted-foreground text-xs">Patalpų</div>
            <div className="font-bold text-lg text-foreground">{rooms.length}</div>
          </div>
          <div>
            <div className="text-muted-foreground text-xs">Bendras plotas</div>
            <div className="font-bold text-lg text-foreground">
              {totals.bendras_plotas_m2.toFixed(2)} m²
            </div>
          </div>
          <div>
            <div className="text-muted-foreground text-xs">Dažomas plotas</div>
            <div className="font-bold text-lg text-amber-400">
              {totals.dazymo_plotas_m2.toFixed(2)} m²
            </div>
          </div>
          <div>
            <div className="text-muted-foreground text-xs">Dažymo kampai</div>
            <div className="font-bold text-lg text-orange-400">
              {totals.kampai_m.toFixed(2)} m
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
            project={project}
            onChange={(updated) => handleRoomChange(idx, updated)}
            onRemove={() => handleRemove(idx)}
            onShowOnPdf={onShowOnPdf}
            onJumpToPage={onJumpToPage}
          />
        ))}
        {/* Add card */}
        <button onClick={handleAdd}
          className="border-2 border-dashed border-border rounded-xl p-6 hover:border-primary/40 hover:bg-muted/60 transition-colors flex flex-col items-center justify-center gap-2 text-muted-foreground hover:text-foreground">
          <Plus className="w-8 h-8" />
          <span className="text-sm font-medium">Pridėti patalpą</span>
        </button>
      </div>

      {/* Detalūs totals */}
      <div className="bg-card border border-border rounded-xl p-4">
        <h3 className="text-sm font-semibold text-foreground mb-3">Sumarinis kiekis</h3>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-x-6 gap-y-2 text-sm">
          {totals.gkp_lubu_standart_m2 > 0 && (
            <div className="flex justify-between">
              <span className="text-muted-foreground">GKP lubos (standart)</span>
              <span className="font-medium">{totals.gkp_lubu_standart_m2.toFixed(2)} m²</span>
            </div>
          )}
          {totals.gkp_lubu_virs_3m_m2 > 0 && (
            <div className="flex justify-between">
              <span className="text-muted-foreground">GKP lubos (virš 3m)</span>
              <span className="font-medium">{totals.gkp_lubu_virs_3m_m2.toFixed(2)} m²</span>
            </div>
          )}
          {totals.plyteles_sienos_m2 > 0 && (
            <div className="flex justify-between">
              <span className="text-muted-foreground">Plytelės sienose</span>
              <span className="font-medium">{totals.plyteles_sienos_m2.toFixed(2)} m²</span>
            </div>
          )}
          {totals.plyteles_grindys_m2 > 0 && (
            <div className="flex justify-between">
              <span className="text-muted-foreground">Plytelės grindyse</span>
              <span className="font-medium">{totals.plyteles_grindys_m2.toFixed(2)} m²</span>
            </div>
          )}
          {totals.grindjuostes_m > 0 && (
            <div className="flex justify-between">
              <span className="text-muted-foreground">Grindjuostės</span>
              <span className="font-medium">{totals.grindjuostes_m.toFixed(2)} m</span>
            </div>
          )}
          {totals.hidroizoliacijos_vnt > 0 && (
            <div className="flex justify-between">
              <span className="text-muted-foreground">Hidroizoliacija</span>
              <span className="font-medium">{totals.hidroizoliacijos_vnt} vnt</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
