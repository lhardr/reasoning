# CC-debrief: openrouter/auto-beta som selvstændig kandidat

run_id: `20260805T080708_autobeta` — `results/auto/20260805T080708_autobeta.jsonl` (80 rækker)
Meta: `results/auto/20260805T080708_autobeta.meta.json`
Script: `run_auto_beta.py` (nyt, standalone — rører ikke `run_auto_router.py`)
Kørt: 2026-08-05. Panelets prissnapshot: 2026-06-26 (40 dage ældre — auto-beta afregner dagsaktuelt, samme forbehold som auto-kørslen).

Direkte opfølgning på registerets §6.1-note (2026-07-27): `openrouter/auto`
er nu markeret DEPRECATED af OpenRouter selv; afløseren `openrouter/auto-beta`
routede på task-klassifikation + community spend-share med default
cost_quality_tradeoff **9** (dokumenteret der som "billigste ~femtedel af
kandidaterne", til forskel fra den gamle `auto`'s NotDiamond-drevne default
på 7). Registeret bemærkede allerede at auto-beta's default-dial favoriserer
billige modeller — denne kørsel tester om det stemmer.

## Hvad blev lavet

1. `run_auto_beta.py`: samme design som `run_auto_router.py` — de samme 16
   celler (10 lette P1-P10 baseline + 3 tunge H1-H3 × {baseline,
   invited_auto}), 5 pass hver = 80 kald, `thinking_budget=16384`,
   `reasoning_effort="high"`, samme `data/prompts.yaml`/`src/heavy_tasks.py`-
   kilde og samme danske `HEAVY_INVITATION`, uændret. Eneste ændring: SLUG
   `openrouter/auto-beta` i stedet for `openrouter/auto`.
2. **DEFAULT SETTINGS**: ingen `plugins`-parameter sendt nogensinde — dvs.
   `cost_quality_tradeoff` er aldrig sat af scriptet, kun platformens egen
   default (9, per OpenRouters dokumentation) er i spil. Dette er bevidst:
   vi tester hvad en almindelig køber, der aldrig rører den knap, faktisk får.
3. **Ingen session-stickiness aktiveret**: intet `user`-felt, intet
   session-id, på noget af de 80 kald. Hver række logger eksplicit
   `session_id_sent: false` og `plugins_param_sent: false` for
   efterprøvbarhed direkte fra JSONL'en. Se punkt 3 i "De tre nye spørgsmål"
   nedenfor for hvad dette faktisk viste sig at betyde.
4. Grading, facit-sikkerhed og cost-kilde (OpenRouters egen `usage.cost`, ikke
   `config/pricing.yaml`) er uændret fra `run_auto_router.py`.
5. Prisloft $10 var aldrig i nærheden af at blive ramt: kørslen kostede i alt
   **$0,2802** for 80/80 kald. Ingen fejl, ingen stop.

Commit `17c2858` pushet til `origin/main` før kørsel; `git log origin/main..HEAD`
var tomt før start.

## Resultater — samme 8 spørgsmål som auto-debriefen

**1. Hvilken model valgte auto-beta? Router den samme prompt til forskellige
modeller på tværs af de 5 pass?**

**Fem** modeller blev valgt, på tværs af alle 80 kald — mod kun 2 for den
gamle `auto`:

| Routed model | n | andel |
|---|---|---|
| `deepseek/deepseek-v4-flash-0731` | 25 | 31,2% |
| `z-ai/glm-5.2` | 25 | 31,2% |
| `deepseek/deepseek-v4-pro` | 20 | 25,0% |
| `google/gemini-2.5-flash` | 5 | 6,2% |
| `anthropic/claude-sonnet-5` | 5 | 6,2% |

**0 af 16 celler er "split" på model-niveau** (alle 5 pass i hver celle valgte
samme model) — mod 1/16 for den gamle `auto`. Men **6 af de 16 model-stabile
celler varierede i `served_by`** (backend) på tværs af pass, selvom modellen
holdt sig fast: P3, P4, P7, P9, P10 (lette) og `finance_calc/baseline` (tung).
Se punkt 3 for hvorfor det betyder noget.

