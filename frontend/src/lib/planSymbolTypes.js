export const PLAN_SYMBOL_TYPES = [
  { id: 'rozetes', label: 'Rozetės', pageTypes: ['electrical', 'elektros'] },
  { id: 'jungikliai', label: 'Jungikliai', pageTypes: ['electrical', 'elektros'] },
  { id: 'sviestuvai', label: 'Šviestuvai', pageTypes: ['electrical', 'elektros', 'ceiling', 'lubu'] },
  { id: 'pakabinami_sviestuvai', label: 'Pakabinami', pageTypes: ['ceiling', 'lubu'] },
  { id: 'led_juostos', label: 'LED', pageTypes: ['ceiling', 'lubu'] },
  { id: 'difuzoriai', label: 'Difūzoriai', pageTypes: ['ceiling', 'lubu', 'ventilation'] },
  { id: 'klozetai', label: 'WC', pageTypes: ['plumbing', 'santechnika'] },
  { id: 'praustuvai', label: 'Praustuvai', pageTypes: ['plumbing', 'santechnika'] },
  { id: 'trapai', label: 'Trapai', pageTypes: ['plumbing', 'santechnika'] },
  { id: 'maisytuvai', label: 'Maišytuvai', pageTypes: ['plumbing', 'santechnika'] },
  { id: 'gyvatukai', label: 'Gyvatukai', pageTypes: ['plumbing', 'santechnika'] },
  { id: 'durys', label: 'Durys', pageTypes: ['floor_plan', 'aukstu', 'pertvar'] },
  { id: 'langai', label: 'Langai', pageTypes: ['floor_plan', 'aukstu', 'pertvar', 'fasadas', 'elevation'] },
];

export function getPlanSymbolTypes(pageType) {
  const normalized = String(pageType || '').toLowerCase();
  if (!normalized || normalized === 'unknown') return PLAN_SYMBOL_TYPES;
  const matches = PLAN_SYMBOL_TYPES.filter(type => (
    type.pageTypes.some(accepted => normalized.includes(accepted) || accepted.includes(normalized))
  ));
  return matches.length ? matches : PLAN_SYMBOL_TYPES;
}
