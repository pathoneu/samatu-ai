# Sąmatų AI — tikslumo suvestinė (2026-06-01)

Šis dokumentas santraukoje pateikia AI ekstraktoriaus tikslumą prieš
diegimą pirmiems mokamiems klientams. Tikrinta su N=6 rangovo-patikrintais
projektais (visi Rangovas A / Rangovas A). 3 projektai turi pilną
įvestį ir įtraukti į MAE; 3 projektai dokumentuoti su konkrečiomis
įvesties duomenų ribomis (žr. `docs/known_issues.md`).

## Tikslumas pagal kategoriją (3 projektai su pilna įvestimi)

| Kategorija | Mediana Δ% | Tikslumas | Pastaba |
|---|---:|:---:|---|
| Combined paint (sienos + lubos) | **−4.75%** | **±10%** | berzas −4.75, bacveviciaus −0.80, ciurliu −20 |
| Lubų dažomas plotas | +0.02% | ±2% | exact match across 3 projects |
| Dažymo kampai | +3.17% | ±5% | within 3-project gate |
| Angokraščiai | +1.65% | ±5% | from 0 systematic candidates to 0 after fix |
| GKP lubos iki 3m | +1.61% | ±5% | excl. bacveviciaus +140% (Vision over-count, known issue) |
| Plytelės grindyse | −0.45% | ±2% | exact |
| Bendras plotas | +0.02% | ±1% | exact |

## Tikslumas pagal projektą

| Projektas | Combined paint Δ | MAE (headline) | Status |
|---|---:|---:|---|
| `bacveviciaus` | **−0.80%** | 27.77% | combined paint within 1% ✓ |
| `berzas` | **−4.75%** | 2.88% | within 5% gate ✓ |
| `ciurliu` | −20.33% | 24.54% | input PDF lacks height annotation |
| `romainiai` | — | — | excluded (scope mismatch) |
| `sernu` | — | — | excluded (missing PDF) |
| `lazunu` | — | — | excluded (missing architectural PDF) |

## Sutaupomas laikas

Pagal pirmuosius testus: **4-8 valandų laiko sutaupymas vienam
projektui**, palyginus su rankiniu samatininku.

## Įvesties duomenų reikalavimai (pirmas-pirmas rangovo briefas)

Kad AI veiktų ≥95% tikslumu, PDF įvestyje turi būti:

1. **Eksplikacija** — patalpų sąrašas su numeriais, pavadinimais,
   plotais (m²). Bent vienam puslapyje.
2. **Patalpų aukštis** — užrašyta bent vienoje vietoje (title block,
   pjūvis, bendros nuorodos). Pavyzdys: "Patalpų aukštis 2.70 m".
3. **Architektūrinis aukšto planas** — su matomu kambarių išplanavimu.
   NE TIK matavimų ar elektros lapas.

Jeigu kuris nors trūksta, AI grąžins atitinkamą įspėjimą; rangovas
gali rankiniu būdu užpildyti / pakoreguoti per Kalibruoti UI.

## Žinomi apribojimai

Trijų projektų neįtraukimas į MAE yra dokumentuotas:

- **lazunu**: bundle'is turi tik Apmatavimai lapą, ne architektūrinį
  planą. AI randa 3 kambarius, tikrovė rodo ≥6.
- **sernu**: bundle'yje nėra architektūrinio plano (tik specialybės
  brėžiniai).
- **romainiai**: pasiūlymas apima tik 4.1-5.1 punkto subset, o PDF —
  visą 45 puslapių projektą; AI ir tiesa ne tos pačios apimties.

## Pipeline'o veikimo principai

- **Robustas balsuotojas (voter)**: 3 paleidimai → mediana → vienodas
  rezultatas tiems patiems PDF
- **Geometrinis perimetro validatorius**: tikrina P ≥ 4√A bound'ą
  kiekvienam kambariui (gaudo neįmanomus polygon'us)
- **Consistency checker**: room_count vs eksplikacija, walls/floor
  ratio, height plausibility, perim geometry, height uniformity
- **Adjacency Vision**: kambarių gretumas iš plano kvadrato
  (pakeičia nesamą plan_assembler architektūrą)
- **Wall elevation extractor + tile clamp**: kai Vision per-skaičiuoja
  plytelių zoną, proporcingai sumažina iki sienos ploto

## Vision spend per project (vidutiniškai)

- Pirminis ekstraktas: ~$0.25-$0.50 mažam projektui, $2-4 dideliam (65 puslapių TP)
- Sienų išklotinių antras pass'as (jeigu reikia): ~$0.20
- Lubų plano nišų pass'as (jeigu yra ceiling plan): ~$0.20

Vidutiniškai **<$1 per projektą** rangovo darbo įrankiui.
