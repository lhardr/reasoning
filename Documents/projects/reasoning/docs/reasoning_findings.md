# Reasoning-findings register

Ét sted for alle verificerede indsigter i reasoning-serien. Hver post: påstand,
tal, kilde, forbehold, status. Rapporter opdateres ved opslag heri, ikke fra
hukommelse. Bygges tema for tema.

Status-koder: **BEKRÆFTET** (står i data) · **RETTET** (tidligere tal var
forkert, nyt tal her) · **BLOKERET** (afventer data) · **NY** (ikke i nogen
rapport endnu).

Datagrundlag: 12 modeller (+ Claude Opus 5 tilføjet 2026-07-27 som
post-panel versionsspring, jf. 5.7 — medregnes med * hvor den indgår i
rankings), 16 opgaver (10 lette danske P1-P10, 3 tunge
H1-H3 i to betingelser). Tunge: 5 gennemløb per celle. Kilde-jsonl i
results/. Konsolideret i datasite/data/reasoning-data.json.

Panelet: **åbne (7)** gemma_4 31B tæt, kimi_k2_7 32B, glm_5_2 40B,
inkling 41B, deepseek_v4 49B, kimi_k3 ~50B, mistral_medium_3_5.
**lukkede (5)** claude_sonnet_4_6, opus_4_8, fable_5, gpt_5_5, gpt_5_6_sol.
Aktive params = per token (MoE). Mistral og de lukkede: størrelse ukendt.

Run-modes (tre, ikke to): **let** = 1 gennemløb per prompt (10 prompts).
**tung** = 5 gennemløb per celle (3 opgaver × 2 betingelser). **varians-suite**
= dedikeret repro-kørsel, 2 gennemløb på let (alle 10 prompts, baseline),
5 gennemløb på tung (samme celler som hoved-suiten, separat run) —
adskilt fra "let" og "tung" ovenfor, ikke en fjerde variant af dem.

METODENOTE (cost_usd): `cost_usd` i alle jsonl er ALTID listepris ×
faktiske tokens, opslået i config/pricing.yaml (src/cost.py) — aldrig
en reelt faktureret sum. Verificeret 2026-08-10: genberegning af
`cost_usd` fra pricing.yaml's satser mod den loggede værdi giver 0,00%
afvigelse på 330 stikprøve-rækker på tværs af fire modeller, uanset
hvilken backend (`served_by`) kaldet gik igennem. Satserne i
pricing.yaml er verificeret mod udbydernes offentlige priser (kilde
noteret per model i filen); for Opus 5 specifikt også krydstjekket mod
et OpenRouter-kalds egne `usage.cost_details`. Konsekvens: enhver
"pris per token"-sammenligning i dette register (5.4, 5.7, m.fl.) er en
sammenligning af listepriser, ikke af reelt differentieret
kanal-/backend-omkostning — se dedup-risiko-noten i TEMA 2 for hvorfor
det specifikt ikke kan afgøre kanaleffekter for Fable 5/Opus 5
(Amazon Bedrock) vs. Sonnet 4.6/Opus 4.8 (Anthropic direkte).

---

## TEMA 1 — Reasoning spend & kvalitet

### 1.1 Reasoning-median, let og tung, alle 12 · BEKRÆFTET
| Model | Let | Tung | Aktive |
|---|---|---|---|
| Claude Fable 5 | 52 | 32 | lukket |
| Claude Opus 4.8 | 50 | 34 | lukket |
| Claude Sonnet 4.6 | 81 | 37 | lukket |
| GPT-5.6 Sol | 68 | 103 | lukket |
| GLM 5.2 | 720 | 474 | 40B |
| Kimi K2.7 | 428 | 492 | 32B |
| GPT-5.5 | 350 | 409 | lukket |
| DeepSeek V4 | 962 | 682 | 49B |
| Inkling | 550 | 686 | 41B |
| Kimi K3 | 44 | 741 | ~50B |
| Mistral Med 3.5 | 1068 | 914 | ? |
| Gemma 4 | 448 | 1192 | 31B tæt |

Kilde: reasoning-data.json, median over hhv. 10 lette og 3 tunge (baseline).

### 1.2 Korrekthed differentierer ikke · BEKRÆFTET, to tal RETTET
Alle 12 løser stort set alt. Facit-bærende (H1-H3 × 2 betingelser, 30 løb/model):
Fable, Opus, Sonnet, Sol, GLM, DeepSeek, Mistral = 30/30. GPT-5.5, Gemma,
Kimi K2.7 = 29/30. Inkling 28/30. Kimi K3 = 30/30: patch-runnet
20260719T195912 udfylder de 2 manglende H2T-pass (HTTP 429), begge korrekte.
Datasitet er patchet 2026-07-21 (K3 H2T n=5). NB: regraded-jsonl
viser Inkling 26/30; de 2 ekstra fejl er loop-artefakt-rækker (fælde 3c,
python_exec-syntaks lækket som tekst) som kun er rettet i datasitet.
Kanonisk korrekthed = reasoning-data.json. Korrekthed er derfor IKKE en
skelne-akse på dette sæt; hele serien handler om ØKONOMI ved samme korrekthed.

### 1.3 Ekstra tænkning køber ikke ekstra korrekthed · BEKRÆFTET
Kimi K3 på kode-opgaven, samme prompt, 5 løb: reasoning 663-4018 tokens, alle
5 korrekte. Med værktøj 552-1632, alle 5 korrekte. En 6x forskel i tænkning
på identisk input giver samme resultat. De ekstra tokens er ikke dybde.
Kilde: reasoning-data.json kimi_k3 H1/H1T.

### 1.4 Ekstra tokens = redundans, IKKE for K3 · NY + nuance
Dommer-redundans (1 lav, 5 høj) mod tung reasoning:
Fable/Opus/Sonnet redundans 1,0 (og tænker 30-52). Mistral 4,0 (tænker 1482).
Kimi K2.7 3,0. **MEN Kimi K3: redundans 1,0 trods 818 reasoning-tokens.**
K3 tænker meget UDEN at være redundant — den er selektiv, ikke ordrig.
Det modsiger den simple "flere tokens = mere redundans"-hypotese.
Kvalitativt (spor): K3 og GLM efterprøver opgavens egne påstande før de
bygger videre på dem (fx verificerer K3 et opgivet primtal ved prøvedivision
— disciplineret forsigtigheds-spend, aldrig cirkulært; i et andet pass
springer den tjekket over og løser samme opgave på en tredjedel af
tokens); DeepSeek stoler på det givne og springer det over.
NB: forsigtigheds-spend er IKKE et forbillede — det er samme familie som
DeepSeeks dato-genudledning — kun et rent eksempel på at volumen og spild
er uafhængige akser.
Kilde: judges-heavy.json + rå spor. FORBEHOLD: dommer-rubrik kalibreret på
danske lette opgaver; overført til engelsk kode/finans (se 1.6).

