# Sprogets pris — data-note

> **Forbehold:** Resultaterne er betinget af oversættelsernes troskab, særligt de kinesiske (zh) varianter. De kinesiske prompts er maskinoversat med engelsk som pivot-sprog og er ikke verificeret af en kyndig taler. Alle konklusioner fra zh-sessioner er indikative, ikke endelige, indtil oversættelserne er efterprøvet. Derudover endte 14 af de 30 kinesiske kald med at tænke på engelsk, så zh-kolonnen blander ægte kinesisk tænkning med tilbagefald, og zh-tallene er kun indikative.

**Kilde:** `20260626T162923_langcost_full.jsonl` — 90 records
**Modeller:** deepseek_v4, glm_5_2, kimi_k2_7, gemma_4, mistral_medium_3_5
**Sprog:** da, en, zh
**Opgaver:** M1–M6 (6 kultur-neutrale opgaver)
**thinking_budget:** 16384 (generøst og ens for alle modeller)

## 1. Sprog-tax i tokens (reasoning_tokens)

Gennemsnit og median per model og sprog over de 6 opgaver. Medianen er robust mod enkeltstående outlier-kørsler. da/en og zh/en er gennemsnitsbaserede forhold: >1 = det sprog bruger flere tokens end engelsk.

| Model | da avg | da med | en avg | en med | zh avg | zh med | da/en | zh/en |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| deepseek_v4 | 298 | 188 | 316 | 234 | 1440 | 344 | 0.94 | 4.56 |
| glm_5_2 | 592 | 482 | 434 | 335 | 378 | 312 | 1.36 | 0.87 |
| kimi_k2_7 | 158 | 129 | 319 | 121 | 141 | 114 | 0.49 | 0.44 |
| gemma_4 | 359 | 336 | 335 | 276 | 328 | 318 | 1.07 | 0.98 |
| mistral_medium_3_5 | 1654 | 1132 | 4068 | 1444 | 1562 | 1224 | 0.41 | 0.38 |

## 2. Sprog-tax i tegn (reasoning_chars)

Gennemsnit og median for antal tegn i det rå trace-tekst. Tegn er et tokenizer-uafhængigt mål: en stigning her er ægte ekstra tekst, ikke blot kodning.

| Model | da avg | da med | en avg | en med | zh avg | zh med | da/en | zh/en |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| deepseek_v4 | 986 | 563 | 1398 | 880 | 2005 | 508 | 0.71 | 1.43 |
| glm_5_2 | 2162 | 1816 | 1832 | 1384 | 873 | 728 | 1.18 | 0.48 |
| kimi_k2_7 | 609 | 508 | 1257 | 512 | 503 | 410 | 0.48 | 0.40 |
| gemma_4 | 1346 | 1272 | 1250 | 1038 | 970 | 842 | 1.08 | 0.78 |
| mistral_medium_3_5 | 5949 | 4168 | 14854 | 5593 | 1808 | 1408 | 0.40 | 0.12 |

## 3. Outlier-robusthed

To enkeltkørsler er markant atypiske og forvrider gennemsnitstallene i tabel 1 og 2. Median-kolonnerne ovenfor er immune, men forholdene (da/en, zh/en) er gennemsnitsbaserede og påvirkes.

**Outlier 1 — mistral_medium_3_5, M1, lang=en:**
13 606 reasoning-tokens og 48 814 tegn — ca. 10× mere end Mistrals typiske engelske kørsel (median: 1 444 tokens). Denne ene kørsel puster Mistrals en-gennemsnit op fra 2 160 til 4 068 tokens og trækker en/da-forholdet fra ~1.5 til ~2.5 (M1 fratrukket begge sider). **Retningen holder dog på alle seks opgaver:** Mistral bruger konsekvent flere tokens på engelsk end på dansk, uanset om M1 medregnes eller ej.

**Outlier 2 — deepseek_v4, M6, lang=zh:**
7 137 reasoning-tokens og 9 357 tegn — ca. 20× mere end DeepSeeks typiske kinesiske kørsel (median: 344 tokens). Denne ene kørsel driver næsten hele zh/en-forholdet: ~4.56 med M6, men ~1.26 uden (M6 fratrukket begge sider). DeepSeeks kinesiske zh/en-forhold på 4,56 bør ikke tolkes som et generelt mønster.

## 4. Dekomponering: tegn per reasoning-token

Hvis **tokens stiger** men **tegn ikke gør** (tegn/token-forholdet falder), er det en ren **kodningsskat** — det samme indhold kræver flere tokens at repræsentere på det pågældende sprog. Hvis **både tokens og tegn stiger** (forholdet er stabilt), er det **ægte ekstra tænkning** — modellen ræsonnerer faktisk mere.

| Model | da tg/tok | en tg/tok | zh tg/tok | Konklusion (da vs en) |
|---|---:|---:|---:|---|
| deepseek_v4 | 3.3 | 4.4 | 1.4 | da billigere end en |
| glm_5_2 | 3.7 | 4.2 | 2.3 | Ægte ekstra tænkning (tok↑ og tegn↑) |
| kimi_k2_7 | 3.9 | 3.9 | 3.6 | da billigere end en |
| gemma_4 | 3.7 | 3.7 | 3.0 | Ægte ekstra tænkning (tok↑ og tegn↑) |
| mistral_medium_3_5 | 3.6 | 3.7 | 1.2 | da billigere end en |

_Note: Kinesisk bruger typisk 1,5–3 tegn per token (effektiv tokenisering af unicode-tegn), mod 3–6 tegn per token for latin-baserede sprog. En lav zh tg/tok kan afspejle tokenizerens effektivitet, ikke kortere tænkning._

## 5. Krydstabel: prompt_lang × primary_trace_language

Substrat-kontrollen: får dansk prompt modellen til at tænke på dansk, eller falder den tilbage på engelsk? Her vises mønstret per model (n=6 per celle — ét kald per opgave), så modelspecifik adfærd er synlig.

| Model | da→ (6 kald) | en→ (6 kald) | zh→ (6 kald) |
|---|---|---|---|
| deepseek_v4 | da:3 en:3 | en:6 | zh-cn:5 en:1 |
| glm_5_2 | en:5 da:1 | en:6 | zh-cn:5 en:1 |
| kimi_k2_7 | en:5 da:1 | en:6 | en:5 zh-cn:1 |
| gemma_4 | en:6 | en:6 | en:6 |
| mistral_medium_3_5 | da:5 en:1 | en:6 | zh-cn:5 en:1 |

**Poolet total (alle modeller, alle 6 opgaver, n=30 per sprog):**
da→ en: 67% / da: 33%  
en→ en: 100%  
zh→ zh-cn: 53% / en: 47%

## 6. Pris per sprog per model (USD)

Samlet pris over alle 6 opgaver, fordelt på sprog og model.

| Model | da | en | zh | Total |
|---|---:|---:|---:|---:|
| deepseek_v4 | $0.00230 | $0.00218 | $0.00790 | $0.01238 |
| glm_5_2 | $0.01497 | $0.00985 | $0.01033 | $0.03515 |
| kimi_k2_7 | $0.00700 | $0.00868 | $0.00539 | $0.02108 |
| gemma_4 | $0.00122 | $0.00104 | $0.00109 | $0.00335 |
| mistral_medium_3_5 | $0.09834 | $0.20146 | $0.07595 | $0.37576 |
| **Total** | **$0.12384** | **$0.22322** | **$0.10066** | **$0.44772** |

---

*Auto-genereret af `run.py --langcost-report`. Kilde: `20260626T162923_langcost_full`.*
