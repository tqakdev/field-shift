"""Environment / Streamlit Secrets settings (never log secret values)."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_KEY_PATH = REPO_ROOT / "secrets" / "ee-key.json"


class Settings(BaseSettings):
    """Runtime configuration. Missing EE credentials → demo mode only."""

    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ee_service_account: str = ""
    ee_private_key_json: str = ""
    ee_project: str = ""

    llm_explain: bool = False
    openai_api_key: str = ""

    nass_api_key: str = ""
    ams_api_key: str = ""

    timelapse_url_ttl_seconds: int = 3600

    @property
    def ee_configured(self) -> bool:
        """True when Earth Engine service-account credentials are present."""
        return bool(
            self.ee_service_account and self.ee_private_key_json and self.ee_project
        )

    @property
    def demo_mode(self) -> bool:
        """App runs on cached / mock fields only when EE is not configured."""
        return not self.ee_configured


def _read_streamlit_secrets() -> dict[str, Any]:
    """Return flat secret key/values from st.secrets if Streamlit is running."""
    try:
        import streamlit as st

        if not hasattr(st, "secrets"):
            return {}
        raw = dict(st.secrets)
        # Allow nested [ee] table
        if "ee" in raw and hasattr(raw["ee"], "items"):
            nested = {str(k).upper(): raw["ee"][k] for k in raw["ee"]}
            flat = {str(k): raw[k] for k in raw if k != "ee"}
            flat.update(nested)
            return flat
        return {str(k): raw[k] for k in raw}
    except Exception:
        return {}


def _credentials_from_key_file(path: Path) -> dict[str, str]:
    """Load service-account email / project / JSON text from a key file path."""
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        "ee_service_account": str(data.get("client_email", "")),
        "ee_project": str(data.get("project_id", "")),
        # Store path so init_ee can use key_file= without embedding in process lists
        "ee_private_key_json": str(path.resolve()),
    }


@lru_cache
def get_settings() -> Settings:
    """Merge credentials. Priority: st.secrets > env > secrets/ee-key.json > Settings defaults."""
    base = Settings()
    updates: dict[str, str] = {}

    file_creds = _credentials_from_key_file(DEFAULT_KEY_PATH)
    updates.update({k: v for k, v in file_creds.items() if v})

    for field in (
        "ee_service_account",
        "ee_private_key_json",
        "ee_project",
        "nass_api_key",
        "ams_api_key",
    ):
        env_val = os.environ.get(field.upper(), "")
        if env_val:
            updates[field] = env_val

    st_secrets = _read_streamlit_secrets()
    mapping = {
        "EE_SERVICE_ACCOUNT": "ee_service_account",
        "EE_PRIVATE_KEY_JSON": "ee_private_key_json",
        "EE_PROJECT": "ee_project",
        "NASS_API_KEY": "nass_api_key",
        "AMS_API_KEY": "ams_api_key",
    }
    for upper, field in mapping.items():
        val = st_secrets.get(upper) or st_secrets.get(upper.lower())
        if val is None or val == "":
            continue
        if isinstance(val, dict):
            updates[field] = json.dumps(val)
        else:
            updates[field] = str(val)

    return base.model_copy(update=updates)


def is_demo_mode() -> bool:
    """Return True when live Earth Engine analysis is unavailable."""
    return get_settings().demo_mode


def clear_settings_cache() -> None:
    """Drop cached settings (used after writing secrets.toml)."""
    get_settings.cache_clear()
