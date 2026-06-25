# Reasoning Benchmark

Measures **reasoning-token economy** across a panel of frontier and open-weight
models, with a Danish/European-language and sovereignty angle.

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

| Key | Provider | Role | Trace exposure |
|-----|----------|------|----------------|
| `deepseek_v4` | DeepSeek | scored | raw |
| `glm_5_2` | Zhipu AI | scored | raw |
| `kimi_k2_7` | Moonshot AI | scored | raw |
| `gpt_5_5` | OpenAI | scored | count\_only |
| `claude_sonnet_4_6` | Anthropic | scored | summarized |
| `gemma_4` | local (Ollama) | anchor | raw |
| `minimax` | MiniMax | judge | stub (Phase 2) |
| `gemini_3_1_pro` | Google | judge | stub (Phase 2) |

---

## Setup

### 1. Install dependencies

```bash
pip3 install -r requirements.txt
```

### 2. Set API keys

Copy `.env.example` to `.env` and fill in the keys you have:

```bash
cp .env.example .env
# edit .env — add the keys for the models you want to test
```

Keys required per model:

| Model key | Env var |
|-----------|---------|
| `deepseek_v4` | `DEEPSEEK_API_KEY` |
| `glm_5_2` | `ZAI_API_KEY` |
| `kimi_k2_7` | `MOONSHOT_API_KEY` |
| `gpt_5_5` | `OPENAI_API_KEY` |
| `claude_sonnet_4_6` | `ANTHROPIC_API_KEY` |
| `gemma_4` | *(none — local via Ollama)* |

A missing key means that model is **skipped gracefully**, not a crash.

### 3. Install and start Ollama (for Gemma 4)

```bash
# Install Ollama from https://ollama.com
ollama pull gemma4
ollama serve   # start the local server if not already running
```

### 4. Verify model IDs

Before a real run, confirm the model IDs in `config/panel.yaml` against each
provider's current API docs — the field is well-documented:

```yaml
deepseek_v4:
  model_id: deepseek-reasoner   # <- verify this
```

Similarly update prices in `config/pricing.yaml` and refresh `snapshot_date`.

---

## Running the smoke test

```bash
python3 run.py --smoke
```

This runs one trivial prompt across all available scored models plus the Gemma
anchor and prints a summary table:

```
Model                  Version                      Input  Reasoning  Output  TraceStatus  Cost(USD)  Latency  Verify
---
deepseek_v4            deepseek-reasoner              128        512      64  raw            $0.00063    3.21s  PASS
glm_5_2                glm-z1-air                     134        480      58  raw            $0.00012    2.10s  PASS
...
gpt_5_5                gpt-5.5                        121        384      48  count_only     $0.00430    4.55s  PASS
claude_sonnet_4_6      claude-sonnet-4-6              119        320      72  summarized     $0.00654    5.18s  PASS
gemma_4                gemma4:latest                   98        210      44  raw            $0.00000    9.33s  PASS
```

**Verify column** shows PASS or MISMATCH per model. A MISMATCH means the
provider's actual trace exposure differs from the expected regime in `panel.yaml`
— this is a finding to investigate, not a crash.

To test a single model:

```bash
python3 run.py --smoke --model claude_sonnet_4_6
```

Results are written to `results/<run_id>.jsonl` (gitignored).

---

## Repository structure

```
reasoning/
  config/
    panel.yaml          models, roles, expected trace exposure
    pricing.yaml        per-model prices + snapshot_date
  src/
    adapters/           one adapter per provider
      base.py           ModelResponse dataclass, BaseAdapter, shared utilities
      deepseek.py       DeepSeek V4
      zai.py            Zhipu AI GLM 5.2
      moonshot.py       Moonshot AI Kimi K2.7
      openai_adapter.py OpenAI GPT-5.5
      anthropic_adapter.py  Anthropic Claude Sonnet 4.6
      local.py          Gemma 4 via Ollama
      minimax.py        MiniMax stub (Phase 2 judge)
      google_adapter.py Gemini stub (Phase 2 judge)
    accounting.py       token-phase accounting (economy axis, no quality)
    cost.py             cost calculation from config/pricing.yaml
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
| `reasoning_tokens` | Billed thinking tokens (count; text may be absent for closed models) |
| `output_tokens` | Visible answer tokens |
| `cache_read_tokens` | Cache-read tokens (billed at cache rate) |
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
| `raw` | Full CoT text returned in `raw_reasoning_trace` |
| `summarized` | Processed/summarized thinking returned (Claude) |
| `count_only` | CoT hidden; reasoning token count in `reasoning_tokens` (GPT) |
| `absent` | No reasoning trace or count exposed |

The smoke test **empirically verifies** these against the `trace_exposure` field
in `panel.yaml` and reports PASS / MISMATCH per model. A mismatch means
provider behaviour changed since the config was last updated.
