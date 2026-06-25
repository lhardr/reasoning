from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).parent.parent / "config"


@lru_cache(maxsize=1)
def load_panel() -> dict:
    with open(CONFIG_DIR / "panel.yaml") as f:
        data = yaml.safe_load(f)
    return data["models"]


@lru_cache(maxsize=1)
def load_pricing() -> dict:
    with open(CONFIG_DIR / "pricing.yaml") as f:
        return yaml.safe_load(f)
