"""2026-10-06 — the project chat's built-in guide to the app names what is on screen today.

The guide inside `main._CHAT_SYSTEM_PROMPT` („PROGRAMOS ŽINYNAS") still described a „Prielaidos" button, a
„Kiekiai" tab, an „Eksportuoti" button in the top bar, a „Bendrinti" link and an orphan-row message the app no
longer shows — so the assistant sent him to places that do not exist. Only the description of the app changed;
these tests pin it to the four steps and the labels the frontend renders.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main  # noqa: E402

FRONTEND = Path(__file__).resolve().parents[2] / "frontend" / "src"
PROMPT = main._CHAT_SYSTEM_PROMPT
GUIDE = PROMPT[PROMPT.index("═══ PROGRAMOS ŽINYNAS"):PROMPT.index("═══ VEIKSMAI")]

# Quoted in the guide on purpose, but not a label on any screen.
NOT_A_SCREEN_LABEL = {
    "Bendrinti",       # the OLD name, quoted to say where it went („buvęs „Bendrinti"")
    "Liko: N d.",      # a template: „Liko:" + the days left
}


def test_the_guide_walks_the_four_steps_and_the_current_buttons():
    assert '„Brėžinys" → „Patikra" → „Sąmata" → „Siųsti"' in GUIDE
    for label in ("Nustatymai", "Glaistymo lygis", "Potinkiniai maišytuvai", "Angokraščiai — kurių angų",
                  "Sienos storis (pertvaros)", "Sienų apdaila (dažomos / nedažomos)", "Užpildyti iš mano kainyno",
                  "Excel (.xlsx)", "PDF pasiūlymas", "Nuoroda klientui", "Įmonės informacija", "Kainynai",
                  "Skaičiuoti kiekius"):
        assert f"„{label}\"" in GUIDE, label


def test_the_prompt_no_longer_sends_him_to_the_old_places():
    for stale in ('skirtuke „Kiekiai"', 'Skirtukas „Kiekiai"', 'Mygtukas „Prielaidos"', 'Skirtukas „Brėžinys"',
                  'Mygtukas „Eksportuoti" (viršutinė juosta)', '„Eksportuoti" in the top bar',
                  '„Bendrinti" sukuria', "„Pradėti analizę\"", "pagal naujas prielaidas",
                  "Mastelis: 1:X", "(automatinis)", "Nustatymai → Įmonė →"):
        assert stale not in PROMPT, stale


def _screen_text() -> str:
    """Every string the frontend can put on screen: lt.json and the components' own literals."""
    parts = []
    for path in FRONTEND.rglob("*"):
        if path.suffix in (".js", ".jsx", ".json") and ".test." not in path.name and "__fixtures__" not in path.parts:
            parts.append(path.read_text(encoding="utf-8", errors="ignore"))
    return "\n".join(parts)


def test_every_label_the_guide_quotes_is_on_screen():
    """A label renamed in the app without the guide following is caught here — say the new name in the guide."""
    labels = {" ".join(q.split()) for q in re.findall(r'„([^"“]+)["“]', GUIDE)}
    assert len(labels) > 40, "the guide quotes almost nothing — did the section markers move?"
    screen = _screen_text()
    missing = sorted(lbl for lbl in labels - NOT_A_SCREEN_LABEL if lbl not in screen)
    assert not missing, f"the chat guide quotes labels the app does not show: {missing}"
