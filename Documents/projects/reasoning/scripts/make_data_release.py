#!/usr/bin/env python3
"""
Package run data into a staged public data release.

Purpose: let strangers run scripts/compute_findings.py on real data without
us handing over provider-owned reasoning-trace text we have no right to
redistribute.

INPUT: results-jsonl directories (default: results/full/, results/heavy/,
results/auto/; results/sprog/ is included automatically if it exists).

OUTPUT: a staged data_release/ directory at the repo root. This is NOT
written into, or committed to, the public repo by this script — publishing
it is a separate, manual decision. Running this script twice overwrites
data_release/ from scratch (idempotent given the same source data).

TRANSFORMATION, per row (everything else is preserved byte-for-byte):
  raw_reasoning_trace -> null, for every row whose ANSWERING model is not
  one of the open families this harness measures (DeepSeek, Z.ai/GLM,
  Moonshot/Kimi, Mistral, Gemma, Thinking Machines/Inkling). This applies
  to panel rows AND to router rows (openrouter/auto, openrouter/auto-beta)
  routed to a closed model — e.g. a router row that landed on
  anthropic/claude-sonnet-5 or google/gemini-2.5-flash gets its trace
  nulled exactly like a direct claude_sonnet_4_6 row would.
  Rationale: summarized/exposed vendor-generated reasoning text (Anthropic,
  OpenAI, Google's closed Gemini family) is provider content, not ours to
  redistribute. The open models' raw traces ARE this dataset's actual
  research value and are kept in full.

  trace_status, tokens, cost_usd, latency_s, served_by, model_version,
  correct, condition, pass_index, and every other field are left exactly
  as recorded — nulling the trace text does not change what regime it was
  (trace_status still says "summarized"/"count_only"/whatever it truly was;
  only the text itself is removed).

SAFETY: before writing anything, every row is scanned for values that look
like API keys, bearer tokens, or literal env-var-style secret assignments.
Any hit aborts the entire release with a non-zero exit and prints exactly
which file/row matched — better a failed release than a leaked key.

Usage:
    python3 scripts/make_data_release.py [--out DIR] [--sources full,heavy,auto,sprog]
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
DEFAULT_SOURCES = ["full", "heavy", "auto"]
OPTIONAL_SOURCES = ["sprog"]  # included automatically if present

ROUTER_MODEL_KEYS = {"openrouter_auto", "openrouter_auto_beta"}
OPEN_SUBSTRINGS = (
    "deepseek", "z-ai", "glm", "moonshot", "kimi", "mistral", "gemma",
    "thinkingmachines", "inkling",
)

SECRET_PATTERNS = [
    # Real key tokens are long (20+), hyphen-free runs after the prefix --
    # unlike this, natural-language Danish/English hyphenated compounds
    # (e.g. "amerikansk-domineret") can coincidentally contain "sk-" but
    # never continue for 20+ hyphen-free word characters. A word-boundary
    # lookaround on both ends keeps this from matching mid-word.
    re.compile(r"(?<![A-Za-z0-9_-])sk-ant-[A-Za-z0-9_]{20,}(?![A-Za-z0-9_-])"),
    re.compile(r"(?<![A-Za-z0-9_-])sk-or-[A-Za-z0-9_]{20,}(?![A-Za-z0-9_-])"),
    re.compile(r"(?<![A-Za-z0-9_-])sk-[A-Za-z0-9_]{20,}(?![A-Za-z0-9_-])"),
    re.compile(r"Bearer [A-Za-z0-9._-]{10,}"),
    re.compile(r"AIza[A-Za-z0-9_-]{10,}"),
    re.compile(r"\b[A-Z][A-Z0-9_]*_(API_)?KEY\b\s*=\s*[\"'][A-Za-z0-9]{10,}[\"']"),
    re.compile(r"/Users/[a-zA-Z]+"),
    re.compile(r"[A-Za-z0-9._%+-]+@(gmail|outlook|hotmail|yahoo)\.[a-z]{2,}"),
]


def is_open_model(row: dict) -> bool:
    """
    True if the model that ACTUALLY ANSWERED this row belongs to an open
    family whose trace we redistribute. Unknown/unrecognized signals default
    to False (closed) — safe-by-default, never the other way around.
    """
    model_key = (row.get("model_key") or "").lower()
    model_version = (row.get("model_version") or "").lower()
    # For router rows, model_key is a routing-policy placeholder
    # ("openrouter_auto[_beta]"), not a model family — trust model_version,
    # the actually-resolved answering model, instead.
    signal = model_version if model_key in ROUTER_MODEL_KEYS else (model_key or model_version)
    if not signal:
        return False
    if "anthropic" in signal or "claude" in signal:
        return False
    if "openai" in signal or "gpt-" in signal or "/gpt" in signal:
        return False
    if "gemini" in signal:  # closed Google family -- distinct from open "gemma"
        return False
    return any(s in signal for s in OPEN_SUBSTRINGS)


def _walk_strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _walk_strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk_strings(v)


def _scan_row_for_secrets(row: dict) -> list[str]:
    hits = []
    for s in _walk_strings(row):
        for pat in SECRET_PATTERNS:
            m = pat.search(s)
            if m:
                start = max(0, m.start() - 15)
                end = min(len(s), m.end() + 15)
                context = s[start:end]
                hits.append(f"{pat.pattern} matched: ...{context!r}...")
    return hits


def transform_row(row: dict) -> dict:
    row = dict(row)
    if not is_open_model(row):
        row["raw_reasoning_trace"] = None
    return row


def process_source(source: str, out_root: Path) -> tuple[int, int, list[str]]:
    """Returns (files_written, rows_written, all_secret_hits)."""
    src_dir = REPO_ROOT / "results" / source
    if not src_dir.is_dir():
        return 0, 0, []
    out_dir = out_root / source
    out_dir.mkdir(parents=True, exist_ok=True)

    files_written = 0
    rows_written = 0
    all_hits: list[str] = []

    for f in sorted(src_dir.glob("*.jsonl")):
        out_lines = []
        with open(f, encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, 1):
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                hits = _scan_row_for_secrets(row)
                if hits:
                    all_hits.extend(f"{f.name}:{lineno}: {h}" for h in hits)
                    continue  # don't write this row even in a partial/failed run
                out_row = transform_row(row)
                out_lines.append(json.dumps(out_row, ensure_ascii=False))

        if not all_hits:
            out_path = out_dir / f.name
            out_path.write_text("\n".join(out_lines) + ("\n" if out_lines else ""), encoding="utf-8")
            files_written += 1
            rows_written += len(out_lines)

    return files_written, rows_written, all_hits


DATA_README_TEMPLATE = """\
# data_release/

