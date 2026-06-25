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
from src.model_resolver import print_resolution_table, resolve_models
from src.storage import RESULTS_DIR, save_result, save_trace

# ---------------------------------------------------------------------------
# Smoke test constants
# ---------------------------------------------------------------------------

SMOKE_PROMPT = (
    "What is 15 + 27? Work through this step by step, then give your final answer."
)

SMOKE_ROLES = {"scored", "anchor"}

# Models where reasoning_tokens MUST be > 0 — zero is a regression.
# gpt_5_5: count_only (reasoning count reported, no text)
# deepseek_v4 / glm_5_2 / kimi_k2_7: raw (text present, tokens estimated or direct)
# claude_sonnet_4_6: summarized (thinking block present, tokens estimated or direct)
# gemma_4: raw (local, tokens estimated from text)
MUST_HAVE_REASONING_TOKENS: set[str] = {
    "deepseek_v4",
    "glm_5_2",
    "kimi_k2_7",
    "gpt_5_5",
    "claude_sonnet_4_6",
    "gemma_4",
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
    print(f"  COST PROJECTION — Full run ({full_prompts} prompts × 6 models)")
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
    args = parser.parse_args()

    if args.smoke:
        code = run_smoke(model_filter=args.model)
        sys.exit(code)
    elif args.pilot:
        pid_list = [p.strip() for p in args.prompts.split(",") if p.strip()]
        code = run_pilot(prompt_ids=pid_list)
        sys.exit(code)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
