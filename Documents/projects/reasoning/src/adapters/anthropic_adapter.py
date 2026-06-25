"""Anthropic Claude Sonnet 4.6 adapter — trace_exposure: summarized.

Extended thinking is enabled. The thinking block contains Anthropic's summarized
(not raw token-by-token) CoT. Billed thinking-token count is read from:
  1. usage.thinking_tokens  (preferred — direct field if available)
  2. usage.output_tokens_details.thinking_tokens  (per brief spec)
  3. Proportional estimate from thinking text length vs total output_tokens
     (fallback — annotated in raw_usage as "thinking_tokens_estimated": true)
"""
from __future__ import annotations

import os
import time

from .base import AdapterError, BaseAdapter, ModelResponse, split_token_estimate


class AnthropicAdapter(BaseAdapter):
    required_env = ["ANTHROPIC_API_KEY"]

    def call(self, prompt: str, thinking_budget: int = 4096) -> ModelResponse:
        import anthropic

        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

        try:
            t0 = time.perf_counter()
            resp = client.messages.create(
                model=self.config["model_id"],
                max_tokens=thinking_budget + 512,
                thinking={"type": "enabled", "budget_tokens": thinking_budget},
                messages=[{"role": "user", "content": prompt}],
            )
            latency = time.perf_counter() - t0
        except Exception as exc:
            raise AdapterError(f"claude_sonnet_4_6 API error: {exc}") from exc

        # Separate thinking blocks from text blocks
        thinking_texts: list[str] = []
        answer_parts: list[str] = []
        for block in resp.content:
            if block.type == "thinking":
                thinking_texts.append(getattr(block, "thinking", "") or "")
            elif block.type == "text":
                answer_parts.append(getattr(block, "text", "") or "")

        thinking_text = "\n\n".join(thinking_texts) if thinking_texts else None
        answer_text = "\n\n".join(answer_parts)

        usage = resp.usage
        raw = usage.model_dump() if hasattr(usage, "model_dump") else {}
        estimated = False

        # Try to read billed thinking tokens from API
        reasoning_tokens: int | None = None

        # Option 1: direct field
        reasoning_tokens = getattr(usage, "thinking_tokens", None)

        # Option 2: nested details (per brief spec)
        if reasoning_tokens is None:
            out_details = getattr(usage, "output_tokens_details", None)
            if out_details is not None:
                reasoning_tokens = getattr(out_details, "thinking_tokens", None)

        # Option 3: proportional estimate
        if reasoning_tokens is None:
            total_out = usage.output_tokens
            reasoning_tokens, _ = split_token_estimate(
                thinking_text, answer_text, total_out
            )
            estimated = True

        output_tokens = max(0, usage.output_tokens - reasoning_tokens)
        if estimated:
            raw["thinking_tokens_estimated"] = True

        return ModelResponse(
            answer_text=answer_text,
            input_tokens=usage.input_tokens,
            reasoning_tokens=reasoning_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
            cache_write_tokens=getattr(usage, "cache_creation_input_tokens", 0) or 0,
            raw_reasoning_trace=thinking_text,   # summarized, not raw CoT
            trace_status="summarized" if thinking_text else "absent",
            latency_s=latency,
            model_version=resp.model,
            raw_usage=raw,
        )
