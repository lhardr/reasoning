# CC Brief — Reasoning Benchmark, Phase 0: Measurement Harness

## Context

We are building a benchmark that measures **reasoning-token economy and legibility** across a panel of frontier and open-weight models, with a Danish/European-language and sovereignty angle. The full design lives in `sprogskat_reasoning_benchmark_design.md` (read it first if present in the repo). This brief covers **Phase 0 only**: the measurement plumbing and a smoke test that validates access and capture before we spend money on a real run.

The benchmark measures four separate things, kept strictly apart by design ("firewalls"): **economy** (tokens and cost), **legibility** (is the trace readable — judged later), **correctness** (right answer vs a known key — later), and it deliberately does **not** measure faithfulness or reasoning-vs-memorization. Phase 0 builds **economy plumbing only**. No quality scoring, no judges, no correctness in this phase.

### Phase plan (so you know the boundaries)
- **Phase 0 (this brief):** repo, config, provider adapters, token accounting, cost calculation, raw-trace storage, smoke test.
- Phase 1 (later): the 10 prompt types.
- Phase 2 (later): legibility judges (MiniMax + Gemini), two-judge agreement.
- Phase 3 (later): optional correctness layer on known-answer prompts.

**Do not build Phases 1–3 now.** Scaffold so they slot in cleanly, but stop at the smoke test.

---

## What to build

### 1. Repo structure
```
reasoning-benchmark/
  config/
    panel.yaml          # models, roles, exposure regimes
    pricing.yaml        # per-model prices + snapshot date
  src/
    adapters/           # one adapter per provider
    accounting.py       # token-phase accounting (the economy axis)
    cost.py             # cost calculation incl. caching
    storage.py          # structured result persistence
    run.py              # orchestration entrypoint
  results/              # gitignored; raw traces + records land here
  tests/
  .env.example
  .gitignore
  README.md
```

### 2. Config (`config/panel.yaml`)
The **scored panel (5)** plus the **anchor** plus the **judges** (judges are defined but unused in Phase 0):

| key | provider | role | trace_exposure |
| --- | --- | --- | --- |
| deepseek_v4 | deepseek | scored | raw |
| glm_5_2 | zai | scored | raw |
| kimi_k2_7 | moonshot | scored | raw |
| gpt_5_5 | openai | scored | count_only |
| claude_sonnet_4_6 | anthropic | scored | summarized |
| gemma_4 | local | anchor | raw |
| minimax | minimax | judge | (unused phase 0) |
| gemini_3_1_pro | google | judge | (unused phase 0) |

`trace_exposure` is our **expected** classification. The smoke test must verify it against live API behaviour and flag any mismatch (the field may have changed since June 2026 — version drift is expected).

### 3. Provider adapters (`src/adapters/`)
A uniform interface. Each adapter takes a prompt and a thinking/effort setting and returns a normalized record:

```python
@dataclass
class ModelResponse:
    answer_text: str
    input_tokens: int
    reasoning_tokens: int        # billed thinking tokens (count), even when text hidden
    output_tokens: int           # visible answer tokens
    cache_read_tokens: int
    cache_write_tokens: int
    raw_reasoning_trace: str | None   # the actual CoT text, or None if not exposed
    trace_status: str            # "raw" | "summarized" | "count_only" | "absent"
    latency_s: float
    model_version: str           # pinned snapshot id reported by the provider
    raw_usage: dict              # the provider's verbatim usage object, for audit
```