**2. Rammer den økonomien?**

Langt bedre end den gamle `auto`, men stadig ikke "billigst":

- Samlet: de samme 80 kald ville have kostet **$0,0396** hvis hver var gået
  til Gemma's celle-pris (auto-beta = **7,07×** dyrere — mod auto's 28,0×) eller
  **$0,0390** til den billigste-KORREKTE panelmodel per celle (auto-beta =
  **7,19×** dyrere).
- **På 5 af 16 celler var auto-beta's egen median faktisk BILLIGERE end
  Gemma/den billigste-korrekte panelmodel** (rang 1 af 14 kandidater — 12
  panelmodeller + Gemma-anker + auto-beta): P1, P2, P7, `code/baseline`,
  `code/invited_auto`. Det skete **aldrig** for den gamle `auto` (aldrig
  blandt de billigste på nogen af de 16 celler).
- På de øvrige 11 celler lå auto-beta typisk midt i feltet (rang 3.-8. af 14),
  aldrig blandt de dyreste — en markant anden profil end den gamle `auto`,
  der ofte lå nær toppen.

*Forbehold:* panelpriser er snapshot 2026-06-26; auto-beta's priser er
dagsaktuelle fra 2026-08-05 (40 dage senere). Se de generelle forbehold
nedenfor for hvorfor dette ikke ændrer retningen.

**3. Rammer den korrektheden?**

Tunge opgaver: **30/30 = 100%** — bedre end panelets egen **355/360 = 98,6%**
og markant bedre end den gamle `auto`'s 28/30 (93,3%).

Lette programmatisk-graderbare celler (P5/P6/P7, n=15): **10/15 = 66,7%**.
Dette er **udelukkende P6's skyld**: alle 5 pass af P6 (logik-gåden om
Anna/Bo/Clara/David) blev routet til `google/gemini-2.5-flash` og fejlede
**alle 5 gange** — 0/5. P5 og P7 (routet til hhv. `z-ai/glm-5.2` og
`deepseek/deepseek-v4-flash-0731`) var 5/5 hver. Dette er en reel,
reproducerbar svaghed hos den valgte model på netop denne opgavetype, ikke
en harness-uforenelighed (i modsætning til den gamle `auto`'s eneste
fejlmønster, som var værktøjsloop-relateret). P3/P8 kræver som før den
separate LLM-dommer og er bevidst ikke kørt her.

**4. Vælger den nogensinde en model uden for vores 12?**

Ja, oftere end den gamle `auto`: **43,7% af alle 80 kald** gik til modeller
uden for panelet — `deepseek/deepseek-v4-flash-0731` (31,2%, en billigere/
hurtigere DeepSeek-variant end panelets `deepseek_v4` = deepseek-v4-**pro**),
`google/gemini-2.5-flash` (6,2%, en ANDEN Google-model end både panelets
`gemma_4` og den gamle `auto`'s `gemini-3.6-flash`), og
`anthropic/claude-sonnet-5` (6,2%, nyere end panelets `claude_sonnet_4_6`).
De resterende 56,3% gik til **faktiske panelmodeller**: `deepseek/deepseek-v4-pro`
(= `deepseek_v4`, 25,0%) og `z-ai/glm-5.2` (= `glm_5_2`, 31,2%) — mod kun
39% for den gamle `auto` (kun `gpt_5_6_sol`). Ingen af de øvrige 10
panelmodeller (Claude Sonnet 4.6/Opus/Fable, Kimi K2.7/K3, GPT-5.5/5.6-Sol,
Mistral, Inkling, Gemma) blev valgt.

**5. Korrekte svar per faktisk betalt dollar**

Tung, samme metode som registrets §4.3-liste: **30 / $0,0738 = 406,4
korrekt/$**. Til sammenligning (registrets fulde liste plus begge
router-kørsler):

Gemma 1286 · DeepSeek 881 · **Auto-beta 406,4** · GLM 364 · K2.7 260 ·
Inkling 185 · Sol (gpt_5_6_sol, direkte) 95 · Sonnet 91 · Opus 71 · GPT-5.5 54 ·
Auto (gammel) 53,0 · K3 50 · Mistral 36 · Fable 33.

Auto-beta lander på en **3.-plads af 14 kandidater** — kun slået af Gemma og
DeepSeek selv, og et **7,7×** spring op fra den gamle `auto`'s 53,0 (som lå
blandt de to dårligste). Det er den enkeltstørste ændring i denne kørsel:
routing-laget gik fra at være en af de værste økonomiske valg i hele feltet
til at være tredjebedst.

