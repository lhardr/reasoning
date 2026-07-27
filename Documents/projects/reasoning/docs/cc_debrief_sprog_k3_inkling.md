# CC-debrief: Sprogets pris — supplement (kimi_k3 + inkling)

run_id: `20260727T082305_sprog_k3_inkling` — `results/sprog/20260727T082305_sprog_k3_inkling.jsonl` (36 rækker)
Original run til sammenligning: `results/langcost/20260626T162923_langcost_full.jsonl` (90 rækker, 5 modeller) + `results/syntese/sprogets_pris_data.md`
Samlet omkostning: **$0,1121** af $3,00-loftet. Ingen fejl.

## Hvad blev ændret

1. **Preflight/første forsøg fejlede korrekt, rettet i egen commit**: mit script kopierede `run_full()`s `hard_errors`-gate ved en fejl. Den stoppede før noget kald blev lavet, fordi `kimi_k3`/`inklings` daterede OpenRouter-pins ikke findes i det live katalog — en kendt, dokumenteret falsk positiv (samme grund til at `run_heavy()` i `run.py` bevidst IKKE gater på dette tjek, kun printer det til orientering). Rettet til at følge `run_heavy()`s egen konvention før andet forsøg.
2. **`run_langcost_k3_inkling.py`** (ny fil): standalone runner, genbruger `save_langcost_result`/`save_langcost_trace` uændret — samme skema som originalkørslen. 6 opgaver (M1–M6) × 3 sprog (da/en/zh) × 1 pass × 2 modeller = 36 kald. `thinking_budget=16384`, `reasoning_effort="high"` — identisk med originalen og resten af panelet.

Begge commits pushet til `origin/main` før kørslen; `git log origin/main..HEAD` var tomt før start (og igen efter fejlrettelsen, før genforsøget).

## Resultater — de 5 spørgsmål

### 1. Tænkesprog per celle

**Reasoning-tokens, gennemsnit/median per model/sprog** (samme format som originalrapportens tabel 1):

| Model | da avg | da med | en avg | en med | zh avg | zh med | da/en | zh/en |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| kimi_k3 | 63 | 38 | 61 | 28 | 89 | 46 | 1.03 | 1.46 |
| inkling | 388 | 398 | 298 | 218 | 638 | 313 | 1.30 | 2.14 |

**Reasoning-tegn, gennemsnit/median** (tabel 2-format):

| Model | da avg | da med | en avg | en med | zh avg | zh med | da/en | zh/en |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| kimi_k3 | 227 | 160 | 222 | 120 | 300 | 165 | 1.02 | 1.35 |
| inkling | 1396 | 1314 | 1301 | 847 | 1466 | 611 | 1.07 | 1.13 |

**Krydstabel prompt_lang × primary_trace_language** (tabel 5-format, n=6 per model/sprog):

| Model | da→ | en→ | zh→ |
|---|---|---|---|
| kimi_k3 | en:5 uklassificeret:1 | en:4 uklassificeret:2 | en:5 uklassificeret:1 |
| inkling | en:5 da:1 | en:6 | en:4 vi:1 zh-cn:1 |

"Uklassificeret" = sporet var for kort til sikker sprogdetektion (`switch_count_confidence: "no_text"`), ikke fravær af spor. K3s korteste spor (M1/da: 10 reasoning-tokens, 31 tegn) var typisk bare `"Answer in Danish, max 80 words."` — en engelsk meta-instruktion til sig selv, ikke ægte ræsonnement.

### 2. K3 mod K2.7

**Ja, mønstret holder — og er skærpet.** K3 tænker **aldrig** på dansk eller kinesisk i noget af de 18 celler i dette forsøg: 13/18 klassificeret som `en`, 5/18 for korte til klassifikation, **0/18** `da` eller `zh-cn`. Til sammenligning viste K2.7 i originalkørslen stadig lejlighedsvise native-sprog-hit: `da:1` af 6 på danske prompts, `zh-cn:1` af 6 på kinesiske. K3 har altså mistet den rest-native-kapacitet K2.7 stadig havde — versionsspringet gjorde den MERE engelsk-låst, ikke mindre, konsistent med registerets 1.5-fund om at K3 "forlod det åbne felt" adfærdsmæssigt på let-økonomi.

**Det indholds-adaptive mønster (engelsk default, dansk på tunge danske jura-opgaver) kan IKKE direkte efterprøves her** — M1–M6 indeholder ingen juridisk opgave (kun factual/math/logic/code_structure/code_bug/open_analysis). Det jeg KAN sige: selv på de tre høj-belastnings-opgaver i dette sæt (M2 math, M3 logic, M6 open_analysis) forbliver K3 konsekvent engelsk, uanset promptsprog. Det modsiger ikke panelfundet — det bekræfter blot at triggeren dengang var juridisk TERMINOLOGI, ikke generel belastning, og dette forsøg har ingen sådan opgave at teste triggeren på. Åbent spørgsmål, ikke besvaret af denne kørsel.

### 3. Inkling: hvilken type?

