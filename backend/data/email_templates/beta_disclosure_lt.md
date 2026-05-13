Tema: Sąmatų AI beta: svarbus pranešimas apie kiekių patikrinimą

Sveiki,

Ačiū, kad bandote Sąmatų AI beta versiją.

2026-05-10 identifikavome kelias kiekio skaičiavimo klaidas, kurios galėjo paveikti:

- dažų / grunto kiekius (kai kurioms patalpoms frontend'as rodė `NaN`),
- angokraščių (langų / durų apvadų) skaičiavimą,
- hidroizoliacijos skaičiavimą (anksčiau skaičiavome kambarių vienetus, ne m²),
- bendrų sienų perimetro skaičiavimą tarp gretimų patalpų.

Kol eilutė nėra pažymėta „Patikrinta“, rezultatą laikykite **pagalbiniu juodraščiu**, o ne galutine sąmata. Prieš teikdami kainos pasiūlymą patikrinkite kiekius — ypač:

1. Langų plotai ir angokraščiai (patikrinkite, ar visi langai ir durys įtraukti).
2. Hidroizoliacija drėgnose patalpose (turi būti m², ne vienetai).
3. Grindjuostės bendroms sienoms tarp dviejų patalpų.
4. Paslėptų durų staktos (jei projektas naudoja paslėptas duris).

Per artimiausias 8 savaites:

- perkeliame visas formules į backend (vienas šaltinis tarp UI ir skaičiavimo),
- pridedame click-to-correct UI (galėsite koreguoti AI rezultatus tiesiogiai ant brėžinio),
- pridedame audito eksportą + F2/F3 Sistela formatą,
- bendradarbiausime su LT samatininkais, kad pasiektume EUR-svorinį tikslumą ≤15 % top-5 pozicijoms.

Jei turite klausimų ar pastabų, atrašykite į šį laišką.

Pagarbiai,
Sąmatų AI komanda