**6. Router-overhead — koster routing-laget noget?**

To adskilte sammenligninger, fordi lette og tunge celler ikke er lige rene:

*Lette celler (P3/P4/P5/P9/P10, routet til panelmodellerne `deepseek_v4`/
`glm_5_2`):* rå tal viser auto-beta med lavere latens end panelets historiske
direkte tal — men **denne sammenligning er forurenet og skal IKKE læses som
"negativt overhead"**: panelets oprindelige lette-suite-kørsler for disse to
modeller brugte `thinking_budget=4096` (se `config/panel.yaml`'s kommentar om
at "de otte gamle modellers rækker" bevidst ikke er opdateret), mens denne
kørsel bruger 16384 konsekvent, og panelets tal er n=1 mod auto-betas n=5-median.
Ikke sammenlignelige uden videre — udeladt fra konklusionen.

*Tunge celler (samme `thinking_budget=16384` begge sider — ren
sammenligning):*

| Celle | Routet til | Auto-beta tokens (median) | Panel direkte tokens | Auto-beta lat. (median) | Panel direkte lat. | Auto-beta cost (median) | Panel direkte cost |
|---|---|---|---|---|---|---|---|
| finance_calc/baseline | deepseek_v4 | 334 | 447 | 3,7s | 13,7s | $0,00205 | $0,00060 |
| finance_calc/invited_auto | deepseek_v4 | 577 | 819 | 4,6s | 14,6s | $0,00494 | $0,00141 |
| finance_interp/baseline | glm_5_2 | 668 | 575 | 8,0s | 23,2s | $0,00315 | $0,00248 |
| finance_interp/invited_auto | glm_5_2 | 436 | 243 | 6,6s | 2,4s | $0,00327 | $0,00177 |

