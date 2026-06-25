from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Optional

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class CredentialMissingError(Exception):
    pass


class AdapterError(Exception):
    pass


@dataclass
class ModelResponse:
    answer_text: str
    input_tokens: int
    reasoning_tokens: int        # billed thinking tokens (count); 0 when not reported
    output_tokens: int           # visible answer tokens
    cache_read_tokens: int
    cache_write_tokens: int
    raw_reasoning_trace: Optional[str]   # CoT text, or None if not exposed
    trace_status: str            # "raw" | "summarized" | "count_only" | "absent"
    latency_s: float
    model_version: str           # pinned snapshot id reported by the provider
    raw_usage: dict = field(default_factory=dict)


class BaseAdapter:
    required_env: list[str] = []

    def __init__(self, model_key: str, config: dict) -> None:
        self.model_key = model_key
        self.config = config
        self._check_credentials()

    def _check_credentials(self) -> None:
        """
        Accept if (a) all required_env vars are present, OR (b) OPENROUTER_API_KEY
        is set (allows OpenAI-compatible adapters to fall back to OpenRouter).
        Subclasses that cannot use OpenRouter (e.g. local) override this.
        """
        direct_ok = all(os.environ.get(v) for v in self.required_env)
        openrouter_ok = bool(os.environ.get("OPENROUTER_API_KEY"))
        if not direct_ok and not openrouter_ok:
            raise CredentialMissingError(
                f"{self.model_key}: missing env var(s): {', '.join(self.required_env)}"
                " (and no OPENROUTER_API_KEY fallback)"
            )

    def _resolve_openai_creds(self) -> tuple[str, Optional[str], str, bool]:
        """
        Returns (api_key, base_url, model_id, via_openrouter).
        Prefers direct provider key; falls back to OpenRouter when absent.
        """
        direct_key_var = self.required_env[0] if self.required_env else None
        direct_key = os.environ.get(direct_key_var) if direct_key_var else None

        if direct_key:
            return (
                direct_key,
                self.config.get("base_url"),
                self.config["model_id"],
                False,
            )

        openrouter_key = os.environ.get("OPENROUTER_API_KEY")
        if openrouter_key:
            model_id = self.config.get(
                "openrouter_model_id", self.config["model_id"]
            )
            return openrouter_key, OPENROUTER_BASE_URL, model_id, True

        raise CredentialMissingError(
            f"{self.model_key}: no usable credential (need "
            f"{', '.join(self.required_env)} or OPENROUTER_API_KEY)"
        )

    def call(self, prompt: str, thinking_budget: int = 4096) -> ModelResponse:
        raise NotImplementedError


# Shared utility for providers that embed reasoning in <think>...</think> tags.
_THINK_PATTERN = re.compile(r"<think>(.*?)</think>\s*", re.DOTALL)


def extract_think_tags(text: str) -> tuple[Optional[str], str]:
    """
    Returns (reasoning_text, answer_text).
    reasoning_text is None when no <think> block is found.
    """
    m = _THINK_PATTERN.search(text)
    if m:
        return m.group(1).strip(), text[m.end():].strip()
    return None, text


def estimate_tokens(text: str) -> int:
    """Rough token count: ~4 UTF-8 bytes per token (good enough for CJK/EN mix)."""
    return max(0, len(text.encode("utf-8")) // 4)


def split_token_estimate(
    reasoning_text: Optional[str],
    answer_text: str,
    total_completion: int,
) -> tuple[int, int]:
    """
    Proportionally split total_completion into (reasoning_tokens, output_tokens)
    based on character length when the provider does not report them separately.
    """
    if not reasoning_text:
        return 0, total_completion
    r_len = len(reasoning_text.encode("utf-8"))
    a_len = len(answer_text.encode("utf-8"))
    total_len = r_len + a_len or 1
    reasoning = round(total_completion * r_len / total_len)
    output = total_completion - reasoning
    return reasoning, output