Ingen fast firetypologi findes dokumenteret i repoet (gennemsøgt `docs/`, `report/`, handover-filerne — intet "fire typer"-skema fundet). Jeg udleder den derfor selv af de fulde 7 rå-spor-modellers mønstre (de 5 originale + K3 + Inkling), eksplicit som min egen kategorisering, ikke en etableret standard:

- **Type A — universelt engelsk** (Gemma): tænker på engelsk uanset promptsprog, 18/18.
- **Type B — genuint tosproget** (DeepSeek): følger promptsproget substantielt på både dansk (da:3/en:3 i original) og kinesisk.
- **Type C — kinesisk-native, dansk-engelsk** (GLM, K2.7, Mistral i original; K3 nu ren engelsk-udgave af samme familie): overvejende kinesisk-native på zh, men engelsk-default på dansk.
- **Type D — længde/indsats-afhængig skifter** (ny, set her): engelsk som standard, men bryder over i promptens sprog specifikt på sine LÆNGSTE, mest arbejdskrævende spor.

**Inkling er Type D.** Dens to genuine native-sprog-hit — `da` på M5 og `zh-cn` på M6 — er SAMTIDIG dens to længste spor i hele datasættet: M5/da har 707 reasoning-tokens/2476 tegn/14 segmenter (dansk kode-bug-opgave), M6/zh har 2311 tokens/4147 tegn/29 segmenter/12 sprogskift (kinesisk åben-analyse-opgave, hendes desidert dyreste celle). Alle 16 øvrige celler (kortere spor) er engelsk. Det er ikke set hos nogen af de andre 6 modeller — hverken DeepSeeks konsistente split eller GLM/K2.7/Mistrals kinesisk-kun-mønster korrelerer med sporlængde på denne måde. Én anomali noteret men ikke over-fortolket: M3/zh klassificeres som `vi` (vietnamesisk) — sandsynligvis en klassifikator-fejlklassifikation på et kort, blandet segment (3 skift, 4 segmenter), ikke en reel sprogbevægelse.

### 4. Tegn per token per sprog (kodningsskat)

| Model | da tg/tok | en tg/tok | zh tg/tok |
|---|---:|---:|---:|
| kimi_k3 | 3.62 | 3.65 | 3.38 |
| inkling | 3.60 | 4.36 | 2.30 |

Begge modeller viser det forventede mønster fra originalrapporten: **lavere tegn/token på kinesisk** (1,5–3 forventet for CJK-tokenisering, matcher her: K3 3.38, Inkling 2.30) mod 3,6–4,4 for dansk/engelsk. **Kendt forbehold gentaget**: en lav zh tg/tok kan afspejle tokenizerens effektivitet (kodningsskat), ikke kortere tænkning — og for begge modeller her tænker de FAKTISK på engelsk selv ved zh-prompt (jf. spg. 1–2), så zh-kolonnens tegn/token-tal måler i praksis engelsk teksts kinesiske token-kodning, ikke kinesisk tænkning. Inklings da vs. en (3.60 vs. 4.36): tokens stiger PÅ engelsk relativt til tegn — svag indikation af at engelsk her er den dyrere kodning for Inkling på dette lille sæt, modsat den generelle "kinesisk billigst"-forventning; givet n=6 per celle er dette indikativt, ikke konklusivt.

### 5. Forbehold

- **Kinesiske oversættelser er stadig ikke efterprøvet af en kyndig taler** — samme forbehold som originalkørslen, arvet uændret fra `data/prompts_multilang.yaml`s header. Alle konklusioner fra zh-sessioner (inkl. `vi`-anomalien i spg. 3) er indikative.
- **n=1 per celle** — hver (model, opgave, sprog)-kombination er ét enkelt kald. Ingen af tallene ovenfor har spredning at vise; range/varians kan ikke beregnes fra denne kørsel alene. Sammenlign med originalkørslens egen advarsel (afsnit 3, sprogets_pris_data.md): to enkeltkørsler dengang var 10–20× atypiske og forvred gennemsnit uden at ændre retning. Samme risiko gælder hver eneste celle her — en enkelt kørsel kan være en outlier uden at der er noget at sammenligne den med i dette datasæt.
- K3s meget lave reasoning-forbrug på flere celler (9–19 tokens) betyder korte spor og dermed lav klassifikations-tillid (5/18 "uklassificeret") — ikke en fejl, men en konsekvens af adaptiv tildeling på simple opgaver (jf. registerets 1.5).

## Ikke rørt

`results/langcost/20260626T162923_langcost_full.jsonl` (original 90-kalds-data, uændret), `results/syntese/sprogets_pris_data.md` (original rapport, uændret — dette er et NYT, separat dokument), `run.py` (ingen ændringer — `LANGCOST_MODELS` stadig kun de oprindelige 5), `data/prompts_multilang.yaml`, `docs/reasoning_findings.md`, `config/panel.yaml`/`config/pricing.yaml` (ingen nye modeller — kimi_k3/inkling var allerede i panelet fra Opus 5-arbejdet).