A packaged, redistributable snapshot of this harness's own run data, staged
by `scripts/make_data_release.py`. Generated from `results/{sources_list}`.

**This directory is staged locally — it is not automatically published.**
Publishing it (to the public repo or elsewhere) is a separate, manual
decision.

## 1. Field documentation

Every row is one (model, prompt-or-task, condition, pass) API call record.
Common fields across `full/`, `heavy/`, and `auto/`:

| Field | Meaning |
|---|---|
| `run_id` | UTC-timestamp-prefixed run identifier (`YYYYMMDDTHHMMSS_<phase>`). Sortable — later run_id means later wall-clock run. |
| `model_key` | Panel key (e.g. `gemma_4`) for direct panel rows, or a routing-policy placeholder (`openrouter_auto`, `openrouter_auto_beta`) for router rows. |
| `model_version` | The model that actually answered, as reported by the provider (`resp.model`). For router rows this is the only place to see which underlying model was chosen. |
| `prompt` / `prompt_id` / `task_id` | The prompt text (light suite) or task identifier (heavy suite: `code`, `finance_calc`, `finance_interp`). |
| `domain` | Heavy-suite task domain (`code`/`finance_calc`/`finance_interp`) or `"light"` for light-suite rows re-used by router scripts. |
| `condition` | `baseline` or `invited_auto` (heavy suite / router scripts) — whether tools were invited. |
| `pass_index` | 1-5, which repeated pass this row is (heavy suite, variance, router scripts; light-suite panel rows are n=1 and omit this). |
| `answer_text` | The model's final answer. |
| `raw_reasoning_trace` | The model's raw chain-of-thought text, or **`null`** — see §2 for when and why. |
| `trace_status` | `"raw"` \\| `"summarized"` \\| `"count_only"` \\| `"absent"` — what regime the ORIGINAL (pre-nulling) trace was in. Nulling the text in §2 never changes this field — it still tells you the truth about trace exposure even where the text itself has been removed. |
| `tokens` | `{{input, reasoning, output, cache_read, cache_write, reasoning_share, reasoning_source}}`. `reasoning_source` is `"api"` (real billed usage metadata) or `"text_estimate"` (proportional fallback — see main README's conventions §5). |
| `cost_usd` | Cost of this one call, from the provider's own live pricing (router rows) or `config/pricing.yaml`'s snapshot (panel rows) — see `pricing_snapshot_date`. |
| `latency_s` | Wall-clock seconds for this call. |
| `served_by` | OpenRouter's reported backend (e.g. `"BaseTen"`, `"CoreWeave"`) — absent for direct-API calls. |
| `correct` | `true`/`false`/`null`. Heavy suite: always populated (programmatic or facit-based grading at call time). Light suite: `null` in these raw files — light-suite correctness requires a separate grading pass (`run_phase3.py`), not stored per-row here. |
| `tool_calls` | List of tool invocations this row made (name, args, result length) — empty list if the model was invited but didn't call anything. |
| `via_openrouter` | Whether this call went through OpenRouter (`true`) or a direct provider API (`false`). |

Router-run-specific fields (`auto/`): `request_model_id` (always the literal
router slug sent, e.g. `"openrouter/auto-beta"` — never the resolved
model), `plugins_param_sent`, `cost_quality_tradeoff`, `session_id_sent`
(routing-metadata bookkeeping — see `run_auto_beta.py`'s docstring).

## 2. Model inclusion: which rows have a trace, and why

`raw_reasoning_trace` is `null` for every row whose answering model belongs
to a closed family: **Anthropic** (Claude Sonnet/Opus/Fable, including
router rows that landed on one), **OpenAI** (GPT-5.x), and **Google's
closed Gemini family** (e.g. `gemini-2.5-flash` — distinct from Google's
OPEN Gemma family, which is kept). These providers only ever expose a
summary or a token count, never their real chain-of-thought, and that
summarized/exposed text is the provider's content, not ours to
redistribute.

`raw_reasoning_trace` is KEPT (the real value) for the seven open models
this harness measures, and for router rows that happened to land on one of
them: **DeepSeek**, **Z.ai/GLM**, **Moonshot/Kimi**, **Mistral**, **Google
Gemma** (open-weight — not to be confused with closed Gemini above),
**Thinking Machines/Inkling**. These raw traces are this dataset's actual
research value.

`trace_status` is never changed by this process — it still records the
TRUE regime the original response was in, whether or not the text itself
was kept. A `null` trace with `trace_status: "raw"` means the text was
removed for redistribution, not that no raw trace ever existed.

## 3. License / attribution per data source

- **Danish light-suite prompts (P1-P10) and their answers**: this project's
  own production.
- **Finance task content** (`finance_calc`, `finance_interp` domains):
  derived from [FinQA](https://github.com/czyssrs/FinQA) (Chen et al.,
  EMNLP 2021), CC BY 4.0-licensed.
- **Code task content** (`code` domain): derived from
  [HumanEval](https://github.com/openai/human-eval) (© OpenAI), MIT-licensed.

## 4. Quickstart

```bash
python3 scripts/compute_findings.py data_release/
```

This recomputes the harness's headline figures (reasoning medians,
correct/actual-$, trace_status inventory, etc.) directly and deterministically
from this data — no API calls. Figures computed this way should closely
track the published report, but are not guaranteed to reproduce every
figure to the decimal: some published numbers draw on a manually curated
dataset (`datasite/reasoning-data.json`, which layers hand-reviewed
corrections on top of the raw per-call rows) that this release does not
include. Where the two diverge, treat the recomputation from this raw data
as the more auditable (if occasionally less curated) number, and the
published report as the more curated (if less directly reproducible) one.

## 5. Conventions

Same four (plus one) conventions as the main README — repeated here since
this directory may circulate independently of it:

1. Heavy numbers = median of per-task medians, baseline condition.
2. Pass-level dedup: latest run wins per cell (this release does NOT
   pre-dedup — `scripts/compute_findings.py` applies this rule at read
   time; if you're writing your own reader, apply it yourself before
   trusting a multi-file aggregate).
3. Efficiency = correct answers / actual summed `cost_usd`, never
   median-cost x row-count.
4. Light-suite numbers are n=1 — read as an indicative spread, not a
   statistically robust estimate.
5. Closed-model reasoning-token counts come from provider usage metadata
   where reported; where the API reports none, a proportional estimate
   from summarized-thinking-text-length vs. total output tokens is used
   instead — check `tokens.reasoning_source` (`"api"` vs `"text_estimate"`)
   before treating a closed-model reasoning figure as directly comparable
   to an open-model one.

## 6. Known artifact: pre-fix trace_status on closed-model tool rows

Runs performed before the `tool_loop.py` provider-awareness fix (see
`CHANGELOG.md`) carry `trace_status: "raw"` on Anthropic-family rows that
went through a tool-invited call, even though Anthropic never returns a
genuine raw trace. Read those specific historical rows as `"summarized"`.
This release does not retroactively relabel them — the field is left as
originally recorded, exactly like every other field in this dataset.
"""


def write_data_readme(out_root: Path, sources_used: list[str]) -> None:
    content = DATA_README_TEMPLATE.format(sources_list=", ".join(f"{s}/" for s in sources_used))
    (out_root / "DATA_README.md").write_text(content, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(REPO_ROOT / "data_release"))
    parser.add_argument("--sources", default=",".join(DEFAULT_SOURCES))
    args = parser.parse_args()

    out_root = Path(args.out)
    sources = [s.strip() for s in args.sources.split(",") if s.strip()]
    for opt in OPTIONAL_SOURCES:
        if opt not in sources and (REPO_ROOT / "results" / opt).is_dir():
            sources.append(opt)

    if out_root.exists():
        shutil.rmtree(out_root)
    out_root.mkdir(parents=True)

    print(f"Sources: {sources}")
    print(f"Output: {out_root}")
    print("-" * 100)

    total_files = 0
    total_rows = 0
    all_hits: list[str] = []
    sources_used: list[str] = []

    for source in sources:
        files, rows, hits = process_source(source, out_root)
        if hits:
            all_hits.extend(hits)
            print(f"  {source:<10} ABORTED — {len(hits)} secret-pattern hit(s)")
            continue
        if files:
            sources_used.append(source)
        total_files += files
        total_rows += rows
        print(f"  {source:<10} {files} file(s), {rows} row(s)")

    if all_hits:
        print("-" * 100)
        print(f"FAILED: {len(all_hits)} secret-pattern hit(s) found. No release written.")
        for h in all_hits[:20]:
            print(f"  {h}")
        if len(all_hits) > 20:
            print(f"  ... and {len(all_hits) - 20} more")
        shutil.rmtree(out_root)
        raise SystemExit(1)

    write_data_readme(out_root, sources_used)

    print("-" * 100)
    print(f"OK: {total_files} file(s), {total_rows} row(s) written to {out_root}")
    print(f"DATA_README.md written")
    print("This directory is staged locally only -- publishing it is a separate decision.")


if __name__ == "__main__":
    main()
