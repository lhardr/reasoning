"""Anthropic Claude Sonnet 4.6 adapter — trace_exposure: summarized.

Direct path (ANTHROPIC_API_KEY): uses the Anthropic SDK with extended thinking
enabled. The thinking block contains Anthropic's summarized CoT.

OpenRouter fallback path (OPENROUTER_API_KEY): uses the OpenAI SDK with
extra_body to pass the thinking parameter. OpenRouter's handling of thinking
blocks varies — the smoke test will show what actually comes through and report
a PASS or MISMATCH accordingly.

Thinking token count sources (tried in order):
  1. usage.thinking_tokens
  2. usage.output_tokens_details.thinking_tokens
  3. Proportional estimate from thinking text vs total output_tokens
"""
from __future__ import annotations

import time

from .base import AdapterError, BaseAdapter, ModelResponse, split_token_estimate, extract_think_tags


class AnthropicAdapter(BaseAdapter):
    required_env = ["ANTHROPIC_API_KEY"]

    def call(self, prompt: str, thinking_budget: int = 4096) -> ModelResponse:
        import os
        if os.environ.get("ANTHROPIC_API_KEY"):
            return self._call_direct(prompt, thinking_budget)
        return self._call_via_openrouter(prompt, thinking_budget)

    # ------------------------------------------------------------------
    # Direct Anthropic SDK path
    # ------------------------------------------------------------------

    def _call_direct(self, prompt: str, thinking_budget: int) -> ModelResponse:
        import anthropic

        client = anthropic.Anthropic(api_key=__import__("os").environ["ANTHROPIC_API_KEY"])

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

        reasoning_tokens: int | None = getattr(usage, "thinking_tokens", None)
        if reasoning_tokens is None:
            out_details = getattr(usage, "output_tokens_details", None)
            if out_details is not None:
                reasoning_tokens = getattr(out_details, "thinking_tokens", None)
        if reasoning_tokens is None:
            reasoning_tokens, _ = split_token_estimate(
                thinking_text, answer_text, usage.output_tokens
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
            raw_reasoning_trace=thinking_text,
            trace_status="summarized" if thinking_text else "absent",
            latency_s=latency,
            model_version=resp.model,
            raw_usage=raw,
        )

    # ------------------------------------------------------------------
    # OpenRouter fallback path (OpenAI-compatible SDK)
    # ------------------------------------------------------------------

    def _call_via_openrouter(self, prompt: str, thinking_budget: int) -> ModelResponse:
        import os
        from openai import OpenAI
        from .base import OPENROUTER_BASE_URL

        or_key = os.environ.get("OPENROUTER_API_KEY")
        if not or_key:
            raise AdapterError("claude_sonnet_4_6: no ANTHROPIC_API_KEY or OPENROUTER_API_KEY")

        model_id = self.config.get("openrouter_model_id", self.config["model_id"])
        client = OpenAI(api_key=or_key, base_url=OPENROUTER_BASE_URL)

        try:
            t0 = time.perf_counter()
            resp = client.chat.completions.create(
                model=model_id,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=thinking_budget + 512,
                extra_body={
                    "thinking": {"type": "enabled", "budget_tokens": thinking_budget}
                },
            )
            latency = time.perf_counter() - t0
        except Exception as exc:
            raise AdapterError(
                f"claude_sonnet_4_6 via OpenRouter API error: {exc}"
            ) from exc

        msg = resp.choices[0].message
        raw_content = msg.content or ""

        # OpenRouter may pass thinking as <thinking> tags, a separate field, or strip it.
        reasoning = getattr(msg, "reasoning", None) or getattr(msg, "thinking", None)
        if reasoning is None:
            import re
            m = re.search(r"<thinking>(.*?)</thinking>\s*", raw_content, re.DOTALL)
            if m:
                reasoning = m.group(1).strip()
                answer = raw_content[m.end():].strip()
            else:
                reasoning, answer = extract_think_tags(raw_content)
                if reasoning is None:
                    answer = raw_content
        else:
            answer = raw_content

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
            raw["thinking_tokens_estimated"] = True

        return ModelResponse(
            answer_text=answer,
            input_tokens=usage.prompt_tokens,
            reasoning_tokens=reasoning_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=0,
            cache_write_tokens=0,
            raw_reasoning_trace=reasoning,
            trace_status="summarized" if reasoning else "absent",
            latency_s=latency,
            model_version=resp.model,
            raw_usage=raw,
        )