### 1.5 K3's modulering: den lærte at skelne · NY (vigtigst i tema)
K2.7 → K3, samme laboratorium. K2.7: let 428, tung 492 = faktor 1,1 (ét gear).
K3: let 44, tung 741 = faktor 16,8 (mest i panelet).
På LETTE opgaver forlod K3 det åbne felt og sluttede sig til de lukkede
frontier-modeller: de 5 mest sparsommelige på let er Fable 52, Opus 50,
K3 44, Sol 68, Sonnet 81 — fire lukkede + K3, eneste åbne i det selskab.
Læren: versionsspringet gav K3 ADAPTIV TILDELING, en frontier-egenskab.
Ikke "dyrere og tungere" — den sparer hvor den kan, skruer op hvor det kræves.
FORBEHOLD: 44 er ét løb per prompt; K3's HØJESTE lette måling var 325, stadig
under hver anden åben models median. Faktor 16,8 er delvist lavt-nævner-artefakt;
retningen (skelner hvor K2.7 ikke gjorde) står uafhængigt.
Kilde: reasoning-data.json + 20260720T084300/090336_full.

### 1.6 Redundans-skala: let vs tung · NY forbehold
De 7 modeller i begge suiter: redundans-gns 2,31 (let) → 2,74 (tung), +18%.
Båret af 2 modeller: Gemma +1,72, K3 +1,10; de 5 øvrige inden for 0,3.
Kan være ægte adfærd (netop de to prøvedividerer i hovedet), ikke rubrik-drift.
CC's oprindelige "skala skred" byggede på skæv sammenligning (kun de 4 nye
lette, som er de leaneste). Reelt skift er mildt og modelspecifikt.
Kilde: judges-light-new.json + judges-heavy.json.

---

## TEMA 2 — Tokenspend & varians

Konvention (deklareret her, gælder hele registeret), TO FORSKELLIGE
AGGREGERINGER, IKKE ÉN: **tunge tal er median af opgave-medianer** (hver
opgaves egen median regnes først over dens gentagne gennemløb, baseline,
med dedup-reglen at seneste run vinder per celle — recaps erstatter
20260709-cellerne), **lette tal er ét fladt median direkte over
prompt-rækkerne** — der er ingen opgave-gruppering at nestle i på let, så
et enkelt let-tal er det flade median over modellens prompt-rækker (10
rækker, ét gennemløb hver, i hovedsuiten; 20 rækker, 10 prompts × 2 pass, i
varians-suiten). At anvende tung-metoden på lette tal (eller omvendt) giver
et andet, forkert tal uden varsel — se 2.1's tidligere version for et
eksempel på præcis denne fejl. Verificeret at 1.1-tabellen og 2.1 allerede
følger denne konvention efter rettelsen 2026-08-10 (eksakt reproduktion af
alle 12 gamle celler i begge suiter). Lette tal er juni-runnet for de 8
gamle modeller, juli-runnet for de 4 nye.

DEDUP-KODE (rettet 2026-08-10, se `scripts/compute_findings.py::_dedup`):
to overlappende filer med SAMME run_id (20260709T093542_heavy.jsonl og dens
`_corrected`-søster) adskiller sig kun på `correct`/`grading_detail` i
79/240 celler — tokens er identiske, så ingen token-baseret post i dette
register var nogensinde ramt. Den faktiske kode (ikke min engangs-
analyseskript, som brugte en anden — og mindre korrekt — sammenligning)
valgte allerede `_corrected` ved uafgjort, men kun ved et tilfælde af
alfabetisk filsortering (`.` < `_`, så `_heavy.jsonl` sorteres før
`_heavy_corrected.jsonl`) kombineret med "seneste-behandlede-vinder" — ikke
en deklareret regel. Rettet til en eksplicit `_dedup_priority()`
(run_id primært, `_corrected`/`_recap`-filnavn som eksplicit
uafgjort-regel), dækket af `tests/test_compute_findings.py`, verificeret
som no-op mod nuværende `results/` (byte-identisk output før/efter).

### 2.1 Reasoning-andel af billed tokens · BEKRÆFTET + ny nuance, Mistral let-tal RETTET 2026-08-10
reasoning/(reasoning+output), median per model:

| Model | Let | Tung (baseline) |
|---|---|---|
| DeepSeek V4 | 80% | 95% |
| GPT-5.5 | 65% | 81% |
| Kimi K2.7 | 72% | 79% |
| Kimi K3 | 17% | 72% |
| Inkling | 78% | 72% |
| GLM 5.2 | 69% | 70% |
| Mistral Med 3.5 | 73,3% | 61% |
| Gemma 4 | 60% | 60% |
| GPT-5.6 Sol | 26% | 53% |
| Opus 4.8 | 11% | 24% |
| Fable 5 | 9% | 22% |
| Sonnet 4.6 | 22% | 20% |
| Opus 5 | 14,9% | 20,8% |

"Reasoning er hovedposten" gælder de åbne modeller og GPT-5.5. For
Anthropic-modellerne er billed-forbruget output-domineret (reasoning kun
20-24% på tunge opgaver). K3's 17% på let er adaptiv tildeling (se 1.5).
RETTELSE: Mistrals lette tal stod tidligere som 66% — det var taget fra
recap-filen (20260714T101953_juni_recap_mistral.jsonl), ikke den kanoniske
juni-kørsel som resten af registeret bruger (samme enkelt-run-konvention
som 2.5 erklærer kanonisk for 1.1-tabellen). Den kanoniske juni-kørsel giver
73,3%. Det flytter Mistral fra sidst i det høj-reasoning-segment til FØRST
foran GLM (69%), GPT-5.5 (65%) og K2.7 (72%) i den lette rangorden — kun
DeepSeek (80%) og Inkling (78%) ligger stadig over.
Kilde: jsonl (full + heavy, dedup), regnet 2026-07-20, Mistral-let og
Opus 5 tilføjet 2026-08-10.

