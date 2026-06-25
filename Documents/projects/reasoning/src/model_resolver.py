"""
Model resolution: map panel entries to the actual API slug that will be used,
and validate each one against the live OpenRouter catalog.

Called at the top of every run to print the resolution table and fail loudly
when a model cannot be confirmed.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Expected intended model names per key (human-readable label for loud failures)
INTENDED_NAMES: dict[str, str] = {
    "deepseek_v4": "DeepSeek V4 Pro (reasoning)",
    "glm_5_2": "GLM 5.2 (Z.ai)",
    "kimi_k2_7": "Kimi K2.7 (Moonshot)",
    "gpt_5_5": "GPT-5.5 (OpenAI)",
    "claude_sonnet_4_6": "Claude Sonnet 4.6 (Anthropic)",
    "gemma_4": "Gemma 4 (OpenRouter)",
    "minimax": "MiniMax M3 (judge)",
    "gemini_3_1_pro": "Gemini 3.1 Pro (judge)",
}

_or_model_set: set[str] | None = None


def _fetch_openrouter_models() -> set[str]:
    global _or_model_set
    if _or_model_set is not None:
        return _or_model_set
    or_key = os.environ.get("OPENROUTER_API_KEY")
    if not or_key:
        _or_model_set = set()
        return _or_model_set
    try:
        import requests
        r = requests.get(
            f"{OPENROUTER_BASE_URL}/models",
            headers={"Authorization": f"Bearer {or_key}"},
            timeout=15,
        )
        r.raise_for_status()
        _or_model_set = {m["id"] for m in r.json().get("data", [])}
    except Exception:
        _or_model_set = set()
    return _or_model_set


@dataclass
class ResolvedModel:
    key: str
    intended_name: str
    resolved_id: str
    provider: str   # "direct" | "openrouter" | "local"
    warning: Optional[str] = None


def resolve_models(panel: dict, model_keys: list[str]) -> list[ResolvedModel]:
    """
    For each model key, determine which API slug will be used and whether it
    is confirmed in the live OpenRouter catalog.
    Returns list of ResolvedModel, one per key.
    """
    or_models = _fetch_openrouter_models()
    results: list[ResolvedModel] = []

    for key in model_keys:
        cfg = panel.get(key, {})
        intended = INTENDED_NAMES.get(key, key)
        provider_type = cfg.get("provider", "unknown")

        # Local models do not use OpenRouter (none in current panel)
        if provider_type == "local":
            results.append(ResolvedModel(
                key=key,
                intended_name=intended,
                resolved_id=cfg.get("model_id", "?"),
                provider="local",
                warning=None,
            ))
            continue

        # Determine which credential path will be used
        env_var = _required_env_var(provider_type)
        has_direct = bool(env_var and os.environ.get(env_var))
        has_or = bool(os.environ.get("OPENROUTER_API_KEY"))

        if has_direct:
            results.append(ResolvedModel(
                key=key,
                intended_name=intended,
                resolved_id=cfg.get("model_id", "?"),
                provider="direct",
                warning=None,
            ))
        elif has_or:
            or_id = cfg.get("openrouter_model_id")
            if not or_id:
                results.append(ResolvedModel(
                    key=key,
                    intended_name=intended,
                    resolved_id="MISSING",
                    provider="openrouter",
                    warning="No openrouter_model_id in panel.yaml",
                ))
                continue
            warning = None
            if or_models and or_id not in or_models:
                warning = (
                    f"NOT FOUND in live OpenRouter catalog: {or_id!r} "
                    f"— intended: {intended}"
                )
            results.append(ResolvedModel(
                key=key,
                intended_name=intended,
                resolved_id=or_id,
                provider="openrouter",
                warning=warning,
            ))
        else:
            results.append(ResolvedModel(
                key=key,
                intended_name=intended,
                resolved_id="NO CREDENTIAL",
                provider="none",
                warning=f"No direct key ({env_var}) or OPENROUTER_API_KEY",
            ))

    return results


def print_resolution_table(resolved: list[ResolvedModel]) -> int:
    """
    Print the model resolution table. Returns the number of hard errors
    (models with warnings that indicate the wrong model would be used).
    """
    print("\nModel Resolution")
    print("-" * 90)
    print(f"  {'Key':<22} {'Intended':<35} {'Resolved ID':<38} {'Via'}")
    print("-" * 90)
    hard_errors = 0
    for r in resolved:
        flag = ""
        if r.warning:
            flag = "  ← ERROR" if "NOT FOUND" in r.warning or "MISSING" in r.warning or "NO CREDENTIAL" in r.resolved_id else "  ← WARN"
            if "NOT FOUND" in r.warning or "MISSING" in r.warning:
                hard_errors += 1
        print(f"  {r.key:<22} {r.intended_name:<35} {r.resolved_id:<38} {r.provider}{flag}")
        if r.warning:
            print(f"  {'':22} !! {r.warning}")
    print("-" * 90)
    return hard_errors


def _required_env_var(provider: str) -> str | None:
    return {
        "deepseek": "DEEPSEEK_API_KEY",
        "zai": "ZAI_API_KEY",
        "moonshot": "MOONSHOT_API_KEY",
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "gemma": None,           # Gemma uses OPENROUTER_API_KEY (checked via has_or)
        "minimax": "MINIMAX_API_KEY",
        "google": "GOOGLE_API_KEY",
        "local": None,
    }.get(provider)
