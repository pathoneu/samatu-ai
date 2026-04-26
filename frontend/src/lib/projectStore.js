import { DEMO_PROJECTS } from '../demoData';

const PROJECTS_KEY = 'samatu_projects';
const PRICE_LISTS_KEY = 'samatu_price_lists';
const SETTINGS_KEY = 'samatu_settings';

// Seed demo data on first load (empty localStorage)
if (!localStorage.getItem(PROJECTS_KEY)) {
  localStorage.setItem(PROJECTS_KEY, JSON.stringify(DEMO_PROJECTS));
}

// ── Projects ──────────────────────────────────────────────────────────────────

export function getProjects() {
  try {
    return JSON.parse(localStorage.getItem(PROJECTS_KEY) || '[]');
  } catch {
    return [];
  }
}

export function getProject(id) {
  return getProjects().find(p => p.id === id) || null;
}

export function createProject(data) {
  const project = {
    ...data,
    id: crypto.randomUUID(),
    created_date: new Date().toISOString(),
  };
  const projects = getProjects();
  projects.unshift(project); // newest first
  localStorage.setItem(PROJECTS_KEY, JSON.stringify(projects));
  return project;
}

export function updateProject(id, updates) {
  const projects = getProjects();
  const idx = projects.findIndex(p => p.id === id);
  if (idx < 0) return null;
  projects[idx] = { ...projects[idx], ...updates };
  localStorage.setItem(PROJECTS_KEY, JSON.stringify(projects));
  return projects[idx];
}

export function deleteProject(id) {
  const projects = getProjects().filter(p => p.id !== id);
  localStorage.setItem(PROJECTS_KEY, JSON.stringify(projects));
}

// ── Price Lists ───────────────────────────────────────────────────────────────

export function getPriceLists() {
  try {
    return JSON.parse(localStorage.getItem(PRICE_LISTS_KEY) || '[]');
  } catch {
    return [];
  }
}

export function createPriceList(data) {
  const pl = {
    ...data,
    id: crypto.randomUUID(),
    created_date: new Date().toISOString(),
  };
  const lists = getPriceLists();
  lists.unshift(pl);
  localStorage.setItem(PRICE_LISTS_KEY, JSON.stringify(lists));
  return pl;
}

export function deletePriceList(id) {
  const lists = getPriceLists().filter(p => p.id !== id);
  localStorage.setItem(PRICE_LISTS_KEY, JSON.stringify(lists));
}

// ── Settings ──────────────────────────────────────────────────────────────────

export function getSettings() {
  try {
    return JSON.parse(localStorage.getItem(SETTINGS_KEY) || '{}');
  } catch {
    return {};
  }
}

export function saveSettings(settings) {
  localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
  return settings;
}
