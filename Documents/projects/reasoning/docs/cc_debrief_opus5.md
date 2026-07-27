# CC-debrief: Claude Opus 5 (fjerde version-spring, Opus 4.8 → Opus 5)

run_id (let): `20260727T062054_full` — `results/full/20260727T062054_full.jsonl` (10 rækker)
run_id (tung): `20260727T062551_heavy` — `results/heavy/20260727T062551_heavy.jsonl` (30 rækker)
Kørt via nyt standalone-script `run_opus5_panel.py` (samme mønster som `fable_5`/`kimi_k3`/`gpt_5_6_sol`/`inkling` — `run.py`s `FULL_MODEL_ORDER`/`HEAVY_MODELS` er stadig ikke udvidet, se "Afvigelser" punkt 1).
Samlet omkostning: **$0.8860** af $5,00-loftet (let $0.3836 + tung $0.5025). Ingen fejl, ingen `n/a_no_tool_support`, ingen `truncated`.

## Hvad blev ændret

1. **Preflight** (to rå kald, ingen harness-kode): bekræftede `claude-opus-5` som udateret model-id på både den direkte Anthropic-API og OpenRouters live `/models`-katalog (kun `anthropic/claude-opus-5` + en separat, dyrere `anthropic/claude-opus-5-fast`-variant — intet `-YYYYMMDD`-suffiks på nogen af dem). `thinking.budget_tokens=16384` + `effort="high"` blev accepteret uden fejl på begge kanaler; `stop_reason`/`finish_reason="end_turn"`/`"stop"` — normal afslutning, ingen afvisning.
2. **Pricing bekræftet live, ikke kun antaget**: OpenRouters egen `usage.cost_details` på preflight-kaldet reproducerede $5/$25/mio tokens til øren nøjagtighed (`upstream_inference_prompt_cost`/`upstream_inference_completions_cost` divideret med token-antal). Identisk med Opus 4.8's snapshot, som ventet.
3. **`config/panel.yaml`**: ny `claude_opus_5`-blok (provider `anthropic`, `trace_exposure: summarized`, `thinking_budget: 16384`, `openrouter_model_id: anthropic/claude-opus-5` — unpinned, samme kaliber-forbehold som `fable_5`/`gpt_5_6_sol`).
4. **`config/pricing.yaml`**: ny `claude_opus_5`-blok, $5,00 / $25,00 / $0,50 / $6,25 per MTok — identisk med `opus_4_8`.
5. **`src/model_resolver.py`**: `INTENDED_NAMES["claude_opus_5"] = "Claude Opus 5 (Anthropic)"`.
6. **`run_opus5_panel.py`** (ny fil): standalone runner, genbruger `AnthropicAdapter`, `save_result`/`save_heavy_result`, `grade_heavy`, `compute_cost` m.fl. uændret — output-skemaet er byte-identisk med hvad `run_full()`/`run_heavy()` selv ville have produceret. Tvinger OpenRouter-kanalen (popper `ANTHROPIC_API_KEY`) for **begge** faser — se afvigelse 2 nedenfor.

Begge commits (`6c93fee`, `d743eda`) pushet til `origin/main` før kørslen; `git log origin/main..HEAD` var tomt før start.

## Resultater — de 6 spørgsmål

### 1. Springtabel-rækken, Opus 4.8 → Opus 5

| | Opus 4.8 | Opus 5 | Δ | Fable 5 (samme metode) |
|---|---|---|---|---|
| Reasoning let (cellemedian) | 50 | **76,5** | 1,53x | 52 |
| Reasoning tung (cellemedian, baseline) | 34 | **50** | 1,47x | 32 |
| Latens tung, base | 3,6s | **4,96s** | 1,38x | 5,5s |
| Latens tung, invited_auto | — (ikke i registeret) | **8,01s** | — | — |
| Impliceret pris/mio tokens (tung, empirisk blend) | 9,0 | **9,81** | 1,09x | 18,3 |
| Sum tung regning | $0,42 | **$0,50** | 1,20x | $0,90 |
| Grebsrate (invited_auto) | 93% | **100%** | +7pp | 100% |
| Korrekt tung | 28/30 | **30/30** | +2 | 30/30 |

