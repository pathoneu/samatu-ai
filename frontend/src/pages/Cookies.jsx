/**
 * Slapukų politika — Pathon (LT, BDAR / LR Elektroninių ryšių įstatymas).
 *
 * 2026-07-05: naujas puslapis DARK graphite identitete (LegalLayout).
 * TEISINIS STATUSAS: profesionalus PROJEKTAS, ne teisinė konsultacija —
 * prieš publikavimą turi peržiūrėti teisininkas.
 *
 * Susijęs su CookieBanner.jsx: kategorijos (būtinieji / analitiniai /
 * rinkodaros) atitinka banner'io perjungiklius; sutikimas saugomas
 * localStorage rakte `pathon_cookie_consent`. Sutikimą galima persvarstyti
 * per poraštės nuorodą „Slapukų nustatymai" (atveria banner'į iš naujo).
 */
import React from 'react';
import LegalLayout, {
  Section, P, Term, UL, LI, Callout, Code, DefTable,
} from '@/components/legal/LegalLayout';
import { Link } from 'react-router';
import { useTranslation } from 'react-i18next';
import { openCookieSettings } from '@/components/CookieBanner';

export default function Cookies() {
  const { t } = useTranslation();
  return (
    <LegalLayout
      eyebrow={t('legal.cookies.eyebrow')}
      index="LEX-02"
      title={t('legal.cookies.title')}
      intro={t('legal.cookies.intro')}
      updated="2026-07-05"
      effective="2026-07-05"
    >
      <Section n={1} title="Kas yra slapukai">
        <P>
          Slapukai (angl. <em>cookies</em>) — nedideli tekstiniai failai, kuriuos
          svetainė įrašo jūsų įrenginyje naršant. Jie leidžia svetainei atpažinti
          jūsų naršyklę, išlaikyti prisijungimo būseną ir prisiminti pasirinkimus.
          Panašias technologijas (pvz., <Code>localStorage</Code>) naudojame jūsų
          slapukų sutikimui įsiminti.
        </P>
      </Section>

      <Section n={2} title="Kokių kategorijų slapukus naudojame">
        <P>
          Slapukus skirstome į tris kategorijas. Būtinieji veikia visada; analitinius
          ir rinkodaros slapukus įjungiame tik gavę jūsų sutikimą.
        </P>
        <UL>
          <LI>
            <Term>Būtinieji</Term> — reikalingi paslaugai veikti: prisijungimui, sesijos
            palaikymui, saugumui ir jūsų slapukų pasirinkimui įsiminti. Be jų svetainė
            neveiktų, todėl jie <em>visada įjungti</em> ir jiems atskiro sutikimo nereikia.
          </LI>
          <LI>
            <Term>Analitiniai</Term> — padeda suprasti, kaip naudojama paslauga
            (apibendrinta naudojimo statistika), kad ją tobulintume. Įjungiami tik
            <em> pagal sutikimą</em>.
          </LI>
          <LI>
            <Term>Rinkodaros</Term> — leidžia rodyti aktualesnį turinį ar vertinti
            rinkodaros veiklą. Įjungiami tik <em>pagal sutikimą</em>.
          </LI>
        </UL>
        <Callout title="Numatytoji būsena — privatumas pirmiausia">
          <P>
            Kol neduodate sutikimo, jokie nebūtinieji (analitiniai, rinkodaros)
            slapukai neįjungiami. Sutikimą galite duoti, jo atsisakyti arba tvarkyti
            pagal kategoriją slapukų juostoje.
          </P>
        </Callout>
      </Section>

      <Section n={3} title="Konkretūs naudojami slapukai">
        <P>
          Toliau — pagrindiniai Pathon naudojami slapukai. Sąrašą periodiškai
          atnaujiname; jei įdiegsime naujų analitikos ar rinkodaros priemonių,
          papildysime šią lentelę.
        </P>
        <DefTable
          head={['Pavadinimas', 'Kategorija', 'Paskirtis', 'Galiojimas']}
          rows={[
            [
              'samatu_session',
              'Būtinasis',
              'Prisijungimo sesijos palaikymas (HTTPOnly, SameSite=Lax). Saugo tik naudotojo ID; nenaudojamas sekimui.',
              'Sesijos / iki atsijungimo',
            ],
            [
              'pathon_cookie_consent',
              'Būtinasis',
              'Įsimena jūsų slapukų sutikimo pasirinkimą (kategorijos + data), kad juosta nesikartotų.',
              '12 mėn. (localStorage)',
            ],
            [
              '— (analitiniai)',
              'Analitinis',
              'Apibendrinta naudojimo statistika. Įjungiami tik davus sutikimą; įdiegus konkrečią priemonę, čia bus nurodyti tikslūs slapukai.',
              'Pagal sutikimą',
            ],
            [
              '— (rinkodaros)',
              'Rinkodaros',
              'Rinkodaros veiklos vertinimas. Įjungiami tik davus sutikimą; šiuo metu tokie slapukai nenaudojami.',
              'Pagal sutikimą',
            ],
          ]}
        />
      </Section>

      <Section n={4} title="Kaip valdyti ar atšaukti sutikimą">
        <P>
          Savo pasirinkimą galite bet kada pakeisti — atšaukti duotą sutikimą arba
          įjungti papildomas kategorijas:
        </P>
        <UL>
          <LI>
            <Term>Slapukų juostoje</Term> — pasirinkite „Sutikti su visais", „Tik būtinieji"
            arba „Tvarkyti" ir įjunkite / išjunkite kategorijas.
          </LI>
          <LI>
            <Term>Bet kada vėliau</Term> — atverkite nustatymus per nuorodą{' '}
            <button
              type="button"
              onClick={openCookieSettings}
              className="text-primary hover:underline font-medium"
            >
              Slapukų nustatymai
            </button>{' '}
            (taip pat rasite svetainės poraštėje).
          </LI>
          <LI>
            <Term>Naršyklės nustatymuose</Term> — galite blokuoti ar ištrinti slapukus.
            Atkreipkite dėmesį: išjungę būtinuosius slapukus, negalėsite naudotis
            paslauga (pvz., prisijungti).
          </LI>
        </UL>
      </Section>

      <Section n={5} title="Trečiųjų šalių slapukai">
        <P>
          Kai kurias funkcijas teikia patikimi partneriai, kurie gali įrašyti savo
          slapukus:
        </P>
        <UL>
          <LI><Term>Stripe</Term> — mokėjimų saugumui ir sukčiavimo prevencijai apmokėjimo metu.</LI>
          <LI><Term>Google</Term> — jei prisijungiate per Google, tapatybės patvirtinimo procese.</LI>
        </UL>
        <P>
          Šie partneriai tvarko duomenis pagal savo privatumo politikas. Bendrą mūsų
          duomenų tvarkymą aprašo{' '}
          <Link to="/privacy" className="text-primary hover:underline">Privatumo politika</Link>.
        </P>
      </Section>

      <Section n={6} title="Politikos atnaujinimas">
        <P>
          Šią slapukų politiką galime atnaujinti pasikeitus naudojamiems slapukams
          ar teisiniams reikalavimams. Paskutinio atnaujinimo data nurodyta šio
          puslapio viršuje.
        </P>
      </Section>
    </LegalLayout>
  );
}
