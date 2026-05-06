/**
 * takeoffStore — Takeoff workflow state management.
 *
 * Atsako už visus brėžinio matavimo duomenis per projektą:
 * - pageScales[pageNr] = { pixels_per_meter, calibrated_at, source }
 * - polygons[] = { id, page, points, room_nr, type, created_at }
 * - actionStack[] = undo/redo istorija (max 50)
 *
 * Persistencija: localStorage per projekto ID.
 * IndexedDB ateityje, jei polygon'ų > 100.
 */

const STORAGE_KEY = (projectId) => `samatu_takeoff_${projectId}`;
export const TAKEOFF_CHANGE_EVENT = 'samatu:takeoff-change';

// ── Defaults ────────────────────────────────────────────────────────────────

const DEFAULT_TAKEOFF = {
  pageScales: {},          // { 1: {pixels_per_meter, source, calibrated_at}, ... }
  polygons: [],            // [{id, page, points, room_nr, type, label}]
  pageLines: {},           // { 1: [{x1,y1,x2,y2}], ... } — vector PDF lines for snap
  actionStack: [],         // [{type, payload, ts}]
  redoStack: [],
  meta: {
    created_at: null,
    last_modified: null,
    version: 1,
  },
};

// ── Public API ──────────────────────────────────────────────────────────────

export function loadTakeoff(projectId) {
  if (!projectId) return { ...DEFAULT_TAKEOFF };
  try {
    const raw = localStorage.getItem(STORAGE_KEY(projectId));
    if (!raw) return { ...DEFAULT_TAKEOFF };
    return { ...DEFAULT_TAKEOFF, ...JSON.parse(raw) };
  } catch {
    return { ...DEFAULT_TAKEOFF };
  }
}

export function saveTakeoff(projectId, takeoff) {
  if (!projectId) return;
  try {
    const updated = {
      ...takeoff,
      meta: {
        ...takeoff.meta,
        created_at: takeoff.meta?.created_at || new Date().toISOString(),
        last_modified: new Date().toISOString(),
      },
    };
    const storageKey = STORAGE_KEY(projectId);
    localStorage.setItem(storageKey, JSON.stringify(updated));
    emitTakeoffChange(projectId, storageKey);
  } catch (e) {
    console.error('Failed to save takeoff', e);
  }
}

export function subscribeTakeoff(projectId, callback) {
  if (typeof window === 'undefined' || !projectId || typeof callback !== 'function') {
    return () => {};
  }

  const onChange = (event) => {
    if (event?.detail?.projectId === projectId) callback(event);
  };
  const onStorage = (event) => {
    if (event.key === STORAGE_KEY(projectId)) {
      callback(new CustomEvent(TAKEOFF_CHANGE_EVENT, {
        detail: { projectId, storageKey: event.key },
      }));
    }
  };

  window.addEventListener(TAKEOFF_CHANGE_EVENT, onChange);
  window.addEventListener('storage', onStorage);
  return () => {
    window.removeEventListener(TAKEOFF_CHANGE_EVENT, onChange);
    window.removeEventListener('storage', onStorage);
  };
}

function emitTakeoffChange(projectId, storageKey) {
  if (typeof window === 'undefined' || typeof CustomEvent === 'undefined') return;
  window.dispatchEvent(new CustomEvent(TAKEOFF_CHANGE_EVENT, {
    detail: { projectId, storageKey },
  }));
}

// ── Mastelio operacijos ─────────────────────────────────────────────────────

/**
 * Nustatyti mastelį konkrečiam puslapiui.
 *
 * @param takeoff Esamas state
 * @param pageNr Puslapio nr (1-indexed)
 * @param pixelsPerMeter Pikselių per metrą skaičius
 * @param source 'manual' | 'auto' | 'inherited'
 */
export function setPageScale(takeoff, pageNr, pixelsPerMeter, source = 'manual') {
  return {
    ...takeoff,
    pageScales: {
      ...takeoff.pageScales,
      [pageNr]: {
        pixels_per_meter: pixelsPerMeter,
        source,
        calibrated_at: new Date().toISOString(),
      },
    },
  };
}

/**
 * Pritaikyti masteli VISIEMS puslapiams nuo dabartinio.
 * Įgyvendina UI „Taikyti visiems" mygtuką.
 */
export function applyScaleToAll(takeoff, pixelsPerMeter, totalPages) {
  const newScales = {};
  for (let p = 1; p <= totalPages; p++) {
    newScales[p] = {
      pixels_per_meter: pixelsPerMeter,
      source: 'inherited',
      calibrated_at: new Date().toISOString(),
    };
  }
  return { ...takeoff, pageScales: newScales };
}

