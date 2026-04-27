/**
 * Terms — naudojimo sąlygos (LT). Static page.
 */

import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';

export default function Terms() {
  return (
    <div className="min-h-screen p-6 bg-background">
      <div className="max-w-3xl mx-auto">
        <Link to="/" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-6">
          <ArrowLeft className="w-4 h-4" /> Grįžti
        </Link>
        <article className="prose prose-neutral dark:prose-invert max-w-none">
          <h1>Naudojimo sąlygos</h1>
          <p className="text-sm text-muted-foreground">Atnaujinta: 2026-04-27</p>

          <h2>1. Paslaugos aprašymas</h2>
          <p>
            Sąmatų AI yra dirbtinio intelekto pagalba veikianti vidaus apdailos
            sąmatų skaičiavimo paslauga. Įkėlus statybos projekto PDF brėžinį,
            sistema automatiškai atpažįsta patalpas, matmenis ir pateikia
            kiekių žiniaraštį (m², m, vnt.) be kainų.
          </p>

          <h2>2. AI rezultatų pobūdis</h2>
          <p className="font-medium">
            SVARBU: AI rezultatai yra <em>orientyriniai</em>, ne galutiniai.
          </p>
          <ul>
            <li>AI gali klysti — visada peržiūrėkite ir patvirtinkite kiekius prieš naudodami komerciniam pasiūlymui.</li>
            <li>Mes neatsakome už tikslumo trūkumą, jei brėžinyje yra netipiški simboliai, pažeisti puslapiai ar netinkami matmenys.</li>
            <li>Jei AI nerado eksplikacijos lentelės, sistema parodys įspėjimą — tokiais atvejais kiekiai gali svyruoti ±10–30%.</li>
            <li>Galutinė atsakomybė už pasiūlymą tenka jums — sąmatininkui ar rangovui.</li>
          </ul>

          <h2>3. Vartotojo įsipareigojimai</h2>
          <ul>
            <li>Įkelti tik teisėtai gautus brėžinius (turint užsakovo arba savininko leidimą).</li>
            <li>Nenaudoti paslaugos neteisėtais tikslais.</li>
            <li>Saugoti paskyros slaptažodį — neperduoti jo tretiesiems asmenims.</li>
            <li>Pranešti apie saugumo incidentus el. paštu solutions@pathon.eu.</li>
          </ul>

          <h2>4. Mūsų įsipareigojimai</h2>
          <ul>
            <li>Teikti paslaugą "kaip yra" — siekti maksimalaus tikslumo, bet negarantuoti 100%.</li>
            <li>Saugoti jūsų duomenis pagal Privatumo politiką.</li>
            <li>Pranešti apie esminius pakeitimus iš anksto.</li>
            <li>Per pagrįstą laiką reaguoti į techninius klausimus el. paštu.</li>
          </ul>

          <h2>5. Atsakomybės ribojimas</h2>
          <p>
            Sąmatų AI atsakomybė ribojama suma, sumokėta už paslaugą per
            pastaruosius 12 mėnesių. Mes neatsakome už netiesioginius nuostolius,
            negautas pajamas ar trečiųjų asmenų pretenzijas, kilusias dėl
            naudojimosi paslauga.
          </p>

          <h2>6. Paskyros ištrynimas</h2>
          <p>
            Galite ištrinti paskyrą bet kuriuo metu, susisiekę solutions@pathon.eu.
            Po ištrynimo jūsų projektai bus negrįžtamai pašalinti per 30 dienų.
            Anonimizuoti agreguoti duomenys (korekcijų statistika) gali būti
            išsaugoti AI promptų tobulinimui.
          </p>

          <h2>7. Pakeitimai</h2>
          <p>
            Šios sąlygos gali būti keičiamos. Esminius pakeitimus paskelbsime
            iš anksto. Tęsdami naudoti paslaugą po pakeitimų, sutinkate su
            naujomis sąlygomis.
          </p>

          <h2>8. Taikoma teisė</h2>
          <p>
            Šioms sąlygoms taikoma Lietuvos Respublikos teisė. Ginčai sprendžiami
            Lietuvos teismuose pagal mūsų buveinės vietą.
          </p>

          <p className="text-sm text-muted-foreground mt-8">
            Klausimai? <a href="mailto:solutions@pathon.eu">solutions@pathon.eu</a>
          </p>
        </article>
      </div>
    </div>
  );
}
