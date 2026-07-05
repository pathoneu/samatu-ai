/**
 * Naudojimo sąlygos — Pathon (LT).
 *
 * 2026-07-05: perrašyta į naują DARK graphite identitetą (LegalLayout),
 * išplėsta. KRITINIS punktas takeoff įrankiui — 6 skyrius: AI ištraukti
 * kiekiai yra orientaciniai/pagalbiniai; naudotojas privalo juos patikrinti
 * prieš remdamasis komerciniuose pasiūlymuose ar sutartyse.
 *
 * TEISINIS STATUSAS: profesionalus PROJEKTAS, ne teisinė konsultacija —
 * prieš publikavimą turi peržiūrėti teisininkas.
 */
import React from 'react';
import LegalLayout, {
  Section, P, Term, UL, LI, Callout,
} from '@/components/legal/LegalLayout';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

export default function Terms() {
  const { t } = useTranslation();
  return (
    <LegalLayout
      eyebrow={t('legal.terms.eyebrow')}
      index="LEX-03"
      title={t('legal.terms.title')}
      intro={t('legal.terms.intro')}
      updated="2026-07-05"
      effective="2026-07-05"
    >
      <Section n={1} title="Paslaugos aprašymas">
        <P>
          Pathon yra dirbtinio intelekto pagalba veikianti statybų sąmatų
          skaičiavimo paslauga. Įkėlus statybos projekto PDF brėžinį, sistema
          atpažįsta patalpas ir elementus, apskaičiuoja kiekius (plotus, ilgius,
          tūrius, vienetus) ir padeda parengti kiekių žiniaraštį bei sąmatą Lietuvos
          formatu.
        </P>
        <P>
          Paslauga skirta profesionaliems verslo klientams (rangovams,
          sąmatininkams, statybos įmonėms) — tai B2B priemonė.
        </P>
      </Section>

      <Section n={2} title="Paskyra ir registracija">
        <UL>
          <LI>Norint naudotis paslauga, reikia sukurti paskyrą su galiojančiu el. paštu.</LI>
          <LI>Pateikta informacija turi būti teisinga ir aktuali.</LI>
          <LI>Esate atsakingi už savo prisijungimo duomenų saugumą ir už visą veiklą savo paskyroje.</LI>
          <LI>Apie neteisėtą prieigą ar saugumo incidentą nedelsdami praneškite el. paštu <a href="mailto:solutions@pathon.eu" className="text-primary hover:underline">solutions@pathon.eu</a>.</LI>
        </UL>
      </Section>

      <Section n={3} title="Leidžiamas naudojimas ir draudimai">
        <P>Naudodamiesi paslauga įsipareigojate:</P>
        <UL>
          <LI>Įkelti tik teisėtai gautus brėžinius — turėdami užsakovo ar savininko leidimą juos tvarkyti.</LI>
          <LI>Nepažeisti trečiųjų asmenų intelektinės nuosavybės ar konfidencialumo teisių.</LI>
          <LI>Nenaudoti paslaugos neteisėtais tikslais ar pažeidžiant galiojančius teisės aktus.</LI>
          <LI>Nebandyti sutrikdyti, apeiti saugumo priemonių ar automatiškai (angl. <em>scraping</em>) rinkti paslaugos duomenų be leidimo.</LI>
          <LI>Neperparduoti paslaugos tretiesiems asmenims be raštiško mūsų sutikimo.</LI>
        </UL>
      </Section>

      <Section n={4} title="Planai, kainos ir mokėjimai">
        <UL>
          <LI>Aktualūs planai ir kainos skelbiami <Link to="/pricing" className="text-primary hover:underline">kainų puslapyje</Link>.</LI>
          <LI>Prenumeratos mokamos periodiškai (mėnesiniais ar kitais nurodytais intervalais) ir, jei nenutraukiamos, atnaujinamos automatiškai.</LI>
          <LI>Mokėjimus tvarko Stripe. Verslo klientams gali būti taikomas atvirkštinis PVM apmokestinimas pagal LR teisės aktus.</LI>
          <LI>Prenumeratą galite nutraukti bet kada — ji galios iki apmokėto laikotarpio pabaigos. Jau prasidėjusio laikotarpio mokestis paprastai negrąžinamas, nebent to reikalauja imperatyvios teisės normos ar susitarsime kitaip.</LI>
          <LI>Pasiliekame teisę keisti kainas; apie pakeitimus pranešime iš anksto, o jie galios nuo kito atsiskaitymo laikotarpio.</LI>
        </UL>
      </Section>

      <Section n={5} title="Intelektinė nuosavybė">
        <UL>
          <LI>
            <Term>Jūsų turinys lieka jūsų.</Term> Įkelti brėžiniai, projektai ir jais remiantis
            sugeneruoti kiekiai bei sąmatos priklauso jums. Suteikiate mums tik ribotą
            licenciją tvarkyti šį turinį tiek, kiek būtina paslaugai teikti (įskaitant
            AI apdorojimą, aprašytą <Link to="/privacy" className="text-primary hover:underline">Privatumo politikoje</Link>).
          </LI>
          <LI>
            <Term>Platformos IP lieka Pathon.</Term> Pati programinė įranga, sąsaja, logika,
            prekės ženklas ir kita platformos intelektinė nuosavybė priklauso Pathon,
            MB. Jums nesuteikiamos jokios teisės, išskyrus teisę naudotis paslauga pagal
            šias sąlygas.
          </LI>
        </UL>
      </Section>

      <Section n={6} title="Atsakomybės apribojimas">
        <Callout title="Kritiškai svarbu — AI rezultatai yra orientaciniai">
          <P>
            Pathon dirbtinio intelekto <Term>ištraukti kiekiai ir sąmatos yra
            orientaciniai (pagalbiniai), o ne galutiniai.</Term> Dirbtinis intelektas gali
            klysti — ypač esant netipiškiems žymėjimams, prastos kokybės ar pažeistiems
            brėžiniams, netiksliam masteliui ar trūkstamai informacijai.
          </P>
          <P>
            <Term>Prieš remdamiesi rezultatais komerciniuose pasiūlymuose, sutartyse ar
            kituose įsipareigojimuose, privalote juos patikrinti ir patvirtinti.</Term>
            Galutinė atsakomybė už pateiktus kiekius, kainas ir pasiūlymus tenka jums
            kaip profesionaliam naudotojui (sąmatininkui ar rangovui).
          </P>
          <P>
            Pathon <Term>neatsako už klaidas, netikslumus ar nuostolius, atsiradusius dėl
            nepatikrintų rezultatų</Term> naudojimo.
          </P>
        </Callout>
        <P>
          Paslauga teikiama „tokia, kokia yra" ir „kiek prieinama" (angl.
          <em> as is / as available</em>). Įstatymų leidžiama apimtimi netaikome jokių
          numanomų garantijų ir neatsakome už netiesioginius, atsitiktinius ar
          pasekminius nuostolius, negautas pajamas ar trečiųjų asmenų pretenzijas,
          kilusias dėl naudojimosi paslauga.
        </P>
        <P>
          Kiek tai leidžia teisės aktai, bendra mūsų atsakomybė ribojama suma, kurią
          sumokėjote už paslaugą per 12 mėnesių iki įvykio, dėl kurio kilo pretenzija.
          Šie apribojimai netaikomi tais atvejais, kai atsakomybės neleidžia riboti
          imperatyvios teisės normos (pvz. tyčia ar didelis neatsargumas).
        </P>
      </Section>

      <Section n={7} title="Paslaugos pakeitimai ir nutraukimas">
        <UL>
          <LI>Galime tobulinti, keisti ar nutraukti atskiras paslaugos funkcijas; apie esminius pakeitimus pranešime iš anksto.</LI>
          <LI>Galite bet kada nutraukti naudojimąsi ir ištrinti paskyrą — susisiekę <a href="mailto:solutions@pathon.eu" className="text-primary hover:underline">solutions@pathon.eu</a> arba per paskyros nustatymus.</LI>
          <LI>Galime sustabdyti ar nutraukti prieigą, jei iš esmės pažeidžiate šias sąlygas arba naudojatės paslauga neteisėtai.</LI>
          <LI>Nutraukus paskyrą, jūsų duomenys tvarkomi pagal <Link to="/privacy" className="text-primary hover:underline">Privatumo politiką</Link>.</LI>
        </UL>
      </Section>

      <Section n={8} title="Sąlygų pakeitimai">
        <P>
          Šias sąlygas galime atnaujinti. Apie esminius pakeitimus pranešime iš
          anksto. Toliau naudodamiesi paslauga po pakeitimų įsigaliojimo, sutinkate su
          atnaujintomis sąlygomis. Paskutinio atnaujinimo data nurodyta viršuje.
        </P>
      </Section>

      <Section n={9} title="Taikoma teisė ir ginčai">
        <P>
          Šioms sąlygoms taikoma Lietuvos Respublikos teisė. Ginčus pirmiausia
          sieksime išspręsti derybomis. Neišsprendus taikiai, ginčai nagrinėjami
          Lietuvos Respublikos teismuose pagal mūsų buveinės vietą, laikantis
          imperatyvių teisės normų.
        </P>
      </Section>

      <Section n={10} title="Kontaktai">
        <P>
          Klausimai dėl naudojimo sąlygų:{' '}
          <a href="mailto:solutions@pathon.eu" className="text-primary hover:underline">solutions@pathon.eu</a>.
        </P>
      </Section>
    </LegalLayout>
  );
}
