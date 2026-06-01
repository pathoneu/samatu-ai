# Annotation viewer API

Public contract for the Annotator's display layer. Today the
implementation is vanilla canvas (`AnnotationCanvas.jsx`); the
future Fabric.js implementation must honour the same imperative
methods + prop callbacks so the swap is a single-file replacement.

## File layout

| File | Responsibility |
| --- | --- |
| `pages/Annotator.jsx`               | Top-level page. Owns app state (rooms, tools, scale, calibration, walkthrough). |
| `components/annotator/PdfPage.jsx`  | Loads + renders one PDF page via `react-pdf`. Reports rendered dimensions. |
| `components/annotator/AnnotationCanvas.jsx` | Vanilla `<canvas>` overlay. Owns all drawing state (measurements, symbols, room polygons, draft cursor, snap target). Exposes an imperative ref API. |
| `components/annotator/CalibrationModal.jsx` | Modal for the contractor-override flow. |
| `components/annotator/WalkthroughOverlay.jsx` | The "Tikrinti kambarius" floating card. |

`pages/Annotator.jsx` does NOT touch the canvas directly. It either:
  - passes data to `AnnotationCanvas` as props (rooms, scale, tool), or
  - calls `canvasRef.current.<method>(…)` for imperative actions.

## `AnnotationCanvas` — props

| prop | type | notes |
| --- | --- | --- |
| `pageDims`        | `{width: number, height: number}` | Page render size from `PdfPage`. The canvas sizes to this. |
| `tool`            | `'none' \| 'calibrate' \| 'measure' \| 'place_symbol' \| 'edit_wall'` | Active tool. |
| `scale`           | `number \| null` | Calibrated mm-per-canvas-pixel. `null` until first calibration. |
| `rooms`           | `RoomGraphRoom[]` | Room polygons (in page-fraction coords) + per-room metadata. |
| `placeSymbolType` | `string \| null`  | Selected symbol type when `tool === 'place_symbol'`. |
| `selectedRoomNr`  | `string \| null`  | Highlighted room (controlled). |
| `hoveredRoomNr`   | `string \| null`  | Hover-highlighted room (controlled). |
| `editingWall`     | `{room_nr, wall_id, p1_pct, p2_pct} \| null` | When set, click sequence finishes a wall measurement. |
| `measurements`    | `Measurement[]`   | Externally-controlled measurements list. |
| `symbols`         | `Symbol[]`        | Externally-controlled symbols list. |
| `onMeasurementComplete` | `(m: Measurement) => void` | Called when the user finishes a 2-click measurement. Caller updates the canonical list. |
| `onSymbolPlaced`        | `(s: Symbol) => void` | Called when the user drops a new symbol. |
| `onSymbolDeleted`       | `(id: string) => void` | Right-click on a symbol. |
| `onCalibrationComplete` | `(scale_mm_per_px: number) => void` | After the 2-click calibrate + mm prompt. |
| `onRoomClick`           | `(roomNr: string) => void` | Magic-wand polygon click. |
| `onRoomHover`           | `(roomNr: string \| null) => void` | Polygon hover. |
| `onWallEditComplete`    | `(roomNr: string, wallId: string, length_mm: number) => void` | Wall-edit 2-click measurement done. |

## `AnnotationCanvas` — imperative ref API

`React.forwardRef` + `useImperativeHandle`. Method shape stays the same
in the Fabric.js implementation; only the body changes.

```ts
type CanvasHandle = {
  // Snap helpers — exposed for tools that need to know what would snap.
  snapPxToCorner(point: {x:number, y:number}): SnapTarget | null;

  // Direct overlay edits when a tool doesn't apply (e.g. paste a saved set).
  setMeasurements(measurements: Measurement[]): void;
  setSymbols(symbols: Symbol[]): void;

  // Visual state (read-only for the caller).
  getCanvasDims(): {width:number, height:number};

  // Imperative draw-state reset (used when changing tools / pages).
  cancelDraft(): void;

  // Hit-test for tool routing.
  hitTestRoomAtPx(point: {x:number, y:number}): string | null;
  hitTestSymbolAtPx(point: {x:number, y:number}): string | null;
};
```

## Data shapes

```ts
type Measurement = {
  id: string;
  p1_pct: {x_pct:number, y_pct:number};
  p2_pct: {x_pct:number, y_pct:number};
  length_mm: number;
};

type Symbol = {
  id: string;
  type: 'socket'|'switch'|'light_ceiling'|'vent_supply'|'water_cold'|'data_outlet';
  pos_pct: {x_pct:number, y_pct:number};
};

type RoomGraphRoom = {
  nr: string;
  name: string;
  polygon_pct: Array<{x_pct:number, y_pct:number}> | null;
  perimeter_mm: number;
  area_m2: number;
  ceiling_height_m: number;
  walls_paintable_m2: number;
  ceiling_paintable_m2: number;
  dazymo_plotas_m2: number;
};

type SnapTarget = {x:number, y:number, room_nr:string, room_name:string};
```

## Coordinates

- The component receives `pageDims` (canvas pixels) and stores ALL state
  in **pct** (0..1 fractions of the page). Pixel-space conversions
  happen at draw time. This means rendered measurements / symbols survive
  page resize and DPI changes — required for save/load.
- When the caller serialises annotations for `/api/projects/{id}/annotations`,
  it passes the same pct-coord objects this component manages.

## Tools — interaction state machine

| Tool | Click 1 | Click 2 | Result |
| --- | --- | --- | --- |
| `none` | Hit-test rooms / symbols. | — | Hover / select / drag |
| `calibrate` | Set point A. | Prompt mm; compute `scale = mm / pxDist`. | `onCalibrationComplete(scale)` |
| `measure` | Set point A (snap-aware). | Set point B (snap-aware), compute mm. | `onMeasurementComplete(m)` |
| `place_symbol` | Drop new symbol at click. | — | `onSymbolPlaced(s)` |
| `edit_wall` | Set point A on the room's wall start vertex (auto-locked). | Set point B; compute new wall length. | `onWallEditComplete(roomNr, wallId, mm)` |

## Migration path to Fabric.js

A Fabric replacement keeps the same `AnnotationCanvas` file path and
re-implements with `fabric.Canvas` internally. The imperative methods
and prop callbacks stay identical; only the rendering primitives change
(canvas paths → `fabric.Line` / `fabric.Polygon` / `fabric.Group` etc).

Drop-in checklist for the Fabric implementation:
- [ ] Mount `fabric.Canvas` on the same `<canvas>` element.
- [ ] Re-implement each draw block as Fabric object creation/update.
- [ ] Wire snap + hit-test using `fabric.Canvas.findTarget()`.
- [ ] Preserve pct coordinate convention at all serialisation boundaries.
- [ ] Run the existing `vite build` — no other code path should change.
