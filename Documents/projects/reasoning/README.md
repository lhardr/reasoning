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
