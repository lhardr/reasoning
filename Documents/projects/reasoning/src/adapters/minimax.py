"""MiniMax adapter stub — role: judge, Phase 2 only.

Not called in Phase 0. Raises AdapterError if accidentally invoked.
"""
from __future__ import annotations

from .base import AdapterError, BaseAdapter, ModelResponse


class MinimaxAdapter(BaseAdapter):
    required_env: list[str] = []

    def call(self, prompt: str, thinking_budget: int = 4096) -> ModelResponse:
        raise AdapterError(
            "minimax is a Phase 2 judge — not called in Phase 0"
        )
