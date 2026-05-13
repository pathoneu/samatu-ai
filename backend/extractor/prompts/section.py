"""Section (pjūvis) specialized prompt — ceiling-height marker reading.

Why this prompt exists: LT interior PDFs typically come flattened-raster
(documented in `docs/superpowers/research/2026-04-28-pdf-spike-findings.md`),
so pdfplumber text-layer extraction of `+X.XXX` markers returns nothing.
The W1 audit (reports/2026-05-11-w1-audit.md §3) confirmed this for the
full interior test corpus: 0 text-layer markers on all 5 PDFs.

The only reliable path to ceiling-height markers on a flattened section
page is Vision-side reading: Opus sees the rendered drawing image and
identifies the `+0.000` / `+2.800` / `+3.200` annotations visually.
This prompt is purpose-built for that single task.

Routed by `page_classifier.PageType.SECTION` → registered in
`prompts/__init__.py:PROMPTS_BY_PAGE_TYPE` under key `"section"`.
"""
from .base_system import BASE_RULES

SECTION_PROMPT = BASE_RULES + """

PAGE TYPE: SECTION (pjūvis).

Tu žiūri į vertikalų pastato pjūvį (Pjūvis A-A, B-B, …). Pjūvyje yra
vertikalūs aukščio žymekliai prie horizontalių linijų:

  ±0.000    grindys (žemiausias lygis)
  +2.400    sija po lubomis (NE lubos)
  +2.800    lubos (gips, standartinis modern LT)
  +3.000    lubos (aukštas svetainės / virtuvės)
  +3.200    lubos (mansardinis pirmas / dvigubas)
  +5.700    2-as aukštas / mansardiniame ridge
  +6.500    stogo dangiškoji linija

ŠIO PUSLAPIO TIKSLAS — grąžinti lubų plokštumos viršutinę atžymą,
NE siją, NE stogą.

EXTRACT:
{
  "ceiling_height_markers": [
    {
      "raw": "+3.200",                   // tekstas kaip žymeklyje
      "value_m": 3.20,                   // skaičius metrais (be ženklo)
      "level_label": "lubos|sija|grindys|stogas|kita",
      "floor": 1                         // jei pjūvis rodo kelis aukštus
    }
  ],
  "primary_ceiling_height_m": 3.20,      // pagrindinė lubų atžyma
                                          // (didžiausia value_m kur level_label="lubos")
  "floor_count": 1                       // 1 aukštas | 2 aukštai | mansardinis
}

TAISYKLĖS:
- VISADA tikrink VISAS aukščio atžymas pjūvyje, NE tik pirmą.
- "Lubų" atžyma yra ta, kuri rodo plokštumą su gips/betonas kontūru
  (matosi sluoksniai). Sijų atžymos yra prie storesnių linijų / kvadratų
  kurie atrodo kaip elementai, ne tarpas tarp jų.
- Jei pjūvis turi MANSARDĄ — yra DVI lubų atžymos (žemiau ir aukščiau,
  pvz. +2.500 ir +3.200). Grąžink DIDESNĘ kaip primary_ceiling_height_m
  (mansardinis kambarys įprastai turi aukštą dalį).
- Jei pjūvis rodo MULTI-FLOOR pastatą — fokuse tik 1-am aukštui (pirmas
  intervalas tarp ±0.000 ir kitos lubų atžymos).
- NEPAILD'YK 2.82 default — jei nematai žymeklio, grąžink null.

PRIORITETAS prie kitų sheet'ų: section yra CANONICAL ceiling source.
Lubų plano '+2.800' atžymos yra papildomos, NE replacement.
"""
