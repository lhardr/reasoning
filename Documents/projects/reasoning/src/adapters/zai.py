"""Zhipu AI GLM 5.2 adapter — trace_exposure: raw.

Uses the OpenAI-compatible endpoint at open.bigmodel.cn.
GLM-Z1 reasoning models expose raw CoT via reasoning_content (same field name as
DeepSeek). Falls back to <think> tag parsing if the field is absent.
Verify model_id and field names against Zhipu AI docs at run time.
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


class ZaiAdapter(BaseAdapter):
    required_env = ["ZAI_API_KEY"]

    def call(self, prompt: str, thinking_budget: int = 4096) -> ModelResponse:
        from openai import OpenAI

        client = OpenAI(
            api_key=os.environ["ZAI_API_KEY"],
            base_url=self.config.get(
                "base_url", "https://open.bigmodel.cn/api/paas/v4/"
            ),
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
            raise AdapterError(f"glm_5_2 API error: {exc}") from exc

        msg = resp.choices[0].message
        answer = msg.content or ""

        reasoning = getattr(msg, "reasoning_content", None)
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
