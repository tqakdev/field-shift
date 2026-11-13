"""Unit tests: EE_PRIVATE_KEY_JSON accepts inline JSON (not only a file path)."""

from __future__ import annotations

import json

import pytest
from fieldshift.data.ee_client import _resolve_key_material


def test_resolve_inline_json_object() -> None:
    payload = {
        "type": "service_account",
        "project_id": "demo-project",
        "client_email": "sa@demo-project.iam.gserviceaccount.com",
        "private_key": "-----BEGIN PRIVATE KEY-----\nNOT_A_REAL_KEY\n-----END PRIVATE KEY-----\n",
    }
    text = json.dumps(payload)
    key_file, key_dict = _resolve_key_material(text)
    assert key_file is None
    assert key_dict is not None
    assert key_dict["project_id"] == "demo-project"


def test_resolve_inline_json_with_surrounding_whitespace() -> None:
    text = '\n  {"type": "service_account", "project_id": "x", "client_email": "a@b"}  \n'
    key_file, key_dict = _resolve_key_material(text)
    assert key_file is None
    assert key_dict is not None
    assert key_dict["type"] == "service_account"


def test_resolve_dict_passthrough() -> None:
    key_file, key_dict = _resolve_key_material({"type": "service_account"})
    assert key_file is None
    assert key_dict == {"type": "service_account"}


def test_resolve_rejects_invalid_json_object_prefix() -> None:
    with pytest.raises(ValueError, match="failed to parse"):
        _resolve_key_material("{not-json")
