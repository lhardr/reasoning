#!/usr/bin/env python3
"""
Reasoning Benchmark — orchestration entry point.

Usage:
    python3 run.py --smoke                    # run smoke test across all available models
    python3 run.py --smoke --model MODEL_KEY  # smoke test one model
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv

load_dotenv()

from src.accounting import build_account
from src.adapters import PROVIDER_MAP, CredentialMissingError
from src.adapters.base import AdapterError, ModelResponse
from src.config_loader import load_experiment, load_panel, load_prompts
from src.cost import compute_cost
from src.judge import (
    DIMENSIONS,
    JudgeResponse,
    build_rubric_prompt,
    call_judge_openrouter,
    compute_agreement,
)
from src.language_metric import measure_trace_language
from src.model_resolver import print_resolution_table, resolve_models
from src.storage import PHASE2_DIR, RESULTS_DIR, save_phase2_result, save_result, save_trace

# ---------------------------------------------------------------------------
# Smoke test constants
# ---------------------------------------------------------------------------

SMOKE_PROMPT = (
    "What is 15 + 27? Work through this step by step, then give your final answer."
)

SMOKE_ROLES = {"scored", "anchor"}

# Models where reasoning_tokens MUST be > 0 — zero is a regression.
# gpt_5_5: count_only (reasoning count reported, no text)
# deepseek_v4 / glm_5_2 / kimi_k2_7 / mistral_medium_3_5: raw (text present)
# claude_sonnet_4_6 / opus_4_8: summarized (thinking block present)
# gemma_4: raw (tokens estimated from text)
MUST_HAVE_REASONING_TOKENS: set[str] = {
    "deepseek_v4",
    "glm_5_2",
    "kimi_k2_7",
    "gpt_5_5",
    "claude_sonnet_4_6",
    "gemma_4",
    # opus_4_8 excluded: when routed via OpenRouter (no ANTHROPIC_API_KEY),
    # the thinking block is not consistently forwarded. trace_status=absent on
    # low-complexity prompts is accurate data, not a configuration error.
    "mistral_medium_3_5",
}

# ---------------------------------------------------------------------------
# Trace exposure verification
# ---------------------------------------------------------------------------

def _verify_trace(
    response: ModelResponse, expected_exposure: Optional[str]
) -> tuple[bool, str]:
    if expected_exposure is None:
        return True, "n/a (judge stub)"

    status = response.trace_status
    has_trace = response.raw_reasoning_trace is not None
    rtoks = response.reasoning_tokens

    if expected_exposure == "raw":
        ok = has_trace and status == "raw"
        detail = f"trace={'present' if has_trace else 'ABSENT'}, status={status!r}"
    elif expected_exposure == "summarized":
        ok = has_trace and status == "summarized"
        detail = f"trace={'present' if has_trace else 'ABSENT'}, status={status!r}"
    elif expected_exposure == "count_only":
        ok = not has_trace and status == "count_only" and rtoks > 0
        detail = (
            f"trace={'PRESENT' if has_trace else 'absent'}, "
            f"status={status!r}, reasoning_tokens={rtoks}"
        )
    elif expected_exposure == "absent":
        ok = status == "absent"
        detail = f"status={status!r}"
    else:
        ok = False
        detail = f"unknown expected_exposure={expected_exposure!r}"

    return ok, detail


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------

def _fmt_row(
    key: str,
    version: str,
    inp: int,
    reas: int,
    out: int,
    status: str,
    cost: float,
    latency: float,
    verify: str,
    reas_assert: str,
) -> str:
    return (
        f"{key:<22} {version:<28} {inp:>7} {reas:>9} {out:>7}  "
        f"{status:<12} ${cost:>8.5f}  {latency:>7.2f}s  {verify:<20}  {reas_assert}"
    )


def run_smoke(model_filter: Optional[str] = None) -> int:
    """
    Run the smoke test. Returns exit code (0 = all checks passed, 1 = failures).
    """
    panel = load_panel()
    experiment = load_experiment()
    reasoning_effort: str = experiment.get("reasoning_effort", "high")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "_smoke"

    target_keys = [
        k
        for k, cfg in panel.items()
        if cfg.get("role") in SMOKE_ROLES
        and (model_filter is None or k == model_filter)
    ]

    # ------------------------------------------------------------------
    # Step 1: Print model resolution table + fail loudly on bad IDs
    # ------------------------------------------------------------------
    print(f"\n{'='*110}")
    print(f"  Reasoning Benchmark — Smoke Test   run_id={run_id}")
    print(f"  Prompt: {SMOKE_PROMPT!r}")
    print(f"  reasoning_effort={reasoning_effort!r}  (experiment condition, locked across all models)")
    print(f"{'='*110}")

    resolved = resolve_models(panel, target_keys)
    hard_errors = print_resolution_table(resolved)
    if hard_errors > 0:
        print(
            f"\n  !! {hard_errors} model(s) could not be resolved to the intended ID. "
            "Fix panel.yaml before running.\n"
        )
        return 1

    # ------------------------------------------------------------------
    # Step 2: Run each model and collect results
    # ------------------------------------------------------------------
    print(
        f"\n{'Model':<22} {'Version':<28} {'Input':>7} {'Reasoning':>9} {'Output':>7}  "
        f"{'TraceStatus':<12} {'Cost(USD)':>10}  {'Latency':>8}  {'Exposure':20}  {'TokenAssert (src)'}"
    )
    print("-" * 140)

    has_failure = False

    for key in target_keys:
        cfg = panel[key]
        provider = cfg["provider"]
        expected_exposure: Optional[str] = cfg.get("trace_exposure")
        thinking_budget: int = cfg.get("thinking_budget", 4096)

        cls = PROVIDER_MAP.get(provider)
        if cls is None:
            print(f"{key:<22} SKIPPED (unknown provider: {provider})")
            continue

        try:
            adapter = cls(key, cfg)
        except CredentialMissingError as e:
            print(f"{key:<22} SKIPPED — {e}")
            continue

        try:
            response = adapter.call(
                SMOKE_PROMPT,
                thinking_budget=thinking_budget,
                reasoning_effort=reasoning_effort,
            )
        except AdapterError as e:
            print(f"{key:<22} ERROR    — {e}")
            has_failure = True
            continue
        except Exception as e:
            print(f"{key:<22} ERROR    — unexpected: {e}")
            has_failure = True
            continue

        account = build_account(response)
        cost_usd, snapshot_date = compute_cost(key, account)

        save_result(
            run_id=run_id,
            model_key=key,
            prompt=SMOKE_PROMPT,
            response=response,
            account=account,
            cost_usd=cost_usd,
            pricing_snapshot_date=snapshot_date,
            thinking_budget=thinking_budget,
            reasoning_effort=reasoning_effort,
        )

        # Exposure check
        exp_ok, exp_detail = _verify_trace(response, expected_exposure)
        exposure_label = "PASS" if exp_ok else f"MISMATCH ({exp_detail})"
        if not exp_ok:
            has_failure = True

        # Reasoning-token assertion — hard failure if zero where we expect non-zero.
        # Include reasoning_source so "measured" and "estimated" values are never
        # silently mixed in the same comparison column.
        reas_label = ""
        if key in MUST_HAVE_REASONING_TOKENS:
            if account.reasoning_tokens == 0:
                reas_label = "FAIL: reasoning_tokens=0"
                has_failure = True
            else:
                src_tag = "api" if response.reasoning_source == "api" else "est"
                reas_label = f"OK ({account.reasoning_tokens}, {src_tag})"

        print(
            _fmt_row(
                key,
                response.model_version[:27],
                account.input_tokens,
                account.reasoning_tokens,
                account.output_tokens,
                response.trace_status,
                cost_usd,
                response.latency_s,
                exposure_label,
                reas_label,
            )
        )

    print("-" * 140)
    status_line = "ALL CHECKS PASSED" if not has_failure else "FAILURES DETECTED — see FAIL/MISMATCH rows"
    print(f"\n  {status_line}")
    print(f"  Results written to results/{run_id}.jsonl\n")
    return 1 if has_failure else 0


# ---------------------------------------------------------------------------
# Pilot (Phase 1)
# ---------------------------------------------------------------------------

# Models that must have reasoning_tokens > 0 for the pilot to be valid.
# gpt_5_5 and claude_sonnet_4_6 are excluded: their reasoning is always on
# (gpt: count-only; claude: budget-forced). Only the raw-trace models need
# this assertion to catch a dropped include_reasoning flag.
PILOT_MUST_REASON: set[str] = {"deepseek_v4", "glm_5_2", "kimi_k2_7", "gemma_4"}

# Pilot prompt IDs (default); override with --prompts P3,P5
PILOT_DEFAULT_PROMPTS = ["P3", "P5"]


# ---------------------------------------------------------------------------
# Full run constants
# ---------------------------------------------------------------------------

# Trace-exposure regime for each model.
# reasoning_share is comparable ONLY within regime="raw".
# "raw_anchor" (gemma) is raw text but separate from the frontier raw cluster.
# "summarized" and "count_only" are NOT comparable to raw — annotate accordingly.
REGIME_MAP: dict[str, str] = {
    "deepseek_v4": "raw",
    "glm_5_2": "raw",
    "kimi_k2_7": "raw",
    "gemma_4": "raw_anchor",
    "claude_sonnet_4_6": "summarized",
    "gpt_5_5": "count_only",
    "opus_4_8": "summarized",
    "mistral_medium_3_5": "raw",
}

# Canonical display order — groups regimes together
FULL_MODEL_ORDER: list[str] = [
    "deepseek_v4",
    "glm_5_2",
    "kimi_k2_7",
    "gemma_4",
    "claude_sonnet_4_6",
    "gpt_5_5",
    "opus_4_8",
    "mistral_medium_3_5",
]

# Models that expose trace text — language metric is applicable to these
# opus_4_8: summarized (measured on the summary, noted in output)
# mistral_medium_3_5: raw
TRACE_TEXT_MODELS: set[str] = {
    "deepseek_v4",
    "glm_5_2",
    "kimi_k2_7",
    "gemma_4",
    "claude_sonnet_4_6",
    "opus_4_8",
    "mistral_medium_3_5",
}

# ---------------------------------------------------------------------------
# Phase 2 constants
# ---------------------------------------------------------------------------

# Models scored for legibility (raw trace exists)
LEGIBILITY_SCORED: list[str] = [
    "deepseek_v4", "glm_5_2", "kimi_k2_7", "gemma_4", "mistral_medium_3_5"
]

# Models explicitly excluded from Phase 2, with the reason
LEGIBILITY_EXCLUDED: dict[str, str] = {
    "claude_sonnet_4_6": (
        "summarized — scoring would measure Anthropic's summarizer, "
        "not the model's raw reasoning process"
    ),
    "opus_4_8": (
        "summarized — same constraint as claude_sonnet_4_6; "
        "legibility scores would reflect Anthropic's summarizer, not Opus's raw CoT"
    ),
    "gpt_5_5": (
        "count_only — no trace text exists to score"
    ),
}

# Judge models (from panel.yaml)
JUDGE_KEYS: list[str] = ["minimax", "gemini_3_1_pro"]

# Maps judge panel key → pricing.yaml key (for cost calculation)
JUDGE_PRICING_KEY: dict[str, str] = {
    "minimax": "minimax",
    "gemini_3_1_pro": "gemini_3_1_pro",
}

# High-disagreement threshold (per-dimension absolute diff)
HIGH_DISAGREEMENT_THRESHOLD: int = 2


def run_pilot(prompt_ids: list[str]) -> int:
    """
    Phase 1 pilot: run selected prompts across all scored+anchor models.
    Economy axis only — no judges, no correctness scoring.
    Returns exit code (0 = pass, 1 = failures).
    """
    panel = load_panel()
    experiment = load_experiment()
    reasoning_effort: str = experiment.get("reasoning_effort", "high")

    # load_prompts() strips facit — it must never appear on the request path.
    prompts = load_prompts()

    # Validate requested prompt IDs.
    missing = [pid for pid in prompt_ids if pid not in prompts]
    if missing:
        print(f"\n  ERROR: unknown prompt ID(s): {', '.join(missing)}")
        print(f"  Available: {', '.join(sorted(prompts))}\n")
        return 1

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "_pilot"
    pilot_dir = RESULTS_DIR / "pilot"
    traces_dir = pilot_dir / f"{run_id}_traces"

    model_keys = [
        k for k, cfg in panel.items() if cfg.get("role") in SMOKE_ROLES
    ]

    # ----------------------------------------------------------------
    # Header
    # ----------------------------------------------------------------
    print(f"\n{'='*110}")
    print(f"  Reasoning Benchmark — Phase 1 Pilot   run_id={run_id}")
    prompt_labels = ", ".join(
        f"{pid} ({prompts[pid].get('type','?')}/{prompts[pid].get('language_probe','?')})"
        for pid in prompt_ids
    )
    print(f"  Prompts: {prompt_labels}")
    print(f"  reasoning_effort={reasoning_effort!r}  |  economy axis only — no judges, no scoring")
    print(f"{'='*110}")

    # Model resolution
    resolved = resolve_models(panel, model_keys)
    hard_errors = print_resolution_table(resolved)
    if hard_errors > 0:
        print(f"\n  !! {hard_errors} model(s) not resolved. Fix panel.yaml.\n")
        return 1

    # ----------------------------------------------------------------
    # Per-prompt runs
    # ----------------------------------------------------------------
    has_failure = False
    # costs[model_key] = list of per-call cost floats
    costs_by_model: dict[str, list[float]] = {k: [] for k in model_keys}

    col_hdr = (
        f"\n{'Model':<22} {'Input':>7} {'Reasoning':>9} {'Output':>7}  "
        f"{'Reas%':>6}  {'Src':<4}  {'Cost(USD)':>10}  {'Latency':>8}  "
        f"{'TraceStatus':<13} {'TokenAssert'}"
    )
    col_sep = "-" * 120

    for pid in prompt_ids:
        p = prompts[pid]

        # Runtime guard: facit must not be present on the request path.
        assert "facit" not in p, (
            f"CRITICAL SECURITY VIOLATION: facit present in request-path object for {pid}"
        )
        prompt_text: str = p["prompt"]
        p_type = p.get("type", "")
        p_probe = p.get("language_probe", "")

        print(f"\n{'─'*110}")
        print(f"  [{pid}]  {p_type} / {p_probe}")
        print(f"  Prompt (first 120 chars): {prompt_text[:120].strip()!r}")
        print(f"{'─'*110}")
        print(col_hdr)
        print(col_sep)

        for key in model_keys:
            cfg = panel[key]
            provider = cfg["provider"]
            thinking_budget: int = cfg.get("thinking_budget", 4096)

            cls = PROVIDER_MAP.get(provider)
            if cls is None:
                print(f"{key:<22} SKIPPED (unknown provider: {provider})")
                continue

            try:
                adapter = cls(key, cfg)
            except CredentialMissingError as e:
                print(f"{key:<22} SKIPPED — {e}")
                continue

            try:
                response = adapter.call(
                    prompt_text,
                    thinking_budget=thinking_budget,
                    reasoning_effort=reasoning_effort,
                )
            except AdapterError as e:
                print(f"{key:<22} ERROR — {e}")
                has_failure = True
                continue
            except Exception as e:
                print(f"{key:<22} ERROR — unexpected: {e}")
                has_failure = True
                continue

            account = build_account(response)
            cost_usd, snapshot_date = compute_cost(key, account)
            costs_by_model[key].append(cost_usd)

            # Save structured record.
            save_result(
                run_id=run_id,
                model_key=key,
                prompt=prompt_text,
                response=response,
                account=account,
                cost_usd=cost_usd,
                pricing_snapshot_date=snapshot_date,
                thinking_budget=thinking_budget,
                reasoning_effort=reasoning_effort,
                results_dir=pilot_dir,
                extra={"prompt_id": pid, "prompt_type": p_type, "language_probe": p_probe},
            )

            # Save human-readable trace.
            save_trace(
                traces_dir=traces_dir,
                run_id=run_id,
                model_key=key,
                prompt_id=pid,
                prompt_meta=p,
                prompt_text=prompt_text,
                answer_text=response.answer_text,
                reasoning_trace=response.raw_reasoning_trace,
                trace_status=response.trace_status,
                reasoning_tokens=account.reasoning_tokens,
                reasoning_source=response.reasoning_source,
            )

            # Token assertion for raw-trace models.
            if key in PILOT_MUST_REASON:
                if account.reasoning_tokens == 0:
                    tok_assert = "FAIL: reasoning_tokens=0"
                    has_failure = True
                else:
                    src_tag = "api" if response.reasoning_source == "api" else "est"
                    tok_assert = f"OK ({account.reasoning_tokens}, {src_tag})"
            else:
                src_tag = "api" if response.reasoning_source == "api" else "est"
                tok_assert = f"{account.reasoning_tokens} ({src_tag})"

            reas_share_pct = account.reasoning_share * 100
            src_tag = "api" if response.reasoning_source == "api" else "est"

            print(
                f"{key:<22} {account.input_tokens:>7} {account.reasoning_tokens:>9} "
                f"{account.output_tokens:>7}  {reas_share_pct:>5.1f}%  {src_tag:<4}  "
                f"${cost_usd:>8.5f}  {response.latency_s:>7.2f}s  "
                f"{response.trace_status:<13} {tok_assert}"
            )

        print(col_sep)

    # ----------------------------------------------------------------
    # Per-model summary
    # ----------------------------------------------------------------
    n_prompts = len(prompt_ids)
    print(f"\n{'─'*110}")
    print(f"  Per-model summary  ({n_prompts} prompt(s) × {len(model_keys)} models)")
    print(f"{'─'*110}")
    print(f"  {'Model':<22}  {'Calls':>5}  {'Total $':>10}  {'Avg $/prompt':>14}")
    print(f"  {'-'*60}")
    total_pilot_cost = 0.0
    avg_by_model: dict[str, float] = {}
    for key in model_keys:
        call_costs = costs_by_model[key]
        if not call_costs:
            print(f"  {key:<22}  {'—':>5}  {'—':>10}  {'—':>14}")
            avg_by_model[key] = 0.0
            continue
        total = sum(call_costs)
        avg = total / len(call_costs)
        avg_by_model[key] = avg
        total_pilot_cost += total
        print(f"  {key:<22}  {len(call_costs):>5}  ${total:>9.5f}  ${avg:>13.5f}")
    print(f"  {'-'*60}")
    print(f"  {'PILOT TOTAL':<22}  {'':>5}  ${total_pilot_cost:>9.5f}")

    # ----------------------------------------------------------------
    # Cost projection — full run (10 × 6)
    # ----------------------------------------------------------------
    full_prompts = 10
    full_models = len([k for k in model_keys if avg_by_model.get(k, 0) > 0])
    total_projected = sum(avg_by_model[k] * full_prompts for k in model_keys)

    print(f"\n{'═'*70}")
    print(f"  COST PROJECTION — Full run ({full_prompts} prompts × {full_models} models)")
    print(f"  Based on pilot averages ({n_prompts} prompt(s) per model)")
    print(f"{'═'*70}")
    print(f"  {'Model':<22}  {'Avg $/prompt':>14}  {f'{full_prompts}×6 projected':>16}")
    print(f"  {'-'*58}")
    for key in model_keys:
        avg = avg_by_model.get(key, 0.0)
        proj = avg * full_prompts
        if avg > 0:
            print(f"  {key:<22}  ${avg:>13.5f}  ${proj:>15.4f}")
        else:
            print(f"  {key:<22}  {'—':>14}  {'—':>16}")
    print(f"  {'-'*58}")
    print(f"  {'TOTAL':<22}  {'':>14}  ${total_projected:>15.4f}")
    print(f"{'═'*70}")

    # ----------------------------------------------------------------
    # Footer
    # ----------------------------------------------------------------
    status_line = "ALL ASSERTIONS PASSED" if not has_failure else "FAILURES — see FAIL rows above"
    print(f"\n  {status_line}")
    print(f"  Structured records  → results/pilot/{run_id}.jsonl")
    print(f"  Raw traces          → results/pilot/{run_id}_traces/<model>_<prompt>.txt\n")

    return 1 if has_failure else 0


# ---------------------------------------------------------------------------
# Full run (Phase 1 — all 10 prompts × all scored+anchor models)
# ---------------------------------------------------------------------------

_FULL_COL_HDR = (
    f"  {'Model':<22} {'Inp':>6} {'Reas':>7} {'Out':>6}  {'Reas%':>7}  "
    f"{'Regime':<12} {'Src':<4}  {'Cost($)':>10}  {'Lat':>7}  "
    f"{'TrStatus':<12} {'Lang':<7} {'SW':>3}  Conf"
)
_FULL_COL_SEP = "  " + "─" * 132


def run_full(model_filter: Optional[list[str]] = None) -> int:
    """
    Phase 1 full economy run: all 10 prompts × all scored+anchor models.
    Adds segment-aware language metrics to every exposed trace.
    Regime-separates reasoning_share: raw cluster (deepseek/glm/kimi) only.

    model_filter: if given, restrict to these model keys (e.g. ["opus_4_8", "mistral_medium_3_5"]).
    Returns exit code (0 = all assertions passed, 1 = any failure/error).
    """
    panel = load_panel()
    experiment = load_experiment()
    reasoning_effort: str = experiment.get("reasoning_effort", "high")
    prompts = load_prompts()

    all_prompt_ids = sorted(prompts.keys(), key=lambda p: int(p[1:]))

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "_full"
    full_dir = RESULTS_DIR / "full"
    traces_dir = full_dir / f"{run_id}_traces"

    model_keys_ordered = [
        k for k in FULL_MODEL_ORDER
        if k in panel and panel[k].get("role") in SMOKE_ROLES
        and (model_filter is None or k in model_filter)
    ]

    n_calls = len(all_prompt_ids) * len(model_keys_ordered)
    print(f"\n{'═'*120}")
    print(f"  Reasoning Benchmark — Phase 1 Full Economy Run   run_id={run_id}")
    print(
        f"  Prompts: {', '.join(all_prompt_ids)}"
        f"  ({len(all_prompt_ids)} × {len(model_keys_ordered)} models = {n_calls} calls)"
    )
    print(f"  reasoning_effort={reasoning_effort!r}  |  economy axis only — no judges, no scoring")
    print(f"{'═'*120}")

    resolved = resolve_models(panel, model_keys_ordered)
    hard_errors = print_resolution_table(resolved)
    if hard_errors > 0:
        print(f"\n  !! {hard_errors} model(s) not resolved. Fix panel.yaml.\n")
        return 1

    has_failure = False
    # Collect per-call data for aggregate tables at the end
    agg: list[dict] = []

    # --- Per-prompt loop ---
    for pid in all_prompt_ids:
        p = prompts[pid]
        assert "facit" not in p, (
            f"CRITICAL SECURITY VIOLATION: facit in request-path object for {pid}"
        )
        prompt_text: str = p["prompt"]
        p_type = p.get("type", "?")
        p_probe = p.get("language_probe", "?")
        p_load = p.get("reasoning_load", "?")
        p_correct = p.get("carries_correctness", False)

        print(f"\n{'═'*120}")
        print(
            f"  [{pid}]  {p_type} / {p_probe}"
            f"  (load: {p_load}, carries_correctness: {p_correct})"
        )
        print(f"  {prompt_text[:110].strip()!r}")
        print(f"{'═'*120}")
        print(_FULL_COL_HDR)
        print(_FULL_COL_SEP)

        for key in model_keys_ordered:
            cfg = panel[key]
            provider = cfg["provider"]
            thinking_budget: int = cfg.get("thinking_budget", 4096)
            regime = REGIME_MAP.get(key, "unknown")

            cls = PROVIDER_MAP.get(provider)
            if cls is None:
                print(f"  {key:<22} SKIPPED (unknown provider: {provider})")
                continue

            try:
                adapter = cls(key, cfg)
            except CredentialMissingError as e:
                print(f"  {key:<22} SKIPPED — {e}")
                continue

            try:
                response = adapter.call(
                    prompt_text,
                    thinking_budget=thinking_budget,
                    reasoning_effort=reasoning_effort,
                )
            except AdapterError as e:
                print(f"  {key:<22} ERROR — {e}")
                has_failure = True
                continue
            except Exception as e:
                print(f"  {key:<22} ERROR — unexpected: {e}")
                has_failure = True
                continue

            account = build_account(response)
            cost_usd, snapshot_date = compute_cost(key, account)

            # Language metric — only for models that expose trace text
            if key in TRACE_TEXT_MODELS and response.raw_reasoning_trace:
                lm = measure_trace_language(response.raw_reasoning_trace)
            else:
                lm = measure_trace_language(None)

            # Persist JSONL record
            save_result(
                run_id=run_id,
                model_key=key,
                prompt=prompt_text,
                response=response,
                account=account,
                cost_usd=cost_usd,
                pricing_snapshot_date=snapshot_date,
                thinking_budget=thinking_budget,
                reasoning_effort=reasoning_effort,
                results_dir=full_dir,
                extra={
                    "prompt_id": pid,
                    "prompt_type": p_type,
                    "language_probe": p_probe,
                    "reasoning_load": p_load,
                    "regime": regime,
                    "language_metric": lm,
                },
            )

            # Persist human-readable trace
            save_trace(
                traces_dir=traces_dir,
                run_id=run_id,
                model_key=key,
                prompt_id=pid,
                prompt_meta=p,
                prompt_text=prompt_text,
                answer_text=response.answer_text,
                reasoning_trace=response.raw_reasoning_trace,
                trace_status=response.trace_status,
                reasoning_tokens=account.reasoning_tokens,
                reasoning_source=response.reasoning_source,
            )

            # Collect for aggregates
            agg.append({
                "pid": pid,
                "reasoning_load": p_load,
                "language_probe": p_probe,
                "model_key": key,
                "regime": regime,
                "reasoning_share": account.reasoning_share,
                "cost_usd": cost_usd,
                "primary_lang": lm.get("primary_trace_language"),
                "sw_count": lm.get("language_switch_count", 0),
                "sw_conf": lm.get("switch_count_confidence", "?"),
            })

            # --- Format output row ---
            reas_share_pct = account.reasoning_share * 100
            share_str = f"{reas_share_pct:.1f}%"
            if regime == "summarized":
                reas_pct_str = share_str + "†"   # not comparable to raw
            elif regime == "count_only":
                reas_pct_str = share_str + "‡"   # text hidden
            else:
                reas_pct_str = share_str

            src_tag = "api" if response.reasoning_source == "api" else "est"

            if key in TRACE_TEXT_MODELS:
                lang_str = lm.get("primary_trace_language") or "?"
                sw_str = str(lm.get("language_switch_count", 0))
                conf_str = (lm.get("switch_count_confidence") or "?")
            else:
                lang_str = sw_str = conf_str = "—"

            # Reasoning-token assertion: warn if zero where non-zero is expected
            tok_warn = ""
            if key in MUST_HAVE_REASONING_TOKENS and account.reasoning_tokens == 0:
                tok_warn = " ← WARN: reasoning_tokens=0"
                has_failure = True

            print(
                f"  {key:<22} {account.input_tokens:>6} {account.reasoning_tokens:>7}"
                f" {account.output_tokens:>6}  {reas_pct_str:>7}  "
                f"{regime:<12} {src_tag:<4}  ${cost_usd:>9.5f}  {response.latency_s:>6.2f}s  "
                f"{response.trace_status:<12} {lang_str:<7} {sw_str:>3}  {conf_str}"
                f"{tok_warn}"
            )

        print(_FULL_COL_SEP)
        print(
            "  † Claude: reas% reflects thinking-budget allocation, not raw CoT fraction  "
            "‡ GPT-5.5: reasoning text hidden; token count from API usage field"
        )

    # ─────────────────────────────────────────────────────────────
    # AGGREGATE 1 — Reasoning share by reasoning_load (raw cluster)
    # ─────────────────────────────────────────────────────────────
    print(f"\n{'═'*80}")
    print(f"  AGGREGATE 1 — Reasoning share by reasoning_load")
    print(f"  Raw cluster only: deepseek_v4, glm_5_2, kimi_k2_7")
    print(f"{'═'*80}")
    print(f"  {'Load':<14} {'n':>5}  {'Avg Reas%':>10}  {'Min%':>8}  {'Max%':>8}")
    print(f"  {'─'*52}")
    raw_rows = [r for r in agg if r["regime"] == "raw"]
    for load in ("low", "medium", "high", "very_high"):
        rows = [r for r in raw_rows if r["reasoning_load"] == load]
        if not rows:
            continue
        shares = [r["reasoning_share"] * 100 for r in rows]
        avg = sum(shares) / len(shares)
        print(
            f"  {load:<14} {len(shares):>5}  {avg:>9.1f}%"
            f"  {min(shares):>7.1f}%  {max(shares):>7.1f}%"
        )
    print(f"  {'─'*52}")

    # ─────────────────────────────────────────────────────────────
    # AGGREGATE 2 — Cost per prompt (all models)
    # ─────────────────────────────────────────────────────────────
    print(f"\n{'═'*120}")
    print(f"  AGGREGATE 2 — Cost per prompt (USD)")
    print(f"{'═'*120}")
    # Abbreviate long model keys for header
    abbrevs = {
        "deepseek_v4": "deepseek",
        "glm_5_2": "glm",
        "kimi_k2_7": "kimi",
        "gemma_4": "gemma",
        "claude_sonnet_4_6": "claude",
        "gpt_5_5": "gpt",
        "opus_4_8": "opus",
        "mistral_medium_3_5": "mistral",
    }
    hdr_cells = "  ".join(f"{abbrevs.get(k, k[:8]):<9}" for k in model_keys_ordered)
    print(f"  {'Prompt':<7}  {'Load':<10} {hdr_cells}  {'Total':>10}")
    print(f"  {'─'*100}")

    model_totals: dict[str, float] = {k: 0.0 for k in model_keys_ordered}
    grand_total = 0.0

    for pid in all_prompt_ids:
        pid_by_model = {r["model_key"]: r for r in agg if r["pid"] == pid}
        load = prompts[pid].get("reasoning_load", "?")
        row_total = 0.0
        cells = []
        for k in model_keys_ordered:
            r = pid_by_model.get(k)
            if r:
                c = r["cost_usd"]
                row_total += c
                model_totals[k] += c
                cells.append(f"${c:.5f}")
            else:
                cells.append(f"{'—':<9}")
        grand_total += row_total
        print(f"  {pid:<7}  {load:<10} {'  '.join(cells)}  ${row_total:.5f}")

    print(f"  {'─'*100}")
    total_cells = "  ".join(f"${model_totals[k]:.5f}" for k in model_keys_ordered)
    print(f"  {'TOTAL':<7}  {'':10} {total_cells}  ${grand_total:.5f}")
    print(f"{'═'*120}")

    # ─────────────────────────────────────────────────────────────
    # AGGREGATE 3 — Primary trace language by prompt
    # ─────────────────────────────────────────────────────────────
    trace_models = [k for k in model_keys_ordered if k in TRACE_TEXT_MODELS]
    abbrev_hdrs = "  ".join(f"{abbrevs.get(k, k[:8]):<7}" for k in trace_models)

    print(f"\n{'═'*100}")
    print(f"  AGGREGATE 3 — Primary trace language by prompt")
    print(f"  (gpt_5_5 excluded — trace text not exposed)")
    print(f"{'═'*100}")
    print(f"  {'Prompt':<7}  {'Probe':<18}  {abbrev_hdrs}")
    print(f"  {'─'*85}")

    da_prompts: set[str] = set()
    for pid in all_prompt_ids:
        pid_by_model = {r["model_key"]: r for r in agg if r["pid"] == pid}
        probe = prompts[pid].get("language_probe", "?")
        cells = []
        for k in trace_models:
            r = pid_by_model.get(k)
            if r:
                lang = r["primary_lang"] or "?"
                cells.append(f"{lang:<7}")
                if lang == "da":
                    da_prompts.add(pid)
            else:
                cells.append(f"{'—':<7}")
        print(f"  {pid:<7}  {probe:<18}  {'  '.join(cells)}")

    print(f"  {'─'*85}")
    if da_prompts:
        print(
            f"\n  Danish (da) detected as primary trace language in:"
            f" {', '.join(sorted(da_prompts, key=lambda p: int(p[1:])))}"
        )
    else:
        print(f"\n  No prompt pulled Danish as the primary trace language in any model.")
    print(f"{'═'*100}")

    # ─────────────────────────────────────────────────────────────
    # Footer
    # ─────────────────────────────────────────────────────────────
    status_line = (
        "ALL ASSERTIONS PASSED"
        if not has_failure
        else "WARNINGS/ERRORS detected — review rows above"
    )
    print(f"\n  {status_line}")
    print(f"  Structured records  → results/full/{run_id}.jsonl")
    print(f"  Raw traces          → results/full/{run_id}_traces/<model>_<prompt>.txt")
    print(f"  Calls completed: {len(agg)} / {n_calls}")
    print()
    return 1 if has_failure else 0


# ---------------------------------------------------------------------------
# Phase 2 helpers
# ---------------------------------------------------------------------------

def _load_phase1_jsonl(run_id: Optional[str] = None) -> tuple[list[dict], str]:
    """
    Load the Phase 1 full-run JSONL. Returns (rows, run_id).
    Uses most-recent results/full/*.jsonl when run_id is None.
    """
    full_dir = RESULTS_DIR / "full"
    if run_id:
        path = full_dir / f"{run_id}.jsonl"
    else:
        candidates = sorted(full_dir.glob("*_full.jsonl"))
        if not candidates:
            raise FileNotFoundError(f"No full-run JSONL found in {full_dir}")
        path = candidates[-1]
    if not path.exists():
        raise FileNotFoundError(f"Phase 1 JSONL not found: {path}")
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(__import__("json").loads(line))
    return rows, path.stem  # stem = run_id without .jsonl


def _judge_one(
    judge_key: str,
    judge_cfg: dict,
    prompt_text: str,
    trace_text: str,
) -> JudgeResponse:
    """Call one judge on one (prompt, trace) pair."""
    rubric = build_rubric_prompt(prompt_text, trace_text)
    model_id = judge_cfg["openrouter_model_id"]
    pricing_key = JUDGE_PRICING_KEY[judge_key]
    return call_judge_openrouter(model_id, rubric, pricing_key)


def _print_judge_row(
    judge_key: str,
    jr: JudgeResponse,
) -> None:
    """Print a compact two-line judge result block."""
    if jr.parse_ok:
        r = jr.scores.get("redundancy", "?")
        c = jr.scores.get("coherence", "?")
        r_just = jr.justifications.get("redundancy", "")
        c_just = jr.justifications.get("coherence", "")
        print(f"  {judge_key:<18}  Redund={r}  Coher={c}"
              f"  ({jr.latency_s:.1f}s  ${jr.cost_usd:.5f})")
        print(f"    redundancy:  {r_just[:90]}")
        print(f"    coherence:   {c_just[:90]}")
    else:
        print(f"  {judge_key:<18}  PARSE ERROR — {jr.parse_error[:80]}")


# ---------------------------------------------------------------------------
# Phase 2 — validate-judges gate (Gemma only)
# ---------------------------------------------------------------------------

def run_validate_judges(source_run_id: Optional[str] = None) -> int:
    """
    Gate step: run both judges on Gemma's traces only (English/Danish — readable
    by Lars). Print a side-by-side of trace excerpt + judge scores + justifications
    so the human can verify judge quality before trusting them on Chinese traces.

    STOPS HERE. Does not proceed to Chinese traces. Run --judge after confirmation.
    """
    panel = load_panel()

    try:
        phase1_rows, p1_run_id = _load_phase1_jsonl(source_run_id)
    except FileNotFoundError as e:
        print(f"\n  ERROR: {e}\n")
        return 1

    gemma_rows = [r for r in phase1_rows if r["model_key"] == "gemma_4"]
    gemma_rows.sort(key=lambda r: int(r["prompt_id"][1:]))

    if not gemma_rows:
        print("\n  ERROR: No gemma_4 records in Phase 1 JSONL.\n")
        return 1

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "_validate"

    print(f"\n{'═'*100}")
    print(f"  PHASE 2 — JUDGE VALIDATION GATE")
    print(f"  Source: {p1_run_id}  |  Scoring: gemma_4 only ({len(gemma_rows)} traces)")
    print(f"  Both judges read Gemma traces (English) — Lars can verify scores before trusting on Chinese.")
    print(f"  LEGIBILITY ONLY: correctness and faithfulness are out of scope.")
    print(f"{'═'*100}")

    has_error = False
    validation_records: list[dict] = []

    for row in gemma_rows:
        pid = row["prompt_id"]
        p_type = row.get("prompt_type", "?")
        p_probe = row.get("language_probe", "?")
        p_load = row.get("reasoning_load", "?")
        prompt_text = row["prompt"]
        trace_text = row.get("raw_reasoning_trace") or ""

        print(f"\n{'─'*100}")
        print(f"  [{pid}]  {p_type} / {p_probe}  (load: {p_load})")
        print(f"  Prompt: {prompt_text[:90].strip()!r}")

        if not trace_text.strip():
            print(f"  SKIPPED — no trace text (trace_status={row.get('trace_status')})")
            continue

        trace_excerpt = trace_text[:500].replace("\n", " ↵ ")
        print(f"\n  Trace excerpt (first 500 chars):")
        print(f"  {trace_excerpt!r}")
        print()

        judge_responses: dict[str, JudgeResponse] = {}
        for judge_key in JUDGE_KEYS:
            judge_cfg = panel.get(judge_key, {})
            if not judge_cfg.get("openrouter_model_id"):
                print(f"  {judge_key}: SKIPPED — no openrouter_model_id in panel.yaml")
                continue
            try:
                jr = _judge_one(judge_key, judge_cfg, prompt_text, trace_text)
            except Exception as e:
                print(f"  {judge_key}: ERROR — {e}")
                has_error = True
                continue
            judge_responses[judge_key] = jr
            _print_judge_row(judge_key, jr)

        # Agreement between the two judges on this trace — only when both parsed OK
        agr_val: Optional[dict] = None
        if len(judge_responses) == 2:
            jr0 = judge_responses[JUDGE_KEYS[0]]
            jr1 = judge_responses[JUDGE_KEYS[1]]
            if jr0.parse_ok and jr1.parse_ok:
                agr_val = compute_agreement(jr0.scores, jr1.scores)
                flag = "  ← HIGH DISAGREEMENT" if agr_val["high_disagreement"] else ""
                print(
                    f"\n  Agreement:  "
                    + "  ".join(
                        f"{dim}=Δ{agr_val['dim_diffs'].get(dim,'?')}"
                        for dim in DIMENSIONS
                    )
                    + f"  mean_diff={agr_val['mean_diff']}{flag}"
                )
            else:
                failed = [k for k in JUDGE_KEYS if not judge_responses[k].parse_ok]
                print(f"\n  Agreement:  n/a ({', '.join(failed)} parse failed)")

        # Save validation records
        for judge_key, jr in judge_responses.items():
            save_phase2_result(
                run_id=run_id,
                source_run_id=p1_run_id,
                model_key="gemma_4",
                prompt_id=pid,
                prompt_type=p_type,
                language_probe=p_probe,
                reasoning_load=p_load,
                judge_key=judge_key,
                judge_response=jr,
                agreement=agr_val,
                phase1_language_metric=row.get("language_metric"),
                trace_status=row.get("trace_status", "raw"),
                results_dir=PHASE2_DIR,
            )
            validation_records.append({"pid": pid, "judge": judge_key, "jr": jr})

    print(f"\n{'═'*100}")
    print(f"  GATE REACHED")
    print(f"  {len(gemma_rows)} Gemma traces scored by both judges.")
    print(f"  Validation records saved → results/phase2/{run_id}.jsonl")
    print()
    print(f"  Review the trace excerpts and judge scores above.")
    print(f"  If the scores match your reading of the traces, proceed with:")
    print()
    print(f"    python3 run.py --judge")
    print()
    print(f"  This will score all four raw-trace models (deepseek/glm/kimi + gemma).")
    print(f"  Claude and GPT are excluded — no scorable trace text exists for them.")
    print(f"{'═'*100}\n")

    return 1 if has_error else 0


# ---------------------------------------------------------------------------
# Phase 2 — full legibility scoring
# ---------------------------------------------------------------------------

def run_judge(source_run_id: Optional[str] = None) -> int:
    """
    Phase 2 full legibility scoring.
    Both judges score all 4 raw-trace models (deepseek/glm/kimi + gemma).
    Claude and GPT are explicitly excluded — reasons stated in output.
    LEGIBILITY ONLY — no correctness, no faithfulness, no economy mixing.
    """
    import statistics

    panel = load_panel()

    try:
        phase1_rows, p1_run_id = _load_phase1_jsonl(source_run_id)
    except FileNotFoundError as e:
        print(f"\n  ERROR: {e}\n")
        return 1

    # Compute which scored models actually appear in this source JSONL.
    # This allows running --judge on a partial JSONL (e.g. two new models only)
    # without noisy "MISSING" rows for the models that weren't in that run.
    models_in_jsonl: set[str] = {r["model_key"] for r in phase1_rows}
    effective_scored: list[str] = [k for k in LEGIBILITY_SCORED if k in models_in_jsonl]

    # Build index: (model_key, prompt_id) → row
    p1_index: dict[tuple[str, str], dict] = {
        (r["model_key"], r["prompt_id"]): r
        for r in phase1_rows
        if r["model_key"] in effective_scored
    }

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "_phase2"
    all_pids = sorted(
        {r["prompt_id"] for r in phase1_rows},
        key=lambda p: int(p[1:])
    )

    n_total = len(effective_scored) * len(all_pids) * len(JUDGE_KEYS)

    print(f"\n{'═'*110}")
    print(f"  PHASE 2 — Legibility Scoring   run_id={run_id}")
    print(f"  Source: {p1_run_id}")
    print(f"  Models: {', '.join(effective_scored)}")
    print(f"  Judges: {', '.join(JUDGE_KEYS)}")
    print(f"  Calls: {len(effective_scored)} models × {len(all_pids)} prompts × {len(JUDGE_KEYS)} judges = {n_total}")
    print(f"  LEGIBILITY ONLY — correctness, faithfulness, and economy are out of scope.")
    print(f"{'═'*110}")

    # Explicit exclusion note
    print(f"\n  EXCLUDED FROM LEGIBILITY SCORING (transparency finding):")
    for mk, reason in LEGIBILITY_EXCLUDED.items():
        print(f"    {mk:<24}  {reason}")
    print(
        f"\n  This is a structural finding: the qualitative legibility axis cannot run"
        f"\n  on closed or summarized traces. Only raw-trace models can be assessed.\n"
    )

    has_error = False
    # scored_data[(model_key, pid, judge_key)] = JudgeResponse
    scored_data: dict[tuple[str, str, str], JudgeResponse] = {}
    # agg list for aggregate tables
    agg_records: list[dict] = []

    SEP = "─" * 110

    for model_key in effective_scored:
        print(f"\n{'═'*110}")
        print(f"  Model: {model_key}")
        print(f"{'═'*110}")
        print(f"\n  {'Prompt':<8}  {'Load':<10}  {'Judge':<18}  {'Redund':>7}  {'Coher':>7}  {'Δ':>4}  {'Cost':>10}  Justifications")
        print(f"  {SEP}")

        for pid in all_pids:
            p1_row = p1_index.get((model_key, pid))
            if p1_row is None:
                print(f"  {pid:<8}  MISSING in Phase 1 JSONL — skipping")
                continue

            trace_text = p1_row.get("raw_reasoning_trace") or ""
            prompt_text = p1_row["prompt"]
            p_type = p1_row.get("prompt_type", "?")
            p_probe = p1_row.get("language_probe", "?")
            p_load = p1_row.get("reasoning_load", "?")

            if not trace_text.strip():
                print(f"  {pid:<8}  {p_load:<10}  SKIPPED — no trace text")
                continue

            prompt_responses: dict[str, JudgeResponse] = {}

            for judge_key in JUDGE_KEYS:
                judge_cfg = panel.get(judge_key, {})
                if not judge_cfg.get("openrouter_model_id"):
                    print(f"  {pid:<8}  {p_load:<10}  {judge_key:<18}  SKIPPED — no openrouter_model_id")
                    continue

                try:
                    jr = _judge_one(judge_key, judge_cfg, prompt_text, trace_text)
                except Exception as e:
                    print(f"  {pid:<8}  {p_load:<10}  {judge_key:<18}  ERROR — {e}")
                    has_error = True
                    continue

                scored_data[(model_key, pid, judge_key)] = jr
                prompt_responses[judge_key] = jr

            # Compute agreement only when both judges responded AND both parsed OK
            agr: Optional[dict] = None
            if len(prompt_responses) == 2:
                jr0 = prompt_responses[JUDGE_KEYS[0]]
                jr1 = prompt_responses[JUDGE_KEYS[1]]
                if jr0.parse_ok and jr1.parse_ok:
                    agr = compute_agreement(jr0.scores, jr1.scores)

            # Print row(s) + save
            for i, judge_key in enumerate(JUDGE_KEYS):
                jr = prompt_responses.get(judge_key)
                if jr is None:
                    continue

                # Save
                save_phase2_result(
                    run_id=run_id,
                    source_run_id=p1_run_id,
                    model_key=model_key,
                    prompt_id=pid,
                    prompt_type=p_type,
                    language_probe=p_probe,
                    reasoning_load=p_load,
                    judge_key=judge_key,
                    judge_response=jr,
                    agreement=agr if i == 0 else None,
                    phase1_language_metric=p1_row.get("language_metric"),
                    trace_status=p1_row.get("trace_status", "raw"),
                    results_dir=PHASE2_DIR,
                )

                # Print
                if jr.parse_ok:
                    r = jr.scores.get("redundancy", "?")
                    c = jr.scores.get("coherence", "?")
                    delta_str = ""
                    if agr and i == 1:
                        d = agr["max_diff"]
                        flag = "!" if agr["high_disagreement"] else " "
                        delta_str = f"{d}{flag}"
                    r_just = jr.justifications.get("redundancy", "")[:40]
                    c_just = jr.justifications.get("coherence", "")[:40]
                    print(
                        f"  {pid:<8}  {p_load:<10}  {judge_key:<18}  {r:>7}  {c:>7}  "
                        f"{delta_str:>4}  ${jr.cost_usd:>8.5f}  "
                        f"R:{r_just!r} / C:{c_just!r}"
                    )
                else:
                    print(
                        f"  {pid:<8}  {p_load:<10}  {judge_key:<18}  "
                        f"PARSE ERROR — {jr.parse_error[:60]}"
                    )
                    has_error = True

                # Collect for aggregates
                if jr.parse_ok:
                    agg_records.append({
                        "model_key": model_key,
                        "prompt_id": pid,
                        "prompt_type": p_type,
                        "reasoning_load": p_load,
                        "judge_key": judge_key,
                        "redundancy": jr.scores.get("redundancy", 0),
                        "coherence": jr.scores.get("coherence", 0),
                        "cost_usd": jr.cost_usd,
                        "high_disagreement": agr["high_disagreement"] if agr else False,
                        "max_diff": agr["max_diff"] if agr else 0,
                    })

        print(f"  {SEP}")

    # ─────────────────────────────────────────────────────────────────────────
    # AGGREGATE TABLES
    # ─────────────────────────────────────────────────────────────────────────

    def avg(vals: list) -> str:
        return f"{statistics.mean(vals):.2f}" if vals else "—"

    # --- Table 1: Average legibility scores by model and judge ---
    print(f"\n{'═'*90}")
    print(f"  AGGREGATE 1 — Average legibility by model  (1–5 scale; higher coher = better, lower redund = better)")
    print(f"{'═'*90}")
    print(f"  {'Model':<22}  {'Judge':<18}  {'Avg Redund':>10}  {'Avg Coher':>10}  {'Calls':>6}")
    print(f"  {'─'*70}")
    for model_key in effective_scored:
        for judge_key in JUDGE_KEYS:
            recs = [r for r in agg_records if r["model_key"] == model_key and r["judge_key"] == judge_key]
            r_vals = [r["redundancy"] for r in recs]
            c_vals = [r["coherence"] for r in recs]
            print(
                f"  {model_key:<22}  {judge_key:<18}  {avg(r_vals):>10}  "
                f"{avg(c_vals):>10}  {len(recs):>6}"
            )
        print(f"  {'·'*70}")
    print(f"  {'─'*70}")

    # --- Table 2: Average legibility by prompt type and judge ---
    print(f"\n{'═'*90}")
    print(f"  AGGREGATE 2 — Average legibility by prompt type (raw-trace models pooled)")
    print(f"{'═'*90}")
    print(f"  {'Type':<22}  {'Load':<12}  {'Judge':<18}  {'Avg Redund':>10}  {'Avg Coher':>10}  {'n':>4}")
    print(f"  {'─'*78}")
    prompt_types: list[str] = []
    seen_types: set[str] = set()
    for r in agg_records:
        key = (r["prompt_type"], r["reasoning_load"])
        if key not in seen_types:
            seen_types.add(key)
            prompt_types.append(key)
    prompt_types.sort(key=lambda x: x[1])  # sort by load
    for (p_type, p_load) in prompt_types:
        for judge_key in JUDGE_KEYS:
            recs = [
                r for r in agg_records
                if r["prompt_type"] == p_type and r["judge_key"] == judge_key
            ]
            r_vals = [r["redundancy"] for r in recs]
            c_vals = [r["coherence"] for r in recs]
            print(
                f"  {p_type:<22}  {p_load:<12}  {judge_key:<18}  {avg(r_vals):>10}  "
                f"{avg(c_vals):>10}  {len(recs):>4}"
            )
    print(f"  {'─'*78}")

    # --- Table 3: Inter-judge agreement by model ---
    print(f"\n{'═'*80}")
    print(f"  AGGREGATE 3 — Inter-judge agreement by model")
    print(f"  (Δ = |minimax_score − gemini_score|; high disagreement = max Δ ≥ {HIGH_DISAGREEMENT_THRESHOLD})")
    print(f"{'═'*80}")
    print(f"  {'Model':<22}  {'Avg ΔRedund':>12}  {'Avg ΔCoher':>11}  {'Max Δ':>7}  {'Flagged':>8}")
    print(f"  {'─'*65}")
    flagged_traces: list[dict] = []
    for model_key in effective_scored:
        mm_recs = {r["prompt_id"]: r for r in agg_records if r["model_key"] == model_key and r["judge_key"] == JUDGE_KEYS[0]}
        gm_recs = {r["prompt_id"]: r for r in agg_records if r["model_key"] == model_key and r["judge_key"] == JUDGE_KEYS[1]}
        shared_pids = set(mm_recs) & set(gm_recs)

        r_diffs, c_diffs, max_diffs = [], [], []
        for pid in shared_pids:
            rd = abs(mm_recs[pid]["redundancy"] - gm_recs[pid]["redundancy"])
            cd = abs(mm_recs[pid]["coherence"] - gm_recs[pid]["coherence"])
            r_diffs.append(rd)
            c_diffs.append(cd)
            max_d = max(rd, cd)
            max_diffs.append(max_d)
            if max_d >= HIGH_DISAGREEMENT_THRESHOLD:
                flagged_traces.append({
                    "model": model_key, "pid": pid,
                    "redund_diff": rd, "coher_diff": cd,
                    "minimax_r": mm_recs[pid]["redundancy"],
                    "minimax_c": mm_recs[pid]["coherence"],
                    "gemini_r": gm_recs[pid]["redundancy"],
                    "gemini_c": gm_recs[pid]["coherence"],
                })

        n_flagged = sum(1 for d in max_diffs if d >= HIGH_DISAGREEMENT_THRESHOLD)
        print(
            f"  {model_key:<22}  {avg(r_diffs):>12}  {avg(c_diffs):>11}  "
            f"{max(max_diffs) if max_diffs else 0:>7}  {n_flagged:>8}"
        )
    print(f"  {'─'*65}")

    if flagged_traces:
        print(f"\n  High-disagreement traces (Δ ≥ {HIGH_DISAGREEMENT_THRESHOLD} — legibility signal least reliable here):")
        print(f"  {'Model':<22}  {'Pid':<6}  {'Dim':<10}  {'MiniMax':>8}  {'Gemini':>7}  {'Diff':>5}")
        print(f"  {'·'*62}")
        for t in flagged_traces:
            if t["redund_diff"] >= HIGH_DISAGREEMENT_THRESHOLD:
                print(f"  {t['model']:<22}  {t['pid']:<6}  {'redundancy':<10}  {t['minimax_r']:>8}  {t['gemini_r']:>7}  {t['redund_diff']:>5}")
            if t["coher_diff"] >= HIGH_DISAGREEMENT_THRESHOLD:
                print(f"  {t['model']:<22}  {t['pid']:<6}  {'coherence':<10}  {t['minimax_c']:>8}  {t['gemini_c']:>7}  {t['coher_diff']:>5}")

    # --- Cost summary ---
    total_cost = sum(r["cost_usd"] for r in agg_records)
    print(f"\n  Phase 2 total judge cost: ${total_cost:.5f}")

    # --- Scope firewall reminder ---
    print(f"\n{'═'*90}")
    print(f"  SCOPE FIREWALL")
    print(f"  These scores measure LEGIBILITY only: is the trace readable and monitorable?")
    print(f"  They do NOT measure:")
    print(f"    - Correctness  (whether the answer is right — Phase 3)")
    print(f"    - Faithfulness (whether the trace drove the output — not measured here)")
    print(f"  Do not mix legibility scores into economy or correctness tables.")
    print(f"{'═'*90}")

    # --- Footer ---
    status = "ALL CALLS COMPLETED" if not has_error else "ERRORS DETECTED — see rows above"
    print(f"\n  {status}")
    print(f"  Records → results/phase2/{run_id}.jsonl")
    print(f"  Calls completed: {len(agg_records)} judge scores recorded")
    print()

    return 1 if has_error else 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Reasoning Benchmark runner")
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Run the smoke test across all available scored models and the Gemma anchor",
    )
    parser.add_argument(
        "--model",
        metavar="MODEL_KEY",
        default=None,
        help="Limit smoke test to a single model key (e.g. claude_sonnet_4_6)",
    )
    parser.add_argument(
        "--pilot",
        action="store_true",
        help="Run the Phase 1 pilot across all scored+anchor models",
    )
    parser.add_argument(
        "--prompts",
        metavar="P3,P5",
        default=",".join(PILOT_DEFAULT_PROMPTS),
        help=f"Comma-separated prompt IDs for the pilot (default: {','.join(PILOT_DEFAULT_PROMPTS)})",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Run Phase 1 full economy run: all 10 prompts × all scored+anchor models",
    )
    parser.add_argument(
        "--models",
        metavar="MODEL1,MODEL2",
        default=None,
        help="Restrict --full to these model keys only (e.g. opus_4_8,mistral_medium_3_5)",
    )
    parser.add_argument(
        "--validate-judges",
        action="store_true",
        help=(
            "Phase 2 gate: run both judges on Gemma traces only (English) "
            "for human verification before proceeding to Chinese traces"
        ),
    )
    parser.add_argument(
        "--judge",
        action="store_true",
        help=(
            "Phase 2 full legibility scoring: both judges on deepseek/glm/kimi + gemma. "
            "Run --validate-judges first and confirm results."
        ),
    )
    parser.add_argument(
        "--source-run-id",
        metavar="RUN_ID",
        default=None,
        help="Phase 1 full run ID to use as source (default: most recent results/full/*.jsonl)",
    )
    args = parser.parse_args()

    if args.smoke:
        code = run_smoke(model_filter=args.model)
        sys.exit(code)
    elif args.pilot:
        pid_list = [p.strip() for p in args.prompts.split(",") if p.strip()]
        code = run_pilot(prompt_ids=pid_list)
        sys.exit(code)
    elif args.full:
        mfilter = [m.strip() for m in args.models.split(",") if m.strip()] if args.models else None
        code = run_full(model_filter=mfilter)
        sys.exit(code)
    elif args.validate_judges:
        code = run_validate_judges(source_run_id=args.source_run_id)
        sys.exit(code)
    elif args.judge:
        code = run_judge(source_run_id=args.source_run_id)
        sys.exit(code)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