### 2.2 Aktiv-parameter-båndet · SVAG TENDENS (nedgraderet fra mønster 2026-08-10), K3-tal RETTET
De fire åbne MoE i samme klasse, median reasoning over BEGGE tunge
betingelser: K2.7 32B → 432, Inkling 41B → 570, DeepSeek 49B → 587,
K3 ~50B → 609,5 (tidligere citeret 702 — regnet UDEN korrektionsfilen
20260719T195912_heavy.jsonl, som retter to fejlede pass, status=error,
tokens=None, i K3's CDNS/2015-invited_auto-celle; et endnu ældre 610-tal
kunne heller ikke reproduceres, uændret ukendt oprindelse).
Rækkefølgen K2.7 < Inkling < DeepSeek < K3 holder stadig efter rettelsen,
MEN trinnet DeepSeek → K3 krymper fra 115 tokens (702−587, 19,6%) til
22,5 tokens (609,5−587, 3,8%) — inden for det 2.3 viser som ren
celle-til-celle-varians for åbne modeller på identisk input. Båndet er
derfor IKKE et mønster der forudsiger K3's placering; det er en svag
tendens hvor K3 og DeepSeek reelt er ens inden for støj. Baseline alene
bryder ordenen i forvejen (442/686/648/663, uændret af rettelsen — den
beskadigede celle er invited_auto, ikke baseline). Og båndet gælder kun de
fire: Gemma 31B TÆT ligger på 1192 og Mistral på 914-1051, langt over.
Arkitektur og lab-konvention slår størrelse. Læses som fire datapunkter med
svag korrelation, ikke en lov og ikke længere en forudsigelse der holdt.
Kilde: heavy-jsonl, dedup, regnet 2026-07-20, K3 rettet 2026-08-10.

### 2.3 Varians på identisk input · median BEKRÆFTET, P90 og K3 RETTET, Opus 5 tilføjet
Tunge celler, samme run, 5 gennemløb, billed tokens (reasoning+output),
78 celler (13 modeller, Opus 5 tilføjet 2026-08-10): median 1,90x, P90
4,16x (tidligere ">5x", holder ikke efter recap-dedup; 72-celle-tallet var
1,95x/4,22x), max 26,7x. Per model (median af max/min per celle):
Sonnet 1,14x strammest; Opus 5 1,31x; Fable 1,32x; GPT-5.5 1,41x; Sol
1,45x; Opus 4,8 1,50x; Mistral 2,06x; DeepSeek 2,09x; Gemma 2,20x (max
26,7x); Inkling 2,30x; GLM 2,62x; K2.7 3,57x (max 24,7x); K3 3,82x
(tidligere citeret 3,60x — samme rodårsag som 2.2: regnet uden
korrektionsfilen 20260719T195912_heavy.jsonl på K3's CDNS/2015-invited_auto-
celle; max 10,4x uændret, den celle er upåvirket, "9x"-observationen
bekræftet fortsat).
Lukkede er systematisk mere deterministiske end åbne — PÅ TUNGE OPGAVER.
På LETTE opgaver bryder mønsteret: Gemma (åben, 1,09x) er strammere end
både Sol (lukket, 1,12x) og K3 (åben, 1,17x).
Lette opgaver (varians-run, nu 13 modeller inkl. Opus 5, 2 pass, 130
celler): median 1,12x, P90 1,79x, max 23,6x (samme DeepSeek-outlier som
80-celle-tallet; de 5 nye modeller er som gruppe strammere end de gamle 8
og trækker begge percentiler svagt ned fra 1,13x/1,87x).
FORBEHOLD: sampling ikke pinnet på tværs af udbydere; rangorden mellem
modeller kan delvist være udbyder-defaults (fælde 5).
Kilde: variance-jsonl + heavy-jsonl, regnet 2026-07-20, K3/Opus 5/130-celle-
genberegning 2026-08-10.

### 2.4 Ligningen med empiriske vægte · BEKRÆFTET med Opus 5 (uændret konklusion)
tokens = model × prompt × ε(model). Dekomposition af log(billed), tung
baseline, n=195 (13 modeller, Opus 5 tilføjet — tidligere n=180/12
modeller gav 54%/27%/6%/13%): model-leddet 53,4%, opgave-leddet 28,0%,
interaktion model×opgave 6,1%, ren stokastik inden for celler 12,5%. Alle
fire andele flytter sig ≤1 procentpoint — ren decimalændring, konklusionen
står uændret.
Hvem du hyrer betyder dobbelt så meget som hvad du beder om, og en
sjettedel af regningen er støj ingen kan styre.
Kilde: heavy-jsonl baseline, regnet 2026-07-20, genberegnet med Opus 5
2026-08-10.

### 2.5 Mistrals spild er budget-uafhængigt · BEKRÆFTET, grundlag afklaret
Recappen ved 16384 (10 lette prompts) afkræfter at spildet var et
budget-artefakt: på P1 (120-ords-opgaven) tæller Mistral stadig ord
16 gange og bruger 3514 reasoning-tokens. Topprompterne blev DYRERE
ved højere budget (P10: 3584 → 4802), så juni-toppen var reelt klemt,
men midterprompterne halverede (P3 1044→548, P7 541→262) — det er
modellens egen run-til-run-varians, ikke cap-release. Let-median:
juni 1068, recap 653, pooled n=20: 906. KANONISK: 1068 beholdes i
1.1-tabellen (samme enkelt-run-konvention som de øvrige 11), med denne
post som varians-note. Spild-karakteristikken (redundans 4,0, dårligst
kalibreret, ordtælling i loop) står uafhængigt af budget og run.
Kilde: 20260714T101953_juni_recap_mistral.jsonl + juni-full, spor læst.

---

## TEMA 3 — Tooluse

Ratioer = cellemedian invited_auto / cellemedian baseline, median over de
tre tunge opgaver. Gen = reasoning+output. Tot = input+reasoning+output.
Grebsrate = andel invited-løb med mindst ét tool-kald.

### 3.1 Værktøjer fordyrer for dem der griber · BEKRÆFTET, tal RETTET
Panel-median tot-ratio 1,31x (tidligere citeret 1,40x, afvigelsen er
recap-dedup). Dyrest: Sonnet 3,40x (tidligere "3,32x for Claude"),
Fable 2,93x, Opus 2,90x. Cost-ratio for Anthropic-trioen 2,3-2,4x.
VIGTIG kontrol: nul-griberne (Gemma, GPT-5.5, Sol, 0% greb) ligger på
0,88-1,28x i tot-ratio UDEN et eneste tool-kald. Betingelses-variansen
alene er altså op til ±25%, så ratioer nær 1 er støj, ikke effekt.
DOBBELTTJEK 2026-07-20: median-ratioerne er stabile på tværs af dedup
(kun Gemma 0,88↔1,02 og Mistral 1,17↔1,22 flytter sig, begge inden for
støjbåndet). Grebsrater krydstjekket mod raw_tool_events: 0 mismatch på
178 invited-løb. Det historiske "1,66x" er nu forklaret: det er samme
data under MEAN-aggregering (panel 1,68x), som skewede tool-løb puster
op (DeepSeek 1,32→1,76, K3 1,31→1,70). Median er konventionen, 1,31x
står.
Kilde: heavy-jsonl, dedup, regnet 2026-07-20.

