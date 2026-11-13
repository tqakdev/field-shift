"""Smoke-import every Streamlit entry module without executing the script body."""

from __future__ import annotations

import ast
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

PAGE_FILES = [
    REPO / "app.py",
    REPO / "views" / "home.py",
    REPO / "views" / "field.py",
    REPO / "views" / "how_it_works.py",
]


def test_streamlit_pages_parse() -> None:
    """Every Streamlit entry/view file must be valid Python."""
    for path in PAGE_FILES:
        source = path.read_text(encoding="utf-8")
        ast.parse(source, filename=str(path))


def test_import_ui_and_fieldshift_helpers() -> None:
    """Import UI helpers and package modules used by views (no Streamlit run)."""
    import fieldshift.cache  # noqa: F401
    import fieldshift.config  # noqa: F401
    import fieldshift.models  # noqa: F401
    import fieldshift.services  # noqa: F401
    import ui.charts  # noqa: F401
    import ui.map  # noqa: F401
    import ui.mock_banner  # noqa: F401
    import ui.source_caption  # noqa: F401
    import ui.strategy_cards  # noqa: F401