export function getPageScale(takeoff, pageNr) {
  return takeoff.pageScales?.[pageNr] || null;
}

/**
 * Sanity check'as — ar mastelis duoda logiškus plotus.
 * Grąžina warning'ų sąrašą.
 */
export function validateScaleSanity(takeoff, pageNr, polygons) {
  const scale = getPageScale(takeoff, pageNr);
  if (!scale) return [];

  const pagePolygons = polygons.filter(p => p.page === pageNr);
  const warnings = [];

  for (const poly of pagePolygons) {
    const area = polygonAreaM2(poly.points, scale.pixels_per_meter);
    if (area > 200) {
      warnings.push({
        level: 'WARNING',
        polygon_id: poly.id,
        message: `${poly.label || 'Patalpa'}: ${area.toFixed(1)} m² — neįprastai didelis. Patikrink mastelį.`,
      });
    } else if (area < 0.5 && area > 0) {
      warnings.push({
        level: 'WARNING',
        polygon_id: poly.id,
        message: `${poly.label || 'Patalpa'}: ${area.toFixed(2)} m² — neįprastai mažas. Patikrink mastelį.`,
      });
    }
  }
  return warnings;
}

// ── Polygon operacijos ──────────────────────────────────────────────────────

let _polygonIdCounter = 0;
function genPolygonId() {
  return `pg_${Date.now()}_${++_polygonIdCounter}`;
}

export function addPolygon(takeoff, polygon) {
  const newPoly = {
    id: polygon.id || genPolygonId(),
    page: polygon.page,
    points: polygon.points,        // [{x, y}, ...] PDF unitais
    room_nr: polygon.room_nr || null,
    type: polygon.type || 'room',  // 'room' | 'count' | 'note'
    label: polygon.label || '',
    color: polygon.color || null,  // null = auto pagal type
    confidence: polygon.confidence || 'high',  // AI prediction'ams
    source: polygon.source || 'manual',         // 'manual' | 'ai'
    created_at: new Date().toISOString(),
  };
  return {
    ...takeoff,
    polygons: [...takeoff.polygons, newPoly],
    actionStack: pushAction(takeoff, { type: 'add_polygon', payload: newPoly }),
    redoStack: [],  // naujas action išvalo redo
  };
}

export function updatePolygon(takeoff, polygonId, updates) {
  const before = takeoff.polygons.find(p => p.id === polygonId);
  if (!before) return takeoff;
  return {
    ...takeoff,
    polygons: takeoff.polygons.map(p =>
      p.id === polygonId ? { ...p, ...updates } : p,
    ),
    actionStack: pushAction(takeoff, {
      type: 'update_polygon',
      payload: { polygonId, before, after: { ...before, ...updates } },
    }),
    redoStack: [],
  };
}

export function removePolygon(takeoff, polygonId) {
  const removed = takeoff.polygons.find(p => p.id === polygonId);
  if (!removed) return takeoff;
  return {
    ...takeoff,
    polygons: takeoff.polygons.filter(p => p.id !== polygonId),
    actionStack: pushAction(takeoff, { type: 'remove_polygon', payload: removed }),
    redoStack: [],
  };
}

export function getPolygonsForPage(takeoff, pageNr) {
  return (takeoff.polygons || []).filter(p => p.page === pageNr);
}

export function getPolygonForRoom(takeoff, roomNr) {
  return (takeoff.polygons || []).find(p => p.room_nr === roomNr);
}

// ── Geometry helpers ────────────────────────────────────────────────────────

/**
 * Polygon plotas (Shoelace formule) → m²
 *
 * @param points [{x, y}, ...] pikseliais (PDF unit'ais)
 * @param pixelsPerMeter mastelio koeficientas
 */
export function polygonAreaM2(points, pixelsPerMeter) {
  if (!points || points.length < 3 || !pixelsPerMeter) return 0;
  let sumPx = 0;
  for (let i = 0; i < points.length; i++) {
    const j = (i + 1) % points.length;
    sumPx += points[i].x * points[j].y;
    sumPx -= points[j].x * points[i].y;
  }
  const areaPxSq = Math.abs(sumPx) / 2;
  const areaM2 = areaPxSq / (pixelsPerMeter * pixelsPerMeter);
  return Math.round(areaM2 * 100) / 100;
}

