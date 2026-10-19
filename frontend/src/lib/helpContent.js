/**
 * helpContent.js — the „Pagalba" page's text (v3 W7-A M6, 2026-10-18), kept as
 * data so the vocabulary guard tests can read it and the page stays a layout.
 *
 * Every answer says what to click and what to check, in the app's own button
 * names. „Kas naujo" lists only what is in this build; newest first.
 */

export const HELP_SECTIONS = Object.freeze([
  {
    id: 'skaicius',
    title: 'Kaip patikrinti skaičių',
    steps: [
      'Sąmatoje spustelėkite eilutę — po ja atsivers patalpos, iš kurių kiekis sudėtas, ir kiekvienos dalis.',
      'Prie skaičiaus parašyta, iš kur jis paimtas: perskaitytas iš brėžinio, apskaičiuotas iš kitų matmenų ar įrašytas jūsų.',
      'Žingsnyje „Patikra" programa užduoda kelis klausimus su siūlomais atsakymais. Atsakę matysite, kiek eilučių perskaičiuota.',
      'Prielaidas (sienos storį, glaistymo lygį, angas) keiskite projekto viršuje, mygtuku „Nustatymai" — kiekiai perskaičiuojami iš karto, o pakeitimą galima atšaukti.',
    ],
  },
  {
    id: 'konturas',
    title: 'Kaip pataisyti patalpos kontūrą',
    steps: [
      'Pasirinkite patalpą sąraše arba brėžinyje — prie jos užrašo atsiras juosta su „Taisyti kontūrą" (klavišas E).',
      'Tempkite kampus: jie prilimpa prie sienų — kvadratas rodo sienos kampą, rombas — sieną. Spustelėkite vidurio tašką — pridėsite kampą, dukart spustelėkite kampą — pašalinsite.',
      'Enter išsaugo: sienos ir angos perskaitomos iš naujo, kiekiai perskaičiuojami. Esc atsisako.',
      'Suklydote? Ctrl+Z (Mac — ⌘Z) grąžina paskutinį pakeitimą; ankstesnes projekto būsenas rasite „Versijos".',
    ],
  },
  {
    id: 'linijos',
    title: 'Ką reiškia linijos brėžinyje',
    steps: [
      'Ištisinė linija — perskaityta iš brėžinio arba jūsų patvirtinta.',
      'Brūkšninė linija — apskaičiuota arba tik pasiūlyta: patikrinkite ir patvirtinkite.',
      'Raudona — tik klaida (pavyzdžiui, kontūrai persidengia). Spalva niekada nėra vienintelis ženklas — šalia visada yra užrašas.',
      'Prieš matuodami patikrinkite lapo mastelį apačioje, būsenos juostoje. Jei rašo „Mastelis nenustatytas", spauskite „Mastelis".',
    ],
  },
  {
    id: 'eksportas',
    title: 'Kaip išsiųsti sąmatą',
    steps: [
      '„Eksportuoti" → Excel arba PDF. Lange pasirinkite skyrius, PVM (21, 9 ar 0 % arba atvirkštinį) ir grupavimą.',
      '„Vidinė kopija su pastabomis" skirta jums: joje programos pastabos ir „Pakeitimų žurnalas". Klientui siųskite failą be jos.',
      '„Nuoroda klientui" rodo sąmatą naršyklėje — su kainomis. Nuorodą galite bet kada atšaukti.',
    ],
  },
]);

export const WHATS_NEW = Object.freeze([
  {
    date: '2026-10-19',
    items: [
      'Įvadas brėžinyje — dešimt trumpų patarimų po vieną, prie to, ką kiekvienas paaiškina.',
      'Pirmą kartą įjungus įrankį ar atidarius skydelį, šalia parodomas vienas sakinys apie jį.',
      '„Nustatymai" suskirstyti į penkis skyrius; patalpos rodomos tik tos, kurių reikšmė skiriasi.',
      'Pakeitę nustatymą matysite, kas sąmatoje pasikeitė, ir galėsite tai atšaukti.',
    ],
  },
  {
    date: '2026-10-18',
    items: [
      'Pamiršus slaptažodį, naują nustatysite per nuorodą el. laiške (kai laiškų siuntimas įjungtas).',
      'Eksporte — jūsų PVM tarifas: 21, 9 arba 0 %. Numatytąjį naujiems projektams nustatysite „Nustatymuose".',
      'Excel sąmatą galima grupuoti pagal aukštus ir butus; vidinėje kopijoje — lapas „Pakeitimų žurnalas".',
      'Įvadas brėžinyje nebeuždengia atidarytų langų.',
      'Kai viename lape matavimų daugiau nei 1500, programa perspėja — brėžinys gali pradėti strigti.',
    ],
  },
  {
    date: '2026-10-16',
    items: [
      'Matuojant ir nustatant mastelį žymeklis prilimpa prie sienų kampų ir paviršių.',
      'Nustatant mastelį programa pasiūlo artimiausią įprastą mastelį ir parodo skirtumą procentais.',
      '„Taisyti kontūrą" — patalpos kontūrą taisote kampas po kampo, sienos perskaitomos iš naujo.',
    ],
  },
]);