| Model | Gen | Tot | Cost | Greb |
|---|---|---|---|---|
| Sonnet 4.6 | 1,93 | 3,40 | 2,39 | 100% |
| Fable 5 | 1,74 | 2,93 | 2,41 | 100% |
| Opus 4.8 | 1,71 | 2,90 | 2,33 | 93% |
| Kimi K2.7 | 1,34 | 2,25 | 1,62 | 87% |
| Inkling | 0,93 | 1,70 | 1,16 | 100% |
| DeepSeek V4 | 1,00 | 1,32 | 1,20 | 53% |
| Kimi K3 | 1,05 | 1,31 | 1,17 | 38% |
| GPT-5.6 Sol | 1,01 | 1,28 | 1,12 | 0% |
| Mistral | 1,05 | 1,17 | 1,08 | 7% |
| GPT-5.5 | 0,98 | 1,16 | 1,03 | 0% |
| GLM 5.2 | 0,53 | 1,16 | 0,75 | 67% |
| Gemma 4 | 0,74 | 0,88 | 0,80 | 0% |

### 3.2 Kun GLM og Inkling sænker genererede tokens · BEKRÆFTET, præciseret
Fem modeller har gen-ratio under 1, men tre af dem (Gemma 0,74,
GPT-5.5 0,98) greb aldrig — deres ratio er støj, jf. 3.1-kontrollen.
Blandt modeller der FAKTISK griber sænker kun GLM (0,53) og Inkling (0,93)
genererede tokens. GLM er desuden den eneste i panelet hvor værktøjer
sænker den samlede PRIS (cost-ratio 0,75): den veksler tung tænkning til
billige tool-runder. Inkling-mekanismen er kendt fra sporlæsning: den
drafter hele svaret i reasoning-tracen, så tool-resultater erstatter
egen-produktion. Kilde: heavy-jsonl + rå spor.

### 3.3 Grebsrate er en selvstændig egenskab · BEKRÆFTET
Spændet er fuldt, fra aldrig til altid, ved identisk invitation:
0% Gemma, GPT-5.5, Sol · 7% Mistral · 40% K3 (6/15 inkl. patch-run) ·
53% DeepSeek · 67% GLM · 87% K2.7 · 93% Opus · 100% Sonnet, Fable, Inkling.
Grebsrate følger
hverken størrelse, åben/lukket eller pris — den er et træningsvalg
(lab-signaturen udfoldes i tema 4). Kilde: heavy-jsonl invited_auto.

### 3.4 Ét-runde-loopet · HISTORISK, kan ikke genberegnes
De fire kanoniske heavy-filer indeholder ingen multi-runde tool-events
og ingen afbrudte finish_reasons — artefaktet er renset ud før/i de
korrigerede filer. Tallet "10/400 afbrudt" stammer fra
præ-korrektions-runs og kan ikke reproduceres fra det kanoniske
datagrundlag. Status: intern metode (fælde 3), ikke publicerbart fund.

---

## TEMA 4 — Open vs closed

Lukkede = Sonnet, Opus, Fable, GPT-5.5, Sol. Åbne = de syv øvrige.
Alle tunge tal på regraded-jsonl med pass-dedup (seneste run vinder per
pass, så patch-runs supplerer i stedet for at erstatte celler).

### 4.1 Grebsrate er en LAB-signatur, og den kan omtrænes · BEKRÆFTET + nuance
Anthropic griber næsten altid, på tværs af tre generationer: Sonnet 100%,
Opus 93%, Fable 100%. OpenAI griber aldrig, på tværs af to: GPT-5.5 0%,
Sol 0%. Signaturen overlever altså versionsspring hos begge huse.
MEN Moonshot beviser at den ikke er støbt i beton: K2.7 87% → K3 40%.
Grebsrate er et træningsvalg, ikke arkitektur, og åben/lukket forklarer
den ikke (åbne spænder 0-100%). Kilde: heavy-jsonl invited_auto.
OPDATERING 2026-07-27 (Opus 5-kørslen): Opus 5 griber 100% (15/15).
Anthropic-signaturen er nu 100/100/100 (Sonnet, Fable, Opus 5); kun den
ældre Opus 4.8 ligger på 93%. Signaturen står styrket.

### 4.2 Lukkede tænker mindst, med én undtagelse · BEKRÆFTET, præciseret
Tung baseline, cellemedian: Anthropic-trioen 32-37, Sol 103. Undtagelsen
er GPT-5.5 med 409, midt i det åbne felt. Det er altså den NYESTE lukkede
generation der tænker kortest (5.5→Sol er et 4x fald, se tema 5).
Kombineret med 2.1: lukkede modeller er output-dominerede, åbne er
reasoning-dominerede. To forskellige økonomier, ikke én skala.
Kilde: heavy-jsonl baseline.

### 4.3 Korrekt per dollar, korrigeret metode · NY (erstatter rapport 3's tabel)
Korrekte svar / FAKTISK sum cost_usd, tung, begge betingelser, korrekthed
fra datasitet (jf. 1.2-noten):
Gemma 1286 · DeepSeek 881 · GLM 364 · K2.7 260 · Inkling 185 · Sol 95 ·
Sonnet 91 · Opus 71 · Opus 5* 60 · GPT-5.5 54 · K3 50 · Mistral 36 ·
Fable 33 c/$. (*Opus 5 = post-panel-kørsel 2026-07-27, jf. 5.7.)
Åbne median 260, lukkede 71, forhold 3,7x. Fuldt spænd 38x ved samme
korrekthed (Gemma vs Fable). To åbne ligger i lukket-territorium: K3
(dyr per token-mængde) og Mistral (spild, jf. 2.5). Kilde: regraded
heavy-jsonl (cost) + reasoning-data.json (correctN), regnet 2026-07-20.

### 4.4 K3 vs Fable: modsatte strategier, samme score · BEKRÆFTET
Begge 30/30. Fable: 32 reasoning-tokens (cellemedian), latens 5,5s
baseline / 10,8s invited, 33 c/$. K3: 741 reasoning-tokens (23x mere),
latens 34,2s / 41,6s med hale til 142s, 50 c/$. Sol som tredje punkt:
103 tokens, 4,7s / 4,1s, 95 c/$, 30/30. Rangordenen VENDER med aksen:
per dollar vinder Gemma/DeepSeek, per minut vinder Sol/Opus/Sonnet.
Latens er en selvstændig akse, ikke en funktion af pris eller tokens.
(Handoverens "Sol 4,6s, Fable 9s, K3 36s" var blandede betingelser;
registeret deklarerer baseline/invited separat.) Kilde: latency_s.

