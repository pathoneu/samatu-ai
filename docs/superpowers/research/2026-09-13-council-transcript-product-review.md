# Council transcript — product review of Pathon (2026-09-13)

## Question

Product review of Pathon (Lithuanian construction cost-estimation app for small interior-finishing contractors, persona "Rimas"). Founder: "looks good so far, but I doubt because everything is very new." Asked: five biggest improvements ranked; what to cut; riskiest assumption; what an estimator would miss in Patikra; how to run a 5-project pilot; disagree with the founder's instincts where warranted. Full framed brief in the transcript.

## Framed brief

See the advisor prompt: app description (four-step flow, how numbers are made, accuracy, rough edges) and five questions. Anonymisation for peer review: A = Outsider, B = Executor, C = Contrarian, D = Expansionist, E = First Principles. Four peer reviews were run; the fifth was skipped because the four had converged.

## Advisor responses

### The Contrarian (C)

Fatal flaw: the check sheet verifies six things Rimas never doubted and hides the one he does. His signed act: 239,4 m² walls. Engine: 298,7. All six facts pass and the biggest line is still 25 % off. He clicks "Teisinga" 54 times, gets "9 iš 9", and the number still isn't his. Worse: if "Teisinga" sets user_verified, the ground-truth builder harvests rubber stamps as human truth.

Riskiest assumption: that the gap is his error. It may be his bidding strategy — omit cabinet walls, win the job, recover on site. "Kaip mano sąmatose" is fitted to N=1.

Ranked: 1. One hour with him marking exclusions on the drawing — no code; then a per-room fact "Neįskaičiuota / prielaidos". 2. Determinism: 12 vs 13 doors between runs kills trust faster than 10 % MAE; pin openings to the door schedule / plan tags; diff on re-read. 3. Prices before the first Sąmata (kainynas at onboarding) — quantities-only is an engine rule, not a UX rule. 4. Crops only for contested facts; auto-accept plan-text areas. 5. Edit telemetry.

Cut: measurement tools and "nekalibruotas"; confidence chips; stat cards; chat button; client link; the paid re-read beside Export. Estimator would miss: per-wall išklotinė breakdown, ceiling drops, tile height, labour-only vs with-material, a "tikrinti objekte" flag. Pilot: one metric — does he send the Pathon export or re-type into his Excel? Good after 5: ≥3 sent directly, ≤10 row edits each, identical output on re-run, asks for #6.


### The First Principles Thinker (E)

Wrong question. Rimas doesn't buy numbers; he buys a document he'd sign. The 239 vs 299 m² gap says the target isn't what the drawing contains but what Rimas bids — convention, not misreading; the 9 % MAE measures the wrong thing.

Ranked: 1. Determinism before accuracy — a tape measure repeats; cache reads; openings become a confirmed fact he clicks. 2. The conventions interview — what do you exclude, deduct, which height, which rooms; encode as settings like corner beads; declared scope isn't curve-fitting. 3. Prices at onboarding, not per project. 4. Measure, don't type, inside "Pataisyti". 5. Never self-contradict ("nekalibruotas" while knowing 1:50; "parquet" guessed under an evidence-first banner → blank + reason).

Cut: chips, DE badge, stat cards, chat, paid re-read beside Export, the 114-row view as default. Riskiest assumption: that measuring is his bottleneck — verify before building. Estimator misses: cross-checks by trade (doors vs schedule, walls/floor ratio per room), out-of-scope surfaces, above-3 m, his override stamped as his. Pilot: five live bids; PDF→sent time vs hand, corrections by type (misread vs convention), residual to what he actually bid, same PDF twice = zero variance, export sent unmodified. Disagrees with quantities-before-prices as pilot sequencing.


### The Expansionist (D)

The check sheet is the product, not a step; every "Pataisyti" is a human-labelled Lithuanian takeoff fact nobody else owns.

Ranked: 1. Make the 239 vs 299 gap a feature: "Palyginti su mano sąmata". 2. Prices first (his kainynas at onboarding; "0,00 €" is the anti-aha; stored prices = lock-in). 3. The proposal that wins the job: client PDF/link with his logo and evidence crops — free distribution. 4. Floors from the floor plan. 5. Template layout as the only layout once a sąmata is uploaded.