Mønster: tokens og latens svinger i begge retninger (ikke et konsistent
overhead-mønster som den gamle `auto`'s ~3× på tools-celler) — men **prisen
er konsekvent højere** via auto-beta end ved direkte panelkald til samme
nominelle model, 1,3-3,5× på tværs af alle fire celler. Dette KAN være en
reel routing-afgift (OpenRouters eget gateway-lag), men kan lige så vel være
backend-lotteriet i sig selv: hverken panelets `deepseek_v4`/`glm_5_2`-rækker
eller auto-beta pinner en bestemt backend, og `served_by` varierede da også
(BaseTen/CoreWeave) på begge sider. De to effekter kan ikke adskilles fra
disse fire datapunkter alene.

**7. Lette celler — auto-beta's egen varians over 5 pass**

Udeladt i samme detaljegrad som auto-debriefens tabel — fem forskellige
modeller gør en samlet min/median/max-tabel per prompt mindre meningsfuld her
end da alt gik til kun 2 modeller. Rå spredning kan læses direkte i
`results/auto/20260805T080708_autobeta.jsonl`.

**8. Sporinventar**

| Routed model | n | raw | absent |
|---|---|---|---|
| `deepseek/deepseek-v4-flash-0731` | 25 | 25 (100%) | 0 |
| `z-ai/glm-5.2` | 25 | 25 (100%) | 0 |
| `deepseek/deepseek-v4-pro` | 20 | 20 (100%) | 0 |
| `google/gemini-2.5-flash` | 5 | 5 (100%) | 0 |
| `anthropic/claude-sonnet-5` | 5 | 0 | 5 (100%) |

**75/80 (93,75%)** af alle rækker har fuldt rå CoT-tekst — markant højere end
den gamle `auto`'s 82,5%. De eneste 5 utraceable rækker sidder alle på
`claude-sonnet-5` (P8), som gav `trace_status="absent"` konsekvent — matcher
mønsteret for Anthropics øvrige modeller i panelet (`claude_sonnet_4_6`/
`opus_4_8`/`fable_5`, alle `summarized`/`absent`, aldrig rå). Ingen
`param_dropped`-flag udløst på nogen af de 80 rækker.

## De tre nye spørgsmål

**1. Auto mod auto-beta, direkte, samme akser**

| Akse | `openrouter/auto` (2026-07-26) | `openrouter/auto-beta` (2026-08-05) |
|---|---|---|
| Distinkte modeller valgt | 2 | 5 |
| Split-celler (model varierer over 5 pass) | 1/16 | 0/16 |
| Total cost (80 kald) | $1,1107 | $0,2802 (**3,96× billigere**) |
| Andel kald til modeller uden for panelet | 61% | 43,7% |
| Andel kald til faktiske panelmodeller | 39% | 56,3% |
| Økonomi vs. Gemma (samlet) | 28,0× dyrere | 7,07× dyrere |
| Økonomi vs. billigste-korrekte (samlet) | ikke opgjort separat (DeepSeek-tal brugt: 11,7×) | 7,19× dyrere |
| Celler hvor auto/-beta var billigst af alle 14 | 0/16 | 5/16 |
| Korrekthed, tung | 28/30 (93,3%) | 30/30 (100%) |
| Korrekthed, lette programmatiske (P5/P6/P7) | 15/15 (100%) | 10/15 (66,7%) |
| Korrekt/faktisk $, tung | 53,0 c/$ (rang 10.-11. af 14) | 406,4 c/$ (rang 3. af 14) |
| Router-overhead, tunge tool-celler | ~3× tokens, ~1,5-2× latens vs. direkte | prisen 1,3-3,5× højere, men tokens/latens ikke konsekvent værre |
| Andel rækker med rå CoT-spor | 82,5% | 93,75% |

Retningen er entydig på næsten alle akser: auto-beta er billigere, mere
modelmangfoldig, mere sportransparent og rammer den tunge korrekthed bedre.
Den eneste akse hvor auto-beta klarer sig **dårligere** er de lette
programmatiske opgaver (66,7% mod 100%) — udelukkende drevet af ét enkelt
routing-valg (P6 → `gemini-2.5-flash`), ikke et generelt mønster.

**2. Vælger auto-beta billigere modeller end auto gjorde? Rammer den
nogensinde det billigste rigtige panel-svar?**

Ja, entydigt billigere — se tabellen ovenfor (3,96× lavere totalomkostning,
og 56,3% af kaldene gik til faktiske, typisk billige panelmodeller mod 39%
for den gamle `auto`). Modelvalget skiftede fra "to mellemdyre generalister"
(gemini-3.6-flash, gpt-5.6-sol) til en spredning domineret af DeepSeek- og
GLM-varianter, som begge er blandt panelets billigste rækker.

Men — "rammer den det billigste rigtige panel-svar" har to forskellige svar
afhængigt af hvad spørgsmålet betyder:

- **Prismæssigt (slår den billigste-korrekte pris på cellen):** Ja, på 5/16
  celler (se punkt 2 i "Resultater"-afsnittet ovenfor).
- **Modelidentitetsmæssigt (vælger den bogstaveligt den samme model som er
  panelets billigste-korrekte for den celle):** **Aldrig.** Panelets
  billigste-korrekte model er `gemma_4` på 14 af 16 celler (og `deepseek_v4`
  på de to resterende: `code/baseline`, `finance_interp/baseline`) — men
  auto-beta valgte aldrig `gemma_4` en eneste gang, og på `code/baseline`
  gik den til `deepseek-v4-flash-0731` (en ANDEN DeepSeek-variant end den
  pinnede `deepseek-v4-pro` som er panelets faktiske `deepseek_v4`-række).
  Auto-beta har ingen adgang til vores facit eller prisliste — dens billige
  valg er en konsekvens af dens egen task-klassifikation + spend-share-logik,
  ikke en tilfældig konvergens mod vores specifikke "korrekte svar"-definition.

**3. Routing-metadata: blev session-stickiness aktiveret?**

Ingen `user`-felt, intet session-id blev sendt på noget af de 80 kald —
verificeret direkte i `run_auto_beta.py`'s `_base_extra_body()` (samme
metode brugt i hele projektets øvrige OpenRouter-adaptere) og logget
eksplicit som `session_id_sent: false`/`plugins_param_sent: false` på hver
række i JSONL'en.

