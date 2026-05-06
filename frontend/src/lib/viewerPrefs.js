export const LARGE_PDF_THUMBNAIL_THRESHOLD = 20;

export function shouldCollapseThumbnails({ savedValue, totalPages }) {
  if (savedValue === '1') return true;
  if (savedValue === '0') return false;
  return (totalPages || 0) > LARGE_PDF_THUMBNAIL_THRESHOLD;
}
