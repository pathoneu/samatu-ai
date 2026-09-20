# Atviros erdvės dalijimas — dvi patalpos be sienos tarp jų gauna savo kontūrus ir savo sienas

2026-09-21. €0. Steigėjo nurodymas: „tai dabaik viską, kas liko iš sąrašo, be manęs ir nemokamai".

## Kodėl
Virtuvė su svetaine — dažniausiai DIDŽIAUSIOS buto patalpos — brėžinyje neatskirtos siena. Geometrijos juosta tai
pasako sąžiningai („atvira erdvė su 05: sienos šių patalpų neskiria") ir kiekvienai patalpai duoda ĮVERTĮ: bendros
erdvės sienų ilgį, padalytą pagal plotą (H: 37,77 m → 16,08 + 21,69 m). Patikroje tai dvi tuščios perimetro
eilutės be jokio būdo jas sutvarkyti, o tų patalpų sienų angos neskaitomos (nėra savo kontūro).
Ribą tarp tokių patalpų žino tik žmogus. Vienos linijos užtenka.

## Ką darome
1. **`vector_rooms.split_space(pdf, page, a_pct, b_pct, seats_pct, table_areas, m_per_pt, page_size, others_pct)`** —
   sienų masyvo veidas, kuriame stovi abiejų patalpų numeriai, perkerpamas tiese per du parodytus taškus (pratęsta
   iki veido krašto). Rezultatas `ok` tik kai gaunamos lygiai dvi dalys ir kiekvienoje stovi lygiai viena patalpa:
   kiekvienai — `polygon_pct`, `plotas_m2`, `paklaida` (su lentele — tik palyginimui), `menamos` (kontūro kraštinės,
   gulinčios ant ribos: ten sienos NĖRA) ir `perimetras_m` = tik tikrų sienų ilgis.
   Kitaip: `bad_line` (riba neatskiria numerių / kerta erdvę ne į dvi dalis), `not_shared` (taškai ne bendroje
   erdvėje), `too_many` (erdvėje daugiau nei dvi patalpos — v1 nepalaiko), `no_walls`.
2. **`dimension_sum`**: kraštinė, gulinti ant `_konturas.menamos`, nėra siena — nei sumoje, nei kontrolėje, nei
   „N iš M sienų be matmens" skaičiuje.
3. **`POST /api/projects/{id}/rooms/{nr}/split-space`** `{page, a: {x_pct, y_pct}, b: {…}}` — NIEKO NEIŠSAUGO (kaip
   `outline-at`): kopijoje abiem patalpoms uždeda kontūrus (`corrected`, `_konturas.saltinis = "padalinta"`,
   `menamos`), nuima `_atvira_erdve`, paleidžia juostą; grąžina abiejų patalpų geometrijos raktus + kaimynų angas.
4. **Patikra**: atviros erdvės nariui — „Padalinti erdvę" (skydelio antraštėje ir perimetro fakte). Du paspaudimai
   brėžinyje (ribos pradžia ir pabaiga; pirmas taškas pažymimas), tada esamas kelias: `saveRoomEdit` → pasekmės
   juosta → „Atšaukti pataisymą" (grąžina ABI patalpas). Perimetro faktas pasako: „Riba su patalpa 05 — menama
   (sienos ten nėra), į perimetrą neįskaičiuota." Menama kraštinė brėžinyje — punktyru.

## Ko nedarome
- Erdvių su 3+ patalpomis (pasakoma ir paliekama kaip yra); kreivų ar laužytų ribų; automatinio ribos spėjimo.
- Kiekių taisyklių: perimetras po dalijimo — sudėtas iš užrašų arba tuščias su įverčiu (tikrų sienų ilgiu), kaip visur.

## Tikrinimas
TDD ant sintetinio plano (dvi patalpos be pertvaros): dalys, plotai, menama kraštinė, perimetras be jos; riba,
neatskirianti numerių → `bad_line`; ne bendroje erdvėje → `not_shared`; `dimension_sum` menamos kraštinės neskaito;
API (nieko neišsaugo; abi patalpos; 404/401); frontend units (dviejų taškų būsena, pataisa abiem patalpoms);
tikras brėžinys: H 04/05 — dalys, plotai prieš lentelę, sudėti perimetrai; naršyklė: H 04 → „Padalinti erdvę" → du
paspaudimai → du kontūrai, perimetro faktai, pasekmės juosta → „Atšaukti". Eval nepaliestas.