Cut: stat cards, 114 rows on Step 1, chips, DE badge, "nekalibruotas", test projects; re-read to a menu. Riskiest assumption: that his pain is takeoff hours; if the product is "defend your number", evidence is the product. Estimator would miss: per-room omissions, a slot for what drawings never show (demolition, floor protection, waste, scaffolding), running m² per room. Pilot: corrections per project 15 → <5, rows added/deleted, minutes upload→sent, export reached a real client unchanged; good = projects 4–5 skip his Excel. Adjacent: designers as a channel; anonymised kainynai as a price index.


### The Outsider (A)

1. Stop calling guesses facts: floor-by-purpose, default height, standard door sizes are questions — ask them first, guess pre-selected; a real read and a guess sharing one "Teisinga" button is the biggest trust leak. 2. Find out what his 239,4 m² excludes — one hour at his table, zero code. 3. His template as default, not a switch (53 rows vs 114). 4. Per-room totals in his language atop each check sheet ("Sienos ~92 m², grindys 38, lubos 38"). 5. Delete the self-contradictions.

Cut: dashboard stats, DE badge, chat, client link, the 114 rows in Step 1; rename "Siųsti" → "Eksportuoti". Riskiest assumption: that his signed act is wrong and the drawing is right — the act got paid. Estimator would miss: partial scope per room (walls behind cabinets, tiles to 2,1 m); ceiling construction ("painted" hides GK/stretch/plain); prep work; watching rows move when a fact is corrected. Pilot: five real projects, you present, he corrects; minutes vs manual, corrections by fact type, per-room walls/floors within 5 % of his hand count after corrections, export reaches a real client; good = he uploads project six unasked. Take his price list once at onboarding; the perimeter sentence is a debug log — one number, one reason, "kodėl?" for the rest.


### The Executor (B)

1. The wall gap (2 days): sit with him, one room, his printed act beside the check sheet; whatever he excludes becomes a per-contractor switch like the corner-bead one. 2. Read floors from the floor plan (3–4 days). 3. Pin openings (2 days): freeze the vision read into the project blob; re-extraction shows a diff, never silently replaces. 4. Mastelis chip (half a day). 5. Per-row ledger — already built; stop.

Cut/hide (one afternoon): chips, the "0,00 €" totals and banner, DE badge, paid re-read to a menu, test projects. Riskiest assumption: that 3 minutes of clicking "Teisinga" beats 20 minutes of tape-and-calculator for him. Missing in Patikra: "this wall isn't painted at all", separate heights for a dropped-ceiling zone, a "this reading is wrong, here's the number" path that doesn't route through standard sizes. Pilot: five new projects he's quoting anyway; minutes on Patikra, facts corrected per room, rows deleted before sending, whether the sent sąmata is Pathon's or retyped; good = export sent unedited once, ≤3 facts/project, asks when project six loads.


## Peer reviews

### Review 1

Strongest E (First Principles) — reconciles the conventions interview with "exam, not textbook"; determinism as a pass/fail instrument test; trade-level cross-checks; fold in the Contrarian's catch that "Teisinga" rubber stamps flow into the ground-truth builder. Biggest blind spot D (Expansionist): never mentions door-count flapping, builds a diff feature and client-facing evidence on it. All missed: (a) a signed aktas records executed work after site scope changes, not the bid — compare against his sąmata for the same project; (b) N=1 — put a second contractor in the pilot.


### Review 2

Strongest E; conventions as settings need the Contrarian's line — declared scope legitimate, a percentage is forbidden tuning. Blind spot D: a diff view against a non-repeatable engine is noise; "design for more corrections" contradicts its own metric. All missed: the act is completed works, not a bid — first question "is this act the whole job?"; N=1.


### Review 3

Strongest B (Executor) — schedulable, day-sized, ends with "stop"; amend: pin openings before floors; add the Contrarian's gate before the pilot. Blind spot D. All missed: act vs bid; N=1.


