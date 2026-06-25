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
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Ensure project root on path so `src` is importable when run as a script.
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv

load_dotenv()

from src.accounting import build_account
from src.adapters import PROVIDER_MAP, CredentialMissingError
from src.adapters.base import AdapterError, ModelResponse
from src.config_loader import load_panel
from src.cost import compute_cost
from src.storage import save_result

# ---------------------------------------------------------------------------
# Expected trace_exposure per model (from panel.yaml "trace_exposure" field).
# The smoke test verifies actual behaviour against this table.
# ---------------------------------------------------------------------------

TRACE_RULES: dict[str, str] = {
    "raw": "raw_reasoning_trace is not None and trace_status == 'raw'",
    "summarized": "raw_reasoning_trace is not None and trace_status == 'summarized'",
    "count_only": "raw_reasoning_trace is None and trace_status == 'count_only' and reasoning_tokens > 0",
    "absent": "trace_status == 'absent'",
}

SMOKE_PROMPT = (
    "What is 15 + 27? Work through this step by step, then give your final answer."
)

# Models that participate in the smoke test (scored + anchor; judges skipped).
SMOKE_ROLES = {"scored", "anchor"}


def _verify_trace(
    response: ModelResponse, expected_exposure: Optional[str]
) -> tuple[bool, str]:
    """
    Check that the actual trace behaviour matches the expected exposure regime.
    Returns (passed, description).
    """
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
) -> str:
    return (
        f"{key:<22} {version:<28} {inp:>7} {reas:>9} {out:>7}  "
        f"{status:<12} ${cost:>8.5f}  {latency:>7.2f}s  {verify}"
    )


def run_smoke(model_filter: Optional[str] = None) -> None:
    panel = load_panel()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "_smoke"

    target_keys = [
        k
        for k, cfg in panel.items()
        if cfg.get("role") in SMOKE_ROLES
        and (model_filter is None or k == model_filter)
    ]

    print(f"\n{'='*100}")
    print(f"  Reasoning Benchmark — Smoke Test   run_id={run_id}")
    print(f"  Prompt: {SMOKE_PROMPT!r}")
    print(f"{'='*100}")
    print(
        f"\n{'Model':<22} {'Version':<28} {'Input':>7} {'Reasoning':>9} {'Output':>7}  "
        f"{'TraceStatus':<12} {'Cost(USD)':>10}  {'Latency':>8}  Verify"
    )
    print("-" * 120)

    for key in target_keys:
        cfg = panel[key]
        provider = cfg["provider"]
        expected_exposure: Optional[str] = cfg.get("trace_exposure")
        thinking_budget: int = cfg.get("thinking_budget", 4096)

        cls = PROVIDER_MAP.get(provider)
        if cls is None:
            print(f"{key:<22} SKIPPED (unknown provider: {provider})")
            continue

        # Instantiate adapter — raises CredentialMissingError if key absent
        try:
            adapter = cls(key, cfg)
        except CredentialMissingError as e:
            print(f"{key:<22} SKIPPED — {e}")
            continue

        # Call the model
        try:
            response = adapter.call(SMOKE_PROMPT, thinking_budget=thinking_budget)
        except AdapterError as e:
            print(f"{key:<22} ERROR    — {e}")
            continue
        except Exception as e:
            print(f"{key:<22} ERROR    — unexpected: {e}")
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
        )

        passed, detail = _verify_trace(response, expected_exposure)
        verify_label = "PASS" if passed else f"MISMATCH ({detail})"

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
                verify_label,
            )
        )

    print("-" * 120)
    print(f"\nResults written to results/{run_id}.jsonl\n")


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
    args = parser.parse_args()

    if args.smoke:
        run_smoke(model_filter=args.model)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