Metode-note: "impliceret pris/mio tokens" er valideret mod registeret ved at genberegne Opus 4.8's egen værdi med samme formel (`sum(cost_usd)/sum(input+reasoning+output)*1e6` over de 30 tunge rækker) — det gav 9,08, dvs. det matcher registerets citerede 9,0 tæt nok til at bekræfte metoden er den samme.

**Læsning**: Opus 5 ligner Opus 4.8's og Fable 5's profil (ikke K3's 5-16x eskalering) — alle tal stiger moderat (1,1-1,5x), prisen per token er praktisk talt uændret (som ventet, da raw-priserne er identiske til Opus 4.8), og grebsraten når nu 100%, samme niveau som Sonnet 4.6 og Fable 5. Korrekthed er perfekt (30/30) for første gang i denne Opus-linje.

### 2. Kalibrering — over-checking på lette opgaver?

Opus 5's lette reasoning-median (76,5) er **højere** end både Opus 4.8 (50) og Fable 5 (52) — det modsiger en hypotese om, at nyere Anthropic-generationer "checker mindre" på simple opgaver. Tværtimod: Opus 5 bruger *mere* reasoning på panelets lette prompts end sine to forgængere.

Vigtigt forbehold, fundet under research til denne kørsel: **registerets citerede "load-korrelation +0,84" for Fable 5 har ingen dokumenteret beregningsmetode noget sted i repoet** (kun tre bare citater af tallet, ingen writeup). Jeg kan derfor ikke reproducere den samme metrik ét-til-ét. Som stedfortræder korrelerede jeg Opus 5's egne lette rækkers `reasoning_load`-klassifikation (low/medium/high/very_high, ordinal 1-4) mod faktiske reasoning-tokens: **Pearson r = 0,52, Spearman ρ = 0,64** — begge markant lavere end den citerede 0,84 for Fable, MEN dette er ikke garanteret samme beregning, så tallet er en tilnærmelse, ikke en direkte sammenligning.

Konkret afvigelse i selve dataene: P7 (`code_structure`, klassificeret `medium`) fik 0 reasoning-tokens — lavere end begge `low`-klassificerede prompts (P1=88, P2=30). P9/P10 (begge `da_open_analysis`, klassificeret `high`) fik langt mere reasoning (716 og 540) end P4 (`very_high`, 497) — rækkefølgen er ikke monoton. Kalibreringen er til stede i store træk (høj-load-prompter får generelt mere reasoning end lav-load), men ikke perfekt ordnet.

### 3. Adaptiv tildeling — let/tung-faktor

Opus 5: tung/let = 50 / 76,5 = **0,65x**. Til sammenligning: K3 = 16,8x (dramatisk eskalering på tunge opgaver), Fable ≈ 0,62x, Opus 4.8 ≈ 0,68x (begge udledt af §5.1's rå tal, faktoren selv er ikke navngivet i registeret). Opus 5 lander tæt på sine to Anthropic-forgængere — ingen tegn på K3-lignende adaptiv eskalering. Reasoning-budgettet bruges relativt fladt på tværs af let/tung for hele denne familie.

### 4. Grebsrate mod Anthropic-signaturen

Signatur (registerets §4.1): Sonnet 100% / Opus 93% / Fable 100%. Opus 5: **100%** (15/15 invited_auto-rækker kaldte `python_exec`; 0 kaldte `web_search` — intet over-reach på nogen af de 3 låste opgaver, som forventet, da alle er selvforsynede). Opus 5 fuldender dermed mønstret: Anthropic-familien er nu 100% på tværs af Sonnet 4.6, Fable 5 og Opus 5 — kun den ældre Opus 4.8 (93%, 14/15) ligger under.

### 5. Trace-regime: raw/summarized/count_only/absent

| Fase | Betingelse | Fordeling |
|---|---|---|
| Let (10) | baseline (alle) | summarized: 9, absent: 1 (P7) |
| Tung (15) | baseline | summarized: 15 (100%) |
| Tung (15) | invited_auto | **"raw": 11**, absent: 4 |

**Vigtigt fund, ikke specifikt for Opus 5**: de 11 "raw"-mærkede tunge invited_auto-rækker er IKKE ægte rå CoT — de går gennem `src/tool_loop.py`'s delte værktøjs-loop (bruges af alle OpenAI-kompatible adaptere OG Anthropics OpenRouter-fallback), som ubetinget sætter `trace_status = "raw" if reasoning_text else ...` uanset udbyder (linje 172/266 i `tool_loop.py`) — den kender ikke til `anthropic_adapter.py`s egen sondring mellem "summarized" og "raw". Jeg verificerede at dette IKKE er nyt: Opus 4.8's egen historiske tunge kørsel (`results/heavy/20260709T093542_heavy_corrected.jsonl`) viser **exact samme mønster** — 15/15 invited_auto-rækker mærket "raw", 10 baseline "summarized" + 5 "absent". Det betyder registerets §4.5-påstand ("Anthropic blander: raw 12-15, summarized 10, absent 6-8 per model") højst sandsynligt tæller netop disse tool-loop-mærkede invited_auto-rækker som "raw" — dvs. den rapporterede "raw"-eksponering for Anthropic-modeller er efter al sandsynlighed et harness-mærkningsartefakt, ikke ægte uforkortet CoT. Dette er ikke rettet her (ingen kildekode ændret i denne kørsel), kun dokumenteret som et åbent fund.

### 6. Afvigelser fra registerets konventioner

1. **`run.py`s `FULL_MODEL_ORDER`/`HEAVY_MODELS` er ikke udvidet** til at inkludere `claude_opus_5` (samme som `fable_5`/`kimi_k3`/`gpt_5_6_sol`/`inkling` — ingen af de fire blev nogensinde committet ind i disse lister, jf. `git log -p -- run.py`). Kørslen skete derfor via et nyt standalone-script i stedet for `run.py --full --models`/`run.py --heavy`, som ville have krævet at redigere delt kode brugt af de 8 oprindelige paneldeltagere.
2. **Begge faser (let OG tung) tvang OpenRouter-kanalen**, ikke kun den tunge (modsat hvad `fable_5`s panel.yaml-kommentar dengang hævdede kun gjaldt `--heavy`) — fordi `fable_5`s FAKTISKE lette resultater (`results/full/20260720T090336_full.jsonl`) viser `via_openrouter: true`, ikke direkte route. Jeg matchede den målte kanal, ikke den skrevne kommentar.
3. **`reasoning_effort` blev ikke sendt som et bogstaveligt request-parameter** på nogen af de 40 kald — kun `thinking.budget_tokens=16384` går over OpenRouter for Claude-modeller (samme konvention som `opus_4_8`/`fable_5`). `reasoning_effort_sent: "high"` i panel.yaml er en logget metadata-etiket, ikke en transmitteret parameter — det var allerede sådan for de to forudgående Claude-rækker, ikke en ny afvigelse jeg introducerede.
4. **Kalibreringsmetrikken (spørgsmål 2) er en tilnærmelse**, ikke en eksakt reproduktion — se forbehold ovenfor.
5. **`served_by` er ikke logget på letfasen** (`results/full/*.jsonl`-skemaet har aldrig haft det feltet — kun tungfasen fik det tilføjet i commit `74f5fc6`). Ingen ny mangel, arvet skema.

## Pending — ikke rettet her

`tool_loop.py`s ubetingede "raw"-mærkning for enhver model med tekst-reasoning under værktøjskald (linje 172/266) er en reel, upåagtet defekt der sandsynligvis har farvet registerets §4.5 trace-regime-tabel for alle tre Anthropic-modeller (Sonnet 4.6, Opus 4.8, Fable 5), ikke kun Opus 5. Bevidst IKKE rettet her for at holde denne kørsel isoleret til "tilføj Opus 5" — bør rettes i en separat, dedikeret arm der også genvurderer de eksisterende Anthropic-rækker i registeret.

Load-korrelationsmetoden bag "+0,84" for Fable 5 er tabt/aldrig dokumenteret. Hvis den skal genbruges fremadrettet, bør den skrives ned som kode, ikke kun citeres som et tal.

## Ikke rørt

`run.py` (ingen ændringer — `FULL_MODEL_ORDER`/`HEAVY_MODELS`/`REGIME_MAP`/`TRACE_TEXT_MODELS`/`LEGIBILITY_EXCLUDED` alle urørte), `src/adapters/anthropic_adapter.py`, `src/tool_loop.py` (raw-mærkningsdefekten dokumenteret, ikke rettet), alle eksisterende filer i `results/full/` og `results/heavy/` (kun nye filer tilføjet, ingen overskrevet), `docs/reasoning_findings.md`, `datasite/` (dashboardet er ikke opdateret med Opus 5's tal i denne kørsel).
