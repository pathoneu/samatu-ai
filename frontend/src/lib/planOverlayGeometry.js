function validRect(rect) {
  return rect &&
    Number.isFinite(rect.left) &&
    Number.isFinite(rect.top) &&
    Number.isFinite(rect.width) &&
    Number.isFinite(rect.height) &&
    rect.width > 0 &&
    rect.height > 0;
}

export function getBboxPctRect(bbox, renderedSize) {
  if (!bbox || !renderedSize?.width || !renderedSize?.height) return null;
  const rect = {
    left: bbox.x * renderedSize.width,
    top: bbox.y * renderedSize.height,
    width: bbox.w * renderedSize.width,
    height: bbox.h * renderedSize.height,
  };
  return validRect(rect) ? rect : null;
}

export function getEksplikacijaRect(bbox, {
  pageWidthPdf,
  pageHeightPdf,
  renderedWidth,
  renderedHeight,
}) {
  if (!Array.isArray(bbox) || bbox.length !== 4 || !pageWidthPdf || !pageHeightPdf || !renderedWidth || !renderedHeight) {
    return null;
  }
  const [x1, y1, x2, y2] = bbox;
  const rect = {
    left: (x1 / pageWidthPdf) * renderedWidth,
    top: (y1 / pageHeightPdf) * renderedHeight,
    width: ((x2 - x1) / pageWidthPdf) * renderedWidth,
    height: ((y2 - y1) / pageHeightPdf) * renderedHeight,
  };
  return validRect(rect) ? rect : null;
}

export function getPolygonPdfPoints(polygon, {
  pageWidthPdf,
  pageHeightPdf,
  renderedWidth,
  renderedHeight,
}) {
  if (
    !Array.isArray(polygon) ||
    polygon.length < 3 ||
    !pageWidthPdf ||
    !pageHeightPdf ||
    !renderedWidth ||
    !renderedHeight
  ) {
    return null;
  }

  const points = polygon.map((point) => {
    if (!Array.isArray(point) || point.length < 2) return null;
    const [x, y] = point;
    if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
    return [
      (x / pageWidthPdf) * renderedWidth,
      (y / pageHeightPdf) * renderedHeight,
    ];
  });

  return points.every(Boolean) ? points : null;
}

export function getPolygonPdfRect(polygon, options) {
  const points = getPolygonPdfPoints(polygon, options);
  if (!points) return null;
  const xs = points.map(point => point[0]);
  const ys = points.map(point => point[1]);
  const rect = {
    left: Math.min(...xs),
    top: Math.min(...ys),
    width: Math.max(...xs) - Math.min(...xs),
    height: Math.max(...ys) - Math.min(...ys),
  };
  return validRect(rect) ? rect : null;
}

export function getTextLabelRect(textItem, { roomNr = null, padding = 10 } = {}) {
  if (!textItem) return null;
  const text = String(textItem.str || '').trim();
  if (!text) return null;
  if (roomNr != null && text !== String(roomNr).trim()) return null;
  if (!Number.isFinite(textItem.x) || !Number.isFinite(textItem.y) || textItem.width <= 0 || textItem.height <= 0) return null;

  const rect = {
    left: textItem.x - padding,
    top: textItem.y - padding,
    width: textItem.width + padding * 2,
    height: textItem.height + padding * 2,
  };
  return validRect(rect) ? rect : null;
}

export function getFocusedRoomRect({
  room,
  page,
  eksplikacijaPage,
  renderedSize,
  pdfSize,
}) {
  if (!room || !renderedSize?.width || !renderedSize?.height) return null;
  const roomPage = room.page_nr ?? room.puslapio_nr;
  if (roomPage === page && Array.isArray(room.polygon_pdf)) {
    const rect = getPolygonPdfRect(room.polygon_pdf, {
      pageWidthPdf: room.page_width_pdf || room.pdf_page_width || pdfSize?.width,
      pageHeightPdf: room.page_height_pdf || room.pdf_page_height || pdfSize?.height,
      renderedWidth: renderedSize.width,
      renderedHeight: renderedSize.height,
    });
    if (rect) return { type: 'room', ...rect };
  }
  if (eksplikacijaPage === page && Array.isArray(room.eksplikacija_row_bbox)) {
    const rect = getEksplikacijaRect(room.eksplikacija_row_bbox, {
      pageWidthPdf: room.eksplikacija_page_width_pdf || room.page_width_pdf || pdfSize?.width,
      pageHeightPdf: room.eksplikacija_page_height_pdf || room.page_height_pdf || pdfSize?.height,
      renderedWidth: renderedSize.width,
      renderedHeight: renderedSize.height,
    });
    return rect ? { type: 'eksplikacija', ...rect } : null;
  }
  return null;
}
