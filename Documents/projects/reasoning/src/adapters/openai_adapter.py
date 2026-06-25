"""OpenAI GPT-5.5 adapter — trace_exposure: count_only.

Raw CoT is hidden. The reasoning token COUNT is captured from the usage object.
Uses the Chat Completions API; usage.completion_tokens_details.reasoning_tokens
carries the count for reasoning ("o"-series) models.
If GPT-5.5 ships as a Responses API-only model, switch to client.responses.create()
and read usage.output_tokens_details.reasoning_tokens.
"""
from __future__ import annotations

import os
import time

from .base import AdapterError, BaseAdapter, ModelResponse


class OpenAIAdapter(BaseAdapter):
    required_env = ["OPENAI_API_KEY"]

    def call(self, prompt: str, thinking_budget: int = 4096) -> ModelResponse:
        from openai import OpenAI

        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

        try:
            t0 = time.perf_counter()
            resp = client.chat.completions.create(
                model=self.config["model_id"],
                messages=[{"role": "user", "content": prompt}],
                # max_completion_tokens controls total output incl. reasoning for o-models
                max_completion_tokens=thinking_budget + 512,
            )
            latency = time.perf_counter() - t0
        except Exception as exc:
            raise AdapterError(f"gpt_5_5 API error: {exc}") from exc

        answer = resp.choices[0].message.content or ""
        usage = resp.usage
        raw = usage.model_dump() if hasattr(usage, "model_dump") else {}

        # Reasoning token count — hidden CoT, count only.
        comp_details = getattr(usage, "completion_tokens_details", None)
        reasoning_tokens = (
            getattr(comp_details, "reasoning_tokens", 0) or 0
            if comp_details
            else 0
        )

        # Also try Responses API field name in case model uses that schema
        if reasoning_tokens == 0:
            out_details = getattr(usage, "output_tokens_details", None)
            reasoning_tokens = (
                getattr(out_details, "reasoning_tokens", 0) or 0
                if out_details
                else 0
            )

        total_completion = usage.completion_tokens
        output_tokens = max(0, total_completion - reasoning_tokens)

        cache_read = (
            getattr(
                getattr(usage, "prompt_tokens_details", None),
                "cached_tokens",
                0,
            )
            or 0
        )

        return ModelResponse(
            answer_text=answer,
            input_tokens=usage.prompt_tokens,
            reasoning_tokens=reasoning_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_read,
            cache_write_tokens=0,
            raw_reasoning_trace=None,   # raw CoT is hidden by OpenAI
            trace_status="count_only",
            latency_s=latency,
            model_version=resp.model,
            raw_usage=raw,
        )
