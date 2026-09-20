# Patalpa vienu paspaudimu — kontūras pagal sienas ten, kur jis parodo, ir iškart perskaitytos sienos

2026-09-20. €0. Steigėjo nurodymas: „pradėk nemokamus be mano sprendimo" (sąrašo 4 punktas: kontūro taisymas
Patikroje + sienų perskaitymas po pataisymo).

## Kodėl
Po pirmo tikro Patikros bandymo (2026-09-17): „labai sunku suprasti, kur ką pataisyti galima", „perimetras kai kur
labai neteisingas". Šiandien patalpa be kontūro (H 01 — kontūras nesutapo su lentele; G 07 — „patalpos vieta plane
nerasta tiksliai — spėjama vieta pateko į patalpą 06"; patalpos, kurių vietą žinojo tik Vision dėžutė) Patikroje
rodo priežastį ir TUŠČIĄ perimetrą su įverčiu — o pataisyti ten negalima nieko, tik įrašyti skaičių ranka.
Išmatuota prieš projektuojant (kodo žemėlapis 2026-09-20):
- viršūnių tempimo redaktoriaus EmbedPDF žiūryklėje NĖRA (`PolygonEditor.jsx` — niekieno neimportuojamas Konva
  palikimas); „Taisyti kontūrą" 1 žingsnyje = rastrinis „click-to-fill", o jo rezultatas įrašomas be jokio
  perskaičiavimo ir be sienų perskaitymo; Patikros žiūryklėje jis išjungtas;
- rastrinis užliejimas ant H išsprendė 4/11 patalpų ir visas — fragmentais (baldai, štrichai); sienų masyvas tame
  pačiame lape duoda tikslius veidus;
- geometrijos juosta žmogaus pataisytą kontūrą (`corrected`) jau gerbia: jo nebeperbraižo, sumuoja jo sienų
  matmenis, skaito jo angas. Trūksta tik būdo tokį kontūrą GAUTI Patikroje.

Viršūnių tempimas — brangus (rodyklės įvykiai per pasuktus lapus, įterpimas, trynimas) ir verčia jį ranka taikyti į
sienos kraštą. Vienas paspaudimas patalpos viduje duoda tą patį tiksliau: sienų masyvo veidą.

## Ką darome
1. **`vector_rooms.outline_at(pdf, page, x_pct, y_pct, table_area_m2, m_per_pt, page_size, others_pct)`** — veidas po
   paspaudimu (durų riba 1,25 m, neradus uždaros erdvės — 1,6 m), auginamas per angas be durų link lentelės ploto
   lygiai kaip juostoje. ŽMOGUS yra autoritetas: plotas gali nesutapti su lentele (grąžinama `paklaida`), bet:
   - paspaudimas kitos patalpos patikimame kontūre → `taken` + jos nr (kontūro nepriskiriame);
   - veidas > 1,6 × lentelės ploto → `open` (sienos šios patalpos nuo gretimos neskiria — H 04/05);
   - lape nėra vektorinių sienų → `no_walls`; paspausta ne uždaroje erdvėje → `outside`.
2. **`POST /api/projects/{id}/rooms/{nr}/outline-at`** `{page, x_pct, y_pct}` — NIEKO NEIŠSAUGO. Išsaugoto projekto
   kopijoje patalpai uždeda kontūrą (`polygon_source = "corrected"`, `_konturas {page, plotas_m2, perimetras_m,
   plotas_uzrasas_m2, paklaida, saltinis: "parodyta"}`) ir paleidžia geometrijos juostą — sienų matmenys sudedami,
   angos perskaitomos, grindų danga pagal kontūrą. Grąžina TIK geometrijos raktus: `room` (šios patalpos) ir
   `kitu_angos` (kaimynų `_angos_sienose`, kad „gretima patalpa" virstų numeriu). Mastelis — iš
   `_meta.geometrija.masteliai`, kitaip iš to lapo matmenų eilučių; be mastelio — aiški klaida.
3. **Patikra**: mygtukas „Parodyti patalpą" (brėžinio skydelio antraštėje visada; perimetro fakte — kai kontūro
   nėra). Įjungus: juosta virš brėžinio „Spustelėkite patalpos VIDUJE — kontūrą nubrėšiu pagal sienas" + „Atšaukti";
   paspaudimas → užklausa → patalpos pataisa → esamas kelias `saveRoomEdit` → `land(…, {factKey: 'perimetras'})`:
   pasekmės juosta po perimetro faktu ir „Atšaukti pataisymą" (grąžina ankstesnį projektą). Nesėkmė pasakoma
   žmoniškai (kita patalpa / atvira erdvė / ne patalpa / šiame lape sienų nėra) ir pasirinkimo režimas lieka įjungtas.
4. **Jo įvestas perimetras lieka jo** (`user_override` — juosta jo neliečia); kontūras vis tiek uždedamas.

## Ko nedarome
- Viršūnių tempimo, atviros erdvės padalijimo linija (atskiras darbas — didžiausios patalpos, bet reikia braižymo),
  rastrinio atsarginio kelio (lapams be vektorinių sienų lieka 1 žingsnio „Taisyti kontūrą").
- Kiekių logikos: perimetras po pataisymo — iš sudėtų matmenų arba tuščias su įverčiu, kaip visur.

## Tikrinimas
TDD ant sintetinio plano (`two_rooms`): veidas po paspaudimu = patalpa; kita patalpa → `taken`; laukas → `outside`;
lapas be sienų → `no_walls`; bendra erdvė → `open`; API testai (nieko neišsaugo, 404 svetimam, 400 blogoms
koordinatėms, juosta sudeda sienas pataisytam kontūrui); frontend units (pataisos sudarymas, koordinačių pasukimas);
tikri brėžiniai: H 01 ir G 07 gauna kontūrą paspaudus jų vietoje; naršyklė: H 01 → „Parodyti patalpą" → paspaudimas →
kontūras, perimetro faktas, pasekmės juosta → „Atšaukti". Eval nepaliestas (juosta ta pati).
