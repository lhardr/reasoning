"""DeepSeek V4 adapter — trace_exposure: raw.

The deepseek-reasoner model returns reasoning_content (raw CoT) separately from
the answer in content. Token breakdown from usage; reasoning/output are split
proportionally when the API does not report them separately.
"""
from __future__ import annotations

import os
import time

from .base import (
    AdapterError,
    BaseAdapter,
    ModelResponse,
    extract_think_tags,
    split_token_estimate,
)


class DeepSeekAdapter(BaseAdapter):
    required_env = ["DEEPSEEK_API_KEY"]

    def call(self, prompt: str, thinking_budget: int = 4096) -> ModelResponse:
        from openai import OpenAI

        client = OpenAI(
            api_key=os.environ["DEEPSEEK_API_KEY"],
            base_url=self.config.get("base_url", "https://api.deepseek.com"),
        )

        try:
            t0 = time.perf_counter()
            resp = client.chat.completions.create(
                model=self.config["model_id"],
                messages=[{"role": "user", "content": prompt}],
                max_tokens=thinking_budget + 512,
            )
            latency = time.perf_counter() - t0
        except Exception as exc:
            raise AdapterError(f"deepseek_v4 API error: {exc}") from exc

        msg = resp.choices[0].message
        answer = msg.content or ""

        # DeepSeek reasoning models expose CoT via reasoning_content
        reasoning = getattr(msg, "reasoning_content", None)
        if reasoning is None:
            # Fallback: parse <think> tags from content
            reasoning, answer = extract_think_tags(answer)

        usage = resp.usage
        raw = usage.model_dump() if hasattr(usage, "model_dump") else {}

        total_completion = usage.completion_tokens

        # Try provider-reported split first
        comp_details = getattr(usage, "completion_tokens_details", None)
        api_reasoning_tokens = (
            getattr(comp_details, "reasoning_tokens", None) if comp_details else None
        )

        if api_reasoning_tokens is not None:
            reasoning_tokens = api_reasoning_tokens
            output_tokens = total_completion - reasoning_tokens
        else:
            reasoning_tokens, output_tokens = split_token_estimate(
                reasoning, answer, total_completion
            )

        cache_read = getattr(usage, "prompt_cache_hit_tokens", 0) or 0
        cache_write = getattr(usage, "prompt_cache_miss_tokens", 0) or 0

        return ModelResponse(
            answer_text=answer,
            input_tokens=usage.prompt_tokens,
            reasoning_tokens=reasoning_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_read,
            cache_write_tokens=cache_write,
            raw_reasoning_trace=reasoning,
            trace_status="raw" if reasoning else "absent",
            latency_s=latency,
            model_version=resp.model,
            raw_usage=raw,
        )
