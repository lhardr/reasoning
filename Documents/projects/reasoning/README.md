# Reasoning Benchmark

Measures **reasoning-token economy** across a panel of frontier models, with a
Danish/European-language and sovereignty angle.

This repo implements **Phase 0** — the measurement plumbing and smoke test.
See `docs/cc_brief_phase0_harness.md` for the full brief and
`docs/sprogskat_reasoning_benchmark_design.md` for the research design.

---

## Phase plan

| Phase | Scope |
|-------|-------|
| **0 (this branch)** | Repo, config, provider adapters, token accounting, cost, storage, smoke test |
| 1 | 10 prompt types |
| 2 | Legibility judges (MiniMax + Gemini), two-judge agreement |
| 3 | Optional correctness layer on known-answer prompts |

---

## Model panel

All models run via **OpenRouter** (`OPENROUTER_API_KEY`) unless a direct provider
key is present (which takes priority). `include_reasoning: true` is set permanently
on all raw-trace adapters so the reasoning content is never silently stripped by
the gateway.

| Key | Provider | Role | Trace exposure | OpenRouter slug |
|-----|----------|------|----------------|-----------------|
| `deepseek_v4` | DeepSeek | scored | raw | `deepseek/deepseek-v4-pro` |
| `glm_5_2` | Z.ai | scored | raw | `z-ai/glm-5.2` |
| `kimi_k2_7` | Moonshot AI | scored | raw | `moonshotai/kimi-k2.7-code` |
| `gpt_5_5` | OpenAI | scored | count\_only | `openai/gpt-5.5` |
| `claude_sonnet_4_6` | Anthropic | scored | summarized | `anthropic/claude-sonnet-4.6` |
| `gemma_4` | Google (anchor) | anchor | raw | `google/gemma-4-31b-it` |
| `minimax` | MiniMax | judge | stub (Phase 2) | `minimax/minimax-m3` |
| `gemini_3_1_pro` | Google | judge | stub (Phase 2) | `google/gemini-3.1-pro-preview` |

Model IDs confirmed against the live OpenRouter catalog on 2026-06-25.
Verify slugs before each production run: `openrouter.ai/models`.

---

## Setup

### 1. Install dependencies

```bash
pip3 install -r requirements.txt
```

### 2. Set API keys

Copy `.env.example` to `.env` and fill in at least `OPENROUTER_API_KEY`:

```bash
cp .env.example .env
# edit .env
```

A single OpenRouter key covers all six models. Direct provider keys (listed
below) take priority over OpenRouter when present.

| Model key | Direct env var | OpenRouter fallback |
|-----------|----------------|---------------------|
| `deepseek_v4` | `DEEPSEEK_API_KEY` | ✓ |
| `glm_5_2` | `ZAI_API_KEY` | ✓ |
| `kimi_k2_7` | `MOONSHOT_API_KEY` | ✓ |
| `gpt_5_5` | `OPENAI_API_KEY` | ✓ |
| `claude_sonnet_4_6` | `ANTHROPIC_API_KEY` | ✓ |
| `gemma_4` | — | ✓ (OpenRouter only) |

A missing key means that model is **skipped gracefully**, not a crash.

---

## Running the smoke test

```bash
python3 run.py --smoke
```

This:
1. Resolves and prints the model IDs that will be used (failing loudly if any slug
   is not found in the live OpenRouter catalog)
2. Runs one trivial prompt across all six models
3. Prints a summary table with trace-exposure verification (PASS/MISMATCH) and a
   hard assertion that `reasoning_tokens > 0` for every thinking model
4. Writes results to `results/<run_id>.jsonl`

To test a single model:

```bash
python3 run.py --smoke --model deepseek_v4
```

**Expected output (all six green):**
```
Model Resolution
---------------------------------------------------------------------------
  deepseek_v4            DeepSeek V4 Pro (reasoning)      deepseek/deepseek-v4-pro  openrouter
  glm_5_2                GLM 5.2 (Z.ai)                   z-ai/glm-5.2              openrouter
  kimi_k2_7              Kimi K2.7 (Moonshot)             moonshotai/kimi-k2.7-code openrouter
  gpt_5_5                GPT-5.5 (OpenAI)                 openai/gpt-5.5            openrouter
  claude_sonnet_4_6      Claude Sonnet 4.6 (Anthropic)    anthropic/claude-sonnet-4.6 openrouter
  gemma_4                Gemma 4 (OpenRouter)             google/gemma-4-31b-it     openrouter

Model   Version  Input  Reasoning  Output  TraceStatus  Cost($)  Latency  Exposure  TokenAssert
deepseek_v4   ...   26    500+    350+   raw     PASS    OK (N)
...
```

---

## Repository structure

```
reasoning/
  config/
    panel.yaml          models, roles, expected trace exposure, confirmed OpenRouter slugs
    pricing.yaml        per-model prices (snapshot_date) confirmed from OpenRouter 2026-06-25
  src/
    adapters/
      base.py           ModelResponse dataclass, BaseAdapter, shared utilities
      deepseek.py       DeepSeek V4 Pro — raw trace, include_reasoning permanent
      zai.py            Z.ai GLM 5.2 — raw trace, include_reasoning permanent
      moonshot.py       Moonshot Kimi K2.7 — raw trace, include_reasoning permanent
      openai_adapter.py OpenAI GPT-5.5 — count_only
      anthropic_adapter.py  Anthropic Claude Sonnet 4.6 — summarized thinking
      gemma.py          Gemma 4 via OpenRouter — raw trace, include_reasoning permanent
      minimax.py        MiniMax M3 stub (Phase 2 judge)
      google_adapter.py Gemini 3.1 Pro stub (Phase 2 judge)
    accounting.py       token-phase accounting (economy axis, no quality)
    cost.py             cost calculation from config/pricing.yaml
    model_resolver.py   model ID resolution + loud failure on bad slugs
    storage.py          JSONL persistence to results/
    config_loader.py    cached YAML loaders
  results/              gitignored; raw traces + records land here
  tests/
  docs/                 brief and design documents
  run.py                entry point
  .env.example          key names, no values
  requirements.txt
```