Per-provider handling to implement:
- **deepseek_v4:** read `reasoning_content` (raw CoT) and `content`; `trace_status="raw"`.
- **glm_5_2, kimi_k2_7:** raw reasoning field (verify exact field name per provider docs at build time); `trace_status="raw"`.
- **claude_sonnet_4_6 (Anthropic):** thinking is summarized by default. Capture the summarized thinking text, and read the billed thinking token count from `usage.output_tokens_details.thinking_tokens`. `raw_reasoning_trace` = summary; `trace_status="summarized"`.
- **gpt_5_5 (OpenAI):** raw CoT is hidden. Capture the reasoning **token count** from the usage object via the Responses API; `raw_reasoning_trace=None`; `trace_status="count_only"`.
- **gemma_4 (local):** run via vLLM, Ollama, or HF transformers; capture the full output stream including the thinking tags; `trace_status="raw"`.
- **minimax, gemini_3_1_pro:** stub adapters only (judges, Phase 2). Do not call in Phase 0.

Notes:
- You may use direct provider APIs or OpenRouter as a gateway. If using OpenRouter, **verify per model** that reasoning tokens/fields are actually captured — some models drop reasoning fields on tool calls and the `exclude` flag is not always respected. The smoke test is where this gets confirmed.
- Read all API keys from environment / `.env`. **Never hardcode secrets, never commit them.** If a key is missing, that model's adapter should fail gracefully and be reported as "skipped (no credential)" so a partial smoke test still runs.

### 4. Token accounting (`src/accounting.py`) — the economy axis
- Store `input`, `reasoning`, `output`, `cache_read`, `cache_write` **separately**. Never collapse them into one number.
- Compute reasoning share = reasoning_tokens / (reasoning_tokens + output_tokens).
- This module does economy only. No quality judgment of any kind lives here. (Firewall: economy is kept apart from quality.)

### 5. Cost (`src/cost.py`)
- `cost = input·p_in + cache_read·p_cache + cache_write·p_cache_write + (reasoning + output)·p_out`, using `config/pricing.yaml`.
- Prices come from the config file, populated from each provider's current pricing page, with a `snapshot_date`. **Do not hardcode prices in logic.** Treat any price as "measured-vs-estimated": stamp the snapshot date on every cost record.

### 6. Storage (`src/storage.py`)
- One record per (model, prompt, run): full token breakdown, cost, latency, `trace_status`, `raw_reasoning_trace` if present, `model_version`, timestamp, thinking/effort setting, pricing snapshot date.
- SQLite or JSONL, your call. `results/` is gitignored.

### 7. Smoke test (`tests/` + a `run.py --smoke`)
Run **one trivial prompt** (e.g. a short arithmetic word problem) across all available scored models + the Gemma anchor. It must:
1. Confirm each adapter returns a populated `ModelResponse`.
2. Confirm token phases are captured (non-null input/reasoning/output where the provider reports them).
3. **Empirically verify `trace_exposure`:** assert raw trace present for deepseek/glm/kimi/gemma, summarized for claude, absent for gpt. Print a clear PASS/MISMATCH per model (mismatch is a finding, not a crash).
4. Print a summary table: model, version, input/reasoning/output tokens, trace_status, cost, latency.

This validates access, capture, and our exposure table before any real spend.

---

## Constraints and standing requirements

- **Python:** use `python3` (not `python`) for all run commands. Mac environment.
- **Secrets:** env / `.env` only; `.env` in `.gitignore`; never commit keys; provide `.env.example` with key names and blank values.
- **Reproducibility:** log model version ids, timestamps, thinking/effort settings, and pricing snapshot date on every record.
- **Git hygiene (standing requirement):**
  1. Commit immediately after each completed change.
  2. Push before any deploy.
  3. Before deploying, verify `git log origin/main..HEAD` is empty.
  (No deploy target in Phase 0, so 2–3 apply once one exists; commit-after-each-change applies throughout.)

## Definition of done
- Repo scaffolded as above.
- Adapters implemented for the five scored models + Gemma; MiniMax/Gemini stubbed.
- Accounting, cost, and storage modules working.
- `python3 run.py --smoke` runs end to end, prints the summary table, and reports the exposure-verification PASS/MISMATCH per model.
- README documents how to set keys and run the smoke test.
- All work committed and pushed.
