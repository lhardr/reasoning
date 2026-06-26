# Sprogets pris — data-note

> **Forbehold:** Resultaterne er betinget af oversættelsernes troskab, særligt de kinesiske (zh) varianter. De kinesiske prompts er maskinoversat med engelsk som pivot-sprog og er ikke verificeret af en kyndig taler. Alle konklusioner fra zh-sessioner er indikative, ikke endelige, indtil oversættelserne er efterprøvet.

**Kilde:** `20260626T162923_langcost_full.jsonl` — 90 records
**Modeller:** deepseek_v4, glm_5_2, kimi_k2_7, gemma_4, mistral_medium_3_5
**Sprog:** da, en, zh
**Opgaver:** M1–M6 (6 kultur-neutrale opgaver)
**thinking_budget:** 16384 (generøst og ens for alle modeller)

## 1. Sprog-tax i tokens (reasoning_tokens)

Gennemsnitlige reasoning-tokens per model og sprog over de 6 opgaver. da/en og zh/en er forholdene: >1 = det sprog bruger flere tokens end engelsk.

| Model | da | en | zh | da/en | zh/en |
|---|---:|---:|---:|---:|---:|
| deepseek_v4 | 298 | 316 | 1440 | 0.94 | 4.56 |
| glm_5_2 | 592 | 434 | 378 | 1.36 | 0.87 |
| kimi_k2_7 | 158 | 319 | 141 | 0.49 | 0.44 |
| gemma_4 | 359 | 335 | 328 | 1.07 | 0.98 |
| mistral_medium_3_5 | 1654 | 4068 | 1562 | 0.41 | 0.38 |

## 2. Sprog-tax i tegn (reasoning_chars)

Antal tegn i det rå trace-tekst per model og sprog. Tegn er et tokenizer-uafhængigt mål: en stigning her er ægte ekstra tekst.

| Model | da | en | zh | da/en | zh/en |
|---|---:|---:|---:|---:|---:|
| deepseek_v4 | 986 | 1398 | 2005 | 0.71 | 1.43 |
| glm_5_2 | 2162 | 1832 | 873 | 1.18 | 0.48 |
| kimi_k2_7 | 609 | 1257 | 503 | 0.48 | 0.40 |
| gemma_4 | 1346 | 1250 | 970 | 1.08 | 0.78 |
| mistral_medium_3_5 | 5949 | 14854 | 1808 | 0.40 | 0.12 |

## 3. Dekomponering: tegn per reasoning-token

Hvis **tokens stiger** men **tegn ikke gør** (tegn/token-forholdet falder), er det en ren **kodningsskat** — det samme indhold kræver flere tokens at repræsentere på det pågældende sprog. Hvis **både tokens og tegn stiger** (forholdet er stabilt), er det **ægte ekstra tænkning** — modellen ræsonnerer faktisk mere.

| Model | da tg/tok | en tg/tok | zh tg/tok | Konklusion (da vs en) |
|---|---:|---:|---:|---|
| deepseek_v4 | 3.3 | 4.4 | 1.4 | da billigere end en |
| glm_5_2 | 3.7 | 4.2 | 2.3 | Ægte ekstra tænkning (tok↑ og tegn↑) |
| kimi_k2_7 | 3.9 | 3.9 | 3.6 | da billigere end en |
| gemma_4 | 3.7 | 3.7 | 3.0 | Ægte ekstra tænkning (tok↑ og tegn↑) |
| mistral_medium_3_5 | 3.6 | 3.7 | 1.2 | da billigere end en |

_Note: Kinesisk bruger typisk 1.5–3 tegn per token (effektiv tokenisering af unicode-tegn), mod 3–6 tegn per token for latin-baserede sprog. En lav zh tg/tok kan afspejle tokenizerens effektivitet, ikke kortere tænkning._

## 4. Krydstabel: prompt_lang × primary_trace_language

Substrat-kontrollen: får dansk prompt modellen til at tænke på dansk, eller falder den tilbage på engelsk? Poolet over alle modeller og alle 6 opgaver.

| prompt_lang | da | en | zh-cn | n |
|---|---:|---:|---:|---:|
| da | 10 (33%) | 20 (67%) | 0 (0%) | 30 |
| en | 0 (0%) | 30 (100%) | 0 (0%) | 30 |
| zh | 0 (0%) | 14 (47%) | 16 (53%) | 30 |

_For per-model opdelinger: filtrer JSONL-filen på `model_key` og `language_metric.primary_trace_language`._

## 5. Pris per sprog per model (USD)

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