---

## Token accounting

Tokens are kept strictly separate — never collapsed:

| Field | Description |
|-------|-------------|
| `input_tokens` | Tokens in the prompt |
| `reasoning_tokens` | Billed thinking tokens (count; text may be absent for GPT-5.5) |
| `reasoning_source` | `"api"` — `reasoning_tokens` came straight from the provider's usage/billing fields, or `"text_estimate"` — the provider didn't report a reasoning count, so the value is a proportional split estimated from the response text. Set by every adapter, stored in every `tokens` sub-object written by `src/storage.py` (`save_result`, `save_langcost_result`, `save_tools_result`, `save_variance_result`, `save_heavy_result`). Not comparable 1:1 across the two values — see the analysis code's `reasoning_source != "api"` filter before pooling estimated and measured cells. |
| `output_tokens` | Visible answer tokens |
| `cache_read_tokens` | Cache-read tokens |
| `cache_write_tokens` | Cache-write tokens |

Cost formula:
```
cost = input * p_in
     + cache_read * p_cache_read
     + cache_write * p_cache_write
     + (reasoning + output) * p_out
```

---

## Trace exposure regimes

| Status | Meaning |
|--------|---------|
| `raw` | Full CoT text in `raw_reasoning_trace` (DeepSeek, GLM, Kimi, Gemma) |
| `summarized` | Processed thinking text (Claude) |
| `count_only` | CoT hidden; count in `reasoning_tokens` (GPT-5.5) |
| `absent` | No trace or count exposed |

The smoke test empirically verifies these against `trace_exposure` in `panel.yaml`
and also asserts `reasoning_tokens > 0` for every thinking model — a regression
guard for the `include_reasoning` flag.

---

## Pricing

Prices live in `config/pricing.yaml` with a `snapshot_date`. The cost formula
reads exclusively from there — no hardcoded prices in logic. Update the file and
`snapshot_date` before each production run.

---

## Limitations (draft — points only, prose TBD)

- **Contamination, heavy vs. light.** The 3 heavy tasks (H1-H3) are unmodified
  records from public benchmarks: `HumanEval/94` (HumanEval, MIT) and FinQA
  test-set ids `CDNS/2015/page_30.pdf-3` / `AMAT/2013/page_37.pdf-2` — both
  scraped GitHub repos, plausibly in pretraining data for most panel models.
  The 10 light prompts (P1-P10, `data/prompts.yaml`) are self-written Danish
  bureaucratic/legal scenarios with no public source. Contamination risk is
  structurally different across the two suites, not just a caveat that
  applies equally to both.
- **Provider routing.** Open models run via OpenRouter, which routes each
  call across 7-14 different backends per model (`served_by` field) —
  token counts for open models are therefore averages over a shifting
  backend population, not one reproducible channel. `kimi_k3`, `inkling`,
  `mistral_medium_3_5`, and the Claude/GPT models each stayed on one backend.
  (See `docs/handover_findings_konsolidering.md`, "Datagrundlags-fælder" #4.)
- **n=1 on light.** Every light-suite number is a single pass per prompt per
  model (10 rows) — there is no per-prompt spread to report, only the flat
  median across prompts. The dedicated variance-suite (2 passes on light)
  shows run-to-run spread up to 23.6x max on identical light input, which
  the main light numbers cannot see or bound.
- **Judge validation.** Each judged cell gets two independent scorers
  (minimax, gemini_3_1_pro), but the canonical judge files that feed every
  redundancy/coherence number in the findings register
  (`datasite/data/judges-heavy.json`, `judges-light-new.json`) never call
  the codebase's own `compute_agreement()` (`src/judge.py`) — no
  `agreement` field is stored, unlike the earlier Phase 2 validation runs
  that did compute it. Recomputing it directly from the two judges' raw
  scores, using the codebase's own high-disagreement threshold (max
  per-dimension diff ≥2 on a 1-5 scale): 11/55 heavy cells (20%) and 7/20
  light cells (35%) disagree at that level, unflagged, under every
  redundancy/coherence claim in the register.
- **June run's route inferred, not logged.** `via_openrouter` and
  `request_model_id` were added 2026-07-14 (commit `04c21a5`).  The
  canonical June light run (`results/full/20260625T181036_full.jsonl`, the
  8 old models, source of table 1.1's light column for those 8) predates
  that by ~3 weeks and has neither field — whether each of those 8 rows
  went via OpenRouter or a direct provider API can only be inferred from
  the shape of `model_version` (slug-with-slash vs. bare label), not read
  off a logged flag.
- **Generating code unverifiable for 4 of 13 models.** `fable_5`,
  `kimi_k3`, `gpt_5_6_sol`, and `inkling` were never added to `run.py`'s
  `FULL_MODEL_ORDER`/`HEAVY_MODELS` lists. Per `docs/cc_debrief_opus5.md`
  ("Afvigelser fra registerets konventioner" #1), their canonical July
  light+heavy runs were produced by a standalone script written outside
  `run.py`'s shared path — and that script itself was never committed.
  Of the 13 models in the datagrundlag (12 panel + Opus 5), these 4 have
  numbers in the register whose exact generating code path cannot be
  inspected or re-run from anything in version control.
