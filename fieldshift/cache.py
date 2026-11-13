"""File-based JSON / GIF cache under fieldshift/cache/."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CACHE_DIR = Path(__file__).resolve().parent / "cache"
MOCK_DIR = Path(__file__).resolve().parent.parent / "mock"


def cache_path(name: str) -> Path:
    """Return the path for a named cache file (e.g. demo_iowa.json)."""
    return CACHE_DIR / name


def mock_path(name: str) -> Path:
    """Return the path for a labelled MOCK JSON file."""
    return MOCK_DIR / name


def read_json(name: str, *, from_mock: bool = False) -> dict[str, Any] | list[Any] | None:
    """Load a JSON cache or mock file, or None if missing."""
    path = mock_path(name) if from_mock else cache_path(name)
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def write_json(name: str, payload: dict[str, Any] | list[Any]) -> Path:
    """Write a JSON cache file and return its path."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = cache_path(name)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return path