**Modelvalget var 100% stabilt inden for hver celle** (0/16 split, se punkt 1)
— hvilket i sig selv hverken beviser eller modbeviser en 5-minutters-cache:
den gamle `auto` (heller ingen session-id) viste næsten samme mønster
(kun 1/16 split), så prompt-stabil routing ser ud til at være en generel
egenskab ved OpenRouters Auto-familie, ikke et symptom på cache-pinning
alene.

Det stærkeste enkeltstående bevis MOD skadelig stickiness er derimod:
**`served_by` (backend) varierede på tværs af pass i 6 af de 16 model-stabile
celler**, selvom modelvalget holdt sig fast (fx `finance_calc/baseline`:
BaseTen/CoreWeave/BaseTen/BaseTen/CoreWeave over de 5 pass). Hvis kaldene
blev serveret fra en fuldt cachet/pinnet session, ville man forvente samme
backend hver gang — det ses ikke. Routeren træffer altså et reelt,
uafhængigt backend-valg per kald, selvom dens model-niveau-beslutning ofte
lander det samme sted for identisk prompt-indhold.

**Ærlig begrænsning:** denne kørsel havde ingen parallel kontrolgruppe med et
bevidst sat session-id at sammenligne mod — den eneste konklusion der kan
drages er "vi introducerede ingen grund til stickiness, og backend-valget
tyder på at der IKKE er nogen fuld cache-pinning i spil", ikke et
vandtæt bevis for routerens interne cache-adfærd.

## Forbehold i denne debrief

- **Dato-bundet politik.** Denne kørsel er bundet til 2026-08-05. Auto-beta's
  spend-share-vindue (community spend-share er en del af dens
  routing-logik, per registerets §6.1-note) ruller løbende — resultatet er
  et øjebliksbillede, ikke en fast egenskab ved routeren. Et gentag om en
  måned kan ramme en helt anden modelfordeling.
- **Default-dial 9** — denne kørsel testede udelukkende platformens egen
  default cost_quality_tradeoff (9), aldrig sat eksplicit af scriptet. En
  bruger der selv skruer på dialen (lavere = mere kvalitetsfokuseret, højere
  = endnu billigere, per OpenRouters egen skala) ville formentlig se en
  anden fordeling. Denne kørsel siger noget om "hvad en almindelig køber der
  aldrig rører knappen får", ikke om routerens fulde register.
- **Auto-beta er ikke en panel-deltager** og hører ikke i leaderboardet — en
  kandidat bedømt mod facit, samme status som den gamle `auto`-kørsel.
