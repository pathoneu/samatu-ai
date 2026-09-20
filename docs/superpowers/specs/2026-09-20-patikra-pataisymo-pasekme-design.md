# Patikra: pataisymo pasekmė, „jūsų" ir „Atšaukti" (2 sub-projekto 2 pjūvis, pirma dalis)

2026-09-20. €0. Tęsia `2026-09-19-patikra-ant-brezinio-design.md` („Not in this slice: … the correction's
consequence strip, „jūsų" badge and undo").

## Kodėl
Steigėjo verdiktas (2026-09-17): „sunku suprasti, ar kažką pataisiau". Išmatuota 2026-09-20 naršyklėje:
- po pataisymo vienintelis ženklas — viena eilutė PAČIOJE dešinės pusės APAČIOJE („Persiskaičiavo 9 eilutės ·
  … +22,40 kg"), už 1–2 ekranų nuo fakto, kurį jis ką tik keitė; ji mini tik vieną (didžiausią) eilutę;
- pataisytas faktas nuo nepataisyto skiriasi tik sakiniu („įrašėte patys") — peržvelgiant patalpą akimis
  nematyti, kas čia jo;
- atšaukti negalima: suklydus reikia prisiminti seną reikšmę ir įvesti ją iš naujo (perimetro atveju senos
  reikšmės lape nebėra).
(Šuolis į lapo viršų po išsaugojimo pataisytas 3 sub-projekte.)

## Ką darome
1. **Pasekmės juosta po pataisytu faktu.** Iškart po išsaugojimo, po TA faktų eilute: „Pakeista. Sąmatoje
   pasikeitė N eilučių:" ir iki 3 eilučių „Pavadinimas: buvo → tapo vnt." (pirma atsiradusios / dingusios,
   tada pagal santykinį pokytį), „ir dar N", kai jų daugiau. Jei eilutės nepasikeitė — „Sąmatos eilutės
   nepasikeitė". Juosta lieka, kol jis keičia kitą faktą arba išeina iš patalpos. Apatinė „ripple" eilutė lieka
   tik tiems veiksmams, kurie nėra fakto pataisymas (apimtis, kiekio perrašymas).
2. **„Atšaukti pataisymą".** Juostoje mygtukas grąžina projektą į būseną PRIEŠ tą pataisymą (visas ankstesnis
   projekto objektas — patalpos, eilutės, prielaidos — ne perskaičiavimas iš naujo, todėl grįžta tiksliai tai,
   kas buvo). Vieno lygio, tik paskutiniam pataisymui šioje patalpoje.
3. **Ženkliukas „jūsų".** Backend'as prie fakto deda `yours: true`, kai reikšmė yra jo (įrašytas plotas /
   perimetras / priimtas įvertis / aukštis, pasirinkta apdaila ar danga, pakeistos angos ar jų dydžiai).
   Faktų eilutėje prie pavadinimo — mažas ženkliukas „jūsų".

## Ko nedarome
Kelių lygių atšaukimo; atšaukimo po puslapio perkrovimo; kontūro viršūnių tempimo (kita pjūvio dalis);
stulpelinio peržiūrėjimo per visas patalpas.

## Tikrinimas
TDD grynoms funkcijoms (`consequenceOf`, `undoPatch`, fakto raktas pagal lauką) ir backend'o `yours`
(po vieną testą kiekvienam faktui); naršyklė: H 03 priimti perimetro įvertį → juosta po perimetru su
eilutėmis → „Atšaukti" grąžina tuščią lauką ir seną sąmatą; G 09 pakeisti dangą → juosta po „Grindys";
ženkliukas „jūsų" matomas; konsolė švari. Vartai: backend pilnas, frontend units, eslint; eval nepaliestas
(kiekių logika nekeičiama).
