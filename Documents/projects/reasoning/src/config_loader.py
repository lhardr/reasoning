from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).parent.parent / "config"


@lru_cache(maxsize=1)
def _raw_panel() -> dict:
    with open(CONFIG_DIR / "panel.yaml") as f:
        return yaml.safe_load(f)


def load_panel() -> dict:
    return _raw_panel()["models"]


def load_experiment() -> dict:
    """Return the experiment-level constants from panel.yaml (reasoning_effort, etc.)."""
    return _raw_panel().get("experiment", {})


@lru_cache(maxsize=1)
def load_pricing() -> dict:
    with open(CONFIG_DIR / "pricing.yaml") as f:
        return yaml.safe_load(f)