- Prissammenligningen bruger panelets 2026-06-26-snapshot mod auto-beta's
  dagsaktuelle 2026-08-05-priser (40 dages forskel, længere end den gamle
  `auto`'s 30 dage).
- P6's 0/5-korrekthed er ét enkelt routing-valg (→ `gemini-2.5-flash`), ikke
  bevis for at denne model generelt er svag på logik — for lille et
  stikprøvegrundlag til at generalisere ud over "denne specifikke opgave, i
  denne specifikke kørsel".
- Router-overhead-tallet for de lette celler er bevidst udeladt af
  konklusionen (se punkt 6) pga. `thinking_budget`-uoverensstemmelse med
  panelets historiske data — kun de tunge celler (samme budget begge sider)
  bruges til overhead-konklusionen.

## Ikke rørt

`results/heavy/`, `results/full/`, `datasite/data/reasoning-data.json`,
`docs/reasoning_findings.md`, `config/pricing.yaml`, `config/panel.yaml`,
`run_auto_router.py`, `results/auto/20260726T111445_auto.jsonl`.

---

## TILLÆG (2026-08-05): Judge-run på de 35 dommer-egnede lette celler

Formål: efterprøve kvalitetspåstanden i routing-diskussionen (registerets
§6.1: "Auto optimerer muligvis kvalitet/hastighed, ikke pris") — leverer
auto-beta's billige, spredte modelvalg svar der er lige så legible som
panelets egne modeller, eller er billigheden købt med et kvalitetstab der
bare ikke viser sig i correctness-tallene?

**Setup:** `judge_auto_beta.py`, ny standalone-fil, rører ikke
`run_auto_beta.py`. 35 rækker (P1/P2/P3/P4/P8/P9/P10 × 5 pass) fra
`results/auto/20260805T080708_autobeta.jsonl`, dømt blindt af de samme to
dommere i de samme (udaterede) versioner som `panel.yaml` altid har brugt —
`minimax/minimax-m3` og `google/gemini-3.1-pro-preview`. Begge blev
bekræftet stadig live i OpenRouters kataloge før scriptet blev skrevet;
ingen af dem har nogensinde haft en dateret pin at miste, så "samme
version" er den samme udaterede slug som producerede `judges-light-new.json`
— ingen substitution var nødvendig, og STOP-betingelsen udløste derfor ikke.
Samme rubrik: `src/judge.py`s `_RUBRIC_TEMPLATE`, uændret (bekræftet
byte-identisk med `src/judge_rubric.py`s `ANCHORED_RUBRIC_TEMPLATE` — der
er reelt kun én rubrik i kodebasen i dag). Samme to dimensioner som
`judges-light-new.json`: redundans + kohærens — ingen separat
"kvalitet/korrekthed"-dimension findes i skemaet eller i `src/judge.py`s
`DIMENSIONS`, så ingen ny dimension er opfundet til denne kørsel. Blind per
konstruktion: rubrikteksten nævner aldrig modelidentitet eller routing.
Pris: **$0,3569** af $3-loftet, 35/35 celler, ingen fejl, ingen stop.

**BEVIDST AFVIGELSE fra panelets setup — læs dette før tabellerne:**
panelets Phase 2 dømmer altid `raw_reasoning_trace`, aldrig `answer_text`
(`run.py`: `trace_text = row.get("raw_reasoning_trace") or ""`). Denne
kørsel dømmer **`answer_text`** for alle 35 rækker, efter eksplicit
instruktion. To grunde: (1) det var en direkte instruktion, ikke betinget af
panelets praksis; (2) det er den eneste måde P8-cellen kunne bedømmes
overhovedet — P8 blev routet til `anthropic/claude-sonnet-5`, som gav
`trace_status="absent"` (intet brugbart reasoning-spor), præcis den
betingelse panelets egen Phase 2 bruger til at EKSKLUDERE en model helt
(`LEGIBILITY_EXCLUDED` dækker `claude_sonnet_4_6`/`opus_4_8` af samme
grund). **Konsekvens: sammenligningerne nedenfor er IKKE et rent
æbler-mod-æbler-mål.** Svar er kortere og mere strukturerede end rå
tænkespor næsten per definition — enhver models FÆRDIGE svar vil typisk
score bedre på denne rubrik end enhver models RÅ tænkespor, uanset
routing. Dette skal holdes for øje gennem hele afsnittet.

### 1. Score-tabel per opgave

| Opgave | Routet til (auto-beta) | Auto-beta red. (median af 5 pass) | Auto-beta koh. (median) |
|---|---|---|---|
| P1 | deepseek-v4-flash-0731 | 1,0 | 5,0 |
| P2 | deepseek-v4-flash-0731 | 1,0 | 5,0 |
| P3 | deepseek-v4-pro | 1,0 | 5,0 |
| P4 | deepseek-v4-pro | 1,0 | 5,0 |
| P8 | claude-sonnet-5 | 1,0 | 5,0 |
| P9 | glm-5.2 | 1,5 | 5,0 |
| P10 | glm-5.2 | 1,5 | 5,0 |

Bemærkelsesværdigt lidt spredning: alle 7 opgaver ligger i et snævert bånd
(redundans 1,0-1,5, kohærens konsekvent 5,0), uanset hvilken af de fem
forskellige routede modeller der svarede. To dommere var også stort set
enige med hinanden på denne kørsel: gennemsnitlig absolut uenighed 0,34
(redundans) / 0,09 (kohærens), **ingen** af de 70 vurderinger nåede
høj-uenigheds-tærsklen (≥2). Det er konsistent med loft-effekt: færdige,
korte svar har simpelthen mindre plads til at variere på denne skala end
rå tænkespor har.

### 2. Sammenligning mod panelets scorer på samme opgaver

Panelets tal er fra `datasite/data/reasoning-data.json` (gennemsnit af de
samme to dommere, RÅ TÆNKESPOR — se afvigelsesnoten ovenfor):

| Opgave | Auto-beta red. | Gemma red. | DeepSeek red. | GLM red. | Panel-median red. | Auto-beta koh. | Panel-median koh. |
|---|---|---|---|---|---|---|---|
| P1 | 1,0 | 1,5 | 1,5 | 1,0 | 1,5 | 5,0 | 4,5 |
| P2 | 1,0 | 2,0 | 2,5 | 2,0 | 2,0 | 5,0 | 4,5 |
| P3 | 1,0 | 1,5 | 3,5 | 2,0 | 2,5 | 5,0 | 4,5 |
| P4 | 1,0 | 2,0 | 2,0 | 1,5 | 2,0 | 5,0 | 4,0 |
| P8 | 1,0 | 1,5 | 4,0 | 3,5 | 4,0 | 5,0 | 4,5 |
| P9 | 1,5 | 3,0 | 3,0 | 2,0 | 3,0 | 5,0 | 4,5 |
| P10 | 1,5 | 4,0 | 1,5 | 3,5 | 3,5 | 5,0 | 4,5 |

Samlet (35 vs. 35 datapunkter): auto-beta redundans gns. **1,17** (median
1,0) mod panelets gns. **2,73** (median 2,5). Auto-beta kohærens gns.
**4,96** (median 5,0) mod panelets gns. **4,31** (median 4,5). Auto-beta
scorer bedre på **hver eneste** af de 7 opgaver, på begge dimensioner, uden
undtagelse.

**Dette skal IKKE læses som "auto-betas modeller ræsonnerer mere legibelt
end panelets."** Det er forventeligt og reelt uinformativt om selve
ræsonnementets legibilitet: vi sammenligner et FÆRDIGT SVAR mod et RÅT
TÆNKESPOR. Et tænkespor indeholder pr. natur udforskning, fejlspor og
selvkorrektion, som et endeligt svar aldrig viser — det er redigeret ned
til konklusionen. Forskellen måler primært hvilket artefakt der blev dømt,
ikke hvilken model der producerede det.

### 3. P8 særskilt

**Faktuel rettelse først:** P8 er IKKE en empati-opgave — det er
`code_bug` (en Python-funktion med en fejl, der skal findes og forklares;
se `data/prompts.yaml`). Note fortsætter alligevel med den substantielle
del af spørgsmålet, da P8 rent faktisk er den eneste celle af de 7 der blev
routet til en model uden for de fire billige DeepSeek/GLM-varianter.

Sonnet 5 (den dyreste model auto-beta valgte i dette scope, og den eneste
uden rå tænkespor) scorer **red=1,0, koh=5,0** — identisk med, ikke bedre
end, de billigt routede cellernes bedste tal (P1-P4, også red=1,0/koh=5,0).
**Nej, den leverer ikke målbart bedre kvalitet** på dette mål end de billige
valg. Men givet loft-effekten fra punkt 1 (næsten alle 35 celler klumper i
et meget snævert topbånd), har dette mål reelt meget lidt diskriminerende
kraft ved n=5 — en "ingen forskel"-konklusion her er lige så meget et
udtryk for målets ufølsomhed på svar-niveau som et bevis på ægte lighed i
underliggende svarkvalitet.

### 4. Konklusion

**Delvist — og strengt taget ikke afgørende afprøvet.** Auto-betas svar er
konsekvent meget legible på dette mål, uden nogen svaghed synlig i de 7
dømte celler; det modsiger ikke påstanden om at billig routing ikke koster
kvalitet her. Men fordi denne kørsel dømmer svar mod panelets tænkespor
(se afvigelsesnoten), kan den hverken bekræfte eller afkræfte "samme
kvalitet som panelet" med den stringens registeret ellers kræver — en
egentlig test ville skulle dømme RÅ TÆNKESPOR for de fire routede modeller,
der faktisk har ét (`deepseek-v4-flash-0731`, `deepseek-v4-pro`, `glm-5.2`,
`gemini-2.5-flash` havde alle `trace_status="raw"` i kildedataen), mod
panelets egne tænkespor-scorer, og efterlade kun P8/Sonnet-5 som
svar-baseret undtagelse. Det er ikke gjort her — ville kræve ny
dommer-kørsel og nyt prisloft-samtykke.

### Forbehold

- **Dommer-scorer er ordinaler, ikke facit** — en gennemsnitlig forskel på
  under 1 skalapunkt bør ikke over-fortolkes som en kvalitativ forskel.
- **n=5 per celle.** Selv med enighed mellem de to dommere er fem pass et
  spinkelt grundlag for at generalisere ud over denne specifikke kørsel.
- **Blind gradering fjerner model-bias, ikke stil-bias.** Dommeren ved ikke
  hvilken model der svarede, men kan stadig favorisere en bestemt
  svarstil (fx struktureret med overskrifter) som nogle modeller
  systematisk producerer og andre ikke gør — det er ikke kontrolleret for
  her.
- **Dato-bundet**, som resten af beta-målingen — kørt 2026-08-05, samme
  forbehold om routing-politikkens og spend-share-vinduets bevægelighed som
  hovedafsnittet ovenfor.
- **Svar-mod-spor-artefaktforskellen (se afvigelsesnoten) er den største
  enkeltstående begrænsning** i denne tillægsanalyse — vigtigere end de
  fire forbehold ovenfor tilsammen for at forstå hvad tallene rent faktisk
  viser.

### Ikke rørt (tillæg)

`judges-light-new.json`, `judges-heavy.json`, `datasite/data/reasoning-data.json`,
`docs/reasoning_findings.md`, `results/auto/20260805T080708_autobeta.jsonl`
(kun læst, ikke ændret), `results/auto/20260726T111445_auto.jsonl`,
`run_auto_beta.py`, `run_auto_router.py`.

Output: `results/auto/judges-autobeta.json` (nyt, gitignored som resten af
`results/`). Registeret opdateres IKKE her — Lars fører selv resultatet ind
i §6.2.