### 4.5 Transparens-regimer i praksis · RETTET 2026-07-27
trace_status på tunge løb: alle syv åbne modeller leverer 100% rå spor.
OpenAI skjuler mest: GPT-5.5 count_only på 20/30, Sol på 16/30 (kun
tokentælling, ingen tekst). RETTELSE: Anthropics "raw"-rækker (12-15 per
model) er et mærknings-artefakt — tool_loop.py stempler ubetinget al
tænketekst under værktøjskald som "raw", men Anthropics API udleverer kun
opsummeringer. Reelt regime: Anthropic = summarized/absent, OpenAI =
count_only/absent. INGEN af de fem lukkede modeller leverede ét ægte råt
tankespor i hele forsøget. Aksen er ikke et miks, den er binær: åben =
læsbar, lukket = lukket. Suverænitets-pointen står dermed STÆRKERE: kun
på åbne modeller kan køberen overhovedet AFLÆSE tænkningen (sprog, spild,
præmisser, jf. knap 4-6 i essayet). De lukkede skal købes på output-tillid
alene. Om-mærkning af de historiske Anthropic-rækker udestår i en separat
arm (tool_loop.py-defekten er dokumenteret, ikke rettet).
Kilde: trace_status-felt, heavy, n=360 + cc_debrief_opus5.md.

---

## TEMA 5 — Versionsspring: tre huse, tre retninger

Samme laboratorium, forrige mod nyeste generation, alle tal regnet forfra
(lette: juni/juli-runs, n=1 per prompt; tunge: regraded pass-dedup).
Pris per mio tokens er impliceret (sum cost / sum tokens, tung).

### 5.1 Springtabellen · NY
| | K2.7 → K3 | GPT-5.5 → Sol | Opus → Fable |
|---|---|---|---|
| Reasoning let | 428 → 44 (0,10x) | 350 → 68 (0,19x) | 50 → 52 (1,04x) |
| Reasoning tung | 492 → 741 (1,51x) | 409 → 103 (0,25x) | 34 → 32 (0,94x) |
| Latens tung, base | 6,6s → 34,2s (5,2x) | 10,1s → 4,7s (0,46x) | 3,6s → 5,5s (1,5x) |
| Pris/mio tokens | 2,1 → 10,1 USD (4,8x) | 17,3 → 13,4 (0,77x) | 9,0 → 18,3 (2,0x) |
| Sum tung regning | 0,11 → 0,60 USD (5,6x) | 0,53 → 0,32 (0,59x) | 0,42 → 0,90 (2,1x) |
| Grebsrate | 87% → 40% | 0% → 0% | 93% → 100% |
| Korrekt tung | 28/30 → 30/30 | 29/30 → 30/30 | 30/30 → 30/30 |

### 5.2 Moonshot købte ADFÆRD · BEKRÆFTET (uddyber 1.5)
K3 fik adaptiv tildeling (let 0,10x, tung 1,51x, faktor 16,8 mod K2.7's
1,1), grebsraten blev omtrænet (87→40%), redundansen faldt til 1,0 trods
højt volumen, og korrektheden steg til 30/30. Prisen: 4,8x dyrere per
token og 5,2x langsommere. Moonshot flyttede K3 op i frontier-adfærd og
frontier-prissats i samme spring. Stil-kontinuitet (telegrafisk syntaks)
består fra K2.7, så det er samme slægt, nyt gear.

### 5.3 OpenAI købte EFFEKTIVITET · BEKRÆFTET
Alt faldt på én gang: tænkning 0,19-0,25x, latens 0,46x, samlet tung
regning 0,59x, pris per token 0,77x. Og korrektheden STEG (29→30).
Sol er panelets hurtigste model (4,7s median) og beviser at man kan
skære fire femtedele af tænkningen uden at røre resultatet — på dette
opgavesæt. Grebsraten forblev 0: OpenAI-signaturen står.

### 5.4 Anthropic solgte KAPACITET dette sæt ikke kan se · BEKRÆFTET, med forbehold
Fable opfører sig som Opus på alle målte akser: samme tænkevolumen
(0,94-1,04x), samme grebsmønster, samme 30/30. Men 2,0x pris per token,
2,1x samlet regning, 1,5x latens. På DETTE opgavesæt er springet ren
prisstigning: samme svar, dobbelt pris. FORBEHOLD: benchmarket kan ikke
måle kvalitet over korrekthedsloftet (jf. 1.2), så Fables merværdi kan
ligge i opgaver sættet ikke indeholder. Det er præcis trygheds-skattens
anatomi fra refleksionerne: man betaler for dygtighed man ikke behøver
her. Bemærk også 1.4-nuancen: Fables forbrug følger opgavetyngden tæt
(KARANTÆNE 2026-07-27: det citerede tal +0,84 har ingen dokumenteret
beregningsmetode i repoet og må ikke bruges før metoden er genudledt som
kode og kørt på alle modeller; den kvalitative påstand står) — den
TÆNKER klogt, den KOSTER bare dobbelt.

### 5.5 Tværlæsningen · NY (essay-bærende)
Tre huse brugte ét versionsspring på tre forskellige ting: Moonshot
købte adfærd (og hævede prisen), OpenAI købte effektivitet (og sænkede
den), Anthropic hævede prisen uden målbar adfærdsændring på dette sæt.
Versionsnummeret fortæller altså INTET om retningen — "nyere" kan
betyde billigere, dyrere eller bare anderledes. Endnu et argument for
at aflæse modellen frem for at stole på navnet.
Kilde: jsonl som ovenfor, regnet 2026-07-20. FORBEHOLD: lette tal n=1
per prompt; K3/GPT/Claude én backend hver; prissnapshots 2026-06-26.

### 5.6 Scope-forbehold: enkelttur, ikke agentisk · NY (gælder hele registeret)
Alle konklusioner gælder enkelttur-arbejde uden loops. Tre spor i egne
data antyder at et agentisk design kunne vende billedet:
(a) Grebsraten skifter fortegn: i dette harness kan opgaverne løses i
hovedet, så grib er ren udgift (Anthropic 2,9-3,4x uden gevinst). I et
loop hvor opgaven KRÆVER værktøjer, er grib-tilbøjelighed en
forudsætning. Egenskaben er målt i et miljø der straffer den.
(b) Ét-runde-loopet (3.4) var symptomet: Kimi og Inkling FORSØGTE at
iterere og blev afbrudt af harnesset. Designet var ikke bygget til loops.
(c) Kalibrering og latens er loop-egenskaber: Fables kalibrering (tal i
karantæne, jf. 5.4) betyder lidt
på én opgave ved korrekthedsloftet, men over en 50-skridts-bane
akkumulerer fejlallokering multiplicativt. Samme med latens: 4,7s mod
34s er en detalje på ét kald og en faktor 7 på en arbejdsdag af kald.
Konsekvens: 5.4's "samme svar, dobbelt pris" står for enkelttur, men
generaliserer ikke til agentiske workloads — og at ANTAGE at Fable
retfærdiggør prisen der, er trygheds-skatten med omvendt fortegn.
Essayets scope-afsnit skal sige enkelttur eksplicit. Agentisk benchmark
(kendt arbejdsgang, faste roller, jf. harness-pointen i refleksionerne)
er den naturlige opfølger.

