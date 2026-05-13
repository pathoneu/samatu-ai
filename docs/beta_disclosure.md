# Beta disclosure (Week 1 Task 1.1, D1)

## Why this exists

The 2026-05-08 council unanimously flagged a **liability blind spot**: live beta
users were producing real estimates from a system with known formula errors
(window default, reveals, grindjuostės, hidroizoliacija unit). Even with no paid
tier active, contractors were bidding real EUR off broken arithmetic. Honest
disclosure beats clever fixes.

## What we shipped

1. **In-app banner** — `frontend/src/components/BetaDisclosureBanner.jsx`,
   mounted at the top of `AppLayout` so every authenticated route renders it
   above the page content.
2. **Email template** — `backend/data/email_templates/beta_disclosure_lt.md`.
3. **Send script** — `scripts/send_beta_disclosure.py`, supports `--dry-run`
   and `--send` (SMTP via env). Default is `--dry-run` until the user list and
   SMTP creds are wired.

## Banner copy (canonical, do not silently change)

> **Sąmatų AI yra beta versijoje.** Aptikome kelias kiekio skaičiavimo
> klaidas, kurios galėjo paveikti dažų, angokraščių, hidroizoliacijos ir
> bendrų sienų skaičiavimus. Iki kol eilutė pažymėta „Patikrinta“,
> rezultatą laikykite pagalbiniu juodraščiu, o ne galutine sąmata. Prieš
> teikdami kainos pasiūlymą patikrinkite kiekius.

The four positions named (langų plotai, angokraščiai, hidroizoliacija, bendros
sienos) are the explicit ones the council and follow-up code audit identified.
Don't replace with a generic "verify your output" — generic disclosure does not
prompt action.

## Operational

- The banner is **dismissible per-session** via localStorage
  (`beta_disclosure_dismissed_2026_05_10`). Returning users won't be nagged but
  the message resets if you bump the storage key (e.g. on a future round of
  fixes).
- The email script defaults to `--dry-run`. Wire `BETA_DISCLOSURE_USERS_FILE`
  pointing at a JSON list of `{email, name}` and the SMTP env vars before
  `--send`.
- Future related deliveries (Week 4 EUR-weighted error report, Week 8 launch)
  should reference this same disclosure path so users see a consistent story.

## When to remove

The plan's Week 8 launch gate (`reports/launch/week8_paid_launch_gate.md`)
includes "Disclosure banner remains visible for beta" as a required check.
Do not remove the banner until:

1. EUR-weighted error ≤15 % on top-5 lines is verified against the human GT.
2. Audit-trail F2 export works.
3. Click-to-correct UI with the `Patikrinta` state is shipped.
4. The owner explicitly signs off on the launch-gate document.
