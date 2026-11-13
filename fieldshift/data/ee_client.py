"""Earth Engine initialization (service account) with demo-mode fallback.

Never log or print private key material. Exception messages are sanitized.
"""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fieldshift.config import clear_settings_cache, get_settings

_INITIALIZED = False
_LAST_ERROR: str | None = None


@dataclass(frozen=True)
class EEStatus:
    """Public status for UI / CLI (no secrets)."""

    configured: bool
    demo_mode: bool
    initialized: bool
    project: str
    service_account_set: bool
    error: str | None = None


def _sanitize_error(exc: BaseException) -> str:
    """Return a short error string that cannot contain key material."""
    msg = str(exc)
    # Allow known safe operational messages through; drop anything that looks like a key.
    if "BEGIN PRIVATE KEY" in msg or "private_key" in msg or len(msg) > 400:
        if "not registered to use Earth Engine" in msg:
            return (
                f"{type(exc).__name__}: GCP project is not registered for Earth Engine "
                "(open Cloud Console → Earth Engine → register the project)"
            )
        return f"{type(exc).__name__}: credential init failed (details redacted)"
    return f"{type(exc).__name__}: {msg}"


def _looks_like_json_object(text: str) -> bool:
    """True if text is (or starts as) a JSON object — including Cloud multiline secrets."""
    stripped = text.strip()
    return stripped.startswith("{") and stripped.endswith("}")


def _resolve_key_material(raw: str | dict[str, Any]) -> tuple[str | None, dict[str, Any] | None]:
    """Return (key_file_path, key_dict).

    Accepts:
    - a dict (already parsed)
    - inline JSON text (Streamlit Cloud / secrets.toml multi-line string)
    - a filesystem path to a ``.json`` key file

    Never treats JSON text as a filesystem path.
    """
    if isinstance(raw, dict):
        return None, raw

    text = str(raw).strip()
    if not text:
        return None, None

    # Inline JSON (Community Cloud / TOML """...""") — parse only, never as a path
    if _looks_like_json_object(text) or text.startswith("{"):
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError("EE_PRIVATE_KEY_JSON looks like JSON but failed to parse") from exc
        if not isinstance(parsed, dict):
            raise ValueError("EE_PRIVATE_KEY_JSON must be a JSON object")
        return None, parsed

    path = Path(text)
    if path.is_file():
        return str(path.resolve()), None

    if text.endswith(".json"):
        return str(path), None

    raise ValueError("EE_PRIVATE_KEY_JSON must be a .json file path or inline JSON object")


def _credentials_from_key_dict(ee: Any, email: str, key_dict: dict[str, Any]) -> Any:
    """Build ServiceAccountCredentials from an in-memory JSON dict (Cloud / inline secrets).

    Tries ``key_data=`` first; if unsupported, writes a temp file (never logged) and uses
    the file-path constructor.
    """
    try:
        return ee.ServiceAccountCredentials(email, key_data=key_dict)
    except TypeError:
        pass

    # Fallback for APIs that only accept a key file path
    tmp = tempfile.NamedTemporaryFile(  # noqa: SIM115 — kept open until process exit is OK
        mode="w",
        suffix=".json",
        delete=False,
        encoding="utf-8",
    )
    try:
        json.dump(key_dict, tmp)
        tmp.flush()
    finally:
        tmp.close()
    return ee.ServiceAccountCredentials(email, tmp.name)


def init_ee(*, force: bool = False) -> EEStatus:
    """Initialize the Earth Engine client if credentials exist.

    Resolution order is handled by ``get_settings`` (st.secrets > env > key file).
    Returns status; does not raise on missing credentials (demo mode).
    """
    global _INITIALIZED, _LAST_ERROR

    clear_settings_cache()
    settings = get_settings()

    if not settings.ee_configured:
        _INITIALIZED = False
        _LAST_ERROR = None
        return EEStatus(
            configured=False,
            demo_mode=True,
            initialized=False,
            project="",
            service_account_set=False,
            error=None,
        )

    if _INITIALIZED and not force:
        return ee_status()

    try:
        import ee

        key_file, key_dict = _resolve_key_material(settings.ee_private_key_json)
        email = settings.ee_service_account
        project = settings.ee_project

        if key_file is not None:
            if not Path(key_file).is_file():
                raise FileNotFoundError("EE service-account key file not found")
            credentials = ee.ServiceAccountCredentials(email, key_file)
        elif key_dict is not None:
            credentials = _credentials_from_key_dict(ee, email, key_dict)
        else:
            raise ValueError("No usable EE private key material")

        ee.Initialize(credentials, project=project)
        _INITIALIZED = True
        _LAST_ERROR = None
    except Exception as exc:  # noqa: BLE001 — never surface raw exception args (may hold paths/JSON)
        _INITIALIZED = False
        _LAST_ERROR = _sanitize_error(exc)

    return ee_status()


def ee_status() -> EEStatus:
    """Return current EE configuration / init status without secrets."""
    settings = get_settings()
    return EEStatus(
        configured=settings.ee_configured,
        demo_mode=(not settings.ee_configured) or (not _INITIALIZED),
        initialized=_INITIALIZED,
        project=settings.ee_project[:64] if settings.ee_project else "",
        service_account_set=bool(settings.ee_service_account),
        error=_LAST_ERROR,
    )
