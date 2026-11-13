"""Load crop knowledge base from crops.json."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

CROPS_PATH = Path(__file__).with_name("crops.json")


@lru_cache(maxsize=1)
def load_crops() -> list[dict[str, Any]]:
    """Return the full crop catalogue (cached)."""
    return json.loads(CROPS_PATH.read_text())


def crop_by_id(crop_id: str) -> dict[str, Any]:
    for c in load_crops():
        if c["id"] == crop_id:
            return c
    raise KeyError(f"Unknown crop_id: {crop_id}")


def crops_needing_review() -> list[str]:
    return [c["id"] for c in load_crops() if c.get("needs_expert_review")]
