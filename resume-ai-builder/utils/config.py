"""Configuration loading from Streamlit secrets, environment and ``.env``."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

from utils.file_utils import PROJECT_ROOT


@lru_cache(maxsize=1)
def _load_env() -> None:
    load_dotenv(PROJECT_ROOT / ".env", override=False)


@lru_cache(maxsize=1)
def _secrets_file_exists() -> bool:
    candidates = [
        PROJECT_ROOT / ".streamlit" / "secrets.toml",
        Path.cwd() / ".streamlit" / "secrets.toml",
        Path.home() / ".streamlit" / "secrets.toml",
    ]
    return any(p.is_file() for p in candidates)


def _from_streamlit_secrets(name: str) -> str | None:
    # Streamlit Community Cloud also exposes root-level secrets as env vars.
    if not _secrets_file_exists():
        return None
    try:
        import streamlit as st

        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:  # no secrets file, or not running under Streamlit
        return None
    return None


def get_setting(name: str, default: str = "") -> str:
    """Read a setting: Streamlit secrets first, then environment / ``.env``."""
    _load_env()
    value = _from_streamlit_secrets(name)
    if value is None:
        value = os.getenv(name)
    return (value if value is not None else default).strip()


def get_bool_setting(name: str, default: bool) -> bool:
    raw = get_setting(name, "")
    if not raw:
        return default
    return raw.lower() in {"1", "true", "yes", "on"}
