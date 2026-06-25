"""Gemma 4 local adapter via Ollama — trace_exposure: raw.

Calls the Ollama REST API at http://localhost:11434. No API key required.
Tries the Ollama `think: true` parameter first (Ollama ≥0.5 with compatible
model); falls back to parsing <think>...</think> tags from the response content.
Token counts come from Ollama's eval_count / prompt_eval_count fields.
Reasoning tokens are estimated proportionally when not reported separately.
"""
from __future__ import annotations

import json
import time

import requests

from .base import (
    AdapterError,
    BaseAdapter,
    ModelResponse,
    extract_think_tags,
    split_token_estimate,
)


class LocalAdapter(BaseAdapter):
    required_env: list[str] = []  # local model, no credentials

    def _check_credentials(self) -> None:
        pass  # Ollama needs no credential; connection error reported at call time

    def call(self, prompt: str, thinking_budget: int = 4096) -> ModelResponse:
        base = self.config.get("ollama_url", "http://localhost:11434")
        model = self.config["model_id"]

        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "think": True,  # Ollama ≥0.5 thinking support; silently ignored if unsupported
            "options": {"num_predict": thinking_budget + 512},
        }

        try:
            t0 = time.perf_counter()
            r = requests.post(f"{base}/api/chat", json=payload, timeout=300)
            latency = time.perf_counter() - t0
            r.raise_for_status()
            data = r.json()
        except Exception as exc:
            raise AdapterError(f"gemma_4 Ollama error: {exc}") from exc

        msg = data.get("message", {})
        full_content = msg.get("content", "")

        # Ollama ≥0.5: thinking in message.thinking field
        reasoning: str | None = msg.get("thinking") or None
        answer = full_content

        # Fallback: parse <think> tags from content
        if reasoning is None:
            reasoning, answer = extract_think_tags(full_content)

        input_tokens: int = data.get("prompt_eval_count", 0) or 0
        total_completion: int = data.get("eval_count", 0) or 0

        reasoning_tokens, output_tokens = split_token_estimate(
            reasoning, answer, total_completion
        )

        # Ollama eval_duration is in nanoseconds
        raw = {
            "prompt_eval_count": input_tokens,
            "eval_count": total_completion,
            "eval_duration_ns": data.get("eval_duration"),
            "load_duration_ns": data.get("load_duration"),
            "thinking_tokens_estimated": True,
        }

        return ModelResponse(
            answer_text=answer,
            input_tokens=input_tokens,
            reasoning_tokens=reasoning_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=0,
            cache_write_tokens=0,
            raw_reasoning_trace=reasoning,
            trace_status="raw" if reasoning else "absent",
            latency_s=latency,
            model_version=data.get("model", model),
            raw_usage=raw,
        )
