# Geometrijos ribos — kas iš sąrašo liko ir kas padaryta (triženkliai numeriai, įstriži matmenys, siena per duris)

2026-09-21. €0. Steigėjo nurodymas: „tai dabaik viską, kas liko iš sąrašo, be manęs ir nemokamai". Dizainas, matavimai
ir žurnalas — viename lape: trys nedideli, vienas nuo kito nepriklausomi pakeitimai juostoje; kiekvienas pirma
IŠMATUOTAS ant tikrų brėžinių, tada padarytas per testus. (Atviros erdvės dalijimas — atskirame plane.)

## Ką parodė apklausa (visi šeši korpuso brėžiniai, 2026-09-21)
Kodėl patalpa negauna kontūro arba iš užrašų sudėto perimetro:
- **A**: 10 iš 11 patalpų neturėjo JOKIOS vietos plane — numeriai „101…111" triženkliai ir parašyti 11 pt šriftu,
  o ieškiklis ėmė tik 1–2 skaitmenis ≤ 6,5 pt.
- **B**: visos 15 patalpų pririštos prie 1 lapo (vizualizacijos — „sienų masyvas" ten baldai ir 3D vaizdai). Tikras
  planas (2 psl.) turi tvarkingas vektorines sienas, bet patalpų jame niekas nežymi: nei numerių, nei pavadinimų —
  tik baldų pozicijų numeriai („08", „17", kai kurie po 2–4 kartus) ir lentelė šone. Čia padeda tik „Parodyti
  patalpą" (žmogus parodo). **„Brūkšniais braižytų pertvarų" atvejo korpuse NĖRA** — tokio skaitytuvo nekūrėme.
- **C, D**: be vektorinių sienų (rastras) — juosta nieko nedaro, kaip ir turi.
- **H**: 09 — „2 iš 5 sienų be matmens (1 įstriža)"; 05 po padalijimo — tas pats; 03 — 2 iš 8.
- **G**: 06 — 1 iš 6; 01 — 3 iš 10.

## 1. Triženkliai patalpų numeriai (`room_locator`)
Ieškomas PAČIOS patalpos numeris, kai jis 3–4 skaitmenų (tikslus žodis, ≤ 14 pt), su tomis pačiomis apsaugomis (ne
lentelės stulpelis, neliečia kito skaičiaus, ne antraštės blokas). Trumpų numerių mažo ženkliuko taisyklė
NEATLAISVINTA — išmatuota ir atmesta: H prarado du kontūrus, o B baldų numeriai tapo patalpomis.
Rezultatas: A — 1 → 11 kontūrų, angos visoms patalpoms; eval antraštė 9,83 % (A 2,78 → 2,81 %), A eilutės ±10 %
35,8 → 37,7 % (€ 27,9 → 47,5 %), korpusas 24,3 → 24,8 %.

## 2. Įstriži matmenys (`plan_dimensions`, `dimension_sum`)
H sienų dažymo plane „2060" (34°) ir „1526" (44°) parašyti išilgai savo plonų įstrižų linijų. Skaitomos skaitmenų
eilės, kurių kampas > 6° nuo kiekvieno ketvirčio; eilutė priimama TIK su savo linija (lygiagreti ±4°, ≤ 14 pt nuo
teksto, ilgis lapo masteliu = reikšmė ±3 %) — ta pati taisyklė kaip horizontalioms. Įstrižą sieną nusako viena
eilutė, kurios linijos galai stovi ties sienos kampais ir kurios reikšmė = sienos ilgis.

## 3. Siena, užrašyta gabalais abipus durų (`dimension_sum`)
Dizaineris durų pločio į sienos grandinę nerašo: H 09 — „660" | durys 1,40 m | „1538" = 3,60 m. Eilė su skylėmis
nusako sieną, kai kiekviena skylė yra (a) pačios patalpos anga toje sienoje tiksliai skylės vietoje (plotis iš
sienų masyvo) arba (b) < 0,4 m stulpelis, kurio niekas nematavo (≤ 0,5 m vienoje sienoje, iš kontūro — kaip trumpos
kraštinės); visuma turi sutapti su sienos ilgiu. Kas NE perskaityta — pasakoma: sakinyje „1,40 (durų anga)" ir
„Durų angų pločio (1,40 m) planas neužrašo — paėmiau jį iš sienų brėžinio", brėžinyje — skliaustuose.
Sąžiningumo riba: stulpelių užpildymas iš kontūro daro sienos sumos patikrą beveik savaime teisingą, todėl jis
ribojamas (0,4 m / 0,5 m) ir visada rodomas (`is_konturo_m`).

## Rezultatas ant tikrų brėžinių
- H: iš užrašų sudėti perimetrai 4 → 5 (09: 16,01 m — buvo įvertis); 03 liko 1 siena iš 8.
- G (fikstūra): 1 → 2 (06: 0,12 m stulpelis + „0.800"); demo-G 06 — 12,14 m sudėta.
- A: 11 kontūrų; perimetrai lieka įverčiai (A sienų matmenų patalpose nerašo; 9 patalpų kontūro plotas 8–12 %
  mažesnis už lentelę — juosta tai sako ir sienų nesumuoja).
- Eval po visko: in-sample 9,83 %, OOS 7,06 %; eilutės ±10 %: A 37,7 %, G 20,0 %, H 29,2 %, korpusas 24,8 %.
- Vartai dienos pabaigoje: backend 3690 passed / 3 skipped; frontend 750/750; eslint 0 klaidų.
- `LANE_VERSION` 5 → 7: išsaugoti projektai visa tai gauna per „Perskaityti nemokamai".
- Kaina: įstrižų eilučių skaitymas B rinkiniui prideda ~5 s (11 s vietoj 6 s) — skaitomi tik lapai su masteliu IR
  įstrižais skaičiais.

## Ko nedarėme
- Brūkšniais braižytų pertvarų (korpuse nėra atvejo, kuriam tai padėtų).
- Patalpų vietos pagal PAVADINIMĄ (B plane pavadinimų nėra; ten — „Parodyti patalpą").
- H 03 paskutinės sienos (jos ilgis užrašytas tik kaimynų pusėse, gabalais per kelias patalpas).