### Review 4

Strongest C (Contrarian) — "verifies six things he never doubted and hides the one he does"; rubber stamps feeding ground truth; the one-metric pilot. Blind spot D (contradicts itself; slides toward tuning). All missed: act is post-completion paperwork — one question settles it; N=1.


## Chairman's verdict

## Where the Council Agrees

- The 239,4 vs 298,7 m² gap is the product question, and it needs his table, not code. Four of five put a one-hour session at his table in their top two. Four read the gap as convention (what he excludes), not misreading.
- Determinism before accuracy. 12 vs 13 doors between runs kills trust faster than 10 % MAE. Pin the vision read in the project blob; a re-read shows a diff, never silently replaces; same PDF twice must be identical.
- A guess and a read must not share one "Teisinga". Floor-by-purpose, default height, standard door sizes are questions with a pre-selected answer, not facts.
- Cut list, near-unanimous: confidence chips, stat cards, DE badge, chat button, test projects, "nekalibruotas" while the engine knows 1:50, the paid re-read beside Export (to a menu), 114 rows as the Step 1 default — his template is the default, not a switch.
- One pilot metric: does the sent sąmata leave Pathon unmodified, or does he retype into Excel? Then corrections by type, same-PDF variance, project six loaded unprompted.
- Stop adding. The ledger is built.

## Where the Council Clashes

Quantities before prices. Three advisors: load his kainynas at onboarding so the first Sąmata opens priced — "0,00 €" is the anti-aha. Two defend the founder. Ruling: it is an engine rule (€ never shapes a quantity) and stays; as UX sequencing it is wrong. One-time kainynas import, quantities from the drawing, they meet in the sąmata.

Conventions as settings vs "exam, not textbook". Declared scope ("už baldų nedažoma", "plytelės iki 2,1 m") is a boolean like the corner-bead switch and legitimate; any factor or percentage derived from his totals is forbidden.

Is the check sheet the product? Chairman sides with the Contrarian — it becomes the product only with a per-room "Neįskaičiuota" fact and per-room totals atop each sheet so he checks outputs against gut, not inputs against crops.

Is takeoff time the pain? Unresolved — the pilot times PDF→sent against his hand process.

## Blind Spots the Council Caught

1. The act is the wrong baseline. A signed atliktų darbų aktas records executed work after site changes, not the bid. One question settles it; then compare against his sąmata for the same project.
2. Rubber stamps become ground truth. If "Teisinga" sets user_verified, the ground-truth builder harvests 3-second clicks as human truth. Gate before the pilot: only a typed or measured value in Pataisyti counts as confirmed.
3. N=1 everywhere — template, conventions, "Kaip mano sąmatose". Two of the five pilot projects must come from a second contractor.
4. The Expansionist's diff view and client-facing crops sit on a non-repeatable engine and could show a client 299 where 239 was a deliberate bid omission. Park.

## The Recommendation

In order, no parallel tracks:
1. The session — zero code, one hour, one room; every wall difference labelled misread / neįskaičiuota / pakeista objekte. Neįskaičiuota items become declared-scope switches, never factors.
2. Determinism gate (2 days) — openings frozen in the blob, diff on re-read, Teisinga ≠ user_verified.
3. Cut afternoon — the list above; "nekalibruotas" → "1:50 (iš brėžinio)"; kainynas import at onboarding so 0,00 € never appears.
4. Guesses become questions on the check sheet; per-room totals atop each sheet.
5. Pilot — five live bids he's quoting anyway, two from a second contractor; you present, he corrects. Good: export sent unmodified twice, ≤3 corrections per project all "convention", same PDF twice identical, project six loaded unasked.

Floors from the floor plan is the one engine task after the session — only if floors turn out misread rather than declared.

## The One Thing to Do First

Book the hour. Bring the Patikra sheet for one room, his printed act, and his sąmata for the same project. First question: "Ar šis aktas — visas darbas, kaip nubraižyta?" Fill the three columns for every wall in that room before writing a line of code.