### 5.7 Fjerde spring: Opus 4.8 → Opus 5 · NY (kørt 2026-07-27, verificeret)
Samme pris ($5/$25, bekræftet live), claude-opus-5 uden dato-suffiks.
| | Opus 4.8 | Opus 5 |
|---|---|---|
| Reasoning let | 50 | 76,5 (1,53x) |
| Reasoning tung (cellemedian, base) | 34 | 51 (1,5x) |
| Latens tung base / invited | 3,6s / — | 4,96s / 8,01s |
| Impliceret pris/mio tokens | 9,0 | 9,81 |
| Sum tung regning | $0,42 | $0,50 (1,2x) |
| Korrekt/dollar (tung, faktisk sum) | 71 | 60 |
| Grebsrate | 93% | 100% |
| Korrekt tung | 30/30 | 30/30 |
NB: cc_debrief_opus5.md angiver 4.8 som 28/30 — forkert, kanonisk er 30/30
(1.2, regraded). LÆSNING: modsat retning af husets første spring. Fable var
dobbelt pris uden adfærdsændring; Opus 5 er uændret pris med mild
adfærdsændring: 1,5x MERE tænkning på begge suiter (vender "nyeste lukkede
tænker mindst" — Sol skar 4x, Opus 5 hæver 1,5x; skalaen står: 51 er stadig
~9-23x under det åbne felt), greb fuldendt til 100%, og på VORES sæt en mild
økonomi-regression: samme svar som 4.8 til 1,2x regningen (71→60 c/$).
Anthropics påståede kapacitetsspring ligger igen over korrekthedsloftet —
trygheds-skattens anatomi gentaget, denne gang til uændret pris.
FORTOLKNING (afstemt mod Anthropics egne partner-tal: 1/7 reasoning-tokens
på tung trading, 26% færre på legal): Opus 5 ser ud til at have komprimeret
tænkeområdet fra toppen og hævet gulvet en anelse — gevinsterne ligger hvor
tænkningen var stor nok til at skære i, og på gulvet tænker den nye default
mere. Token-effektivitet er en egenskab ved model PÅ arbejdsbyrde, ikke ved
modellen. 5.5 står
stærkere: retningen skifter nu selv inden for ét hus.
Let-detalje: P7 fik 0 reasoning-tokens, P9/P10 fik 540-716 — Opus 5 KAN
slå tænkningen fra, men bruger mest let-reasoning af alle Anthropic-modeller.
Kilde: 20260727T062054_full.jsonl + 20260727T062551_heavy.jsonl,
cc_debrief_opus5.md, verificeret mod rådata 2026-07-27.

---

## TEMA 6 — Routing-kandidaten (perspektivering, ikke panelresultat)

### 6.1 OpenRouter Auto mod facit · NY (kørt 2026-07-26, dato-bundet) — VIGTIG ROUTER-VERSIONSNOTE 2026-07-27
80 kald, samme 16 opgaver, $1,11. Auto valgte kun 2 modeller: gemini-3.6-flash
(61%, uden for panelet) og Sol (39%). Økonomi: dyrere end billigste rigtige
panel-svar i 16/16 celler; 28x dyrere end ren Gemma-kørsel. Korrekthed:
28/30 tung (begge fejl én celle, harness-uforenelighed, ikke regnefejl) mod
panelets 98,6%. 53 c/$ — mellem K3 og GPT-5.5, blandt panelets to dårligste,
selvom Sol direkte scorer 95. Routing-lag koster selv: ~3x tokens / ~2x
latens på tunge tool-opgaver mod samme model kaldt direkte; intet overhead
på lette. FAIR LÆSNING (essay-bærende): Auto optimerer muligvis kvalitet/
hastighed, ikke pris — den besvarer et andet spørgsmål. En blanket-router
kan ikke kende prompt-leddet i tokens = model × prompt × ε(model) × tooluse
før svaret findes, så den må kollapse markedet til få generalister — og
opgiver dermed gevinsten ved modelvalget (54% af regningen, jf. 2.4).
Routing virker hvor variansen er lav (refleksionernes harness-pointe).
Auto hører IKKE i leaderboard/charts. Routing-politik kan skifte; resultat
bundet til 2026-07-26 (registeret citerede tidligere 07-21 — rettet; run-fil
20260726T111445_auto.jsonl). Kilde: results/auto/ + cc_debrief_auto_router.md.
ROUTER-VERSION (verificeret i rådata + OpenRouters docs 2026-07-27): vi
testede `openrouter/auto` — som OpenRouter nu selv markerer DEPRECATED
(NotDiamond-drevet, default cost_quality_tradeoff 7). Afloséren
`openrouter/auto-beta` router på task-klassifikation + community
spend-share med default cqt 9 (billigste ~femtedel af kandidaterne), og
OpenRouters egne benchmarks viser beta MARKANT bedre end auto (GPQA 83,8
mod 50,0; τ-bench 74 mod 34 ved quality-setting). KONSEKVENS: 6.1's tal
beskriver den udgående politik og må ikke publiceres som "markedets
router" uden denne note; auto-beta-kørsel på samme 16 opgaver udestår.
BEMÆRK også vinklen: auto-betas default-dial FAVORISERER billige modeller
— markedets nye router er rykket MOD seriens konklusion (rut billigt,
evidensbaseret). Det er en stærkere essay-pointe end kritikken af den
gamle.

