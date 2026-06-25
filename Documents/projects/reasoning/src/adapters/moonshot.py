"""Moonshot AI Kimi K2.7 adapter — trace_exposure: raw.

Uses the OpenAI-compatible endpoint at api.moonshot.cn. Falls back to OpenRouter
when MOONSHOT_API_KEY is absent. Kimi reasoning models expose raw CoT via
reasoning_content; falls back to <think> tag parsing.
Verify model_id and field names against Moonshot AI docs at run time.
"""
from __future__ import annotations

import time

from .base import (
    AdapterError,
    BaseAdapter,
    ModelResponse,
    extract_think_tags,
    split_token_estimate,
)


class MoonshotAdapter(BaseAdapter):
    required_env = ["MOONSHOT_API_KEY"]

    def call(self, prompt: str, thinking_budget: int = 4096) -> ModelResponse:
        from openai import OpenAI

        api_key, base_url, model_id, _via_or = self._resolve_openai_creds()
        kwargs: dict = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        client = OpenAI(**kwargs)

        try:
            t0 = time.perf_counter()
            resp = client.chat.completions.create(
                model=model_id,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=thinking_budget + 512,
                # include_reasoning is permanent — ensures reasoning_content passthrough.
                extra_body={"include_reasoning": True},
            )
            latency = time.perf_counter() - t0
        except Exception as exc:
            raise AdapterError(f"kimi_k2_7 API error: {exc}") from exc

        msg = resp.choices[0].message
        answer = msg.content or ""

        reasoning = getattr(msg, "reasoning_content", None)
        if reasoning is None:
            reasoning = getattr(msg, "reasoning", None)
        if reasoning is None:
            reasoning, answer = extract_think_tags(answer)

        usage = resp.usage
        raw = usage.model_dump() if hasattr(usage, "model_dump") else {}

        total_completion = usage.completion_tokens
        comp_details = getattr(usage, "completion_tokens_details", None)
        api_reasoning = (
            getattr(comp_details, "reasoning_tokens", None) if comp_details else None
        )
        if api_reasoning is not None:
            reasoning_tokens = api_reasoning
            output_tokens = total_completion - reasoning_tokens
        else:
            reasoning_tokens, output_tokens = split_token_estimate(
                reasoning, answer, total_completion
            )

        cache_read = getattr(usage, "prompt_cache_hit_tokens", 0) or 0
        cache_write = getattr(usage, "prompt_cache_miss_tokens", 0) or 0

        if reasoning:
            trace_status = "raw"
        elif reasoning_tokens > 0:
            trace_status = "count_only"  # text stripped (e.g. via OpenRouter)
        else:
            trace_status = "absent"

        return ModelResponse(
            answer_text=answer,
            input_tokens=usage.prompt_tokens,
            reasoning_tokens=reasoning_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_read,
            cache_write_tokens=cache_write,
            raw_reasoning_trace=reasoning,
            trace_status=trace_status,
            latency_s=latency,
            model_version=resp.model,
            raw_usage=raw,
        )
