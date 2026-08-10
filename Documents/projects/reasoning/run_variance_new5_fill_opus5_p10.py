"""
One-off completion call: claude_opus_5 / P10 / pass 2, the single row the
price cap cut off from run_variance_new5.py's run (results/variance/
20260810T121201_variance_new5.jsonl stopped at 99/100 with exactly this row
missing). Appends the one missing row to that same file under the same
run_id, via save_variance_result(), so the dataset schema/shape is
unchanged and claude_opus_5 ends up with 10/10 complete cells like the rest
of the panel.

Not a general-purpose script — hardcoded to this single call. Same route
(ANTHROPIC_API_KEY removed to force OpenRouter -> Amazon Bedrock, matching
every other row already in the file) and same params (thinking_budget,
reasoning_effort) as run_variance_new5.py.
"""
from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

load_dotenv()

from src.accounting import build_account
from src.adapters import PROVIDER_MAP, CredentialMissingError
from src.adapters.base import AdapterError
from src.config_loader import load_panel, load_prompts
from src.cost import compute_cost
from src.model_resolver import assert_no_silent_direct_route, print_resolution_table, resolve_models
from src.storage import save_variance_result

MODEL_KEY = "claude_opus_5"
PROMPT_ID = "P10"
PASS_INDEX = 2
RUN_ID = "20260810T121201_variance_new5"  # same run_id as the cut-off run — appends to the same file
REASONING_EFFORT = "high"
PRICE_CAP_USD = 0.50


def main() -> int:
    panel = load_panel()
    prompts = load_prompts()
    p = prompts[PROMPT_ID]
    assert "facit" not in p, f"CRITICAL SECURITY VIOLATION: facit in request-path object for {PROMPT_ID}"
    prompt_text: str = p["prompt"]

    cfg = panel[MODEL_KEY]
    thinking_budget = cfg.get("thinking_budget", 16384)
    pinned_id = cfg.get("openrouter_model_id", cfg.get("model_id"))

    saved_key = os.environ.pop("ANTHROPIC_API_KEY", None)
    if saved_key:
        print("!! ANTHROPIC_API_KEY temporarily removed — forcing OpenRouter route (matches the rest of this run's rows).")

    try:
        resolved = resolve_models(panel, [MODEL_KEY])
        print_resolution_table(resolved)
        assert_no_silent_direct_route(panel, [MODEL_KEY], allow_direct=False)

        cls = PROVIDER_MAP[cfg["provider"]]
        try:
            adapter = cls(MODEL_KEY, cfg)
        except CredentialMissingError as e:
            print(f"SKIPPED — {e}")
            return 1

        try:
            response = adapter.call(prompt_text, thinking_budget=thinking_budget, reasoning_effort=REASONING_EFFORT)
        except AdapterError as e:
            print(f"ERROR — {e}")
            save_variance_result(
                run_id=RUN_ID, model_key=MODEL_KEY, prompt_id=PROMPT_ID, pass_index=PASS_INDEX,
                pinned_model_id=pinned_id, status="error", response=None, account=None,
                cost_usd=None, pricing_snapshot_date=None, thinking_budget=thinking_budget,
                reasoning_effort=REASONING_EFFORT, extra={"error": str(e)},
            )
            return 1

        account = build_account(response)
        cost_usd, snapshot_date = compute_cost(MODEL_KEY, account)

        if cost_usd > PRICE_CAP_USD:
            print(f"!!! PRICE CAP: single call cost ${cost_usd:.4f} > cap ${PRICE_CAP_USD} — NOT saving, reporting only.")
            print(f"    (tokens: in={account.input_tokens} reas={account.reasoning_tokens} out={account.output_tokens})")
            return 1

        save_variance_result(
            run_id=RUN_ID, model_key=MODEL_KEY, prompt_id=PROMPT_ID, pass_index=PASS_INDEX,
            pinned_model_id=pinned_id, status="ok", response=response, account=account,
            cost_usd=cost_usd, pricing_snapshot_date=snapshot_date,
            thinking_budget=thinking_budget, reasoning_effort=REASONING_EFFORT,
        )
        print(
            f"  {MODEL_KEY:<16} pass{PASS_INDEX} in={account.input_tokens:>6} reas={account.reasoning_tokens:>7}"
            f" out={account.output_tokens:>6}  cost=${cost_usd:.5f}  served_by={response.served_by}"
            f"  model_version={response.model_version}  reasoning_source={response.reasoning_source}"
        )
        print(f"\n  TOTAL COST: ${cost_usd:.4f}  (cap ${PRICE_CAP_USD})")
        print(f"  Appended to results/variance/{RUN_ID}.jsonl")
        return 0
    finally:
        if saved_key:
            os.environ["ANTHROPIC_API_KEY"] = saved_key


if __name__ == "__main__":
    sys.exit(main())
