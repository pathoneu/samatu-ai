// frontend/src/lib/categoryColor.js
/**
 * Sprint 3: maps `skyrius_enum` to category accent color.
 *
 * Decision (spec §3 locked): single brand-blue across all categories.
 * Module exists to keep room for future per-category palette without
 * touching consumer components. For now: every category returns the
 * same primary blue.
 */

export const BRAND_PRIMARY = '#2a6fb5'; // from index.css --primary 211 62% 44%

export function categoryAccent(_skyrius) {
  return BRAND_PRIMARY;
}
