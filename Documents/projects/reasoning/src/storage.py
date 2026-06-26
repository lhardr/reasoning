from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .adapters.base import ModelResponse
    from .accounting import TokenAccount
    from .judge import JudgeResponse

RESULTS_DIR = Path(__file__).parent.parent / "results"
PHASE2_DIR = RESULTS_DIR / "phase2"


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


def save_langcost_result(
    *,
    run_id: str,
    model_key: str,
    task_id: str,
    prompt_lang: str,
    prompt_text: str,
    response: "ModelResponse",
    account: "TokenAccount",
    cost_usd: float,
    pricing_snapshot_date: str,
    thinking_budget: int,
    reasoning_effort: str,
    reasoning_chars: int,
    output_chars: int,
    regime: str,
    language_metric: dict,
    results_dir: Path,
) -> dict:
    """
    Persist one (model, task, lang) langcost record to results/langcost/<run_id>.jsonl.
    Fields follow the Phase 1 structure, extended with per-language dimensions.
    """
    record = {
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model_key": model_key,
        "model_version": response.model_version,
        "task_id": task_id,
        "prompt_lang": prompt_lang,
        "prompt_text": prompt_text,
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
        "reasoning_chars": reasoning_chars,
        "output_chars": output_chars,
        "cost_usd": cost_usd,
        "pricing_snapshot_date": pricing_snapshot_date,
        "latency_s": round(response.latency_s, 3),
        "regime": regime,
        "language_metric": language_metric,
        "raw_usage": response.raw_usage,
    }

    results_dir.mkdir(parents=True, exist_ok=True)
    out_path = results_dir / f"{run_id}.jsonl"
    with open(out_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return record


def save_langcost_trace(
    *,
    traces_dir: Path,
    model_key: str,
    task_id: str,
    prompt_lang: str,
    prompt_text: str,
    answer_text: str,
    reasoning_trace: Optional[str],
    trace_status: str,
    reasoning_tokens: int,
    reasoning_source: str,
) -> Path:
    """
    Write human-readable trace file to traces_dir/<model>_<task>_<lang>.txt.
    """
    traces_dir.mkdir(parents=True, exist_ok=True)
    path = traces_dir / f"{model_key}_{task_id}_{prompt_lang}.txt"

    sep = "=" * 72
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"model:            {model_key}\n")
        f.write(f"task_id:          {task_id}\n")
        f.write(f"prompt_lang:      {prompt_lang}\n")
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


def save_phase2_result(
    *,
    run_id: str,
    source_run_id: str,
    model_key: str,
    prompt_id: str,
    prompt_type: str,
    language_probe: str,
    reasoning_load: str,
    judge_key: str,
    judge_response: "JudgeResponse",
    agreement: Optional[dict] = None,
    phase1_language_metric: Optional[dict] = None,
    trace_status: str,
    results_dir: Optional[Path] = None,
) -> dict:
    """
    Persist one (model, prompt, judge) Phase 2 legibility record.

    FIREWALL: no correctness or faithfulness fields are stored here.
    Legibility scores are kept strictly separate from Phase 1 economy records.
    """
    record = {
        "phase": 2,
        "run_id": run_id,
        "source_run_id": source_run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model_key": model_key,
        "prompt_id": prompt_id,
        "prompt_type": prompt_type,
        "language_probe": language_probe,
        "reasoning_load": reasoning_load,
        "trace_status": trace_status,
        "judge": judge_key,
        "judge_model_version": judge_response.model_version,
        # Legibility scores — do not mix into economy or correctness tables
        "scores": judge_response.scores,
        "justifications": judge_response.justifications,
        "parse_ok": judge_response.parse_ok,
        "parse_error": judge_response.parse_error,
        "agreement": agreement,
        # Phase 1 language metric carried for reference only — not re-scored here
        "phase1_language_metric": phase1_language_metric,
        "judge_tokens": {
            "input": judge_response.input_tokens,
            "output": judge_response.output_tokens,
        },
        "cost_usd": judge_response.cost_usd,
        "latency_s": round(judge_response.latency_s, 3),
    }

    out_dir = results_dir if results_dir is not None else PHASE2_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{run_id}.jsonl"
    with open(out_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return record