### 6.2 OpenRouter Auto Beta mod facit · NY (kørt 2026-08-05, dato-bundet)
Samme 16 opgaver, 80 kald, DEFAULT settings (dial 9), ingen session_id.
Samlet $0,28 — 3,96x billigere end gamle auto. Valgte 5 modeller (auto: 2),
56,3% af kaldene til panel-medlemmer (auto: 39%).
CASTING (100% stabilt per celle, taksonomien aflæst af valgene):
deepseek-v4-flash-0731 (25 kald): kode-SKRIVNING (HumanEval ± tools) +
de simple opgaver (P1, P2, P7/JSON). deepseek-v4-pro (20): jura (P3, P4)
+ CDNS-finans ± tools. glm-5.2 (25): AMAT-finans ± tools + matematik (P5)
+ åbne analyser (P9, P10). gemini-2.5-flash (5): logikgåden P6 (fejlcast).
claude-sonnet-5 (5): kode-DEBUGGING P8 — kørslens eneste premium-valg.
Bemærk: routeren skelner kode-skrivning fra debugging, og dens jura-valg
er netop panel-modellen der udleder Langfredag fra bunden (fanget i 3/5
pass, jf. kvalitetslæsningen).
Tung korrekthed 30/30
(auto: 28/30). Korrekt per faktisk dollar: 406 — RANG 3 af 15 (12 panel +
Opus 5* + begge routere), kun bag
Gemma og DeepSeek selv (auto: 53, rang 10-11). Slår Gemmas pris på 5/16
celler, men rammer ALDRIG cellens billigste-korrekte panel-svar præcist
(den kender ikke vores facit/priser — strukturelt, ikke tilfældigt).
SVAGHEDEN: let-suitens programmatisk graderede opgaver 10/15, hele tabet
i ÉN celle: alle 5 pass af P6 (logikgåden) routet til gemini-2.5-flash som
fejlede hver gang — reproducerbart model/opgave-svagt punkt, ikke et
generelt mønster. Stabilitet: modelvalg 100% stabilt inden for celler
(0/16 split; auto 1/16); served_by varierede i 6 celler trods fast model
(taler imod fuld session-caching, ikke kontrolleret bevis).
LÆSNING (essay-bærende, afløser 6.1's ramme): markedets router er
konvergeret mod seriens svar — task-klassifikation + spend-share + billig
default leverer næsten panel-økonomi uden at kende opgaverne. De to
rest-lærdomme: (a) en router kan aldrig slå at kende sit eget opgavesæt,
for den har ingen adgang til din facit; (b) fejltilstanden har skiftet
karakter — fra systematisk overbetaling (auto) til enkeltstående blinde
pletter (P6), som spend-share-signalet ikke kan se fordi det måler hvad
folk BRUGER, ikke hvad der VIRKER på din opgave. At aflæse modellen på
egne opgaver forbliver derfor det sidste, uerstattelige led.
OVERHEAD-NOTE (regnet 2026-08-05): på cellerne hvor beta routede til
panel-medlemmer (DeepSeek Pro/CDNS, GLM/AMAT) er input-tokens IDENTISKE
med direkte kald (1,00-1,02x) — beta injicerer ingen målbar wrapper.
Gamle autos ~3x/2x-overhead var dens egen stack, ikke routing-konceptets.
Den ene forhøjede celle (GLM/AMAT tools, 1,69x total) er grebs-adfærd
(GLM greb via beta, typisk ikke direkte), altså 3.1-effekten, ikke router.
Latens-sammenligninger på tværs af kørselsdage er ikke retvisende og
krediteres ingen.
JUDGE-RUN (2026-08-05, $0,36, begge panel-dommere pinnet OK, blind):
de 7 dommer-opgaver × 5 pass graderet. HOVEDFORBEHOLD FØRST: der blev
graderet answer_text, mens panelets judge-run graderer
raw_reasoning_trace — nødvendigt for at dække P8-cellen (Sonnet 5, intet
spor), men det gør tallene IKKE like-for-like mod panelet. Med den ramme:
beta-svarene scorede bedre end panelet på alle 7 opgaver (redundans 1,17
mod 2,73; kohærens 4,96 mod 4,31) — hvilket i vidt omfang forklares af at
færdige svar er kortere og renere end rå tænkespor, ikke af mere læselig
reasoning. RETTELSE: P8 er code_bug (Python-debugging), IKKE en
empati-opgave som tidligere antaget i chat/judge-brief — læsningen
"routeren sender menneske-opgaven til Anthropic" TRÆKKES TILBAGE; den
korrekte læsning er at routeren sender debugging til Sonnet 5. Sonnet 5
scorede identisk med de billige valg (1,0/5,0) — ceiling-effekt, metrikken
diskriminerer ikke ved n=5. KONKLUSION på kvalitetsspørgsmålet: DELVIST —
intet afkræfter "samme kvalitet", men answer/trace-mismatchet gør at det
heller ikke er afgjort. Reel test ville være trace-baseret gradering af de
fire åbne routede modeller (30 rækker, udestår, valgfri).
Kilde: results/auto/judges-autobeta.json + cc_debrief_auto_beta.md-tillæg.
DATAGRUNDLAGS-NOTE (OpenRouters egen dokumentation, læst 2026-08-05):
routerens evidens = forbrugs-metadata (tokens/spend/modelvalg, beholdes
altid) + "Anonymous Input Categorization": stikprøver af brugernes
prompts læses og klassificeres i opgavetyper til rankings/routing.
Prompts/svar gemmes ellers ikke som default; opt-in logging giver ifølge
tredjepartslæsninger af ToS OpenRouter uigenkaldelig kommerciel brugsret
(VERIFICER mod ToS før citat); primært US-infrastruktur.
MOAT-POINTEN (essay-bærende): denne evidens kan kun samles af den der
sidder på massiv trafik PÅ TVÆRS af modeller — aggregatorer, og i egen
niche produkt-ejere som Cursor. Labs ser kun egne modeller; aggregatoren
alene ser alle modeller på identiske arbejdsbyrder. Routing-kvalitet er
en funktion af trafik-udsyn, og køberen betaler med eksponering (to hop,
sampling, US-infra). Symmetri: serien læser modellernes spor, routeren
læser brugernes prompts — evidens skal komme et sted fra; spørgsmålet er
hvis.
ØKONOMI MOD ÉN-MODEL-STRATEGIER (samme 80-kalds-arbejdsbyrde; lette summer
skaleret ×5 fra n=1; panelpriser snapshot 2026-06-26 mod betas augustpriser
— estimater, ikke facit):
| Ren kørsel | USD | Router USD | Diff USD | Diff % |
|---|---|---|---|---|
| Fable 5 | 2,65 | 0,28 | +2,37 | +89% |
| Opus 5 | 2,42 | 0,28 | +2,14 | +88% |
| GPT-5.5 | 1,68 | 0,28 | +1,40 | +83% |
| Mistral | 1,66 | 0,28 | +1,38 | +83% |
| Opus 4.8 | 1,23 | 0,28 | +0,95 | +77% |
| Kimi K3 | 1,03 | 0,28 | +0,75 | +73% |
| Sol | 0,97 | 0,28 | +0,69 | +71% |
| Sonnet 4.6 | 0,79 | 0,28 | +0,51 | +65% |
| Inkling | 0,49 | 0,28 | +0,21 | +43% |
| Kimi K2.7 | 0,31 | 0,28 | +0,03 | +9% |
| GLM 5.2 | 0,26 | 0,28 | −0,02 | −8% |
| DeepSeek V4 | 0,10 | 0,28 | −0,18 | −186% |
| Gemma 4 | 0,04 | 0,28 | −0,24 | −600% |
LÆSNING: routeren slår VANEN, ikke hjemmearbejdet — 65-89% besparelse mod
flagskibs-default (ved samme målte korrekthed), men taber 3-7x til en
velvalgt billigste model (som ovenikøbet løser P6). Routerens værditilbud
= forsikring mod ikke at kende sin arbejdsbyrde + ukendt fremtidig trafik.
TRYGHEDS-SKAT-EFTERSKRIFT (essay-bærende): routeren AFLASTER skatten —
den følte sikkerhed ("en kompetent tager sig af det") leveres nu af
routing-laget til en brøkdel af prisen, og med bedre begrundelse end
flagskibs-vanen (evidens om hvad tusinder faktisk bruger til opgavetypen:
crowd-sourcet tryghed). MEN skatten afskaffes ikke, den skifter valuta:
fra overpris per token til delegeret tillid uden audit. P6-fejlcastet er
hvad DEN regning ser ud som når den forfalder: fem identiske fejl,
usynlige for alle der stolede, fordi opdagelsen var det man outsourcede.
Tre valutaer, samme skat: flagskibet koster kroner, routeren koster
kontrol, hjemmearbejdet koster arbejde. Ingen fjerde mulighed.
FORBEHOLD: dato-bundet; spend-share-vinduet ruller (7 dage), så resultatet
er et øjebliksbillede; default-dial 9. Kilde: results/auto/ (auto-beta-run)
+ docs/cc_debrief_auto_beta.md (commit 8fa65b4).

### 6.3 Fire scenarier, tre valutaer · NY (essay-bærende slutsten, Lars' taksonomi)
1. MONO-MODEL FLAGSKIB: koster PENGE. 65-89% overpris på ordinært arbejde
(jf. økonomitabellen) mod enkelhed og følt sikkerhed — sikkerhed målingerne
viser man mest ikke behøver på dette opgaveniveau.
2. DATADREVET 3.-PARTS-ROUTER (auto-beta-typen): koster KONTROL. Sparer
størstedelen af flagskibs-præmien, men betales i delegeret tillid uden
audit, lejlighedsvise usynlige fejlcasts (P6) og dataeksponering til
routing-laget (sampling + metadata; bredere ved opt-in logging — citat
SKAL følge 6.2-datanotens præcision, ikke "harvests your data").
3. HJEMMEBYGGET ROUTER: koster ARBEJDE, løbende — og har en skjult fork.
MED egne målinger: bedst af alle verdener (egne casting-regler, egen
facit, nær-optimal pris; dekompositionen 2.4 viser at grov
opgavetype-mapping fanger næsten hele gevinsten) — men vedligeholdet er
reelt: 8/13 model-pins stale på få uger i vores eget repo. UDEN egne
målinger (LLM-gætteren): kortets værste hjørne — byggeomkostning plus
blinde pletter, uden nogens evidens bag valgene.
4. MANUEL CASTING I CUSTOM HARNESSES: koster ARBEJDE, per opgave.
Maksimal kontrol, kvalitet og økonomi; skalerer præcis så langt som
opmærksomheden rækker.
PRINCIP: routing er en deployment-detalje, hjemmearbejdet er evidensen —
enhver router, købt, lejet eller bygget, er præcis så god som den facit
den ruter på. Fire scenarier, tre valutaer: penge, kontrol, arbejde.
Der findes ingen fjerde valuta.
Citat-præcision: "my 5 test runs" = fem gennemløb af ÉN opgave i
beta-kørslen.

---

## TEMA 7 — Tænkesproget (Sprogets pris-forsøget)

Kilde for alle tre poster: sprog_afsnit_opdateret_igen.md (seks kultur-
neutrale opgaver × tre sprog × fem åbne modeller). Tallene er IKKE
genverificeret fra jsonl i denne session — genverificering udestår.

### 7.1 Prompt-sproget styrer ikke tænkesproget · BEKRÆFTET (fra forsøgsdok)
Samlet: dansk prompt → dansk tænkning 33%, kinesisk prompt → kinesisk 53%,
engelsk prompt → engelsk 100%. Engelsk er tyngdepunktet modellerne falder
tilbage til. Fire typer: Gemma altid engelsk (18/18); DeepSeek og Mistral
spejler prompt-sproget pålideligt; GLM taber dansk til engelsk men holder
kinesisk; Kimi K2.7 falder tilbage til engelsk SELV fra kinesisk prompt
(5/6) — forsøgets mest kontraintuitive fund. NB: fundet er målt på K2.7;
K3 og Inkling var ikke med i forsøget. PARTIEL VERIFICERING 2026-07-27
(fra panelets lette juli-kørsler, rå spor): K3 tænker fortsat overvejende
engelsk på danske prompts (~7-8/10), MEN skifter til dansk på de to tunge
danske jura-opgaver (P3, P4) — muligt indholds-adaptivt sprogvalg, forbehold:
flere K3-spor er 8-46 tokens. Kinesisk-prompt-påstanden kan IKKE
ekstrapoleres til K3 uden ny kørsel (suppleringskørsel K3+Inkling planlagt).
Køber-pointe: skal tænkningen
kunne læses på dansk, er det en egenskab der testes per model; kun DeepSeek
og Mistral leverede det pålideligt.

### 7.2 Ingen universel "dansk er dyrere" i reasoning · BEKRÆFTET (fra forsøgsdok)
Det dyreste sprog afhænger af modellen: Mistral ræsonnerede TUNGERE på de
engelske udgaver end de danske (alle 6 opgaver, ~1,5x tænke-tokens — mod
forventningen); GLM omvendt ægte dyrere på dansk (1,36x tokens, 1,18x tegn);
DeepSeek flad på tværs. Feltet rummer både et tilfælde for og imod.

### 7.3 Kodningsskatten er lille; kinesiske tal kun indikative · BEKRÆFTET (fra forsøgsdok)
Tegn per token skiller tænkning fra tokenizer: dansk/engelsk ens (3,3-4,4),
så token-forskelle dér er ægte tænkning; dansk kodningsskat ~10%. Kinesisk
hakkes i små stykker (1-2,5 tegn/token) og ser token-tungt ud af tekniske
grunde alene — kan ikke sammenlignes direkte. FORBEHOLD: 14/30 kinesiske
kald faldt tilbage til engelsk tænkning; kinesiske oversættelser ikke
efterprøvet af kyndig taler; to outlier-kørsler (Mistral en 13606, DeepSeek
zh 7137) holdt ude af konklusionerne — uden DeepSeek-outlieren er zh/en-
forholdet 1,26, altså ingen forskel.
