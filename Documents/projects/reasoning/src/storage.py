from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .adapters.base import ModelResponse
    from .accounting import TokenAccount

RESULTS_DIR = Path(__file__).parent.parent / "results"


def save_result(
    *,
    run_id: str,
    model_key: str,
    prompt: str,
    response: "ModelResponse",
    account: "TokenAccount",
    cost_usd: float,
    pricing_snapshot_date: str,
    thinking_budget: int,
) -> dict:
    """
    Persist one (model, prompt, run) record to results/<run_id>.jsonl.
    Each line is a self-contained JSON object.
    Correctness fields (score, correct) are reserved for Phase 3 — left absent here.
    """
    record = {
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model_key": model_key,
        "model_version": response.model_version,
        "prompt": prompt,
        "thinking_budget": thinking_budget,
        "answer_text": response.answer_text,
        "raw_reasoning_trace": response.raw_reasoning_trace,
        "trace_status": response.trace_status,
        "tokens": {
            "input": account.input_tokens,
            "reasoning": account.reasoning_tokens,
            "output": account.output_tokens,
            "cache_read": account.cache_read_tokens,
            "cache_write": account.cache_write_tokens,
            "reasoning_share": round(account.reasoning_share, 4),
        },
        "cost_usd": cost_usd,
        "pricing_snapshot_date": pricing_snapshot_date,
        "latency_s": round(response.latency_s, 3),
        "raw_usage": response.raw_usage,
        # Phase 3 placeholders — not populated here:
        # "correct": null,
        # "score": null,
    }

    RESULTS_DIR.mkdir(exist_ok=True)
    out_path = RESULTS_DIR / f"{run_id}.jsonl"
    with open(out_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return record