/**
 * Polygon perimetras → m
 */
export function polygonPerimeterM(points, pixelsPerMeter) {
  if (!points || points.length < 2 || !pixelsPerMeter) return 0;
  let totalPx = 0;
  for (let i = 0; i < points.length; i++) {
    const j = (i + 1) % points.length;
    const dx = points[j].x - points[i].x;
    const dy = points[j].y - points[i].y;
    totalPx += Math.sqrt(dx * dx + dy * dy);
  }
  const perimM = totalPx / pixelsPerMeter;
  return Math.round(perimM * 100) / 100;
}

/**
 * Atstumas tarp 2 taškų pikseliais → m
 */
export function distanceM(p1, p2, pixelsPerMeter) {
  if (!pixelsPerMeter) return 0;
  const dx = p2.x - p1.x;
  const dy = p2.y - p1.y;
  return Math.sqrt(dx * dx + dy * dy) / pixelsPerMeter;
}

/**
 * Snap point'as į artimiausią vector liniją per puslapį.
 * Grąžina arba originalų point'ą (jei nėra arti linijos), arba snap'inta.
 *
 * @param point {x, y}
 * @param lines [{x1, y1, x2, y2}, ...]
 * @param snapRadius pikseliais (default 8)
 */
export function snapToLines(point, lines, snapRadius = 8) {
  if (!lines || lines.length === 0) return { ...point, snapped: false };

  let closestPoint = null;
  let closestDist = snapRadius;

  for (const line of lines) {
    // Atstumas nuo point'o iki linijos segmento
    const proj = projectPointOnSegment(point, line);
    const d = Math.sqrt((proj.x - point.x) ** 2 + (proj.y - point.y) ** 2);
    if (d < closestDist) {
      closestDist = d;
      closestPoint = proj;
    }
  }

  if (closestPoint) {
    return { x: closestPoint.x, y: closestPoint.y, snapped: true };
  }
  return { ...point, snapped: false };
}

function projectPointOnSegment(point, line) {
  const dx = line.x2 - line.x1;
  const dy = line.y2 - line.y1;
  const lenSq = dx * dx + dy * dy;
  if (lenSq === 0) return { x: line.x1, y: line.y1 };
  const t = Math.max(0, Math.min(1,
    ((point.x - line.x1) * dx + (point.y - line.y1) * dy) / lenSq,
  ));
  return { x: line.x1 + t * dx, y: line.y1 + t * dy };
}

// ── Undo/Redo ───────────────────────────────────────────────────────────────

const MAX_ACTIONS = 50;

function pushAction(takeoff, action) {
  const stack = [...(takeoff.actionStack || []), { ...action, ts: Date.now() }];
  return stack.slice(-MAX_ACTIONS);
}

export function undo(takeoff) {
  const stack = takeoff.actionStack || [];
  if (stack.length === 0) return takeoff;
  const last = stack[stack.length - 1];
  let newPolygons = takeoff.polygons;

  if (last.type === 'add_polygon') {
    newPolygons = newPolygons.filter(p => p.id !== last.payload.id);
  } else if (last.type === 'remove_polygon') {
    newPolygons = [...newPolygons, last.payload];
  } else if (last.type === 'update_polygon') {
    newPolygons = newPolygons.map(p =>
      p.id === last.payload.polygonId ? last.payload.before : p,
    );
  }

  return {
    ...takeoff,
    polygons: newPolygons,
    actionStack: stack.slice(0, -1),
    redoStack: [...(takeoff.redoStack || []), last],
  };
}

export function redo(takeoff) {
  const stack = takeoff.redoStack || [];
  if (stack.length === 0) return takeoff;
  const last = stack[stack.length - 1];
  let newPolygons = takeoff.polygons;

  if (last.type === 'add_polygon') {
    newPolygons = [...newPolygons, last.payload];
  } else if (last.type === 'remove_polygon') {
    newPolygons = newPolygons.filter(p => p.id !== last.payload.id);
  } else if (last.type === 'update_polygon') {
    newPolygons = newPolygons.map(p =>
      p.id === last.payload.polygonId ? last.payload.after : p,
    );
  }

  return {
    ...takeoff,
    polygons: newPolygons,
    actionStack: [...(takeoff.actionStack || []), last],
    redoStack: stack.slice(0, -1),
  };
}

export function canUndo(takeoff) {
  return (takeoff.actionStack || []).length > 0;
}

export function canRedo(takeoff) {
  return (takeoff.redoStack || []).length > 0;
}
