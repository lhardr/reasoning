"""
Light-variance repro for the 5 models missing from the existing light-variance
dataset (results/variance/20260708T143500_variance.jsonl: 2 pass, 8 models,
80 cells). Closes that gap for: kimi_k3, inkling, gpt_5_6_sol, fable_5,
claude_opus_5.

Same design as run.py's run_variance() (--variance): baseline only (no
tools), all 10 light prompts (data/prompts.yaml), pinned dated
openrouter_model_id strings from panel.yaml where a dated pin exists
(kimi_k3, inkling) — gpt_5_6_sol/fable_5/claude_opus_5 have no dated
snapshot available (panel.yaml documents this per-model; using the undated
slug is the documented, deliberate choice, not an oversight). No alias
fallback on a dead pin. served_by logged on every row.

Anthropic-provider models in this set (fable_5, claude_opus_5) are called
with ANTHROPIC_API_KEY removed from the environment for the duration of the
run, forcing the OpenRouter route — matches the channel the original
--variance run used for claude_sonnet_4_6/opus_4_8, and matches what
run_opus5_panel.py / fable_5's own --heavy run already do.

Writes results/variance/<run_id>_variance_new5.jsonl via the shared
save_variance_result() helper — same schema as the existing variance file.
Never touches any existing results file.

Cost guard: stops (does not crash) if cumulative cost_usd reaches
PRICE_CAP_USD. Partial results remain valid data.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from src.accounting import build_account
from src.adapters import PROVIDER_MAP, CredentialMissingError
from src.adapters.base import AdapterError
from src.config_loader import load_panel, load_prompts
from src.cost import compute_cost
from src.model_resolver import assert_no_silent_direct_route, print_resolution_table, resolve_models
from src.storage import save_variance_result

NEW5_MODELS: list[str] = ["kimi_k3", "inkling", "gpt_5_6_sol", "fable_5", "claude_opus_5"]
PASSES = 2
REASONING_EFFORT = "high"
PRICE_CAP_USD = 2.0

DEAD_PIN_MARKERS: tuple[str, ...] = (
    "not found",
    "not a valid model",
    "does not exist",
    "no endpoints found",
    "invalid model",
    "no allowed providers",
    "model_not_found",
)


def _classify_pin_error(exc: Exception) -> str:
    msg = str(exc).lower()
    if any(marker in msg for marker in DEAD_PIN_MARKERS):
        return "dead_pin"
    return "error"


def main() -> int:
    panel = load_panel()
    prompts = load_prompts()
    all_prompt_ids = sorted(prompts.keys(), key=lambda p: int(p[1:]))

    model_keys = [k for k in NEW5_MODELS if k in panel]
    if len(model_keys) != len(NEW5_MODELS):
        missing = set(NEW5_MODELS) - set(model_keys)
        print(f"!! Missing from panel.yaml: {missing}")
        return 1

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "_variance_new5"
    n_calls = len(all_prompt_ids) * len(model_keys) * PASSES

    print(f"\n{'='*110}")
    print(f"  Light Variance Repro — 5 missing models   run_id={run_id}")
    print(f"  Prompts: {len(all_prompt_ids)} x models: {len(model_keys)} x passes: {PASSES} = {n_calls} calls")
    print(f"  baseline only, closed-book, no tools  |  reasoning_effort={REASONING_EFFORT!r}  |  price cap ${PRICE_CAP_USD}")
    print(f"  Pinned versions (panel.yaml openrouter_model_id):")
    for key in model_keys:
        print(f"    {key:<16} {panel[key].get('openrouter_model_id')}")
    print(f"{'='*110}")

    saved_anthropic_key = os.environ.pop("ANTHROPIC_API_KEY", None)
    if saved_anthropic_key:
        print(f"  !! ANTHROPIC_API_KEY temporarily removed from env — forcing OpenRouter route for fable_5/claude_opus_5.")

    total_cost = 0.0
    stopped_reason: str | None = None
    has_failure = False

    try:
        resolved = resolve_models(panel, model_keys)
        print_resolution_table(resolved)
        assert_no_silent_direct_route(panel, model_keys, allow_direct=False)
        print(
            f"\n  NOTE: catalog mismatches above are not a gate — dated snapshot slugs"
            f" can be absent from OpenRouter's /models listing while still callable."
            f" The real gate is assert_model_pin_honored() (adapters/base.py), which"
            f" checks the request variable (request_model_id) against panel.yaml before"
            f" the call — same convention as --variance."
        )

        dead_pins: dict[str, str] = {}
        rows: list[dict] = []

        col_hdr = (
            f"  {'Model':<16} {'Pass':>4} {'Inp':>6} {'Reas':>7} {'Out':>6}  "
            f"{'Cost($)':>10}  {'ServedBy':<14} {'ModelVersion':<38} Status"
        )
        col_sep = "  " + "-" * 112

        for pass_index in range(1, PASSES + 1):
            for pid in all_prompt_ids:
                if stopped_reason:
                    break
                p = prompts[pid]
                assert "facit" not in p, (
                    f"CRITICAL SECURITY VIOLATION: facit in request-path object for {pid}"
                )
                prompt_text: str = p["prompt"]

                print(f"\n{'='*110}")
                print(f"  Pass {pass_index}/{PASSES}  [{pid}]  {prompt_text[:90].strip()!r}")
                print(f"{'='*110}")
                print(col_hdr)
                print(col_sep)

                for key in model_keys:
                    if stopped_reason:
                        break
                    if key in dead_pins:
                        print(f"  {key:<16} {pass_index:>4}  SKIPPED — dead pin ({dead_pins[key][:60]})")
                        continue

                    if total_cost >= PRICE_CAP_USD:
                        stopped_reason = f"PRICE CAP reached before {key}/{pid}/pass{pass_index}: cum_cost=${total_cost:.4f} >= ${PRICE_CAP_USD}"
                        print(f"\n!!! {stopped_reason}")
                        break

                    cfg = panel[key]
                    provider = cfg["provider"]
                    thinking_budget: int = cfg.get("thinking_budget", 16384)
                    pinned_id = cfg.get("openrouter_model_id", cfg.get("model_id"))

                    cls = PROVIDER_MAP.get(provider)
                    if cls is None:
                        print(f"  {key:<16} SKIPPED (unknown provider: {provider})")
                        continue

                    try:
                        adapter = cls(key, cfg)
                    except CredentialMissingError as e:
                        print(f"  {key:<16} SKIPPED — {e}")
                        continue

                    try:
                        response = adapter.call(
                            prompt_text,
                            thinking_budget=thinking_budget,
                            reasoning_effort=REASONING_EFFORT,
                        )
                    except AdapterError as e:
                        classification = _classify_pin_error(e)
                        if classification == "dead_pin":
                            dead_pins[key] = str(e)
                            print(f"\n  !!!!!! DEAD PIN !!!!!!  {key} — {pinned_id!r} is not callable:")
                            print(f"  !!!!!!                  {e}")
                            print(f"  !!!!!!                  No fallback to alias. Skipping {key} for the rest of this run.\n")
                        else:
                            print(f"  {key:<16} {pass_index:>4}  ERROR — {e}")
                        save_variance_result(
                            run_id=run_id, model_key=key, prompt_id=pid, pass_index=pass_index,
                            pinned_model_id=pinned_id, status=classification, response=None, account=None,
                            cost_usd=None, pricing_snapshot_date=None, thinking_budget=thinking_budget,
                            reasoning_effort=REASONING_EFFORT, extra={"error": str(e)},
                        )
                        has_failure = True
                        continue
                    except Exception as e:
                        print(f"  {key:<16} {pass_index:>4}  ERROR — unexpected: {e}")
                        save_variance_result(
                            run_id=run_id, model_key=key, prompt_id=pid, pass_index=pass_index,
                            pinned_model_id=pinned_id, status="error", response=None, account=None,
                            cost_usd=None, pricing_snapshot_date=None, thinking_budget=thinking_budget,
                            reasoning_effort=REASONING_EFFORT, extra={"error": str(e)},
                        )
                        has_failure = True
                        continue

                    account = build_account(response)
                    cost_usd, snapshot_date = compute_cost(key, account)
                    total_cost += cost_usd

                    version_flag = "" if response.model_version == pinned_id else "  <- differs from pin (expected for undated slugs)"

                    save_variance_result(
                        run_id=run_id, model_key=key, prompt_id=pid, pass_index=pass_index,
                        pinned_model_id=pinned_id, status="ok", response=response, account=account,
                        cost_usd=cost_usd, pricing_snapshot_date=snapshot_date,
                        thinking_budget=thinking_budget, reasoning_effort=REASONING_EFFORT,
                    )
                    rows.append({
                        "model_key": key, "pass_index": pass_index, "pid": pid,
                        "reasoning": account.reasoning_tokens, "output": account.output_tokens,
                        "reasoning_source": response.reasoning_source,
                        "served_by": response.served_by, "model_version": response.model_version,
                        "cost_usd": cost_usd,
                    })

                    print(
                        f"  {key:<16} {pass_index:>4} {account.input_tokens:>6} {account.reasoning_tokens:>7}"
                        f" {account.output_tokens:>6}  ${cost_usd:>9.5f}  {str(response.served_by):<14} "
                        f"{response.model_version:<38} ok{version_flag}"
                    )

                print(col_sep)
            if stopped_reason:
                break

        print(f"\n{'='*100}")
        print(f"  SUMMARY")
        print(f"{'='*100}")
        if dead_pins:
            print(f"  DEAD PINS (never resolved, no fallback used):")
            for k, err in dead_pins.items():
                print(f"    {k:<16} {panel[k].get('openrouter_model_id')}")
                print(f"      {err}")
        else:
            print(f"  All {len(model_keys)} pinned/slug strings resolved and were callable.")

        served_by_seen: dict[str, set] = {}
        for r in rows:
            served_by_seen.setdefault(r["model_key"], set()).add(r["served_by"])
        print(f"\n  Underlying backend(s) reported by OpenRouter per model (fingerprint, not a version guarantee):")
        for key in model_keys:
            backends = served_by_seen.get(key)
            print(f"    {key:<16} {sorted(b for b in backends if b) if backends else '-'}")

        text_estimate_cells = [r for r in rows if r["reasoning_source"] != "api"]
        if text_estimate_cells:
            print(f"\n  {len(text_estimate_cells)} row(s) used reasoning_source=text_estimate (not comparable to API-reported counts):")
            for r in text_estimate_cells:
                print(f"    {r['model_key']:<16} pass={r['pass_index']} {r['pid']}")

        print(f"\n  TOTAL COST: ${total_cost:.4f}  (cap ${PRICE_CAP_USD})")
        if stopped_reason:
            print(f"  STOPPED EARLY: {stopped_reason}")
        status_line = "ALL CALLS COMPLETED" if not has_failure and not stopped_reason else "ISSUES DETECTED / STOPPED — see above"
        print(f"\n  {status_line}")
        print(f"  Structured records -> results/variance/{run_id}.jsonl")
        print()
        return 1 if (has_failure or stopped_reason) else 0

    finally:
        if saved_anthropic_key:
            os.environ["ANTHROPIC_API_KEY"] = saved_anthropic_key


if __name__ == "__main__":
    sys.exit(main())
