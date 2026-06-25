from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Optional

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
    reasoning_effort: str,
    results_dir: Optional[Path] = None,
    extra: Optional[dict] = None,
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
        "reasoning_effort": reasoning_effort,
        "answer_text": response.answer_text,
        "raw_reasoning_trace": response.raw_reasoning_trace,
        "trace_status": response.trace_status,
        "tokens": {
            "input": account.input_tokens,
            "reasoning": account.reasoning_tokens,
            "reasoning_source": response.reasoning_source,
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
    if extra:
        record.update(extra)

    out_dir = results_dir if results_dir is not None else RESULTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{run_id}.jsonl"
    with open(out_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return record


def save_trace(
    *,
    traces_dir: Path,
    run_id: str,
    model_key: str,
    prompt_id: str,
    prompt_meta: dict,
    prompt_text: str,
    answer_text: str,
    reasoning_trace: Optional[str],
    trace_status: str,
    reasoning_tokens: int,
    reasoning_source: str,
) -> Path:
    """
    Write a human-readable plain-text file with the raw reasoning trace.
    Saved to traces_dir/<model_key>_<prompt_id>.txt so a reader can eyeball
    the language probe without parsing JSONL.
    """
    traces_dir.mkdir(parents=True, exist_ok=True)
    path = traces_dir / f"{model_key}_{prompt_id}.txt"

    p_type = prompt_meta.get("type", "")
    p_probe = prompt_meta.get("language_probe", "")
    sep = "=" * 72

    with open(path, "w", encoding="utf-8") as f:
        f.write(f"run_id:           {run_id}\n")
        f.write(f"model:            {model_key}\n")
        f.write(f"prompt_id:        {prompt_id}  ({p_type} / {p_probe})\n")
        f.write(f"trace_status:     {trace_status}\n")
        f.write(f"reasoning_tokens: {reasoning_tokens}  [{reasoning_source}]\n")
        f.write(f"\n{sep}\nPROMPT\n{sep}\n")
        f.write(prompt_text.strip() + "\n")
        f.write(f"\n{sep}\nREASONING TRACE\n{sep}\n")
        if reasoning_trace:
            f.write(reasoning_trace.strip() + "\n")
        else:
            f.write(f"[{trace_status} — reasoning text not exposed]\n")
        f.write(f"\n{sep}\nANSWER\n{sep}\n")
        f.write(answer_text.strip() + "\n")

    return path
